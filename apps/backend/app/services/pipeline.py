"""The inspection pipeline orchestrator (Section 30):

FETCH -> PARSE -> IMAGE_DOWNLOAD -> IMAGE_QUALITY -> OCR ->
DECLARATION_EXTRACTION -> CLASSIFICATION -> RULE_SELECTION -> COMPLIANCE ->
CONSISTENCY -> REPORT

Runs synchronously inside a FastAPI BackgroundTasks callback for V1 (Section
30: "a lightweight worker/background task approach is acceptable... design
so Celery/RQ/etc. can be introduced later"). Every stage is wrapped so a
failure in one stage never crashes the whole run (Section 26: never fail the
inspection outright) and is recorded as a PipelineEvent the frontend can
poll for live progress (Section 43).
"""
from __future__ import annotations

import datetime as dt
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.compliance.engine import compute_overall_status, run_compliance_checks
from app.core.config import get_settings
from app.models.compliance import ComplianceCheck, Evidence, Violation
from app.models.declaration import Declaration
from app.models.enums import (
    DeclarationSourceType,
    EvidenceSourceType,
    InspectionStatus,
    PipelineStage,
    PipelineStageStatus,
    WebFetchStatus,
)
from app.models.inspection import Inspection, PipelineEvent
from app.models.scraping import OCRResult, ProductImage, WebExtraction, WebPage
from app.nlp.declaration_extractor import extract_declarations_from_ocr, extract_declarations_from_webpage
from app.repositories.product_repository import get_or_create_product, touch_last_checked
from app.services.classification_service import classify_product
from app.services.image_service import download_image, process_image_bytes
from app.services.scraping_service import scrape_product_page

logger = logging.getLogger(__name__)
settings = get_settings()


@contextmanager
def _stage(db: Session, inspection: Inspection, stage: PipelineStage, message: str | None = None):
    started = time.monotonic()
    inspection.current_stage = stage.value
    db.commit()
    _record(db, inspection, stage, PipelineStageStatus.RUNNING, message)
    try:
        yield
    except Exception as exc:  # noqa: BLE001 - a stage must never crash the whole pipeline
        logger.exception("Pipeline stage %s failed for inspection %s", stage.value, inspection.id)
        _record(
            db,
            inspection,
            stage,
            PipelineStageStatus.FAILED,
            f"{message or stage.value} — error: {exc}",
            duration_ms=int((time.monotonic() - started) * 1000),
        )
    else:
        _record(
            db,
            inspection,
            stage,
            PipelineStageStatus.SUCCEEDED,
            message,
            duration_ms=int((time.monotonic() - started) * 1000),
        )


def _record(
    db: Session,
    inspection: Inspection,
    stage: PipelineStage,
    status: PipelineStageStatus,
    message: str | None,
    duration_ms: int | None = None,
) -> None:
    db.add(
        PipelineEvent(
            inspection_id=inspection.id,
            stage=stage.value,
            status=status.value,
            message=message,
            duration_ms=duration_ms,
            created_at=dt.datetime.now(dt.timezone.utc),
        )
    )
    db.commit()


def run_inspection_pipeline_new_session(inspection_id) -> None:  # noqa: ANN001
    """Entry point for FastAPI BackgroundTasks: opens its own DB session
    rather than reusing the request-scoped one, since the request's session
    may already be closed by the time a background task runs."""
    db = SessionLocal()
    try:
        run_inspection_pipeline(db, inspection_id)
    except Exception:  # noqa: BLE001 - last-resort guard so a bug never leaves an inspection stuck IN_PROGRESS
        logger.exception("Unhandled error running pipeline for inspection %s", inspection_id)
        try:
            inspection = db.get(Inspection, inspection_id)
            if inspection is not None and inspection.status != InspectionStatus.COMPLETED.value:
                inspection.status = InspectionStatus.FAILED.value
                db.commit()
        except Exception:  # noqa: BLE001
            logger.exception("Could not mark inspection %s as FAILED", inspection_id)
    finally:
        db.close()


def _reset_derived_data_for_reanalysis(db: Session, inspection: Inspection) -> None:
    """Clears every row this pipeline itself re-derives on each run, so
    re-running analysis (POST .../analyze — e.g. after uploading another
    screenshot, or simply re-checking a listing) recomputes findings from
    the current full evidence set instead of silently appending a second
    copy of every declaration, compliance finding, and auto-fetched
    image/page alongside the first run's (P0 audit fix: "re-analysis
    duplication" — previously every one of those tables only ever grew,
    never got superseded, so a second analyze() call doubled the "Legal
    Metrology Findings" and "Extracted Declarations" sections, doubled
    stored images, and re-ran OCR on the resulting duplicate images).

    What is NOT cleared: officer-uploaded screenshots (ProductImage rows
    with source_type USER_INPUT) and manually-typed declarations
    (Declaration rows with source_type USER_INPUT) — those are evidence the
    officer supplied directly, never automatically re-derived, so a re-run
    must never lose them. OCRResult rows belonging to a preserved image are
    kept too (re-running OCR on an unchanged image can't change the
    result — `_run_ocr_parallel` already skips images that already have
    OCRResult rows); their declarations are still recomputed fresh below,
    since DECLARATION_EXTRACTION re-derives declarations from whatever
    OCRResult/WebExtraction rows exist at the time it runs.
    """
    check_ids = [
        row[0] for row in db.query(ComplianceCheck.id).filter(ComplianceCheck.inspection_id == inspection.id)
    ]
    if check_ids:
        db.query(Evidence).filter(Evidence.compliance_check_id.in_(check_ids)).delete(synchronize_session=False)
        db.query(Violation).filter(Violation.compliance_check_id.in_(check_ids)).delete(synchronize_session=False)
        db.query(ComplianceCheck).filter(ComplianceCheck.id.in_(check_ids)).delete(synchronize_session=False)

    db.query(Declaration).filter(
        Declaration.inspection_id == inspection.id,
        Declaration.source_type != DeclarationSourceType.USER_INPUT.value,
    ).delete(synchronize_session=False)

    web_page_ids = [row[0] for row in db.query(WebPage.id).filter(WebPage.inspection_id == inspection.id)]
    if web_page_ids:
        db.query(WebExtraction).filter(WebExtraction.web_page_id.in_(web_page_ids)).delete(synchronize_session=False)
        db.query(WebPage).filter(WebPage.id.in_(web_page_ids)).delete(synchronize_session=False)

    auto_image_ids = [
        row[0]
        for row in db.query(ProductImage.id).filter(
            ProductImage.inspection_id == inspection.id,
            ProductImage.source_type == EvidenceSourceType.ONLINE_LISTING.value,
        )
    ]
    if auto_image_ids:
        db.query(OCRResult).filter(OCRResult.product_image_id.in_(auto_image_ids)).delete(synchronize_session=False)
        db.query(ProductImage).filter(ProductImage.id.in_(auto_image_ids)).delete(synchronize_session=False)

    db.commit()
    # The bulk deletes above bypassed the ORM identity map (synchronize_session=False),
    # so anything already loaded on `inspection` (e.g. inspection.web_pages) would
    # otherwise still show the now-deleted rows for the rest of this session.
    db.expire_all()


def run_inspection_pipeline(db: Session, inspection_id) -> None:  # noqa: ANN001
    inspection = db.get(Inspection, inspection_id)
    if inspection is None:
        logger.error("run_inspection_pipeline: inspection %s not found", inspection_id)
        return

    inspection.status = InspectionStatus.IN_PROGRESS.value
    db.commit()

    _reset_derived_data_for_reanalysis(db, inspection)

    scraped_product = None

    with _stage(db, inspection, PipelineStage.FETCH, "Fetching product page…"):
        if inspection.source_url:
            web_page, scraped_product = scrape_product_page(db, inspection, inspection.source_url)
            inspection.platform = web_page.platform

            if scraped_product is not None:
                product = get_or_create_product(db, inspection.source_url, web_page.platform)
                product.title = scraped_product.title or product.title
                product.brand = scraped_product.brand or product.brand
                product.description = scraped_product.description or product.description
                product.listed_price = scraped_product.listed_price or product.listed_price
                product.currency = scraped_product.currency or product.currency or "INR"
                inspection.product_id = product.id
                touch_last_checked(db, product)
                db.commit()
            elif web_page.fetch_status != WebFetchStatus.SUCCESS.value:
                _record(
                    db, inspection, PipelineStage.FETCH, PipelineStageStatus.FAILED,
                    "Automatic page extraction unavailable. Upload screenshots to continue this inspection.",
                )
        else:
            # Manual scan: no listing URL was ever provided, so there is
            # nothing to fetch — this is not a failure, just a different
            # entry point. Evidence comes entirely from uploaded/captured
            # screenshots (Section 5/25's "upload instead" fallback, now
            # also reachable directly rather than only after a failed
            # automatic fetch).
            _record(
                db, inspection, PipelineStage.FETCH, PipelineStageStatus.SUCCEEDED,
                "Manual inspection — no listing URL provided; skipped automatic retrieval, relying on uploaded screenshots.",
            )

    with _stage(db, inspection, PipelineStage.PARSE, "Parsing structured page data…"):
        pass  # Parsing happens as part of scrape_product_page; this stage is a checkpoint for UX/progress.

    with _stage(db, inspection, PipelineStage.IMAGE_DOWNLOAD, "Downloading product images…") as _:
        if scraped_product and scraped_product.images:
            _download_images_parallel(db, inspection, scraped_product.images[: settings.scraper_max_images_per_product])

    with _stage(db, inspection, PipelineStage.IMAGE_QUALITY, "Assessing image quality…"):
        images = db.query(ProductImage).filter(ProductImage.inspection_id == inspection.id).all()
        acceptable = sum(1 for i in images if i.quality_acceptable)
        _record(
            db, inspection, PipelineStage.IMAGE_QUALITY, PipelineStageStatus.SUCCEEDED,
            f"{acceptable}/{len(images)} image(s) met quality thresholds." if images else "No images available yet.",
        )

    with _stage(db, inspection, PipelineStage.OCR, "Running OCR on product images…"):
        images = db.query(ProductImage).filter(ProductImage.inspection_id == inspection.id).all()
        _run_ocr_parallel(db, images)

    with _stage(db, inspection, PipelineStage.DECLARATION_EXTRACTION, "Extracting declarations…"):
        web_pages = db.query(WebPage).filter(
            WebPage.inspection_id == inspection.id, WebPage.fetch_status == WebFetchStatus.SUCCESS.value
        ).all()
        for wp in web_pages:
            extract_declarations_from_webpage(db, inspection.id, wp, list(wp.extractions))

        images = db.query(ProductImage).filter(ProductImage.inspection_id == inspection.id).all()
        for img in images:
            ocr_results = db.query(OCRResult).filter(OCRResult.product_image_id == img.id).all()
            if ocr_results:
                extract_declarations_from_ocr(db, inspection.id, img, ocr_results)

    category_value = None
    with _stage(db, inspection, PipelineStage.CLASSIFICATION, "Classifying product category…"):
        if inspection.product_id and inspection.product is not None:
            product = inspection.product
            images = db.query(ProductImage).filter(ProductImage.inspection_id == inspection.id).all()
            ocr_texts = [
                r.text for img in images for r in db.query(OCRResult).filter(OCRResult.product_image_id == img.id)
            ]
            category = classify_product(db, product, ocr_texts)
            category_value = category
            _record(
                db, inspection, PipelineStage.CLASSIFICATION, PipelineStageStatus.SUCCEEDED,
                f"Classified as {category.value} (confidence {product.category_confidence or 0:.0%}).",
            )
        else:
            from app.models.enums import ProductCategoryCode

            category_value = ProductCategoryCode.UNKNOWN
            _record(
                db, inspection, PipelineStage.CLASSIFICATION, PipelineStageStatus.SUCCEEDED,
                "No product record available yet; defaulting to UNKNOWN pending officer classification.",
            )

    checks = []
    with _stage(db, inspection, PipelineStage.RULE_SELECTION, "Selecting applicable rules…"):
        pass  # Rule selection is folded into run_compliance_checks (category/exemption gating).

    with _stage(db, inspection, PipelineStage.COMPLIANCE, "Applying compliance rules…"):
        checks = run_compliance_checks(db, inspection, category_value)

    with _stage(db, inspection, PipelineStage.CONSISTENCY, "Checking cross-source consistency…"):
        pass  # Consistency rules are evaluated inside run_compliance_checks alongside the rest.

    with _stage(db, inspection, PipelineStage.REPORT, "Finalizing results…"):
        inspection.overall_status = compute_overall_status(checks).value
        inspection.status = InspectionStatus.COMPLETED.value
        inspection.current_stage = PipelineStage.DONE.value
        inspection.completed_at = dt.datetime.now(dt.timezone.utc)
        db.commit()


def _download_images_parallel(db: Session, inspection: Inspection, scraped_images) -> None:  # noqa: ANN001
    results: list[tuple] = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(download_image, img.url): img for img in scraped_images}
        for future in as_completed(futures):
            scraped_img = futures[future]
            try:
                outcome = future.result()
            except Exception as exc:  # noqa: BLE001
                logger.info("Image download raised for %s: %s", scraped_img.url, exc)
                continue
            if outcome is not None:
                results.append((scraped_img, outcome))

    for scraped_img, (content, content_type) in results:
        try:
            process_image_bytes(
                db,
                inspection_id=inspection.id,
                content=content,
                source_type=EvidenceSourceType.ONLINE_LISTING,
                original_url=scraped_img.url,
                original_filename=None,
                content_type=content_type,
                run_ocr=False,
            )
        except Exception as exc:  # noqa: BLE001
            logger.info("Failed to persist downloaded image %s: %s", scraped_img.url, exc)


def _run_ocr_parallel(db: Session, images: list[ProductImage]) -> None:
    """Section 42: OCR runs in parallel across images. Each image's OCR call
    still commits through the same Session sequentially (SQLAlchemy Sessions
    are not thread-safe) — the parallelism is in the CPU/subprocess-bound
    OCR recognition itself, run in worker threads, with results applied to
    the DB session on the main thread afterward."""
    from app.ocr.registry import get_ocr_engine
    from app.storage.files import read_bytes
    from app.vision.preprocessing import preprocess_for_ocr
    import io
    import tempfile

    from PIL import Image

    pending = [img for img in images if not db.query(OCRResult).filter(OCRResult.product_image_id == img.id).count()]
    if not pending:
        return

    def _recognize(image: ProductImage):
        content = read_bytes(image.storage_path)
        with Image.open(io.BytesIO(content)) as im:
            preprocessed = preprocess_for_ocr(im)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                preprocessed.save(tmp, format="PNG")
                tmp_path = tmp.name
        engine = get_ocr_engine()
        return image, engine.recognize(tmp_path)

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(_recognize, img): img for img in pending}
        for future in as_completed(futures):
            img = futures[future]
            try:
                _, blocks = future.result()
            except Exception as exc:  # noqa: BLE001
                logger.warning("OCR failed for image %s: %s", img.id, exc)
                continue
            now = dt.datetime.now(dt.timezone.utc)
            for block in blocks:
                db.add(
                    OCRResult(
                        product_image_id=img.id,
                        engine=block.engine,
                        engine_version=block.engine_version,
                        model_name=block.model_name,
                        text=block.text,
                        confidence=block.confidence,
                        bounding_box=block.bounding_box.as_dict(),
                        created_at=now,
                    )
                )
            db.commit()
