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
        self.assertEqual(result["scenario_count"], 13)
        self.assertEqual(result["failed_count"], 0)
        self.assertEqual(
            {scenario["name"] for scenario in result["scenarios"]},
            {
                "capacity_rollover",
                "capacity_objective_protects_goal_progress",
                "protected_overload_warning",
                "low_energy_lightens_plan",
                "high_energy_deep_fit_no_expansion",
                "dependency_chain_protection",
                "user_priority_adjustment_protection",
                "behavior_feedback_penalizes_interruptions",
                "multi_goal_competition_protects_high_value_goal",
                "overdue_goal_recovery_promotes_next_task",
                "goal_progress_strategy_closes_near_done_goal",
                "semantic_history_personalizes_duration",
                "planner_feedback_preference_explained_without_reordering",
            },
        )
        for scenario in result["scenarios"]:
            self.assertEqual(scenario["details"]["planner_agent_provider"], "mock")
            self.assertEqual(scenario["details"]["planner_agent_model"], "structured-mock-v1")
            self.assertEqual(scenario["details"]["planner_agent_prompt_version"], "p2-daily-planner-agent-v1")
            self.assertTrue(scenario["details"]["planner_agent_output_applied"])
            self.assertTrue(scenario["details"]["score_explanation_summary"])
            self.assertTrue(scenario["details"]["score_explanation_signal_keys"])
            self.assertTrue(scenario["details"]["item_signals"])
            for item_signal in scenario["details"]["item_signals"]:
                self.assertTrue(item_signal["score_version"])
                self.assertTrue(item_signal["score_band"])
                self.assertTrue(item_signal["dominant_factor"])
                self.assertTrue(item_signal["dominant_reason"])
                self.assertTrue(item_signal["score_signal_keys"])
                self.assertIn("planning_objective_score", item_signal)
                self.assertIn("planning_objective_selected", item_signal)
                self.assertIn("planning_objective_reason_key", item_signal)

    def test_write_jsonl_result_outputs_summary_and_scenario_records(self):
        result = run_evaluation(run_id="jsonl-test-run")

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "planner-eval.jsonl"
            write_jsonl_result(result, output_path)
            write_jsonl_result(result, output_path, append=True)

            records = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(len(records), 28)
        self.assertEqual(records[0]["record_type"], "run_summary")
        self.assertEqual(records[0]["run_id"], "jsonl-test-run")
        self.assertEqual(records[0]["status"], "ok")
        self.assertEqual(records[14]["record_type"], "run_summary")
        self.assertEqual({record["record_type"] for record in records[1:14]}, {"scenario_result"})
        self.assertEqual(
            {record["scenario_name"] for record in records[1:14]},
            {
                "capacity_rollover",
                "capacity_objective_protects_goal_progress",
                "protected_overload_warning",
                "low_energy_lightens_plan",
                "high_energy_deep_fit_no_expansion",
                "dependency_chain_protection",
                "user_priority_adjustment_protection",
                "behavior_feedback_penalizes_interruptions",
                "multi_goal_competition_protects_high_value_goal",
                "overdue_goal_recovery_promotes_next_task",
                "goal_progress_strategy_closes_near_done_goal",
                "semantic_history_personalizes_duration",
                "planner_feedback_preference_explained_without_reordering",
            },
        )
        self.assertEqual(records[1]["details"]["planner_agent_provider"], "mock")
        self.assertIn("item_signals", records[1]["details"])
        self.assertIn("score_explanation_summary", records[1]["details"])
        self.assertIn("score_explanation_signal_keys", records[1]["details"])
        self.assertIn("dominant_factor", records[1]["details"]["item_signals"][0])
        self.assertIn("planning_objective_version", records[1]["details"])
        self.assertIn("planning_objective_score", records[1]["details"]["item_signals"][0])

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
        self.assertEqual(len(records), 14)


if __name__ == "__main__":
    unittest.main()
