from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import AIJobStatus, AIJobType, enum_values
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AIJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_jobs"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    job_type: Mapped[AIJobType] = mapped_column(
        Enum(AIJobType, name="ai_job_type", values_callable=enum_values),
        nullable=False,
    )
    status: Mapped[AIJobStatus] = mapped_column(
        Enum(AIJobStatus, name="ai_job_status", values_callable=enum_values),
        default=AIJobStatus.QUEUED,
        nullable=False,
        index=True,
    )
    input_entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    input_entity_id: Mapped[uuid.UUID] = mapped_column(index=True)
    result_entity_type: Mapped[str | None] = mapped_column(String(80))
    result_entity_id: Mapped[uuid.UUID | None]
    celery_task_id: Mapped[str | None] = mapped_column(String(255), index=True)
    provider: Mapped[str | None] = mapped_column(String(80))
    model: Mapped[str | None] = mapped_column(String(120))
    prompt_version: Mapped[str | None] = mapped_column(String(80))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    job_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
