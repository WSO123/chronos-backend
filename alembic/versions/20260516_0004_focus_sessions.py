"""create focus session table

Revision ID: 20260516_0004
Revises: 20260516_0003
Create Date: 2026-05-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260516_0004"
down_revision: Union[str, None] = "20260516_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


focus_session_status = sa.Enum(
    "active",
    "paused",
    "completed",
    "interrupted",
    "postponed",
    name="focus_session_status",
)


def upgrade() -> None:
    op.create_table(
        "focus_sessions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("daily_plan_id", sa.Uuid(), nullable=True),
        sa.Column("daily_plan_item_id", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("planned_duration_min", sa.Integer(), nullable=True),
        sa.Column("actual_duration_min", sa.Integer(), nullable=False),
        sa.Column("status", focus_session_status, nullable=False),
        sa.Column("interruption_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["daily_plan_id"], ["daily_plans.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["daily_plan_item_id"], ["daily_plan_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_focus_sessions_daily_plan_id"), "focus_sessions", ["daily_plan_id"], unique=False)
    op.create_index(op.f("ix_focus_sessions_daily_plan_item_id"), "focus_sessions", ["daily_plan_item_id"], unique=False)
    op.create_index(op.f("ix_focus_sessions_status"), "focus_sessions", ["status"], unique=False)
    op.create_index(op.f("ix_focus_sessions_task_id"), "focus_sessions", ["task_id"], unique=False)
    op.create_index(op.f("ix_focus_sessions_user_id"), "focus_sessions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_focus_sessions_user_id"), table_name="focus_sessions")
    op.drop_index(op.f("ix_focus_sessions_task_id"), table_name="focus_sessions")
    op.drop_index(op.f("ix_focus_sessions_status"), table_name="focus_sessions")
    op.drop_index(op.f("ix_focus_sessions_daily_plan_item_id"), table_name="focus_sessions")
    op.drop_index(op.f("ix_focus_sessions_daily_plan_id"), table_name="focus_sessions")
    op.drop_table("focus_sessions")

    focus_session_status.drop(op.get_bind())
