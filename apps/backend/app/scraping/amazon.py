"""Amazon.in product-page adapter (Section 3/26).

Verified against live Amazon.in product pages rather than guessed from
memory. Two things held true across the pages checked:

- `#productTitle` and the `.a-price`/`.a-price.a-text-price` price classes
  are Amazon's long-stable ids/classes for the title and selling/MRP price —
  worth a dedicated CSS_SELECTOR candidate.
- Net quantity / manufacturer / country of origin, when present at all,
  aren't under a stable class name — they're rows in Amazon's "detail
  bullets" list (`#detailBullets_feature_div li`, one label:value pair per
  `<li>`) or its technical-details table (`#productDetails_techSpec_section_1`).
  Grocery listings frequently have neither (MRP then only appears as plain
  "M.R.P: ₹X" text, e.g. in the "compare with similar items" block) — when
  that happens this adapter contributes nothing extra and the inherited
  GenericProductPageScraper strategies (JSON-LD/OpenGraph/fallback text
  regex, which does catch "M.R.P: ₹X") are what actually finds the value.
  That's intentional, not a gap: Section 27 requires extraction to degrade
  gracefully rather than depend on any one marketplace's markup forever.
"""
from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from app.scraping.base import GenericProductPageScraper
from app.scraping.data import ExtractionStrategyName, FieldExtraction, ScrapedProduct
from app.scraping.extractors import (
    extract_bullet_label_value_pairs,
    extract_table_label_value_pairs,
    field_candidates_from_label_value_pairs,
)

logger = logging.getLogger(__name__)

TITLE_SELECTORS: list[str] = ["#productTitle", "h1#title span#productTitle", "h1#title"]
MRP_SELECTORS: list[str] = ["span.a-price.a-text-price span.a-offscreen", ".basisPrice .a-offscreen"]

# Containers known (from live inspection) to hold Amazon's label:value
# declaration rows, when a given listing has them at all.
BULLET_CONTAINER_SELECTORS: list[str] = ["#detailBullets_feature_div li", "#productOverview_feature_div tr"]
TABLE_CONTAINER_SELECTORS: list[str] = [
    "#productDetails_techSpec_section_1",
    "#productDetails_detailBullets_sections1",
]


class AmazonScraper(GenericProductPageScraper):
    platform_name = "amazon"

    def can_handle(self, url: str) -> bool:
        return "amazon.in" in url.lower()

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
                    confidence=0.7,
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
                    # Deliberately above the generic fallback-text MRP
                    # ceiling (0.7 — app/nlp/patterns.py's bare "₹<amount>"
                    # pattern, which matches ANY rupee amount on the page,
                    # selling price included, with no label context). This
                    # selector specifically targets Amazon's strikethrough
                    # "was" price class, which the *selling* price never
                    # carries — verified live: without out-ranking the
                    # promiscuous fallback here, a tie on confidence is
                    # resolved in text order, and Amazon shows the selling
                    # price before the MRP, so the wrong one would win.
                    confidence=0.8,
                    raw_snippet=mrp,
                )
            )

        pairs = extract_table_label_value_pairs(soup, TABLE_CONTAINER_SELECTORS)
        pairs += extract_bullet_label_value_pairs(soup, BULLET_CONTAINER_SELECTORS)
        product.field_candidates.extend(field_candidates_from_label_value_pairs(pairs))

        return product

    @staticmethod
    def _first_match(soup: BeautifulSoup, selectors: list[str]) -> str | None:
        for selector in selectors:
            try:
                element = soup.select_one(selector)
            except Exception:  # noqa: BLE001 - a malformed/stale selector must not break extraction
                logger.warning("AmazonScraper: selector failed, skipping: %s", selector)
                continue
            if element is not None:
                text = element.get_text(strip=True)
                if text:
                    return text
        return None
