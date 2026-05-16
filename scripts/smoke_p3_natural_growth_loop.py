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
from app.workers.tasks import dispatch_due_reminders, generate_execution_reminders, sync_health_energy_connection


def run_smoke(*, email: str, name: str, timezone: str) -> dict[str, Any]:
    user = seed_user(email=email, name=name, timezone=timezone)
    headers = {"X-User-Id": str(user.id)}
    client = TestClient(app)
    now = datetime.now(UTC)
    suffix = now.strftime("%Y%m%d%H%M%S")
    plan_date = now.date()

    settings = _expect(
        client.patch(
            "/api/v1/me/settings",
            json={
                "notification_enabled": True,
                "reminder_execution_enabled": True,
                "reminder_deadline_enabled": True,
                "reminder_channel_in_app_enabled": True,
                "execution_reminder_limit": 1,
                "execution_reminder_start_hour": 0,
                "execution_reminder_spacing_minutes": 15,
            },
            headers=headers,
        ),
        200,
        "update reminder settings",
    )
    if settings["execution_reminder_limit"] != 1:
        raise RuntimeError("settings did not update execution reminder limit")

    health_connection = _expect(
        client.put(
            "/api/v1/data-sources/health/apple_health",
            json={
                "external_account_label": "Chronos P3 Smoke Health",
                "sync_enabled": True,
                "connection_metadata": {
                    "fake_energy_metrics": [
                        {
                            "external_metric_id": f"p3-smoke-health-{suffix}",
                            "metric_date": plan_date.isoformat(),
                            "sleep_minutes": 390,
                            "sleep_quality_score": 68,
                            "stress_score": 42,
                            "energy_score": 64,
                        }
                    ],
                    "fake_next_cursor": f"p3-smoke-health-cursor-{suffix}",
                },
            },
            headers=headers,
        ),
        200,
        "connect health source",
    )
    health_sync = sync_health_energy_connection.run(
        health_connection["id"],
        end_date=plan_date.isoformat(),
        days=1,
    )
    if health_sync["status"] != "synced" or health_sync["imported_count"] != 1:
        raise RuntimeError(f"health sync did not import one metric: {health_sync}")

    dashboard = _expect(
        client.get(
            f"/api/v1/energy/dashboard?end_date={plan_date.isoformat()}&days=1",
            headers=headers,
        ),
        200,
        "get energy dashboard",
    )
    if not dashboard["trends"][0]["has_data"]:
        raise RuntimeError("energy dashboard did not include the smoke metric")
    sync_summary_after_health = _expect(
        client.get("/api/v1/data-sources/sync-summary", headers=headers),
        200,
        "get sync summary after health sync",
    )
    if sync_summary_after_health["connected_count"] != 1 or sync_summary_after_health["attention_count"] != 0:
        raise RuntimeError(f"unexpected sync summary after health sync: {sync_summary_after_health}")

    calendar_connection = _expect(
        client.put(
            "/api/v1/data-sources/calendar/google_calendar",
            json={
                "external_account_label": "chronos-p3-smoke@example.com",
                "sync_enabled": True,
                "connection_metadata": {"origin": "p3_smoke"},
            },
            headers=headers,
        ),
        200,
        "connect calendar source",
    )
    imported = _expect(
        client.post(
            "/api/v1/captures/external-imports",
            json={
                "data_source_connection_id": calendar_connection["id"],
                "external_item_id": f"p3-smoke-calendar-{suffix}",
                "external_item_type": "calendar_event",
                "title": f"P3 smoke execution task {suffix}",
                "body": "Imported from a calendar source, then confirmed into Today.",
                "occurred_at": now.isoformat(),
                "external_payload": {"smoke": True},
            },
            headers=headers,
        ),
        200,
        "import calendar capture",
    )
    if not imported["created"]:
        raise RuntimeError("calendar import reused an existing record unexpectedly")
    edited_inbox = _expect(
        client.patch(
            f"/api/v1/inbox/{imported['inbox_item']['id']}",
            json={
                "item_type": "task",
                "title": f"P3 smoke execution task {suffix}",
                "suggested_priority": 1,
                "suggested_deadline": plan_date.isoformat(),
            },
            headers=headers,
        ),
        200,
        "classify imported inbox item as task",
    )
    if edited_inbox["item_type"] != "task":
        raise RuntimeError("imported inbox item was not classified as task")
    confirmed = _expect(
        client.post(
            f"/api/v1/inbox/{imported['inbox_item']['id']}/confirm",
            headers=headers,
        ),
        200,
        "confirm imported inbox item",
    )
    task_id = confirmed["result_entity_id"]
    task_detail = _expect(
        client.get(f"/api/v1/tasks/{task_id}", headers=headers),
        200,
        "get imported task detail",
    )
    source_context = task_detail["source_context"]
    if task_detail["source"] != "calendar" or source_context["provider"] != "google_calendar":
        raise RuntimeError("imported task did not preserve calendar source context")

    today = _expect(
        client.get(f"/api/v1/today?plan_date={plan_date.isoformat()}", headers=headers),
        200,
        "create/read today plan",
    )
    if _find_today_item(today, task_id=task_id) is None:
        raise RuntimeError("P3 smoke task was not present in Today")
    sync_summary = _expect(
        client.get("/api/v1/data-sources/sync-summary", headers=headers),
        200,
        "get data source sync summary",
    )
    if sync_summary["connected_count"] != 2 or sync_summary["attention_count"] != 0:
        raise RuntimeError(f"unexpected data source sync summary: {sync_summary}")

    execution_reminders = generate_execution_reminders.run(
        user_id=str(user.id),
        plan_date=plan_date.isoformat(),
        limit=1,
        start_hour=0,
        spacing_minutes=15,
    )
    if execution_reminders["created_count"] < 1:
        raise RuntimeError(f"execution generator did not create a reminder: {execution_reminders}")

    summary = _expect(
        client.get(
            "/api/v1/reminders/summary",
            params={"now": now.isoformat()},
            headers=headers,
        ),
        200,
        "get reminder summary",
    )
    if summary["pending_count"] < 1 or summary["unseen_count"] < 1:
        raise RuntimeError("reminder summary did not show pending unseen reminders")
    reminder_id = summary["next_reminder"]["id"]

    batch_seen = _expect(
        client.post(
            "/api/v1/reminders/seen",
            json={"reminder_ids": [reminder_id]},
            headers=headers,
        ),
        200,
        "batch mark reminder seen",
    )
    if batch_seen["updated_count"] != 1:
        raise RuntimeError("batch seen did not update one reminder")

    dispatch = dispatch_due_reminders.run(limit=10, channel="in_app", now=now.isoformat())
    if dispatch["sent_count"] < 1:
        raise RuntimeError(f"dispatch did not send the in-app reminder: {dispatch}")
    sent_reminders = _expect(
        client.get("/api/v1/reminders?status=sent", headers=headers),
        200,
        "list sent reminders",
    )
    if not any(reminder["id"] == reminder_id for reminder in sent_reminders["reminders"]):
        raise RuntimeError("dispatch did not move the smoke reminder to sent")

    scheduler_plan = _expect(
        client.get("/api/v1/scheduler/reminders", headers=headers),
        200,
        "get reminder scheduler plan",
    )
    beat_proposal = _expect(
        client.get("/api/v1/scheduler/reminders/celery-beat", headers=headers),
        200,
        "get celery beat proposal",
    )
    data_source_scheduler_plan = _expect(
        client.get("/api/v1/scheduler/data-sources", headers=headers),
        200,
        "get data source scheduler plan",
    )
    data_source_beat_proposal = _expect(
        client.get("/api/v1/scheduler/data-sources/celery-beat", headers=headers),
        200,
        "get data source celery beat proposal",
    )
    scheduler_overview = _expect(
        client.get("/api/v1/scheduler/overview", headers=headers),
        200,
        "get scheduler overview",
    )
    expected_scheduler_tasks = {
        "reminder.generate_deadline",
        "reminder.generate_execution_for_active_users",
        "reminder.dispatch_due",
        "reminder.cleanup_delivery_attempts",
    }
    scheduler_tasks = {entry["task_name"] for entry in scheduler_plan["entries"]}
    beat_tasks = {entry["task"] for entry in beat_proposal["entries"]}
    if not expected_scheduler_tasks.issubset(scheduler_tasks):
        raise RuntimeError(f"scheduler plan missing entries: {expected_scheduler_tasks - scheduler_tasks}")
    if not expected_scheduler_tasks.issubset(beat_tasks):
        raise RuntimeError(f"beat proposal missing entries: {expected_scheduler_tasks - beat_tasks}")
    expected_data_source_tasks = {
        "data_source.sync_ready_connections",
        "health.sync_ready_energy_connections",
    }
    data_source_scheduler_tasks = {entry["task_name"] for entry in data_source_scheduler_plan["entries"]}
    data_source_beat_tasks = {entry["task"] for entry in data_source_beat_proposal["entries"]}
    if not expected_data_source_tasks.issubset(data_source_scheduler_tasks):
        missing = expected_data_source_tasks - data_source_scheduler_tasks
        raise RuntimeError(f"data source scheduler plan missing entries: {missing}")
    if not expected_data_source_tasks.issubset(data_source_beat_tasks):
        missing = expected_data_source_tasks - data_source_beat_tasks
        raise RuntimeError(f"data source beat proposal missing entries: {missing}")
    overview_domains = {domain["domain"]: domain for domain in scheduler_overview["domains"]}
    if set(overview_domains) != {"data_sources", "reminders"}:
        raise RuntimeError(f"scheduler overview returned unexpected domains: {overview_domains}")

    return {
        "status": "ok",
        "user_id": str(user.id),
        "health_connection_id": health_connection["id"],
        "health_sync_run_id": health_sync["sync_run_id"],
        "calendar_connection_id": calendar_connection["id"],
        "external_import_id": imported["import_record"]["id"],
        "inbox_item_id": imported["inbox_item"]["id"],
        "task_id": task_id,
        "daily_plan_id": today["daily_plan_id"],
        "data_source_attention_count": sync_summary["attention_count"],
        "execution_reminder_id": reminder_id,
        "execution_created_count": execution_reminders["created_count"],
        "summary_pending_count": summary["pending_count"],
        "batch_seen_updated_count": batch_seen["updated_count"],
        "dispatch_sent_count": dispatch["sent_count"],
        "scheduler_entries": sorted(scheduler_tasks),
        "beat_entries": sorted(beat_tasks),
        "data_source_scheduler_entries": sorted(data_source_scheduler_tasks),
        "data_source_beat_entries": sorted(data_source_beat_tasks),
        "scheduler_overview_domains": sorted(overview_domains),
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
    parser = argparse.ArgumentParser(description="Run the Chronos P3 natural growth smoke test against the local DB.")
    parser.add_argument(
        "--email",
        default=f"smoke-p3+{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}@chronos.local",
    )
    parser.add_argument("--name", default="Chronos P3 Smoke")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    args = parser.parse_args()

    result = run_smoke(email=args.email, name=args.name, timezone=args.timezone)
    print("Chronos P3 smoke passed.")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
