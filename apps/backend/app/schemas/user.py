from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import RoleName


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: RoleName
    full_name: str
    user_id: uuid.UUID


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str
    role: RoleName


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: RoleName
    is_active: bool

    @classmethod
    def from_orm_user(cls, user) -> "UserOut":  # type: ignore[no-untyped-def]
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=RoleName(user.role.name),
            is_active=user.is_active,
        )
