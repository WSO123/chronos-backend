from datetime import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import TimestampedResponse


class ReminderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    message: str | None = None
    reminder_type: str = "execution"
    scheduled_for: datetime
    channel: str = "in_app"
    source: str = "manual"
    task_id: uuid.UUID | None = None
    goal_id: uuid.UUID | None = None
    reminder_metadata: dict = Field(default_factory=dict)


class ReminderResponse(TimestampedResponse):
    user_id: uuid.UUID
    task_id: uuid.UUID | None
    goal_id: uuid.UUID | None
    title: str
    message: str | None
    reminder_type: str
    status: str
    scheduled_for: datetime
    channel: str
    source: str
    seen_at: datetime | None
    dismissed_at: datetime | None
    sent_at: datetime | None
    reminder_metadata: dict


class ReminderListResponse(BaseModel):
    reminders: list[ReminderResponse]
    scheduled_count: int
    overdue_count: int


class ReminderSummaryResponse(BaseModel):
    pending_count: int
    unseen_count: int
    due_count: int
    execution_count: int
    deadline_count: int
    next_reminder: ReminderResponse | None


class ReminderBulkSeenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reminder_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)


class ReminderBulkSeenResponse(BaseModel):
    updated_count: int
    already_seen_count: int
    reminders: list[ReminderResponse]


class ReminderSnoozeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minutes: int = Field(default=15, ge=5, le=1440)
