from datetime import date
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DailyPlanItemSection, DailyPlanItemStatus, InboxItemStatus, InboxItemType
from app.schemas.common import TimestampedResponse


class InboxItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_type: InboxItemType | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    suggested_goal_id: uuid.UUID | None = None
    suggested_priority: int | None = Field(default=None, ge=1, le=5)
    suggested_deadline: date | None = None


class InboxItemResponse(TimestampedResponse):
    user_id: uuid.UUID
    capture_input_id: uuid.UUID
    parse_result_id: uuid.UUID
    item_type: InboxItemType
    title: str
    description: str | None
    suggested_goal_id: uuid.UUID | None
    suggested_priority: int | None
    suggested_deadline: date | None
    status: InboxItemStatus
    result_entity_type: str | None
    result_entity_id: uuid.UUID | None


class InboxConfirmTodayImpactResponse(BaseModel):
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


class InboxConfirmResponse(BaseModel):
    inbox_item: InboxItemResponse
    result_entity_type: str
    result_entity_id: uuid.UUID
    today_impact: InboxConfirmTodayImpactResponse | None = None
