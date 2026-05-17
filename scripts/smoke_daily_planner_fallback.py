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
from scripts.dev_seed_user import seed_user


def run_smoke(*, email: str, name: str, timezone: str) -> dict[str, Any]:
    original = {
        "AI_ENABLE_REAL_LLM": settings.AI_ENABLE_REAL_LLM,
        "LLM_PROVIDER": settings.LLM_PROVIDER,
        "LLM_MODEL": settings.LLM_MODEL,
        "LLM_API_KEY": settings.LLM_API_KEY,
        "LLM_ALLOWED_PROVIDERS": settings.LLM_ALLOWED_PROVIDERS,
        "LLM_ALLOWED_MODELS": settings.LLM_ALLOWED_MODELS,
    }
    try:
        settings.AI_ENABLE_REAL_LLM = True
        settings.LLM_PROVIDER = "openai"
        settings.LLM_MODEL = "gpt-4.1-mini"
        settings.LLM_API_KEY = None
        settings.LLM_ALLOWED_PROVIDERS = "openai"
        settings.LLM_ALLOWED_MODELS = "gpt-4.1-mini"
        return _run_provider_failure_smoke(email=email, name=name, timezone=timezone)
    finally:
        settings.AI_ENABLE_REAL_LLM = original["AI_ENABLE_REAL_LLM"]
        settings.LLM_PROVIDER = original["LLM_PROVIDER"]
        settings.LLM_MODEL = original["LLM_MODEL"]
        settings.LLM_API_KEY = original["LLM_API_KEY"]
        settings.LLM_ALLOWED_PROVIDERS = original["LLM_ALLOWED_PROVIDERS"]
        settings.LLM_ALLOWED_MODELS = original["LLM_ALLOWED_MODELS"]


def _run_provider_failure_smoke(*, email: str, name: str, timezone: str) -> dict[str, Any]:
    user = seed_user(email=email, name=name, timezone=timezone)
    headers = {"X-User-Id": str(user.id)}
    client = TestClient(app)
    suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    plan_date = datetime.now(UTC).date()

    task = _expect(
        client.post(
            "/api/v1/tasks",
            json={
                "title": f"LLM fallback smoke protected task {suffix}",
                "estimated_duration_min": 30,
                "priority": 1,
                "value_level": "high",
                "deadline": plan_date.isoformat(),
            },
            headers=headers,
        ),
        201,
        "create fallback smoke task",
    )
    strategy = _expect(
        client.get(f"/api/v1/today/strategy?plan_date={plan_date.isoformat()}", headers=headers),
        200,
        "get strategy detail with forced provider failure",
    )
    ai_job_id = strategy["source"]["ai_job_id"]
    ai_job = _expect(
        client.get(f"/api/v1/ai-jobs/{ai_job_id}", headers=headers),
        200,
        "get fallback planner AI job",
    )
    payload = fallback_evidence_payload(
        user_id=str(user.id),
        task_id=task["id"],
        strategy=strategy,
        ai_job=ai_job,
    )
    if not payload["fallback_verified"]:
        raise RuntimeError(f"fallback smoke failed: {json.dumps(payload, ensure_ascii=False, default=str)}")
    return payload


def fallback_evidence_payload(
    *,
    user_id: str,
    task_id: str,
    strategy: dict[str, Any],
    ai_job: dict[str, Any],
) -> dict[str, Any]:
    metadata = ai_job.get("job_metadata") or {}
    task_titles = [item.get("title") for item in strategy.get("task_rationales", [])]
    fallback_verified = (
        ai_job.get("status") == "succeeded_with_fallback"
        and metadata.get("output_applied") is False
        and metadata.get("fallback_reason") == "daily_planner_agent_failed"
        and metadata.get("failure_type") == "provider_error"
        and bool(strategy.get("daily_plan_id"))
        and strategy.get("source", {}).get("model_name") == "planning-engine-v1"
        and strategy.get("factors", {}).get("planner_agent_failure_type") == "provider_error"
        and bool(strategy.get("task_rationales"))
    )
    return {
        "status": "ok" if fallback_verified else "failed",
        "scenario": "daily_planner_provider_failure",
        "fallback_verified": fallback_verified,
        "today_available": bool(strategy.get("daily_plan_id")),
        "planning_engine_used": strategy.get("source", {}).get("model_name") == "planning-engine-v1",
        "user_id": user_id,
        "task_id": task_id,
        "daily_plan_id": strategy.get("daily_plan_id"),
        "ai_job_id": ai_job.get("id"),
        "planner_agent_status": ai_job.get("status"),
        "planner_agent_provider": ai_job.get("provider"),
        "planner_agent_model": ai_job.get("model"),
        "planner_agent_failure_type": metadata.get("failure_type"),
        "planner_agent_output_applied": metadata.get("output_applied"),
        "fallback_reason": metadata.get("fallback_reason"),
        "fallback_error_type": metadata.get("fallback_error_type"),
        "fallback_root_error_type": metadata.get("fallback_root_error_type"),
        "provider_observability_version": metadata.get("provider_observability_version"),
        "latency_ms": ai_job.get("latency_ms"),
        "task_count": len(strategy.get("task_rationales", [])),
        "task_titles": task_titles,
    }


def _expect(response, status_code: int, label: str) -> dict[str, Any]:
    if response.status_code != status_code:
        raise RuntimeError(
            f"{label} failed: expected {status_code}, got {response.status_code}, body={response.text}"
        )
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test Daily Planner fallback without calling a real LLM.")
    parser.add_argument(
        "--email",
        default=f"smoke-llm-fallback+{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}@chronos.local",
    )
    parser.add_argument("--name", default="Chronos LLM Fallback Smoke")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    args = parser.parse_args()

    result = run_smoke(email=args.email, name=args.name, timezone=args.timezone)
    print("Chronos LLM fallback smoke passed.")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
