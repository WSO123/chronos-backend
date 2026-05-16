from pydantic import BaseModel


class SchedulerOverviewDomainResponse(BaseModel):
    domain: str
    display_name: str
    plan_path: str
    beat_path: str
    entry_count: int
    enabled_entry_count: int
    beat_entry_count: int
    excluded_entry_count: int
    task_names: list[str]
    beat_task_names: list[str]
    excluded_task_names: list[str]
    guardrail_count: int


class SchedulerOverviewResponse(BaseModel):
    timezone: str
    domains: list[SchedulerOverviewDomainResponse]
    notes: list[str]


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


class DataSourceSchedulerPlanResponse(BaseModel):
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


class DataSourceCeleryBeatScheduleResponse(BaseModel):
    timezone: str
    entries: list[CeleryBeatScheduleEntryResponse]
    excluded_entries: list[ExcludedSchedulerEntryResponse]
    notes: list[str]
