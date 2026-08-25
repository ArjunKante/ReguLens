"""Pluggable OCR interface (Section 7).

`OCREngine.recognize` must return every detected text block, including
low-confidence ones — the engine never discards results, per Section 7's
explicit instruction. Downstream consumers (declaration extraction,
compliance engine) decide what to do with low confidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class BoundingBox:
    x: int
    y: int
    width: int
    height: int

    def as_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


@dataclass
class OCRTextBlock:
    text: str
    confidence: float  # 0..1
    bounding_box: BoundingBox
    engine: str
    engine_version: str
    model_name: str | None = None


class OCREngine(Protocol):
    name: str
    version: str

    def recognize(self, image_path: str) -> list[OCRTextBlock]: ...
