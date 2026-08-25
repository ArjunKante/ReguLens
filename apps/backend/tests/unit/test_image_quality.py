"""Image quality heuristics tests (Section 8/34)."""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFilter

from app.vision.image_quality import assess_quality


def _sharp_textured_image() -> Image.Image:
    """A label-like image with a moderate amount of fine text/line detail,
    representative of a product package photo rather than a mostly-blank
    page — deliberately avoids near-all-white framing so the blur signal
    isn't swamped by background pixels."""
    img = Image.new("RGB", (600, 600), "white")
    draw = ImageDraw.Draw(img)
    for y in range(40, 580, 24):
        draw.text((30, y), "Net Quantity 250 g MRP Rs. 99.00 Mfg by Example Foods", fill="black")
    return img


def test_sharp_high_contrast_image_is_not_flagged_blurry():
    report = assess_quality(_sharp_textured_image())
    assert report.is_blurry is False


def test_blurred_image_is_flagged_blurry():
    sharp = _sharp_textured_image()
    blurred = sharp.filter(ImageFilter.GaussianBlur(radius=15))
    sharp_report = assess_quality(sharp)
    blurred_report = assess_quality(blurred)
    assert blurred_report.blur_score < sharp_report.blur_score
    assert blurred_report.is_blurry is True


def test_plain_white_background_is_not_misclassified_as_glare():
    """A plain white product-label background (low local variance) must not
    be conflated with photographic glare — see image_quality.py docstring."""
    img = Image.new("RGB", (500, 500), "white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), "MRP Rs. 99", fill="black")
    report = assess_quality(img)
    assert report.glare_detected is False


def test_small_image_flags_low_resolution_note():
    img = Image.new("RGB", (100, 100), "white")
    report = assess_quality(img)
    assert any("resolution" in note.lower() for note in report.notes)
