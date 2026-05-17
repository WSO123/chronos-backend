from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.user import User, UserSettings
from app.services.auth_service import auth_service


def seed_user(*, email: str, name: str, timezone: str, password: str | None = None) -> User:
    normalized_email = email.strip().lower()
    with SessionLocal() as db:
        existing = db.scalars(
            select(User)
            .options(selectinload(User.settings))
            .where(User.email == normalized_email)
        ).first()
        if existing is not None:
            if existing.settings is None:
                db.add(UserSettings(user_id=existing.id))
            if password is not None:
                existing.password_hash = hash_password(password)
            if existing.settings is None or password is not None:
                db.commit()
                db.refresh(existing)
            return existing

        user = User(
            email=normalized_email,
            name=name,
            timezone=timezone,
            password_hash=hash_password(password) if password is not None else None,
        )
        db.add(user)
        db.flush()
        db.add(UserSettings(user_id=user.id))
        db.commit()
        db.refresh(user)
        return user


def issue_local_token(*, email: str, password: str) -> dict:
    normalized_email = email.strip().lower()
    with SessionLocal() as db:
        token_pair = auth_service.login(db, email=normalized_email, password=password)
        return auth_service.to_token_response(token_pair)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a local Chronos development user.")
    parser.add_argument("--email", default="dev@chronos.local")
    parser.add_argument("--name", default="Chronos Dev")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--password", default=None, help="Optional local password for /api/v1/auth/login.")
    parser.add_argument(
        "--emit-token",
        action="store_true",
        help="Print a local auth token pair. Requires --password.",
    )
    args = parser.parse_args()
    if args.emit_token and not args.password:
        parser.error("--emit-token requires --password")

    user = seed_user(email=args.email, name=args.name, timezone=args.timezone, password=args.password)
    print(f"Dev user ready: {user.id}")
    print(f"Use header: X-User-Id: {user.id}")
    if args.password:
        print(f"Login email: {user.email}")
        print("Login endpoint: POST /api/v1/auth/login")
    if args.emit_token:
        token_payload = issue_local_token(email=user.email, password=args.password)
        print("Local auth token pair:")
        print(json.dumps(token_payload, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
