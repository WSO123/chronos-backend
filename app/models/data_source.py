from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import DataSourceStatus, DataSourceType, enum_values
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class DataSourceConnection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "data_source_connections"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "source_type",
            "provider",
            name="uq_data_source_connections_user_source_provider",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[DataSourceType] = mapped_column(
        Enum(DataSourceType, name="data_source_type", values_callable=enum_values),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[DataSourceStatus] = mapped_column(
        Enum(DataSourceStatus, name="data_source_status", values_callable=enum_values),
        default=DataSourceStatus.CONNECTED,
        nullable=False,
        index=True,
    )
    external_account_label: Mapped[str | None] = mapped_column(String(255))
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    sync_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sync_cursor: Mapped[str | None] = mapped_column(String(500))
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    connection_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="data_source_connections")
