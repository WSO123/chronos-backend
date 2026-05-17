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
from scripts.dev_seed_demo import seed_demo_data


def run_smoke(*, email: str, password: str, name: str, timezone: str) -> dict[str, Any]:
    original_auth_mode = settings.AUTH_MODE
    original_environment = settings.ENVIRONMENT
    try:
        settings.AUTH_MODE = "jwt"
        settings.ENVIRONMENT = "development"

        seed = seed_demo_data(
            email=email,
            name=name,
            timezone=timezone,
            password=password,
            emit_token=True,
        )
        client = TestClient(app)
        headers = {"Authorization": f"Bearer {seed['auth']['access_token']}"}
        high_value_task_id = str(seed["high_value_task_id"])

        auth_me = _expect(client.get("/api/v1/auth/me", headers=headers), 200, "get auth me")
        today = _expect(client.get("/api/v1/today", headers=headers), 200, "get today")
        today_item = _find_today_item(today, task_id=high_value_task_id)
        if today_item is None:
            raise RuntimeError("seeded high-value task was not present in Today plan")

        task_detail = _expect(
            client.get(f"/api/v1/tasks/{high_value_task_id}", headers=headers),
            200,
            "get task detail",
        )
        if not task_detail["steps"]:
            raise RuntimeError("seeded high-value task should include execution steps")
        if task_detail["today_context"]["daily_plan_item_id"] != today_item["daily_plan_item_id"]:
            raise RuntimeError("Task Detail today context does not match Today item")

        focus = _expect(
            client.post(
                "/api/v1/focus-sessions",
                json={
                    "task_id": high_value_task_id,
                    "daily_plan_item_id": today_item["daily_plan_item_id"],
                    "planned_duration_min": 25,
                },
                headers=headers,
            ),
            201,
            "start focus",
        )
        finished_focus = _expect(
            client.post(
                f"/api/v1/focus-sessions/{focus['id']}/complete",
                json={"actual_duration_min": 12},
                headers=headers,
            ),
            200,
            "complete focus",
        )
        if finished_focus["status"] != "completed":
            raise RuntimeError(f"unexpected focus status: {finished_focus['status']}")

        refreshed_today = _expect(client.get("/api/v1/today", headers=headers), 200, "refresh today")
        refreshed_item = _find_today_item(refreshed_today, task_id=high_value_task_id)
        if refreshed_item is None or refreshed_item["item_status"] != "completed":
            raise RuntimeError("completed focus did not mark the Today item completed")

        report = _expect(
            client.post("/api/v1/reports/daily/generate", headers=headers),
            200,
            "generate daily report",
        )
        if report["completed_task_count"] < 1 or report["focus_minutes"] < 12:
            raise RuntimeError("daily report did not include the completed focus result")

        me_overview = _expect(client.get("/api/v1/me/overview", headers=headers), 200, "get me overview")
        if me_overview["profile"]["user_id"] != str(seed["user_id"]):
            raise RuntimeError("Me overview user did not match seeded user")

        return {
            "status": "ok",
            "scenario": "p1_bearer_execution_loop",
            "user_id": str(seed["user_id"]),
            "auth_me_email": auth_me["email"],
            "daily_plan_id": today["daily_plan_id"],
            "daily_plan_item_id": today_item["daily_plan_item_id"],
            "task_id": high_value_task_id,
            "focus_session_id": focus["id"],
            "daily_report_id": report["id"],
            "today_completion_rate": refreshed_today["progress"]["completion_rate"],
            "report_completed_task_count": report["completed_task_count"],
            "report_focus_minutes": report["focus_minutes"],
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


def _find_today_item(today: dict[str, Any], *, task_id: str) -> dict[str, Any] | None:
    for section_name in ("pinned_tasks", "recommended_tasks", "low_priority_tasks", "rolled_over_tasks"):
        for item in today["sections"][section_name]:
            if item["task_id"] == task_id:
                return item
    return None


def main() -> None:
    suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    parser = argparse.ArgumentParser(description="Run the Chronos P1 execution loop through JWT auth.")
    parser.add_argument("--email", default=f"p1-bearer-smoke+{suffix}@chronos.local")
    parser.add_argument("--password", default=f"p1-bearer-smoke-password-{suffix}")
    parser.add_argument("--name", default="Chronos P1 Bearer Smoke")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    args = parser.parse_args()

    result = run_smoke(email=args.email, password=args.password, name=args.name, timezone=args.timezone)
    print("Chronos P1 Bearer smoke passed.")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
