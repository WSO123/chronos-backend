from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class InsightPatternOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    signal: str = Field(min_length=1, max_length=40)
    evidence: str = Field(min_length=1, max_length=300)
    suggestion: str = Field(min_length=1, max_length=300)


class InsightRecommendationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    suggestion: str = Field(min_length=1, max_length=300)
    rationale: str = Field(min_length=1, max_length=300)


class InsightDetailOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    behavior_patterns: list[InsightPatternOutput] = Field(min_length=1, max_length=5)
    recommendations: list[InsightRecommendationOutput] = Field(min_length=1, max_length=3)
    strategy_notes: list[str] = Field(min_length=1, max_length=3)
    confidence: float = Field(default=0.7, ge=0, le=1)
