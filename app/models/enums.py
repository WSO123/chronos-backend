from enum import StrEnum


class ValueLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PlanningPreference(StrEnum):
    LIGHT = "light"
    NORMAL = "normal"
    SPRINT = "sprint"


class AIStrategyPreference(StrEnum):
    BALANCED = "balanced"
    HIGH_VALUE_FIRST = "high_value_first"
    ENERGY_AWARE = "energy_aware"


class GoalStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class GoalHomeFilter(StrEnum):
    ALL = "all"
    ACTIVE = "active"
    DUE_SOON = "due_soon"
    COMPLETED = "completed"
    HIGH_VALUE = "high_value"


class TaskStatus(StrEnum):
    ACTIVE = "active"
    IN_FOCUS = "in_focus"
    COMPLETED = "completed"
    POSTPONED = "postponed"
    ARCHIVED = "archived"


class TaskSource(StrEnum):
    MANUAL = "manual"
    CAPTURE = "capture"
    AI = "ai"
    EMAIL = "email"
    CALENDAR = "calendar"


class DailyPlanStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"


class PlanRevisionTrigger(StrEnum):
    INITIAL = "initial"
    REPLAN = "replan"
    MANUAL_ADJUST = "manual_adjust"
    SYSTEM_REFRESH = "system_refresh"


class DailyPlanItemSection(StrEnum):
    PINNED = "pinned"
    RECOMMENDED = "recommended"
    LOW_PRIORITY = "low_priority"
    ROLLED_OVER = "rolled_over"


class DailyPlanItemStatus(StrEnum):
    PLANNED = "planned"
    COMPLETED = "completed"
    POSTPONED = "postponed"
    SKIPPED = "skipped"


class FocusSessionStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    POSTPONED = "postponed"


class CaptureInputType(StrEnum):
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    EXTERNAL = "external"


class CaptureSource(StrEnum):
    MANUAL = "manual"
    VOICE = "voice"
    IMAGE = "image"
    EMAIL = "email"
    CALENDAR = "calendar"


class CaptureStatus(StrEnum):
    RECEIVED = "received"
    PARSING = "parsing"
    PARSED = "parsed"
    FAILED = "failed"
    ARCHIVED = "archived"


class ParseResultType(StrEnum):
    TASK = "task"
    GOAL = "goal"
    IDEA = "idea"
    CALENDAR_ITEM = "calendar_item"
    UNKNOWN = "unknown"


class InboxItemType(StrEnum):
    TASK = "task"
    GOAL = "goal"
    IDEA = "idea"
    UNKNOWN = "unknown"


class InboxItemStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    EDITED = "edited"
    DISCARDED = "discarded"


class DataSourceType(StrEnum):
    CALENDAR = "calendar"
    EMAIL = "email"
    HEALTH = "health"


class DataSourceStatus(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    NEEDS_REAUTH = "needs_reauth"
    PAUSED = "paused"


class EntityType(StrEnum):
    TASK = "task"
    GOAL = "goal"
    CAPTURE = "capture"
    INBOX = "inbox"
    DAILY_PLAN = "daily_plan"
    FOCUS_SESSION = "focus_session"
    AI_JOB = "ai_job"
    REPORT = "report"
    DATA_SOURCE = "data_source"


class ActorType(StrEnum):
    USER = "user"
    AI = "ai"
    SYSTEM = "system"


class EventSource(StrEnum):
    API = "api"
    WORKER = "worker"
    SCHEDULER = "scheduler"


class AIJobType(StrEnum):
    CAPTURE_PARSER = "capture_parser"
    DAILY_PLANNER = "daily_planner"
    STRATEGY_EXPLANATION = "strategy_explanation"
    TASK_BREAKDOWN = "task_breakdown"
    DAILY_REPORT_GENERATOR = "daily_report_generator"
    INSIGHT_GENERATOR = "insight_generator"


class AIJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    SUCCEEDED_WITH_FALLBACK = "succeeded_with_fallback"
    FAILED = "failed"
    CANCELED = "canceled"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]
