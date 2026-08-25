from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.audit.service import log_action
from app.auth.dependencies import require_admin
from app.core.database import get_db
from app.core.security import hash_password
from app.models.user import User
from app.repositories.user_repository import (
    create_user,
    get_role_by_name,
    get_user_by_email,
    list_users,
)
from app.schemas.user import UserCreate, UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def get_users(
    db: Session = Depends(get_db), _admin: User = Depends(require_admin)
) -> list[UserOut]:
    return [UserOut.from_orm_user(u) for u in list_users(db)]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_new_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> UserOut:
    if get_user_by_email(db, payload.email) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered.")
    role = get_role_by_name(db, payload.role)
    if role is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown role.")
    user = create_user(
        db,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=role,
    )
    log_action(
        db,
        actor_id=admin.id,
        action="USER_CREATED",
        entity_type="user",
        entity_id=str(user.id),
        extra={"role": payload.role.value},
    )
    return UserOut.from_orm_user(user)
