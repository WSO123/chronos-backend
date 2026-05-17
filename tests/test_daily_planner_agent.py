import unittest

from app.ai.agents.daily_planner import DailyPlannerAgent
from app.ai.schemas.planning import DailyPlannerOutput


class DailyPlannerAgentTests(unittest.TestCase):
    def test_mock_agent_returns_structured_output(self):
        agent = DailyPlannerAgent()

        result = agent.run(
            plan_context={"plan_date": "2026-05-17"},
            candidates=[
                {
                    "task_id": "task-1",
                    "title": "Important task",
                    "section": "pinned",
                    "sort_order": 1,
                    "recommendation_reason": "Protected high-value task.",
                    "estimated_duration_min": 30,
                    "score_breakdown": {"total_score": 90},
                }
            ],
            strategy_seed={
                "mode": "normal",
                "summary": "Keep a steady order.",
                "primary_reason": "The sequence balances value and capacity.",
                "score_factors": {"task_count": 1},
            },
        )

        self.assertIsInstance(result.output, DailyPlannerOutput)
        self.assertEqual(result.provider, "mock")
        self.assertEqual(result.model, "structured-mock-v1")
        self.assertEqual(result.output.items[0].task_id, "task-1")
        self.assertEqual(result.output.strategy_summary, "Keep a steady order.")


if __name__ == "__main__":
    unittest.main()
