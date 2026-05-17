from __future__ import annotations

from datetime import datetime
import uuid

from pydantic import BaseModel, Field, field_validator


class AuthUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    timezone: str
    is_active: bool


class AuthRegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    timezone: str = Field(default="Asia/Shanghai", min_length=1, max_length=64)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("email must be valid")
        return normalized

    @field_validator("name", "timezone")
    @classmethod
    def strip_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank")
        return stripped


class AuthLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class AuthRefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=16)


class AuthLogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=16)


class AuthTokenResponse(BaseModel):
    token_type: str = "bearer"
    access_token: str
    expires_in: int
    refresh_token: str
    refresh_expires_in: int
    user: AuthUserResponse


class AuthLogoutResponse(BaseModel):
    revoked: bool
    revoked_at: datetime | None
