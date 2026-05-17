from datetime import date

from pydantic import BaseModel


class InsightOverviewResponse(BaseModel):
    average_completion_rate: float
    total_completed_task_count: int
    high_value_completed_task_count: int
    total_focus_minutes: int
    overdue_task_count: int
    at_risk_goal_count: int


class InsightPatternResponse(BaseModel):
    key: str
    title: str
    signal: str
    evidence: str
    suggestion: str


class InsightEfficiencyWindowResponse(BaseModel):
    label: str
    start_hour: int
    end_hour: int
    focus_minutes: int
    completed_focus_count: int
    signal: str


class InsightRecommendationResponse(BaseModel):
    category: str
    title: str
    suggestion: str
    rationale: str


class InsightSourceResponse(BaseModel):
    generated_by: str
    period_days: int
    data_points: int
    ai_job_id: str | None = None
    ai_job_status: str | None = None
    model_name: str | None = None
    prompt_version: str | None = None
    fallback_reason: str | None = None


class InsightDetailResponse(BaseModel):
    anchor_date: date
    period_start: date
    period_end: date
    overview: InsightOverviewResponse
    behavior_patterns: list[InsightPatternResponse]
    efficiency_windows: list[InsightEfficiencyWindowResponse]
    recommendations: list[InsightRecommendationResponse]
    strategy_notes: list[str]
    source: InsightSourceResponse
