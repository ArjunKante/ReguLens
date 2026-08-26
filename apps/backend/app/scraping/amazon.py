"""Amazon.in product-page adapter (Section 3/26).

Verified against live Amazon.in product pages rather than guessed from
memory — including one dead end worth recording so it isn't re-attempted:

- `#productTitle` is Amazon's long-stable, unique id for the title — safe
  to match unscoped, confirmed correct against a real listing.
- Grabbing MRP from a `.a-price`-family price element was tried and
  abandoned. `.a-price.a-text-price` (the strikethrough "was" price) is not
  unique to the primary listing — a "compare with similar items" carousel,
  or even an alternate seller's offer for the *same* product, can carry the
  exact same class on a different price entirely. Two attempts at scoping
  this to a "primary buybox" container id (`#corePriceDisplay_desktop_feature_div`
  and similar) still picked up the wrong price on a real page — Amazon
  apparently renders other sellers' offers inside that same container for
  at least some grocery listings, so there is no CSS-only way to reliably
  tell "the real MRP" apart from "some other price" without confirmed,
  page-specific knowledge this adapter doesn't have. Rather than keep
  guessing increasingly specific selectors against an unverified DOM, MRP
  is deliberately left to the two strategies that *are* verified reliable:
  the label:value extraction below (an explicit "M.R.P"/"MRP" label paired
  with a value is a real, low-ambiguity signal) and the inherited
  GenericProductPageScraper fallback-text regex.
- Net quantity / manufacturer / country of origin, when present at all,
  aren't under a stable class name either — they're rows in Amazon's
  "detail bullets" list (`#detailBullets_feature_div li`, one label:value
  pair per `<li>`) or its technical-details table
  (`#productDetails_techSpec_section_1`). Grocery listings frequently have
  neither — when that happens this adapter contributes nothing extra and
  the inherited generic strategies are what actually find a value. That's
  intentional, not a gap: Section 27 requires extraction to degrade
  gracefully rather than depend on any one marketplace's markup forever.
"""
from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from app.scraping.base import GenericProductPageScraper, hostname_matches
from app.scraping.data import ExtractionStrategyName, FieldExtraction, ScrapedProduct
from app.scraping.extractors import (
    extract_bullet_label_value_pairs,
    extract_table_label_value_pairs,
    field_candidates_from_label_value_pairs,
)

logger = logging.getLogger(__name__)

TITLE_SELECTORS: list[str] = ["#productTitle", "h1#title span#productTitle", "h1#title"]

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
        return hostname_matches(url, "amazon.in")

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
            # Always wins over the generic og:title/JSON-LD/<title> chain
            # already applied by the parent class, not just when that chain
            # came up empty (`if not product.title` was previously a
            # near-dead guard, since the parent's meta-tag fallback chain
            # is truthy on almost every real page). This was a real,
            # live-verified bug (Demo Hardening live-listing test): Amazon.in
            # sets `og:title` to the bare literal string "Amazon" site-wide
            # rather than a per-product value, so `product_title` displayed
            # "Amazon" for every single Amazon inspection even though
            # #productTitle (long-stable, verified reliable — see module
            # docstring) had the real product name the whole time.
            product.title = title

        # No CSS-selector MRP guess here — see the module docstring for why
        # that was tried and abandoned. MRP comes only from the label:value
        # extraction below and the inherited generic fallback-text regex.
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
