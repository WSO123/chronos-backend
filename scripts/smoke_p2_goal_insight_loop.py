from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
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
    now = datetime.now(UTC)
    suffix = now.strftime("%Y%m%d%H%M%S")
    plan_date = now.date()
    week_start = plan_date - timedelta(days=plan_date.weekday())

    goal = _expect(
        client.post(
            "/api/v1/goals",
            json={
                "title": f"P2 smoke goal {suffix}",
                "deadline": (plan_date + timedelta(days=14)).isoformat(),
                "value_level": "high",
            },
            headers=headers,
        ),
        201,
        "create goal",
    )
    goal_id = goal["id"]

    prerequisite = _expect(
        client.post(
            "/api/v1/tasks",
            json={
                "title": f"P2 smoke prerequisite {suffix}",
                "goal_id": goal_id,
                "estimated_duration_min": 35,
                "priority": 2,
                "value_level": "high",
                "deadline": plan_date.isoformat(),
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
                "title": f"P2 smoke dependent {suffix}",
                "goal_id": goal_id,
                "estimated_duration_min": 45,
                "priority": 4,
                "value_level": "medium",
                "deadline": (plan_date + timedelta(days=1)).isoformat(),
            },
            headers=headers,
        ),
        201,
        "create dependent task",
    )
    overdue = _expect(
        client.post(
            "/api/v1/tasks",
            json={
                "title": f"P2 smoke overdue {suffix}",
                "goal_id": goal_id,
                "estimated_duration_min": 25,
                "priority": 1,
                "value_level": "high",
                "deadline": (plan_date - timedelta(days=1)).isoformat(),
            },
            headers=headers,
        ),
        201,
        "create overdue task",
    )

    priority_adjustment = _expect(
        client.patch(
            f"/api/v1/tasks/{dependent['id']}/priority",
            json={"priority": 1, "value_level": "high", "reason": "P2 smoke priority correction"},
            headers=headers,
        ),
        200,
        "adjust task priority",
    )
    if priority_adjustment["current_priority"] != 1:
        raise RuntimeError("priority adjustment did not update priority")

    dependency = _expect(
        client.post(
            f"/api/v1/tasks/{dependent['id']}/dependencies",
            json={"prerequisite_task_id": prerequisite["id"], "reason": "P2 smoke dependency"},
            headers=headers,
        ),
        201,
        "create task dependency",
    )
    dependencies = _expect(
        client.get(f"/api/v1/tasks/{dependent['id']}/dependencies", headers=headers),
        200,
        "get task dependencies",
    )
    if not dependencies["prerequisites"] or dependency["id"] != dependencies["prerequisites"][0]["id"]:
        raise RuntimeError("dependency was not returned in prerequisites")

    today = _expect(
        client.get(f"/api/v1/today?plan_date={plan_date.isoformat()}", headers=headers),
        200,
        "get today",
    )
    if not today["insights_preview"]["risk_alerts"]:
        raise RuntimeError("today insights preview did not surface risk alerts")

    strategy = _expect(
        client.get(f"/api/v1/today/strategy?plan_date={plan_date.isoformat()}", headers=headers),
        200,
        "get strategy detail",
    )
    if strategy["daily_plan_id"] != today["daily_plan_id"]:
        raise RuntimeError("strategy detail did not use the current plan")

    today_item = _find_today_item(today, task_id=prerequisite["id"])
    if today_item is None:
        raise RuntimeError("prerequisite task was not present in Today")

    focus = _expect(
        client.post(
            "/api/v1/focus-sessions",
            json={
                "task_id": prerequisite["id"],
                "daily_plan_item_id": today_item["daily_plan_item_id"],
                "planned_duration_min": 25,
            },
            headers=headers,
        ),
        201,
        "start focus",
    )
    _expect(
        client.post(
            f"/api/v1/focus-sessions/{focus['id']}/complete",
            json={"actual_duration_min": 18},
            headers=headers,
        ),
        200,
        "complete focus",
    )

    goals_home = _expect(client.get("/api/v1/goals/home", headers=headers), 200, "get goals home")
    if goals_home["summary"]["total_goal_count"] < 1:
        raise RuntimeError("goals home did not include smoke goal")

    goal_detail = _expect(client.get(f"/api/v1/goals/{goal_id}/detail", headers=headers), 200, "get goal detail")
    if not goal_detail["dependency_map"]["edges"]:
        raise RuntimeError("goal detail did not include dependency edges")

    timeline = _expect(
        client.get(f"/api/v1/goals/{goal_id}/progress-timeline", headers=headers),
        200,
        "get goal progress timeline",
    )
    if not timeline["milestones"]:
        raise RuntimeError("goal progress timeline did not include milestones")

    weekly = _expect(
        client.get(f"/api/v1/reports/weekly?week_start={week_start.isoformat()}", headers=headers),
        200,
        "get weekly report",
    )
    monthly = _expect(
        client.get(f"/api/v1/reports/monthly?month={plan_date.isoformat()}", headers=headers),
        200,
        "get monthly report",
    )
    insight = _expect(
        client.get(f"/api/v1/insights/detail?anchor_date={plan_date.isoformat()}", headers=headers),
        200,
        "get insight detail",
    )
    me = _expect(
        client.get(f"/api/v1/me/overview?today={plan_date.isoformat()}", headers=headers),
        200,
        "get me overview",
    )

    return {
        "status": "ok",
        "user_id": str(user.id),
        "goal_id": goal_id,
        "completed_task_id": prerequisite["id"],
        "dependent_task_id": dependent["id"],
        "overdue_task_id": overdue["id"],
        "daily_plan_id": today["daily_plan_id"],
        "focus_session_id": focus["id"],
        "weekly_completed_task_count": weekly["summary"]["total_completed_task_count"],
        "monthly_completed_task_count": monthly["summary"]["total_completed_task_count"],
        "insight_recommendation_count": len(insight["recommendations"]),
        "me_insight_count": len(me["insights"]["highlights"]),
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
    parser = argparse.ArgumentParser(description="Run the Chronos P2 goal and insight smoke test.")
    parser.add_argument(
        "--email",
        default=f"smoke-p2+{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}@chronos.local",
    )
    parser.add_argument("--name", default="Chronos P2 Smoke")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    args = parser.parse_args()

    result = run_smoke(email=args.email, name=args.name, timezone=args.timezone)
    print("Chronos P2 smoke passed.")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
