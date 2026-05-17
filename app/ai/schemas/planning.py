from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DailyPlannerItemOutput(BaseModel):
    task_id: str
    section: Literal["pinned", "recommended", "low_priority", "rolled_over"]
    sort_order: int = Field(ge=1)
    recommendation_reason: str = Field(min_length=1, max_length=500)


class DailyPlannerOutput(BaseModel):
    mode: Literal["light", "normal", "sprint"]
    strategy_summary: str = Field(min_length=1, max_length=500)
    primary_reason: str = Field(min_length=1, max_length=500)
    items: list[DailyPlannerItemOutput]
    confidence: float = Field(default=0.7, ge=0, le=1)
