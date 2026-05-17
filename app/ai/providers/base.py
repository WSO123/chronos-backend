from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, Protocol, TypeVar

from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)


class LLMProviderError(RuntimeError):
    pass


def empty_llm_usage() -> dict[str, Any]:
    return {
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "cost_usd": None,
    }


@dataclass(frozen=True)
class LLMStructuredGeneration(Generic[T]):
    output: T
    usage: dict[str, Any]
    response_id: str | None = None
    raw_metadata: dict[str, Any] | None = None


class LLMProvider(Protocol):
    provider_name: str
    model_name: str

    def generate_structured(
        self,
        *,
        prompt: str,
        schema: type[T],
        temperature: float = 0.2,
        metadata: dict | None = None,
    ) -> LLMStructuredGeneration[T]:
        ...
