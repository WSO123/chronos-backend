from __future__ import annotations

from datetime import date
import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import GoalStatus, ValueLevel, enum_values
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Goal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "goals"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    deadline: Mapped[date | None]
    value_level: Mapped[ValueLevel] = mapped_column(
        Enum(ValueLevel, name="value_level", values_callable=enum_values),
        default=ValueLevel.MEDIUM,
        nullable=False,
    )
    status: Mapped[GoalStatus] = mapped_column(
        Enum(GoalStatus, name="goal_status", values_callable=enum_values),
        default=GoalStatus.ACTIVE,
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="goals")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="goal")
