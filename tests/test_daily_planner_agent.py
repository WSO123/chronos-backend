import unittest

from app.ai.agents.daily_planner import DailyPlannerAgent
from app.ai.providers.base import LLMStructuredGeneration
from app.ai.prompts import prompt_registry
from app.ai.prompts.registry import PromptRegistryError
from app.ai.schemas.planning import DailyPlannerOutput


class RecordingProvider:
    provider_name = "recording"
    model_name = "recording-model"

    def __init__(self) -> None:
        self.prompt = ""
        self.metadata = {}

    def generate_structured(self, *, prompt, schema, temperature=0.2, metadata=None):
        del temperature
        self.prompt = prompt
        self.metadata = metadata or {}
        return LLMStructuredGeneration(
            output=schema.model_validate(self.metadata["mock_output"]),
            usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15, "cost_usd": None},
            response_id="recording-response",
        )


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
        self.assertEqual(result.prompt_version, "p2-daily-planner-agent-v1")
        self.assertEqual(len(result.prompt_checksum), 64)
        self.assertEqual(result.usage["total_tokens"], None)
        self.assertEqual(result.response_id, None)
        self.assertEqual(result.output.items[0].task_id, "task-1")
        self.assertEqual(result.output.strategy_summary, "Keep a steady order.")

    def test_agent_uses_versioned_prompt_registry(self):
        agent = DailyPlannerAgent()
        provider = RecordingProvider()

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
            provider=provider,
        )

        template = prompt_registry.get("daily_planner")
        self.assertIn("Chronos Daily Planner Agent v1", provider.prompt)
        self.assertIn("Do not reorder tasks in v1.", provider.prompt)
        self.assertEqual(provider.metadata["prompt"]["key"], "daily_planner")
        self.assertEqual(provider.metadata["prompt"]["version"], template.version)
        self.assertEqual(provider.metadata["prompt"]["checksum"], template.checksum)
        self.assertEqual(result.prompt_version, template.version)
        self.assertEqual(result.prompt_checksum, template.checksum)
        self.assertEqual(result.usage["total_tokens"], 15)
        self.assertEqual(result.response_id, "recording-response")

    def test_prompt_registry_rejects_unknown_key(self):
        with self.assertRaises(PromptRegistryError):
            prompt_registry.get("unknown_prompt")


if __name__ == "__main__":
    unittest.main()
