from pydantic import BaseModel


class SchedulerEntryResponse(BaseModel):
    task_name: str
    cadence: str
    schedule_hint: str
    scope: str
    enabled: bool
    payload_template: dict
    guardrails: list[str]


class ReminderSchedulerPlanResponse(BaseModel):
    timezone: str
    entries: list[SchedulerEntryResponse]
    notes: list[str]
