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
        review_context: dict | None = None,
        provider: LLMProvider | None = None,
    ) -> DailyPlannerAgentResult:
        resolved_provider = provider or llm_provider_registry.current_provider()
        prompt_template = self.prompts.get(self.prompt_key)
        resolved_review_context = review_context or {}
        generation = resolved_provider.generate_structured(
            prompt=prompt_template.content,
            schema=DailyPlannerOutput,
            temperature=0.2,
            metadata={
                "plan_context": plan_context,
                "candidates": candidates,
                "strategy_seed": strategy_seed,
                "review_context": resolved_review_context,
                "prompt": {
                    "key": prompt_template.key,
                    "version": prompt_template.version,
                    "checksum": prompt_template.checksum,
                },
                "mock_output": self._mock_output(
                    candidates=candidates,
                    strategy_seed=strategy_seed,
                    review_context=resolved_review_context,
                ),
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

    def _mock_output(self, *, candidates: list[dict], strategy_seed: dict, review_context: dict) -> dict:
        capacity = review_context.get("capacity") if isinstance(review_context, dict) else {}
        workload = review_context.get("workload") if isinstance(review_context, dict) else {}
        user_feedback = review_context.get("user_feedback") if isinstance(review_context, dict) else {}
        if not isinstance(capacity, dict):
            capacity = {}
        if not isinstance(workload, dict):
            workload = {}
        if not isinstance(user_feedback, dict):
            user_feedback = {}

        suggestions: list[dict] = [
            {
                "key": "start_with_first_task",
                "title": "先开始第一项",
                "message": "当前排序已经可执行，先从主序列第一项开始，完成后再看下一步。",
                "signal": "positive",
            }
        ]
        daily_capacity_minutes = int(capacity.get("daily_capacity_minutes") or 0)
        selected_estimated_minutes = int(workload.get("selected_estimated_minutes") or 0)
        capacity_source = str(capacity.get("capacity_source") or "")
        if capacity_source == "manual_today_override" and daily_capacity_minutes:
            suggestions.append(
                {
                    "key": "manual_capacity_respected",
                    "title": "按可用时间执行",
                    "message": f"你今天设定了 {daily_capacity_minutes} 分钟可用时间，主序列约 {selected_estimated_minutes} 分钟，先按这个边界开始。",
                    "signal": "positive",
                }
            )
        elif capacity.get("energy_capacity_adjusted") and daily_capacity_minutes:
            suggestions.append(
                {
                    "key": "energy_capacity_respected",
                    "title": "保持轻量边界",
                    "message": f"今天容量已收敛到 {daily_capacity_minutes} 分钟，用来匹配当前精力，先不要把滚动任务拉回。",
                    "signal": "watch",
                }
            )
        rolled_over_count = len([candidate for candidate in candidates if candidate["section"] == "rolled_over"])
        if rolled_over_count:
            rolled_over_minutes = int(workload.get("rolled_over_estimated_minutes") or 0)
            minutes_suffix = f"，约 {rolled_over_minutes} 分钟" if rolled_over_minutes else ""
            ignored_keys = set(user_feedback.get("top_ignored_keys") or [])
            preference_summary = user_feedback.get("preference_summary") or {}
            preference_key = (
                preference_summary.get("key")
                if isinstance(preference_summary, dict)
                else None
            )
            if preference_key in {"capacity_flexibility_preferred", "capacity_flexibility_emerging"} or "respect_rollover" in ignored_keys:
                suggestions.append(
                    {
                        "key": "adjust_capacity_if_needed",
                        "title": "需要时再加容量",
                        "message": f"{rolled_over_count} 个任务仍被后移{minutes_suffix}；如果你今天确实想多推进，先手动增加可用时间再重新编排。",
                        "signal": "watch",
                    }
                )
            else:
                suggestions.append(
                    {
                        "key": "respect_rollover",
                        "title": "保持滚动边界",
                        "message": f"{rolled_over_count} 个任务已后移{minutes_suffix}，今天先保护主序列，不急着全部拉回。",
                        "signal": "watch",
                    }
                )
        review_summary = "Planning Engine 的排序可以直接执行，LLM 只补充轻量审阅，不改变任务顺序。"
        if capacity_source == "manual_today_override" and daily_capacity_minutes:
            review_summary = f"Planning Engine 已按你今天 {daily_capacity_minutes} 分钟可用时间收敛主序列，LLM 只补充审阅，不改变任务顺序。"
        elif capacity.get("energy_capacity_adjusted") and daily_capacity_minutes:
            review_summary = f"Planning Engine 已按低精力状态把主序列收敛到 {daily_capacity_minutes} 分钟，LLM 只补充审阅，不改变任务顺序。"
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
            "review_summary": review_summary,
            "suggestions": suggestions[:3],
            "confidence": 0.72,
        }


daily_planner_agent = DailyPlannerAgent()
