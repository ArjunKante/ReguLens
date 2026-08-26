"""The scraper abstraction (Section 26).

`ProductScraper` is the common interface. `GenericProductPageScraper`
implements it using only strategies that work on any e-commerce page
(structured metadata, JSON-LD, OpenGraph, visible DOM text, generic <img>
tags) — it is the fallback that keeps LM-SCAN working even against a
marketplace with no dedicated adapter, and even after a known marketplace
changes its HTML (Section 27: "never assume Blinkit forever").

Platform-specific adapters (e.g. BlinkitScraper) subclass this and layer a
`CSS_SELECTOR` strategy with centralized, named selectors on top — they
never replace the generic strategies, only supplement them, so a selector
going stale degrades to "slightly lower confidence", not "zero data".
"""
from __future__ import annotations

import re
import urllib.parse
from abc import ABC, abstractmethod

from bs4 import BeautifulSoup

from app.nlp.patterns import find_field_candidates
from app.scraping.data import ExtractionStrategyName, FetchResult, FieldExtraction, ScrapedImage, ScrapedProduct
from app.scraping.extractors import (
    extract_image_urls,
    find_product_json_ld,
    parse_basic_meta,
    parse_json_ld,
    parse_open_graph,
    visible_text,
)
from app.scraping.fetcher import PageFetcher, PlaywrightPageFetcher

_PRICE_PATTERN = re.compile(r"[\d,]+(?:\.\d{1,2})?")


def hostname_matches(url: str, *registrable_domains: str) -> bool:
    """True if `url`'s hostname IS one of `registrable_domains`, or a proper
    subdomain of one (e.g. `www.blinkit.com`, `blackberry.blinkit.com`).

    Platform adapters previously matched with a plain substring test
    (`"blinkit.com" in url.lower()`), which a URL like
    `https://evil.example/?next=blinkit.com` or
    `https://blinkit.com.attacker.net/...` also satisfies — the first
    routes an attacker-controlled page through the Blinkit-specific
    selectors (low impact, just wrong extraction), but both patterns are
    exactly the kind of hostname check that must never be done by substring
    (Section 4/26 audit fix: "proper marketplace hostname validation")."""
    hostname = (urllib.parse.urlsplit(url).hostname or "").lower()
    if not hostname:
        return False
    return any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in (d.lower() for d in registrable_domains)
    )


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value)
    match = _PRICE_PATTERN.search(text.replace(",", ""))
    return float(match.group().replace(",", "")) if match else None


class ProductScraper(ABC):
    platform_name: str = "generic"
    max_images: int = 8

    def __init__(self, fetcher: PageFetcher | None = None):
        self.fetcher: PageFetcher = fetcher or PlaywrightPageFetcher()

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """Whether this scraper has a platform-specific adapter for `url`."""

    def fetch_page(self, url: str) -> FetchResult:
        return self.fetcher.fetch(url)

    @abstractmethod
    def extract_structured_data(self, html: str, url: str) -> list[FieldExtraction]:
        """JSON-LD + OpenGraph + other structured-metadata candidates."""

    @abstractmethod
    def extract_product_data(self, html: str, url: str) -> ScrapedProduct:
        """The full consolidated product record for this page."""

    @abstractmethod
    def extract_images(self, html: str, url: str) -> list[ScrapedImage]:
        ...


class GenericProductPageScraper(ProductScraper):
    """Platform-agnostic fallback scraper (Section 3/26)."""

    platform_name = "generic"

    def can_handle(self, url: str) -> bool:  # noqa: ARG002 - generic scraper accepts anything
        return True

    def extract_structured_data(self, html: str, url: str) -> list[FieldExtraction]:
        soup = BeautifulSoup(html, "lxml")
        candidates: list[FieldExtraction] = []

        json_ld_objects = parse_json_ld(soup)
        product = find_product_json_ld(json_ld_objects)
        if product:
            candidates.extend(self._fields_from_json_ld(product))

        og = parse_open_graph(soup)
        candidates.extend(self._fields_from_open_graph(og))

        return candidates

    def extract_images(self, html: str, url: str) -> list[ScrapedImage]:
        soup = BeautifulSoup(html, "lxml")
        images: list[ScrapedImage] = []
        seen: set[str] = set()

        json_ld_objects = parse_json_ld(soup)
        product = find_product_json_ld(json_ld_objects)
        if product:
            raw_images = product.get("image")
            if isinstance(raw_images, str):
                raw_images = [raw_images]
            if isinstance(raw_images, list):
                for img in raw_images:
                    img_url = img if isinstance(img, str) else (img.get("url") if isinstance(img, dict) else None)
                    if img_url and img_url not in seen:
                        seen.add(img_url)
                        images.append(ScrapedImage(url=img_url, alt_text="product image (JSON-LD)"))

        og = parse_open_graph(soup)
        if "og:image" in og and og["og:image"] not in seen:
            seen.add(og["og:image"])
            images.append(ScrapedImage(url=og["og:image"], alt_text="product image (OpenGraph)"))

        if len(images) < self.max_images:
            for img_url, alt in extract_image_urls(soup, url, self.max_images * 2):
                if img_url not in seen:
                    seen.add(img_url)
                    images.append(ScrapedImage(url=img_url, alt_text=alt))
                if len(images) >= self.max_images:
                    break

        return images[: self.max_images]

    def extract_product_data(self, html: str, url: str) -> ScrapedProduct:
        soup = BeautifulSoup(html, "lxml")
        meta = parse_basic_meta(soup)
        og = parse_open_graph(soup)
        json_ld_objects = parse_json_ld(soup)
        product_ld = find_product_json_ld(json_ld_objects)

        title = og.get("og:title") or (product_ld or {}).get("name") or meta.get("title")
        description = og.get("og:description") or (product_ld or {}).get("description") or meta.get("description")
        brand = None
        if product_ld:
            brand_field = product_ld.get("brand")
            if isinstance(brand_field, dict):
                brand = brand_field.get("name")
            elif isinstance(brand_field, str):
                brand = brand_field

        listed_price = None
        currency = None
        offers = (product_ld or {}).get("offers") if product_ld else None
        if isinstance(offers, list) and offers:
            offers = offers[0]
        if isinstance(offers, dict):
            listed_price = _to_float(offers.get("price"))
            currency = offers.get("priceCurrency")

        field_candidates = self.extract_structured_data(html, url)

        # Strategy 4/6: visible DOM text + fallback keyword/regex extraction,
        # applied last so structured-data candidates (higher confidence) are
        # preferred by consumers that pick the max-confidence candidate.
        text = visible_text(soup)
        for match in find_field_candidates(text):
            field_candidates.append(
                FieldExtraction(
                    field_name=match.field_name,
                    value=match.value,
                    strategy=ExtractionStrategyName.FALLBACK_TEXT,
                    confidence=match.base_confidence,
                    raw_snippet=match.raw_snippet,
                )
            )

        images = self.extract_images(html, url)

        return ScrapedProduct(
            platform=self.platform_name,
            source_url=url,
            page_title=meta.get("title"),
            title=title,
            brand=brand,
            description=description,
            listed_price=listed_price,
            mrp=None,
            currency=currency,
            field_candidates=field_candidates,
            images=images,
        )

    # --- internal helpers ---

    def _fields_from_json_ld(self, product: dict) -> list[FieldExtraction]:
        out: list[FieldExtraction] = []
        name = product.get("name")
        if name:
            out.append(
                FieldExtraction(
                    field_name="product_name",
                    value=str(name),
                    strategy=ExtractionStrategyName.JSON_LD,
                    confidence=0.95,
                    raw_snippet=str(name),
                )
            )
        # Note: schema.org Product.offers.price is the (often-discounted) selling
        # price shown to the buyer, NOT the statutory MRP — the two are legally
        # distinct concepts (MRP is the ceiling price; the listed price may be
        # lower). It is intentionally NOT emitted as an "mrp" field candidate
        # here, to avoid manufacturing a false MRP-mismatch finding against the
        # actual MRP declaration found in page text/images. It is instead
        # captured separately as ScrapedProduct.listed_price (see caller).
        brand = product.get("brand")
        brand_name = brand.get("name") if isinstance(brand, dict) else brand
        manufacturer = product.get("manufacturer")
        manufacturer_name = manufacturer.get("name") if isinstance(manufacturer, dict) else manufacturer
        if manufacturer_name:
            out.append(
                FieldExtraction(
                    field_name="manufacturer_name",
                    value=str(manufacturer_name),
                    strategy=ExtractionStrategyName.JSON_LD,
                    confidence=0.85,
                    raw_snippet=str(manufacturer_name),
                )
            )
        elif brand_name:
            # Brand is a weaker proxy for manufacturer — low confidence, never
            # silently treated as equivalent to an explicit manufacturer declaration.
            out.append(
                FieldExtraction(
                    field_name="manufacturer_name",
                    value=str(brand_name),
                    strategy=ExtractionStrategyName.JSON_LD,
                    confidence=0.3,
                    raw_snippet=f"brand: {brand_name} (weak proxy, not an explicit manufacturer declaration)",
                )
            )
        return out

    def _fields_from_open_graph(self, og: dict[str, str]) -> list[FieldExtraction]:
        out: list[FieldExtraction] = []
        if "og:title" in og:
            out.append(
                FieldExtraction(
                    field_name="product_name",
                    value=og["og:title"],
                    strategy=ExtractionStrategyName.OPEN_GRAPH,
                    confidence=0.6,
                    raw_snippet=og["og:title"],
                )
            )
        return out
