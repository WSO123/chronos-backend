import unittest

from app.ai.agents.insight_detail import InsightDetailAgent
from app.ai.providers.base import LLMStructuredGeneration
from app.ai.prompts import prompt_registry
from app.ai.schemas.insight import InsightDetailOutput


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
            usage={"input_tokens": 17, "output_tokens": 11, "total_tokens": 28, "cost_usd": None},
            response_id="insight-detail-response",
        )


class InsightDetailAgentTests(unittest.TestCase):
    def test_agent_returns_structured_insight_detail(self):
        agent = InsightDetailAgent()

        result = agent.run(
            insight_context={
                "anchor_date": "2026-05-17",
                "overview": {"total_completed_task_count": 1},
            },
            fallback_output={
                "behavior_patterns": [
                    {
                        "key": "high_value_progress",
                        "title": "高价值任务有推进",
                        "signal": "positive",
                        "evidence": "本周完成了 1 个高价值任务。",
                        "suggestion": "下周继续把高价值任务放在 Today 的前段。",
                    }
                ],
                "recommendations": [
                    {
                        "category": "schedule",
                        "title": "把难任务放到优势时段",
                        "suggestion": "下周优先在上午开始一个高价值任务。",
                        "rationale": "这是本周 Focus 时长最集中的时段。",
                    }
                ],
                "strategy_notes": ["可以把高价值任务优先安排在上午。"],
                "confidence": 0.68,
            },
        )

        self.assertIsInstance(result.output, InsightDetailOutput)
        self.assertEqual(result.provider, "mock")
        self.assertEqual(result.model, "structured-mock-v1")
        self.assertEqual(result.prompt_version, "p2-insight-detail-agent-v1")
        self.assertEqual(len(result.prompt_checksum), 64)
        self.assertEqual(len(result.output.behavior_patterns), 1)

    def test_agent_uses_insight_detail_prompt_registry(self):
        agent = InsightDetailAgent()
        provider = RecordingProvider()

        result = agent.run(
            insight_context={
                "anchor_date": "2026-05-17",
                "overview": {"total_completed_task_count": 1},
            },
            fallback_output={
                "behavior_patterns": [
                    {
                        "key": "lagging_tasks",
                        "title": "存在滞后任务",
                        "signal": "risk",
                        "evidence": "当前有 1 个任务已过截止时间。",
                        "suggestion": "先判断它是否仍重要。",
                    }
                ],
                "recommendations": [
                    {
                        "category": "planning",
                        "title": "清理滞后任务",
                        "suggestion": "先处理仍有价值的滞后任务。",
                        "rationale": "滞后任务会挤占 Today 的行动清晰度。",
                    }
                ],
                "strategy_notes": ["下周 Today 编排需要继续保护有风险的 Goal。"],
                "confidence": 0.68,
            },
            provider=provider,
        )

        template = prompt_registry.get("insight_detail")
        self.assertIn("Chronos Insight Detail Agent v1", provider.prompt)
        self.assertIn("不要改变 task、goal、plan", provider.prompt)
        self.assertEqual(provider.metadata["prompt"]["key"], "insight_detail")
        self.assertEqual(provider.metadata["prompt"]["version"], template.version)
        self.assertEqual(provider.metadata["prompt"]["checksum"], template.checksum)
        self.assertEqual(result.prompt_version, template.version)
        self.assertEqual(result.prompt_checksum, template.checksum)
        self.assertEqual(result.usage["total_tokens"], 28)
        self.assertEqual(result.response_id, "insight-detail-response")


if __name__ == "__main__":
    unittest.main()
