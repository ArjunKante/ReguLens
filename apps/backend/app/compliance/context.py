"""Wraps everything the rule engine needs to know about one inspection's
extracted evidence into a single, query-friendly object, so validators never
touch the ORM/session directly (Section 11: keep validators generic and
data-driven)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.models.declaration import Declaration
from app.models.scraping import OCRResult, ProductImage, WebPage
from app.models.enums import WebFetchStatus

# Country-of-origin gating needs three states, not two (P0 audit fix:
# "imported/domestic/unknown classification"). The previous `is_imported:
# bool` collapsed "we positively found manufacturer evidence and no
# importer" and "we found no evidence about origin at all" into the same
# `False` — which then let `_country_of_origin_gate` report a confident
# NOT_APPLICABLE ("this is a domestic product") for an inspection that
# actually had no evidence to determine that from at all, e.g. a page fetch
# that failed with zero declarations extracted.
OriginStatus = Literal["IMPORTED", "DOMESTIC", "UNKNOWN"]


@dataclass
class InspectionContext:
    declarations: list[Declaration]
    web_pages: list[WebPage]
    images: list[ProductImage]
    ocr_results: list[OCRResult]
    is_tobacco_product: bool = False
    origin_status: OriginStatus = "UNKNOWN"

    _by_field: dict[str, list[Declaration]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self._by_field = {}
        for d in self.declarations:
            self._by_field.setdefault(d.field_name, []).append(d)

    def values_for(self, field_name: str) -> list[Declaration]:
        return self._by_field.get(field_name, [])

    def best(self, field_name: str) -> Declaration | None:
        values = self.values_for(field_name)
        if not values:
            return None
        return max(values, key=lambda d: d.confidence)

    def has_value(self, field_name: str) -> bool:
        d = self.best(field_name)
        return d is not None and bool((d.value or "").strip())

    def webpage_source_has_value(self, field_name: str) -> bool:
        """True only if a non-empty value for this field came from the listing
        page itself (WEBPAGE_TEXT / STRUCTURED_METADATA) — used by Rule 6(10),
        which requires display 'on the digital and electronic network'."""
        for d in self.values_for(field_name):
            if d.source_type in ("WEBPAGE_TEXT", "STRUCTURED_METADATA") and (d.value or "").strip():
                return True
        return False

    def distinct_values(self, field_name: str) -> list[Declaration]:
        """All declarations for a field, used by the consistency engine to
        detect cross-source disagreement."""
        return self.values_for(field_name)

    # --- Evidence-quality heuristics (Section 13: never do a naive "if missing then illegal") ---

    @property
    def webpage_fetch_succeeded(self) -> bool:
        return any(wp.fetch_status == WebFetchStatus.SUCCESS for wp in self.web_pages)

    @property
    def has_any_images(self) -> bool:
        return len(self.images) > 0

    @property
    def average_ocr_confidence(self) -> float | None:
        if not self.ocr_results:
            return None
        return sum(r.confidence for r in self.ocr_results) / len(self.ocr_results)

    @property
    def evidence_quality_score(self) -> float:
        """A 0..1 heuristic combining page-fetch success, image availability,
        and OCR confidence. Low scores push ambiguous findings toward
        NEEDS_MANUAL_REVIEW / UNABLE_TO_VERIFY instead of an automatic
        POTENTIAL_NON_COMPLIANCE, per Section 13's worked examples."""
        score = 0.0
        weight_total = 0.0

        weight_total += 1.0
        score += 1.0 if self.webpage_fetch_succeeded else 0.0

        weight_total += 1.0
        score += 1.0 if self.has_any_images else 0.3

        avg_ocr = self.average_ocr_confidence
        weight_total += 1.0
        if avg_ocr is not None:
            score += avg_ocr
        elif self.has_any_images:
            # Images were supplied but OCR produced no text at all (engine
            # failure, blank/corrupt image, unsupported format, ...). This
            # is a genuine evidence gap, not a neutral "unknown" — treating
            # it as a middling 0.5 (P0 audit fix: "failed OCR doesn't
            # become automatic non-compliance") could previously combine
            # with the `has_any_images` term above to land the overall
            # score exactly at 0.5, which `_absence_outcome` treats as
            # "not low quality" and confidently reports
            # POTENTIAL_NON_COMPLIANCE — i.e. a total OCR failure could
            # silently turn into an asserted violation instead of a
            # NEEDS_MANUAL_REVIEW/UNABLE_TO_VERIFY.
            score += 0.15
        else:
            score += 0.5

        return score / weight_total if weight_total else 0.0

    @property
    def has_sufficient_evidence(self) -> bool:
        """If neither the webpage fetch succeeded nor any images/screenshots
        were supplied at all, there is nothing to evaluate — findings should
        be UNABLE_TO_VERIFY rather than a confident PASS or violation."""
        return self.webpage_fetch_succeeded or self.has_any_images
