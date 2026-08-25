from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.models.enums import RoleName
from app.models.user import User
from app.repositories.user_repository import get_user_by_email


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def issue_token(user: User) -> str:
    return create_access_token(
        subject=str(user.id),
        extra_claims={"role": RoleName(user.role.name).value, "email": user.email},
    )
