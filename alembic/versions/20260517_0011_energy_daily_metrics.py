"""create energy daily metrics table

Revision ID: 20260517_0011
Revises: 20260517_0010
Create Date: 2026-05-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260517_0011"
down_revision: Union[str, None] = "20260517_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "energy_daily_metrics",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("data_source_connection_id", sa.Uuid(), nullable=True),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("sleep_minutes", sa.Integer(), nullable=True),
        sa.Column("sleep_quality_score", sa.Integer(), nullable=True),
        sa.Column("stress_score", sa.Integer(), nullable=True),
        sa.Column("energy_score", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["data_source_connection_id"], ["data_source_connections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "metric_date", name="uq_energy_daily_metrics_user_date"),
    )
    op.create_index(
        op.f("ix_energy_daily_metrics_data_source_connection_id"),
        "energy_daily_metrics",
        ["data_source_connection_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_energy_daily_metrics_metric_date"),
        "energy_daily_metrics",
        ["metric_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_energy_daily_metrics_user_id"),
        "energy_daily_metrics",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_energy_daily_metrics_user_id"), table_name="energy_daily_metrics")
    op.drop_index(op.f("ix_energy_daily_metrics_metric_date"), table_name="energy_daily_metrics")
    op.drop_index(
        op.f("ix_energy_daily_metrics_data_source_connection_id"),
        table_name="energy_daily_metrics",
    )
    op.drop_table("energy_daily_metrics")
