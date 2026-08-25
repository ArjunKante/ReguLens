"""PaddleOCR adapter (Section 7: "Preferred initial provider: PaddleOCR").

Honest status for this V1 build: the `paddleocr` / `paddlepaddle` packages
are NOT installed in requirements.txt because they add a very large
(multi-hundred-MB, GPU-toolchain-adjacent) dependency footprint that is
impractical for this academic prototype's build environment. The interface
below is real and would work if those packages were installed — importing
them is deferred to first use (never at module import time) specifically so
the rest of the application keeps working when PaddleOCR is absent.

`app/ocr/registry.py` automatically falls back to TesseractOCREngine if this
engine's dependencies are missing, and logs that it did so — this is the
concrete "Allow fallback to Tesseract where practical" behavior the product
brief asks for. See docs/ocr.md and docs/limitations.md for the full
explanation; this is not silently pretended to work.
"""
from __future__ import annotations

from app.ocr.base import BoundingBox, OCRTextBlock


class PaddleOCREngineUnavailable(RuntimeError):
    pass


class PaddleOCREngine:
    name = "paddleocr"
    version = "unknown"

    def __init__(self) -> None:
        try:
            from paddleocr import PaddleOCR  # type: ignore[import-not-found]
        except ImportError as exc:
            raise PaddleOCREngineUnavailable(
                "paddleocr/paddlepaddle are not installed in this environment. "
                "Install the optional 'paddleocr' extra to enable this engine; "
                "LM-SCAN will use Tesseract in the meantime."
            ) from exc
        self._ocr = PaddleOCR(use_angle_cls=True, lang="en")
        try:
            import paddleocr  # type: ignore[import-not-found]

            self.version = getattr(paddleocr, "__version__", "unknown")
        except ImportError:
            pass

    def recognize(self, image_path: str) -> list[OCRTextBlock]:
        result = self._ocr.ocr(image_path, cls=True)
        blocks: list[OCRTextBlock] = []
        for line in result or []:
            for box_points, (text, confidence) in line:
                xs = [p[0] for p in box_points]
                ys = [p[1] for p in box_points]
                box = BoundingBox(
                    x=int(min(xs)),
                    y=int(min(ys)),
                    width=int(max(xs) - min(xs)),
                    height=int(max(ys) - min(ys)),
                )
                blocks.append(
                    OCRTextBlock(
                        text=text,
                        confidence=float(confidence),
                        bounding_box=box,
                        engine=self.name,
                        engine_version=self.version,
                        model_name="PP-OCRv4",
                    )
                )
        return blocks
