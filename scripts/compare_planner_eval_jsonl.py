from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


COMPARISON_VERSION = "p2-planner-eval-compare-v1"
DETAIL_FIELDS = [
    "ordered_titles",
    "rolled_over_titles",
    "risk_keys",
    "capacity_status",
    "daily_capacity_minutes",
    "selected_estimated_minutes",
    "rolled_over_estimated_minutes",
    "over_capacity_minutes",
    "energy_applied",
    "planner_agent_status",
    "planner_agent_provider",
    "planner_agent_model",
    "planner_agent_prompt_version",
    "planner_agent_prompt_checksum",
    "planner_agent_failure_type",
    "planner_agent_output_applied",
]
ITEM_SIGNAL_FIELDS = [
    "section",
    "total_score",
    "goal_value_score",
    "goal_urgency_score",
    "behavior_feedback_score",
    "dependency_score",
    "user_preference_score",
]


def load_eval_run(path: Path, *, run_id: str | None = None) -> dict[str, Any]:
    records = _read_jsonl(path)
    runs: dict[str, dict[str, Any]] = {}
    run_order: list[str] = []
    for record in records:
        record_run_id = record.get("run_id")
        if not record_run_id:
            continue
        if record_run_id not in runs:
            runs[record_run_id] = {
                "run_id": record_run_id,
                "summary": None,
                "scenarios": {},
            }
            run_order.append(record_run_id)

        record_type = record.get("record_type")
        if record_type == "run_summary":
            runs[record_run_id]["summary"] = record
        elif record_type == "scenario_result" and record.get("scenario_name"):
            runs[record_run_id]["scenarios"][record["scenario_name"]] = record

    if not run_order:
        raise ValueError(f"No planner eval runs found in {path}")

    selected_run_id = run_id or run_order[-1]
    if selected_run_id not in runs:
        raise ValueError(f"Run id '{selected_run_id}' was not found in {path}")

    run = runs[selected_run_id]
    summary = run["summary"] or {}
    return {
        "path": str(path),
        "run_id": selected_run_id,
        "evaluator_version": summary.get("evaluator_version"),
        "status": summary.get("status"),
        "scenario_count": len(run["scenarios"]),
        "summary": summary,
        "scenarios": run["scenarios"],
    }


def compare_eval_runs(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    baseline_scenarios = baseline["scenarios"]
    candidate_scenarios = candidate["scenarios"]
    baseline_names = set(baseline_scenarios)
    candidate_names = set(candidate_scenarios)
    missing_in_candidate = sorted(baseline_names - candidate_names)
    added_in_candidate = sorted(candidate_names - baseline_names)

    scenario_diffs: list[dict[str, Any]] = []
    regressions: list[str] = []
    improvements: list[str] = []
    for scenario_name in sorted(baseline_names & candidate_names):
        baseline_record = baseline_scenarios[scenario_name]
        candidate_record = candidate_scenarios[scenario_name]
        diff = _scenario_diff(scenario_name, baseline_record, candidate_record)
        if baseline_record.get("passed") is True and candidate_record.get("passed") is False:
            regressions.append(scenario_name)
        if baseline_record.get("passed") is False and candidate_record.get("passed") is True:
            improvements.append(scenario_name)
        if diff["field_changes"] or diff["item_signal_changes"]:
            scenario_diffs.append(diff)

    status = "ok"
    if regressions or missing_in_candidate:
        status = "regressed"
    elif improvements or added_in_candidate or scenario_diffs:
        status = "changed"

    return {
        "comparison_version": COMPARISON_VERSION,
        "status": status,
        "baseline": _run_summary(baseline),
        "candidate": _run_summary(candidate),
        "missing_in_candidate": missing_in_candidate,
        "added_in_candidate": added_in_candidate,
        "regression_count": len(regressions) + len(missing_in_candidate),
        "improvement_count": len(improvements),
        "changed_count": len(scenario_diffs),
        "regressions": regressions,
        "improvements": improvements,
        "scenario_diffs": scenario_diffs,
    }


def _scenario_diff(name: str, baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    field_changes: list[dict[str, Any]] = []
    _add_change_if_needed(
        field_changes,
        "passed",
        baseline.get("passed"),
        candidate.get("passed"),
    )
    _add_change_if_needed(
        field_changes,
        "failures",
        baseline.get("failures") or [],
        candidate.get("failures") or [],
    )

    baseline_details = baseline.get("details") or {}
    candidate_details = candidate.get("details") or {}
    for field in DETAIL_FIELDS:
        _add_change_if_needed(field_changes, field, baseline_details.get(field), candidate_details.get(field))

    return {
        "scenario_name": name,
        "field_changes": field_changes,
        "item_signal_changes": _item_signal_changes(
            baseline_details.get("item_signals") or [],
            candidate_details.get("item_signals") or [],
        ),
    }


def _item_signal_changes(baseline_items: list[dict[str, Any]], candidate_items: list[dict[str, Any]]) -> list[dict]:
    baseline_by_title = {item.get("title"): item for item in baseline_items if item.get("title")}
    candidate_by_title = {item.get("title"): item for item in candidate_items if item.get("title")}
    changes: list[dict[str, Any]] = []

    for title in sorted(set(baseline_by_title) | set(candidate_by_title)):
        baseline_item = baseline_by_title.get(title)
        candidate_item = candidate_by_title.get(title)
        if baseline_item is None or candidate_item is None:
            changes.append(
                {
                    "title": title,
                    "field": "presence",
                    "baseline": "present" if baseline_item else "missing",
                    "candidate": "present" if candidate_item else "missing",
                }
            )
            continue
        for field in ITEM_SIGNAL_FIELDS:
            if baseline_item.get(field) != candidate_item.get(field):
                changes.append(
                    {
                        "title": title,
                        "field": field,
                        "baseline": baseline_item.get(field),
                        "candidate": candidate_item.get(field),
                    }
                )
    return changes


def _add_change_if_needed(changes: list[dict[str, Any]], field: str, baseline: Any, candidate: Any) -> None:
    if baseline == candidate:
        return
    changes.append({"field": field, "baseline": baseline, "candidate": candidate})


def _run_summary(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": run["path"],
        "run_id": run["run_id"],
        "evaluator_version": run["evaluator_version"],
        "status": run["status"],
        "scenario_count": run["scenario_count"],
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL record at {path}:{line_number}: {exc}") from exc
    return records


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two Chronos planner evaluation JSONL runs.")
    parser.add_argument("baseline", type=Path, help="Baseline planner eval JSONL path.")
    parser.add_argument("candidate", type=Path, help="Candidate planner eval JSONL path.")
    parser.add_argument("--baseline-run-id", default=None, help="Run id to read from the baseline JSONL.")
    parser.add_argument("--candidate-run-id", default=None, help="Run id to read from the candidate JSONL.")
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Exit with code 1 when candidate regresses or misses baseline scenarios.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        baseline = load_eval_run(args.baseline, run_id=args.baseline_run_id)
        candidate = load_eval_run(args.candidate, run_id=args.candidate_run_id)
        result = compare_eval_runs(baseline, candidate)
    except Exception as exc:  # noqa: BLE001 - CLI should print a compact error payload.
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2), flush=True)
        raise SystemExit(2) from exc

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str), flush=True)
    if args.fail_on_regression and result["status"] == "regressed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
