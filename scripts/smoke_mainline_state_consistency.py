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
        suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
        today_deadline = datetime.now(UTC).date().isoformat()

        goal = _expect(
            client.post(
                "/api/v1/goals",
                json={"title": f"Mainline state goal {suffix}", "value_level": "high"},
                headers=headers,
            ),
            201,
            "create goal",
        )
        prerequisite = _expect(
            client.post(
                "/api/v1/tasks",
                json={
                    "title": f"Prepare prerequisite {suffix}",
                    "goal_id": goal["id"],
                    "priority": 2,
                    "value_level": "high",
                    "estimated_duration_min": 20,
                    "deadline": today_deadline,
                },
                headers=headers,
            ),
            201,
            "create prerequisite task",
        )
        dependent = _expect(
            client.post(
                "/api/v1/tasks",
                json={
                    "title": f"Finish dependent work {suffix}",
                    "goal_id": goal["id"],
                    "priority": 2,
                    "value_level": "high",
                    "estimated_duration_min": 30,
                    "deadline": today_deadline,
                },
                headers=headers,
            ),
            201,
            "create dependent task",
        )

        initial_today = _expect(client.get("/api/v1/today", headers=headers), 200, "get initial today")
        plan_date = initial_today["date"]
        initial_version = initial_today["plan_version"]
        if _find_today_item(initial_today, task_id=prerequisite["id"]) is None:
            raise RuntimeError("prerequisite task was not present in initial Today")
        if _find_today_item(initial_today, task_id=dependent["id"]) is None:
            raise RuntimeError("dependent task was not present in initial Today")

        _expect(
            client.post(
                f"/api/v1/tasks/{dependent['id']}/dependencies",
                json={"prerequisite_task_id": prerequisite["id"], "reason": "Unlock dependent work first"},
                headers=headers,
            ),
            201,
            "add dependency",
        )
        after_dependency_today = _expect(client.get("/api/v1/today", headers=headers), 200, "today after dependency")
        if after_dependency_today["plan_version"] <= initial_version:
            raise RuntimeError("dependency change did not refresh current Today plan")
        _assert_task_order(
            after_dependency_today,
            before_task_id=prerequisite["id"],
            after_task_id=dependent["id"],
            label="dependency order",
        )
        goal_detail = _expect(
            client.get(f"/api/v1/goals/{goal['id']}/detail", headers=headers),
            200,
            "get goal detail after dependency",
        )
        next_task = goal_detail["task_list"]["recommended_next_task"]
        if next_task is None or next_task["id"] != prerequisite["id"]:
            raise RuntimeError("Goal Detail recommended next task did not respect unfinished prerequisite")

        capture = _expect(
            client.post(
                "/api/v1/captures",
                json={"raw_text": f"todo Review mainline state consistency {suffix}"},
                headers=headers,
            ),
            201,
            "create capture after active Today",
        )
        inbox_item_id = capture["inbox_item"]["id"]
        confirmed = _expect(
            client.post(f"/api/v1/inbox/{inbox_item_id}/confirm", headers=headers),
            200,
            "confirm inbox after active Today",
        )
        capture_task_id = confirmed["result_entity_id"]
        confirm_impact = confirmed["today_impact"]
        if not confirm_impact or not confirm_impact["plan_exists"] or not confirm_impact["replanned"]:
            raise RuntimeError(f"Inbox confirm did not refresh active Today: {confirm_impact}")

        after_confirm_today = _expect(client.get("/api/v1/today", headers=headers), 200, "today after inbox confirm")
        captured_item = _find_today_item(after_confirm_today, task_id=capture_task_id)
        if captured_item is None:
            raise RuntimeError("confirmed capture task was not present in refreshed Today")

        priority_adjustment = _expect(
            client.patch(
                f"/api/v1/tasks/{capture_task_id}/priority",
                json={"priority": 1, "value_level": "high", "reason": "Protect this mainline smoke task"},
                headers=headers,
            ),
            200,
            "adjust captured task priority",
        )
        priority_impact = priority_adjustment["today_impact"]
        if not priority_impact or not priority_impact["plan_exists"] or not priority_impact["replanned"]:
            raise RuntimeError(f"priority adjustment did not refresh active Today: {priority_impact}")

        after_priority_today = _expect(client.get("/api/v1/today", headers=headers), 200, "today after priority")
        priority_item = _find_today_item(after_priority_today, task_id=capture_task_id)
        if priority_item is None:
            raise RuntimeError("priority-adjusted task was not present in Today")
        strategy = _expect(
            client.get(f"/api/v1/today/strategy?plan_date={plan_date}", headers=headers),
            200,
            "get strategy after priority",
        )
        if strategy["factors"]["user_adjusted_count"] < 1:
            raise RuntimeError("Strategy Detail did not expose user priority adjustment")
        if strategy["factors"]["dependency_protected_count"] < 1:
            raise RuntimeError("Strategy Detail did not expose dependency protection")

        task_detail = _expect(client.get(f"/api/v1/tasks/{capture_task_id}", headers=headers), 200, "get task detail")
        if task_detail["today_context"]["daily_plan_item_id"] != priority_item["daily_plan_item_id"]:
            raise RuntimeError("Task Detail today_context did not match the current Today item")

        stale_report = _expect(
            client.post(f"/api/v1/reports/daily/generate?report_date={plan_date}", headers=headers),
            200,
            "generate report before focus",
        )

        focus = _expect(
            client.post(
                "/api/v1/focus-sessions",
                json={"task_id": capture_task_id, "planned_duration_min": 25},
                headers=headers,
            ),
            201,
            "start focus without explicit Today item",
        )
        if focus["daily_plan_item_id"] != priority_item["daily_plan_item_id"]:
            raise RuntimeError("Focus did not auto-link to the current Today item")
        finished_focus = _expect(
            client.post(
                f"/api/v1/focus-sessions/{focus['id']}/complete",
                json={"actual_duration_min": 17},
                headers=headers,
            ),
            200,
            "complete auto-linked focus",
        )
        if finished_focus["status"] != "completed":
            raise RuntimeError(f"unexpected focus status: {finished_focus['status']}")
        if finished_focus["daily_plan_item_id"] != priority_item["daily_plan_item_id"]:
            raise RuntimeError("completed focus lost its Today item linkage")

        after_focus_today = _expect(client.get("/api/v1/today", headers=headers), 200, "today after focus")
        completed_item = _find_today_item(after_focus_today, task_id=capture_task_id)
        if completed_item is None or completed_item["item_status"] != "completed":
            raise RuntimeError("completed focus did not mark the Today item completed")
        if after_focus_today["progress"]["focus_minutes"] < 17:
            raise RuntimeError("Today progress did not include auto-linked focus minutes")

        refreshed_report = _expect(
            client.get(f"/api/v1/reports/daily?report_date={plan_date}", headers=headers),
            200,
            "get report after focus",
        )
        if refreshed_report["id"] != stale_report["id"]:
            raise RuntimeError("Daily Report auto refresh should update the same report")
        if refreshed_report["focus_minutes"] < 17 or refreshed_report["completed_task_count"] < 1:
            raise RuntimeError("Daily Report GET did not auto-refresh execution metrics")

        payload = build_mainline_state_payload(
            user_id=registered["user"]["id"],
            goal_id=goal["id"],
            prerequisite_task_id=prerequisite["id"],
            dependent_task_id=dependent["id"],
            capture_id=capture["capture"]["id"],
            inbox_item_id=inbox_item_id,
            captured_task_id=capture_task_id,
            daily_plan_id=after_focus_today["daily_plan_id"],
            initial_plan_version=initial_version,
            dependency_plan_version=after_dependency_today["plan_version"],
            confirm_plan_version=confirm_impact["plan_version"],
            priority_plan_version=priority_impact["plan_version"],
            final_plan_version=after_focus_today["plan_version"],
            focus_session_id=focus["id"],
            daily_report_id=refreshed_report["id"],
            report_focus_minutes=refreshed_report["focus_minutes"],
            report_completed_task_count=refreshed_report["completed_task_count"],
            strategy_user_adjusted_count=strategy["factors"]["user_adjusted_count"],
            strategy_dependency_protected_count=strategy["factors"]["dependency_protected_count"],
            focus_auto_linked=focus["daily_plan_item_id"] == priority_item["daily_plan_item_id"],
            report_reused=refreshed_report["id"] == stale_report["id"],
        )
        validate_mainline_state_payload(payload)
        return payload
    finally:
        settings.AUTH_MODE = original_auth_mode
        settings.ENVIRONMENT = original_environment


def build_mainline_state_payload(
    *,
    user_id: str,
    goal_id: str,
    prerequisite_task_id: str,
    dependent_task_id: str,
    capture_id: str,
    inbox_item_id: str,
    captured_task_id: str,
    daily_plan_id: str,
    initial_plan_version: int,
    dependency_plan_version: int,
    confirm_plan_version: int,
    priority_plan_version: int,
    final_plan_version: int,
    focus_session_id: str,
    daily_report_id: str,
    report_focus_minutes: int,
    report_completed_task_count: int,
    strategy_user_adjusted_count: int,
    strategy_dependency_protected_count: int,
    focus_auto_linked: bool,
    report_reused: bool,
) -> dict[str, Any]:
    return {
        "status": "ok",
        "scenario": "mainline_state_consistency",
        "user_id": user_id,
        "entities": {
            "goal_id": goal_id,
            "prerequisite_task_id": prerequisite_task_id,
            "dependent_task_id": dependent_task_id,
            "capture_id": capture_id,
            "inbox_item_id": inbox_item_id,
            "captured_task_id": captured_task_id,
            "daily_plan_id": daily_plan_id,
            "focus_session_id": focus_session_id,
            "daily_report_id": daily_report_id,
        },
        "today_versions": {
            "initial": initial_plan_version,
            "after_dependency": dependency_plan_version,
            "after_inbox_confirm": confirm_plan_version,
            "after_priority_adjustment": priority_plan_version,
            "final": final_plan_version,
        },
        "state_checks": {
            "dependency_refresh": dependency_plan_version > initial_plan_version,
            "inbox_confirm_refresh": confirm_plan_version > dependency_plan_version,
            "priority_adjustment_refresh": priority_plan_version > confirm_plan_version,
            "focus_did_not_replan_today": final_plan_version == priority_plan_version,
            "focus_auto_linked": focus_auto_linked,
            "report_reused_on_auto_refresh": report_reused,
            "report_has_focus_minutes": report_focus_minutes >= 17,
            "report_has_completed_task": report_completed_task_count >= 1,
            "strategy_has_user_adjustment": strategy_user_adjusted_count >= 1,
            "strategy_has_dependency_protection": strategy_dependency_protected_count >= 1,
        },
    }


def validate_mainline_state_payload(payload: dict[str, Any]) -> None:
    failed = [key for key, passed in payload.get("state_checks", {}).items() if not passed]
    if payload.get("status") != "ok" or payload.get("scenario") != "mainline_state_consistency" or failed:
        raise RuntimeError(
            "mainline state consistency smoke failed: "
            + json.dumps({"status": payload.get("status"), "scenario": payload.get("scenario"), "failed": failed})
        )


def _expect(response, status_code: int, label: str) -> dict[str, Any]:
    if response.status_code != status_code:
        raise RuntimeError(
            f"{label} failed: expected {status_code}, got {response.status_code}, body={response.text}"
        )
    return response.json()


def _find_today_item(today: dict[str, Any], *, task_id: str) -> dict[str, Any] | None:
    for item in _flatten_today_items(today):
        if item["task_id"] == task_id:
            return item
    return None


def _assert_task_order(today: dict[str, Any], *, before_task_id: str, after_task_id: str, label: str) -> None:
    positions = {item["task_id"]: index for index, item in enumerate(_flatten_today_items(today))}
    before_position = positions.get(before_task_id)
    after_position = positions.get(after_task_id)
    if before_position is None or after_position is None or before_position >= after_position:
        raise RuntimeError(
            f"{label} failed: expected {before_task_id} before {after_task_id}, positions={positions}"
        )


def _flatten_today_items(today: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for section_name in ("pinned_tasks", "recommended_tasks", "low_priority_tasks", "rolled_over_tasks"):
        items.extend(today["sections"][section_name])
    return sorted(
        items,
        key=lambda item: (
            _section_rank(str(item["section"])),
            item["sort_order"],
            item["title"],
        ),
    )


def _section_rank(section: str) -> int:
    return {
        "pinned": 0,
        "recommended": 1,
        "low_priority": 2,
        "rolled_over": 3,
    }.get(section, 99)


def main() -> None:
    suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    parser = argparse.ArgumentParser(description="Run the Chronos mainline state consistency smoke test.")
    parser.add_argument("--email", default=f"mainline-state-smoke+{suffix}@chronos.local")
    parser.add_argument("--password", default=f"mainline-state-password-{suffix}")
    parser.add_argument("--name", default="Chronos Mainline State Smoke")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    args = parser.parse_args()

    result = run_smoke(email=args.email, password=args.password, name=args.name, timezone=args.timezone)
    print("Chronos mainline state consistency smoke passed.")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
