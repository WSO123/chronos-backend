from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from time import perf_counter
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.ai.agents.daily_planner import DailyPlannerAgent
from app.ai.providers.base import LLMProviderError
from app.ai.providers.guard import validate_real_llm_request
from app.ai.providers.registry import llm_provider_registry
from app.core.config import settings


EXPECTED_TASK_IDS = ["manual-smoke-task-1", "manual-smoke-task-2"]


class SmokeValidationError(RuntimeError):
    def __init__(self, message: str, *, payload: dict[str, Any]) -> None:
        super().__init__(message)
        self.payload = payload


def main() -> None:
    args = _parse_args()
    try:
        result = run_smoke(allow_real_llm=args.allow_real_llm)
    except SmokeValidationError as exc:
        print(json.dumps(exc.payload, ensure_ascii=False, indent=2, default=str), flush=True)
        raise SystemExit(1) from exc
    except Exception as exc:  # noqa: BLE001 - smoke scripts should print a compact failure payload.
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2), flush=True)
        raise SystemExit(1) from exc
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str), flush=True)


def run_smoke(*, allow_real_llm: bool) -> dict[str, Any]:
    if not allow_real_llm:
        return {
            "status": "skipped",
            "reason": "Pass --allow-real-llm with AI_ENABLE_REAL_LLM=true and LLM_API_KEY to call a real provider.",
        }
    _validate_real_llm_config()

    agent = DailyPlannerAgent()
    provider = llm_provider_registry.current_provider()
    started = perf_counter()
    result = agent.run(
        plan_context={
            "plan_date": "2026-05-17",
            "daily_plan_id": "manual-smoke-daily-plan",
            "plan_revision_id": "manual-smoke-revision",
        },
        candidates=[
            {
                "task_id": EXPECTED_TASK_IDS[0],
                "title": "Protect the high-value writing block",
                "section": "pinned",
                "sort_order": 1,
                "recommendation_reason": "This is the most valuable task and fits the current capacity.",
                "estimated_duration_min": 45,
                "score_breakdown": {"total_score": 92, "value_score": 30, "priority_score": 18},
            },
            {
                "task_id": EXPECTED_TASK_IDS[1],
                "title": "Clear a small admin follow-up",
                "section": "recommended",
                "sort_order": 2,
                "recommendation_reason": "This keeps momentum without overloading the plan.",
                "estimated_duration_min": 20,
                "score_breakdown": {"total_score": 64, "duration_fit_score": 10, "priority_score": 10},
            },
        ],
        strategy_seed={
            "mode": "normal",
            "summary": "Start with the protected writing block, then clear one small follow-up.",
            "primary_reason": "The plan keeps the high-value task protected while staying realistic.",
            "score_factors": {
                "task_count": 2,
                "daily_capacity_minutes": 150,
                "selected_estimated_minutes": 65,
                "capacity_status": "within_capacity",
            },
        },
        provider=provider,
    )
    latency_ms = max(0, int((perf_counter() - started) * 1000))
    output_task_ids = [item.task_id for item in result.output.items]
    task_id_summary = task_id_preservation_summary(expected=EXPECTED_TASK_IDS, actual=output_task_ids)
    payload = {
        "status": "ok",
        "provider": result.provider,
        "model": result.model,
        "prompt_version": result.prompt_version,
        "prompt_checksum": result.prompt_checksum,
        "latency_ms": latency_ms,
        "mode": result.output.mode,
        "confidence": result.output.confidence,
        "item_count": len(result.output.items),
        "usage": result.usage,
        "provider_response_id": result.response_id,
        **task_id_summary,
    }
    if not task_id_summary["task_ids_preserved"]:
        raise SmokeValidationError(
            "LLM provider returned unexpected task ids.",
            payload={**payload, "status": "failed", "error": "LLM provider returned unexpected task ids."},
        )
    return payload


def task_id_preservation_summary(*, expected: list[str], actual: list[str]) -> dict[str, Any]:
    missing_task_ids = [task_id for task_id in expected if task_id not in actual]
    unexpected_task_ids = [task_id for task_id in actual if task_id not in expected]
    return {
        "expected_task_ids": expected,
        "output_task_ids": actual,
        "task_ids_preserved": actual == expected,
        "task_id_set_preserved": set(actual) == set(expected),
        "task_count_preserved": len(actual) == len(expected),
        "missing_task_ids": missing_task_ids,
        "unexpected_task_ids": unexpected_task_ids,
    }


def _validate_real_llm_config() -> None:
    if not settings.AI_ENABLE_REAL_LLM:
        raise RuntimeError("AI_ENABLE_REAL_LLM must be true for real provider smoke.")
    if settings.LLM_PROVIDER not in {"openai", "openai-compatible"}:
        raise RuntimeError("LLM_PROVIDER must be openai or openai-compatible for this smoke.")
    if not settings.LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY is required for real provider smoke.")
    if not settings.LLM_MODEL or settings.LLM_MODEL == "structured-mock-v1":
        raise RuntimeError("LLM_MODEL must be set to a real provider model.")
    try:
        validate_real_llm_request(settings.LLM_PROVIDER, settings.LLM_MODEL)
    except LLMProviderError as exc:
        raise RuntimeError(str(exc)) from exc


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manually smoke test a real LLM provider.")
    parser.add_argument(
        "--allow-real-llm",
        action="store_true",
        help="Actually call the configured real provider. Without this flag the script exits as skipped.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
