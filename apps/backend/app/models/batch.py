"""Bulk/batch scan + triage queue (Section 30/48 follow-on): a batch is
nothing more than a label tying a group of ordinary Inspection rows
together, so every existing pipeline/compliance/review/report code path
needs zero changes — see docs/architecture.md for why this stays additive.
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import BatchStatus
from app.models.mixins import TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.inspection import Inspection
    from app.models.user import User


class InspectionBatch(Base, UUIDPKMixin, TimestampMixin):
    """One officer-initiated bulk scan: a set of listing URLs submitted
    together, each becoming its own Inspection (tagged via
    Inspection.batch_id) so the full pipeline/compliance history for every
    item is identical to a standalone inspection. Deliberately has no
    stored `processed_count` — that would be a second source of truth that
    can drift if the in-process worker restarts mid-batch (same limitation
    already documented for single inspections); progress is always computed
    live from the batch's own Inspection rows at read time."""

    __tablename__ = "inspection_batches"

    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[BatchStatus] = mapped_column(String(32), default=BatchStatus.CREATED, nullable=False, index=True)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False)
    rejected_urls: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    """Submitted URLs that never became an Inspection (blank, duplicate, or
    over batch_max_urls) — recorded so the officer can see what was skipped
    and why on every later page load, not just the moment of submission."""
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by: Mapped["User"] = relationship()
    inspections: Mapped[list["Inspection"]] = relationship(back_populates="batch")
