import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from scripts.compare_planner_eval_jsonl import compare_eval_runs, load_eval_run


class PlannerEvalCompareTests(unittest.TestCase):
    def test_compare_identical_runs_is_ok(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "baseline.jsonl"
            _write_jsonl(path, _records(run_id="baseline"))

            baseline = load_eval_run(path)
            candidate = load_eval_run(path)
            result = compare_eval_runs(baseline, candidate)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["regression_count"], 0)
        self.assertEqual(result["changed_count"], 0)

    def test_compare_detects_regression_and_signal_changes(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_path = Path(tmp_dir) / "baseline.jsonl"
            candidate_path = Path(tmp_dir) / "candidate.jsonl"
            _write_jsonl(baseline_path, _records(run_id="baseline"))
            _write_jsonl(
                candidate_path,
                _records(
                    run_id="candidate",
                    passed=False,
                    ordered_titles=["Frequently interrupted task", "Stable task"],
                    item_signals=[
                        {
                            "title": "Stable task",
                            "section": "recommended",
                            "total_score": 38,
                            "behavior_feedback_score": 0,
                            "dependency_score": 0,
                            "user_preference_score": 0,
                        },
                        {
                            "title": "Frequently interrupted task",
                            "section": "recommended",
                            "total_score": 42,
                            "behavior_feedback_score": 4,
                            "dependency_score": 0,
                            "user_preference_score": 0,
                        },
                    ],
                    failures=["interrupted task receives behavior penalty"],
                ),
            )

            result = compare_eval_runs(load_eval_run(baseline_path), load_eval_run(candidate_path))

        self.assertEqual(result["status"], "regressed")
        self.assertEqual(result["regression_count"], 1)
        self.assertEqual(result["regressions"], ["behavior_feedback_penalizes_interruptions"])
        diff = result["scenario_diffs"][0]
        self.assertEqual(diff["scenario_name"], "behavior_feedback_penalizes_interruptions")
        self.assertIn("ordered_titles", {change["field"] for change in diff["field_changes"]})
        self.assertIn(
            ("Frequently interrupted task", "behavior_feedback_score"),
            {(change["title"], change["field"]) for change in diff["item_signal_changes"]},
        )

    def test_load_eval_run_defaults_to_latest_run(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "appended.jsonl"
            _write_jsonl(path, _records(run_id="old-run"))
            _write_jsonl(path, _records(run_id="latest-run"), append=True)

            latest = load_eval_run(path)
            old = load_eval_run(path, run_id="old-run")

        self.assertEqual(latest["run_id"], "latest-run")
        self.assertEqual(old["run_id"], "old-run")

    def test_compare_missing_candidate_scenario_is_regression(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_path = Path(tmp_dir) / "baseline.jsonl"
            candidate_path = Path(tmp_dir) / "candidate.jsonl"
            _write_jsonl(baseline_path, _records(run_id="baseline"))
            _write_jsonl(candidate_path, [_records(run_id="candidate")[0]])

            result = compare_eval_runs(load_eval_run(baseline_path), load_eval_run(candidate_path))

        self.assertEqual(result["status"], "regressed")
        self.assertEqual(result["regression_count"], 1)
        self.assertEqual(result["missing_in_candidate"], ["behavior_feedback_penalizes_interruptions"])

    def test_compare_added_candidate_scenario_is_changed(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_path = Path(tmp_dir) / "baseline.jsonl"
            candidate_path = Path(tmp_dir) / "candidate.jsonl"
            _write_jsonl(baseline_path, _records(run_id="baseline"))
            candidate_records = _records(run_id="candidate")
            extra = _scenario_record(run_id="candidate", scenario_name="new_candidate_scenario")
            _write_jsonl(candidate_path, [*candidate_records, extra])

            result = compare_eval_runs(load_eval_run(baseline_path), load_eval_run(candidate_path))

        self.assertEqual(result["status"], "changed")
        self.assertEqual(result["regression_count"], 0)
        self.assertEqual(result["added_in_candidate"], ["new_candidate_scenario"])

    def test_compare_detects_prompt_checksum_change(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_path = Path(tmp_dir) / "baseline.jsonl"
            candidate_path = Path(tmp_dir) / "candidate.jsonl"
            _write_jsonl(baseline_path, _records(run_id="baseline", prompt_checksum="baseline-checksum"))
            _write_jsonl(candidate_path, _records(run_id="candidate", prompt_checksum="candidate-checksum"))

            result = compare_eval_runs(load_eval_run(baseline_path), load_eval_run(candidate_path))

        self.assertEqual(result["status"], "changed")
        diff = result["scenario_diffs"][0]
        self.assertIn("planner_agent_prompt_checksum", {change["field"] for change in diff["field_changes"]})

    def test_cli_fail_on_regression_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_path = Path(tmp_dir) / "baseline.jsonl"
            candidate_path = Path(tmp_dir) / "candidate.jsonl"
            _write_jsonl(baseline_path, _records(run_id="baseline"))
            _write_jsonl(
                candidate_path,
                _records(
                    run_id="candidate",
                    passed=False,
                    failures=["regressed"],
                ),
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/compare_planner_eval_jsonl.py",
                    str(baseline_path),
                    str(candidate_path),
                    "--fail-on-regression",
                ],
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "regressed")


def _records(
    *,
    run_id: str,
    passed: bool = True,
    ordered_titles: list[str] | None = None,
    item_signals: list[dict] | None = None,
    failures: list[str] | None = None,
    prompt_checksum: str = "test-checksum",
) -> list[dict]:
    scenario_name = "behavior_feedback_penalizes_interruptions"
    return [
        {
            "run_id": run_id,
            "evaluator_version": "p2-planning-engine-eval-v2",
            "record_type": "run_summary",
            "status": "ok" if passed else "failed",
            "scenario_count": 1,
            "passed_count": 1 if passed else 0,
            "failed_count": 0 if passed else 1,
        },
        _scenario_record(
            run_id=run_id,
            scenario_name=scenario_name,
            passed=passed,
            ordered_titles=ordered_titles,
            item_signals=item_signals,
            failures=failures,
            planner_agent_prompt_checksum=prompt_checksum,
        ),
    ]


def _scenario_record(
    *,
    run_id: str,
    scenario_name: str,
    passed: bool = True,
    ordered_titles: list[str] | None = None,
    item_signals: list[dict] | None = None,
    failures: list[str] | None = None,
    planner_agent_prompt_checksum: str = "test-checksum",
) -> dict:
    return {
        "run_id": run_id,
        "evaluator_version": "p2-planning-engine-eval-v2",
        "record_type": "scenario_result",
        "scenario_name": scenario_name,
        "passed": passed,
        "failures": failures or [],
        "details": {
            "ordered_titles": ordered_titles or ["Stable task", "Frequently interrupted task"],
            "rolled_over_titles": [],
            "risk_keys": [],
            "capacity_status": "within_capacity",
            "daily_capacity_minutes": 150,
            "selected_estimated_minutes": 60,
            "rolled_over_estimated_minutes": 0,
            "over_capacity_minutes": 0,
            "energy_applied": False,
            "planner_agent_status": "succeeded",
            "planner_agent_provider": "mock",
            "planner_agent_model": "structured-mock-v1",
            "planner_agent_prompt_version": "p2-daily-planner-agent-v1",
            "planner_agent_prompt_checksum": planner_agent_prompt_checksum,
            "planner_agent_failure_type": None,
            "planner_agent_output_applied": True,
            "item_signals": item_signals or _default_item_signals(),
        },
    }


def _default_item_signals() -> list[dict]:
    return [
        {
            "title": "Stable task",
            "section": "recommended",
            "total_score": 38,
            "behavior_feedback_score": 0,
            "dependency_score": 0,
            "user_preference_score": 0,
        },
        {
            "title": "Frequently interrupted task",
            "section": "recommended",
            "total_score": 30,
            "behavior_feedback_score": -8,
            "dependency_score": 0,
            "user_preference_score": 0,
        },
    ]


def _write_jsonl(path: Path, records: list[dict], *, append: bool = False) -> None:
    mode = "a" if append else "w"
    with path.open(mode, encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False))
            file.write("\n")


if __name__ == "__main__":
    unittest.main()
