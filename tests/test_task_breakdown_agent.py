import unittest

from app.ai.agents.task_breakdown import TaskBreakdownAgent
from app.ai.providers.base import LLMStructuredGeneration
from app.ai.prompts import prompt_registry
from app.ai.schemas.task_breakdown import TaskBreakdownOutput


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
            usage={"input_tokens": 9, "output_tokens": 7, "total_tokens": 16, "cost_usd": None},
            response_id="breakdown-response",
        )


class TaskBreakdownAgentTests(unittest.TestCase):
    def test_agent_returns_structured_breakdown_output(self):
        agent = TaskBreakdownAgent()

        result = agent.run(
            task_context={
                "task_id": "task-1",
                "title": "Write API docs",
                "estimated_duration_min": 70,
            },
            fallback_output={
                "steps": [
                    {"title": "Clarify the finished state", "sort_order": 1, "rationale": None},
                    {"title": "Do the main work", "sort_order": 2, "rationale": None},
                ],
                "confidence": 0.68,
                "summary": "Rule fallback breakdown for local mock mode.",
            },
        )

        self.assertIsInstance(result.output, TaskBreakdownOutput)
        self.assertEqual(result.provider, "mock")
        self.assertEqual(result.model, "structured-mock-v1")
        self.assertEqual(result.prompt_version, "p2-task-breakdown-agent-v1")
        self.assertEqual(len(result.prompt_checksum), 64)
        self.assertEqual(len(result.output.steps), 2)

    def test_agent_uses_task_breakdown_prompt_registry(self):
        agent = TaskBreakdownAgent()
        provider = RecordingProvider()

        result = agent.run(
            task_context={
                "task_id": "task-1",
                "title": "Write API docs",
                "estimated_duration_min": 70,
            },
            fallback_output={
                "steps": [
                    {"title": "Clarify the finished state", "sort_order": 1, "rationale": None},
                    {"title": "Do the main work", "sort_order": 2, "rationale": None},
                ],
                "confidence": 0.68,
                "summary": "Rule fallback breakdown for local mock mode.",
            },
            provider=provider,
        )

        template = prompt_registry.get("task_breakdown")
        self.assertIn("Chronos Task Breakdown Agent v1", provider.prompt)
        self.assertIn("Do not overwrite existing user-created steps.", provider.prompt)
        self.assertEqual(provider.metadata["prompt"]["key"], "task_breakdown")
        self.assertEqual(provider.metadata["prompt"]["version"], template.version)
        self.assertEqual(provider.metadata["prompt"]["checksum"], template.checksum)
        self.assertEqual(result.prompt_version, template.version)
        self.assertEqual(result.prompt_checksum, template.checksum)
        self.assertEqual(result.usage["total_tokens"], 16)
        self.assertEqual(result.response_id, "breakdown-response")


if __name__ == "__main__":
    unittest.main()
