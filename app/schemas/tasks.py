from datetime import date, datetime
from decimal import Decimal
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    AIJobStatus,
    AIJobType,
    ActorType,
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


class TaskDetailResponse(TaskResponse):
    goal: TaskDetailGoalResponse | None
    ai_info: TaskDetailAIInfoResponse
    progress_info: TaskDetailProgressResponse
    today_context: TaskDetailTodayContextResponse | None
    focus_state: TaskDetailFocusStateResponse
    actions: TaskDetailActionsResponse


class TaskBreakdownAIJobResponse(BaseModel):
    id: uuid.UUID
    job_type: AIJobType
    status: AIJobStatus
    result_entity_type: str | None
    result_entity_id: uuid.UUID | None
    error_message: str | None
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
