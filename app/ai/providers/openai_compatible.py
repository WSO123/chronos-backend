from __future__ import annotations

import json
from typing import Any

from openai import OpenAI, OpenAIError
from pydantic import ValidationError

from app.ai.providers.base import LLMProviderError, LLMStructuredGeneration, T, empty_llm_usage
from app.core.config import settings


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        client: Any | None = None,
        provider_name: str = "openai",
        model_name: str | None = None,
    ) -> None:
        self.provider_name = provider_name
        self._client = client
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        return self._model_name or settings.LLM_MODEL

    def generate_structured(
        self,
        *,
        prompt: str,
        schema: type[T],
        temperature: float = 0.2,
        metadata: dict | None = None,
    ) -> LLMStructuredGeneration[T]:
        try:
            response = self._client_instance().responses.parse(
                model=self.model_name,
                instructions=prompt,
                input=self._input_from_metadata(metadata),
                text_format=schema,
                temperature=temperature,
            )
            parsed = getattr(response, "output_parsed", None)
            if parsed is None:
                raise LLMProviderError("OpenAI provider returned no parsed output")
            if isinstance(parsed, schema):
                output = parsed
            else:
                output = schema.model_validate(parsed)
            return LLMStructuredGeneration(
                output=output,
                usage=self._usage_from_response(response),
                response_id=self._response_id(response),
                raw_metadata={"provider_mode": self.provider_name},
            )
        except LLMProviderError:
            raise
        except (OpenAIError, ValidationError, ValueError, TypeError) as exc:
            raise LLMProviderError(f"OpenAI provider structured generation failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 - provider clients can raise transport-specific exceptions.
            raise LLMProviderError(f"OpenAI provider structured generation failed: {exc}") from exc

    def _client_instance(self) -> Any:
        if self._client is not None:
            return self._client
        if not settings.LLM_API_KEY:
            raise LLMProviderError("LLM_API_KEY is required when AI_ENABLE_REAL_LLM=true")

        kwargs: dict[str, Any] = {
            "api_key": settings.LLM_API_KEY,
            "timeout": settings.LLM_TIMEOUT_SECONDS,
            "max_retries": settings.LLM_MAX_RETRIES,
        }
        if settings.LLM_BASE_URL:
            kwargs["base_url"] = settings.LLM_BASE_URL
        self._client = OpenAI(**kwargs)
        return self._client

    def _input_from_metadata(self, metadata: dict | None) -> str:
        public_metadata = {
            key: value
            for key, value in (metadata or {}).items()
            if key not in {"mock_output", "prompt"}
        }
        return (
            "Use the following JSON context to produce the requested structured output. "
            "Respect the system prompt and the schema exactly.\n\n"
            f"{json.dumps(public_metadata, ensure_ascii=False, default=str)}"
        )

    def _usage_from_response(self, response: Any) -> dict[str, Any]:
        usage = getattr(response, "usage", None)
        if usage is None:
            return empty_llm_usage()

        input_tokens = self._usage_int(usage, "input_tokens", "prompt_tokens")
        output_tokens = self._usage_int(usage, "output_tokens", "completion_tokens")
        total_tokens = self._usage_int(usage, "total_tokens")
        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost_usd": None,
        }

    def _usage_int(self, usage: Any, *keys: str) -> int | None:
        for key in keys:
            value = self._value_from_object(usage, key)
            if value is None:
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
        return None

    def _response_id(self, response: Any) -> str | None:
        value = self._value_from_object(response, "id")
        return str(value) if value else None

    def _value_from_object(self, obj: Any, key: str) -> Any:
        if isinstance(obj, dict):
            return obj.get(key)
        if hasattr(obj, "model_dump"):
            dumped = obj.model_dump()
            if isinstance(dumped, dict) and key in dumped:
                return dumped[key]
        return getattr(obj, key, None)


openai_provider = OpenAICompatibleProvider()
openai_compatible_provider = OpenAICompatibleProvider(provider_name="openai-compatible")
