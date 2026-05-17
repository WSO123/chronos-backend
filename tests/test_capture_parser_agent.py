import unittest

from app.ai.agents.capture_parser import CaptureParserAgent
from app.ai.providers.base import LLMStructuredGeneration
from app.ai.prompts import prompt_registry
from app.ai.schemas.capture import CaptureParserOutput


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
            usage={"input_tokens": 8, "output_tokens": 6, "total_tokens": 14, "cost_usd": None},
            response_id="capture-response",
        )


class CaptureParserAgentTests(unittest.TestCase):
    def test_agent_returns_structured_capture_output(self):
        agent = CaptureParserAgent()

        result = agent.run(
            raw_text="完成 API 文档",
            input_type="text",
            source="manual",
            fallback_output={
                "result_type": "task",
                "item_type": "task",
                "title": "完成 API 文档",
                "description": None,
                "estimated_duration_min": 25,
                "suggested_priority": 3,
                "suggested_deadline": None,
                "confidence": 0.68,
                "rationale": "Rule parser fallback output for local mock mode.",
            },
        )

        self.assertIsInstance(result.output, CaptureParserOutput)
        self.assertEqual(result.provider, "mock")
        self.assertEqual(result.model, "structured-mock-v1")
        self.assertEqual(result.prompt_version, "p2-capture-parser-agent-v1")
        self.assertEqual(len(result.prompt_checksum), 64)
        self.assertEqual(result.output.result_type.value, "task")
        self.assertEqual(result.output.item_type.value, "task")

    def test_agent_uses_capture_prompt_registry(self):
        agent = CaptureParserAgent()
        provider = RecordingProvider()

        result = agent.run(
            raw_text="目标：上线 Chronos MVP",
            input_type="text",
            source="manual",
            fallback_output={
                "result_type": "goal",
                "item_type": "goal",
                "title": "目标：上线 Chronos MVP",
                "description": None,
                "estimated_duration_min": None,
                "suggested_priority": None,
                "suggested_deadline": None,
                "confidence": 0.72,
                "rationale": "Rule parser fallback output for local mock mode.",
            },
            provider=provider,
        )

        template = prompt_registry.get("capture_parser")
        self.assertIn("Chronos Capture Parser Agent v1", provider.prompt)
        self.assertIn("不要直接创建 Task 或 Goal。", provider.prompt)
        self.assertEqual(provider.metadata["prompt"]["key"], "capture_parser")
        self.assertEqual(provider.metadata["prompt"]["version"], template.version)
        self.assertEqual(provider.metadata["prompt"]["checksum"], template.checksum)
        self.assertEqual(result.prompt_version, template.version)
        self.assertEqual(result.prompt_checksum, template.checksum)
        self.assertEqual(result.usage["total_tokens"], 14)
        self.assertEqual(result.response_id, "capture-response")


if __name__ == "__main__":
    unittest.main()
