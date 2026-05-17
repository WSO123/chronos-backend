from __future__ import annotations

from app.ai.providers.base import LLMProvider
from app.ai.providers.mock import mock_llm_provider
from app.core.config import settings


class LLMProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}

    def register(self, provider: LLMProvider) -> None:
        self._providers[provider.provider_name] = provider

    def current_provider(self) -> LLMProvider:
        if not settings.AI_ENABLE_REAL_LLM:
            return self._providers["mock"]
        return self._providers.get(settings.LLM_PROVIDER) or self._providers["mock"]


llm_provider_registry = LLMProviderRegistry()
llm_provider_registry.register(mock_llm_provider)
