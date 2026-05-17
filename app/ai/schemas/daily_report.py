from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DailyReportOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ai_summary: str = Field(min_length=1, max_length=500)
    ai_suggestions: list[str] = Field(min_length=1, max_length=3)
    confidence: float = Field(default=0.7, ge=0, le=1)
