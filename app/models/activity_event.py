from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import ActorType, EntityType, EventSource, enum_values
from app.models.mixins import UUIDPrimaryKeyMixin, utc_now


class ActivityEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "activity_events"
    __table_args__ = (
        Index("ix_activity_events_user_occurred_at", "user_id", "occurred_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    entity_type: Mapped[EntityType] = mapped_column(
        Enum(EntityType, name="entity_type", values_callable=enum_values),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(index=True)
    related_task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"))
    related_daily_plan_id: Mapped[uuid.UUID | None]
    related_focus_session_id: Mapped[uuid.UUID | None]
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    actor_type: Mapped[ActorType] = mapped_column(
        Enum(ActorType, name="actor_type", values_callable=enum_values),
        default=ActorType.USER,
        nullable=False,
    )
    source: Mapped[EventSource] = mapped_column(
        Enum(EventSource, name="event_source", values_callable=enum_values),
        default=EventSource.API,
        nullable=False,
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), unique=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
