import unittest

from app.ai.agents.strategy_explanation import StrategyExplanationAgent
from app.ai.providers.base import LLMStructuredGeneration
from app.ai.prompts import prompt_registry
from app.ai.schemas.strategy_explanation import StrategyExplanationOutput


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
            usage={"input_tokens": 11, "output_tokens": 8, "total_tokens": 19, "cost_usd": None},
            response_id="strategy-explanation-response",
        )


class StrategyExplanationAgentTests(unittest.TestCase):
    def test_agent_returns_structured_strategy_explanation(self):
        agent = StrategyExplanationAgent()

        result = agent.run(
            strategy_context={
                "daily_plan_id": "plan-1",
                "plan_date": "2026-05-17",
                "summary": "High-value task first.",
                "mode": "normal",
                "primary_reason": "High-value task protected.",
            },
            factors={"pinned_count": 1, "rolled_over_count": 0},
            task_rationales=[],
            fallback_output={
                "explanation": ["高价值任务被放在前面，今天先从它开始。"],
                "confidence": 0.68,
                "summary": "High-value task first.",
            },
        )

        self.assertIsInstance(result.output, StrategyExplanationOutput)
        self.assertEqual(result.provider, "mock")
        self.assertEqual(result.model, "structured-mock-v1")
        self.assertEqual(result.prompt_version, "p2-strategy-explanation-agent-v1")
        self.assertEqual(len(result.prompt_checksum), 64)
        self.assertEqual(len(result.output.explanation), 1)

    def test_agent_uses_strategy_explanation_prompt_registry(self):
        agent = StrategyExplanationAgent()
        provider = RecordingProvider()

        result = agent.run(
            strategy_context={
                "daily_plan_id": "plan-1",
                "plan_date": "2026-05-17",
                "summary": "High-value task first.",
                "mode": "normal",
                "primary_reason": "High-value task protected.",
            },
            factors={"pinned_count": 1, "rolled_over_count": 0},
            task_rationales=[],
            fallback_output={
                "explanation": ["高价值任务被放在前面，今天先从它开始。"],
                "confidence": 0.68,
                "summary": "High-value task first.",
            },
            provider=provider,
        )

        template = prompt_registry.get("strategy_explanation")
        self.assertIn("Chronos Strategy Explanation Agent v1", provider.prompt)
        self.assertIn("不要改变任务顺序", provider.prompt)
        self.assertEqual(provider.metadata["prompt"]["key"], "strategy_explanation")
        self.assertEqual(provider.metadata["prompt"]["version"], template.version)
        self.assertEqual(provider.metadata["prompt"]["checksum"], template.checksum)
        self.assertEqual(result.prompt_version, template.version)
        self.assertEqual(result.prompt_checksum, template.checksum)
        self.assertEqual(result.usage["total_tokens"], 19)
        self.assertEqual(result.response_id, "strategy-explanation-response")


if __name__ == "__main__":
    unittest.main()
