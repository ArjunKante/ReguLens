from __future__ import annotations

import datetime as dt
import random
import string
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.compliance import ComplianceCheck
from app.models.inspection import Inspection
from app.models.rules import RuleVersion
from app.models.user import User


def generate_inspection_number() -> str:
    today = dt.date.today().strftime("%Y%m%d")
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"LMSCAN-{today}-{suffix}"


def create_inspection(db: Session, *, officer: User, source_url: str, notes: str | None) -> Inspection:
    inspection = Inspection(
        inspection_number=generate_inspection_number(),
        officer_id=officer.id,
        source_url=source_url,
        notes=notes,
    )
    db.add(inspection)
    db.commit()
    db.refresh(inspection)
    return inspection


def get_inspection(db: Session, inspection_id: uuid.UUID) -> Inspection | None:
    return db.execute(
        select(Inspection)
        .where(Inspection.id == inspection_id)
        .options(
            selectinload(Inspection.declarations),
            selectinload(Inspection.images),
            selectinload(Inspection.web_pages),
            selectinload(Inspection.pipeline_events),
            selectinload(Inspection.compliance_checks).selectinload(ComplianceCheck.violation),
            selectinload(Inspection.compliance_checks).selectinload(ComplianceCheck.evidence_items),
            selectinload(Inspection.compliance_checks).selectinload(ComplianceCheck.review_decisions),
            selectinload(Inspection.compliance_checks)
            .selectinload(ComplianceCheck.rule_version)
            .selectinload(RuleVersion.rule),
            selectinload(Inspection.product),
            selectinload(Inspection.officer),
        )
    ).unique().scalar_one_or_none()


def list_inspections(
    db: Session,
    *,
    officer_id: uuid.UUID | None = None,
    status: str | None = None,
    overall_status: str | None = None,
    platform: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Inspection]:
    stmt = select(Inspection).options(selectinload(Inspection.officer), selectinload(Inspection.product))
    if officer_id is not None:
        stmt = stmt.where(Inspection.officer_id == officer_id)
    if status is not None:
        stmt = stmt.where(Inspection.status == status)
    if overall_status is not None:
        stmt = stmt.where(Inspection.overall_status == overall_status)
    if platform is not None:
        stmt = stmt.where(Inspection.platform == platform)
    stmt = stmt.order_by(Inspection.created_at.desc()).limit(limit).offset(offset)
    return list(db.execute(stmt).unique().scalars())
