"""Low-level, source-agnostic HTML extraction helpers. Pure functions over a
BeautifulSoup tree — no network, no Playwright — so they're trivially unit
testable against saved fixtures (Section 36)."""
from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup


def parse_json_ld(soup: BeautifulSoup) -> list[dict]:
    """Returns every JSON-LD object on the page (Section 3, strategy #2).
    Handles single objects, arrays, and @graph wrappers, and never raises on
    malformed JSON — malformed script tags are simply skipped."""
    objects: list[dict] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text()
        if not raw or not raw.strip():
            continue
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = parsed if isinstance(parsed, list) else [parsed]
        for candidate in candidates:
            if isinstance(candidate, dict):
                if "@graph" in candidate and isinstance(candidate["@graph"], list):
                    objects.extend(o for o in candidate["@graph"] if isinstance(o, dict))
                else:
                    objects.append(candidate)
    return objects


def find_product_json_ld(objects: list[dict]) -> dict | None:
    for obj in objects:
        obj_type = obj.get("@type")
        types = obj_type if isinstance(obj_type, list) else [obj_type]
        if any(isinstance(t, str) and t.lower() == "product" for t in types):
            return obj
    return None


def parse_open_graph(soup: BeautifulSoup) -> dict[str, str]:
    """Section 3, strategy #3."""
    og: dict[str, str] = {}
    for tag in soup.find_all("meta"):
        prop = tag.get("property") or tag.get("name")
        if prop and prop.startswith("og:") and tag.get("content"):
            og[prop] = tag["content"]
    return og


def parse_basic_meta(soup: BeautifulSoup) -> dict[str, str]:
    meta: dict[str, str] = {}
    title_tag = soup.find("title")
    if title_tag and title_tag.get_text(strip=True):
        meta["title"] = title_tag.get_text(strip=True)
    description_tag = soup.find("meta", attrs={"name": "description"})
    if description_tag and description_tag.get("content"):
        meta["description"] = description_tag["content"]
    return meta


def visible_text(soup: BeautifulSoup, max_chars: int = 20000) -> str:
    """Section 3, strategy #4 (visible DOM content). Strips script/style and
    collapses whitespace so downstream regex matching in app/nlp/patterns.py
    works on clean text."""
    working = BeautifulSoup(str(soup), "lxml")
    for tag in working(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = working.get_text(separator=" | ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"(\s*\|\s*){2,}", " | ", text)
    return text.strip()[:max_chars]


def extract_image_urls(soup: BeautifulSoup, base_url: str, max_images: int) -> list[tuple[str, str | None]]:
    """Section 3: generic <img> extraction fallback, used when structured
    data doesn't supply a product image gallery."""
    import urllib.parse

    urls: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src")
        if not src:
            continue
        absolute = urllib.parse.urljoin(base_url, src)
        if absolute in seen:
            continue
        seen.add(absolute)
        urls.append((absolute, img.get("alt")))
        if len(urls) >= max_images:
            break
    return urls
