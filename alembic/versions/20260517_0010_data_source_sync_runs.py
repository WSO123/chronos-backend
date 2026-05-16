"""create data source sync runs table

Revision ID: 20260517_0010
Revises: 20260517_0009
Create Date: 2026-05-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260517_0010"
down_revision: Union[str, None] = "20260517_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


data_source_type = postgresql.ENUM(
    "calendar",
    "email",
    "health",
    name="data_source_type",
    create_type=False,
)


def upgrade() -> None:
    op.create_table(
        "data_source_sync_runs",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("data_source_connection_id", sa.Uuid(), nullable=True),
        sa.Column("source_type", data_source_type, nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("trigger", sa.String(length=40), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("retryable", sa.Boolean(), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("skip_reason", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processed_count", sa.Integer(), nullable=False),
        sa.Column("imported_count", sa.Integer(), nullable=False),
        sa.Column("reused_count", sa.Integer(), nullable=False),
        sa.Column("fetched_from_provider", sa.Boolean(), nullable=False),
        sa.Column("provider_mode", sa.String(length=40), nullable=True),
        sa.Column("sync_cursor_before", sa.String(length=500), nullable=True),
        sa.Column("sync_cursor_after", sa.String(length=500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["data_source_connection_id"], ["data_source_connections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_data_source_sync_runs_data_source_connection_id"),
        "data_source_sync_runs",
        ["data_source_connection_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_data_source_sync_runs_source_type"),
        "data_source_sync_runs",
        ["source_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_data_source_sync_runs_status"),
        "data_source_sync_runs",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_data_source_sync_runs_user_id"),
        "data_source_sync_runs",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_data_source_sync_runs_user_id"), table_name="data_source_sync_runs")
    op.drop_index(op.f("ix_data_source_sync_runs_status"), table_name="data_source_sync_runs")
    op.drop_index(op.f("ix_data_source_sync_runs_source_type"), table_name="data_source_sync_runs")
    op.drop_index(
        op.f("ix_data_source_sync_runs_data_source_connection_id"),
        table_name="data_source_sync_runs",
    )
    op.drop_table("data_source_sync_runs")
