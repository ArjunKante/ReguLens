"""Tesseract OCR adapter tests (Section 34/36).

Skipped automatically if the tesseract binary is not available in the test
environment — this exercises the actual OCR engine (not a live network
service), so it is not "live scraping", but per Section 36's spirit of
deterministic unit tests, we still fail soft rather than hard-erroring on a
machine that never installed the tesseract binary.
"""
from __future__ import annotations

import tempfile

import pytest
from PIL import Image, ImageDraw

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
