"""The compliance engine (Section 13): evaluates every applicable,
currently-active RuleVersion against one inspection's declarations and
evidence, and persists ComplianceCheck / Violation / Evidence rows.

This module owns the one piece of business logic the whole system exists
to protect: it NEVER does a naive "if missing then illegal". Every outcome
comes from a validator (app/rules/validators.py) or the consistency engine
(app/compliance/consistency.py), both of which weigh evidence quality before
choosing between PASS / POTENTIAL_NON_COMPLIANCE / NEEDS_MANUAL_REVIEW /
NOT_APPLICABLE / UNABLE_TO_VERIFY.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.compliance.consistency import evaluate_consistency
from app.compliance.context import InspectionContext
from app.compliance.outcome import ValidationOutcome
from app.models.compliance import ComplianceCheck, Evidence, Violation
from app.models.declaration import Declaration
from app.models.enums import ComplianceStatus, ProductCategoryCode, ValidationType
from app.models.inspection import Inspection
from app.models.rules import Rule, RuleVersion
from app.models.scraping import OCRResult, ProductImage, WebPage
from app.nlp.classification import is_tobacco_product
from app.rules import fields as F
from app.rules.validators import VALIDATORS, evaluate_small_package_exemption

ENGINE_VERSION = "1.0.0"

# Rules that determine the small-package exemption's own trigger condition
# must never be suppressed by that same exemption (Section 26/Rule 26(a)).
_SKIP_SMALL_PACKAGE_GATE = {"LMPC-R6-1C-NET-QUANTITY"}


def _build_context(db: Session, inspection: Inspection) -> InspectionContext:
    declarations = list(
        db.execute(select(Declaration).where(Declaration.inspection_id == inspection.id)).scalars()
    )
    web_pages = list(db.execute(select(WebPage).where(WebPage.inspection_id == inspection.id)).scalars())
    images = list(db.execute(select(ProductImage).where(ProductImage.inspection_id == inspection.id)).scalars())
    image_ids = [img.id for img in images]
    ocr_results = (
        list(db.execute(select(OCRResult).where(OCRResult.product_image_id.in_(image_ids))).scalars())
        if image_ids
        else []
    )

    text_blob_parts = [inspection.source_url or ""]
    for d in declarations:
        if d.field_name == F.PRODUCT_NAME and d.value:
            text_blob_parts.append(d.value)
    if inspection.product is not None:
        text_blob_parts.append(inspection.product.title or "")
        text_blob_parts.append(inspection.product.description or "")

    ctx = InspectionContext(
        declarations=declarations,
        web_pages=web_pages,
        images=images,
        ocr_results=ocr_results,
        is_tobacco_product=is_tobacco_product(*text_blob_parts),
        is_imported=any(
            d.field_name == F.IMPORTER_NAME and (d.value or "").strip() for d in declarations
        ),
    )
    return ctx


def _active_rule_versions(db: Session) -> list[RuleVersion]:
    return list(
        db.execute(
            select(RuleVersion)
            .join(Rule, RuleVersion.rule_id == Rule.id)
            .where(RuleVersion.is_current.is_(True), Rule.active.is_(True))
        ).scalars()
    )


def _category_gate(rule_version: RuleVersion, category: ProductCategoryCode) -> ValidationOutcome | None:
    if category.value in (rule_version.excluded_categories or []):
        return ValidationOutcome(
            status=ComplianceStatus.NOT_APPLICABLE,
            reason=(
                f"Rule '{rule_version.title}' does not apply to category '{category.value}' "
                f"(see docs/legal-rules.md exceptions for {rule_version.rule_reference})."
            ),
            confidence=0.9,
        )
    applicable = rule_version.applicable_categories or []
    if applicable and category.value not in applicable:
        return ValidationOutcome(
            status=ComplianceStatus.NOT_APPLICABLE,
            reason=(
                f"Rule '{rule_version.title}' only applies to categories {applicable}; "
                f"this product was classified as '{category.value}'."
            ),
            confidence=0.85,
        )
    return None


def run_compliance_checks(
    db: Session, inspection: Inspection, category: ProductCategoryCode
) -> list[ComplianceCheck]:
    ctx = _build_context(db, inspection)
    exempt = evaluate_small_package_exemption(ctx)

    now = dt.datetime.now(dt.timezone.utc)
    created_checks: list[ComplianceCheck] = []

    for rule_version in _active_rule_versions(db):
        if rule_version.gating_only:
            continue

        outcome = _category_gate(rule_version, category)

        if outcome is None and exempt is True and rule_version.rule.rule_key not in _SKIP_SMALL_PACKAGE_GATE:
            outcome = ValidationOutcome(
                status=ComplianceStatus.NOT_APPLICABLE,
                reason=(
                    "Declared net quantity is 10g/10ml or less; Rule 26(a) exempts this "
                    "package from the Legal Metrology (Packaged Commodities) Rules, 2011."
                ),
                confidence=0.7,
            )

        if outcome is None:
            if rule_version.validation_type == ValidationType.CONSISTENCY_CHECK.value:
                outcome = evaluate_consistency(rule_version.validator_config, ctx)
            else:
                validator = VALIDATORS.get(rule_version.validation_type)
                if validator is None:
                    outcome = ValidationOutcome(
                        status=ComplianceStatus.UNABLE_TO_VERIFY,
                        reason=f"No validator implemented for validation_type '{rule_version.validation_type}'.",
                        confidence=0.0,
                    )
                else:
                    outcome = validator(rule_version.validator_config, ctx)

        check = ComplianceCheck(
            inspection_id=inspection.id,
            rule_version_id=rule_version.id,
            status=outcome.status.value,
            reason=outcome.reason,
            confidence=outcome.confidence,
            checked_fields=outcome.checked_fields,
            engine_version=ENGINE_VERSION,
            executed_at=now,
        )
        db.add(check)
        db.flush()

        if outcome.status == ComplianceStatus.POTENTIAL_NON_COMPLIANCE:
            db.add(
                Violation(
                    compliance_check_id=check.id,
                    severity=rule_version.severity,
                    summary=rule_version.title,
                    details=outcome.reason,
                )
            )

        for ev in outcome.evidence:
            db.add(
                Evidence(
                    compliance_check_id=check.id,
                    declaration_id=uuid.UUID(ev.declaration_id) if ev.declaration_id else None,
                    evidence_type=ev.evidence_type,
                    description=ev.description,
                    reference=ev.reference,
                    created_at=now,
                )
            )

        created_checks.append(check)

    db.commit()
    return created_checks


_STATUS_PRIORITY = [
    ComplianceStatus.POTENTIAL_NON_COMPLIANCE,
    ComplianceStatus.NEEDS_MANUAL_REVIEW,
    ComplianceStatus.UNABLE_TO_VERIFY,
    ComplianceStatus.PASS,
    ComplianceStatus.NOT_APPLICABLE,
]


def compute_overall_status(checks: list[ComplianceCheck]) -> ComplianceStatus:
    """Deterministic aggregation: the most severe status present wins,
    where severity ordering is POTENTIAL_NON_COMPLIANCE > NEEDS_MANUAL_REVIEW
    > UNABLE_TO_VERIFY > PASS, and an inspection with only NOT_APPLICABLE
    checks (nothing could be meaningfully evaluated) also reports
    UNABLE_TO_VERIFY rather than a hollow PASS."""
    statuses = {ComplianceStatus(c.status) for c in checks}
    if not statuses or statuses == {ComplianceStatus.NOT_APPLICABLE}:
        return ComplianceStatus.UNABLE_TO_VERIFY
    for candidate in _STATUS_PRIORITY:
        if candidate in statuses:
            return candidate
    return ComplianceStatus.UNABLE_TO_VERIFY
