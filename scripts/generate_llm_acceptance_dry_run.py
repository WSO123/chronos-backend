from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.ai.prompts import prompt_registry
from scripts.generate_llm_acceptance_record import generate_acceptance_markdown


DEFAULT_JSON_DIR = Path("/tmp/chronos-llm-acceptance-dry-run")
DEFAULT_OUTPUT = DEFAULT_JSON_DIR / "dry-run-openai-gpt-4-1-mini-daily-planner.md"


def build_dry_run_payloads() -> dict[str, dict[str, Any]]:
    prompt = prompt_registry.get("daily_planner")
    return {
        "smoke": {
            "status": "ok",
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "prompt_version": prompt.version,
            "prompt_checksum": prompt.checksum,
            "latency_ms": 820,
            "mode": "normal",
            "confidence": 0.82,
            "item_count": 2,
            "expected_task_ids": ["manual-smoke-task-1", "manual-smoke-task-2"],
            "output_task_ids": ["manual-smoke-task-1", "manual-smoke-task-2"],
            "task_ids_preserved": True,
            "task_id_set_preserved": True,
            "task_count_preserved": True,
            "missing_task_ids": [],
            "unexpected_task_ids": [],
            "usage": {
                "input_tokens": 420,
                "output_tokens": 140,
                "total_tokens": 560,
                "cost_usd": 0.0021,
            },
            "provider_response_id": "dry-run-response-id",
        },
        "fallback": {
            "status": "ok",
            "scenario": "daily_planner_provider_failure",
            "fallback_verified": True,
            "today_available": True,
            "planning_engine_used": True,
            "daily_plan_id": "dry-run-daily-plan",
            "ai_job_id": "dry-run-ai-job",
            "planner_agent_status": "succeeded_with_fallback",
            "planner_agent_provider": "openai",
            "planner_agent_model": "gpt-4.1-mini",
            "planner_agent_failure_type": "provider_error",
            "planner_agent_output_applied": False,
            "fallback_reason": "daily_planner_agent_failed",
            "fallback_error_type": "LLMProviderError",
            "fallback_root_error_type": "LLMProviderError",
            "provider_observability_version": "v1",
            "latency_ms": 3,
            "task_count": 1,
            "task_titles": ["Fallback protected task"],
        },
        "compare": {
            "comparison_version": "p2-planner-eval-compare-v1",
            "status": "ok",
            "baseline": {"run_id": "dry-run-baseline"},
            "candidate": {"run_id": "dry-run-candidate"},
            "missing_in_candidate": [],
            "added_in_candidate": [],
            "regression_count": 0,
            "improvement_count": 0,
            "changed_count": 0,
            "regressions": [],
            "improvements": [],
            "scenario_diffs": [],
        },
        "policy": {
            "check_version": "p2-planner-eval-policy-check-v1",
            "status": "ok",
            "policy": {
                "policy_version": "p2-planner-eval-policy-v1",
                "evaluator_version": "p2-planning-engine-eval-v3",
                "required_scenario_count": 9,
            },
            "eval_run": {
                "run_id": "dry-run-candidate",
                "evaluator_version": "p2-planning-engine-eval-v3",
                "scenario_count": 9,
            },
            "regression_count": 0,
            "change_count": 0,
            "regression_issues": [],
            "change_issues": [],
        },
    }


def generate_dry_run(
    *,
    json_dir: Path = DEFAULT_JSON_DIR,
    output: Path = DEFAULT_OUTPUT,
    record_date: str | None = None,
) -> dict[str, str]:
    payloads = build_dry_run_payloads()
    json_dir.mkdir(parents=True, exist_ok=True)
    json_paths = {
        name: json_dir / f"{name}.json"
        for name in ("smoke", "fallback", "compare", "policy")
    }
    for name, path in json_paths.items():
        path.write_text(json.dumps(payloads[name], ensure_ascii=False, indent=2), encoding="utf-8")

    markdown = generate_acceptance_markdown(
        smoke=payloads["smoke"],
        fallback=payloads["fallback"],
        compare=payloads["compare"],
        policy=payloads["policy"],
        provider="openai",
        model="gpt-4.1-mini",
        purpose="daily-planner-provider-acceptance-dry-run",
        owner="Chronos dry-run",
        commit="dry-run",
        iteration="docs/iterations/2026-05-17-p2-llm-acceptance-dry-run.md",
        environment="dry-run / no network",
        base_url="dry-run / no provider call",
        record_date=record_date or date.today().isoformat(),
        notes="Dry-run generated from synthetic JSON. This is not a real provider acceptance record.",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8")

    return {
        "status": "ok",
        "output": str(output),
        "smoke_json": str(json_paths["smoke"]),
        "fallback_json": str(json_paths["fallback"]),
        "compare_json": str(json_paths["compare"]),
        "policy_json": str(json_paths["policy"]),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a synthetic LLM provider acceptance dry-run.")
    parser.add_argument("--json-dir", type=Path, default=DEFAULT_JSON_DIR, help="Directory for synthetic JSON files.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Markdown dry-run output path.")
    parser.add_argument("--date", default=None, help="Record date in YYYY-MM-DD. Defaults to today.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = generate_dry_run(json_dir=args.json_dir, output=args.output, record_date=args.date)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
