from datetime import date, datetime
from decimal import Decimal
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import (
    AIJobStatus,
    AIJobType,
    ActorType,
    CaptureSource,
    DailyPlanItemSection,
    DailyPlanItemStatus,
    EntityType,
    EventSource,
    TaskSource,
    TaskStatus,
    ValueLevel,
)
from app.schemas.common import ORMModel, TimestampedResponse


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    goal_id: uuid.UUID | None = None
    estimated_duration_min: int | None = Field(default=None, ge=1)
    priority: int = Field(default=3, ge=1, le=5)
    value_level: ValueLevel = ValueLevel.MEDIUM
    deadline: date | None = None


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    goal_id: uuid.UUID | None = None
    estimated_duration_min: int | None = Field(default=None, ge=1)
    priority: int | None = Field(default=None, ge=1, le=5)
    value_level: ValueLevel | None = None
    deadline: date | None = None


class TaskPriorityAdjust(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: int | None = Field(default=None, ge=1, le=5)
    value_level: ValueLevel | None = None
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def require_priority_or_value_level(self) -> "TaskPriorityAdjust":
        if self.priority is None and self.value_level is None:
            raise ValueError("priority or value_level is required")
        return self


class TaskStepCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    sort_order: int = Field(default=0, ge=0)


class TaskStepResponse(TimestampedResponse):
    task_id: uuid.UUID
    title: str
    sort_order: int
    is_completed: bool
    completed_at: datetime | None


class TaskResponse(TimestampedResponse):
    user_id: uuid.UUID
    goal_id: uuid.UUID | None
    title: str
    description: str | None
    estimated_duration_min: int | None
    actual_duration_min: int
    priority: int
    value_level: ValueLevel
    deadline: date | None
    progress: Decimal
    status: TaskStatus
    source: TaskSource
    steps: list[TaskStepResponse] = Field(default_factory=list)


class TaskTodayImpactResponse(BaseModel):
    plan_date: date
    plan_exists: bool
    replanned: bool
    daily_plan_id: uuid.UUID | None = None
    plan_version: int | None = None
    daily_plan_item_id: uuid.UUID | None = None
    task_in_today: bool
    section: DailyPlanItemSection | None = None
    item_status: DailyPlanItemStatus | None = None
    reason: str


class TaskPriorityAdjustmentResponse(BaseModel):
    task: TaskResponse
    previous_priority: int
    current_priority: int
    previous_value_level: ValueLevel
    current_value_level: ValueLevel
    changed_fields: list[str] = Field(default_factory=list)
    reason: str | None
    today_impact: TaskTodayImpactResponse | None = None


class TaskDetailGoalResponse(BaseModel):
    id: uuid.UUID
    title: str
    deadline: date | None
    value_level: ValueLevel


class TaskDetailAIInfoResponse(BaseModel):
    recommended_duration_min: int
    priority: int
    value_level: ValueLevel
    execution_suggestion: str


class TaskDetailProgressResponse(BaseModel):
    progress: Decimal
    status: TaskStatus
    actual_duration_min: int


class TaskSourceContextResponse(BaseModel):
    source: TaskSource
    capture_source: CaptureSource | None
    provider: str | None
    external_item_id: str | None
    external_item_type: str | None
    external_title: str | None
    external_body_preview: str | None
    occurred_at: datetime | None
    imported_at: datetime | None
    capture_input_id: uuid.UUID | None
    inbox_item_id: uuid.UUID | None
    data_source_connection_id: uuid.UUID | None


class TaskDetailTodayContextResponse(BaseModel):
    daily_plan_id: uuid.UUID
    daily_plan_item_id: uuid.UUID
    plan_date: date
    plan_version: int
    section: DailyPlanItemSection
    item_status: DailyPlanItemStatus
    sort_order: int
    recommendation_reason: str


class TaskDetailFocusStateResponse(BaseModel):
    active_focus_session_id: uuid.UUID | None
    is_currently_focusing_this_task: bool


class TaskDetailActionsResponse(BaseModel):
    can_start_focus: bool
    can_complete: bool
    can_postpone: bool
    can_edit: bool


class TaskDependencyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prerequisite_task_id: uuid.UUID
    reason: str | None = Field(default=None, max_length=500)


class TaskDependencyNodeResponse(BaseModel):
    task_id: uuid.UUID
    title: str
    status: TaskStatus
    value_level: ValueLevel
    deadline: date | None


class TaskDependencyEdgeResponse(BaseModel):
    id: uuid.UUID
    prerequisite_task: TaskDependencyNodeResponse
    dependent_task: TaskDependencyNodeResponse
    reason: str | None


class TaskDependenciesResponse(BaseModel):
    task_id: uuid.UUID
    prerequisites: list[TaskDependencyEdgeResponse] = Field(default_factory=list)
    dependents: list[TaskDependencyEdgeResponse] = Field(default_factory=list)


class TaskDetailResponse(TaskResponse):
    source_context: TaskSourceContextResponse | None
    goal: TaskDetailGoalResponse | None
    ai_info: TaskDetailAIInfoResponse
    progress_info: TaskDetailProgressResponse
    today_context: TaskDetailTodayContextResponse | None
    dependency_info: TaskDependenciesResponse
    focus_state: TaskDetailFocusStateResponse
    actions: TaskDetailActionsResponse


class TaskBreakdownAIJobResponse(BaseModel):
    id: uuid.UUID
    job_type: AIJobType
    status: AIJobStatus
    result_entity_type: str | None
    result_entity_id: uuid.UUID | None
    error_message: str | None
    provider: str | None
    model: str | None
    prompt_version: str | None
    job_metadata: dict


class TaskBreakdownResponse(BaseModel):
    ai_job: TaskBreakdownAIJobResponse
    created_steps: list[TaskStepResponse] = Field(default_factory=list)


class ActivityEventResponse(ORMModel):
    id: uuid.UUID
    user_id: uuid.UUID
    entity_type: EntityType
    entity_id: uuid.UUID
    related_task_id: uuid.UUID | None
    related_daily_plan_id: uuid.UUID | None
    related_focus_session_id: uuid.UUID | None
    event_type: str
    actor_type: ActorType
    source: EventSource
    payload: dict
    occurred_at: datetime
