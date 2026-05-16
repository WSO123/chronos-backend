from __future__ import annotations

from datetime import date, datetime
import uuid

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, JSON, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class DailyReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "daily_reports"
    __table_args__ = (
        UniqueConstraint("user_id", "report_date", name="uq_daily_reports_user_date"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    daily_plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("daily_plans.id", ondelete="SET NULL"), index=True)
    report_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    completed_task_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    postponed_task_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    interrupted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    focus_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    ai_summary: Mapped[str] = mapped_column(Text, nullable=False)
    ai_suggestions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    generated_from_plan_version: Mapped[int | None] = mapped_column(Integer)
    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
