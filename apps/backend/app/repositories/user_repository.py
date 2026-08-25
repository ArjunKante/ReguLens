from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import RoleName
from app.models.user import Role, User


def get_role_by_name(db: Session, name: RoleName) -> Role | None:
    return db.execute(select(Role).where(Role.name == name)).scalar_one_or_none()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


def get_user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def list_users(db: Session) -> list[User]:
    return list(db.execute(select(User).order_by(User.created_at)).scalars())


def create_user(
    db: Session, *, email: str, hashed_password: str, full_name: str, role: Role
) -> User:
    user = User(email=email, hashed_password=hashed_password, full_name=full_name, role_id=role.id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
