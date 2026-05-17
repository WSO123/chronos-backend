from __future__ import annotations

from dataclasses import dataclass

from app.ai.providers.base import LLMProvider
from app.ai.providers.registry import llm_provider_registry
from app.ai.schemas.planning import DailyPlannerOutput


@dataclass(frozen=True)
class DailyPlannerAgentResult:
    output: DailyPlannerOutput
    provider: str
    model: str
    prompt_version: str


class DailyPlannerAgent:
    prompt_version = "p2-daily-planner-agent-v1"

    def run(
        self,
        *,
        plan_context: dict,
        candidates: list[dict],
        strategy_seed: dict,
        provider: LLMProvider | None = None,
    ) -> DailyPlannerAgentResult:
        resolved_provider = provider or llm_provider_registry.current_provider()
        output = resolved_provider.generate_structured(
            prompt=self._prompt(),
            schema=DailyPlannerOutput,
            temperature=0.2,
            metadata={
                "plan_context": plan_context,
                "candidates": candidates,
                "strategy_seed": strategy_seed,
                "mock_output": self._mock_output(candidates=candidates, strategy_seed=strategy_seed),
            },
        )
        return DailyPlannerAgentResult(
            output=output,
            provider=resolved_provider.provider_name,
            model=resolved_provider.model_name,
            prompt_version=self.prompt_version,
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

    def _prompt(self) -> str:
        return (
            "You are Chronos Daily Planner. Return structured planning suggestions only. "
            "Do not create tasks, delete data, bypass user confirmation, or ignore capacity and dependency constraints."
        )


daily_planner_agent = DailyPlannerAgent()
