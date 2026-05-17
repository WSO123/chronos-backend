from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient

from app.core.config import settings
from main import app


def run_smoke(*, email: str, password: str, name: str, timezone: str) -> dict[str, Any]:
    client = TestClient(app)
    original_auth_mode = settings.AUTH_MODE
    original_environment = settings.ENVIRONMENT
    try:
        settings.AUTH_MODE = "jwt"
        settings.ENVIRONMENT = "development"

        registered = _expect(
            client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": password, "name": name, "timezone": timezone},
            ),
            201,
            "register",
        )
        user_id = registered["user"]["id"]

        logged_in = _expect(
            client.post("/api/v1/auth/login", json={"email": email, "password": password}),
            200,
            "login",
        )
        auth_headers = {"Authorization": f"Bearer {logged_in['access_token']}"}
        auth_me = _expect(client.get("/api/v1/auth/me", headers=auth_headers), 200, "get auth me")
        me_overview = _expect(client.get("/api/v1/me/overview", headers=auth_headers), 200, "get me overview")

        refreshed = _expect(
            client.post("/api/v1/auth/refresh", json={"refresh_token": logged_in["refresh_token"]}),
            200,
            "refresh",
        )
        reused = client.post("/api/v1/auth/refresh", json={"refresh_token": logged_in["refresh_token"]})
        if reused.status_code != 401:
            raise RuntimeError(f"old refresh token reuse should fail, got {reused.status_code}: {reused.text}")

        logout = _expect(
            client.post("/api/v1/auth/logout", json={"refresh_token": refreshed["refresh_token"]}),
            200,
            "logout",
        )
        after_logout = client.post("/api/v1/auth/refresh", json={"refresh_token": refreshed["refresh_token"]})
        if after_logout.status_code != 401:
            raise RuntimeError(f"refresh after logout should fail, got {after_logout.status_code}: {after_logout.text}")

        return {
            "status": "ok",
            "scenario": "auth_token_loop",
            "user_id": user_id,
            "auth_me_email": auth_me["email"],
            "me_overview_user_id": me_overview["profile"]["user_id"],
            "refresh_rotated": refreshed["refresh_token"] != logged_in["refresh_token"],
            "old_refresh_rejected": reused.json()["error"]["code"],
            "logout_revoked": logout["revoked"],
            "post_logout_refresh_rejected": after_logout.json()["error"]["code"],
        }
    finally:
        settings.AUTH_MODE = original_auth_mode
        settings.ENVIRONMENT = original_environment


def _expect(response, status_code: int, label: str) -> dict[str, Any]:
    if response.status_code != status_code:
        raise RuntimeError(
            f"{label} failed: expected {status_code}, got {response.status_code}, body={response.text}"
        )
    return response.json()


def main() -> None:
    suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    parser = argparse.ArgumentParser(description="Run the Chronos auth token loop smoke test against the local DB.")
    parser.add_argument("--email", default=f"auth-smoke+{suffix}@chronos.local")
    parser.add_argument("--password", default=f"auth-smoke-password-{suffix}")
    parser.add_argument("--name", default="Chronos Auth Smoke")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    args = parser.parse_args()

    result = run_smoke(email=args.email, password=args.password, name=args.name, timezone=args.timezone)
    print("Chronos auth token smoke passed.")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
