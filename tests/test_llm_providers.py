import unittest
from types import SimpleNamespace

from app.ai.providers.base import LLMProviderError
from app.ai.providers.openai_compatible import OpenAICompatibleProvider
from app.ai.providers.registry import llm_provider_registry
from app.ai.schemas.planning import DailyPlannerOutput
from app.core.config import settings


class FakeResponses:
    def __init__(self, parsed=None, error=None):
        self.parsed = parsed
        self.error = error
        self.kwargs = None

    def parse(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return SimpleNamespace(output_parsed=self.parsed)


class FakeOpenAIClient:
    def __init__(self, *, parsed=None, error=None):
        self.responses = FakeResponses(parsed=parsed, error=error)


class OpenAICompatibleProviderTests(unittest.TestCase):
    def test_generate_structured_uses_responses_parse_and_filters_internal_metadata(self):
        parsed = DailyPlannerOutput(
            mode="normal",
            strategy_summary="Keep a steady order.",
            primary_reason="The sequence balances value and capacity.",
            items=[],
            confidence=0.8,
        )
        client = FakeOpenAIClient(parsed=parsed)
        provider = OpenAICompatibleProvider(client=client, model_name="gpt-test")

        result = provider.generate_structured(
            prompt="Planner prompt",
            schema=DailyPlannerOutput,
            temperature=0.1,
            metadata={
                "plan_context": {"plan_date": "2026-05-17"},
                "mock_output": {"should": "not be sent"},
                "prompt": {"checksum": "not-sent"},
            },
        )

        self.assertEqual(result, parsed)
        self.assertEqual(client.responses.kwargs["model"], "gpt-test")
        self.assertEqual(client.responses.kwargs["instructions"], "Planner prompt")
        self.assertEqual(client.responses.kwargs["text_format"], DailyPlannerOutput)
        self.assertEqual(client.responses.kwargs["temperature"], 0.1)
        self.assertIn("plan_context", client.responses.kwargs["input"])
        self.assertNotIn("mock_output", client.responses.kwargs["input"])
        self.assertNotIn("not-sent", client.responses.kwargs["input"])

    def test_generate_structured_rejects_missing_parsed_output(self):
        provider = OpenAICompatibleProvider(client=FakeOpenAIClient(parsed=None), model_name="gpt-test")

        with self.assertRaises(LLMProviderError):
            provider.generate_structured(prompt="Prompt", schema=DailyPlannerOutput)

    def test_generate_structured_wraps_provider_errors(self):
        provider = OpenAICompatibleProvider(
            client=FakeOpenAIClient(error=RuntimeError("network unavailable")),
            model_name="gpt-test",
        )

        with self.assertRaises(LLMProviderError):
            provider.generate_structured(prompt="Prompt", schema=DailyPlannerOutput)

    def test_registry_defaults_to_mock_until_real_llm_is_enabled(self):
        original = {
            "AI_ENABLE_REAL_LLM": settings.AI_ENABLE_REAL_LLM,
            "LLM_PROVIDER": settings.LLM_PROVIDER,
            "LLM_FALLBACK_PROVIDER": settings.LLM_FALLBACK_PROVIDER,
        }
        try:
            settings.AI_ENABLE_REAL_LLM = False
            settings.LLM_PROVIDER = "openai"
            self.assertEqual(llm_provider_registry.current_provider().provider_name, "mock")

            settings.AI_ENABLE_REAL_LLM = True
            self.assertEqual(llm_provider_registry.current_provider().provider_name, "openai")

            settings.LLM_PROVIDER = "openai-compatible"
            self.assertEqual(llm_provider_registry.current_provider().provider_name, "openai-compatible")

            settings.LLM_PROVIDER = "unknown"
            settings.LLM_FALLBACK_PROVIDER = "mock"
            self.assertEqual(llm_provider_registry.current_provider().provider_name, "mock")
        finally:
            settings.AI_ENABLE_REAL_LLM = original["AI_ENABLE_REAL_LLM"]
            settings.LLM_PROVIDER = original["LLM_PROVIDER"]
            settings.LLM_FALLBACK_PROVIDER = original["LLM_FALLBACK_PROVIDER"]


if __name__ == "__main__":
    unittest.main()
