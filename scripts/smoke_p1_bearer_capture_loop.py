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
    original_auth_mode = settings.AUTH_MODE
    original_environment = settings.ENVIRONMENT
    try:
        settings.AUTH_MODE = "jwt"
        settings.ENVIRONMENT = "development"

        client = TestClient(app)
        registered = _expect(
            client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": password, "name": name, "timezone": timezone},
            ),
            201,
            "register",
        )
        headers = {"Authorization": f"Bearer {registered['access_token']}"}
        auth_me = _expect(client.get("/api/v1/auth/me", headers=headers), 200, "get auth me")

        suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
        capture = _expect(
            client.post(
                "/api/v1/captures",
                json={"raw_text": f"todo Finish Chronos real capture smoke {suffix}"},
                headers=headers,
            ),
            201,
            "create capture",
        )
        if capture["parse_result"]["result_type"] != "task":
            raise RuntimeError(f"capture should parse as task, got {capture['parse_result']['result_type']}")
        inbox_item_id = capture["inbox_item"]["id"]

        confirmed = _expect(
            client.post(f"/api/v1/inbox/{inbox_item_id}/confirm", headers=headers),
            200,
            "confirm inbox item",
        )
        if confirmed["result_entity_type"] != "task":
            raise RuntimeError(f"confirmed inbox item should create task, got {confirmed['result_entity_type']}")
        if confirmed["today_impact"]["plan_exists"]:
            raise RuntimeError("fresh capture smoke should not create Today before GET /today")
        task_id = confirmed["result_entity_id"]

        today = _expect(client.get("/api/v1/today", headers=headers), 200, "get today")
        today_item = _find_today_item(today, task_id=task_id)
        if today_item is None:
            raise RuntimeError("captured task was not present in Today plan")

        task_detail = _expect(client.get(f"/api/v1/tasks/{task_id}", headers=headers), 200, "get task detail")
        if not task_detail["actions"]["can_start_focus"]:
            raise RuntimeError("captured task should be startable from Task Detail")
        if task_detail["today_context"]["daily_plan_item_id"] != today_item["daily_plan_item_id"]:
            raise RuntimeError("Task Detail today context does not match Today item")

        breakdown = _expect(
            client.post(f"/api/v1/tasks/{task_id}/breakdown", headers=headers),
            200,
            "break down captured task",
        )
        if not breakdown["created_steps"]:
            raise RuntimeError("breakdown did not create steps for captured task")
        ai_job = _expect(
            client.get(f"/api/v1/ai-jobs/{breakdown['ai_job']['id']}", headers=headers),
            200,
            "get breakdown ai job",
        )
        if ai_job["status"] not in {"succeeded", "succeeded_with_fallback"}:
            raise RuntimeError(f"unexpected breakdown AI job status: {ai_job['status']}")

        task_detail_after_breakdown = _expect(
            client.get(f"/api/v1/tasks/{task_id}", headers=headers),
            200,
            "get task detail after breakdown",
        )
        if not task_detail_after_breakdown["steps"]:
            raise RuntimeError("task detail did not include generated steps")

        focus = _expect(
            client.post(
                "/api/v1/focus-sessions",
                json={
                    "task_id": task_id,
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
        refreshed_item = _find_today_item(refreshed_today, task_id=task_id)
        if refreshed_item is None or refreshed_item["item_status"] != "completed":
            raise RuntimeError("completed focus did not mark the captured Today item completed")

        report = _expect(
            client.post("/api/v1/reports/daily/generate", headers=headers),
            200,
            "generate daily report",
        )
        if report["completed_task_count"] < 1 or report["focus_minutes"] < 12:
            raise RuntimeError("daily report did not include captured focus result")

        me_overview = _expect(client.get("/api/v1/me/overview", headers=headers), 200, "get me overview")
        if me_overview["profile"]["user_id"] != registered["user"]["id"]:
            raise RuntimeError("Me overview user did not match registered user")

        return {
            "status": "ok",
            "scenario": "p1_bearer_capture_loop",
            "user_id": registered["user"]["id"],
            "auth_me_email": auth_me["email"],
            "capture_id": capture["capture"]["id"],
            "inbox_item_id": inbox_item_id,
            "task_id": task_id,
            "breakdown_ai_job_id": ai_job["id"],
            "daily_plan_id": today["daily_plan_id"],
            "daily_plan_item_id": today_item["daily_plan_item_id"],
            "focus_session_id": focus["id"],
            "daily_report_id": report["id"],
            "today_completion_rate": refreshed_today["progress"]["completion_rate"],
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
    parser = argparse.ArgumentParser(description="Run the Chronos P1 Capture -> Focus loop through JWT auth.")
    parser.add_argument("--email", default=f"p1-bearer-capture-smoke+{suffix}@chronos.local")
    parser.add_argument("--password", default=f"p1-bearer-capture-password-{suffix}")
    parser.add_argument("--name", default="Chronos P1 Bearer Capture Smoke")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    args = parser.parse_args()

    result = run_smoke(email=args.email, password=args.password, name=args.name, timezone=args.timezone)
    print("Chronos P1 Bearer Capture smoke passed.")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
