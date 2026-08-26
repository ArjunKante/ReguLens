"""Flipkart.com product-page adapter (Section 3/26).

Verified against a live Flipkart product page rather than guessed from
memory — but title only; see below for what that excludes. Flipkart's
"Product Details" panel is a genuine label:value specification table
(`Brand`, `Quantity`, `Country of Origin`, ...) whose *row shape* — not any
class name — is what this adapter actually relies on, via the same
marketplace-agnostic `extract_table_label_value_pairs` heuristic the Amazon
adapter uses. That table has no stable id, so unlike Amazon's table
extraction this is left unscoped (searches every table on the page);
`extract_table_label_value_pairs` already discards any table that doesn't
look like a real spec sheet.

Deliberately not attempted: grabbing MRP from a raw price element by class
name (e.g. a guessed `_3I9_wc`/`yRaY8j`-style selector). AmazonScraper tried
exactly that and, even after two rounds of narrowing the selector, it still
matched the wrong price on a live page — Flipkart shows the same failure
mode risk (a "similar products" rail sharing price classes with the primary
listing) and its selectors were never live-verified to begin with, only
recalled from memory. Rather than ship an equally unverified version of a
bug already proven real elsewhere, MRP here comes only from the label:value
table above (an explicit "MRP"/"M.R.P" labeled row is unambiguous) and the
inherited GenericProductPageScraper fallback-text regex.
"""
from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from app.scraping.base import GenericProductPageScraper, hostname_matches
from app.scraping.data import ExtractionStrategyName, FieldExtraction, ScrapedProduct
from app.scraping.extractors import extract_table_label_value_pairs, field_candidates_from_label_value_pairs

logger = logging.getLogger(__name__)

# Best-effort only (Section 27: broad, not exact — Flipkart's hashed classes
# churn often); the generic JSON-LD/OpenGraph/fallback-text strategies and
# the label:value table extraction below are the resilient part of this
# adapter, not these.
TITLE_SELECTORS: list[str] = ["span.VU-ZEz", "span.B_NuCI", "h1 span"]


class FlipkartScraper(GenericProductPageScraper):
    platform_name = "flipkart"

    def can_handle(self, url: str) -> bool:
        return hostname_matches(url, "flipkart.com")

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

        # No CSS-selector MRP guess here — see the module docstring for why
        # that was deliberately not attempted. MRP comes only from the
        # label:value table below and the inherited generic fallback-text
        # regex.
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
