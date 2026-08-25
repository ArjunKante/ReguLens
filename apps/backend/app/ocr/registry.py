from __future__ import annotations

import logging

from app.core.config import get_settings
from app.ocr.base import OCREngine
from app.ocr.tesseract_engine import TesseractOCREngine

logger = logging.getLogger(__name__)
settings = get_settings()

_engine_singleton: OCREngine | None = None


def get_ocr_engine() -> OCREngine:
    global _engine_singleton
    if _engine_singleton is not None:
        return _engine_singleton

    if settings.ocr_engine == "paddleocr":
        try:
            from app.ocr.paddleocr_engine import PaddleOCREngine

            _engine_singleton = PaddleOCREngine()
            return _engine_singleton
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "OCR_ENGINE=paddleocr requested but unavailable (%s); falling back to Tesseract.",
                exc,
            )

    _engine_singleton = TesseractOCREngine()
    return _engine_singleton


def reset_for_tests() -> None:
    global _engine_singleton
    _engine_singleton = None
