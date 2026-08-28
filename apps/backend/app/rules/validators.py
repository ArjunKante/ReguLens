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
from app.nlp.normalization import normalize_currency
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


def _declared_text_haystack(ctx: InspectionContext, field_names: list[str]) -> str:
    return " ".join(v.value or "" for f in field_names for v in ctx.values_for(f))


def manual_review_check(config: dict, ctx: InspectionContext) -> ValidationOutcome:
    if not ctx.has_sufficient_evidence:
        return ValidationOutcome(
            status=ComplianceStatus.UNABLE_TO_VERIFY,
            reason="No page content or images were retrieved for this inspection.",
            confidence=0.3,
        )

    # Optional applicability gate: some MANUAL_REVIEW_CHECK rules describe an
    # exemption condition (e.g. Rule 26(c) drug formulations, Rule 26(e)
    # thread coil sold to handloom weavers) that is narrow enough that most
    # products clearly don't relate to it at all. Rather than routing EVERY
    # inspection to manual review for questions that plainly don't apply
    # (noisy and useless), a narrow keyword hint decides whether the
    # condition is even plausibly in play. Critically, this only ever
    # widens the set of things routed to NEEDS_MANUAL_REVIEW -- it never
    # asserts a confident exemption from the keyword hint itself (that
    # would be exactly the "classify a qualifying drug formulation from OCR
    # keywords alone" mistake the specification warns against). Absence of
    # the hint yields NOT_APPLICABLE (a claim only that this narrow
    # exemption doesn't plausibly relate to this product -- not a claim
    # about drug/thread status itself); presence of the hint always yields
    # NEEDS_MANUAL_REVIEW, never PASS or a confident exemption.
    hint_patterns = config.get("applicability_hint_patterns")
    if hint_patterns:
        haystack = _declared_text_haystack(ctx, config.get("applicability_hint_fields", [F.PRODUCT_NAME]))
        if not any(re.search(p, haystack, re.IGNORECASE) for p in hint_patterns):
            return ValidationOutcome(
                status=ComplianceStatus.NOT_APPLICABLE,
                reason=config.get(
                    "applicability_absent_reason",
                    "No evidence was found that this exemption condition applies to this product.",
                ),
                confidence=0.6,
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
    if ctx.origin_status == "UNKNOWN":
        # Absence of an importer declaration only means "domestic" if we
        # actually looked and found manufacturer/packer evidence instead —
        # with no evidence at all (failed fetch, no images, nothing
        # extracted), it must not be reported as a confident NOT_APPLICABLE
        # (P0 audit fix: "imported/domestic/unknown classification").
        return ValidationOutcome(
            status=ComplianceStatus.UNABLE_TO_VERIFY,
            reason=(
                "Neither an importer nor a manufacturer/packer could be identified for this "
                "inspection, so whether this product is domestic or imported (and therefore "
                "whether Rule 6(1)(aa) applies) cannot be determined from the available evidence."
            ),
            confidence=0.3,
        )
    if ctx.origin_status == "DOMESTIC":
        # Rule 6(1)(aa) is strictly imported-products-only per the
        # authoritative supplied specification; there is no broader "all
        # products" extension of 6(1)(aa) itself. (An earlier version of
        # this handler speculated that e-commerce policy broadened this for
        # online listings of domestic products too — first citing a general
        # 2020 DPIIT direction, later a purported "Rule 6(10A)" 2026
        # amendment — neither citation could be traced to the authoritative
        # supplied source, and both have been removed; see
        # `LMPC-R6-10A-COO-FILTER`'s removal note in seed_rules.py, dated
        # 2026-08-28.)
        return ValidationOutcome(
            status=ComplianceStatus.NOT_APPLICABLE,
            reason="This product was identified as domestically manufactured (no importer declared); country-of-origin declaration is not applicable under Rule 6(1)(aa).",
            confidence=0.6,
        )
    return presence_check({"require_any_group": [[F.COUNTRY_OF_ORIGIN]]}, ctx)


    # NOTE: a `_coo_searchable_filter_gate` handler previously lived here,
    # backing a purported "Rule 6(10A)" e-commerce country-of-origin filter
    # requirement. It was removed on 2026-08-28 along with the
    # `LMPC-R6-10A-COO-FILTER` seed rule that referenced it — see that seed
    # rule's removal note in `app/rules/seed_rules.py` for the full
    # correction. Do not re-add a handler for that rule_key unless a
    # corresponding requirement is confirmed against the authoritative
    # supplied specification.


def _consumer_care_check(config: dict, ctx: InspectionContext) -> ValidationOutcome:
    """Rule 6(2), corrected per docs/Legal_Metrology_Rules_Corrected.md
    Section 5: name, address, telephone number, AND e-mail address are each
    independently REQUIRED by the current substituted text -- none of the
    four is a substitute for another. (An earlier version of this handler
    accepted name-OR-address plus phone-OR-email as sufficient for a PASS,
    reasoning that an older PDF revision's "if available" wording made
    phone/email optional; the corrected specification is explicit that this
    reasoning must not be retained -- the "if available" text is historical,
    superseded by the 2015 substitution.)

    Uncertainty about *whether evidence was actually captured* is still
    handled the same evidence-quality-aware way as every other rule (never
    "if missing then illegal"): a missing field under strong, otherwise-
    complete evidence is POTENTIAL_NON_COMPLIANCE; under weak/uncertain
    evidence it is NEEDS_MANUAL_REVIEW; with no usable evidence at all it is
    UNABLE_TO_VERIFY. That's `_absence_outcome`'s existing job -- this
    handler's only change from the old version is which fields it demands.
    """
    fields = [F.CONSUMER_CARE_NAME, F.CONSUMER_CARE_ADDRESS, F.CONSUMER_CARE_PHONE, F.CONSUMER_CARE_EMAIL]
    missing = [f for f in fields if not ctx.has_value(f)]

    if not missing:
        evidence = [e for f in fields for e in _evidence_for(ctx, f)]
        return ValidationOutcome(
            status=ComplianceStatus.PASS,
            reason="Consumer-care name, address, telephone number, and e-mail address were all found.",
            confidence=0.85,
            checked_fields=fields,
            evidence=evidence,
        )

    if len(missing) == len(fields):
        base_reason = "No consumer-care name, address, phone, or email was found anywhere in the extracted declarations."
    else:
        base_reason = (
            f"Consumer-care field(s) {missing} were not found; Rule 6(2)'s current substituted "
            "text requires name, address, telephone number, AND e-mail address -- none of "
            "these four is an accepted substitute for another."
        )

    return _absence_outcome(ctx, missing, base_reason)


def _ecommerce_display_aggregate(config: dict, ctx: InspectionContext) -> ValidationOutcome:
    if not ctx.web_pages:
        # Rule 6(10) requires declarations on "the digital and electronic
        # network used for e-commerce transactions" — i.e. it only has
        # something to say about an actual online listing. A manual/
        # photo-only inspection (no source_url, so no WebPage was ever
        # fetched) is inspecting a physical package directly, not an online
        # listing, so there is no digital listing for this rule to apply to
        # (P0 audit fix: "online vs physical rule applicability" — this
        # previously fell through to the same absence-based scoring as an
        # online listing missing its declarations, so a manual scan could
        # be flagged for not displaying declarations "on the digital and
        # electronic network" it never had in the first place).
        return ValidationOutcome(
            status=ComplianceStatus.NOT_APPLICABLE,
            reason="This is a manual/photo-only inspection with no online listing page; Rule 6(10)'s e-commerce display duty applies to declarations shown on a digital listing, which does not exist here.",
            confidence=0.9,
        )

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


def _fast_food_restaurant_gate(config: dict, ctx: InspectionContext) -> ValidationOutcome:
    """Rule 26(b): the Rules do not apply to a package containing fast food
    items packed by a restaurant or hotel and the like. LM-SCAN cannot
    confirm from a marketplace listing that a given seller is actually a
    restaurant/hotel packing its own fast food (as opposed to, say, a
    packaged-snacks brand using the words "fast food" in its title), so
    this never asserts a confident exemption -- a keyword hint only decides
    whether the question is even plausibly in play. No hint at all ->
    NOT_APPLICABLE (this exemption plainly doesn't relate to this product);
    a hint present -> NEEDS_MANUAL_REVIEW so an officer can confirm the
    actual restaurant/hotel-packed fact before treating the package as
    exempt.
    """
    haystack = _declared_text_haystack(ctx, config.get("hint_fields", [F.PRODUCT_NAME]))
    hint_patterns = config.get("hint_patterns", [])
    if not any(re.search(p, haystack, re.IGNORECASE) for p in hint_patterns):
        return ValidationOutcome(
            status=ComplianceStatus.NOT_APPLICABLE,
            reason="No evidence was found that this product is a fast food item packed by a restaurant or hotel.",
            confidence=0.6,
        )
    return ValidationOutcome(
        status=ComplianceStatus.NEEDS_MANUAL_REVIEW,
        reason=(
            "Listing text suggests this may be a fast food item packed by a restaurant, hotel, "
            "or similar establishment (Rule 26(b) exemption) -- but LM-SCAN cannot confirm the "
            "actual packer's identity/status from a marketplace listing alone, so this is "
            "routed for officer confirmation rather than treated as a confident exemption."
        ),
        confidence=0.5,
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


_PIN_CODE_PATTERN = re.compile(r"\b\d{6}\b")
_LOCALITY_PATTERN = re.compile(r"\b[A-Za-z][A-Za-z\s]+,\s*[A-Za-z][A-Za-z\s]+\b")


def _name_address_form_check(config: dict, ctx: InspectionContext) -> ValidationOutcome:
    """Rule 10(1)/10(2), corrected per docs/Legal_Metrology_Rules_Corrected.md
    Section 9: do NOT implement `PIN code OR "word, word"` as a universal
    "complete address" test -- that was this rule's previous behavior
    (a single PATTERN_CHECK where either signal alone was sufficient for a
    PASS) and the corrected specification names it directly as the wrong
    approach to fix (Section 18 Correction 2).

    Layered heuristic used here instead:
      1. No address declared at all -> the existing evidence-quality-aware
         absence path (`_absence_outcome`): UNABLE_TO_VERIFY with no
         evidence, NEEDS_MANUAL_REVIEW under weak evidence, or
         POTENTIAL_NON_COMPLIANCE under otherwise-strong evidence (a
         completely missing address is a genuine gap, not merely a "short"
         one).
      2. An address is declared and shows BOTH a 6-digit PIN code AND a
         separate locality/city-state token -> PASS. Requiring both,
         instead of either, raises the bar rather than lowering it -- this
         is deliberately conservative, not a stronger legal claim than the
         evidence supports.
      3. An address is declared but doesn't clear that bar -> always
         NEEDS_MANUAL_REVIEW, never escalated to POTENTIAL_NON_COMPLIANCE
         by this heuristic alone. Rule 28 allows a manufacturer/packer to
         register a shorter address the authority is satisfied is
         sufficient; a short/ambiguous address extracted from a listing
         cannot be distinguished from a legitimately registered shorter
         address without officer input, so this never asserts a confident
         violation from format alone.
    """
    address_fields = config.get("any_of_fields", [F.MANUFACTURER_ADDRESS, F.PACKER_ADDRESS, F.IMPORTER_ADDRESS])
    candidates = [d for f in address_fields for d in ctx.values_for(f) if (d.value or "").strip()]

    if not candidates:
        return _absence_outcome(
            ctx,
            address_fields,
            f"No value was found for field(s) {address_fields}.",
        )

    best = max(candidates, key=lambda d: d.confidence)
    field_name = best.field_name
    best_value = best.value or ""
    has_pin = bool(_PIN_CODE_PATTERN.search(best_value))
    has_locality = bool(_LOCALITY_PATTERN.search(best_value))

    if has_pin and has_locality:
        return ValidationOutcome(
            status=ComplianceStatus.PASS,
            reason=(
                f"Field '{field_name}' value {best.value!r} contains both a PIN code and a "
                "locality/city-state token, sufficient under this heuristic for a consumer to "
                "identify and locate the manufacturer, packer, or importer."
            ),
            confidence=round(best.confidence, 2),
            checked_fields=[field_name],
            evidence=_evidence_for(ctx, field_name),
        )

    return ValidationOutcome(
        status=ComplianceStatus.NEEDS_MANUAL_REVIEW,
        reason=(
            f"Field '{field_name}' value {best.value!r} was found but does not clearly show "
            "both a PIN code and a locality/city-state token, so this heuristic cannot confirm "
            "the address is complete enough to identify and locate the manufacturer, packer, "
            "or importer. This may still be a valid Rule 28 registered shorter address; an "
            "officer should confirm rather than this being auto-flagged as a violation."
        ),
        confidence=0.5,
        checked_fields=[field_name],
        evidence=_evidence_for(ctx, field_name),
    )


_CHAPTER2_GENERAL_THRESHOLD_G = 25_000  # 25 kg
_CHAPTER2_GENERAL_THRESHOLD_ML = 25_000  # 25 litre
_CHAPTER2_BAGGED_COMMODITY_CEILING_G = 50_000  # 50 kg


def evaluate_chapter2_applicability(ctx: InspectionContext) -> bool | None:
    """Rule 3 — Chapter II applicability gate, corrected per
    docs/Legal_Metrology_Rules_Corrected.md Section 3 / Section 18
    Correction 4. Returns True if Chapter II clearly does NOT apply (this
    package is exempt), False if it clearly does apply, or None if this
    cannot be confidently determined from the evidence LM-SCAN's extraction
    pipeline actually provides -- mirroring `evaluate_small_package_exemption`'s
    tri-state contract and its "never guess an exemption" default.

    Deliberately NOT implemented: a commodity-type classifier that could
    positively identify "this is/isn't a cement, fertilizer, or
    agricultural farm produce bag." No such classifier exists in this
    codebase and building one was explicitly out of scope for this pass
    ("do not build a speculative classifier" / "use only evidence the
    current extraction pipeline can actually provide"). Its absence is
    handled conservatively, not by guessing:

    - Net quantity > 50 kg (or > 25 litre for liquids, which have no
      bagged-commodity carve-out in the specification) is exempt under
      Rule 3 regardless of commodity type -- even the most generous
      carve-out in the specification (cement/fertilizer/agricultural farm
      produce bags) only extends coverage up to 50 kg, so anything above
      that is unambiguously exempt.
    - Net quantity strictly between 25 kg and 50 kg is where the
      specification's cement/fertilizer/farm-produce carve-out actually
      matters (Chapter II *continues to apply* to those three commodities
      in that band) -- and since LM-SCAN cannot determine commodity type,
      it never asserts a confident exemption in that band. It returns None
      (not True), so the caller falls through to continued applicability
      rather than a false exemption.
    - Net quantity <= 25 kg / 25 litre: Chapter II applies normally (False).
    - Net quantity absent/unparseable: None (unable to determine).

    The industrial/institutional-consumer exemption is checked via
    `ctx.institutional_or_industrial_context`, itself only ever set True by
    an explicit self-description in listing/product text (never inferred
    from package size or any other proxy) -- see
    app/nlp/classification.py::is_institutional_or_industrial_context.
    """
    if ctx.institutional_or_industrial_context:
        return True

    decl = ctx.best(F.NET_QUANTITY)
    if decl is None or not decl.value:
        return None
    parsed = parse_net_quantity(decl.value)
    if parsed is None:
        return None

    if parsed.basis == "volume_ml":
        if parsed.normalized_value > _CHAPTER2_GENERAL_THRESHOLD_ML:
            return True
        return False

    if parsed.basis == "weight_g":
        grams = parsed.normalized_value
        if grams > _CHAPTER2_BAGGED_COMMODITY_CEILING_G:
            return True
        if grams > _CHAPTER2_GENERAL_THRESHOLD_G:
            # Ambiguous band: could be an ordinary >25kg item (exempt) or a
            # cement/fertilizer/agricultural-farm-produce bag <=50kg (still
            # covered). No reliable commodity-type signal exists -- prefer
            # continued applicability over a false exemption.
            return None
        return False

    return None


def _chapter2_applicability_gate(config: dict, ctx: InspectionContext) -> ValidationOutcome:
    """Not invoked in normal operation -- LMPC-R3-APPLICABILITY is seeded
    with `gating_only: True`, so the compliance engine consults
    `evaluate_chapter2_applicability` directly (see app/compliance/engine.py)
    and never calls this handler as a standalone check, the same way
    `_small_package_exemption_gate` is never called for Rule 26(a). Kept for
    documentation symmetry and in case `gating_only` is ever toggled off."""
    exempt = evaluate_chapter2_applicability(ctx)
    if exempt is None:
        return ValidationOutcome(
            status=ComplianceStatus.UNABLE_TO_VERIFY,
            reason="Net quantity and consumer-type evidence were insufficient to determine Rule 3 Chapter II applicability.",
            confidence=0.3,
            checked_fields=[F.NET_QUANTITY],
        )
    if exempt:
        return ValidationOutcome(
            status=ComplianceStatus.NOT_APPLICABLE,
            reason="Rule 3 exempts this package from Chapter II of the Legal Metrology (Packaged Commodities) Rules, 2011.",
            confidence=0.7,
            checked_fields=[F.NET_QUANTITY],
        )
    return ValidationOutcome(
        status=ComplianceStatus.PASS,
        reason="This package does not qualify for any Rule 3 Chapter II exemption; Chapter II applies.",
        confidence=0.7,
        checked_fields=[F.NET_QUANTITY],
    )


def _advertisement_net_quantity_check(config: dict, ctx: InspectionContext) -> ValidationOutcome:
    """Rule 31(1)-(2): any advertisement mentioning the retail sale price of
    a pre-packaged commodity must also declare the net quantity (or number)
    of the commodity, and the font size of the net-quantity numerals in the
    advertisement must equal that of the RSP. Per
    docs/Legal_Metrology_Rules_Corrected.md Section 12 / Section 18
    Correction 6, this rule matters directly for an online/advertising
    scanner and must not be filed away as out-of-scope alongside Rules
    32-34.

    Only meaningful for an online listing (an "advertisement" in the sense
    this rule addresses) -- a manual/photo-only inspection has no
    advertisement for this rule to apply to. The net-quantity-presence
    sub-requirement is a deterministic, evidence-quality-aware presence
    check; the font-size-equality sub-requirement can never be verified
    from scraped page text/images (no reliable DOM/CSS measurement is
    available), so the best outcome this rule ever reports, once RSP and
    net quantity are both present, is NEEDS_MANUAL_REVIEW -- never a full
    PASS, per the specification's explicit "do not claim automatic
    verification of font-size equality" instruction.
    """
    if not ctx.web_pages:
        return ValidationOutcome(
            status=ComplianceStatus.NOT_APPLICABLE,
            reason="Rule 31 concerns advertisements; this is a manual/photo-only inspection with no online listing/advertisement to check.",
            confidence=0.85,
        )

    if not ctx.has_value(F.MRP):
        return ValidationOutcome(
            status=ComplianceStatus.NOT_APPLICABLE,
            reason="No retail sale price is displayed on this listing; Rule 31 applies only to advertisements that mention the retail sale price.",
            confidence=0.6,
        )

    if not ctx.has_value(F.NET_QUANTITY):
        return _absence_outcome(
            ctx,
            [F.NET_QUANTITY],
            "This listing displays a retail sale price but no net quantity or count "
            "declaration was found alongside it; Rule 31 requires an advertisement "
            "mentioning the retail sale price to also declare the net quantity or number "
            "of the commodity.",
        )

    return ValidationOutcome(
        status=ComplianceStatus.NEEDS_MANUAL_REVIEW,
        reason=(
            "This listing displays both a retail sale price and a net quantity/count "
            "declaration, satisfying Rule 31's core disclosure requirement -- but LM-SCAN "
            "cannot verify from page content whether the font size of the net-quantity "
            "numerals matches that of the retail sale price, as Rule 31 also requires; an "
            "officer should confirm this from the actual advertisement."
        ),
        confidence=0.55,
        checked_fields=[F.MRP, F.NET_QUANTITY],
        evidence=_evidence_for(ctx, F.MRP) + _evidence_for(ctx, F.NET_QUANTITY),
    )


def _currency_declarations_equal(a, b) -> bool:
    a_norm = a.normalized_value or normalize_currency(a.value)
    b_norm = b.normalized_value or normalize_currency(b.value)
    if a_norm is None or b_norm is None:
        return False
    return a_norm == b_norm


def _unit_sale_price_check(config: dict, ctx: InspectionContext) -> ValidationOutcome:
    """Rule 6(11), corrected per docs/Legal_Metrology_Rules_Corrected.md
    Section 7 / Section 18 Correction 3: unit sale price is not required
    where the retail sale price equals the unit sale price -- an express,
    narrow statutory exception. The corrected specification explicitly
    warns against implementing this as a blanket "single item = exempt"
    rule; that shortcut is not implemented here or anywhere else in this
    handler. This now uses the already-extracted `unit_sale_price`
    declaration (app/nlp/patterns.py already produces it; nothing previously
    consumed it) for that one deterministic comparison, and otherwise keeps
    the prior manual-review-first posture -- LM-SCAN still cannot reliably
    determine general multi-unit-pack applicability from a listing alone,
    so nothing here ever asserts a confident violation from a text hint by
    itself; a hint only decides whether to apply the same evidence-quality-
    aware absence logic used everywhere else in this file (never a fixed
    auto-fail, never a fixed auto-pass).
    """
    mrp_decl = ctx.best(F.MRP)
    unit_price_decl = ctx.best(F.UNIT_SALE_PRICE)

    if mrp_decl and unit_price_decl and _currency_declarations_equal(mrp_decl, unit_price_decl):
        return ValidationOutcome(
            status=ComplianceStatus.PASS,
            reason=(
                "The declared unit sale price equals the retail sale price; Rule 6(11) "
                "expressly does not require a separate unit sale price disclosure in this case."
            ),
            confidence=round(min(mrp_decl.confidence, unit_price_decl.confidence), 2),
            checked_fields=[F.MRP, F.UNIT_SALE_PRICE],
            evidence=_evidence_for(ctx, F.MRP) + _evidence_for(ctx, F.UNIT_SALE_PRICE),
        )

    if not ctx.has_sufficient_evidence:
        return ValidationOutcome(
            status=ComplianceStatus.UNABLE_TO_VERIFY,
            reason="No page content or images were retrieved for this inspection.",
            confidence=0.3,
        )

    hint_patterns = config.get("multipack_hint_patterns")
    if hint_patterns and not ctx.has_value(F.UNIT_SALE_PRICE):
        haystack = _declared_text_haystack(ctx, [F.PRODUCT_NAME, F.NET_QUANTITY])
        if any(re.search(p, haystack, re.IGNORECASE) for p in hint_patterns):
            return _absence_outcome(
                ctx,
                [F.UNIT_SALE_PRICE],
                config.get(
                    "reason_multipack_hint",
                    "Listing text suggests this may be a multi-unit pack (e.g. 'Pack of N') "
                    "and no distinct unit sale price was found, and the retail sale price "
                    "does not appear to already equal a declared unit price.",
                ),
            )

    reason = config.get("reason_default", "This requirement needs human judgment and is routed for officer review.")
    return ValidationOutcome(status=ComplianceStatus.NEEDS_MANUAL_REVIEW, reason=reason, confidence=0.5)


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
    "fast_food_restaurant_gate": _fast_food_restaurant_gate,
    "when_packed_phrase": _when_packed_phrase,
    "small_package_exemption_gate": _small_package_exemption_gate,
    "name_address_form_check": _name_address_form_check,
    "chapter2_applicability_gate": _chapter2_applicability_gate,
    "advertisement_net_quantity_check": _advertisement_net_quantity_check,
    "unit_sale_price_check": _unit_sale_price_check,
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
