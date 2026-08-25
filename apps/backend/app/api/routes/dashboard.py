from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import require_any_authenticated
from app.core.database import get_db
from app.models.user import User
from app.schemas.dashboard import DashboardStatistics
from app.services.dashboard_service import get_dashboard_statistics

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/statistics", response_model=DashboardStatistics)
def statistics(db: Session = Depends(get_db), _user: User = Depends(require_any_authenticated)) -> DashboardStatistics:
    return get_dashboard_statistics(db)
