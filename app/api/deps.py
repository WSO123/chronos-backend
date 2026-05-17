import uuid

from fastapi import Depends, Header
from jose import JWTError
from jose.exceptions import ExpiredSignatureError
from sqlalchemy.orm import Session

from app.api.errors import APIError
from app.core.config import settings
from app.core.db import get_db
from app.core.security import decode_access_token
from app.models.user import User


def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> User:
    auth_mode = settings.AUTH_MODE.lower()
    if auth_mode == "jwt":
        _ensure_jwt_auth_configured()
        user_id = _user_id_from_bearer_token(authorization)
    elif auth_mode == "dev_header":
        user_id = _user_id_from_dev_header(x_user_id)
    else:
        raise APIError(
            status_code=500,
            code="AUTH_CONFIGURATION_ERROR",
            message="AUTH_MODE must be one of: dev_header, jwt",
        )

    user = db.get(User, user_id)
    if user is None:
        raise APIError(
            status_code=404,
            code="USER_NOT_FOUND",
            message="User not found",
        )
    if not user.is_active:
        raise APIError(
            status_code=403,
            code="USER_INACTIVE",
            message="User is inactive",
        )
    return user


def get_current_user_id(
    current_user: User = Depends(get_current_user),
) -> uuid.UUID:
    return current_user.id


def _user_id_from_dev_header(x_user_id: str | None) -> uuid.UUID:
    if not _dev_auth_header_allowed():
        raise APIError(
            status_code=500,
            code="INSECURE_AUTH_CONFIGURATION",
            message="X-User-Id development auth is disabled for this environment",
        )
    if not x_user_id:
        raise APIError(
            status_code=400,
            code="MISSING_USER_ID",
            message="X-User-Id header is required",
        )

    try:
        user_id = uuid.UUID(x_user_id)
    except ValueError as exc:
        raise APIError(
            status_code=400,
            code="INVALID_USER_ID",
            message="X-User-Id must be a valid UUID",
        ) from exc

    return user_id


def _dev_auth_header_allowed() -> bool:
    environment = settings.ENVIRONMENT.lower()
    return settings.ALLOW_DEV_AUTH_HEADER and environment not in {"prod", "production"}


def _ensure_jwt_auth_configured() -> None:
    environment = settings.ENVIRONMENT.lower()
    if environment in {"prod", "production"} and settings.SECRET_KEY == "change-me-in-production":
        raise APIError(
            status_code=500,
            code="INSECURE_AUTH_CONFIGURATION",
            message="SECRET_KEY must be configured for production JWT auth",
        )


def _user_id_from_bearer_token(authorization: str | None) -> uuid.UUID:
    if not authorization:
        raise APIError(
            status_code=401,
            code="AUTH_REQUIRED",
            message="Authorization bearer token is required",
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise APIError(
            status_code=401,
            code="INVALID_AUTH_HEADER",
            message="Authorization header must use Bearer token",
        )

    try:
        payload = decode_access_token(token.strip())
    except ExpiredSignatureError as exc:
        raise APIError(
            status_code=401,
            code="ACCESS_TOKEN_EXPIRED",
            message="Access token has expired",
        ) from exc
    except JWTError as exc:
        raise APIError(
            status_code=401,
            code="INVALID_ACCESS_TOKEN",
            message="Access token is invalid",
        ) from exc

    if payload.get("type") != "access":
        raise APIError(
            status_code=401,
            code="INVALID_ACCESS_TOKEN",
            message="Access token is invalid",
        )

    subject = payload.get("sub")
    try:
        return uuid.UUID(str(subject))
    except (TypeError, ValueError) as exc:
        raise APIError(
            status_code=401,
            code="INVALID_ACCESS_TOKEN",
            message="Access token subject is invalid",
        ) from exc
