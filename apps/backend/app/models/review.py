from __future__ import annotations

import datetime as dt
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ComplianceStatus, ReviewDecisionType
from app.models.mixins import UUIDPKMixin

if TYPE_CHECKING:
    from app.models.compliance import ComplianceCheck
    from app.models.user import User


class ReviewDecision(Base, UUIDPKMixin):
    """Human-in-the-loop review of one ComplianceCheck (Section 16). The
    automated result (`automated_status`, copied at review time from the
    ComplianceCheck) is never overwritten — only appended to. The
    `final_status` is what reports and the dashboard should use once present;
    until then the automated status stands, labeled as preliminary."""

    __tablename__ = "review_decisions"

    compliance_check_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("compliance_checks.id"), nullable=False)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    decision: Mapped[ReviewDecisionType] = mapped_column(String(32), nullable=False)
    automated_status: Mapped[ComplianceStatus] = mapped_column(String(32), nullable=False)
    final_status: Mapped[ComplianceStatus] = mapped_column(String(32), nullable=False)

    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    additional_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    compliance_check: Mapped["ComplianceCheck"] = relationship(back_populates="review_decisions")
    reviewer: Mapped["User"] = relationship()
