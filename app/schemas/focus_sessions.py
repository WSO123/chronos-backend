from datetime import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import FocusSessionStatus
from app.schemas.common import TimestampedResponse
from app.schemas.goal_feedback import GoalProgressFeedbackItemResponse


class FocusSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: uuid.UUID
    daily_plan_item_id: uuid.UUID | None = None
    planned_duration_min: int | None = Field(default=None, ge=1)


class FocusSessionFinishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actual_duration_min: int | None = Field(default=None, ge=0)
    interruption_reason: str | None = Field(default=None, max_length=500)


class FocusSessionResponse(TimestampedResponse):
    user_id: uuid.UUID
    task_id: uuid.UUID
    daily_plan_id: uuid.UUID | None
    daily_plan_item_id: uuid.UUID | None
    started_at: datetime
    ended_at: datetime | None
    planned_duration_min: int | None
    actual_duration_min: int
    status: FocusSessionStatus
    interruption_reason: str | None
    goal_progress_feedback: GoalProgressFeedbackItemResponse | None = None
