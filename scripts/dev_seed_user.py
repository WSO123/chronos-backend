from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.db import SessionLocal
from app.models.user import User, UserSettings


def seed_user(*, email: str, name: str, timezone: str) -> User:
    with SessionLocal() as db:
        existing = db.scalars(
            select(User)
            .options(selectinload(User.settings))
            .where(User.email == email)
        ).first()
        if existing is not None:
            if existing.settings is None:
                db.add(UserSettings(user_id=existing.id))
                db.commit()
                db.refresh(existing)
            return existing

        user = User(email=email, name=name, timezone=timezone)
        db.add(user)
        db.flush()
        db.add(UserSettings(user_id=user.id))
        db.commit()
        db.refresh(user)
        return user


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a local Chronos development user.")
    parser.add_argument("--email", default="dev@chronos.local")
    parser.add_argument("--name", default="Chronos Dev")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    args = parser.parse_args()

    user = seed_user(email=args.email, name=args.name, timezone=args.timezone)
    print(f"Dev user ready: {user.id}")
    print(f"Use header: X-User-Id: {user.id}")


if __name__ == "__main__":
    main()
