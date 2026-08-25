"""FastAPI dependencies enforcing authentication and role-based access
control (RBAC). Every route that requires a specific role uses `require_role`
so permission logic lives in one place and is enforced server-side
regardless of what the frontend does or doesn't hide (Section 20: "Enforce
permissions on the backend")."""
from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.enums import RoleName
from app.models.user import User
from app.repositories.user_repository import get_user_by_id

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise credentials_exception
    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        raise credentials_exception
    try:
        user_id = uuid.UUID(payload["sub"])
    except ValueError:
        raise credentials_exception from None
    user = get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def require_role(*allowed_roles: RoleName) -> Callable[[User], User]:
    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if RoleName(current_user.role.name) not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role.name}' is not permitted to perform this action.",
            )
        return current_user

    return _dependency


require_admin = require_role(RoleName.ADMIN)
require_inspector = require_role(RoleName.ADMIN, RoleName.INSPECTOR)
require_reviewer = require_role(RoleName.ADMIN, RoleName.REVIEWER)
require_any_authenticated = require_role(RoleName.ADMIN, RoleName.INSPECTOR, RoleName.REVIEWER)
