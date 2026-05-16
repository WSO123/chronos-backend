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


class CeleryBeatScheduleEntryResponse(BaseModel):
    name: str
    task: str
    schedule: dict
    kwargs: dict


class ExcludedSchedulerEntryResponse(BaseModel):
    task_name: str
    reason: str


class ReminderCeleryBeatScheduleResponse(BaseModel):
    timezone: str
    entries: list[CeleryBeatScheduleEntryResponse]
    excluded_entries: list[ExcludedSchedulerEntryResponse]
    notes: list[str]
