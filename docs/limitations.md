# Known Limitations

Honest, explicit list — Section 53 asks for this directly. If something
isn't listed here, it's because it works as documented elsewhere, not
because it was overlooked.

## Legal / rule coverage

- Only 14 rules drawn directly from the Legal Metrology (Packaged
  Commodities) Rules, 2011 (plus 6 internal cross-source consistency
  checks) are implemented — the subset that is actually checkable from an
  online listing. Rules 7–8, 12–25, 27–34 and most Schedules are cataloged
  as explicitly out of scope with reasons in `docs/legal-rules.md`, not
  silently omitted.
- Rule 13's full unit-format requirements were not present in the excerpt
  of the source PDF reviewed while building the rule database; net-quantity
  validation is a basic "numeric value + recognized unit" pattern check,
  not a full format validator.
- This system covers only the Legal Metrology (Packaged Commodities)
  Rules, 2011. FSSAI food-labeling regulations, Drugs & Cosmetics Rules,
  BIS standards, and State-level notifications are referenced by
  cross-pointer where the source PDF mentions them (e.g. "food articles are
  governed by the FSS Act instead") but are not independently implemented —
  no such source document was supplied.

## Extraction quality

- Declaration extraction is regex/keyword-based, not an NLP model. It will
  miss phrasings the patterns in `app/nlp/patterns.py` don't anticipate,
  and it will occasionally produce false-positive low-confidence matches
  (e.g. a bare number matching the loose net-quantity fallback pattern).
  Every match carries a confidence score specifically so downstream logic
  (and the officer reading the UI) can weigh this.
- The classifier (`app/nlp/classification.py`) is a hand-built keyword
  table, not a trained model. It will return `UNKNOWN` for products whose
  title/description don't contain any of its ~120 keywords, and it has no
  formal accuracy measurement (see `docs/dataset.md`).
- Image-quality heuristics (blur/contrast/glare thresholds in
  `app/vision/image_quality.py`) are calibrated against synthetic
  label-like test images, not a corpus of real camera/screenshot photos —
  documented explicitly in the module and in `docs/ocr.md`.

## OCR

- PaddleOCR (the brief's stated preferred provider) is **not installed** —
  only its interface is implemented. Tesseract is the actual, tested engine
  in this build. See `docs/ocr.md`.

## Scraping

- Only one platform adapter (`BlinkitScraper`) exists beyond the generic
  fallback. Amazon/Flipkart/Zepto/BigBasket adapters are architecturally
  supported (subclass `ProductScraper`, register in
  `app/scraping/registry.py`) but not implemented.
- Marketplaces with aggressive anti-bot protection (Cloudflare/Akamai
  challenges, JS-heavy fingerprinting checks) may block even a
  fully-compliant Playwright fetch. LM-SCAN does not attempt to circumvent
  this (by design — see Section 4) and will report `ACCESS_DENIED`/`FAILED`
  and fall back to the screenshot-upload flow.
- No automated integration test exercises a real, live marketplace fetch —
  this was manually smoke-tested once during development (see
  `docs/demo-guide.md` and `docs/testing.md`), not part of CI.

## Compliance engine

- Evidence-quality scoring (`InspectionContext.evidence_quality_score`) is
  a hand-tuned heuristic combining three signals with equal weight — it has
  not been validated against real officer judgments of "was this evidence
  actually adequate."
- `NUMERIC_CHECK` is implemented but not exercised by any V1 rule; it
  exists for architectural completeness ahead of a future physical
  measurement module.

## Background processing

- The pipeline runs as a FastAPI `BackgroundTasks` callback in the same
  process as the API server, per Section 30's "lightweight worker approach
  is acceptable for MVP." This means a backend restart mid-pipeline loses
  that in-flight run (it will be left `IN_PROGRESS` until manually
  re-triggered via `/analyze`). A production deployment should migrate to
  Celery/RQ, exactly as Section 30 anticipates — the pipeline function
  itself (`app/services/pipeline.py::run_inspection_pipeline`) takes a
  plain `(db, inspection_id)` and has no FastAPI-specific coupling, so this
  migration would not require rewriting pipeline logic.

## Frontend

- Rule Management's UI is read-focused (view all rules, versions, and
  citations); the create/update rule *forms* are not built — those
  operations are exercised via the API (`POST /rules`, `PUT
  /rules/{key}`), tested at the API layer, but have no dedicated frontend
  form in V1.
- No dark mode, no i18n/Hindi UI (declarations on packages may legally be
  in Hindi or English per Rule 9(4), but the LM-SCAN interface itself is
  English-only in V1).
- 8 mypy warnings remain in the backend (a documented enum/string-column
  typing pattern, functionally correct — see `docs/testing.md`).

## Testing

- No formal, labeled precision/recall/F1 evaluation exists — see
  `docs/dataset.md` for exactly what testing does and doesn't cover, and
  why no numbers are invented.
- Frontend test coverage is intentionally focused (10 tests: core shared
  components, the login flow, and route protection) rather than covering
  every page — a full click-through of every page was done manually (see
  `docs/testing.md`'s "Manual end-to-end smoke test" section) rather than
  automated end-to-end (e.g. Playwright/Cypress) tests, which are a natural
  next addition.

## Deployment

- See `docs/deployment.md`'s "What's NOT provided" section — no TLS, no
  production process manager config, no CI/CD, no object storage, no
  gated-migration rollout process.
