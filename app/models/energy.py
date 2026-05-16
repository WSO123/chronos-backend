from __future__ import annotations

from datetime import date
import uuid

from sqlalchemy import Date, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class EnergyDailyMetric(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "energy_daily_metrics"
    __table_args__ = (
        UniqueConstraint("user_id", "metric_date", name="uq_energy_daily_metrics_user_date"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    data_source_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_source_connections.id", ondelete="SET NULL"),
        index=True,
    )
    metric_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(40), default="manual", nullable=False)
    sleep_minutes: Mapped[int | None] = mapped_column(Integer)
    sleep_quality_score: Mapped[int | None] = mapped_column(Integer)
    stress_score: Mapped[int | None] = mapped_column(Integer)
    energy_score: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text)
    metric_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    data_source_connection = relationship("DataSourceConnection")
