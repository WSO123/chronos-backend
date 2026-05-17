from __future__ import annotations

import argparse
from datetime import UTC, datetime
from decimal import Decimal
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


FOCUS_MINUTES = 18


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
        focus_task = _capture_and_confirm_task(
            client,
            headers=headers,
            raw_text=f"todo Finish P1 mainline contract focus task {suffix}",
            label="focus task",
        )
        postpone_task = _capture_and_confirm_task(
            client,
            headers=headers,
            raw_text=f"todo Postpone P1 mainline contract follow-up {suffix}",
            label="postpone task",
        )

        today = _expect(client.get("/api/v1/today", headers=headers), 200, "get today")
        plan_date = today["date"]
        focus_item = _find_today_item(today, task_id=focus_task["task_id"])
        postpone_item = _find_today_item(today, task_id=postpone_task["task_id"])
        if focus_item is None or postpone_item is None:
            raise RuntimeError("confirmed Capture tasks were not both present in Today")

        task_detail_before = _expect(
            client.get(f"/api/v1/tasks/{focus_task['task_id']}", headers=headers),
            200,
            "get focus task detail before focus",
        )
        if task_detail_before["today_context"]["daily_plan_item_id"] != focus_item["daily_plan_item_id"]:
            raise RuntimeError("Task Detail today_context does not match Today item before focus")
        if not task_detail_before["actions"]["can_start_focus"]:
            raise RuntimeError("focus task should be startable from Task Detail")

        focus = _expect(
            client.post(
                "/api/v1/focus-sessions",
                json={
                    "task_id": focus_task["task_id"],
                    "daily_plan_item_id": task_detail_before["today_context"]["daily_plan_item_id"],
                    "planned_duration_min": 25,
                },
                headers=headers,
            ),
            201,
            "start focus from Task Detail context",
        )
        task_detail_during_focus = _expect(
            client.get(f"/api/v1/tasks/{focus_task['task_id']}", headers=headers),
            200,
            "get focus task detail during focus",
        )
        if not task_detail_during_focus["focus_state"]["is_currently_focusing_this_task"]:
            raise RuntimeError("Task Detail did not expose active Focus state")
        if task_detail_during_focus["actions"]["can_start_focus"]:
            raise RuntimeError("Task Detail should disable Start Focus while session is active")

        completed_focus = _expect(
            client.post(
                f"/api/v1/focus-sessions/{focus['id']}/complete",
                json={"actual_duration_min": FOCUS_MINUTES},
                headers=headers,
            ),
            200,
            "complete focus",
        )
        task_detail_after_focus = _expect(
            client.get(f"/api/v1/tasks/{focus_task['task_id']}", headers=headers),
            200,
            "get focus task detail after focus",
        )

        postponed_today_item = _expect(
            client.patch(
                f"/api/v1/today/items/{postpone_item['daily_plan_item_id']}",
                json={"status": "postponed"},
                headers=headers,
            ),
            200,
            "postpone today item",
        )
        task_detail_after_postpone = _expect(
            client.get(f"/api/v1/tasks/{postpone_task['task_id']}", headers=headers),
            200,
            "get postponed task detail",
        )

        today_after_actions = _expect(client.get("/api/v1/today", headers=headers), 200, "get today after actions")
        focus_item_after_actions = _find_today_item(today_after_actions, task_id=focus_task["task_id"])
        postpone_item_after_actions = _find_today_item(today_after_actions, task_id=postpone_task["task_id"])
        if focus_item_after_actions is None or postpone_item_after_actions is None:
            raise RuntimeError("Today lost one of the smoke tasks after actions")

        report = _expect(
            client.get(f"/api/v1/reports/daily?report_date={plan_date}", headers=headers),
            200,
            "get daily report",
        )
        me_overview = _expect(
            client.get(f"/api/v1/me/overview?today={plan_date}", headers=headers),
            200,
            "get me overview",
        )

        payload = build_p1_contract_payload(
            user_id=registered["user"]["id"],
            auth_me_email=auth_me["email"],
            registered_email=registered["user"]["email"],
            focus_capture_id=focus_task["capture_id"],
            focus_inbox_item_id=focus_task["inbox_item_id"],
            focus_task_id=focus_task["task_id"],
            focus_confirm_plan_exists=focus_task["confirm_plan_exists"],
            focus_confirm_replanned=focus_task["confirm_replanned"],
            postpone_capture_id=postpone_task["capture_id"],
            postpone_inbox_item_id=postpone_task["inbox_item_id"],
            postpone_task_id=postpone_task["task_id"],
            postpone_confirm_plan_exists=postpone_task["confirm_plan_exists"],
            postpone_confirm_replanned=postpone_task["confirm_replanned"],
            daily_plan_id=today_after_actions["daily_plan_id"],
            today_plan_version=today["plan_version"],
            final_plan_version=today_after_actions["plan_version"],
            today_total_count=today_after_actions["progress"]["total_count"],
            today_focus_minutes=today_after_actions["progress"]["focus_minutes"],
            today_completion_rate=today_after_actions["progress"]["completion_rate"],
            today_can_replan=today_after_actions["quick_actions"]["can_replan"],
            today_can_capture=today_after_actions["quick_actions"]["can_capture"],
            today_can_view_report=today_after_actions["quick_actions"]["can_view_report"],
            task_detail_context_matches=task_detail_before["today_context"]["daily_plan_item_id"]
            == focus_item["daily_plan_item_id"],
            focus_session_id=focus["id"],
            focus_completed_status=completed_focus["status"],
            focus_daily_plan_item_id=completed_focus["daily_plan_item_id"],
            expected_focus_daily_plan_item_id=focus_item["daily_plan_item_id"],
            task_detail_during_focus_session_id=task_detail_during_focus["focus_state"]["active_focus_session_id"],
            task_detail_after_focus_status=task_detail_after_focus["status"],
            task_detail_after_focus_progress=str(task_detail_after_focus["progress"]),
            today_focus_item_status=focus_item_after_actions["item_status"],
            postponed_today_item_status=postponed_today_item["item_status"],
            task_detail_after_postpone_status=task_detail_after_postpone["status"],
            today_postpone_item_status=postpone_item_after_actions["item_status"],
            daily_report_id=report["id"],
            report_daily_plan_id=report["daily_plan_id"],
            report_completed_task_count=report["completed_task_count"],
            report_postponed_task_count=report["postponed_task_count"],
            report_focus_minutes=report["focus_minutes"],
            report_completion_rate=report["completion_rate"],
            me_daily_report_id=me_overview["reports"]["daily_report_id"],
            me_daily_report_available=me_overview["reports"]["daily_report_available"],
            me_today_completed_task_count=me_overview["today"]["completed_task_count"],
            me_today_focus_minutes=me_overview["today"]["focus_minutes"],
            me_tasks_completed_task_count=me_overview["tasks"]["completed_task_count"],
            me_tasks_postponed_task_count=me_overview["tasks"]["postponed_task_count"],
        )
        validate_p1_contract_payload(payload)
        return payload
    finally:
        settings.AUTH_MODE = original_auth_mode
        settings.ENVIRONMENT = original_environment


def _capture_and_confirm_task(
    client: TestClient,
    *,
    headers: dict[str, str],
    raw_text: str,
    label: str,
) -> dict[str, Any]:
    capture = _expect(
        client.post("/api/v1/captures", json={"raw_text": raw_text}, headers=headers),
        201,
        f"create {label} capture",
    )
    if capture["parse_result"]["result_type"] != "task":
        raise RuntimeError(f"{label} Capture should parse as task")
    confirmed = _expect(
        client.post(f"/api/v1/inbox/{capture['inbox_item']['id']}/confirm", headers=headers),
        200,
        f"confirm {label} inbox item",
    )
    if confirmed["result_entity_type"] != "task":
        raise RuntimeError(f"{label} Inbox confirm should create task")
    today_impact = confirmed["today_impact"]
    return {
        "capture_id": capture["capture"]["id"],
        "inbox_item_id": capture["inbox_item"]["id"],
        "task_id": confirmed["result_entity_id"],
        "confirm_plan_exists": bool(today_impact and today_impact["plan_exists"]),
        "confirm_replanned": bool(today_impact and today_impact["replanned"]),
    }


def build_p1_contract_payload(
    *,
    user_id: str,
    auth_me_email: str,
    registered_email: str,
    focus_capture_id: str,
    focus_inbox_item_id: str,
    focus_task_id: str,
    focus_confirm_plan_exists: bool,
    focus_confirm_replanned: bool,
    postpone_capture_id: str,
    postpone_inbox_item_id: str,
    postpone_task_id: str,
    postpone_confirm_plan_exists: bool,
    postpone_confirm_replanned: bool,
    daily_plan_id: str,
    today_plan_version: int,
    final_plan_version: int,
    today_total_count: int,
    today_focus_minutes: int,
    today_completion_rate: float,
    today_can_replan: bool,
    today_can_capture: bool,
    today_can_view_report: bool,
    task_detail_context_matches: bool,
    focus_session_id: str,
    focus_completed_status: str,
    focus_daily_plan_item_id: str,
    expected_focus_daily_plan_item_id: str,
    task_detail_during_focus_session_id: str | None,
    task_detail_after_focus_status: str,
    task_detail_after_focus_progress: str,
    today_focus_item_status: str,
    postponed_today_item_status: str,
    task_detail_after_postpone_status: str,
    today_postpone_item_status: str,
    daily_report_id: str,
    report_daily_plan_id: str | None,
    report_completed_task_count: int,
    report_postponed_task_count: int,
    report_focus_minutes: int,
    report_completion_rate: float,
    me_daily_report_id: str | None,
    me_daily_report_available: bool,
    me_today_completed_task_count: int,
    me_today_focus_minutes: int,
    me_tasks_completed_task_count: int,
    me_tasks_postponed_task_count: int,
) -> dict[str, Any]:
    focus_progress = Decimal(str(task_detail_after_focus_progress))
    return {
        "status": "ok",
        "scenario": "p1_mainline_contract",
        "user_id": user_id,
        "entities": {
            "focus_capture_id": focus_capture_id,
            "focus_inbox_item_id": focus_inbox_item_id,
            "focus_task_id": focus_task_id,
            "postpone_capture_id": postpone_capture_id,
            "postpone_inbox_item_id": postpone_inbox_item_id,
            "postpone_task_id": postpone_task_id,
            "daily_plan_id": daily_plan_id,
            "focus_session_id": focus_session_id,
            "daily_report_id": daily_report_id,
        },
        "today": {
            "initial_plan_version": today_plan_version,
            "final_plan_version": final_plan_version,
            "total_count": today_total_count,
            "focus_minutes": today_focus_minutes,
            "completion_rate": today_completion_rate,
        },
        "report": {
            "completed_task_count": report_completed_task_count,
            "postponed_task_count": report_postponed_task_count,
            "focus_minutes": report_focus_minutes,
            "completion_rate": report_completion_rate,
        },
        "me": {
            "today_completed_task_count": me_today_completed_task_count,
            "today_focus_minutes": me_today_focus_minutes,
            "tasks_completed_task_count": me_tasks_completed_task_count,
            "tasks_postponed_task_count": me_tasks_postponed_task_count,
        },
        "contract_checks": {
            "auth_me_matches_registered": auth_me_email == registered_email,
            "captures_confirm_without_hidden_today": not focus_confirm_plan_exists
            and not focus_confirm_replanned
            and not postpone_confirm_plan_exists
            and not postpone_confirm_replanned,
            "today_contains_confirmed_tasks": today_total_count >= 2,
            "today_quick_actions_available": today_can_replan and today_can_capture and today_can_view_report,
            "task_detail_context_matches_today": task_detail_context_matches,
            "focus_uses_task_detail_context": focus_daily_plan_item_id == expected_focus_daily_plan_item_id,
            "task_detail_exposes_active_focus": task_detail_during_focus_session_id == focus_session_id,
            "focus_completion_updates_task": focus_completed_status == "completed"
            and task_detail_after_focus_status == "completed"
            and focus_progress >= Decimal("1.00"),
            "today_reflects_focus_completion": today_focus_item_status == "completed",
            "today_quick_postpone_updates_task": postponed_today_item_status == "postponed"
            and task_detail_after_postpone_status == "postponed"
            and today_postpone_item_status == "postponed",
            "daily_report_matches_actions": report_daily_plan_id == daily_plan_id
            and report_completed_task_count >= 1
            and report_postponed_task_count >= 1
            and report_focus_minutes >= FOCUS_MINUTES,
            "me_overview_matches_report": me_daily_report_available
            and me_daily_report_id == daily_report_id
            and me_today_completed_task_count == report_completed_task_count
            and me_today_focus_minutes == report_focus_minutes
            and me_tasks_completed_task_count >= 1
            and me_tasks_postponed_task_count >= 1,
        },
    }


def validate_p1_contract_payload(payload: dict[str, Any]) -> None:
    failed = [key for key, passed in payload.get("contract_checks", {}).items() if not passed]
    if payload.get("status") != "ok" or payload.get("scenario") != "p1_mainline_contract" or failed:
        raise RuntimeError(
            "p1 mainline contract smoke failed: "
            + json.dumps({"status": payload.get("status"), "scenario": payload.get("scenario"), "failed": failed})
        )


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
    parser = argparse.ArgumentParser(description="Run the Chronos P1 mainline contract smoke test.")
    parser.add_argument("--email", default=f"p1-mainline-contract+{suffix}@chronos.local")
    parser.add_argument("--password", default=f"p1-mainline-contract-password-{suffix}")
    parser.add_argument("--name", default="Chronos P1 Mainline Contract Smoke")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    args = parser.parse_args()

    result = run_smoke(email=args.email, password=args.password, name=args.name, timezone=args.timezone)
    print("Chronos P1 mainline contract smoke passed.")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
