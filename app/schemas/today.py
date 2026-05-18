from datetime import date, datetime
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    DailyPlanItemSection,
    DailyPlanItemStatus,
    PlanningPreference,
    PlanRevisionTrigger,
    TaskStatus,
    ValueLevel,
)
from app.schemas.goal_feedback import GoalProgressFeedbackItemResponse


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
    score_breakdown: dict = Field(default_factory=dict)
    goal_progress_feedback: GoalProgressFeedbackItemResponse | None = None


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
    base_capacity_minutes: int = 0
    daily_capacity_minutes: int
    capacity_source: str = "planning_preference"
    manual_available_minutes: int | None = None
    energy_capacity_adjusted: bool = False
    selected_estimated_minutes: int
    rolled_over_estimated_minutes: int
    over_capacity_minutes: int
    capacity_status: str
    dependency_protected_count: int
    goal_next_action_count: int = 0
    goal_progress_signal_count: int = 0
    user_adjusted_count: int
    semantic_signal_count: int = 0
    semantic_protected_count: int = 0
    minimum_viable_progress_count: int = 0
    execution_feedback_count: int = 0
    personalization_signal_count: int = 0
    energy_level: str
    energy_applied: bool
    planner_agent_latency_ms: int | None = None
    planner_agent_failure_type: str | None = None
    completed_count: int
    focus_minutes: int


class StrategyDetailSourceResponse(BaseModel):
    strategy_snapshot_id: uuid.UUID
    ai_job_id: uuid.UUID | None = None
    model_name: str | None
    prompt_version: str | None
    generated_at: datetime
    explanation_ai_job_id: uuid.UUID | None = None
    explanation_model_name: str | None = None
    explanation_prompt_version: str | None = None
    explanation_status: str | None = None


class StrategyDetailEnergyResponse(BaseModel):
    has_data: bool
    metric_date: date
    energy_score: int | None
    energy_level: str
    recommended_mode: str
    explanation: str
    applied_to_plan: bool
    source: str


class StrategyScoreSignalResponse(BaseModel):
    key: str
    title: str
    message: str
    signal: str
    score: int | None = None


class StrategyScoreExplanationResponse(BaseModel):
    summary: str
    signals: list[StrategyScoreSignalResponse] = Field(default_factory=list)
    source: str


class StrategyPlannerSuggestionResponse(BaseModel):
    key: str
    title: str
    message: str
    signal: str


class PlannerUserLearningContractResponse(BaseModel):
    version: str
    scope: str
    source_of_truth: str
    can_affect: list[str] = Field(default_factory=list)
    cannot_affect: list[str] = Field(default_factory=list)
    plan_mutation_allowed: bool
    requires_explicit_user_action: bool
    explanation: str


class StrategyPlannerFeedbackSummaryResponse(BaseModel):
    key: str
    title: str
    message: str
    signal: str
    confidence: float
    evidence_count: int
    source: str
    learning_contract: PlannerUserLearningContractResponse


class StrategyPlannerReviewResponse(BaseModel):
    summary: str | None = None
    suggestions: list[StrategyPlannerSuggestionResponse] = Field(default_factory=list)
    feedback_summary: StrategyPlannerFeedbackSummaryResponse | None = None
    source: str


class PlannerReviewFeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suggestion_key: str = Field(min_length=1, max_length=80)
    action: Literal["accepted", "ignored"]
    note: str | None = Field(default=None, max_length=300)


class PlannerReviewFeedbackResponse(BaseModel):
    plan_date: date
    daily_plan_id: uuid.UUID
    plan_version: int
    suggestion_key: str
    action: Literal["accepted", "ignored"]
    feedback_event_id: uuid.UUID
    learning_signal: str
    applied_to_plan: bool
    replan_triggered: bool
    learning_contract: PlannerUserLearningContractResponse
    source: str


class StrategyTaskRationaleResponse(TodayTaskResponse):
    dominant_factor: str
    dominant_reason: str
    score_signals: list[StrategyScoreSignalResponse] = Field(default_factory=list)


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
    energy: StrategyDetailEnergyResponse
    score_explanation: StrategyScoreExplanationResponse
    planner_review: StrategyPlannerReviewResponse | None = None
    task_rationales: list[StrategyTaskRationaleResponse]
    source: StrategyDetailSourceResponse


class TodayReplanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500)
    available_minutes: int | None = Field(default=None, ge=15, le=720)


class TodayPlanningSignalsPrepareResponse(BaseModel):
    plan_date: date
    task_count: int
    generated_count: int
    existing_count: int
    stale_count: int = 0
    skipped_count: int
    replanned: bool
    planning_signal_ids: list[uuid.UUID] = Field(default_factory=list)
    ai_job_ids: list[uuid.UUID] = Field(default_factory=list)
    today: TodayResponse


class TodayItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: DailyPlanItemStatus
