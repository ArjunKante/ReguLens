from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.audit.service import log_action
from app.auth.dependencies import require_any_authenticated, require_inspector
from app.core.database import get_db
from app.models.batch import InspectionBatch
from app.models.inspection import Inspection
from app.models.user import User
from app.repositories.batch_repository import create_batch, get_batch, list_batches
from app.schemas.batch import BatchCreate, BatchDetail, BatchItemOut, BatchSummary
from app.services.batch_pipeline import run_batch_new_session
from app.services.triage import triage_metrics, triage_sort_key

router = APIRouter(prefix="/batches", tags=["batches"])

# Mirrors InspectionStatus's terminal states — an item counts as "processed"
# for progress-bar purposes once the pipeline has finished with it, whether
# it succeeded or failed (Section 26: a stage failure never crashes the
# whole run, and here that extends to "one bad URL never stalls the batch's
# reported progress either).
_TERMINAL_INSPECTION_STATUSES = {"COMPLETED", "FAILED"}


def _to_item_out(inspection: Inspection) -> BatchItemOut:
    m = triage_metrics(inspection)
    return BatchItemOut(
        id=inspection.id,
        inspection_number=inspection.inspection_number,
        source_url=inspection.source_url,
        platform=inspection.platform,
        status=inspection.status,
        overall_status=inspection.overall_status,
        officer_id=inspection.officer_id,
        officer_name=inspection.officer.full_name if inspection.officer else None,
        product_title=inspection.product.title if inspection.product else None,
        created_at=inspection.created_at,
        completed_at=inspection.completed_at,
        is_demo=inspection.is_demo,
        violation_count=m.violation_count,
        critical_violation_count=m.critical_violation_count,
        max_violation_confidence=m.max_violation_confidence,
    )


def _outcome_counts(inspections: list[Inspection]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for insp in inspections:
        if insp.overall_status:
            counts[insp.overall_status] = counts.get(insp.overall_status, 0) + 1
    return counts


def _to_summary(batch: InspectionBatch) -> BatchSummary:
    processed = sum(1 for i in batch.inspections if i.status in _TERMINAL_INSPECTION_STATUSES)
    return BatchSummary(
        id=batch.id,
        name=batch.name,
        status=batch.status,
        total_count=batch.total_count,
        processed_count=processed,
        outcome_counts=_outcome_counts(batch.inspections),
        created_by_id=batch.created_by_id,
        created_by_name=batch.created_by.full_name if batch.created_by else None,
        created_at=batch.created_at,
        completed_at=batch.completed_at,
    )


@router.post("", response_model=BatchSummary, status_code=status.HTTP_201_CREATED)
def create_new_batch(
    payload: BatchCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    officer: User = Depends(require_inspector),
) -> BatchSummary:
    batch, rejected = create_batch(db, officer=officer, name=payload.name, urls=payload.urls)
    if batch.total_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No usable URLs in this batch. Rejected: {rejected}",
        )
    background_tasks.add_task(run_batch_new_session, batch.id)
    log_action(
        db, actor_id=officer.id, action="BATCH_SCAN_STARTED", entity_type="inspection_batch",
        entity_id=str(batch.id), extra={"total_count": batch.total_count, "rejected_count": len(rejected)},
    )
    db.refresh(batch)
    return _to_summary(batch)


@router.get("", response_model=list[BatchSummary])
def get_batches(
    mine_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(require_any_authenticated),
) -> list[BatchSummary]:
    officer_id = user.id if mine_only else None
    batches = list_batches(db, officer_id=officer_id, limit=limit, offset=offset)
    return [_to_summary(b) for b in batches]


@router.get("/{batch_id}", response_model=BatchDetail)
def get_batch_detail(
    batch_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_any_authenticated)
) -> BatchDetail:
    batch = get_batch(db, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found.")
    summary = _to_summary(batch)
    items = sorted(batch.inspections, key=triage_sort_key)
    return BatchDetail(
        **summary.model_dump(),
        items=[_to_item_out(i) for i in items],
        rejected_urls=list(batch.rejected_urls or []),
    )
