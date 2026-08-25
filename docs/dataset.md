# Dataset / Evaluation

Section 38 asks for `data/samples`, `data/annotations`, `data/fixtures`, and
measured (not invented) OCR/extraction/classification/compliance
precision/recall/F1 numbers.

## Honest status for V1

**No formal, labeled evaluation dataset with ground-truth annotations was
built, and no precision/recall/F1/confusion-matrix numbers are reported
here.** Fabricating plausible-looking metrics would violate the explicit
instruction in Section 38 ("Do not invent performance numbers. Only report
measured results.") — so this document says what actually exists instead of
inventing what doesn't.

## What actually exists

### `apps/backend/tests/fixtures/html/` — the real sample set for V1

Six hand-authored HTML fixtures, each representing a distinct scenario
named in Section 35:

| File | Scenario |
|---|---|
| `success_listing.html` | Complete listing: JSON-LD + OpenGraph + visible text all present, MRP/net-quantity/manufacturer/country-of-origin/consumer-care all declared |
| `missing_declaration.html` | MRP and net quantity present; manufacturer and consumer-care entirely absent |
| `conflicting_mrp.html` | JSON-LD `offers.price` differs from the page's stated MRP (used to verify the scraper does *not* conflate selling price with MRP — see `docs/scraper.md`) |
| `missing_quantity.html` | Net quantity declaration absent; other fields present |
| `incomplete_page.html` | A near-empty "still loading" page |
| `malformed_page.html` | Deliberately invalid JSON-LD and unbalanced HTML tags |

These are consumed directly by `tests/unit/test_scraper_extraction.py` (12
tests) as **correctness** fixtures (does the scraper extract what it should,
degrade gracefully on what it shouldn't) rather than as a statistical
evaluation corpus. This is real, deterministic, repeatable testing — just
not the same thing as a labeled precision/recall dataset.

### `data/` (this repository)

```
data/
  samples/       Placeholder — intended home for real (anonymized/synthetic)
                 product listing captures once available; currently empty
                 beyond a README pointing back to the pytest fixtures above.
  annotations/   Placeholder — intended home for human-labeled ground truth
                 (correct field values per sample) once a real sample set
                 exists. Empty in V1.
  fixtures/      Placeholder — intended home for OCR/image test fixtures
                 beyond the HTML fixtures already under apps/backend/tests/.
                 Empty in V1.
```

These directories exist (per Section 38's structure) with README stubs
explaining their intended purpose, rather than being populated with
synthetic-looking "sample data" that would misrepresent itself as
evaluation-grade.

## What correctness testing *does* exist, and where

- **OCR**: `tests/unit/test_ocr_tesseract.py` verifies the Tesseract
  adapter returns non-empty text with valid confidence/bbox for a rendered
  synthetic label image, and that low-confidence blocks are not silently
  dropped — a correctness check, not an accuracy measurement against
  ground truth.
- **Declaration extraction**: `tests/unit/test_declaration_extraction.py`
  and `test_scraper_extraction.py` verify specific inputs produce the
  expected field/value/source/confidence — again correctness, not recall
  against a labeled corpus.
- **Classification**: `tests/unit/test_classification.py` verifies five
  representative title/description strings map to the expected category —
  five hand-picked examples, not a statistically meaningful accuracy
  figure.
- **Compliance engine**: `tests/integration/test_compliance_engine.py`
  verifies each of the five statuses is reachable and correct for
  representative scenarios (see `docs/testing.md`).

## If this were extended past V1

A genuine evaluation pass would need: (1) a set of real (or realistic
synthetic) product listings with permission to store/use them, (2) human
annotation of the correct value for every declaration field on each
listing, (3) a scoring script comparing LM-SCAN's extracted
`Declaration.normalized_value` against the annotation per field, and (4)
the same for classification (predicted vs. annotated category) and for
compliance status (predicted vs. an officer's actual determination on a
sample of real inspections). None of that infrastructure was built in V1;
the `data/annotations/` directory is where its output would live.
