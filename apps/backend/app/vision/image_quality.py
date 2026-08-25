"""Image quality checks (Section 8): resolution, blur, contrast, glare.

Deliberately implemented with only Pillow + numpy (no OpenCV) to keep the
backend's system/install footprint small — these are documented heuristics,
not a trained quality model, and are used to *inform* confidence and the
PASS vs. NEEDS_MANUAL_REVIEW decision, never as a hard pass/fail gate on
their own (Section 33: "do not confuse AI confidence with legal certainty").
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter

MIN_ACCEPTABLE_DIMENSION = 400  # px, on the shorter side
BLUR_VARIANCE_THRESHOLD = 800.0  # below this, edge-variance suggests a blurry image
# Calibrated against synthetic label-like text images (see
# tests/unit/test_image_quality.py): sharp renders scored ~5000+, Gaussian-blurred
# (radius>=6) versions of the same content dropped to ~400-430. This is a
# documented starting point, not a validated threshold for real camera photos —
# see docs/limitations.md.
LOW_CONTRAST_STD_THRESHOLD = 25.0  # grayscale std-dev below this suggests flat/low contrast
GLARE_BRIGHT_PIXEL_RATIO_THRESHOLD = 0.5  # fraction of near-white pixels suggesting glare


@dataclass
class ImageQualityReport:
    width: int
    height: int
    is_blurry: bool
    blur_score: float
    contrast_score: float
    glare_detected: bool
    quality_acceptable: bool
    notes: list[str]


def validate_image(image: Image.Image) -> None:
    """Raises ValueError if the image cannot be used at all (corrupt, zero-size)."""
    image.verify()


def assess_quality(image: Image.Image) -> ImageQualityReport:
    # `.verify()` invalidates the image object for further use, so re-open logic is
    # handled by the caller; this function assumes `image` is already a live, loaded image.
    notes: list[str] = []
    width, height = image.size

    if min(width, height) < MIN_ACCEPTABLE_DIMENSION:
        notes.append(
            f"Image resolution ({width}x{height}) is below the recommended minimum "
            f"({MIN_ACCEPTABLE_DIMENSION}px on the shorter side); OCR accuracy may be reduced."
        )

    grayscale = image.convert("L")
    gray_array = np.asarray(grayscale, dtype=np.float64)

    # Blur: variance of a Laplacian-like edge filter. Low variance == few sharp
    # edges == likely blurry.
    edges = grayscale.filter(ImageFilter.FIND_EDGES)
    edge_array = np.asarray(edges, dtype=np.float64)
    blur_score = float(edge_array.var())
    is_blurry = blur_score < BLUR_VARIANCE_THRESHOLD
    if is_blurry:
        notes.append(f"Image appears blurry (edge-variance score {blur_score:.1f}).")

    # Contrast: standard deviation of the grayscale histogram.
    contrast_score = float(gray_array.std())
    if contrast_score < LOW_CONTRAST_STD_THRESHOLD:
        notes.append(f"Image appears low-contrast (std-dev {contrast_score:.1f}).")

    # Glare: a large fraction of blown-out (near-white) pixels co-occurring
    # with otherwise-adequate contrast elsewhere in the frame. The contrast
    # condition matters: a plain white product-label background is *also*
    # mostly near-white pixels, but has LOW overall contrast — that is a
    # flat background, not glare. Genuine glare (a reflective hotspot on
    # glossy packaging) shows up as a bright patch against a more varied,
    # higher-contrast scene. This is a documented heuristic, not a trained
    # classifier — see module docstring.
    bright_ratio = float((gray_array >= 250).mean())
    glare_detected = bright_ratio > GLARE_BRIGHT_PIXEL_RATIO_THRESHOLD and contrast_score >= LOW_CONTRAST_STD_THRESHOLD
    if glare_detected:
        notes.append(f"Possible glare/overexposure detected ({bright_ratio:.0%} near-white pixels).")

    quality_acceptable = not is_blurry and contrast_score >= LOW_CONTRAST_STD_THRESHOLD and not glare_detected

    return ImageQualityReport(
        width=width,
        height=height,
        is_blurry=is_blurry,
        blur_score=round(blur_score, 2),
        contrast_score=round(contrast_score, 2),
        glare_detected=glare_detected,
        quality_acceptable=quality_acceptable,
        notes=notes,
    )
