"""Bulk/batch scan orchestration: fans a batch's URLs out to the existing,
already-hardened single-inspection pipeline with bounded concurrency.

Deliberately contains no pipeline/compliance logic of its own — every item
runs through the exact same `run_inspection_pipeline_new_session` a
standalone inspection would (Section 30's "lightweight worker approach is
acceptable for MVP", same in-process BackgroundTasks model), so a batch
scan is guaranteed to produce identical results to running each URL one at
a time.
"""
from __future__ import annotations

import datetime as dt
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.batch import InspectionBatch
from app.models.enums import BatchStatus
from app.models.inspection import Inspection
from app.services.pipeline import run_inspection_pipeline_new_session

logger = logging.getLogger(__name__)
settings = get_settings()


def run_batch_new_session(batch_id) -> None:  # noqa: ANN001
    """Entry point for FastAPI BackgroundTasks. Opens its own DB session for
    the batch-status bookkeeping around the fan-out; each individual
    inspection still opens/closes its own session inside
    run_inspection_pipeline_new_session (SQLAlchemy Sessions are not
    thread-safe, same reasoning as _run_ocr_parallel/_download_images_parallel
    in services/pipeline.py)."""
    db = SessionLocal()
    try:
        batch = db.get(InspectionBatch, batch_id)
        if batch is None:
            logger.error("run_batch_new_session: batch %s not found", batch_id)
            return
        batch.status = BatchStatus.IN_PROGRESS.value
        db.commit()
        inspection_ids = [
            row[0] for row in db.query(Inspection.id).filter(Inspection.batch_id == batch_id)
        ]
    finally:
        db.close()

    if inspection_ids:
        with ThreadPoolExecutor(max_workers=settings.batch_max_concurrency) as executor:
            futures = {
                executor.submit(run_inspection_pipeline_new_session, iid): iid for iid in inspection_ids
            }
            for future in as_completed(futures):
                iid = futures[future]
                try:
                    future.result()
                except Exception:  # noqa: BLE001 - one item's unexpected failure must never abort the batch
                    logger.exception("Batch %s: inspection %s raised unexpectedly", batch_id, iid)

    db = SessionLocal()
    try:
        batch = db.get(InspectionBatch, batch_id)
        if batch is not None:
            batch.status = BatchStatus.COMPLETED.value
            batch.completed_at = dt.datetime.now(dt.timezone.utc)
            db.commit()
    finally:
        db.close()
