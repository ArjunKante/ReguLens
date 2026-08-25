from __future__ import annotations

import datetime as dt
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import DeclarationSourceType
from app.models.mixins import UUIDPKMixin

if TYPE_CHECKING:
    from app.models.inspection import Inspection


class Declaration(Base, UUIDPKMixin):
    """A single consolidated declared field for an inspection, e.g.
    {field: 'mrp', value: '₹120', source_type: 'IMAGE_OCR', confidence: 0.91}
    as specified in Section 6 of the product brief. Multiple Declaration rows
    may exist for the same field_name when multiple sources disagree — the
    compliance/consistency engine consumes all of them, it never collapses
    disagreement into a single silently-chosen value."""

    __tablename__ = "declarations"

    inspection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inspections.id"), nullable=False)

    field_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_type: Mapped[DeclarationSourceType] = mapped_column(String(32), nullable=False)
    # Polymorphic evidence pointer: exactly one of these is populated depending on source_type.
    source_web_page_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("web_pages.id"), nullable=True)
    source_web_extraction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("web_extractions.id"), nullable=True
    )
    source_ocr_result_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ocr_results.id"), nullable=True)
    source_product_image_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_images.id"), nullable=True
    )
    source_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    extraction_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)

    extracted_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    inspection: Mapped["Inspection"] = relationship(back_populates="declarations")
