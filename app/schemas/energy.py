from datetime import date
import uuid

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedResponse


class EnergyDailyMetricUpsert(BaseModel):
    metric_date: date
    source: str = "manual"
    data_source_connection_id: uuid.UUID | None = None
    sleep_minutes: int | None = Field(default=None, ge=0, le=1440)
    sleep_quality_score: int | None = Field(default=None, ge=0, le=100)
    stress_score: int | None = Field(default=None, ge=0, le=100)
    energy_score: int | None = Field(default=None, ge=0, le=100)
    note: str | None = None
    metric_metadata: dict = Field(default_factory=dict)


class EnergyDailyMetricResponse(TimestampedResponse):
    user_id: uuid.UUID
    data_source_connection_id: uuid.UUID | None
    metric_date: date
    source: str
    sleep_minutes: int | None
    sleep_quality_score: int | None
    stress_score: int | None
    energy_score: int | None
    energy_level: str
    note: str | None
    metric_metadata: dict


class EnergyDashboardDayResponse(BaseModel):
    date: date
    sleep_minutes: int | None
    sleep_quality_score: int | None
    stress_score: int | None
    energy_score: int | None
    energy_level: str
    has_data: bool


class EnergyDashboardSummaryResponse(BaseModel):
    date: date
    energy_score: int | None
    energy_level: str
    sleep_minutes: int | None
    sleep_quality_score: int | None
    stress_score: int | None
    status_message: str


class EnergySuggestionResponse(BaseModel):
    key: str
    title: str
    message: str
    signal: str


class EnergyTaskMatchResponse(BaseModel):
    recommended_mode: str
    reason: str


class EnergyDashboardResponse(BaseModel):
    start_date: date
    end_date: date
    summary: EnergyDashboardSummaryResponse
    trends: list[EnergyDashboardDayResponse]
    task_match: EnergyTaskMatchResponse
    suggestions: list[EnergySuggestionResponse]
