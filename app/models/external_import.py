from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import CaptureSource, enum_values
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ExternalCaptureImport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "external_capture_imports"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "source",
            "provider",
            "external_item_id",
            name="uq_external_capture_imports_external_item",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    data_source_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_source_connections.id", ondelete="SET NULL"),
        index=True,
    )
    source: Mapped[CaptureSource] = mapped_column(
        Enum(CaptureSource, name="capture_source", values_callable=enum_values),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    external_item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_item_type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    external_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    capture_input_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("capture_inputs.id", ondelete="SET NULL"),
        index=True,
    )
    inbox_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inbox_items.id", ondelete="SET NULL"),
        index=True,
    )

    data_source_connection = relationship("DataSourceConnection")
    capture_input = relationship("CaptureInput")
    inbox_item = relationship("InboxItem")
