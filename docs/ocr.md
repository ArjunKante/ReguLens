# OCR Subsystem

## Interface (Section 7)

`app/ocr/base.py::OCREngine` is a `Protocol`:

```python
class OCREngine(Protocol):
    name: str
    version: str
    def recognize(self, image_path: str) -> list[OCRTextBlock]: ...
```

`OCRTextBlock` carries `text`, `confidence` (0..1), `bounding_box`,
`engine`, `engine_version`, `model_name` — matching every field the brief
asks for (Section 7). Every block is persisted to the `ocr_results` table,
**including low-confidence ones** — the engine never filters by a
confidence threshold; that decision belongs to the compliance layer, which
uses OCR confidence to inform (not override) its own status decisions
(`app/compliance/context.py::average_ocr_confidence`).

## Engines

### Tesseract (wired, default)

`app/ocr/tesseract_engine.py::TesseractOCREngine` uses `pytesseract`'s
`image_to_data` to get per-word bounding boxes and confidences directly
from the tesseract binary. `TESSERACT_CMD` in `.env` points at the binary
(a bare `tesseract` on PATH for Linux/Docker; a full path like
`C:\Program Files\Tesseract-OCR\tesseract.exe` on Windows dev machines
where it isn't on PATH).

**Languages.** Rule 9(4) permits mandatory declarations to be in Hindi
(Devanagari) or English — a label whose required field is printed only in
Hindi is real, legally-compliant evidence, not something OCR is allowed to
ignore. `OCR_LANGUAGES` (`app/core/config.py::ocr_languages`, default
`"eng+hin"`) is passed as Tesseract's multi-language `lang=` argument, so
both scripts are recognized in the same pass. The Docker image installs
`tesseract-ocr-hin` (the Hindi trained-data package) alongside
`tesseract-ocr` for this; a local, non-Docker Tesseract install needs the
Hindi language pack too — see the README's setup section. Recognizing the
text is only half the job: `app/nlp/patterns.py` also carries Devanagari
keyword patterns (शुद्ध मात्रा, अधिकतम खुदरा मूल्य, निर्माता, ...) for the
same fields its English patterns already cover, and
`app/rules/quantity.py` understands Devanagari unit words (ग्राम,
किलोग्राम, मिली, लीटर, ...) for the Rule 26(a) small-package exemption
gate — without this, correctly-transcribed Hindi text still wouldn't be
recognized as a declaration. Devanagari **numerals** (०-९) are explicitly
not parsed — real packaging overwhelmingly uses Arabic numerals even in
Hindi-language text, so this stays a documented non-goal rather than a
guessed conversion table. Marathi was considered and deliberately left out:
Rule 9(4) names only Hindi and English, and mixing a third, closely-related
Devanagari script into the same Tesseract pass raises glyph-confusion risk
between Hindi and Marathi for no compliance benefit.

### PaddleOCR (interface implemented, not installed)

Section 7 names PaddleOCR as the "preferred initial provider." Being
straightforward about V1's actual state: **`paddleocr`/`paddlepaddle` are
not installed** in `requirements.txt`. They add a very large
(multi-hundred-MB, GPU-toolchain-adjacent) dependency footprint that was
judged impractical for this academic prototype's build/CI environment.

`app/ocr/paddleocr_engine.py::PaddleOCREngine` is a real, complete adapter
implementation against the actual `paddleocr` Python API — it would work if
those packages were installed — but it imports them lazily (inside
`__init__`, never at module load time) specifically so the rest of the app
keeps working without them. `app/ocr/registry.py::get_ocr_engine` reads
`OCR_ENGINE` from settings; if set to `paddleocr` and the import fails, it
logs a warning and falls back to `TesseractOCREngine` — this is the actual,
tested "Allow fallback to Tesseract where practical" behavior the brief
asks for (Section 7), not a TODO.

To enable PaddleOCR: `pip install paddleocr paddlepaddle` and set
`OCR_ENGINE=paddleocr` in `.env`.

## Image quality checks (Section 8)

`app/vision/image_quality.py::assess_quality` runs on every image
(uploaded screenshot or downloaded product photo) and reports:

- **Resolution** — flags images below 400px on the shorter side.
- **Blur** — variance of a Laplacian-like edge filter (PIL
  `ImageFilter.FIND_EDGES` + numpy `.var()`). Calibrated against synthetic
  label-like text images in `tests/unit/test_image_quality.py`: sharp
  renders scored ~5000+, the same content Gaussian-blurred (radius ≥ 6)
  dropped to ~400-430. `BLUR_VARIANCE_THRESHOLD = 800` is a documented
  starting point, **not** a value validated against real camera photos —
  see `docs/limitations.md`.
- **Contrast** — grayscale standard deviation.
- **Glare** — fraction of near-white pixels, but only counted when
  contrast is *also* adequate. A plain white product-label background is
  *also* mostly near-white pixels but has **low** overall contrast (a flat
  background, not glare); genuine glare (a reflective hotspot on glossy
  packaging) shows up as a bright patch against an otherwise more varied,
  higher-contrast scene. This distinction is unit-tested
  (`test_plain_white_background_is_not_misclassified_as_glare`).

None of these gate OCR from running — they inform `quality_acceptable` and
feed `Evidence`/confidence downstream (Section 33: "do not confuse AI
confidence with legal certainty").

## Preprocessing (Section 8)

`app/vision/preprocessing.py::preprocess_for_ocr` resizes to a
tesseract-friendly range (800–2200px), converts to grayscale, autocontrasts,
and sharpens — returning a **new** in-memory image. The original file on
disk is never touched (Section 8: "must preserve the original image").

## Declaration extraction from OCR text

`app/nlp/declaration_extractor.py::extract_declarations_from_ocr` orders
OCR blocks top-to-bottom/left-to-right, joins them into one text blob (so a
multi-word phrase like "MRP" / "Rs." / "60.00" split across blocks still
reads coherently), and runs the same `find_field_candidates` regex library
the scraper uses on webpage text. Combined confidence is
`regex_match_confidence × avg_ocr_block_confidence`, so a textually-perfect
regex match on garbled, low-confidence OCR text still ends up low-confidence
overall.
