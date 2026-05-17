import unittest

from scripts.evaluate_planning_engine import run_evaluation


class PlanningEngineEvaluationTests(unittest.TestCase):
    def test_fixed_scenarios_pass(self):
        result = run_evaluation()

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


if __name__ == "__main__":
    unittest.main()
