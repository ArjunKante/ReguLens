from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.models.batch import InspectionBatch
from app.models.compliance import ComplianceCheck
from app.models.enums import BatchStatus
from app.models.inspection import Inspection
from app.models.user import User
from app.repositories.inspection_repository import create_inspection


def create_batch(
    db: Session, *, officer: User, name: str | None, urls: list[str]
) -> tuple[InspectionBatch, list[str]]:
    """Dedupes/validates/caps the submitted URLs, creates the InspectionBatch
    row, then creates one ordinary Inspection per accepted URL tagged with
    `batch_id`. Rejected input (blank, duplicate, or over the
    `batch_max_urls` cap) is never silently dropped — it's returned so the
    caller can show the officer exactly what wasn't scanned and why (same
    "always show why" discipline used throughout this codebase, e.g.
    NOT_APPLICABLE reasons in the compliance engine)."""
    settings = get_settings()
    accepted: list[str] = []
    rejected: list[str] = []
    seen: set[str] = set()

    for raw in urls:
        url = (raw or "").strip()
        if len(url) < 8:
            rejected.append(f"{raw!r} — too short to be a valid listing URL.")
            continue
        if url in seen:
            rejected.append(f"{url} — duplicate of another URL already accepted in this batch.")
            continue
        if len(accepted) >= settings.batch_max_urls:
            rejected.append(f"{url} — batch exceeds the {settings.batch_max_urls}-URL limit for a single run.")
            continue
        seen.add(url)
        accepted.append(url)

    batch = InspectionBatch(
        name=name,
        created_by_id=officer.id,
        status=BatchStatus.CREATED.value,
        total_count=len(accepted),
        rejected_urls=rejected,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    for url in accepted:
        create_inspection(db, officer=officer, source_url=url, notes=None, batch_id=batch.id)

    return batch, rejected


def get_batch(db: Session, batch_id: uuid.UUID) -> InspectionBatch | None:
    return db.execute(
        select(InspectionBatch)
        .where(InspectionBatch.id == batch_id)
        .options(
            selectinload(InspectionBatch.created_by),
            selectinload(InspectionBatch.inspections).selectinload(Inspection.officer),
            selectinload(InspectionBatch.inspections).selectinload(Inspection.product),
            selectinload(InspectionBatch.inspections)
            .selectinload(Inspection.compliance_checks)
            .selectinload(ComplianceCheck.violation),
        )
    ).unique().scalar_one_or_none()


def list_batches(
    db: Session, *, officer_id: uuid.UUID | None = None, limit: int = 50, offset: int = 0
) -> list[InspectionBatch]:
    stmt = select(InspectionBatch).options(
        selectinload(InspectionBatch.created_by), selectinload(InspectionBatch.inspections)
    )
    if officer_id is not None:
        stmt = stmt.where(InspectionBatch.created_by_id == officer_id)
    stmt = stmt.order_by(InspectionBatch.created_at.desc()).limit(limit).offset(offset)
    return list(db.execute(stmt).unique().scalars())
