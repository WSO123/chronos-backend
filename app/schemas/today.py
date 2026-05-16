from datetime import date
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    DailyPlanItemSection,
    DailyPlanItemStatus,
    PlanningPreference,
    TaskStatus,
    ValueLevel,
)


class TodayStrategyResponse(BaseModel):
    strategy_snapshot_id: uuid.UUID
    summary: str
    mode: PlanningPreference
    primary_reason: str


class TodayProgressResponse(BaseModel):
    completed_count: int
    total_count: int
    focus_minutes: int
    completion_rate: float


class TodayTaskResponse(BaseModel):
    daily_plan_item_id: uuid.UUID
    task_id: uuid.UUID
    title: str
    goal_id: uuid.UUID | None
    sort_order: int
    section: DailyPlanItemSection
    recommendation_reason: str
    estimated_duration_min: int | None
    item_status: DailyPlanItemStatus
    task_status: TaskStatus
    priority: int
    value_level: ValueLevel
    deadline: date | None


class TodaySectionsResponse(BaseModel):
    pinned_tasks: list[TodayTaskResponse] = Field(default_factory=list)
    recommended_tasks: list[TodayTaskResponse] = Field(default_factory=list)
    low_priority_tasks: list[TodayTaskResponse] = Field(default_factory=list)
    rolled_over_tasks: list[TodayTaskResponse] = Field(default_factory=list)


class TodayQuickActionsResponse(BaseModel):
    can_replan: bool
    can_capture: bool
    can_view_report: bool


class TodayResponse(BaseModel):
    date: date
    greeting: str
    daily_plan_id: uuid.UUID
    plan_version: int
    strategy: TodayStrategyResponse
    progress: TodayProgressResponse
    sections: TodaySectionsResponse
    quick_actions: TodayQuickActionsResponse


class TodayReplanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500)


class TodayItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: DailyPlanItemStatus
