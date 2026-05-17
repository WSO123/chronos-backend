from __future__ import annotations

from app.ai.providers.base import LLMProviderError
from app.core.config import settings


def validate_real_llm_request(provider_name: str, model_name: str) -> None:
    if not settings.AI_ENABLE_REAL_LLM:
        return

    allowed_providers = _csv_values(settings.LLM_ALLOWED_PROVIDERS)
    if provider_name not in allowed_providers:
        raise LLMProviderError(
            f"LLM provider '{provider_name}' is not allowed by LLM_ALLOWED_PROVIDERS."
        )

    allowed_models = _csv_values(settings.LLM_ALLOWED_MODELS)
    if not allowed_models:
        raise LLMProviderError("LLM_ALLOWED_MODELS must include at least one model when real LLM is enabled.")
    if model_name not in allowed_models:
        raise LLMProviderError(f"LLM model '{model_name}' is not allowed by LLM_ALLOWED_MODELS.")

    if settings.LLM_MAX_OUTPUT_TOKENS <= 0:
        raise LLMProviderError("LLM_MAX_OUTPUT_TOKENS must be a positive integer.")


def _csv_values(raw: str | None) -> set[str]:
    return {value.strip() for value in (raw or "").split(",") if value.strip()}
