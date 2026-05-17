import uuid

from app.core.security import hash_password
from app.models.user import User


def create_user(
    db,
    *,
    name: str = "Test User",
    email: str | None = None,
    password: str | None = None,
    is_active: bool = True,
) -> User:
    user = User(
        id=uuid.uuid4(),
        name=name,
        email=email or f"{uuid.uuid4()}@example.com",
        password_hash=hash_password(password) if password is not None else None,
        timezone="Asia/Shanghai",
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
