"""Flipkart.com product-page adapter (Section 3/26).

Verified against a live Flipkart product page rather than guessed from
memory. Flipkart's title/price CSS classes are hashed and have been known to
change on deploy (`_30jeq3`, `.Nx9bqj`, ... — kept here only as a
best-effort, low-confidence supplement), but its "Product Details" panel is
a genuine label:value specification table (`Brand`, `Quantity`, `Country of
Origin`, ...) whose *row shape* — not any class name — is what this adapter
actually relies on, via the same marketplace-agnostic
`extract_table_label_value_pairs` heuristic the Amazon adapter uses. That
table also has no stable id, so unlike Amazon this is left unscoped
(searches every table on the page); `extract_table_label_value_pairs`
already discards any table that doesn't look like a real spec sheet.
"""
from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from app.scraping.base import GenericProductPageScraper
from app.scraping.data import ExtractionStrategyName, FieldExtraction, ScrapedProduct
from app.scraping.extractors import extract_table_label_value_pairs, field_candidates_from_label_value_pairs

logger = logging.getLogger(__name__)

# Best-effort only (Section 27: broad, not exact — Flipkart's hashed classes
# churn often); the generic JSON-LD/OpenGraph/fallback-text strategies and
# the label:value table extraction below are the resilient part of this
# adapter, not these.
TITLE_SELECTORS: list[str] = ["span.VU-ZEz", "span.B_NuCI", "h1 span"]
# Single-class, not compound (Section 27: broad matching is more resilient)
# — Flipkart frequently reorders/adds utility classes on the same element
# across deploys, so requiring two specific classes together is a strictly
# worse bet than matching on the one that has historically identified the
# strikethrough "was" price.
MRP_SELECTORS: list[str] = ["div.yRaY8j", "div._3I9_wc"]


class FlipkartScraper(GenericProductPageScraper):
    platform_name = "flipkart"

    def can_handle(self, url: str) -> bool:
        return "flipkart.com" in url.lower()

    def extract_product_data(self, html: str, url: str) -> ScrapedProduct:
        product = super().extract_product_data(html, url)
        product.platform = self.platform_name

        soup = BeautifulSoup(html, "lxml")

        title = self._first_match(soup, TITLE_SELECTORS)
        if title:
            product.field_candidates.append(
                FieldExtraction(
                    field_name="product_name",
                    value=title,
                    strategy=ExtractionStrategyName.CSS_SELECTOR,
                    confidence=0.6,
                    raw_snippet=title,
                )
            )
            if not product.title:
                product.title = title

        mrp = self._first_match(soup, MRP_SELECTORS)
        if mrp:
            product.field_candidates.append(
                FieldExtraction(
                    field_name="mrp",
                    value=mrp,
                    strategy=ExtractionStrategyName.CSS_SELECTOR,
                    # See AmazonScraper's identical MRP confidence for why
                    # this must clear the generic fallback-text MRP ceiling
                    # (0.7, app/nlp/patterns.py) rather than sit below it:
                    # a same-confidence tie against the selling price (also
                    # a bare "₹<amount>" match) is resolved by text order,
                    # and the selling price is shown first.
                    confidence=0.75,
                    raw_snippet=mrp,
                )
            )

        pairs = extract_table_label_value_pairs(soup)
        product.field_candidates.extend(field_candidates_from_label_value_pairs(pairs))

        return product

    @staticmethod
    def _first_match(soup: BeautifulSoup, selectors: list[str]) -> str | None:
        for selector in selectors:
            try:
                element = soup.select_one(selector)
            except Exception:  # noqa: BLE001 - a malformed/stale selector must not break extraction
                logger.warning("FlipkartScraper: selector failed, skipping: %s", selector)
                continue
            if element is not None:
                text = element.get_text(strip=True)
                if text:
                    return text
        return None
