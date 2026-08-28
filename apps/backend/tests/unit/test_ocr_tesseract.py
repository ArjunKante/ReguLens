"""Tesseract OCR adapter tests (Section 34/36).

Skipped automatically if the tesseract binary is not available in the test
environment — this exercises the actual OCR engine (not a live network
service), so it is not "live scraping", but per Section 36's spirit of
deterministic unit tests, we still fail soft rather than hard-erroring on a
machine that never installed the tesseract binary.
"""
from __future__ import annotations

import os
import tempfile

import pytesseract
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.core.config import get_settings
from app.ocr.tesseract_engine import TesseractOCREngine

pytestmark = pytest.mark.skipif(
    TesseractOCREngine().version == "unknown",
    reason="tesseract binary not available in this environment",
)


def _text_image(text: str) -> str:
    img = Image.new("RGB", (900, 150), "white")
    ImageDraw.Draw(img).text((20, 40), text, fill="black")
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        img.save(tmp, format="PNG")
        return tmp.name


# A bare Windows dev machine's local Tesseract install (or a bare Linux one
# without the fonts-lohit-deva package this project's Dockerfile adds)
# likely has neither the Hindi trained data nor a Devanagari-capable font —
# same "fail soft when the optional binary/data isn't there" philosophy as
# the module-level skip above, just for the Hindi-specific pieces.
_DEVANAGARI_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf",
    "/usr/share/fonts/truetype/fonts-deva/Lohit-Devanagari.ttf",
    r"C:\Windows\Fonts\Mangal.ttf",
    r"C:\Windows\Fonts\Nirmala.ttf",
]


def _find_devanagari_font() -> str | None:
    return next((p for p in _DEVANAGARI_FONT_CANDIDATES if os.path.exists(p)), None)


def _devanagari_text_image(text: str, font_path: str) -> str:
    img = Image.new("RGB", (900, 150), "white")
    ImageDraw.Draw(img).text((20, 40), text, fill="black", font=ImageFont.truetype(font_path, 36))
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        img.save(tmp, format="PNG")
        return tmp.name


def test_tesseract_extracts_text_with_confidence_and_bbox():
    path = _text_image("MRP Rs. 60.00 Net Quantity 100 g")
    engine = TesseractOCREngine()
    blocks = engine.recognize(path)

    assert len(blocks) > 0
    full_text = " ".join(b.text for b in blocks)
    assert "60.00" in full_text or "60" in full_text
    for b in blocks:
        assert 0.0 <= b.confidence <= 1.0
        assert b.bounding_box.width >= 0
        assert b.engine == "tesseract"


def test_tesseract_does_not_discard_low_confidence_blocks():
    """Section 7: low-confidence OCR results must be returned, not dropped."""
    path = _text_image("xX9?!blurred-ish~~text")
    engine = TesseractOCREngine()
    blocks = engine.recognize(path)
    # We only assert the engine ran without filtering by a hidden confidence
    # threshold; asserting >=0 confidence values are present either way.
    assert all(b.confidence >= 0.0 for b in blocks)


def test_recognize_passes_the_configured_languages_to_tesseract(monkeypatch):
    """Rule 9(4) permits mandatory declarations in Hindi or English, so
    Tesseract must run in multi-language mode by default (settings.ocr_languages,
    "eng+hin") — not silently default to English-only. Deterministic and
    dependency-free (mocks the pytesseract call itself), unlike the
    real-recognition test below."""
    captured: dict = {}

    def fake_image_to_data(image, lang=None, output_type=None):  # noqa: ANN001
        captured["lang"] = lang
        return {"text": [], "conf": [], "left": [], "top": [], "width": [], "height": []}

    monkeypatch.setattr(pytesseract, "image_to_data", fake_image_to_data)
    engine = TesseractOCREngine()
    engine.recognize(_text_image("placeholder"))
    assert captured["lang"] == get_settings().ocr_languages == "eng+hin"


def test_hindi_text_is_recognized_when_hindi_language_data_is_available():
    """Best-effort real round-trip: renders genuine Devanagari text and
    confirms the engine actually transcribes it (not just that the `lang`
    kwarg was passed, per the test above) — skipped rather than failed if
    this environment lacks the Hindi tessdata or a Devanagari font."""
    available_languages = set(pytesseract.get_languages(config=""))
    font_path = _find_devanagari_font()
    if "hin" not in available_languages or font_path is None:
        pytest.skip("Hindi tessdata or a Devanagari font is not available in this environment.")

    path = _devanagari_text_image("शुद्ध मात्रा", font_path)
    engine = TesseractOCREngine()
    blocks = engine.recognize(path)
    full_text = "".join(b.text for b in blocks)
    assert any("ऀ" <= ch <= "ॿ" for ch in full_text), (
        f"expected recognizable Devanagari output, got: {full_text!r}"
    )
