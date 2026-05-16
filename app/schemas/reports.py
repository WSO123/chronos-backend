from datetime import date, datetime
import uuid

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
