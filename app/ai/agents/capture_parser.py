from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai.providers.base import LLMProvider
from app.ai.providers.registry import llm_provider_registry
from app.ai.prompts.registry import PromptRegistry, prompt_registry
from app.ai.schemas.capture import CaptureParserOutput


@dataclass(frozen=True)
class CaptureParserAgentResult:
    output: CaptureParserOutput
    provider: str
    model: str
    prompt_version: str
    prompt_checksum: str
    usage: dict[str, Any]
    response_id: str | None = None


class CaptureParserAgent:
    prompt_key = "capture_parser"

    def __init__(self, *, prompts: PromptRegistry | None = None) -> None:
        self.prompts = prompts or prompt_registry

    @property
    def prompt_version(self) -> str:
        return self.prompts.get(self.prompt_key).version

    @property
    def prompt_checksum(self) -> str:
        return self.prompts.get(self.prompt_key).checksum

    def run(
        self,
        *,
        raw_text: str,
        input_type: str,
        source: str,
        parse_context: dict | None = None,
        fallback_output: dict | None = None,
        provider: LLMProvider | None = None,
    ) -> CaptureParserAgentResult:
        resolved_provider = provider or llm_provider_registry.current_provider()
        prompt_template = self.prompts.get(self.prompt_key)
        generation = resolved_provider.generate_structured(
            prompt=prompt_template.content,
            schema=CaptureParserOutput,
            temperature=0.1,
            metadata={
                "capture": {
                    "raw_text": raw_text,
                    "input_type": input_type,
                    "source": source,
                    "context": parse_context or {},
                },
                "prompt": {
                    "key": prompt_template.key,
                    "version": prompt_template.version,
                    "checksum": prompt_template.checksum,
                },
                "mock_output": fallback_output or self._unknown_output(raw_text),
            },
        )
        return CaptureParserAgentResult(
            output=generation.output,
            provider=resolved_provider.provider_name,
            model=resolved_provider.model_name,
            prompt_version=prompt_template.version,
            prompt_checksum=prompt_template.checksum,
            usage=generation.usage,
            response_id=generation.response_id,
        )

    def _unknown_output(self, raw_text: str) -> dict:
        return {
            "result_type": "unknown",
            "item_type": "unknown",
            "title": " ".join(raw_text.strip().split())[:255] or "Untitled input",
            "description": None,
            "estimated_duration_min": None,
            "suggested_priority": None,
            "suggested_deadline": None,
            "confidence": 0.2,
            "rationale": "Fallback output used when no mock output is supplied.",
        }


capture_parser_agent = CaptureParserAgent()
