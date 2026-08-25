"""Image preprocessing before OCR (Section 8: "Preprocess -> Run OCR").

Never mutates or overwrites the original file — always returns a new
in-memory image, so the stored original remains pristine evidence
(Section 8: "The system must preserve the original image")."""
from __future__ import annotations

from PIL import Image, ImageEnhance, ImageOps

MAX_OCR_DIMENSION = 2200
MIN_OCR_DIMENSION = 800


def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    working = image.convert("RGB")

    width, height = working.size
    shortest = min(width, height)
    if shortest < MIN_OCR_DIMENSION:
        scale = MIN_OCR_DIMENSION / shortest
        working = working.resize((int(width * scale), int(height * scale)), Image.Resampling.LANCZOS)
    elif max(width, height) > MAX_OCR_DIMENSION:
        scale = MAX_OCR_DIMENSION / max(width, height)
        working = working.resize((int(width * scale), int(height * scale)), Image.Resampling.LANCZOS)

    grayscale = ImageOps.grayscale(working)
    autocontrasted = ImageOps.autocontrast(grayscale, cutoff=1)
    sharpened = ImageEnhance.Sharpness(autocontrasted).enhance(1.5)
    return sharpened
