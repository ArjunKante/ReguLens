"""Low-level, source-agnostic HTML extraction helpers. Pure functions over a
BeautifulSoup tree — no network, no Playwright — so they're trivially unit
testable against saved fixtures (Section 36)."""
from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from app.rules import fields as F
from app.scraping.data import ExtractionStrategyName, FieldExtraction


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


# --- "Specifications table" / "detail bullets" extraction ------------------
#
# Amazon and Flipkart (and most marketplaces beyond Blinkit) render Legal
# Metrology declarations — net quantity, manufacturer, country of origin —
# not as free page text but as label:value rows: a genuine <table> of
# specifications (Flipkart's "Product Details"), or a bullet list where each
# <li> reads "Label : Value" (Amazon's #detailBullets_feature_div). Matching
# by *label text* here, instead of a marketplace's hashed/versioned CSS
# class names, is deliberate: verified against live Amazon.in and Flipkart
# product pages, the class names on the value cells churn across deploys but
# the label wording ("Manufacturer", "Country of Origin", "Net Quantity", a
# plain "Quantity") does not. This keeps both adapters working the same way
# Section 27 already requires of Blinkit: even if a marketplace's markup
# drifts, extraction degrades to "slightly lower confidence", not "zero
# data".


def _row_label_value_pairs(container: BeautifulSoup) -> list[tuple[str, str]]:
    """Reads every 2-cell <tr> under `container` as (label, value) — but
    only if most of the container's rows look that way, so an unrelated
    layout table (comparison carousels, review lists, ...) that happens to
    contain one stray 2-cell row isn't mistaken for a genuine spec sheet."""
    rows = container.find_all("tr")
    if not rows:
        return []
    pairs: list[tuple[str, str]] = []
    for row in rows:
        cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
        cells = [c for c in cells if c]
        if len(cells) == 2:
            pairs.append((cells[0], cells[1]))
    if len(pairs) < 2 or len(pairs) / len(rows) < 0.6:
        return []
    return pairs


def extract_table_label_value_pairs(
    soup: BeautifulSoup, container_selectors: list[str] | None = None
) -> list[tuple[str, str]]:
    """Extracts label:value pairs from specification-table-shaped markup.

    `container_selectors`, when given, scopes the search to specific known
    containers (e.g. Amazon's `#productDetails_techSpec_section_1`) instead
    of scanning every table on the page — pass this when a marketplace
    adapter knows a reliable container id/selector. Without it, every
    <table> on the page is checked and only ones that actually look like a
    spec sheet (see `_row_label_value_pairs`) contribute pairs, which is the
    right default for marketplaces (e.g. Flipkart) whose container classes
    are hashed/unstable but whose overall table *shape* is not."""
    containers = [soup.select(sel) for sel in container_selectors] if container_selectors else [soup.find_all("table")]
    pairs: list[tuple[str, str]] = []
    for group in containers:
        for element in group:
            pairs.extend(_row_label_value_pairs(element))
    return pairs


_BULLET_LABEL_VALUE = re.compile(
    r"^(?P<label>[A-Za-z][A-Za-z0-9 /&\-]{1,40}?)[\s‎‏]*:[\s‎‏]*(?P<value>.{1,150})$"
)


def extract_bullet_label_value_pairs(soup: BeautifulSoup, selectors: list[str]) -> list[tuple[str, str]]:
    """Amazon-style '<li>Label ‏ : ‎ Value</li>' bullet lists (e.g.
    #detailBullets_feature_div), where each bullet is one label:value
    declaration rendered as plain text rather than as table cells. Amazon
    surrounds the colon with invisible left/right-mark characters
    (U+200E/U+200F) for RTL-locale support; the pattern tolerates their
    presence or absence."""
    pairs: list[tuple[str, str]] = []
    for selector in selectors:
        for item in soup.select(selector):
            text = item.get_text(" ", strip=True)
            match = _BULLET_LABEL_VALUE.match(text)
            if match:
                pairs.append((match.group("label").strip(), match.group("value").strip()))
    return pairs


# Label keyword -> our field vocabulary (app/rules/fields.py). Matched by
# substring on the lowercased label, in order, so a more specific label
# (e.g. "net weight") should be listed before a more generic one it also
# contains. Deliberately conservative: a label with no match here is simply
# dropped rather than guessed at, per Section 7 ("do not fabricate a
# declaration the page didn't actually make").
SPEC_LABEL_FIELD_MAP: list[tuple[str, str]] = [
    ("country of origin", F.COUNTRY_OF_ORIGIN),
    ("net quantity", F.NET_QUANTITY),
    ("net weight", F.NET_QUANTITY),
    ("item weight", F.NET_QUANTITY),
    ("quantity", F.NET_QUANTITY),
    ("m.r.p", F.MRP),
    ("mrp", F.MRP),
    ("manufacturer", F.MANUFACTURER_NAME),
    ("packed by", F.PACKER_NAME),
    ("packer", F.PACKER_NAME),
    ("imported by", F.IMPORTER_NAME),
    ("importer", F.IMPORTER_NAME),
    ("marketed by", F.CONSUMER_CARE_NAME),
    ("customer care", F.CONSUMER_CARE_NAME),
    ("consumer care", F.CONSUMER_CARE_NAME),
    ("best before", F.BEST_BEFORE_DATE),
    ("use by", F.BEST_BEFORE_DATE),
    ("expiry", F.BEST_BEFORE_DATE),
    ("date of manufacture", F.MFG_DATE),
    ("manufacture date", F.MFG_DATE),
    ("mfg date", F.MFG_DATE),
]


def field_candidates_from_label_value_pairs(
    pairs: list[tuple[str, str]], *, confidence: float = 0.7
) -> list[FieldExtraction]:
    """Converts (label, value) pairs into FieldExtraction candidates for
    every label recognized by SPEC_LABEL_FIELD_MAP. Kept separate from the
    row/bullet extraction above so it can be reused unchanged by any adapter
    that produces label:value pairs, regardless of whether they came from a
    table or a bullet list."""
    candidates: list[FieldExtraction] = []
    for label, value in pairs:
        if not value:
            continue
        label_lower = label.lower()
        field_name = next((field for key, field in SPEC_LABEL_FIELD_MAP if key in label_lower), None)
        if field_name is None:
            continue
        candidates.append(
            FieldExtraction(
                field_name=field_name,
                value=value,
                strategy=ExtractionStrategyName.CSS_SELECTOR,
                confidence=confidence,
                raw_snippet=f"{label}: {value}",
            )
        )
    return candidates
