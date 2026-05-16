import uuid

from app.models.user import User


def create_user(db, *, name: str = "Test User", email: str | None = None) -> User:
    user = User(
        id=uuid.uuid4(),
        name=name,
        email=email or f"{uuid.uuid4()}@example.com",
        timezone="Asia/Shanghai",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
