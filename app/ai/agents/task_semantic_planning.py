from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai.prompts.registry import PromptRegistry, prompt_registry
from app.ai.providers.base import LLMProvider
from app.ai.providers.registry import llm_provider_registry
from app.ai.schemas.task_semantic_planning import TaskSemanticPlanningOutput


@dataclass(frozen=True)
class TaskSemanticPlanningAgentResult:
    output: TaskSemanticPlanningOutput
    provider: str
    model: str
    prompt_version: str
    prompt_checksum: str
    usage: dict[str, Any]
    response_id: str | None = None


class TaskSemanticPlanningAgent:
    prompt_key = "task_semantic_planning"

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
        task_context: dict,
        fallback_output: dict,
        provider: LLMProvider | None = None,
    ) -> TaskSemanticPlanningAgentResult:
        resolved_provider = provider or llm_provider_registry.current_provider()
        prompt_template = self.prompts.get(self.prompt_key)
        generation = resolved_provider.generate_structured(
            prompt=prompt_template.content,
            schema=TaskSemanticPlanningOutput,
            temperature=0.1,
            metadata={
                "task": task_context,
                "prompt": {
                    "key": prompt_template.key,
                    "version": prompt_template.version,
                    "checksum": prompt_template.checksum,
                },
                "mock_output": fallback_output,
            },
        )
        return TaskSemanticPlanningAgentResult(
            output=generation.output,
            provider=resolved_provider.provider_name,
            model=resolved_provider.model_name,
            prompt_version=prompt_template.version,
            prompt_checksum=prompt_template.checksum,
            usage=generation.usage,
            response_id=generation.response_id,
        )


task_semantic_planning_agent = TaskSemanticPlanningAgent()
