"""add strategy explanation ai job type

Revision ID: 20260517_0017
Revises: 20260517_0016
Create Date: 2026-05-17 00:17:00.000000
"""

from alembic import op


revision = "20260517_0017"
down_revision = "20260517_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE ai_job_type ADD VALUE IF NOT EXISTS 'strategy_explanation'")


def downgrade() -> None:
    # PostgreSQL enum values are not removed safely without rebuilding dependent columns.
    pass
