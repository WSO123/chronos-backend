from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class TaskDependency(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "task_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "dependent_task_id",
            "prerequisite_task_id",
            name="uq_task_dependencies_edge",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    dependent_task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    prerequisite_task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    reason: Mapped[str | None] = mapped_column(String(500))

    dependent_task: Mapped["Task"] = relationship("Task", foreign_keys=[dependent_task_id])
    prerequisite_task: Mapped["Task"] = relationship("Task", foreign_keys=[prerequisite_task_id])
