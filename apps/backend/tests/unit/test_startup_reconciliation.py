"""Startup reconciliation tests: an Inspection/InspectionBatch left at
IN_PROGRESS by a process that no longer exists (a redeploy mid-run, a
crash) must not sit there forever with no error surfaced anywhere. Found
via a real batch-scan test against the deployed app — see
app/services/startup_reconciliation.py for the full story."""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.orm import Session

from app.models.batch import InspectionBatch
from app.models.enums import BatchStatus, InspectionStatus, PipelineStage, PipelineStageStatus
from app.models.inspection import Inspection, PipelineEvent
from app.models.user import User
from app.services.startup_reconciliation import reconcile_orphaned_work


def _inspection(db: Session, officer: User, status: InspectionStatus) -> Inspection:
    inspection = Inspection(
        inspection_number=f"LMSCAN-{uuid.uuid4().hex[:8].upper()}",
        officer_id=officer.id,
        source_url="https://www.amazon.in/dp/B0BSX9N69D",
        platform="amazon",
        status=status.value,
    )
    db.add(inspection)
    db.commit()
    db.refresh(inspection)
    return inspection


def test_reconciles_an_orphaned_in_progress_inspection(db: Session, inspector_user: User):
    inspection = _inspection(db, inspector_user, InspectionStatus.IN_PROGRESS)

    summary = reconcile_orphaned_work(db)

    assert summary == {"inspections": 1, "batches": 0}
    db.refresh(inspection)
    assert inspection.status == InspectionStatus.FAILED.value

    events = db.query(PipelineEvent).filter(PipelineEvent.inspection_id == inspection.id).all()
    assert len(events) == 1
    assert events[0].stage == PipelineStage.DONE.value
    assert events[0].status == PipelineStageStatus.FAILED.value
    assert "restart" in events[0].message.lower()


def test_leaves_created_inspections_untouched(db: Session, inspector_user: User):
    """CREATED is a legitimate resting state (create now, scan later via
    .../scan-url) — not evidence of an interrupted run."""
    inspection = _inspection(db, inspector_user, InspectionStatus.CREATED)

    summary = reconcile_orphaned_work(db)

    assert summary == {"inspections": 0, "batches": 0}
    db.refresh(inspection)
    assert inspection.status == InspectionStatus.CREATED.value
    assert db.query(PipelineEvent).filter(PipelineEvent.inspection_id == inspection.id).count() == 0


def test_leaves_completed_and_failed_inspections_untouched(db: Session, inspector_user: User):
    completed = _inspection(db, inspector_user, InspectionStatus.COMPLETED)
    failed = _inspection(db, inspector_user, InspectionStatus.FAILED)

    summary = reconcile_orphaned_work(db)

    assert summary == {"inspections": 0, "batches": 0}
    db.refresh(completed)
    db.refresh(failed)
    assert completed.status == InspectionStatus.COMPLETED.value
    assert failed.status == InspectionStatus.FAILED.value


def test_reconciles_an_orphaned_in_progress_batch(db: Session, inspector_user: User):
    batch = InspectionBatch(
        name="Orphan test batch",
        created_by_id=inspector_user.id,
        status=BatchStatus.IN_PROGRESS.value,
        total_count=3,
        rejected_urls=[],
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    assert batch.completed_at is None

    summary = reconcile_orphaned_work(db)

    assert summary == {"inspections": 0, "batches": 1}
    db.refresh(batch)
    assert batch.status == BatchStatus.COMPLETED.value
    assert batch.completed_at is not None


def test_leaves_created_batches_untouched(db: Session, inspector_user: User):
    batch = InspectionBatch(
        name="Fresh batch",
        created_by_id=inspector_user.id,
        status=BatchStatus.CREATED.value,
        total_count=2,
        rejected_urls=[],
    )
    db.add(batch)
    db.commit()

    summary = reconcile_orphaned_work(db)

    assert summary == {"inspections": 0, "batches": 0}
    db.refresh(batch)
    assert batch.status == BatchStatus.CREATED.value


def test_is_idempotent(db: Session, inspector_user: User):
    _inspection(db, inspector_user, InspectionStatus.IN_PROGRESS)

    first = reconcile_orphaned_work(db)
    second = reconcile_orphaned_work(db)

    assert first == {"inspections": 1, "batches": 0}
    assert second == {"inspections": 0, "batches": 0}
