import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from scripts.evaluate_planning_engine import EVALUATOR_VERSION, run_evaluation, write_jsonl_result


class PlanningEngineEvaluationTests(unittest.TestCase):
    def test_fixed_scenarios_pass(self):
        result = run_evaluation(run_id="test-run")

        self.assertEqual(result["run_id"], "test-run")
        self.assertEqual(result["evaluator_version"], EVALUATOR_VERSION)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["scenario_count"], 4)
        self.assertEqual(result["failed_count"], 0)
        self.assertEqual(
            {scenario["name"] for scenario in result["scenarios"]},
            {
                "capacity_rollover",
                "protected_overload_warning",
                "low_energy_lightens_plan",
                "high_energy_deep_fit_no_expansion",
            },
        )
        for scenario in result["scenarios"]:
            self.assertEqual(scenario["details"]["planner_agent_provider"], "mock")
            self.assertEqual(scenario["details"]["planner_agent_model"], "structured-mock-v1")
            self.assertEqual(scenario["details"]["planner_agent_prompt_version"], "p2-daily-planner-agent-v1")
            self.assertTrue(scenario["details"]["planner_agent_output_applied"])

    def test_write_jsonl_result_outputs_summary_and_scenario_records(self):
        result = run_evaluation(run_id="jsonl-test-run")

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "planner-eval.jsonl"
            write_jsonl_result(result, output_path)
            write_jsonl_result(result, output_path, append=True)

            records = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(len(records), 10)
        self.assertEqual(records[0]["record_type"], "run_summary")
        self.assertEqual(records[0]["run_id"], "jsonl-test-run")
        self.assertEqual(records[0]["status"], "ok")
        self.assertEqual(records[5]["record_type"], "run_summary")
        self.assertEqual({record["record_type"] for record in records[1:5]}, {"scenario_result"})
        self.assertEqual(
            {record["scenario_name"] for record in records[1:5]},
            {
                "capacity_rollover",
                "protected_overload_warning",
                "low_energy_lightens_plan",
                "high_energy_deep_fit_no_expansion",
            },
        )
        self.assertEqual(records[1]["details"]["planner_agent_provider"], "mock")

    def test_cli_can_write_jsonl_output(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "cli-eval.jsonl"
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/evaluate_planning_engine.py",
                    "--run-id",
                    "cli-test-run",
                    "--jsonl-output",
                    str(output_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(result.stdout)
            records = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(payload["run_id"], "cli-test-run")
        self.assertEqual(records[0]["run_id"], "cli-test-run")
        self.assertEqual(len(records), 5)


if __name__ == "__main__":
    unittest.main()
