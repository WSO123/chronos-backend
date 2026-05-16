from __future__ import annotations

from datetime import date
import uuid

from sqlalchemy import Date, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import InboxItemStatus, InboxItemType, enum_values
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class InboxItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "inbox_items"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    capture_input_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("capture_inputs.id", ondelete="CASCADE"),
        index=True,
    )
    parse_result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_parse_results.id", ondelete="CASCADE"),
        index=True,
    )
    item_type: Mapped[InboxItemType] = mapped_column(
        Enum(InboxItemType, name="inbox_item_type", values_callable=enum_values),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    suggested_goal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("goals.id", ondelete="SET NULL"))
    suggested_priority: Mapped[int | None] = mapped_column(Integer)
    suggested_deadline: Mapped[date | None] = mapped_column(Date)
    status: Mapped[InboxItemStatus] = mapped_column(
        Enum(InboxItemStatus, name="inbox_item_status", values_callable=enum_values),
        default=InboxItemStatus.PENDING,
        nullable=False,
        index=True,
    )
    result_entity_type: Mapped[str | None] = mapped_column(String(80))
    result_entity_id: Mapped[uuid.UUID | None]

    capture_input = relationship("CaptureInput")
    parse_result = relationship("AIParseResult")
