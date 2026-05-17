from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TypedDict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.mixins import utc_now
from app.models.user import AuthRefreshToken, User
from app.services.errors import AuthenticationError, ConflictError, ForbiddenError, SecurityConfigurationError


class TokenPair(TypedDict):
    token_type: str
    access_token: str
    expires_in: int
    refresh_token: str
    refresh_expires_in: int
    user: User


class AuthService:
    def register(
        self,
        db: Session,
        *,
        email: str,
        password: str,
        name: str,
        timezone_name: str,
    ) -> TokenPair:
        normalized_email = self._normalize_email(email)
        if self._find_user_by_email(db, normalized_email) is not None:
            raise ConflictError("Email already registered")

        user = User(
            email=normalized_email,
            name=name.strip(),
            timezone=timezone_name.strip(),
            password_hash=hash_password(password),
        )
        db.add(user)
        db.flush()
        token_pair = self._issue_token_pair(db, user=user)
        db.commit()
        db.refresh(user)
        return token_pair

    def login(self, db: Session, *, email: str, password: str) -> TokenPair:
        user = self._find_user_by_email(db, self._normalize_email(email))
        if user is None or not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password")
        self._ensure_active(user)
        token_pair = self._issue_token_pair(db, user=user)
        db.commit()
        db.refresh(user)
        return token_pair

    def refresh(self, db: Session, *, refresh_token: str) -> TokenPair:
        token = self._get_refresh_token(db, refresh_token=refresh_token)
        now = utc_now()
        if token.revoked_at is not None:
            raise AuthenticationError("Refresh token has been revoked")
        if self._as_aware(token.expires_at) <= now:
            raise AuthenticationError("Refresh token has expired")

        user = token.user
        self._ensure_active(user)
        token.revoked_at = now
        token.last_used_at = now
        token_pair = self._issue_token_pair(db, user=user)
        db.commit()
        db.refresh(user)
        return token_pair

    def logout(self, db: Session, *, refresh_token: str) -> dict:
        token_hash = hash_refresh_token(refresh_token)
        token = db.scalars(select(AuthRefreshToken).where(AuthRefreshToken.token_hash == token_hash)).first()
        if token is None:
            return {"revoked": False, "revoked_at": None}
        if token.revoked_at is None:
            token.revoked_at = utc_now()
            token.last_used_at = token.revoked_at
            db.commit()
            db.refresh(token)
        return {"revoked": True, "revoked_at": token.revoked_at}

    def to_user_response(self, user: User) -> dict:
        return {
            "id": user.id,
            "email": user.email or "",
            "name": user.name,
            "timezone": user.timezone,
            "is_active": user.is_active,
        }

    def to_token_response(self, token_pair: TokenPair) -> dict:
        return {
            "token_type": token_pair["token_type"],
            "access_token": token_pair["access_token"],
            "expires_in": token_pair["expires_in"],
            "refresh_token": token_pair["refresh_token"],
            "refresh_expires_in": token_pair["refresh_expires_in"],
            "user": self.to_user_response(token_pair["user"]),
        }

    def _issue_token_pair(self, db: Session, *, user: User) -> TokenPair:
        self._ensure_token_configured()
        refresh_token = generate_refresh_token()
        refresh_expires_in = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
        db.add(
            AuthRefreshToken(
                user_id=user.id,
                token_hash=hash_refresh_token(refresh_token),
                expires_at=utc_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            )
        )
        return {
            "token_type": "bearer",
            "access_token": create_access_token(user.id),
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "refresh_token": refresh_token,
            "refresh_expires_in": refresh_expires_in,
            "user": user,
        }

    def _get_refresh_token(self, db: Session, *, refresh_token: str) -> AuthRefreshToken:
        token_hash = hash_refresh_token(refresh_token)
        token = db.scalars(
            select(AuthRefreshToken).where(AuthRefreshToken.token_hash == token_hash)
        ).first()
        if token is None:
            raise AuthenticationError("Refresh token is invalid")
        return token

    def _find_user_by_email(self, db: Session, email: str) -> User | None:
        return db.scalars(select(User).where(func.lower(User.email) == email)).first()

    def _normalize_email(self, email: str) -> str:
        return email.strip().lower()

    def _ensure_active(self, user: User) -> None:
        if not user.is_active:
            raise ForbiddenError("User is inactive")

    def _ensure_token_configured(self) -> None:
        environment = settings.ENVIRONMENT.lower()
        if environment in {"prod", "production"} and settings.SECRET_KEY == "change-me-in-production":
            raise SecurityConfigurationError("SECRET_KEY must be configured for production auth")

    def _as_aware(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


auth_service = AuthService()
