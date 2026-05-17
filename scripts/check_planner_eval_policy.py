from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.compare_planner_eval_jsonl import load_eval_run

DEFAULT_POLICY_PATH = ROOT_DIR / "docs/planner-eval-baselines/p2-planning-engine-eval-v5.json"
CHECK_VERSION = "p2-planner-eval-policy-check-v1"


def load_policy(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        policy = json.load(file)
    if not isinstance(policy, dict):
        raise ValueError(f"Planner eval policy must be a JSON object: {path}")
    if not policy.get("policy_version"):
        raise ValueError(f"Planner eval policy is missing policy_version: {path}")
    return policy


def check_eval_policy(eval_run: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    required_scenarios = policy.get("required_scenarios") or []
    required_by_name = {scenario["name"]: scenario for scenario in required_scenarios}
    candidate_scenarios = eval_run["scenarios"]
    candidate_names = set(candidate_scenarios)
    required_names = set(required_by_name)

    regression_issues: list[dict[str, Any]] = []
    change_issues: list[dict[str, Any]] = []

    expected_evaluator_version = policy.get("evaluator_version")
    if expected_evaluator_version and eval_run.get("evaluator_version") != expected_evaluator_version:
        change_issues.append(
            _issue(
                "evaluator_version_changed",
                "Evaluator version differs from the active golden baseline policy.",
                expected=expected_evaluator_version,
                actual=eval_run.get("evaluator_version"),
            )
        )

    required_run_status = policy.get("required_run_status")
    if required_run_status and eval_run.get("status") != required_run_status:
        regression_issues.append(
            _issue(
                "run_status_not_ok",
                "Planner eval run status does not satisfy the policy.",
                expected=required_run_status,
                actual=eval_run.get("status"),
            )
        )

    missing_scenarios = sorted(required_names - candidate_names)
    for scenario_name in missing_scenarios:
        regression_issues.append(
            _issue(
                "required_scenario_missing",
                "Required planner eval scenario is missing.",
                scenario_name=scenario_name,
            )
        )

    additional_scenarios = sorted(candidate_names - required_names)
    if policy.get("exact_scenario_set", True):
        for scenario_name in additional_scenarios:
            change_issues.append(
                _issue(
                    "additional_scenario_present",
                    "Planner eval includes a scenario not yet recorded in the golden baseline policy.",
                    scenario_name=scenario_name,
                )
            )

    for scenario_name in sorted(required_names & candidate_names):
        scenario_policy = required_by_name[scenario_name]
        scenario_record = candidate_scenarios[scenario_name]
        if scenario_policy.get("must_pass", True) and scenario_record.get("passed") is not True:
            regression_issues.append(
                _issue(
                    "required_scenario_failed",
                    "Required planner eval scenario did not pass.",
                    scenario_name=scenario_name,
                    actual=scenario_record.get("failures") or [],
                )
            )
        regression_issues.extend(_detail_field_issues(scenario_name, scenario_record, policy))

    status = "ok"
    if regression_issues:
        status = "regressed"
    elif change_issues:
        status = "changed"

    return {
        "check_version": CHECK_VERSION,
        "status": status,
        "policy": {
            "path": str(policy.get("_path") or ""),
            "policy_version": policy.get("policy_version"),
            "evaluator_version": policy.get("evaluator_version"),
            "required_scenario_count": len(required_scenarios),
        },
        "eval_run": {
            "path": eval_run["path"],
            "run_id": eval_run["run_id"],
            "evaluator_version": eval_run["evaluator_version"],
            "status": eval_run["status"],
            "scenario_count": eval_run["scenario_count"],
        },
        "regression_count": len(regression_issues),
        "change_count": len(change_issues),
        "regression_issues": regression_issues,
        "change_issues": change_issues,
    }


def _detail_field_issues(
    scenario_name: str,
    scenario_record: dict[str, Any],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    details = scenario_record.get("details") or {}
    for field in policy.get("required_detail_fields") or []:
        if field not in details:
            issues.append(
                _issue(
                    "required_detail_missing",
                    "Required scenario detail field is missing.",
                    scenario_name=scenario_name,
                    field=field,
                )
            )

    required_item_signal_fields = policy.get("required_item_signal_fields") or []
    item_signals = details.get("item_signals") or []
    if required_item_signal_fields and not item_signals:
        issues.append(
            _issue(
                "required_item_signals_missing",
                "Scenario item signals are required for planner explainability.",
                scenario_name=scenario_name,
            )
        )
        return issues

    for item in item_signals:
        title = item.get("title")
        for field in required_item_signal_fields:
            if field not in item:
                issues.append(
                    _issue(
                        "required_item_signal_missing",
                        "Required item signal field is missing.",
                        scenario_name=scenario_name,
                        title=title,
                        field=field,
                    )
                )
    return issues


def _issue(code: str, message: str, **extra: Any) -> dict[str, Any]:
    payload = {"code": code, "message": message}
    payload.update(extra)
    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check a Chronos planner eval JSONL run against a golden policy.")
    parser.add_argument("eval_jsonl", type=Path, help="Planner eval JSONL path.")
    parser.add_argument("--run-id", default=None, help="Run id to read from the eval JSONL. Defaults to latest.")
    parser.add_argument(
        "--policy-file",
        type=Path,
        default=DEFAULT_POLICY_PATH,
        help="Planner eval policy manifest path.",
    )
    parser.add_argument(
        "--fail-on-changed",
        action="store_true",
        help="Exit with code 1 when policy status is changed, not only regressed.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        policy = load_policy(args.policy_file)
        policy["_path"] = str(args.policy_file)
        eval_run = load_eval_run(args.eval_jsonl, run_id=args.run_id)
        result = check_eval_policy(eval_run, policy)
    except Exception as exc:  # noqa: BLE001 - CLI should emit compact JSON for shell workflows.
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2), flush=True)
        raise SystemExit(2) from exc

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str), flush=True)
    if result["status"] == "regressed" or (args.fail_on_changed and result["status"] == "changed"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
