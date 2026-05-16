from datetime import date
import uuid

from pydantic import BaseModel


class MeProfileResponse(BaseModel):
    user_id: uuid.UUID
    name: str
    timezone: str
    current_streak_days: int


class MeTodayOverviewResponse(BaseModel):
    date: date
    completed_task_count: int
    planned_task_count: int
    completion_rate: float
    focus_minutes: int


class MeWeekOverviewResponse(BaseModel):
    week_start: date
    week_end: date
    focus_minutes: int


class MeGoalOverviewResponse(BaseModel):
    active_goal_count: int
    completed_goal_count: int


class MeTaskOverviewResponse(BaseModel):
    active_task_count: int
    postponed_task_count: int
    completed_task_count: int


class MeReportsOverviewResponse(BaseModel):
    daily_report_available: bool
    daily_report_id: uuid.UUID | None


class MeSettingsOverviewResponse(BaseModel):
    notification_enabled: bool
    focus_mode_default_minutes: int


class MeOverviewResponse(BaseModel):
    profile: MeProfileResponse
    today: MeTodayOverviewResponse
    week: MeWeekOverviewResponse
    goals: MeGoalOverviewResponse
    tasks: MeTaskOverviewResponse
    reports: MeReportsOverviewResponse
    settings: MeSettingsOverviewResponse
