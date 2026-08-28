from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field

from app.models.enums import BatchStatus
from app.schemas.inspection import InspectionSummary


class BatchCreate(BaseModel):
    name: str | None = None
    urls: list[str] = Field(min_length=1, description="Product listing URLs, one per entry.")


class BatchItemOut(InspectionSummary):
    """One inspection within a batch, augmented with the triage metrics
    (app/services/triage.py) used to sort the queue worst-first."""

    violation_count: int
    critical_violation_count: int
    max_violation_confidence: float


class BatchSummary(BaseModel):
    id: uuid.UUID
    name: str | None
    status: BatchStatus
    total_count: int
    processed_count: int
    """Computed live from item statuses (COMPLETED/FAILED), not stored —
    see app/models/batch.py for why."""
    outcome_counts: dict[str, int]
    """Count of completed items per overall_status, for an at-a-glance chip row."""
    created_by_id: uuid.UUID
    created_by_name: str | None = None
    created_at: dt.datetime
    completed_at: dt.datetime | None


class BatchDetail(BatchSummary):
    items: list[BatchItemOut]
    """Pre-sorted worst-first via app/services/triage.py::triage_sort_key."""
    rejected_urls: list[str]
    """Submitted URLs that were never turned into an Inspection (blank,
    duplicate, or over the batch_max_urls cap) — never silently dropped."""
