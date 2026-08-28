"""Reconciles work orphaned by a process restart, run once at container
start (see the Dockerfile CMD sequence, mirroring `app/rules/loader.py`'s
own run-once-before-serving pattern).

BackgroundTasks -- both a single inspection's pipeline and a batch's
ThreadPoolExecutor fan-out (`services/pipeline.py`, `services/batch_pipeline.py`)
-- are in-process threads: they do not survive a restart of the process
running them, whether that's a redeploy, a crash, or a manual restart.
Nothing else ever moves an Inspection/InspectionBatch out of IN_PROGRESS
once its owning process is gone, so without this, an interrupted run sits
at IN_PROGRESS forever with no error surfaced anywhere and no way to tell
from the UI that it will never finish.

Found via a real batch-scan test against the deployed app (2026-08-28): an
unrelated `git push` triggered a Render auto-deploy mid-run, silently
orphaning a batch and all three of its inspections.

Only IN_PROGRESS is reconciled here, never CREATED. CREATED is a
legitimate, often long-lived resting state for a standalone Inspection --
an officer can create one now and scan it later via a separate
`.../scan-url` call -- so an inspection sitting at CREATED is not
evidence of anything having been interrupted. IN_PROGRESS is different:
every code path that sets it (see `services/pipeline.py`'s
`run_inspection_pipeline`, `services/batch_pipeline.py`'s
`run_batch_new_session`, and the `/scan-url` and `/demo` routes) sets it
in the same commit that queues the background task meant to move it
forward. Seeing it at process startup -- before this process has queued
any work of its own -- unambiguously means that task no longer exists.
"""
from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.batch import InspectionBatch
from app.models.enums import BatchStatus, InspectionStatus, PipelineStage, PipelineStageStatus
from app.models.inspection import Inspection, PipelineEvent

logger = logging.getLogger(__name__)

_ORPHAN_MESSAGE = (
    "Orphaned by a server restart during analysis (e.g. a redeploy) — the "
    "process that was running this inspection no longer exists. Re-run "
    "analysis to retry."
)


def reconcile_orphaned_work(db: Session) -> dict[str, int]:
    """Marks every IN_PROGRESS Inspection FAILED and every IN_PROGRESS
    InspectionBatch COMPLETED, with an explanatory PipelineEvent on each
    affected inspection. Safe to call on an already-clean database (finds
    nothing, commits nothing) — see `run()` below for the container-start
    entry point."""
    now = dt.datetime.now(dt.timezone.utc)

    orphaned_inspections = (
        db.query(Inspection).filter(Inspection.status == InspectionStatus.IN_PROGRESS.value).all()
    )
    for inspection in orphaned_inspections:
        inspection.status = InspectionStatus.FAILED.value
        db.add(
            PipelineEvent(
                inspection_id=inspection.id,
                stage=PipelineStage.DONE.value,
                status=PipelineStageStatus.FAILED.value,
                message=_ORPHAN_MESSAGE,
                created_at=now,
            )
        )

    orphaned_batches = (
        db.query(InspectionBatch).filter(InspectionBatch.status == BatchStatus.IN_PROGRESS.value).all()
    )
    for batch in orphaned_batches:
        # Not FAILED: BatchStatus has no such state by design (see
        # models/enums.py — individual items already self-report FAILED via
        # InspectionStatus, which the loop above just did for this batch's
        # own orphaned items). COMPLETED is accurate regardless: the batch
        # is done being worked on, even though it ended in some FAILED
        # items rather than real results.
        batch.status = BatchStatus.COMPLETED.value
        batch.completed_at = now

    if orphaned_inspections or orphaned_batches:
        db.commit()

    return {"inspections": len(orphaned_inspections), "batches": len(orphaned_batches)}


def run() -> None:
    db = SessionLocal()
    try:
        summary = reconcile_orphaned_work(db)
        if summary["inspections"] or summary["batches"]:
            print(
                f"Startup reconciliation: marked {summary['inspections']} orphaned inspection(s) "
                f"FAILED and {summary['batches']} orphaned batch(es) COMPLETED "
                "(owning process no longer exists)."
            )
        else:
            print("Startup reconciliation: no orphaned work found.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
