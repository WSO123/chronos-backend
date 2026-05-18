from datetime import date
import uuid

from pydantic import BaseModel, Field

from app.models.enums import ValueLevel


class GoalProgressFeedbackItemResponse(BaseModel):
    goal_id: uuid.UUID
    goal_title: str
    goal_value_level: ValueLevel
    task_id: uuid.UUID | None = None
    task_title: str | None = None
    impact_type: str
    progress_before: float
    progress_after: float
    progress_delta: float
    task_progress_delta: float = 0.0
    completed_task_count: int
    total_task_count: int
    unfinished_task_count: int
    focus_minutes: int
    message: str
    signal: str
    source: str = "goal-progress-feedback-v1"


class DailyGoalProgressFeedbackResponse(BaseModel):
    report_date: date
    touched_goal_count: int
    advanced_goal_count: int
    high_value_goal_count: int
    total_progress_delta: float
    items: list[GoalProgressFeedbackItemResponse] = Field(default_factory=list)
    source: str = "goal-progress-feedback-v1"
