"""add reminder preferences to user settings

Revision ID: 20260517_0013
Revises: 20260517_0012
Create Date: 2026-05-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260517_0013"
down_revision: Union[str, None] = "20260517_0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("reminder_execution_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "user_settings",
        sa.Column("reminder_deadline_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "user_settings",
        sa.Column("reminder_channel_in_app_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "user_settings",
        sa.Column("reminder_channel_push_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "user_settings",
        sa.Column("reminder_channel_email_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "user_settings",
        sa.Column("execution_reminder_limit", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "user_settings",
        sa.Column("execution_reminder_start_hour", sa.Integer(), nullable=False, server_default="9"),
    )
    op.add_column(
        "user_settings",
        sa.Column("execution_reminder_spacing_minutes", sa.Integer(), nullable=False, server_default="45"),
    )
    op.add_column(
        "user_settings",
        sa.Column("deadline_reminder_hour", sa.Integer(), nullable=False, server_default="9"),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "deadline_reminder_hour")
    op.drop_column("user_settings", "execution_reminder_spacing_minutes")
    op.drop_column("user_settings", "execution_reminder_start_hour")
    op.drop_column("user_settings", "execution_reminder_limit")
    op.drop_column("user_settings", "reminder_channel_email_enabled")
    op.drop_column("user_settings", "reminder_channel_push_enabled")
    op.drop_column("user_settings", "reminder_channel_in_app_enabled")
    op.drop_column("user_settings", "reminder_deadline_enabled")
    op.drop_column("user_settings", "reminder_execution_enabled")
