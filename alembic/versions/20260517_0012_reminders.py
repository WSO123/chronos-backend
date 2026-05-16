"""create reminders table

Revision ID: 20260517_0012
Revises: 20260517_0011
Create Date: 2026-05-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260517_0012"
down_revision: Union[str, None] = "20260517_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reminders",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("goal_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("reminder_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("channel", sa.String(length=40), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reminders_goal_id"), "reminders", ["goal_id"], unique=False)
    op.create_index(op.f("ix_reminders_reminder_type"), "reminders", ["reminder_type"], unique=False)
    op.create_index(op.f("ix_reminders_scheduled_for"), "reminders", ["scheduled_for"], unique=False)
    op.create_index(op.f("ix_reminders_status"), "reminders", ["status"], unique=False)
    op.create_index(op.f("ix_reminders_task_id"), "reminders", ["task_id"], unique=False)
    op.create_index(op.f("ix_reminders_user_id"), "reminders", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_reminders_user_id"), table_name="reminders")
    op.drop_index(op.f("ix_reminders_task_id"), table_name="reminders")
    op.drop_index(op.f("ix_reminders_status"), table_name="reminders")
    op.drop_index(op.f("ix_reminders_scheduled_for"), table_name="reminders")
    op.drop_index(op.f("ix_reminders_reminder_type"), table_name="reminders")
    op.drop_index(op.f("ix_reminders_goal_id"), table_name="reminders")
    op.drop_table("reminders")
