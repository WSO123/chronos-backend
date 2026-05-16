from datetime import date, datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    DailyPlanItemSection,
    DailyPlanItemStatus,
    PlanningPreference,
    PlanRevisionTrigger,
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


class TodayInsightMessageResponse(BaseModel):
    key: str
    title: str
    message: str
    signal: str
    task_id: uuid.UUID | None = None


class TodayInsightsPreviewResponse(BaseModel):
    risk_alerts: list[TodayInsightMessageResponse] = Field(default_factory=list)
    remaining_time_suggestion: TodayInsightMessageResponse
    adjustment_suggestions: list[TodayInsightMessageResponse] = Field(default_factory=list)
    source: str


class TodayResponse(BaseModel):
    date: date
    greeting: str
    daily_plan_id: uuid.UUID
    plan_version: int
    strategy: TodayStrategyResponse
    progress: TodayProgressResponse
    sections: TodaySectionsResponse
    insights_preview: TodayInsightsPreviewResponse
    quick_actions: TodayQuickActionsResponse


class StrategyDetailRevisionResponse(BaseModel):
    plan_revision_id: uuid.UUID
    version: int
    trigger: PlanRevisionTrigger
    reason: str | None
    created_at: datetime


class StrategyDetailFactorsResponse(BaseModel):
    task_count: int
    high_value_task_count: int
    pinned_count: int
    recommended_count: int
    low_priority_count: int
    rolled_over_count: int
    total_estimated_minutes: int
    dependency_protected_count: int
    user_adjusted_count: int
    completed_count: int
    focus_minutes: int


class StrategyDetailSourceResponse(BaseModel):
    strategy_snapshot_id: uuid.UUID
    model_name: str | None
    prompt_version: str | None
    generated_at: datetime


class StrategyDetailResponse(BaseModel):
    date: date
    daily_plan_id: uuid.UUID
    plan_version: int
    summary: str
    mode: PlanningPreference
    primary_reason: str
    revision: StrategyDetailRevisionResponse
    factors: StrategyDetailFactorsResponse
    explanation: list[str]
    task_rationales: list[TodayTaskResponse]
    source: StrategyDetailSourceResponse


class TodayReplanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500)


class TodayItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: DailyPlanItemStatus
