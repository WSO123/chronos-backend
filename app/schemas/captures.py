from datetime import date, datetime
from decimal import Decimal
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CaptureInputType, CaptureSource, CaptureStatus, ParseResultType
from app.schemas.common import ORMModel, TimestampedResponse
from app.schemas.inbox import InboxItemResponse


class CaptureCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_text: str = Field(min_length=1)


class CaptureResponse(TimestampedResponse):
    user_id: uuid.UUID
    input_type: CaptureInputType
    raw_text: str
    attachment_url: str | None
    source: CaptureSource
    status: CaptureStatus


class AIParseResultResponse(ORMModel):
    id: uuid.UUID
    capture_input_id: uuid.UUID
    result_type: ParseResultType
    title: str
    description: str | None
    estimated_duration_min: int | None
    suggested_priority: int | None
    suggested_deadline: date | None
    suggested_goal_id: uuid.UUID | None
    confidence: Decimal
    raw_model_output: dict
    created_at: datetime


class CaptureCreateResponse(BaseModel):
    capture: CaptureResponse
    parse_result: AIParseResultResponse
    inbox_item: InboxItemResponse
