"""Blinkit-style product-page adapter (Section 3/26).

All Blinkit-specific knowledge is centralized in `SELECTORS` below (Section
27: "selectors should be centralized"). If Blinkit changes its markup, only
this dict needs updating — and even if every selector here goes stale, the
inherited GenericProductPageScraper strategies (JSON-LD/OpenGraph/fallback
text) still run, so extraction degrades gracefully rather than failing
outright (Section 26/27: "do not assume Blinkit forever").
"""
from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from app.scraping.base import GenericProductPageScraper, hostname_matches
from app.scraping.data import ExtractionStrategyName, FieldExtraction, ScrapedProduct

logger = logging.getLogger(__name__)

# Centralized, best-effort CSS selectors for Blinkit-style product pages.
# These are intentionally broad (class-name substrings via CSS attribute
# selectors) because marketplace frontends frequently rename hashed CSS
# classes on every deploy; broad matching plus the generic fallback below is
# more resilient than a single brittle exact selector.
SELECTORS: dict[str, list[str]] = {
    "product_name": ["h1[class*='ProductName']", "h1[class*='Title']", "h1"],
    "mrp": ["[class*='MRP']", "[class*='StrikedPrice']", "[data-testid*='mrp']"],
    "price": ["[class*='Price']:not([class*='MRP'])", "[data-testid*='price']"],
    "net_quantity": ["[class*='Quantity']", "[class*='Weight']", "[class*='PackSize']"],
    "manufacturer_name": ["[class*='Manufacturer']", "[class*='Mfg']"],
    "country_of_origin": ["[class*='CountryOfOrigin']", "[class*='Origin']"],
}


class BlinkitScraper(GenericProductPageScraper):
    platform_name = "blinkit"

    def can_handle(self, url: str) -> bool:
        return hostname_matches(url, "blinkit.com")

    def extract_product_data(self, html: str, url: str) -> ScrapedProduct:
        product = super().extract_product_data(html, url)
        product.platform = self.platform_name

        soup = BeautifulSoup(html, "lxml")
        for field_name, selectors in SELECTORS.items():
            candidate = self._first_match(soup, selectors)
            if candidate is None:
                continue
            target_field = "mrp" if field_name == "mrp" else field_name
            product.field_candidates.append(
                FieldExtraction(
                    field_name=target_field,
                    value=candidate,
                    strategy=ExtractionStrategyName.CSS_SELECTOR,
                    confidence=0.65,
                    raw_snippet=candidate,
                )
            )
            if field_name == "product_name" and not product.title:
                product.title = candidate

        return product

    @staticmethod
    def _first_match(soup: BeautifulSoup, selectors: list[str]) -> str | None:
        for selector in selectors:
            try:
                element = soup.select_one(selector)
            except Exception:  # noqa: BLE001 - a malformed/stale selector must not break extraction
                logger.warning("BlinkitScraper: selector failed, skipping: %s", selector)
                continue
            if element is not None:
                text = element.get_text(strip=True)
                if text:
                    return text
        return None
