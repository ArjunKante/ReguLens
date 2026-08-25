from __future__ import annotations

import datetime as dt
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ReportFormat
from app.models.mixins import UUIDPKMixin

if TYPE_CHECKING:
    from app.models.inspection import Inspection
    from app.models.user import User


class Report(Base, UUIDPKMixin):
    __tablename__ = "reports"

    inspection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inspections.id"), nullable=False)
    generated_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    format: Mapped[ReportFormat] = mapped_column(String(8), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    rule_version_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    """Rule IDs/versions evaluated, frozen at generation time — see Section 12/17."""

    generated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    inspection: Mapped["Inspection"] = relationship(back_populates="reports")
    generated_by: Mapped["User"] = relationship()
