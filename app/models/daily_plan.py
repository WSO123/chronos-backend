from __future__ import annotations

from datetime import date, datetime
import uuid

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import (
    ActorType,
    DailyPlanItemSection,
    DailyPlanItemStatus,
    DailyPlanStatus,
    PlanningPreference,
    PlanRevisionTrigger,
    enum_values,
)
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class DailyPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "daily_plans"
    __table_args__ = (
        UniqueConstraint("user_id", "plan_date", "status", name="uq_daily_plans_user_date_status"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    status: Mapped[DailyPlanStatus] = mapped_column(
        Enum(DailyPlanStatus, name="daily_plan_status", values_callable=enum_values),
        default=DailyPlanStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    current_revision_id: Mapped[uuid.UUID | None]
    total_estimated_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    focus_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[ActorType] = mapped_column(
        Enum(ActorType, name="actor_type", values_callable=enum_values),
        default=ActorType.SYSTEM,
        nullable=False,
    )

    revisions: Mapped[list["PlanRevision"]] = relationship(
        "PlanRevision",
        back_populates="daily_plan",
        cascade="all, delete-orphan",
        order_by="PlanRevision.version",
    )
    strategy_snapshots: Mapped[list["StrategySnapshot"]] = relationship(
        "StrategySnapshot",
        back_populates="daily_plan",
        cascade="all, delete-orphan",
    )
    items: Mapped[list["DailyPlanItem"]] = relationship(
        "DailyPlanItem",
        back_populates="daily_plan",
        cascade="all, delete-orphan",
    )


class PlanRevision(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "plan_revisions"
    __table_args__ = (
        UniqueConstraint("daily_plan_id", "version", name="uq_plan_revisions_daily_plan_version"),
    )

    daily_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("daily_plans.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    trigger: Mapped[PlanRevisionTrigger] = mapped_column(
        Enum(PlanRevisionTrigger, name="plan_revision_trigger", values_callable=enum_values),
        nullable=False,
    )
    created_by: Mapped[ActorType] = mapped_column(
        Enum(ActorType, name="actor_type", values_callable=enum_values),
        default=ActorType.SYSTEM,
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(Text)
    diff_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    daily_plan: Mapped[DailyPlan] = relationship("DailyPlan", back_populates="revisions")
    strategy_snapshots: Mapped[list["StrategySnapshot"]] = relationship(
        "StrategySnapshot",
        back_populates="plan_revision",
        cascade="all, delete-orphan",
    )
    items: Mapped[list["DailyPlanItem"]] = relationship(
        "DailyPlanItem",
        back_populates="plan_revision",
        cascade="all, delete-orphan",
    )


class StrategySnapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "strategy_snapshots"

    daily_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("daily_plans.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    plan_revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plan_revisions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    mode: Mapped[PlanningPreference] = mapped_column(
        Enum(PlanningPreference, name="planning_preference", values_callable=enum_values),
        default=PlanningPreference.NORMAL,
        nullable=False,
    )
    primary_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    score_factors: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(120))
    prompt_version: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    daily_plan: Mapped[DailyPlan] = relationship("DailyPlan", back_populates="strategy_snapshots")
    plan_revision: Mapped[PlanRevision] = relationship("PlanRevision", back_populates="strategy_snapshots")


class DailyPlanItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "daily_plan_items"

    daily_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("daily_plans.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    plan_revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plan_revisions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[DailyPlanItemSection] = mapped_column(
        Enum(DailyPlanItemSection, name="daily_plan_item_section", values_callable=enum_values),
        nullable=False,
        index=True,
    )
    recommendation_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    estimated_duration_min: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[DailyPlanItemStatus] = mapped_column(
        Enum(DailyPlanItemStatus, name="daily_plan_item_status", values_callable=enum_values),
        default=DailyPlanItemStatus.PLANNED,
        nullable=False,
        index=True,
    )

    daily_plan: Mapped[DailyPlan] = relationship("DailyPlan", back_populates="items")
    plan_revision: Mapped[PlanRevision] = relationship("PlanRevision", back_populates="items")
    task: Mapped["Task"] = relationship("Task")
