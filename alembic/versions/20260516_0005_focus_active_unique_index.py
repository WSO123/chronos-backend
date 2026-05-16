"""add active focus session uniqueness

Revision ID: 20260516_0005
Revises: 20260516_0004
Create Date: 2026-05-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260516_0005"
down_revision: Union[str, None] = "20260516_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_focus_sessions_user_active",
        "focus_sessions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uq_focus_sessions_user_active", table_name="focus_sessions")
