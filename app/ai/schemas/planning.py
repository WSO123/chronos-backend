from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DailyPlannerItemOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    section: Literal["pinned", "recommended", "low_priority", "rolled_over"]
    sort_order: int = Field(ge=1)
    recommendation_reason: str = Field(min_length=1, max_length=500)


class DailyPlannerSuggestionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=300)
    signal: Literal["info", "watch", "risk", "positive"] = "info"


class DailyPlannerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["light", "normal", "sprint"]
    strategy_summary: str = Field(min_length=1, max_length=500)
    primary_reason: str = Field(min_length=1, max_length=500)
    items: list[DailyPlannerItemOutput]
    review_summary: str | None = Field(default=None, max_length=500)
    suggestions: list[DailyPlannerSuggestionOutput] = Field(default_factory=list, max_length=3)
    confidence: float = Field(default=0.7, ge=0, le=1)
