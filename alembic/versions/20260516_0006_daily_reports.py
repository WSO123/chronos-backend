"""create daily report table

Revision ID: 20260516_0006
Revises: 20260516_0005
Create Date: 2026-05-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260516_0006"
down_revision: Union[str, None] = "20260516_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "daily_reports",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("daily_plan_id", sa.Uuid(), nullable=True),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("completed_task_count", sa.Integer(), nullable=False),
        sa.Column("postponed_task_count", sa.Integer(), nullable=False),
        sa.Column("interrupted_count", sa.Integer(), nullable=False),
        sa.Column("focus_minutes", sa.Integer(), nullable=False),
        sa.Column("completion_rate", sa.Float(), nullable=False),
        sa.Column("ai_summary", sa.Text(), nullable=False),
        sa.Column("ai_suggestions", sa.JSON(), nullable=False),
        sa.Column("generated_from_plan_version", sa.Integer(), nullable=True),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["daily_plan_id"], ["daily_plans.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "report_date", name="uq_daily_reports_user_date"),
    )
    op.create_index(op.f("ix_daily_reports_daily_plan_id"), "daily_reports", ["daily_plan_id"], unique=False)
    op.create_index(op.f("ix_daily_reports_report_date"), "daily_reports", ["report_date"], unique=False)
    op.create_index(op.f("ix_daily_reports_user_id"), "daily_reports", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_daily_reports_user_id"), table_name="daily_reports")
    op.drop_index(op.f("ix_daily_reports_report_date"), table_name="daily_reports")
    op.drop_index(op.f("ix_daily_reports_daily_plan_id"), table_name="daily_reports")
    op.drop_table("daily_reports")
