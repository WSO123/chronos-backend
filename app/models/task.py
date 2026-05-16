from __future__ import annotations

from datetime import date
from decimal import Decimal
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import TaskSource, TaskStatus, ValueLevel, enum_values
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Task(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tasks"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    goal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("goals.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    estimated_duration_min: Mapped[int | None] = mapped_column(Integer)
    actual_duration_min: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    value_level: Mapped[ValueLevel] = mapped_column(
        Enum(ValueLevel, name="value_level", values_callable=enum_values),
        default=ValueLevel.MEDIUM,
        nullable=False,
    )
    deadline: Mapped[date | None]
    progress: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("0.00"), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status", values_callable=enum_values),
        default=TaskStatus.ACTIVE,
        nullable=False,
    )
    source: Mapped[TaskSource] = mapped_column(
        Enum(TaskSource, name="task_source", values_callable=enum_values),
        default=TaskSource.MANUAL,
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="tasks")
    goal: Mapped["Goal | None"] = relationship("Goal", back_populates="tasks")
    steps: Mapped[list["TaskStep"]] = relationship(
        "TaskStep",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskStep.sort_order",
    )
