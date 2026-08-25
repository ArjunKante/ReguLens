from __future__ import annotations

import datetime as dt
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ComplianceStatus, RuleSeverity
from app.models.mixins import UUIDPKMixin

if TYPE_CHECKING:
    from app.models.inspection import Inspection
    from app.models.review import ReviewDecision
    from app.models.rules import RuleVersion


class ComplianceCheck(Base, UUIDPKMixin):
    """Result of evaluating one RuleVersion against one Inspection's
    declarations/evidence. This is the atomic unit the review workflow
    (ReviewDecision) attaches to (Section 13/16)."""

    __tablename__ = "compliance_checks"

    inspection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inspections.id"), nullable=False)
    rule_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rule_versions.id"), nullable=False)

    status: Mapped[ComplianceStatus] = mapped_column(String(32), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    checked_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    engine_version: Mapped[str] = mapped_column(String(32), nullable=False)
    executed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    inspection: Mapped["Inspection"] = relationship(back_populates="compliance_checks")
    rule_version: Mapped["RuleVersion"] = relationship()

    violation: Mapped["Violation | None"] = relationship(
        back_populates="compliance_check", cascade="all, delete-orphan", uselist=False
    )
    evidence_items: Mapped[list["Evidence"]] = relationship(
        back_populates="compliance_check", cascade="all, delete-orphan"
    )
    review_decisions: Mapped[list["ReviewDecision"]] = relationship(
        back_populates="compliance_check", cascade="all, delete-orphan", order_by="ReviewDecision.created_at"
    )


class Violation(Base, UUIDPKMixin):
    """Created for compliance checks whose status is POTENTIAL_NON_COMPLIANCE
    (including cross-source POTENTIAL_INCONSISTENCY findings). This never
    represents a final legal determination (Section 46/48) — wording is
    always framed as requiring officer verification."""

    __tablename__ = "violations"

    compliance_check_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("compliance_checks.id"), unique=True, nullable=False
    )
    severity: Mapped[RuleSeverity] = mapped_column(String(16), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False)

    compliance_check: Mapped[ComplianceCheck] = relationship(back_populates="violation")


class Evidence(Base, UUIDPKMixin):
    """A traceable pointer answering 'why did the system flag this?'
    (Section 32/33). Always linked to a compliance_check; may additionally
    reference a declaration for direct field-level provenance."""

    __tablename__ = "evidence"

    compliance_check_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("compliance_checks.id"), nullable=False)
    declaration_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("declarations.id"), nullable=True)

    evidence_type: Mapped[str] = mapped_column(String(32), nullable=False)
    """WEBPAGE_TEXT | IMAGE_OCR | SCREENSHOT | MANUAL"""

    description: Mapped[str] = mapped_column(Text, nullable=False)
    reference: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    """Free-form pointer, e.g. {"url": "..."} or {"image_id": "...", "bounding_box": {...}}"""

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    compliance_check: Mapped[ComplianceCheck] = relationship(back_populates="evidence_items")
