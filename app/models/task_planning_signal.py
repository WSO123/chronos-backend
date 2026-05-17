from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class TaskPlanningSignal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "task_planning_signals"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    ai_job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_jobs.id", ondelete="SET NULL"), index=True)
    source: Mapped[str] = mapped_column(String(32), default="ai", nullable=False)
    task_type: Mapped[str] = mapped_column(String(64), default="general", nullable=False)
    complexity: Mapped[str] = mapped_column(String(16), default="medium", nullable=False)
    cognitive_load: Mapped[str] = mapped_column(String(16), default="medium", nullable=False)
    energy_fit: Mapped[str] = mapped_column(String(32), default="steady", nullable=False)
    blocking_risk: Mapped[str] = mapped_column(String(16), default="medium", nullable=False)
    estimated_duration_min: Mapped[int | None] = mapped_column(Integer)
    duration_confidence: Mapped[float] = mapped_column(Float, default=0.6, nullable=False)
    goal_alignment_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    semantic_priority_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    breakdown_recommended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    minimum_viable_step: Mapped[str | None] = mapped_column(String(255))
    semantic_summary: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.6, nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
