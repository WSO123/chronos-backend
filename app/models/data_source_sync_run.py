from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import DataSourceType, enum_values
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class DataSourceSyncRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "data_source_sync_runs"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    data_source_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_source_connections.id", ondelete="SET NULL"),
        index=True,
    )
    source_type: Mapped[DataSourceType] = mapped_column(
        Enum(DataSourceType, name="data_source_type", values_callable=enum_values),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="running", nullable=False, index=True)
    trigger: Mapped[str] = mapped_column(String(40), default="worker", nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    retryable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    skip_reason: Mapped[str | None] = mapped_column(String(120))
    error_message: Mapped[str | None] = mapped_column(Text)
    processed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    imported_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reused_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fetched_from_provider: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    provider_mode: Mapped[str | None] = mapped_column(String(40))
    sync_cursor_before: Mapped[str | None] = mapped_column(String(500))
    sync_cursor_after: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    run_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    data_source_connection = relationship("DataSourceConnection")
