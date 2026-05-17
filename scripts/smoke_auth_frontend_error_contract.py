from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sys
from typing import Any
import uuid

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import create_access_token
from main import app


def run_smoke(*, email: str, password: str, name: str, timezone: str) -> dict[str, Any]:
    client = TestClient(app)
    original_auth_mode = settings.AUTH_MODE
    original_environment = settings.ENVIRONMENT
    try:
        settings.AUTH_MODE = "jwt"
        settings.ENVIRONMENT = "development"

        registered = _expect_ok(
            client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": password, "name": name, "timezone": timezone},
            ),
            201,
            "register",
        )
        user_id = registered["user"]["id"]

        duplicate = _expect_error(
            client.post(
                "/api/v1/auth/register",
                json={"email": email.upper(), "password": password, "name": name, "timezone": timezone},
            ),
            409,
            "CONFLICT",
            "duplicate register",
        )
        invalid_login = _expect_error(
            client.post("/api/v1/auth/login", json={"email": email, "password": "wrong-password"}),
            401,
            "AUTHENTICATION_FAILED",
            "invalid login",
        )
        missing_bearer = _expect_error(
            client.get("/api/v1/me/overview"),
            401,
            "AUTH_REQUIRED",
            "missing bearer",
        )
        invalid_header = _expect_error(
            client.get("/api/v1/me/overview", headers={"Authorization": "Token not-a-bearer-token"}),
            401,
            "INVALID_AUTH_HEADER",
            "invalid auth header",
        )
        expired_token = create_access_token(uuid.UUID(user_id), expires_delta=timedelta(seconds=-1))
        expired_access = _expect_error(
            client.get("/api/v1/me/overview", headers={"Authorization": f"Bearer {expired_token}"}),
            401,
            "ACCESS_TOKEN_EXPIRED",
            "expired access token",
        )

        refreshed = _expect_ok(
            client.post("/api/v1/auth/refresh", json={"refresh_token": registered["refresh_token"]}),
            200,
            "refresh token",
        )
        refresh_reuse = _expect_error(
            client.post("/api/v1/auth/refresh", json={"refresh_token": registered["refresh_token"]}),
            401,
            "AUTHENTICATION_FAILED",
            "refresh token reuse",
        )
        unknown_logout = _expect_ok(
            client.post("/api/v1/auth/logout", json={"refresh_token": "not-a-real-refresh-token"}),
            200,
            "unknown logout",
        )
        logout = _expect_ok(
            client.post("/api/v1/auth/logout", json={"refresh_token": refreshed["refresh_token"]}),
            200,
            "logout",
        )
        post_logout_refresh = _expect_error(
            client.post("/api/v1/auth/refresh", json={"refresh_token": refreshed["refresh_token"]}),
            401,
            "AUTHENTICATION_FAILED",
            "post logout refresh",
        )

        return {
            "status": "ok",
            "scenario": "auth_frontend_error_contract",
            "user_id": user_id,
            "error_codes": {
                "duplicate_register": duplicate,
                "invalid_login": invalid_login,
                "missing_bearer": missing_bearer,
                "invalid_auth_header": invalid_header,
                "expired_access_token": expired_access,
                "refresh_token_reuse": refresh_reuse,
                "post_logout_refresh": post_logout_refresh,
            },
            "refresh_rotated": refreshed["refresh_token"] != registered["refresh_token"],
            "unknown_logout_revoked": unknown_logout["revoked"],
            "logout_revoked": logout["revoked"],
        }
    finally:
        settings.AUTH_MODE = original_auth_mode
        settings.ENVIRONMENT = original_environment


def _expect_ok(response, status_code: int, label: str) -> dict[str, Any]:
    if response.status_code != status_code:
        raise RuntimeError(
            f"{label} failed: expected {status_code}, got {response.status_code}, body={response.text}"
        )
    return response.json()


def _expect_error(response, status_code: int, code: str, label: str) -> str:
    if response.status_code != status_code:
        raise RuntimeError(
            f"{label} failed: expected status {status_code}, got {response.status_code}, body={response.text}"
        )
    body = response.json()
    actual_code = body.get("error", {}).get("code")
    if actual_code != code:
        raise RuntimeError(f"{label} failed: expected error {code}, got {actual_code}, body={response.text}")
    return actual_code


def main() -> None:
    suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    parser = argparse.ArgumentParser(description="Run the Chronos auth frontend error contract smoke test.")
    parser.add_argument("--email", default=f"auth-errors+{suffix}@chronos.local")
    parser.add_argument("--password", default=f"auth-errors-password-{suffix}")
    parser.add_argument("--name", default="Chronos Auth Errors Smoke")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    args = parser.parse_args()

    result = run_smoke(email=args.email, password=args.password, name=args.name, timezone=args.timezone)
    print("Chronos auth frontend error contract smoke passed.")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
