from __future__ import annotations

import datetime as dt
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ComplianceStatus, EvidenceSourceType, InspectionStatus, PipelineStage, PipelineStageStatus
from app.models.mixins import TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.compliance import ComplianceCheck
    from app.models.declaration import Declaration
    from app.models.product import Product
    from app.models.report import Report
    from app.models.scraping import ProductImage, WebPage
    from app.models.user import User


class Inspection(Base, UUIDPKMixin, TimestampMixin):
    """One inspection = one officer-initiated review of one product listing
    at a point in time. Re-scanning the same URL creates a new Inspection
    linked to the same Product, so history is never silently overwritten
    (Section 31, Section 52 acceptance criterion #17)."""

    __tablename__ = "inspections"

    inspection_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    officer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"), nullable=True)

    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str | None] = mapped_column(String(64), nullable=True)

    status: Mapped[InspectionStatus] = mapped_column(
        String(32), default=InspectionStatus.CREATED, nullable=False, index=True
    )
    current_stage: Mapped[PipelineStage | None] = mapped_column(String(32), nullable=True)
    overall_status: Mapped[ComplianceStatus | None] = mapped_column(String(32), nullable=True, index=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    officer: Mapped["User"] = relationship(foreign_keys=[officer_id])
    product: Mapped["Product | None"] = relationship(back_populates="inspections")

    pipeline_events: Mapped[list["PipelineEvent"]] = relationship(
        back_populates="inspection", cascade="all, delete-orphan", order_by="PipelineEvent.created_at"
    )
    sources: Mapped[list["InspectionSource"]] = relationship(
        back_populates="inspection", cascade="all, delete-orphan"
    )
    web_pages: Mapped[list["WebPage"]] = relationship(
        back_populates="inspection", cascade="all, delete-orphan"
    )
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="inspection", cascade="all, delete-orphan"
    )
    declarations: Mapped[list["Declaration"]] = relationship(
        back_populates="inspection", cascade="all, delete-orphan"
    )
    compliance_checks: Mapped[list["ComplianceCheck"]] = relationship(
        back_populates="inspection", cascade="all, delete-orphan"
    )
    reports: Mapped[list["Report"]] = relationship(
        back_populates="inspection", cascade="all, delete-orphan"
    )


class InspectionSource(Base, UUIDPKMixin, TimestampMixin):
    """Records each distinct evidence-gathering event for an inspection
    (an automated scrape attempt, a screenshot upload batch, a manual
    reviewer note). This is the concrete table backing the EvidenceSource
    abstraction (Section 15) that the future physical-inspection module will
    also write into via a PHYSICAL_IMAGE / PHYSICAL_MEASUREMENT source_type."""

    __tablename__ = "inspection_sources"

    inspection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inspections.id"), nullable=False)
    source_type: Mapped[EvidenceSourceType] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    inspection: Mapped[Inspection] = relationship(back_populates="sources")


class PipelineEvent(Base, UUIDPKMixin):
    """Progress-tracking row so the frontend can show live pipeline status
    (Section 30/43) without needing a message broker for V1."""

    __tablename__ = "pipeline_events"

    inspection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inspections.id"), nullable=False)
    stage: Mapped[PipelineStage] = mapped_column(String(32), nullable=False)
    status: Mapped[PipelineStageStatus] = mapped_column(String(32), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    inspection: Mapped[Inspection] = relationship(back_populates="pipeline_events")
