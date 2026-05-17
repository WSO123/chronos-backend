from __future__ import annotations

from pydantic import BaseModel

from app.ai.providers.base import LLMProviderError, T


class MockLLMProvider:
    provider_name = "mock"
    model_name = "structured-mock-v1"

    def generate_structured(
        self,
        *,
        prompt: str,
        schema: type[T],
        temperature: float = 0.2,
        metadata: dict | None = None,
    ) -> T:
        del prompt, temperature
        mock_output = (metadata or {}).get("mock_output")
        if mock_output is None:
            raise LLMProviderError("Mock provider requires metadata.mock_output")
        if isinstance(mock_output, BaseModel):
            mock_output = mock_output.model_dump()
        return schema.model_validate(mock_output)


mock_llm_provider = MockLLMProvider()
