from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ReminderDeliveryAttempt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reminder_delivery_attempts"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    reminder_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reminders.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(String(120))
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    attempt_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    reminder = relationship("Reminder")
