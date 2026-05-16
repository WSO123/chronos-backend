from datetime import datetime
import uuid

from app.models.enums import AIJobStatus, AIJobType
from app.schemas.common import TimestampedResponse


class AIJobResponse(TimestampedResponse):
    user_id: uuid.UUID
    job_type: AIJobType
    status: AIJobStatus
    input_entity_type: str
    input_entity_id: uuid.UUID
    result_entity_type: str | None
    result_entity_id: uuid.UUID | None
    celery_task_id: str | None
    provider: str | None
    model: str | None
    prompt_version: str | None
    latency_ms: int | None
    error_message: str | None
    retry_count: int
    job_metadata: dict
    started_at: datetime | None
    finished_at: datetime | None
