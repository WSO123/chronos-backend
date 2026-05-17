from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai.providers.base import LLMProvider
from app.ai.providers.registry import llm_provider_registry
from app.ai.prompts.registry import PromptRegistry, prompt_registry
from app.ai.schemas.daily_report import DailyReportOutput


@dataclass(frozen=True)
class DailyReportAgentResult:
    output: DailyReportOutput
    provider: str
    model: str
    prompt_version: str
    prompt_checksum: str
    usage: dict[str, Any]
    response_id: str | None = None


class DailyReportAgent:
    prompt_key = "daily_report"

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
        report_context: dict,
        fallback_output: dict,
        provider: LLMProvider | None = None,
    ) -> DailyReportAgentResult:
        resolved_provider = provider or llm_provider_registry.current_provider()
        prompt_template = self.prompts.get(self.prompt_key)
        generation = resolved_provider.generate_structured(
            prompt=prompt_template.content,
            schema=DailyReportOutput,
            temperature=0.2,
            metadata={
                "report": report_context,
                "prompt": {
                    "key": prompt_template.key,
                    "version": prompt_template.version,
                    "checksum": prompt_template.checksum,
                },
                "mock_output": fallback_output,
            },
        )
        return DailyReportAgentResult(
            output=generation.output,
            provider=resolved_provider.provider_name,
            model=resolved_provider.model_name,
            prompt_version=prompt_template.version,
            prompt_checksum=prompt_template.checksum,
            usage=generation.usage,
            response_id=generation.response_id,
        )


daily_report_agent = DailyReportAgent()
