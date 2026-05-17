from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StrategyExplanationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explanation: list[str] = Field(min_length=1, max_length=4)
    confidence: float = Field(default=0.7, ge=0, le=1)
    summary: str | None = Field(default=None, max_length=500)
