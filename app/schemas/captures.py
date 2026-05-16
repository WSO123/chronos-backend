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


class ExternalCaptureImportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_source_connection_id: uuid.UUID
    external_item_id: str = Field(min_length=1, max_length=255)
    external_item_type: str = Field(default="external_item", min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=255)
    body: str | None = None
    occurred_at: datetime | None = None
    external_payload: dict = Field(default_factory=dict)


class ExternalCaptureImportResponse(TimestampedResponse):
    user_id: uuid.UUID
    data_source_connection_id: uuid.UUID | None
    source: CaptureSource
    provider: str
    external_item_id: str
    external_item_type: str
    title: str
    body: str | None
    occurred_at: datetime | None
    normalized_text: str
    external_payload: dict
    capture_input_id: uuid.UUID | None
    inbox_item_id: uuid.UUID | None


class ExternalCaptureImportCreateResponse(BaseModel):
    import_record: ExternalCaptureImportResponse
    capture: CaptureResponse
    parse_result: AIParseResultResponse
    inbox_item: InboxItemResponse
    created: bool
