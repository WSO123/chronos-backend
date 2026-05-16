from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AIStrategyPreference, PlanningPreference


class UserSettingsResponse(BaseModel):
    notification_enabled: bool
    reminder_execution_enabled: bool
    reminder_deadline_enabled: bool
    reminder_channel_in_app_enabled: bool
    reminder_channel_push_enabled: bool
    reminder_channel_email_enabled: bool
    execution_reminder_limit: int
    execution_reminder_start_hour: int
    execution_reminder_spacing_minutes: int
    deadline_reminder_hour: int
    focus_mode_default_minutes: int
    planning_preference: PlanningPreference
    ai_strategy_preference: AIStrategyPreference


class UserSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notification_enabled: bool | None = None
    reminder_execution_enabled: bool | None = None
    reminder_deadline_enabled: bool | None = None
    reminder_channel_in_app_enabled: bool | None = None
    reminder_channel_push_enabled: bool | None = None
    reminder_channel_email_enabled: bool | None = None
    execution_reminder_limit: int | None = Field(default=None, ge=1, le=10)
    execution_reminder_start_hour: int | None = Field(default=None, ge=0, le=23)
    execution_reminder_spacing_minutes: int | None = Field(default=None, ge=15, le=180)
    deadline_reminder_hour: int | None = Field(default=None, ge=0, le=23)
    focus_mode_default_minutes: int | None = Field(default=None, ge=5, le=180)
    planning_preference: PlanningPreference | None = None
    ai_strategy_preference: AIStrategyPreference | None = None
