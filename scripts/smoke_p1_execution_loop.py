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

from main import app
from scripts.dev_seed_user import seed_user


def run_smoke(*, email: str, name: str, timezone: str) -> dict[str, Any]:
    user = seed_user(email=email, name=name, timezone=timezone)
    headers = {"X-User-Id": str(user.id)}
    client = TestClient(app)
    suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S")

    capture = _expect(
        client.post(
            "/api/v1/captures",
            json={"raw_text": f"todo Run P1 execution smoke {suffix}"},
            headers=headers,
        ),
        201,
        "create capture",
    )
    inbox_item_id = capture["inbox_item"]["id"]

    confirmed = _expect(
        client.post(f"/api/v1/inbox/{inbox_item_id}/confirm", headers=headers),
        200,
        "confirm inbox item",
    )
    task_id = confirmed["result_entity_id"]

    breakdown = _expect(
        client.post(f"/api/v1/tasks/{task_id}/breakdown", headers=headers),
        200,
        "break down task",
    )
    if not breakdown["created_steps"]:
        raise RuntimeError("breakdown did not create steps for a new smoke task")

    ai_job_id = breakdown["ai_job"]["id"]
    ai_job = _expect(
        client.get(f"/api/v1/ai-jobs/{ai_job_id}", headers=headers),
        200,
        "get AI job",
    )
    if ai_job["status"] != "succeeded_with_fallback":
        raise RuntimeError(f"unexpected AI job status: {ai_job['status']}")

    today = _expect(client.get("/api/v1/today", headers=headers), 200, "get today")
    today_item = _find_today_item(today, task_id=task_id)
    if today_item is None:
        raise RuntimeError("smoke task was not present in Today plan")

    task_detail = _expect(client.get(f"/api/v1/tasks/{task_id}", headers=headers), 200, "get task detail")
    if not task_detail["steps"]:
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

    report = _expect(
        client.post("/api/v1/reports/daily/generate", headers=headers),
        200,
        "generate daily report",
    )
    me_overview = _expect(client.get("/api/v1/me/overview", headers=headers), 200, "get me overview")

    return {
        "status": "ok",
        "user_id": str(user.id),
        "task_id": task_id,
        "ai_job_id": ai_job_id,
        "daily_plan_id": today["daily_plan_id"],
        "focus_session_id": focus["id"],
        "daily_report_id": report["id"],
        "me_today_completion_rate": me_overview["today"]["completion_rate"],
    }


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
    parser = argparse.ArgumentParser(description="Run the Chronos P1 execution loop smoke test against the local DB.")
    parser.add_argument(
        "--email",
        default=f"smoke+{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}@chronos.local",
    )
    parser.add_argument("--name", default="Chronos Smoke")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    args = parser.parse_args()

    result = run_smoke(email=args.email, name=args.name, timezone=args.timezone)
    print("Chronos P1 smoke passed.")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
