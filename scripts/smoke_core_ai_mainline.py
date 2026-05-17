from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any
import uuid

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.ai_job import AIJob
from app.models.enums import AIJobStatus, AIJobType
from main import app
from scripts.dev_seed_user import seed_user


EXPECTED_AI_JOB_TYPES = (
    AIJobType.CAPTURE_PARSER.value,
    AIJobType.DAILY_PLANNER.value,
    AIJobType.STRATEGY_EXPLANATION.value,
    AIJobType.TASK_BREAKDOWN.value,
    AIJobType.DAILY_REPORT_GENERATOR.value,
    AIJobType.INSIGHT_GENERATOR.value,
)
SUCCESSFUL_AI_JOB_STATUSES = {
    AIJobStatus.SUCCEEDED.value,
    AIJobStatus.SUCCEEDED_WITH_FALLBACK.value,
}


def run_smoke(*, email: str, name: str, timezone: str) -> dict[str, Any]:
    user = seed_user(email=email, name=name, timezone=timezone)
    headers = {"X-User-Id": str(user.id)}
    client = TestClient(app)
    now = datetime.now(UTC)
    suffix = now.strftime("%Y%m%d%H%M%S")
    plan_date = now.date()

    capture = _expect(
        client.post(
            "/api/v1/captures",
            json={
                "raw_text": (
                    f"todo Prepare Chronos core AI mainline smoke {suffix}. "
                    "Need 35 minutes, high priority, finish today."
                )
            },
            headers=headers,
        ),
        201,
        "create capture through Capture Parser Agent",
    )
    inbox_item_id = capture["inbox_item"]["id"]

    confirmed = _expect(
        client.post(f"/api/v1/inbox/{inbox_item_id}/confirm", headers=headers),
        200,
        "confirm inbox item into task",
    )
    task_id = confirmed["result_entity_id"]

    today = _expect(
        client.get(f"/api/v1/today?plan_date={plan_date.isoformat()}", headers=headers),
        200,
        "get Today plan",
    )
    today_item = _find_today_item(today, task_id=task_id)
    if today_item is None:
        raise RuntimeError("confirmed capture task was not present in Today plan")
    if not today.get("insights_preview"):
        raise RuntimeError("Today response did not include insights preview")

    strategy = _expect(
        client.get(f"/api/v1/today/strategy?plan_date={plan_date.isoformat()}", headers=headers),
        200,
        "get Strategy Detail with explanation agents",
    )
    if not strategy["source"].get("ai_job_id"):
        raise RuntimeError("Strategy Detail did not expose Daily Planner AI job id")
    if not strategy["source"].get("explanation_ai_job_id"):
        raise RuntimeError("Strategy Detail did not expose Strategy Explanation AI job id")
    if not strategy.get("planner_review"):
        raise RuntimeError("Strategy Detail did not include Daily Planner review")

    breakdown = _expect(
        client.post(f"/api/v1/tasks/{task_id}/breakdown", headers=headers),
        200,
        "break down task through Task Breakdown Agent",
    )
    if not breakdown["created_steps"]:
        raise RuntimeError("Task Breakdown Agent did not create editable steps for a new task")

    task_detail = _expect(client.get(f"/api/v1/tasks/{task_id}", headers=headers), 200, "get task detail")
    if not task_detail["steps"]:
        raise RuntimeError("Task Detail did not include generated steps")

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
        "start focus session",
    )
    finished_focus = _expect(
        client.post(
            f"/api/v1/focus-sessions/{focus['id']}/complete",
            json={"actual_duration_min": 18},
            headers=headers,
        ),
        200,
        "complete focus session",
    )
    if finished_focus["status"] != "completed":
        raise RuntimeError(f"unexpected focus status: {finished_focus['status']}")

    report = _expect(
        client.post(f"/api/v1/reports/daily/generate?report_date={plan_date.isoformat()}", headers=headers),
        200,
        "generate Daily Report through Daily Report Agent",
    )
    if not report["ai_summary"] or not report["ai_suggestions"]:
        raise RuntimeError("Daily Report did not include agent-generated summary and suggestions")

    insight = _expect(
        client.get(f"/api/v1/insights/detail?anchor_date={plan_date.isoformat()}", headers=headers),
        200,
        "get Insight Detail through Insight Detail Agent",
    )
    if not insight["source"].get("ai_job_id"):
        raise RuntimeError("Insight Detail did not expose Insight Generator AI job id")

    ai_jobs = ai_job_summaries_for_mainline(
        user_id=user.id,
        inbox_item_id=inbox_item_id,
        strategy_source=strategy["source"],
        task_breakdown_ai_job_id=breakdown["ai_job"]["id"],
        daily_report_id=report["id"],
        insight_source=insight["source"],
    )
    validate_ai_job_statuses(ai_jobs)

    return build_core_ai_evidence_payload(
        user_id=str(user.id),
        capture_id=capture["capture"]["id"],
        inbox_item_id=inbox_item_id,
        task_id=task_id,
        daily_plan_id=today["daily_plan_id"],
        daily_plan_item_id=today_item["daily_plan_item_id"],
        focus_session_id=focus["id"],
        daily_report_id=report["id"],
        insight_anchor_date=insight["anchor_date"],
        strategy_source=strategy["source"],
        planner_review=strategy["planner_review"],
        ai_jobs=ai_jobs,
    )


def ai_job_summaries_for_mainline(
    *,
    user_id: uuid.UUID,
    inbox_item_id: str,
    strategy_source: dict[str, Any],
    task_breakdown_ai_job_id: str,
    daily_report_id: str,
    insight_source: dict[str, Any],
) -> dict[str, dict[str, Any] | None]:
    with SessionLocal() as db:
        return {
            AIJobType.CAPTURE_PARSER.value: ai_job_summary(
                _job_by_type_and_result(
                    db,
                    user_id=user_id,
                    job_type=AIJobType.CAPTURE_PARSER,
                    result_entity_id=inbox_item_id,
                )
            ),
            AIJobType.DAILY_PLANNER.value: ai_job_summary(
                _job_by_id(db, user_id=user_id, job_id=strategy_source.get("ai_job_id"))
            ),
            AIJobType.STRATEGY_EXPLANATION.value: ai_job_summary(
                _job_by_id(db, user_id=user_id, job_id=strategy_source.get("explanation_ai_job_id"))
            ),
            AIJobType.TASK_BREAKDOWN.value: ai_job_summary(
                _job_by_id(db, user_id=user_id, job_id=task_breakdown_ai_job_id)
            ),
            AIJobType.DAILY_REPORT_GENERATOR.value: ai_job_summary(
                _job_by_type_and_result(
                    db,
                    user_id=user_id,
                    job_type=AIJobType.DAILY_REPORT_GENERATOR,
                    result_entity_id=daily_report_id,
                )
            ),
            AIJobType.INSIGHT_GENERATOR.value: ai_job_summary(
                _job_by_id(db, user_id=user_id, job_id=insight_source.get("ai_job_id"))
            ),
        }


def ai_job_summary(job: AIJob | None) -> dict[str, Any] | None:
    if job is None:
        return None
    return {
        "id": str(job.id),
        "job_type": job.job_type.value,
        "status": job.status.value,
        "provider": job.provider,
        "model": job.model,
        "prompt_version": job.prompt_version,
        "latency_ms": job.latency_ms,
        "fallback_reason": job.job_metadata.get("fallback_reason") if job.job_metadata else None,
        "failure_type": job.job_metadata.get("failure_type") if job.job_metadata else None,
    }


def _job_by_id(db, *, user_id: uuid.UUID, job_id: str | None) -> AIJob | None:
    parsed_id = _parse_uuid(job_id)
    if parsed_id is None:
        return None
    return db.scalars(
        select(AIJob).where(
            AIJob.id == parsed_id,
            AIJob.user_id == user_id,
        )
    ).first()


def _job_by_type_and_result(
    db,
    *,
    user_id: uuid.UUID,
    job_type: AIJobType,
    result_entity_id: str,
) -> AIJob | None:
    parsed_result_id = _parse_uuid(result_entity_id)
    if parsed_result_id is None:
        return None
    return db.scalars(
        select(AIJob).where(
            AIJob.user_id == user_id,
            AIJob.job_type == job_type,
            AIJob.result_entity_id == parsed_result_id,
        )
    ).first()


def _parse_uuid(value: str | None) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def validate_ai_job_statuses(ai_jobs: dict[str, dict[str, Any] | None]) -> None:
    missing = [job_type for job_type in EXPECTED_AI_JOB_TYPES if ai_jobs.get(job_type) is None]
    failed = [
        {
            "job_type": job_type,
            "status": ai_jobs[job_type]["status"],
        }
        for job_type in EXPECTED_AI_JOB_TYPES
        if ai_jobs.get(job_type) is not None and ai_jobs[job_type]["status"] not in SUCCESSFUL_AI_JOB_STATUSES
    ]
    if missing or failed:
        raise RuntimeError(
            "core AI mainline did not complete successfully: "
            + json.dumps({"missing": missing, "failed": failed}, ensure_ascii=False, default=str)
        )


def build_core_ai_evidence_payload(
    *,
    user_id: str,
    capture_id: str,
    inbox_item_id: str,
    task_id: str,
    daily_plan_id: str,
    daily_plan_item_id: str,
    focus_session_id: str,
    daily_report_id: str,
    insight_anchor_date: str,
    strategy_source: dict[str, Any],
    planner_review: dict[str, Any],
    ai_jobs: dict[str, dict[str, Any] | None],
) -> dict[str, Any]:
    validate_ai_job_statuses(ai_jobs)
    return {
        "status": "ok",
        "scenario": "core_ai_mainline",
        "user_id": user_id,
        "entities": {
            "capture_id": capture_id,
            "inbox_item_id": inbox_item_id,
            "task_id": task_id,
            "daily_plan_id": daily_plan_id,
            "daily_plan_item_id": daily_plan_item_id,
            "focus_session_id": focus_session_id,
            "daily_report_id": daily_report_id,
            "insight_anchor_date": insight_anchor_date,
        },
        "strategy": {
            "daily_planner_ai_job_id": strategy_source.get("ai_job_id"),
            "strategy_explanation_ai_job_id": strategy_source.get("explanation_ai_job_id"),
            "planner_review_source": planner_review.get("source"),
            "planner_suggestion_count": len(planner_review.get("suggestions") or []),
        },
        "ai_jobs": ai_jobs,
        "all_ai_jobs_successful": True,
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
    parser = argparse.ArgumentParser(description="Run the Chronos core AI mainline smoke test.")
    parser.add_argument(
        "--email",
        default=f"smoke-ai-mainline+{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}@chronos.local",
    )
    parser.add_argument("--name", default="Chronos AI Mainline Smoke")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    args = parser.parse_args()

    result = run_smoke(email=args.email, name=args.name, timezone=args.timezone)
    print("Chronos core AI mainline smoke passed.")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
