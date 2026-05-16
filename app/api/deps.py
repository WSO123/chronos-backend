import uuid

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.api.errors import APIError
from app.core.db import get_db
from app.models.user import User


def get_current_user_id(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> uuid.UUID:
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

    if db.get(User, user_id) is None:
        raise APIError(
            status_code=404,
            code="USER_NOT_FOUND",
            message="User not found",
        )

    return user_id
