"""Tesseract OCR engine adapter — the V1 default/wired-up engine (Section 7:
"Allow fallback to Tesseract where practical")."""
from __future__ import annotations

import logging

import pytesseract
from PIL import Image

from app.core.config import get_settings
from app.ocr.base import BoundingBox, OCRTextBlock

logger = logging.getLogger(__name__)
settings = get_settings()


class TesseractOCREngine:
    name = "tesseract"

    def __init__(self) -> None:
        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
        try:
            self.version = str(pytesseract.get_tesseract_version())
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not determine tesseract version: %s", exc)
            self.version = "unknown"

    def recognize(self, image_path: str) -> list[OCRTextBlock]:
        image = Image.open(image_path)
        data = pytesseract.image_to_data(
            image, lang=settings.ocr_languages, output_type=pytesseract.Output.DICT
        )

        blocks: list[OCRTextBlock] = []
        n = len(data.get("text", []))
        for i in range(n):
            text = (data["text"][i] or "").strip()
            if not text:
                continue
            try:
                conf_raw = float(data["conf"][i])
            except (ValueError, TypeError):
                conf_raw = -1.0
            confidence = max(0.0, conf_raw) / 100.0 if conf_raw >= 0 else 0.0
            box = BoundingBox(
                x=int(data["left"][i]),
                y=int(data["top"][i]),
                width=int(data["width"][i]),
                height=int(data["height"][i]),
            )
            blocks.append(
                OCRTextBlock(
                    text=text,
                    confidence=confidence,
                    bounding_box=box,
                    engine=self.name,
                    engine_version=self.version,
                    model_name="tesseract-default",
                )
            )
        return blocks
