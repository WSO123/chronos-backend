"""create data source connections table

Revision ID: 20260516_0008
Revises: 20260516_0007
Create Date: 2026-05-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260516_0008"
down_revision: Union[str, None] = "20260516_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


data_source_type = postgresql.ENUM(
    "calendar",
    "email",
    "health",
    name="data_source_type",
    create_type=False,
)
data_source_status = postgresql.ENUM(
    "disconnected",
    "connected",
    "needs_reauth",
    "paused",
    name="data_source_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM("calendar", "email", "health", name="data_source_type").create(bind, checkfirst=True)
    postgresql.ENUM(
        "disconnected",
        "connected",
        "needs_reauth",
        "paused",
        name="data_source_status",
    ).create(bind, checkfirst=True)
    op.execute("ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'data_source'")

    op.create_table(
        "data_source_connections",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", data_source_type, nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("status", data_source_status, nullable=False),
        sa.Column("external_account_label", sa.String(length=255), nullable=True),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("sync_enabled", sa.Boolean(), nullable=False),
        sa.Column("sync_cursor", sa.String(length=500), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "source_type",
            "provider",
            name="uq_data_source_connections_user_source_provider",
        ),
    )
    op.create_index(
        op.f("ix_data_source_connections_source_type"),
        "data_source_connections",
        ["source_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_data_source_connections_status"),
        "data_source_connections",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_data_source_connections_user_id"),
        "data_source_connections",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_data_source_connections_user_id"), table_name="data_source_connections")
    op.drop_index(op.f("ix_data_source_connections_status"), table_name="data_source_connections")
    op.drop_index(op.f("ix_data_source_connections_source_type"), table_name="data_source_connections")
    op.drop_table("data_source_connections")
    data_source_status.drop(op.get_bind(), checkfirst=True)
    data_source_type.drop(op.get_bind(), checkfirst=True)
