from datetime import date, datetime
import uuid

from pydantic import BaseModel

from app.models.enums import ValueLevel
from app.schemas.common import TimestampedResponse


class DailyReportResponse(TimestampedResponse):
    user_id: uuid.UUID
    daily_plan_id: uuid.UUID | None
    report_date: date
    completed_task_count: int
    postponed_task_count: int
    interrupted_count: int
    focus_minutes: int
    completion_rate: float
    ai_summary: str
    ai_suggestions: list[str]
    generated_from_plan_version: int | None
    refreshed_at: datetime


class WeeklyReportDailyTrendResponse(BaseModel):
    report_date: date
    planned_task_count: int
    completed_task_count: int
    postponed_task_count: int
    interrupted_count: int
    focus_minutes: int
    completion_rate: float
    high_value_completed_task_count: int


class WeeklyReportSummaryResponse(BaseModel):
    total_planned_task_count: int
    total_completed_task_count: int
    total_postponed_task_count: int
    total_interrupted_count: int
    total_focus_minutes: int
    average_completion_rate: float
    high_value_completed_task_count: int
    active_goal_count: int
    at_risk_goal_count: int
    overdue_task_count: int


class WeeklyReportFocusResponse(BaseModel):
    total_minutes: int
    average_minutes_per_active_day: int
    best_focus_date: date | None
    best_focus_minutes: int


class WeeklyReportLaggingTaskResponse(BaseModel):
    id: uuid.UUID
    title: str
    goal_id: uuid.UUID | None
    deadline: date | None
    days_overdue: int
    value_level: ValueLevel
    priority: int
    reason: str


class WeeklyReportResponse(BaseModel):
    week_start: date
    week_end: date
    summary: WeeklyReportSummaryResponse
    daily_trends: list[WeeklyReportDailyTrendResponse]
    focus: WeeklyReportFocusResponse
    lagging_tasks: list[WeeklyReportLaggingTaskResponse]
    ai_suggestions: list[str]
