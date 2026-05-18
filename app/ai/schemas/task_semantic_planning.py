from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TaskSemanticPlanningOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    semantic_schema_version: str = Field(default="task-semantic-planning-v2", max_length=64)
    task_type: str = Field(default="general", min_length=1, max_length=64)
    complexity: Literal["low", "medium", "high"] = "medium"
    complexity_reason: str = Field(default="", max_length=255)
    cognitive_load: Literal["low", "medium", "high"] = "medium"
    energy_fit: Literal["low_energy", "steady", "high_energy"] = "steady"
    blocking_risk: Literal["low", "medium", "high"] = "medium"
    estimated_duration_min: int | None = Field(default=None, ge=1, le=480)
    duration_confidence: float = Field(default=0.6, ge=0, le=1)
    duration_reason: str = Field(default="", max_length=255)
    goal_alignment_score: float = Field(default=0.5, ge=0, le=1)
    goal_progress_impact: Literal["none", "small", "medium", "large"] = "small"
    goal_relevance_reason: str = Field(default="", max_length=255)
    semantic_priority_score: float = Field(default=0.5, ge=0, le=1)
    breakdown_recommended: bool = False
    minimum_viable_step: str | None = Field(default=None, max_length=255)
    minimum_viable_minutes: int | None = Field(default=None, ge=5, le=120)
    semantic_summary: str = Field(default="", max_length=500)
    confidence: float = Field(default=0.6, ge=0, le=1)
