"""Cross-source consistency engine (Section 14).

Compares declarations that came from the online listing (WEBPAGE_TEXT /
STRUCTURED_METADATA / USER_INPUT) against declarations that came from
product images (IMAGE_OCR) for the same field. A disagreement is reported
as POTENTIAL_NON_COMPLIANCE with the literal wording the product brief
requires ("Potential inconsistency detected... Officer verification
required.") — LM-SCAN never asserts which source is "correct" and never
frames this as a confirmed legal violation on its own (Section 14: "Never
automatically declare legal liability").

These checks are evaluated against synthetic RuleVersions whose
`source_document` honestly says "LM-SCAN internal engineering rule" rather
than pretending to cite the Legal Metrology Rules, 2011 — see
seed_rules.py's LMSCAN-CONSISTENCY-* entries and docs/legal-rules.md.
"""
from __future__ import annotations

from app.compliance.context import InspectionContext
from app.compliance.outcome import EvidenceRef, ValidationOutcome
from app.models.enums import ComplianceStatus, DeclarationSourceType
from app.nlp.normalization import fuzzy_equal

_ONLINE_SOURCES = {
    DeclarationSourceType.WEBPAGE_TEXT.value,
    DeclarationSourceType.STRUCTURED_METADATA.value,
    DeclarationSourceType.USER_INPUT.value,
}
_IMAGE_SOURCES = {DeclarationSourceType.IMAGE_OCR.value}

_NUMERIC_FIELDS = {"mrp", "net_quantity", "unit_sale_price"}


def _side_values(ctx: InspectionContext, field_name: str, sources: set[str]) -> list:
    return [d for d in ctx.values_for(field_name) if d.source_type in sources]


def _values_match(field_name: str, a_norm: str | None, b_norm: str | None, a_raw: str, b_raw: str) -> bool:
    if field_name in _NUMERIC_FIELDS:
        if a_norm is None or b_norm is None:
            return fuzzy_equal(a_raw, b_raw, threshold=90)
        return a_norm == b_norm
    return fuzzy_equal(a_raw, b_raw, threshold=85) or bool(a_norm and b_norm and a_norm == b_norm)


def evaluate_consistency(config: dict, ctx: InspectionContext) -> ValidationOutcome:
    field_name = config["field"]
    online_values = _side_values(ctx, field_name, _ONLINE_SOURCES)
    image_values = _side_values(ctx, field_name, _IMAGE_SOURCES)

    if not online_values or not image_values:
        present_sides = []
        if online_values:
            present_sides.append("listing page")
        if image_values:
            present_sides.append("product image(s)")
        return ValidationOutcome(
            status=ComplianceStatus.UNABLE_TO_VERIFY,
            reason=(
                f"Cross-source consistency check for '{field_name}' requires a value from "
                f"both the listing page and product images; only found: {present_sides or 'neither'}."
            ),
            confidence=0.3,
            checked_fields=[field_name],
        )

    online_best = max(online_values, key=lambda d: d.confidence)
    image_best = max(image_values, key=lambda d: d.confidence)

    if _values_match(field_name, online_best.normalized_value, image_best.normalized_value, online_best.value or "", image_best.value or ""):
        return ValidationOutcome(
            status=ComplianceStatus.PASS,
            reason=f"Listing-page and product-image values for '{field_name}' agree.",
            confidence=round(min(online_best.confidence, image_best.confidence), 2),
            checked_fields=[field_name],
            evidence=[
                EvidenceRef(
                    evidence_type="WEBPAGE_TEXT",
                    description=f"Listing value for '{field_name}': {online_best.value!r}",
                    reference={"web_page_id": str(online_best.source_web_page_id) if online_best.source_web_page_id else None},
                    declaration_id=str(online_best.id),
                ),
                EvidenceRef(
                    evidence_type="IMAGE_OCR",
                    description=f"Image OCR value for '{field_name}': {image_best.value!r}",
                    reference={"product_image_id": str(image_best.source_product_image_id) if image_best.source_product_image_id else None},
                    declaration_id=str(image_best.id),
                ),
            ],
        )

    return ValidationOutcome(
        status=ComplianceStatus.POTENTIAL_NON_COMPLIANCE,
        reason=(
            f"Potential inconsistency detected for '{field_name}': listing page shows "
            f"{online_best.value!r}, product image shows {image_best.value!r}. "
            "Officer verification required."
        ),
        confidence=round(min(online_best.confidence, image_best.confidence), 2),
        checked_fields=[field_name],
        evidence=[
            EvidenceRef(
                evidence_type="WEBPAGE_TEXT",
                description=f"Listing value for '{field_name}': {online_best.value!r}",
                reference={"web_page_id": str(online_best.source_web_page_id) if online_best.source_web_page_id else None},
                declaration_id=str(online_best.id),
            ),
            EvidenceRef(
                evidence_type="IMAGE_OCR",
                description=f"Image OCR value for '{field_name}': {image_best.value!r}",
                reference={"product_image_id": str(image_best.source_product_image_id) if image_best.source_product_image_id else None},
                declaration_id=str(image_best.id),
            ),
        ],
    )
