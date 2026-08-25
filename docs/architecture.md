# Architecture

## Design principle

The product brief's central instruction (Section 48) is that LM-SCAN is
*"AI-assisted regulatory inspection that reduces manual search and
highlights potential compliance issues with traceable evidence"* — not
*"AI that declares products illegal."* Every architectural decision below
exists to make that literally true: every finding traces back through a
`ComplianceCheck` to a `RuleVersion` (with a source citation) and to one or
more `Evidence` rows (with a pointer to the exact webpage text, OCR block,
or manual note that produced it).

## High-level data flow

```
Officer pastes URL
      │
      ▼
┌─────────────┐   ┌──────────────┐   ┌───────────────┐
│  Scraping    │──▶│   Storage    │   │  Screenshot    │
│ (Playwright  │   │ (raw HTML,   │   │  upload        │
│  + BS4/JSON- │   │  images)     │   │  (fallback)    │
│  LD parsing) │   └──────┬───────┘   └───────┬────────┘
└──────┬───────┘          │                   │
       │                  ▼                   │
       │           ┌─────────────┐            │
       │           │ Image        │◀───────────┘
       │           │ quality +    │
       │           │ OCR (Tesseract)│
       │           └──────┬───────┘
       ▼                  ▼
┌──────────────────────────────────┐
│  Declaration extraction (nlp/)    │  <- regex/keyword, source-tagged
└──────────────┬────────────────────┘
               ▼
┌──────────────────────────────────┐
│  Classification (nlp/classification)│ -> ProductCategoryCode
└──────────────┬────────────────────┘
               ▼
┌──────────────────────────────────┐
│  Compliance engine (compliance/)   │  <- loads active RuleVersions,
│   + Consistency engine             │     runs validators, gates by
│                                     │     category/exemption
└──────────────┬────────────────────┘
               ▼
   ComplianceCheck / Violation / Evidence rows
               │
     ┌─────────┴─────────┐
     ▼                   ▼
 Officer review      Report generation
 (ReviewDecision)    (Jinja2 -> HTML/PDF)
```

Every stage is recorded as a `PipelineEvent` row so the frontend can show
live progress (Section 30/43), and every stage is wrapped so a failure in
one never crashes the whole run (Section 26).

## Module boundaries and why they exist

- **`scraping/`** is deliberately split into an I/O boundary
  (`fetcher.py`, the only module that touches Playwright or makes live
  requests) and pure parsing logic (`base.py`, `extractors.py`,
  `blinkit.py`). This is what lets `tests/unit/test_scraper_extraction.py`
  run against saved HTML fixtures with zero network access (Section 36).
- **`ocr/`** is a `Protocol`-based pluggable interface
  (`OCREngine`) so `TesseractOCREngine` (wired, default) and
  `PaddleOCREngine` (interface implemented, dependencies not installed —
  see `docs/ocr.md`) are interchangeable via `ocr/registry.py`.
- **`nlp/`** owns the *shared* regex/keyword vocabulary
  (`patterns.py`) used both by the scraper's fallback-text-extraction
  strategy and by OCR-text declaration extraction, so "what does an
  MRP-looking string look like" is defined once, not twice.
- **`rules/`** is data, not code: `seed_rules.py` is the only
  place a new rule is added, `validators.py` is the small, closed set of
  generic validator functions (`PRESENCE_CHECK`, `PATTERN_CHECK`, ...)
  every rule is built from, and `loader.py` is the versioning-aware
  upsert that keeps historical `ComplianceCheck` rows pointing at
  immutable `RuleVersion` snapshots (Section 12).
- **`compliance/`** is the orchestrator (`engine.py`) plus the
  cross-source consistency engine (`consistency.py`) — the only two
  places that decide what status a finding gets, and both weigh evidence
  quality rather than doing a naive "if missing then illegal" (Section 13).
- **`services/`** is glue: `pipeline.py` is the one place that
  calls scraping → OCR → extraction → classification → compliance in
  order; `scraping_service.py`, `image_service.py`,
  `classification_service.py` each persist one stage's output.

## Database

20 tables (see `apps/backend/app/models/`), matching Section 21's minimum
list plus a few additive tables the pipeline needed for honest progress
reporting (`pipeline_events`) and rule-content storage
(`rule_versions.validator_config` as JSON, so new data-driven rules don't
need schema migrations). Full list and rationale for each table is in the
model docstrings; see also `apps/backend/alembic/versions/` for the actual
DDL history.

## Rule versioning (Section 12)

`Rule` holds a stable business key (`rule_key`, e.g.
`LMPC-R6-1E-MRP`). `RuleVersion` holds the actual content (requirement
text, validator config, source citation, effective dates) and is
**immutable** once created — `app/rules/loader.py` hashes a rule's content
fields and only creates a *new* `RuleVersion` row (flagging the old one
`is_current = False`) when the content actually changed. Every
`ComplianceCheck.rule_version_id` is a hard foreign key to one specific
version, so re-running `python -m app.rules.loader` after editing
`seed_rules.py` (or an admin editing a rule via `PUT /rules/{key}`) never
retroactively changes what a past inspection shows.

## Evidence abstraction and the future physical module

Section 15 asks for an `EvidenceSource` abstraction so a future physical
inspection module (camera measurement, calibration cards) can plug into the
same pipeline without rewriting extraction/rules/compliance/evidence/reports.

`app/models/enums.py::EvidenceSourceType` already has four values:
`ONLINE_LISTING`, `USER_INPUT`, `MANUAL_REVIEW`, and `PHYSICAL_IMAGE`
(reserved, unused in V1). `ProductImage.source_type` and
`InspectionSource.source_type` are typed against this enum today. A future
physical module would:

1. Add a `PHYSICAL_MEASUREMENT` evidence source type and a
   `physical_measurements` table (dimensions, weight, calibration
   reference) — additive, no existing table changes.
2. Feed measurements into `Declaration` rows the same way OCR does today
   (`source_type="PHYSICAL_IMAGE"`, pointing at a captured image + a new
   measurement result), so the compliance engine's `InspectionContext`
   (`app/compliance/context.py`) needs zero changes — it already reads
   `Declaration` rows generically by `field_name`.
3. Add new rules to `seed_rules.py` for the physically-measured
   requirements cataloged as out-of-scope in `docs/legal-rules.md`
   (Rule 7 numeral-height tables, Rule 8 panel layout) — the validator
   architecture (`PRESENCE_CHECK`/`NUMERIC_CHECK`/...) already supports a
   tolerance-band numeric check with no new validator type needed.
4. The consistency engine (Section 14) would then compare
   `ONLINE_LISTING` vs. `PHYSICAL_IMAGE` declarations exactly the way it
   already compares `ONLINE_LISTING` vs. today's `IMAGE_OCR` — the
   `_ONLINE_SOURCES`/`_IMAGE_SOURCES` split in
   `app/compliance/consistency.py` would just gain a third source-type set.

No part of the extraction, rule, compliance, evidence, or report layer
needs to change shape to support this — only new rows and new rule data.
No physical measurement code is implemented in V1 (Section 47: "Do not
create fake implementations just to claim the feature exists").

## LLM usage (Section 46)

**None is used in the implemented pipeline.** Declaration extraction is
regex/keyword-based (`app/nlp/patterns.py`), classification is a keyword
frequency table (`app/nlp/classification.py`), and the compliance engine is
a deterministic rule evaluator (`app/rules/validators.py`). This is a
conservative, auditable choice appropriate for a preliminary compliance
tool — every decision is traceable to source code and rule data, not to an
opaque model call. If a future version adds an LLM for
normalization/explanation assistance, it must never gate the final status
returned by the compliance engine, per Section 46.
