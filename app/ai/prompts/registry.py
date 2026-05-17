from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from importlib import resources


@dataclass(frozen=True)
class PromptSpec:
    key: str
    version: str
    resource_path: str


@dataclass(frozen=True)
class PromptTemplate:
    key: str
    version: str
    content: str
    checksum: str


class PromptRegistryError(RuntimeError):
    pass


class PromptRegistry:
    def __init__(self, specs: dict[str, PromptSpec] | None = None) -> None:
        self._specs = specs or {}
        self._cache: dict[str, PromptTemplate] = {}

    def get(self, key: str) -> PromptTemplate:
        if key in self._cache:
            return self._cache[key]
        spec = self._specs.get(key)
        if spec is None:
            raise PromptRegistryError(f"Prompt spec not found: {key}")
        content = self._read_prompt(spec.resource_path)
        template = PromptTemplate(
            key=spec.key,
            version=spec.version,
            content=content,
            checksum=sha256(content.encode("utf-8")).hexdigest(),
        )
        self._cache[key] = template
        return template

    def _read_prompt(self, resource_path: str) -> str:
        try:
            resource = resources.files("app.ai.prompts")
            for part in resource_path.split("/"):
                resource = resource.joinpath(part)
            return resource.read_text(encoding="utf-8").strip()
        except FileNotFoundError as exc:
            raise PromptRegistryError(f"Prompt file not found: {resource_path}") from exc


prompt_registry = PromptRegistry(
    {
        "daily_planner": PromptSpec(
            key="daily_planner",
            version="p2-daily-planner-agent-v1",
            resource_path="daily_planner/p2-daily-planner-agent-v1.md",
        )
    }
)
