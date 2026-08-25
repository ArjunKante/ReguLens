"""The generic validator architecture (Section 11).

Each function here implements one `validation_type`. All of them take the
same two arguments — the RuleVersion's `validator_config` dict and an
`InspectionContext` — and return a `ValidationOutcome`. The compliance
engine (app/compliance/engine.py) is the only caller; it looks up which
function to run purely from `rule_version.validation_type` (and, for
CROSS_FIELD_CHECK, `validator_config["handler"]`), so adding a new rule
never requires touching the engine, only adding data to seed_rules.py plus,
if genuinely novel, one small handler function here.
"""
from __future__ import annotations

import re
from datetime import datetime

from dateutil import parser as dateutil_parser

from app.compliance.context import InspectionContext
from app.compliance.outcome import EvidenceRef, ValidationOutcome
from app.models.enums import ComplianceStatus
from app.rules import fields as F
from app.rules.quantity import parse_net_quantity

_WHEN_PACKED_PATTERN = re.compile(r"when\s+packed", re.IGNORECASE)


def _evidence_for(ctx: InspectionContext, field_name: str) -> list[EvidenceRef]:
    evidence: list[EvidenceRef] = []
    for d in ctx.values_for(field_name):
        if d.source_type == "IMAGE_OCR":
            evidence.append(
                EvidenceRef(
                    evidence_type="IMAGE_OCR",
                    description=f"OCR-extracted value for '{field_name}': {d.value!r}",
                    reference={"product_image_id": str(d.source_product_image_id) if d.source_product_image_id else None},
                    declaration_id=str(d.id),
                )
            )
        elif d.source_type in ("WEBPAGE_TEXT", "STRUCTURED_METADATA"):
            evidence.append(
                EvidenceRef(
                    evidence_type="WEBPAGE_TEXT",
                    description=f"Listing-page value for '{field_name}': {d.value!r}",
                    reference={"web_page_id": str(d.source_web_page_id) if d.source_web_page_id else None},
                    declaration_id=str(d.id),
                )
            )
        else:
            evidence.append(
                EvidenceRef(
                    evidence_type="MANUAL",
                    description=f"'{field_name}' provided via {d.source_type}: {d.value!r}",
                    reference={},
                    declaration_id=str(d.id),
                )
            )
    return evidence


def _absence_outcome(ctx: InspectionContext, field_names: list[str], base_reason: str) -> ValidationOutcome:
    if not ctx.has_sufficient_evidence:
        return ValidationOutcome(
            status=ComplianceStatus.UNABLE_TO_VERIFY,
            reason=(
                f"{base_reason} No page content or images were successfully retrieved for "
                "this inspection, so absence cannot be distinguished from a retrieval failure."
            ),
            confidence=0.3,
            checked_fields=field_names,
        )
    quality = ctx.evidence_quality_score
    if quality < 0.5:
        return ValidationOutcome(
            status=ComplianceStatus.NEEDS_MANUAL_REVIEW,
            reason=(
                f"{base_reason} Evidence quality for this inspection was low (score "
                f"{quality:.2f}), so this is flagged for manual review rather than treated "
                "as a confirmed omission."
            ),
            confidence=round(0.5 + 0.3 * (1 - quality), 2),
            checked_fields=field_names,
        )
    return ValidationOutcome(
        status=ComplianceStatus.POTENTIAL_NON_COMPLIANCE,
        reason=(
            f"{base_reason} Listing/image evidence for this inspection was otherwise complete "
            f"(evidence quality score {quality:.2f}), so this appears to be a genuine gap "
            "requiring officer verification."
        ),
        confidence=round(0.55 + 0.35 * quality, 2),
        checked_fields=field_names,
    )


def presence_check(config: dict, ctx: InspectionContext) -> ValidationOutcome:
    groups: list[list[str]] = config.get("require_any_group", [])
    all_fields = [f for group in groups for f in group]

    for group in groups:
        if all(ctx.has_value(f) for f in group):
            confidences = [ctx.best(f).confidence for f in group if ctx.best(f)]  # type: ignore[union-attr]
            evidence = [e for f in group for e in _evidence_for(ctx, f)]
            return ValidationOutcome(
                status=ComplianceStatus.PASS,
                reason=f"Required field(s) {group} were found with satisfactory evidence.",
                confidence=round(min(confidences), 2) if confidences else 0.6,
                checked_fields=group,
                evidence=evidence,
            )

    return _absence_outcome(
        ctx,
        all_fields,
        f"None of the accepted field group(s) {groups} were found in the extracted declarations.",
    )


def pattern_check(config: dict, ctx: InspectionContext) -> ValidationOutcome:
    field_name = config.get("field")
    any_of_fields = config.get("any_of_fields") or ([field_name] if field_name else [])
    patterns = [re.compile(p, re.IGNORECASE) for p in config.get("patterns", [])]

    for f in any_of_fields:
        decl = ctx.best(f)
        if decl and decl.value and any(p.search(decl.value) for p in patterns):
            return ValidationOutcome(
                status=ComplianceStatus.PASS,
                reason=f"Field '{f}' value {decl.value!r} matched the expected format.",
                confidence=round(decl.confidence, 2),
                checked_fields=[f],
                evidence=_evidence_for(ctx, f),
            )

    # Present but malformed vs. entirely absent are distinguished in the reason text.
    any_present = any(ctx.has_value(f) for f in any_of_fields)
    if any_present:
        outcome = _absence_outcome(
            ctx,
            any_of_fields,
            f"A value was found for {any_of_fields} but it did not match the expected format "
            "for this declaration.",
        )
        return outcome

    return _absence_outcome(ctx, any_of_fields, f"No value was found for field(s) {any_of_fields}.")


_DATE_HINT_PATTERN = re.compile(
    r"\b(0?[1-9]|1[0-2])[\/\-\.](\d{2,4})\b|"
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*\d{2,4}\b",
    re.IGNORECASE,
)


def _looks_like_date(value: str) -> bool:
    if _DATE_HINT_PATTERN.search(value):
        return True
    try:
        dateutil_parser.parse(value, fuzzy=True, default=datetime(2000, 1, 1))
        return True
    except (ValueError, OverflowError):
        return False


def date_check(config: dict, ctx: InspectionContext) -> ValidationOutcome:
    field_name = config["field"]
    decl = ctx.best(field_name)

    if decl and decl.value and _looks_like_date(decl.value):
        return ValidationOutcome(
            status=ComplianceStatus.PASS,
            reason=f"A date-like value was found for '{field_name}': {decl.value!r}.",
            confidence=round(decl.confidence, 2),
            checked_fields=[field_name],
            evidence=_evidence_for(ctx, field_name),
        )

    if decl and decl.value:
        # Present but not parseable as a date.
        return _absence_outcome(
            ctx,
            [field_name],
            f"A value was found for '{field_name}' ({decl.value!r}) but it could not be "
            "recognized as a valid date/month-year.",
        )

    if not ctx.has_sufficient_evidence:
        return ValidationOutcome(
            status=ComplianceStatus.UNABLE_TO_VERIFY,
            reason=f"No evidence was retrieved to check '{field_name}'.",
            confidence=0.3,
            checked_fields=[field_name],
        )

    quality = ctx.evidence_quality_score
    if quality < 0.5:
        configured_status = ComplianceStatus.NEEDS_MANUAL_REVIEW
    else:
        configured_status = ComplianceStatus(config.get("absence_status", "NEEDS_MANUAL_REVIEW"))

    reason = config.get(
        "absence_reason", f"No value was found for '{field_name}' in the extracted declarations."
    )
    return ValidationOutcome(
        status=configured_status,
        reason=reason,
        confidence=0.55,
        checked_fields=[field_name],
    )


def manual_review_check(config: dict, ctx: InspectionContext) -> ValidationOutcome:
    if not ctx.has_sufficient_evidence:
        return ValidationOutcome(
            status=ComplianceStatus.UNABLE_TO_VERIFY,
            reason="No page content or images were retrieved for this inspection.",
            confidence=0.3,
        )

    reason = config.get("reason_default", "This requirement needs human judgment and is routed for officer review.")

    hint_patterns = config.get("multipack_hint_patterns")
    if hint_patterns:
        product_name = ctx.best(F.PRODUCT_NAME)
        net_qty = ctx.best(F.NET_QUANTITY)
        haystack = " ".join(v.value or "" for v in [product_name, net_qty] if v)
        if any(re.search(p, haystack, re.IGNORECASE) for p in hint_patterns):
            reason = config.get("reason_multipack_hint", reason)

    if config.get("use_ocr_confidence_hint") and ctx.average_ocr_confidence is not None:
        reason = f"{reason} (Average OCR confidence for this inspection's images: {ctx.average_ocr_confidence:.0%}.)"

    return ValidationOutcome(status=ComplianceStatus.NEEDS_MANUAL_REVIEW, reason=reason, confidence=0.5)


# --- CROSS_FIELD_CHECK handlers -------------------------------------------------


def _country_of_origin_gate(config: dict, ctx: InspectionContext) -> ValidationOutcome:
    if not ctx.is_imported:
        return ValidationOutcome(
            status=ComplianceStatus.NOT_APPLICABLE,
            reason="No importer was identified for this listing; country-of-origin declaration is not applicable to domestically manufactured products.",
            confidence=0.6,
        )
    return presence_check({"require_any_group": [[F.COUNTRY_OF_ORIGIN]]}, ctx)


def _consumer_care_check(config: dict, ctx: InspectionContext) -> ValidationOutcome:
    name_or_addr = ctx.has_value(F.CONSUMER_CARE_NAME) or ctx.has_value(F.CONSUMER_CARE_ADDRESS)
    phone_or_email = ctx.has_value(F.CONSUMER_CARE_PHONE) or ctx.has_value(F.CONSUMER_CARE_EMAIL)

    if name_or_addr and phone_or_email:
        fields = [F.CONSUMER_CARE_NAME, F.CONSUMER_CARE_ADDRESS, F.CONSUMER_CARE_PHONE, F.CONSUMER_CARE_EMAIL]
        evidence = [e for f in fields for e in _evidence_for(ctx, f)]
        return ValidationOutcome(
            status=ComplianceStatus.PASS,
            reason="Consumer-care name/address and a phone or email contact were both found.",
            confidence=0.85,
            checked_fields=fields,
            evidence=evidence,
        )

    if name_or_addr and not phone_or_email:
        return ValidationOutcome(
            status=ComplianceStatus.NEEDS_MANUAL_REVIEW,
            reason=(
                "Consumer-care name/address was found but no phone or email contact was "
                "detected. Source-text history for this sub-rule is ambiguous about whether "
                "phone/email is unconditionally mandatory (see docs/legal-rules.md), so this "
                "is routed for officer review rather than auto-flagged."
            ),
            confidence=0.55,
            checked_fields=[F.CONSUMER_CARE_NAME, F.CONSUMER_CARE_ADDRESS],
        )

    return _absence_outcome(
        ctx,
        [F.CONSUMER_CARE_NAME, F.CONSUMER_CARE_ADDRESS, F.CONSUMER_CARE_PHONE, F.CONSUMER_CARE_EMAIL],
        "No consumer-care name, address, phone, or email was found anywhere in the extracted declarations.",
    )


def _ecommerce_display_aggregate(config: dict, ctx: InspectionContext) -> ValidationOutcome:
    missing_groups: list[list[str]] = []
    all_fields: list[str] = []
    evidence: list[EvidenceRef] = []

    for group in F.ECOMMERCE_DISPLAY_FIELD_GROUPS:
        all_fields.extend(group)
        if any(ctx.webpage_source_has_value(f) for f in group):
            for f in group:
                evidence.extend(e for e in _evidence_for(ctx, f) if e.evidence_type == "WEBPAGE_TEXT")
        else:
            missing_groups.append(group)

    if not missing_groups:
        return ValidationOutcome(
            status=ComplianceStatus.PASS,
            reason="All mandatory Rule 6(1) declaration groups were found on the listing page itself.",
            confidence=0.85,
            checked_fields=all_fields,
            evidence=evidence,
        )

    return _absence_outcome(
        ctx,
        [f for group in missing_groups for f in group],
        f"The following declaration group(s) were not found on the listing page text/metadata "
        f"(image-only evidence does not satisfy Rule 6(10)'s 'digital and electronic network' "
        f"display duty): {missing_groups}.",
    )


def _when_packed_phrase(config: dict, ctx: InspectionContext) -> ValidationOutcome:
    decl = ctx.best(F.NET_QUANTITY)
    if decl is None or not decl.value:
        return ValidationOutcome(
            status=ComplianceStatus.UNABLE_TO_VERIFY,
            reason="No net-quantity declaration was found to check for a disallowed 'when packed' qualifier.",
            confidence=0.3,
            checked_fields=[F.NET_QUANTITY],
        )
    if _WHEN_PACKED_PATTERN.search(decl.value):
        return ValidationOutcome(
            status=ComplianceStatus.POTENTIAL_NON_COMPLIANCE,
            reason=f"The net-quantity declaration {decl.value!r} appears to be qualified by 'when packed', which Rule 11 disallows.",
            confidence=0.7,
            checked_fields=[F.NET_QUANTITY],
            evidence=_evidence_for(ctx, F.NET_QUANTITY),
        )
    return ValidationOutcome(
        status=ComplianceStatus.PASS,
        reason="Net-quantity declaration does not contain a disallowed 'when packed' qualifier.",
        confidence=round(decl.confidence, 2),
        checked_fields=[F.NET_QUANTITY],
        evidence=_evidence_for(ctx, F.NET_QUANTITY),
    )


def evaluate_small_package_exemption(ctx: InspectionContext) -> bool | None:
    """Returns True if the small-package exemption (Rule 26(a)) applies,
    False if it clearly doesn't, or None if net quantity couldn't be parsed
    confidently enough to decide either way."""
    decl = ctx.best(F.NET_QUANTITY)
    if decl is None or not decl.value:
        return None
    parsed = parse_net_quantity(decl.value)
    if parsed is None:
        return None
    if ctx.is_tobacco_product:
        return False
    if parsed.basis == "weight_g":
        return parsed.normalized_value <= 10
    if parsed.basis == "volume_ml":
        return parsed.normalized_value <= 10
    return None


def _small_package_exemption_gate(config: dict, ctx: InspectionContext) -> ValidationOutcome:
    exempt = evaluate_small_package_exemption(ctx)
    if exempt is None:
        return ValidationOutcome(
            status=ComplianceStatus.UNABLE_TO_VERIFY,
            reason="Net quantity could not be parsed confidently enough to determine small-package exemption status.",
            confidence=0.3,
            checked_fields=[F.NET_QUANTITY],
        )
    if exempt:
        return ValidationOutcome(
            status=ComplianceStatus.NOT_APPLICABLE,
            reason="Declared net quantity is 10g/10ml or less; Rule 26(a) exempts this package from the Rules.",
            confidence=0.7,
            checked_fields=[F.NET_QUANTITY],
        )
    return ValidationOutcome(
        status=ComplianceStatus.PASS,
        reason="Declared net quantity exceeds the Rule 26(a) small-package exemption threshold; standard rules apply.",
        confidence=0.7,
        checked_fields=[F.NET_QUANTITY],
    )


_CROSS_FIELD_HANDLERS = {
    "country_of_origin_gate": _country_of_origin_gate,
    "consumer_care_check": _consumer_care_check,
    "ecommerce_display_aggregate": _ecommerce_display_aggregate,
    "when_packed_phrase": _when_packed_phrase,
    "small_package_exemption_gate": _small_package_exemption_gate,
}


def cross_field_check(config: dict, ctx: InspectionContext) -> ValidationOutcome:
    handler_name = config.get("handler")
    handler = _CROSS_FIELD_HANDLERS.get(handler_name)  # type: ignore[arg-type]
    if handler is None:
        return ValidationOutcome(
            status=ComplianceStatus.UNABLE_TO_VERIFY,
            reason=f"No handler registered for cross-field check '{handler_name}'.",
            confidence=0.0,
        )
    return handler(config, ctx)


def numeric_check(config: dict, ctx: InspectionContext) -> ValidationOutcome:
    """Generic numeric-range validator. Not exercised by any V1 online-listing
    rule today (kept for architectural completeness / future rules, e.g. a
    future physical-measurement tolerance check per Section 47)."""
    field_name = config["field"]
    decl = ctx.best(field_name)
    if decl is None or not decl.value:
        return _absence_outcome(ctx, [field_name], f"No numeric value found for '{field_name}'.")
    match = re.search(r"[-+]?\d*\.?\d+", decl.value)
    if not match:
        return _absence_outcome(ctx, [field_name], f"Value for '{field_name}' was not numeric.")
    numeric_value = float(match.group())
    min_v, max_v = config.get("min"), config.get("max")
    if (min_v is not None and numeric_value < min_v) or (max_v is not None and numeric_value > max_v):
        return ValidationOutcome(
            status=ComplianceStatus.POTENTIAL_NON_COMPLIANCE,
            reason=f"Value {numeric_value} for '{field_name}' is outside the expected range [{min_v}, {max_v}].",
            confidence=round(decl.confidence, 2),
            checked_fields=[field_name],
            evidence=_evidence_for(ctx, field_name),
        )
    return ValidationOutcome(
        status=ComplianceStatus.PASS,
        reason=f"Value {numeric_value} for '{field_name}' is within the expected range.",
        confidence=round(decl.confidence, 2),
        checked_fields=[field_name],
        evidence=_evidence_for(ctx, field_name),
    )


VALIDATORS = {
    "PRESENCE_CHECK": presence_check,
    "PATTERN_CHECK": pattern_check,
    "NUMERIC_CHECK": numeric_check,
    "DATE_CHECK": date_check,
    "CROSS_FIELD_CHECK": cross_field_check,
    "MANUAL_REVIEW_CHECK": manual_review_check,
}
