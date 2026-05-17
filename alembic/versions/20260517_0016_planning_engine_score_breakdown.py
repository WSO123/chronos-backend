"""add planning score breakdown

Revision ID: 20260517_0016
Revises: 20260517_0015
Create Date: 2026-05-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260517_0016"
down_revision: Union[str, None] = "20260517_0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "daily_plan_items",
        sa.Column("score_breakdown", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.alter_column("daily_plan_items", "score_breakdown", server_default=None)


def downgrade() -> None:
    op.drop_column("daily_plan_items", "score_breakdown")
