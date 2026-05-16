"""create reminder delivery attempts table

Revision ID: 20260517_0014
Revises: 20260517_0013
Create Date: 2026-05-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260517_0014"
down_revision: Union[str, None] = "20260517_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reminder_delivery_attempts",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("reminder_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=40), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.String(length=120), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["reminder_id"], ["reminders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_reminder_delivery_attempts_attempted_at"),
        "reminder_delivery_attempts",
        ["attempted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reminder_delivery_attempts_next_retry_at"),
        "reminder_delivery_attempts",
        ["next_retry_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reminder_delivery_attempts_reminder_id"),
        "reminder_delivery_attempts",
        ["reminder_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reminder_delivery_attempts_status"),
        "reminder_delivery_attempts",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reminder_delivery_attempts_user_id"),
        "reminder_delivery_attempts",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_reminder_delivery_attempts_user_id"), table_name="reminder_delivery_attempts")
    op.drop_index(op.f("ix_reminder_delivery_attempts_status"), table_name="reminder_delivery_attempts")
    op.drop_index(op.f("ix_reminder_delivery_attempts_reminder_id"), table_name="reminder_delivery_attempts")
    op.drop_index(op.f("ix_reminder_delivery_attempts_next_retry_at"), table_name="reminder_delivery_attempts")
    op.drop_index(op.f("ix_reminder_delivery_attempts_attempted_at"), table_name="reminder_delivery_attempts")
    op.drop_table("reminder_delivery_attempts")
