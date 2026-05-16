from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import (
    AIStrategyPreference,
    PlanningPreference,
    enum_values,
)
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    settings: Mapped[UserSettings | None] = relationship(
        "UserSettings",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    goals: Mapped[list["Goal"]] = relationship("Goal", back_populates="user")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="user")


class UserSettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    notification_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    focus_mode_default_minutes: Mapped[int] = mapped_column(Integer, default=25, nullable=False)
    planning_preference: Mapped[PlanningPreference] = mapped_column(
        Enum(
            PlanningPreference,
            name="planning_preference",
            values_callable=enum_values,
        ),
        default=PlanningPreference.NORMAL,
        nullable=False,
    )
    ai_strategy_preference: Mapped[AIStrategyPreference] = mapped_column(
        Enum(
            AIStrategyPreference,
            name="ai_strategy_preference",
            values_callable=enum_values,
        ),
        default=AIStrategyPreference.BALANCED,
        nullable=False,
    )

    user: Mapped[User] = relationship("User", back_populates="settings")
