from datetime import date
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import GoalStatus, ValueLevel
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
