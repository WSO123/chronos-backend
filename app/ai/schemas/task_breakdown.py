from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TaskBreakdownStepOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    sort_order: int = Field(ge=1, le=12)
    rationale: str | None = Field(default=None, max_length=500)


class TaskBreakdownOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    steps: list[TaskBreakdownStepOutput] = Field(min_length=1, max_length=6)
    confidence: float = Field(default=0.7, ge=0, le=1)
    summary: str | None = Field(default=None, max_length=500)
