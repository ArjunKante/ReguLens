"""Glues image storage + quality assessment + OCR together and persists the
results (ProductImage, OCRResult) for one inspection (Section 8)."""
from __future__ import annotations

import datetime as dt
import io
import logging
import tempfile
import uuid

import httpx
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.enums import EvidenceSourceType
from app.models.scraping import OCRResult, ProductImage
from app.ocr.registry import get_ocr_engine
from app.storage.files import UnsafeUploadError, read_bytes, save_image_bytes
from app.vision.image_quality import assess_quality
from app.vision.preprocessing import preprocess_for_ocr

logger = logging.getLogger(__name__)
settings = get_settings()

MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024


def process_image_bytes(
    db: Session,
    *,
    inspection_id: uuid.UUID,
    content: bytes,
    source_type: EvidenceSourceType,
    original_url: str | None,
    original_filename: str | None,
    content_type: str | None,
    run_ocr: bool = False,
) -> ProductImage:
    storage_path, safe_filename = save_image_bytes(
        inspection_id, content, original_filename=original_filename, content_type=content_type
    )

    quality_report = None
    width = height = None
    try:
        with Image.open(io.BytesIO(content)) as img:
            img.verify()
        with Image.open(io.BytesIO(content)) as img:
            quality_report = assess_quality(img)
            width, height = quality_report.width, quality_report.height
    except Exception as exc:  # noqa: BLE001 - a corrupt image must not crash the pipeline
        logger.warning("Image quality assessment failed for %s: %s", storage_path, exc)

    product_image = ProductImage(
        inspection_id=inspection_id,
        source_type=source_type.value,
        original_url=original_url,
        storage_path=storage_path,
        original_filename=original_filename,
        content_type=content_type,
        width=width,
        height=height,
        is_blurry=quality_report.is_blurry if quality_report else None,
        blur_score=quality_report.blur_score if quality_report else None,
        contrast_score=quality_report.contrast_score if quality_report else None,
        glare_detected=quality_report.glare_detected if quality_report else None,
        quality_notes="; ".join(quality_report.notes) if quality_report and quality_report.notes else None,
        quality_acceptable=quality_report.quality_acceptable if quality_report else None,
        downloaded_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(product_image)
    db.flush()

    if run_ocr and quality_report is not None:
        _run_ocr_and_store(db, product_image, content)

    db.commit()
    db.refresh(product_image)
    return product_image


def _run_ocr_and_store(db: Session, product_image: ProductImage, original_bytes: bytes) -> None:
    try:
        with Image.open(io.BytesIO(original_bytes)) as img:
            preprocessed = preprocess_for_ocr(img)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                preprocessed.save(tmp, format="PNG")
                tmp_path = tmp.name
    except Exception as exc:  # noqa: BLE001
        logger.warning("OCR preprocessing failed for image %s: %s", product_image.id, exc)
        return

    try:
        engine = get_ocr_engine()
        blocks = engine.recognize(tmp_path)
    except Exception as exc:  # noqa: BLE001 - OCR failure must not crash the pipeline (Section 26/43)
        logger.warning("OCR failed for image %s: %s", product_image.id, exc)
        return

    now = dt.datetime.now(dt.timezone.utc)
    for block in blocks:
        db.add(
            OCRResult(
                product_image_id=product_image.id,
                engine=block.engine,
                engine_version=block.engine_version,
                model_name=block.model_name,
                text=block.text,
                confidence=block.confidence,
                bounding_box=block.bounding_box.as_dict(),
                created_at=now,
            )
        )


def run_ocr_for_image(db: Session, product_image: ProductImage) -> int:
    """Runs OCR for exactly one already-persisted image and returns the
    number of OCRResult rows created. Used for single-image, on-demand
    OCR (e.g. an officer re-running OCR on one screenshot from the UI).
    The bulk pipeline OCR stage (app/services/pipeline.py::_run_ocr_parallel)
    intentionally does NOT call this — it parallelizes the CPU-bound
    recognition step across a thread pool and only touches the (non
    thread-safe) SQLAlchemy Session from the main thread afterward. Safe to
    call more than once — existing OCRResult rows for the image are left
    untouched (Section 7/8: never overwrite evidence)."""
    existing = db.query(OCRResult).filter(OCRResult.product_image_id == product_image.id).count()
    if existing > 0:
        return 0
    try:
        content = read_bytes(product_image.storage_path)
    except (OSError, Exception) as exc:  # noqa: BLE001
        logger.warning("Could not read stored image %s for OCR: %s", product_image.storage_path, exc)
        return 0
    before = db.query(OCRResult).filter(OCRResult.product_image_id == product_image.id).count()
    _run_ocr_and_store(db, product_image, content)
    db.commit()
    after = db.query(OCRResult).filter(OCRResult.product_image_id == product_image.id).count()
    return after - before


def download_image(url: str) -> tuple[bytes, str | None] | None:
    """Downloads a product image referenced by the scraper. Returns
    (content_bytes, content_type) or None if the download failed/was
    rejected — download failures never crash the pipeline (Section 26)."""
    try:
        with httpx.stream(
            "GET",
            url,
            timeout=settings.scraper_request_timeout_seconds,
            headers={"User-Agent": settings.scraper_user_agent},
            follow_redirects=True,
        ) as response:
            if response.status_code >= 400:
                logger.info("Image download failed (%s) for %s", response.status_code, url)
                return None
            content_type = response.headers.get("content-type")
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    logger.warning("Image download exceeded size limit for %s", url)
                    return None
                chunks.append(chunk)
            return b"".join(chunks), content_type
    except (httpx.HTTPError, UnsafeUploadError) as exc:
        logger.info("Image download error for %s: %s", url, exc)
        return None
