import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from scripts.check_planner_eval_policy import DEFAULT_POLICY_PATH, check_eval_policy, load_policy
from scripts.evaluate_planning_engine import EVALUATOR_VERSION


class PlannerEvalPolicyTests(unittest.TestCase):
    def test_bundled_policy_matches_current_evaluator_version(self):
        policy = load_policy(DEFAULT_POLICY_PATH)

        self.assertEqual(policy["evaluator_version"], EVALUATOR_VERSION)
        self.assertEqual(len(policy["required_scenarios"]), 12)
        self.assertTrue(policy["exact_scenario_set"])

    def test_policy_check_accepts_matching_run(self):
        policy = _policy("scenario_a", "scenario_b")
        result = check_eval_policy(_run("scenario_a", "scenario_b"), policy)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["regression_count"], 0)
        self.assertEqual(result["change_count"], 0)

    def test_policy_check_marks_missing_required_scenario_as_regression(self):
        policy = _policy("scenario_a", "scenario_b")
        result = check_eval_policy(_run("scenario_a"), policy)

        self.assertEqual(result["status"], "regressed")
        self.assertIn("required_scenario_missing", {issue["code"] for issue in result["regression_issues"]})

    def test_policy_check_marks_failed_required_scenario_as_regression(self):
        policy = _policy("scenario_a")
        result = check_eval_policy(_run("scenario_a", failed={"scenario_a"}), policy)

        self.assertEqual(result["status"], "regressed")
        self.assertIn("required_scenario_failed", {issue["code"] for issue in result["regression_issues"]})

    def test_policy_check_marks_extra_scenario_as_changed(self):
        policy = _policy("scenario_a")
        result = check_eval_policy(_run("scenario_a", "scenario_b"), policy)

        self.assertEqual(result["status"], "changed")
        self.assertIn("additional_scenario_present", {issue["code"] for issue in result["change_issues"]})

    def test_policy_check_requires_item_signal_fields(self):
        policy = _policy("scenario_a")
        run = _run("scenario_a")
        item = run["scenarios"]["scenario_a"]["details"]["item_signals"][0]
        item.pop("goal_urgency_score")

        result = check_eval_policy(run, policy)

        self.assertEqual(result["status"], "regressed")
        self.assertIn("required_item_signal_missing", {issue["code"] for issue in result["regression_issues"]})

    def test_policy_check_requires_non_empty_item_signals(self):
        policy = _policy("scenario_a")
        run = _run("scenario_a")
        run["scenarios"]["scenario_a"]["details"]["item_signals"] = []

        result = check_eval_policy(run, policy)

        self.assertEqual(result["status"], "regressed")
        self.assertIn("required_item_signals_missing", {issue["code"] for issue in result["regression_issues"]})

    def test_cli_fail_on_changed_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            policy_path = tmp_path / "policy.json"
            eval_path = tmp_path / "eval.jsonl"
            policy_path.write_text(json.dumps(_policy("scenario_a")), encoding="utf-8")
            _write_jsonl(eval_path, _records("scenario_a", "scenario_b"))

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/check_planner_eval_policy.py",
                    str(eval_path),
                    "--policy-file",
                    str(policy_path),
                    "--fail-on-changed",
                ],
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "changed")


def _policy(*scenario_names: str) -> dict:
    return {
        "policy_version": "test-policy-v1",
        "evaluator_version": EVALUATOR_VERSION,
        "required_run_status": "ok",
        "exact_scenario_set": True,
        "required_detail_fields": [
            "ordered_titles",
            "capacity_status",
            "planner_agent_provider",
            "score_explanation_summary",
            "score_explanation_signal_keys",
            "item_signals",
        ],
        "required_item_signal_fields": [
            "section",
            "score_version",
            "score_band",
            "total_score",
            "goal_value_score",
            "goal_urgency_score",
            "goal_progress_score",
            "goal_progress_completion_rate",
            "behavior_feedback_score",
            "personalization_score",
            "personalization_sample_count",
            "dependency_score",
            "user_preference_score",
            "dominant_factor",
            "dominant_reason",
            "score_signal_keys",
        ],
        "required_scenarios": [{"name": name, "must_pass": True} for name in scenario_names],
    }


def _run(*scenario_names: str, failed: set[str] | None = None) -> dict:
    failed = failed or set()
    return {
        "path": "/tmp/test-eval.jsonl",
        "run_id": "test-run",
        "evaluator_version": EVALUATOR_VERSION,
        "status": "failed" if failed else "ok",
        "scenario_count": len(scenario_names),
        "summary": {},
        "scenarios": {name: _scenario(name, passed=name not in failed) for name in scenario_names},
    }


def _scenario(name: str, *, passed: bool = True) -> dict:
    return {
        "record_type": "scenario_result",
        "scenario_name": name,
        "passed": passed,
        "failures": [] if passed else ["regressed"],
        "details": {
            "ordered_titles": [f"{name} task"],
            "rolled_over_titles": [],
            "risk_keys": [],
            "capacity_status": "within_capacity",
            "daily_capacity_minutes": 150,
            "selected_estimated_minutes": 30,
            "rolled_over_estimated_minutes": 0,
            "over_capacity_minutes": 0,
            "energy_applied": False,
            "planner_agent_status": "succeeded",
            "planner_agent_provider": "mock",
            "planner_agent_model": "structured-mock-v1",
            "planner_agent_prompt_version": "p2-daily-planner-agent-v1",
            "planner_agent_prompt_checksum": "test-checksum",
            "planner_agent_output_applied": True,
            "score_explanation_summary": "测试策略解释。",
            "score_explanation_signal_keys": ["value"],
            "item_signals": [
                {
                    "title": f"{name} task",
                    "section": "recommended",
                    "score_version": "planning-engine-score-v1",
                    "score_band": "normal",
                    "total_score": 30,
                    "goal_value_score": 0,
                    "goal_urgency_score": 0,
                    "goal_progress_score": 0,
                    "goal_progress_completion_rate": 0.0,
                    "behavior_feedback_score": 0,
                    "personalization_score": 0,
                    "personalization_sample_count": 0,
                    "dependency_score": 0,
                    "user_preference_score": 0,
                    "dominant_factor": "value",
                    "dominant_reason": "任务价值较高。",
                    "score_signal_keys": ["value"],
                }
            ],
        },
    }


def _records(*scenario_names: str) -> list[dict]:
    return [
        {
            "run_id": "test-run",
            "evaluator_version": EVALUATOR_VERSION,
            "record_type": "run_summary",
            "status": "ok",
            "scenario_count": len(scenario_names),
            "passed_count": len(scenario_names),
            "failed_count": 0,
        },
        *[
            {
                "run_id": "test-run",
                "evaluator_version": EVALUATOR_VERSION,
                **_scenario(name),
            }
            for name in scenario_names
        ],
    ]


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False))
            file.write("\n")


if __name__ == "__main__":
    unittest.main()
