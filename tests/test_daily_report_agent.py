import unittest

from app.ai.agents.daily_report import DailyReportAgent
from app.ai.providers.base import LLMStructuredGeneration
from app.ai.prompts import prompt_registry
from app.ai.schemas.daily_report import DailyReportOutput


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
            usage={"input_tokens": 13, "output_tokens": 9, "total_tokens": 22, "cost_usd": None},
            response_id="daily-report-response",
        )


class DailyReportAgentTests(unittest.TestCase):
    def test_agent_returns_structured_daily_report(self):
        agent = DailyReportAgent()

        result = agent.run(
            report_context={
                "report_date": "2026-05-17",
                "completed_task_count": 1,
                "postponed_task_count": 0,
                "interrupted_count": 0,
                "focus_minutes": 30,
                "completion_rate": 1.0,
                "planned_task_count": 1,
            },
            fallback_output={
                "ai_summary": "今天形成了一个清晰的执行闭环。",
                "ai_suggestions": ["明天继续先做最重要的一件事。"],
                "confidence": 0.68,
            },
        )

        self.assertIsInstance(result.output, DailyReportOutput)
        self.assertEqual(result.provider, "mock")
        self.assertEqual(result.model, "structured-mock-v1")
        self.assertEqual(result.prompt_version, "p2-daily-report-agent-v1")
        self.assertEqual(len(result.prompt_checksum), 64)
        self.assertEqual(len(result.output.ai_suggestions), 1)

    def test_agent_uses_daily_report_prompt_registry(self):
        agent = DailyReportAgent()
        provider = RecordingProvider()

        result = agent.run(
            report_context={
                "report_date": "2026-05-17",
                "completed_task_count": 1,
                "postponed_task_count": 1,
                "interrupted_count": 0,
                "focus_minutes": 35,
                "completion_rate": 0.5,
                "planned_task_count": 2,
            },
            fallback_output={
                "ai_summary": "今天已经有清晰进展，下一步是让节奏更稳定。",
                "ai_suggestions": ["明天继续从 Today 推荐序列里的第一个任务开始。"],
                "confidence": 0.68,
            },
            provider=provider,
        )

        template = prompt_registry.get("daily_report")
        self.assertIn("Chronos Daily Report Agent v1", provider.prompt)
        self.assertIn("不要改变 task、goal、plan", provider.prompt)
        self.assertEqual(provider.metadata["prompt"]["key"], "daily_report")
        self.assertEqual(provider.metadata["prompt"]["version"], template.version)
        self.assertEqual(provider.metadata["prompt"]["checksum"], template.checksum)
        self.assertEqual(result.prompt_version, template.version)
        self.assertEqual(result.prompt_checksum, template.checksum)
        self.assertEqual(result.usage["total_tokens"], 22)
        self.assertEqual(result.response_id, "daily-report-response")


if __name__ == "__main__":
    unittest.main()
