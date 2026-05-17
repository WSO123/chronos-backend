from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import InboxItemType, ParseResultType


class CaptureParserOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_type: ParseResultType
    item_type: InboxItemType
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    estimated_duration_min: int | None = Field(default=None, ge=1, le=1440)
    suggested_priority: int | None = Field(default=None, ge=1, le=5)
    suggested_deadline: date | None = None
    confidence: float = Field(ge=0, le=1)
    rationale: str | None = Field(default=None, max_length=500)
