# Compliance Engine

## The rule engine architecture (Section 11)

Every rule is a `RuleVersion` row (data), not a hard-coded `if` statement.
`app/rules/validators.py` implements the generic validator types Section 11
asks for, and `app/compliance/engine.py::run_compliance_checks` is the only
place that dispatches `rule_version.validation_type` to a validator
function — adding a rule never means touching the engine, only adding a row
to `app/rules/seed_rules.py::SEED_RULES` (see `docs/legal-rules.md` for the
full, source-cited list of implemented rules).

| `validation_type` | What it checks | Example rule |
|---|---|---|
| `PRESENCE_CHECK` | At least one of a set of field-groups (DNF: OR of ANDs) has a value | Manufacturer/packer/importer name+address |
| `PATTERN_CHECK` | A field's value matches one of a set of regexes | MRP currency format, net-quantity units |
| `DATE_CHECK` | A field parses as a date/month-year; absence has a configurable fallback status | Mfg date, best-before date |
| `CROSS_FIELD_CHECK` | Dispatches to a named Python handler for logic that genuinely needs code (gating, aggregation) | Country-of-origin gate, e-commerce display aggregate, small-package exemption |
| `CONSISTENCY_CHECK` | Compares the same field across `ONLINE_LISTING` vs. `IMAGE_OCR` sources | MRP/net-qty/name/manufacturer/importer/country consistency |
| `MANUAL_REVIEW_CHECK` | Always routes to a human, with a rule-specific explanatory message | Manner of declaration (legibility), unit sale price |
| `NUMERIC_CHECK` | A numeric value falls within a configured range | Implemented, not exercised by any V1 rule — reserved for a future physical-measurement tolerance check |

## Status decision logic (Section 13)

The brief is explicit: never do a naive "if missing then illegal." Every
validator that can conclude "the field is absent" routes through
`app/rules/validators.py::_absence_outcome`, which asks two questions in
order:

1. **Was there any evidence at all** for this inspection
   (`InspectionContext.has_sufficient_evidence` — did the page fetch
   succeed, or were any images supplied)? If not → `UNABLE_TO_VERIFY`.
   Absence can't be distinguished from a retrieval failure.
2. **How complete was the evidence that *was* gathered**
   (`InspectionContext.evidence_quality_score`, a 0..1 heuristic combining
   page-fetch success, image availability, and average OCR confidence)?
   - Below 0.5 → `NEEDS_MANUAL_REVIEW` (this matches the brief's worked
     example: "If MRP is not found but webpage/images have poor quality
     → NEEDS_MANUAL_REVIEW").
   - 0.5 or above → `POTENTIAL_NON_COMPLIANCE` ("If MRP is clearly absent
     in a high-quality complete listing → POTENTIAL_NON_COMPLIANCE").

A fetch that HTTP-succeeded but retrieved nothing real (`WebPage.hollow`,
set by `services/pipeline.py`'s hollow-success detection — e.g. Blinkit
serving its generic app-shell homepage instead of the listing because a
stateless fetch never provides the delivery-location context the real page
needs) does **not** count as a successful fetch for either of the two
questions above (`InspectionContext.webpage_fetch_succeeded` excludes
hollow pages). Before this, a hollow "success" looked identical to a
genuinely complete scrape to this scoring, so a marketplace blocking/gating
the real page turned into confident `POTENTIAL_NON_COMPLIANCE` findings
against data that was never actually retrieved — found by live-testing real
Blinkit/Amazon listings, not a hypothetical.

`NOT_APPLICABLE` is decided *before* any validator runs, by category gating
(`RuleVersion.applicable_categories` / `excluded_categories`, e.g.
best-before-date only applies to `FOOD`) and by the Rule 26(a) small-package
exemption gate (`app/rules/validators.py::evaluate_small_package_exemption`)
— if net quantity parses to ≤10g/10ml and the product isn't tobacco, every
other rule (except the net-quantity rule itself, which would be circular)
is marked `NOT_APPLICABLE` with a citation to Rule 26(a).

Confidence numbers reported alongside every status are **extraction/
evidence confidence**, not legal certainty (Section 33) — this is stated in
the frontend's disclaimer banner and in every generated report.

## Cross-source consistency engine (Section 14)

`app/compliance/consistency.py::evaluate_consistency` compares the
highest-confidence `ONLINE_LISTING`-side declaration (webpage text or
structured metadata) against the highest-confidence `IMAGE_OCR`-side
declaration for the same field. Numeric fields (MRP, net quantity, unit
sale price) are compared on their normalized values
(`app/nlp/normalization.py`); text fields (product name, manufacturer,
importer, country of origin) use fuzzy matching
(`rapidfuzz.fuzz.token_sort_ratio ≥ 85`) so trivial formatting differences
("Pvt Ltd" vs. "Pvt. Ltd.") are not reported as conflicts.

- If only one side (or neither) has a value → `UNABLE_TO_VERIFY` ("requires
  both listing and image evidence").
- If both agree → `PASS`.
- If both disagree → `POTENTIAL_NON_COMPLIANCE`, with the reason text
  literally containing *"Potential inconsistency detected... Officer
  verification required"* per the brief's exact wording (Section 14), and
  both pieces of evidence attached.

These six consistency rules are seeded in `seed_rules.py` with
`source_document` explicitly reading *"LM-SCAN internal engineering rule...
this is NOT a citation to the Legal Metrology (Packaged Commodities)
Rules, 2011"* — the compliance engine never pretends an engineering check
is a statutory citation (Section 46).

## Why regex/keyword, not an LLM (Section 46)

The brief is explicit that an LLM, if used, may only assist with
normalization/entity-extraction/classification/explanation — never invent
rules, make final legal decisions, or fabricate missing information. V1
uses **no LLM anywhere** in the extraction or compliance path: declaration
extraction is regex/keyword (`app/nlp/patterns.py`), classification is a
keyword-frequency table (`app/nlp/classification.py`), and every status
decision is deterministic Python in `validators.py`/`consistency.py`. This
is slower to extend to new phrasings than an LLM would be, but every
decision is traceable to a line of code or a rule row — appropriate for a
tool whose entire premise is auditability.

## Aggregating to an overall status

`app/compliance/engine.py::compute_overall_status` picks the single most
severe status present across all of an inspection's checks, in priority
order `POTENTIAL_NON_COMPLIANCE > NEEDS_MANUAL_REVIEW > UNABLE_TO_VERIFY >
PASS`, with one special case: if every check came back `NOT_APPLICABLE`
(nothing could be meaningfully evaluated at all), the overall status is
`UNABLE_TO_VERIFY` rather than a hollow `PASS`.
