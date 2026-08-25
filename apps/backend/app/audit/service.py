"""Central helper for writing audit_log rows (Section 28/39). Callers pass
only what happened and to what — sensitive payloads (passwords, tokens)
must never be passed in `extra`."""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def log_action(
    db: Session,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    extra: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        request_id=request_id,
        ip_address=ip_address,
        extra=extra or {},
        created_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
