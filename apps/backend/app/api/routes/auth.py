from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.audit.service import log_action
from app.auth.service import authenticate_user, issue_token
from app.core.database import get_db
from app.schemas.user import LoginRequest, Token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> Token:
    user = authenticate_user(db, payload.email, payload.password)
    if user is None:
        log_action(
            db,
            actor_id=None,
            action="LOGIN_FAILED",
            entity_type="user",
            entity_id=payload.email,
            ip_address=request.client.host if request.client else None,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    token = issue_token(user)
    log_action(
        db,
        actor_id=user.id,
        action="LOGIN_SUCCESS",
        entity_type="user",
        entity_id=str(user.id),
        ip_address=request.client.host if request.client else None,
    )
    return Token(
        access_token=token,
        role=user.role.name,  # type: ignore[arg-type]
        full_name=user.full_name,
        user_id=user.id,
    )
