from __future__ import annotations

import datetime as dt
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import UUIDPKMixin

if TYPE_CHECKING:
    from app.models.user import User


class AuditLog(Base, UUIDPKMixin):
    """Append-only audit trail for security-relevant and inspection-relevant
    actions (Section 28/39). Never logs credentials or raw secrets."""

    __tablename__ = "audit_logs"

    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extra: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    actor: Mapped["User | None"] = relationship()
