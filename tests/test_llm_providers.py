import unittest
from types import SimpleNamespace

from app.ai.providers.base import LLMProviderError
from app.ai.providers.openai_compatible import OpenAICompatibleProvider
from app.ai.providers.registry import llm_provider_registry
from app.ai.schemas.planning import DailyPlannerOutput
from app.core.config import settings


class FakeResponses:
    def __init__(self, parsed=None, error=None, usage=None, response_id="resp-test"):
        self.parsed = parsed
        self.error = error
        self.usage = usage
        self.response_id = response_id
        self.kwargs = None

    def parse(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return SimpleNamespace(output_parsed=self.parsed, usage=self.usage, id=self.response_id)


class FakeOpenAIClient:
    def __init__(self, *, parsed=None, error=None, usage=None, response_id="resp-test"):
        self.responses = FakeResponses(
            parsed=parsed,
            error=error,
            usage=usage,
            response_id=response_id,
        )


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

        self.assertEqual(result.output, parsed)
        self.assertEqual(result.usage["total_tokens"], None)
        self.assertEqual(result.response_id, "resp-test")
        self.assertEqual(client.responses.kwargs["model"], "gpt-test")
        self.assertEqual(client.responses.kwargs["instructions"], "Planner prompt")
        self.assertEqual(client.responses.kwargs["text_format"], DailyPlannerOutput)
        self.assertEqual(client.responses.kwargs["temperature"], 0.1)
        self.assertEqual(client.responses.kwargs["max_output_tokens"], settings.LLM_MAX_OUTPUT_TOKENS)
        self.assertIn("plan_context", client.responses.kwargs["input"])
        self.assertNotIn("mock_output", client.responses.kwargs["input"])
        self.assertNotIn("not-sent", client.responses.kwargs["input"])

    def test_generate_structured_extracts_usage_from_response(self):
        parsed = DailyPlannerOutput(
            mode="normal",
            strategy_summary="Keep a steady order.",
            primary_reason="The sequence balances value and capacity.",
            items=[],
            confidence=0.8,
        )
        client = FakeOpenAIClient(
            parsed=parsed,
            usage=SimpleNamespace(input_tokens=123, output_tokens=45, total_tokens=168),
            response_id="resp-usage",
        )
        provider = OpenAICompatibleProvider(client=client, model_name="gpt-test")

        result = provider.generate_structured(prompt="Planner prompt", schema=DailyPlannerOutput)

        self.assertEqual(result.output, parsed)
        self.assertEqual(result.usage["input_tokens"], 123)
        self.assertEqual(result.usage["output_tokens"], 45)
        self.assertEqual(result.usage["total_tokens"], 168)
        self.assertEqual(result.usage["cost_usd"], None)
        self.assertEqual(result.response_id, "resp-usage")

    def test_real_provider_guard_rejects_disallowed_model_before_request(self):
        original = {
            "AI_ENABLE_REAL_LLM": settings.AI_ENABLE_REAL_LLM,
            "LLM_ALLOWED_PROVIDERS": settings.LLM_ALLOWED_PROVIDERS,
            "LLM_ALLOWED_MODELS": settings.LLM_ALLOWED_MODELS,
            "LLM_MAX_OUTPUT_TOKENS": settings.LLM_MAX_OUTPUT_TOKENS,
        }
        client = FakeOpenAIClient(parsed={})
        provider = OpenAICompatibleProvider(client=client, model_name="expensive-model")
        try:
            settings.AI_ENABLE_REAL_LLM = True
            settings.LLM_ALLOWED_PROVIDERS = "openai"
            settings.LLM_ALLOWED_MODELS = "gpt-4.1-mini"
            settings.LLM_MAX_OUTPUT_TOKENS = 800

            with self.assertRaisesRegex(LLMProviderError, "LLM_ALLOWED_MODELS"):
                provider.generate_structured(prompt="Prompt", schema=DailyPlannerOutput)

            self.assertIsNone(client.responses.kwargs)
        finally:
            settings.AI_ENABLE_REAL_LLM = original["AI_ENABLE_REAL_LLM"]
            settings.LLM_ALLOWED_PROVIDERS = original["LLM_ALLOWED_PROVIDERS"]
            settings.LLM_ALLOWED_MODELS = original["LLM_ALLOWED_MODELS"]
            settings.LLM_MAX_OUTPUT_TOKENS = original["LLM_MAX_OUTPUT_TOKENS"]

    def test_real_provider_guard_rejects_disallowed_provider_before_request(self):
        original = {
            "AI_ENABLE_REAL_LLM": settings.AI_ENABLE_REAL_LLM,
            "LLM_ALLOWED_PROVIDERS": settings.LLM_ALLOWED_PROVIDERS,
            "LLM_ALLOWED_MODELS": settings.LLM_ALLOWED_MODELS,
            "LLM_MAX_OUTPUT_TOKENS": settings.LLM_MAX_OUTPUT_TOKENS,
        }
        client = FakeOpenAIClient(parsed={})
        provider = OpenAICompatibleProvider(
            client=client,
            provider_name="openai-compatible",
            model_name="gpt-4.1-mini",
        )
        try:
            settings.AI_ENABLE_REAL_LLM = True
            settings.LLM_ALLOWED_PROVIDERS = "openai"
            settings.LLM_ALLOWED_MODELS = "gpt-4.1-mini"
            settings.LLM_MAX_OUTPUT_TOKENS = 800

            with self.assertRaisesRegex(LLMProviderError, "LLM_ALLOWED_PROVIDERS"):
                provider.generate_structured(prompt="Prompt", schema=DailyPlannerOutput)

            self.assertIsNone(client.responses.kwargs)
        finally:
            settings.AI_ENABLE_REAL_LLM = original["AI_ENABLE_REAL_LLM"]
            settings.LLM_ALLOWED_PROVIDERS = original["LLM_ALLOWED_PROVIDERS"]
            settings.LLM_ALLOWED_MODELS = original["LLM_ALLOWED_MODELS"]
            settings.LLM_MAX_OUTPUT_TOKENS = original["LLM_MAX_OUTPUT_TOKENS"]

    def test_real_provider_guard_rejects_invalid_max_output_tokens_before_request(self):
        original = {
            "AI_ENABLE_REAL_LLM": settings.AI_ENABLE_REAL_LLM,
            "LLM_ALLOWED_PROVIDERS": settings.LLM_ALLOWED_PROVIDERS,
            "LLM_ALLOWED_MODELS": settings.LLM_ALLOWED_MODELS,
            "LLM_MAX_OUTPUT_TOKENS": settings.LLM_MAX_OUTPUT_TOKENS,
        }
        client = FakeOpenAIClient(parsed={})
        provider = OpenAICompatibleProvider(client=client, model_name="gpt-4.1-mini")
        try:
            settings.AI_ENABLE_REAL_LLM = True
            settings.LLM_ALLOWED_PROVIDERS = "openai"
            settings.LLM_ALLOWED_MODELS = "gpt-4.1-mini"
            settings.LLM_MAX_OUTPUT_TOKENS = 0

            with self.assertRaisesRegex(LLMProviderError, "LLM_MAX_OUTPUT_TOKENS"):
                provider.generate_structured(prompt="Prompt", schema=DailyPlannerOutput)

            self.assertIsNone(client.responses.kwargs)
        finally:
            settings.AI_ENABLE_REAL_LLM = original["AI_ENABLE_REAL_LLM"]
            settings.LLM_ALLOWED_PROVIDERS = original["LLM_ALLOWED_PROVIDERS"]
            settings.LLM_ALLOWED_MODELS = original["LLM_ALLOWED_MODELS"]
            settings.LLM_MAX_OUTPUT_TOKENS = original["LLM_MAX_OUTPUT_TOKENS"]

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
