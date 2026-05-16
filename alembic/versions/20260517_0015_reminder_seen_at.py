"""add seen_at to reminders

Revision ID: 20260517_0015
Revises: 20260517_0014
Create Date: 2026-05-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260517_0015"
down_revision: Union[str, None] = "20260517_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("reminders", sa.Column("seen_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("reminders", "seen_at")
