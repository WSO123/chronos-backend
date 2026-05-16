from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import uuid

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import (
    CaptureInputType,
    CaptureSource,
    CaptureStatus,
    ParseResultType,
    enum_values,
)
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class CaptureInput(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "capture_inputs"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    input_type: Mapped[CaptureInputType] = mapped_column(
        Enum(CaptureInputType, name="capture_input_type", values_callable=enum_values),
        default=CaptureInputType.TEXT,
        nullable=False,
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    attachment_url: Mapped[str | None] = mapped_column(String(500))
    source: Mapped[CaptureSource] = mapped_column(
        Enum(CaptureSource, name="capture_source", values_callable=enum_values),
        default=CaptureSource.MANUAL,
        nullable=False,
    )
    status: Mapped[CaptureStatus] = mapped_column(
        Enum(CaptureStatus, name="capture_status", values_callable=enum_values),
        default=CaptureStatus.RECEIVED,
        nullable=False,
        index=True,
    )

    parse_results: Mapped[list["AIParseResult"]] = relationship(
        "AIParseResult",
        back_populates="capture_input",
        cascade="all, delete-orphan",
    )


class AIParseResult(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ai_parse_results"

    capture_input_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("capture_inputs.id", ondelete="CASCADE"),
        index=True,
    )
    result_type: Mapped[ParseResultType] = mapped_column(
        Enum(ParseResultType, name="parse_result_type", values_callable=enum_values),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    estimated_duration_min: Mapped[int | None] = mapped_column(Integer)
    suggested_priority: Mapped[int | None] = mapped_column(Integer)
    suggested_deadline: Mapped[date | None] = mapped_column(Date)
    suggested_goal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("goals.id", ondelete="SET NULL"))
    confidence: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    raw_model_output: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    capture_input: Mapped[CaptureInput] = relationship("CaptureInput", back_populates="parse_results")
