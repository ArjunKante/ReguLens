"""Data structures produced by the scraping layer. Kept independent of the
ORM so extraction logic (Section 36) can be unit-tested against saved HTML
fixtures with no database or network involved."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ExtractionStrategyName(str, Enum):
    JSON_LD = "JSON_LD"
    OPEN_GRAPH = "OPEN_GRAPH"
    STRUCTURED_METADATA = "STRUCTURED_METADATA"
    DOM_VISIBLE = "DOM_VISIBLE"
    CSS_SELECTOR = "CSS_SELECTOR"
    FALLBACK_TEXT = "FALLBACK_TEXT"


@dataclass
class FieldExtraction:
    """One (strategy, value) candidate for one product field. The scraper
    emits every candidate it finds — even ones it doesn't ultimately prefer —
    so disagreement between strategies is visible (Section 3/27)."""

    field_name: str
    value: str
    strategy: ExtractionStrategyName
    confidence: float
    raw_snippet: str | None = None


@dataclass
class ScrapedImage:
    url: str
    alt_text: str | None = None


@dataclass
class ScrapedProduct:
    """Consolidated view built from all FieldExtraction candidates, plus the
    raw candidate list itself for full traceability.

    `title`/`brand`/`listed_price`/`mrp`/`discount`/`description` are
    marketplace-listing metadata that map directly onto Product columns.
    `field_candidates` are the Legal-Metrology-relevant declaration fields
    (app.rules.fields vocabulary) that flow into the Declaration table for
    the compliance engine — the two overlap in meaning (e.g. price) but are
    tracked separately because they answer different questions: "what does
    the marketplace say this listing is" vs. "what did we find that looks
    like a legally required declaration"."""

    platform: str
    source_url: str
    page_title: str | None = None
    title: str | None = None
    brand: str | None = None
    description: str | None = None
    listed_price: float | None = None
    mrp: float | None = None
    currency: str | None = None
    discount: str | None = None
    field_candidates: list[FieldExtraction] = field(default_factory=list)
    images: list[ScrapedImage] = field(default_factory=list)

    def best(self, field_name: str) -> FieldExtraction | None:
        candidates = [c for c in self.field_candidates if c.field_name == field_name]
        if not candidates:
            return None
        return max(candidates, key=lambda c: c.confidence)

    def all_for(self, field_name: str) -> list[FieldExtraction]:
        return [c for c in self.field_candidates if c.field_name == field_name]


@dataclass
class FetchResult:
    status: str  # matches WebFetchStatus values
    url: str
    html: str | None = None
    http_status_code: int | None = None
    error_message: str | None = None
    robots_txt_allowed: bool | None = None
    scraper_name: str | None = None
    scraper_version: str | None = None
    raw_metadata: dict = field(default_factory=dict)
