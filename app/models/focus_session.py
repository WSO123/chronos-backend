from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import FocusSessionStatus, enum_values
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class FocusSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "focus_sessions"
    __table_args__ = (
        Index(
            "uq_focus_sessions_user_active",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    daily_plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("daily_plans.id", ondelete="SET NULL"), index=True)
    daily_plan_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("daily_plan_items.id", ondelete="SET NULL"),
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    planned_duration_min: Mapped[int | None] = mapped_column(Integer)
    actual_duration_min: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[FocusSessionStatus] = mapped_column(
        Enum(FocusSessionStatus, name="focus_session_status", values_callable=enum_values),
        default=FocusSessionStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    interruption_reason: Mapped[str | None] = mapped_column(Text)

    task: Mapped["Task"] = relationship("Task")
