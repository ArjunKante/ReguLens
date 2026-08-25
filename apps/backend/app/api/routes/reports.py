from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth.dependencies import require_any_authenticated
from app.core.database import get_db
from app.models.report import Report
from app.models.user import User
from app.storage.files import read_bytes

router = APIRouter(prefix="/reports", tags=["reports"])

_MEDIA_TYPES = {"PDF": "application/pdf", "HTML": "text/html"}


@router.get("/{report_id}/download")
def download_report(
    report_id: uuid.UUID, db: Session = Depends(get_db), _user: User = Depends(require_any_authenticated)
) -> Response:
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    content = read_bytes(report.file_path)
    media_type = _MEDIA_TYPES.get(report.format, "application/octet-stream")
    filename = f"lmscan-report-{report.inspection_id}.{report.format.lower()}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
