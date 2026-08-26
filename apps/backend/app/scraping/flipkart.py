"""Flipkart.com product-page adapter (Section 3/26).

Verified against a live Flipkart product page rather than guessed from
memory. The "Product Details" panel is a genuine label:value specification
(`Brand`, `Quantity`, `Country of Origin`, "Manufactured By", "Net
Quantity", ...) — but as of a live-listing test this session (Demo
Hardening), it is **no longer a real `<table>` element at all**: this
module's own earlier version claimed it was and relied on
`extract_table_label_value_pairs`, which searches `soup.find_all("table")`
and — verified directly against a real captured Flipkart page — found
**zero** `<table>` tags, silently contributing nothing. The panel is now a
flex-div grid, each spec row its own `<div class="grid-formation-dynamic">`
containing exactly two child `<div>`s (label, value); see
`extract_div_grid_label_value_pairs` for that shape's extraction. With this
gone unnoticed, recall for MRP/net_quantity/manufacturer_name had been
resting entirely on the generic fallback-text regexes in app/nlp/patterns.py
— which is exactly why their unanchored ("bare ₹", bare "\\d+g") variants'
false positives were so damaging in practice (see that module's history):
there was no more-trustworthy structured candidate to outrank them with.

Deliberately not attempted: grabbing MRP from a raw price element by class
name (e.g. a guessed `_3I9_wc`/`yRaY8j`-style selector). AmazonScraper tried
exactly that and, even after two rounds of narrowing the selector, it still
matched the wrong price on a live page — Flipkart shows the same failure
mode risk (a "similar products" rail sharing price classes with the primary
listing) and its selectors were never live-verified to begin with, only
recalled from memory. A live capture also showed Flipkart's own spec grid
has no "MRP"/"M.R.P" row at all — MRP appears to be shown only as a
strikethrough price with no accompanying text label, which no text-based
strategy here can safely attribute. Rather than ship an equally unverified
CSS guess or a false-positive-prone bare-price fallback, MRP is left to
whatever the label:value extraction and the (now keyword-anchored) generic
fallback-text regex can honestly find — absence is reported as absence,
not fabricated.
"""
from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from app.scraping.base import GenericProductPageScraper, hostname_matches
from app.scraping.data import ExtractionStrategyName, FieldExtraction, ScrapedProduct
from app.scraping.extractors import (
    extract_div_grid_label_value_pairs,
    extract_table_label_value_pairs,
    field_candidates_from_label_value_pairs,
)

logger = logging.getLogger(__name__)

# Best-effort only (Section 27: broad, not exact — Flipkart's hashed classes
# churn often); the generic JSON-LD/OpenGraph/fallback-text strategies and
# the label:value table extraction below are the resilient part of this
# adapter, not these.
#
# `span.VU-ZEz`/`span.B_NuCI`/`h1 span` (the original selectors here) no
# longer match anything on a live page as of this session's live-listing
# testing (Demo Hardening) — Flipkart's title is now a bare `<h1>` with only
# hashed classes and no child `<span>` at all, e.g.
# `<h1 class="v1zwn21n ...">Lay's Stax Original Potato Crisps Chips Can Pack
# Chips (163 g)</h1>`. Rather than chase specific hashed class names (which
# the module docstring already predicts will churn again), `h1` is kept as a
# broad last-resort match — same tradeoff the Amazon/Blinkit adapters make
# already (Section 27: broad match beats a brittle exact one).
TITLE_SELECTORS: list[str] = ["span.VU-ZEz", "span.B_NuCI", "h1 span", "h1"]

# Live-verified (Demo Hardening) — `.grid-formation-dynamic` itself is a
# one-child wrapper; the row proper (containing exactly a label div, a
# value div, and one empty spacer/icon div) is its direct child, so the
# selector goes one level in. Not a hashed/build-specific class — stable
# across the whole page's ~35 spec rows on the captured listing — but
# still treated as best-effort (Section 27) like every other selector
# here, since Flipkart could rename it in a future deploy the same way
# TITLE_SELECTORS's classes churned.
DIV_GRID_ROW_SELECTORS: list[str] = [".grid-formation-dynamic > div"]


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
            # Always wins over the parent class's generic og:title/<title>
            # fallback, not just when that came up empty (see amazon.py's
            # identical fix for the full rationale — same bug, same root
            # cause). Live-verified: Flipkart's `og:title` (and `<title>`)
            # both carry its full SEO boilerplate ("... Price in India - Buy
            # ... online at Flipkart.com"), so `product_title` displayed that
            # entire sentence instead of the clean name this selector
            # already had.
            product.title = title

        # No CSS-selector MRP guess here — see the module docstring for why
        # that was deliberately not attempted. MRP comes only from whatever
        # the label:value extraction below and the generic fallback-text
        # regex can honestly find.
        pairs = extract_table_label_value_pairs(soup)  # kept in case Flipkart ever reverts to a real <table>
        pairs += extract_div_grid_label_value_pairs(soup, DIV_GRID_ROW_SELECTORS)
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
