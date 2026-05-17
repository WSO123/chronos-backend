from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai.providers.base import LLMProvider
from app.ai.providers.registry import llm_provider_registry
from app.ai.prompts.registry import PromptRegistry, prompt_registry
from app.ai.schemas.planning import DailyPlannerOutput


@dataclass(frozen=True)
class DailyPlannerAgentResult:
    output: DailyPlannerOutput
    provider: str
    model: str
    prompt_version: str
    prompt_checksum: str
    usage: dict[str, Any]
    response_id: str | None = None


class DailyPlannerAgent:
    prompt_key = "daily_planner"

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
        plan_context: dict,
        candidates: list[dict],
        strategy_seed: dict,
        provider: LLMProvider | None = None,
    ) -> DailyPlannerAgentResult:
        resolved_provider = provider or llm_provider_registry.current_provider()
        prompt_template = self.prompts.get(self.prompt_key)
        generation = resolved_provider.generate_structured(
            prompt=prompt_template.content,
            schema=DailyPlannerOutput,
            temperature=0.2,
            metadata={
                "plan_context": plan_context,
                "candidates": candidates,
                "strategy_seed": strategy_seed,
                "prompt": {
                    "key": prompt_template.key,
                    "version": prompt_template.version,
                    "checksum": prompt_template.checksum,
                },
                "mock_output": self._mock_output(candidates=candidates, strategy_seed=strategy_seed),
            },
        )
        return DailyPlannerAgentResult(
            output=generation.output,
            provider=resolved_provider.provider_name,
            model=resolved_provider.model_name,
            prompt_version=prompt_template.version,
            prompt_checksum=prompt_template.checksum,
            usage=generation.usage,
            response_id=generation.response_id,
        )

    def _mock_output(self, *, candidates: list[dict], strategy_seed: dict) -> dict:
        return {
            "mode": strategy_seed["mode"],
            "strategy_summary": strategy_seed["summary"],
            "primary_reason": strategy_seed["primary_reason"],
            "items": [
                {
                    "task_id": candidate["task_id"],
                    "section": candidate["section"],
                    "sort_order": candidate["sort_order"],
                    "recommendation_reason": candidate["recommendation_reason"],
                }
                for candidate in candidates
            ],
            "confidence": 0.72,
        }


daily_planner_agent = DailyPlannerAgent()
