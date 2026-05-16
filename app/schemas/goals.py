from datetime import date
from decimal import Decimal
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import GoalHomeFilter, GoalStatus, TaskStatus, ValueLevel
from app.schemas.common import TimestampedResponse


class GoalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    deadline: date | None = None
    value_level: ValueLevel = ValueLevel.MEDIUM


class GoalUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    deadline: date | None = None
    value_level: ValueLevel | None = None
    status: GoalStatus | None = None


class GoalResponse(TimestampedResponse):
    user_id: uuid.UUID
    title: str
    description: str | None
    deadline: date | None
    value_level: ValueLevel
    status: GoalStatus


class GoalTaskSummaryResponse(BaseModel):
    id: uuid.UUID
    title: str
    deadline: date | None
    estimated_duration_min: int | None
    actual_duration_min: int
    priority: int
    value_level: ValueLevel
    progress: Decimal
    status: TaskStatus
    step_count: int
    completed_step_count: int


class GoalProgressResponse(BaseModel):
    total_task_count: int
    unfinished_task_count: int
    completed_task_count: int
    postponed_task_count: int
    completion_rate: float
    total_estimated_duration_min: int
    total_actual_duration_min: int
    risk_level: str
    risk_reason: str


class GoalTaskListResponse(BaseModel):
    unfinished_tasks: list[GoalTaskSummaryResponse] = Field(default_factory=list)
    completed_tasks: list[GoalTaskSummaryResponse] = Field(default_factory=list)
    recommended_next_task: GoalTaskSummaryResponse | None


class GoalDependencyNodeResponse(BaseModel):
    task_id: uuid.UUID
    title: str
    status: TaskStatus
    sort_order: int


class GoalDependencyEdgeResponse(BaseModel):
    from_task_id: uuid.UUID
    to_task_id: uuid.UUID
    reason: str | None = None


class GoalDependencyMapResponse(BaseModel):
    nodes: list[GoalDependencyNodeResponse] = Field(default_factory=list)
    edges: list[GoalDependencyEdgeResponse] = Field(default_factory=list)
    note: str


class GoalAISuggestionResponse(BaseModel):
    source: str
    summary: str
    next_action_task_id: uuid.UUID | None
    risk_warning: str | None
    suggestions: list[str] = Field(default_factory=list)


class GoalActionsResponse(BaseModel):
    can_add_task: bool
    can_edit_goal: bool
    can_mark_complete: bool


class GoalDetailResponse(BaseModel):
    overview: GoalResponse
    progress: GoalProgressResponse
    task_list: GoalTaskListResponse
    dependency_map: GoalDependencyMapResponse
    ai_suggestion: GoalAISuggestionResponse
    actions: GoalActionsResponse


class GoalHomeItemResponse(BaseModel):
    id: uuid.UUID
    title: str
    deadline: date | None
    value_level: ValueLevel
    status: GoalStatus
    progress: float
    risk_level: str
    risk_reason: str
    associated_task_count: int
    unfinished_task_count: int
    completed_task_count: int
    recommended_next_task_id: uuid.UUID | None


class GoalHomeSummaryResponse(BaseModel):
    total_goal_count: int
    active_goal_count: int
    completed_goal_count: int
    due_soon_goal_count: int
    high_value_goal_count: int
    at_risk_goal_count: int
    weekly_completed_task_count: int
    weekly_touched_goal_count: int


class GoalHomeFilterCountsResponse(BaseModel):
    all: int
    active: int
    due_soon: int
    completed: int
    high_value: int


class GoalsHomeResponse(BaseModel):
    selected_filter: GoalHomeFilter
    summary: GoalHomeSummaryResponse
    filters: GoalHomeFilterCountsResponse
    goals: list[GoalHomeItemResponse] = Field(default_factory=list)
