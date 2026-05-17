"""add insight generator ai job type

Revision ID: 20260517_0018
Revises: 20260517_0017
Create Date: 2026-05-17 00:18:00.000000
"""

from alembic import op


revision = "20260517_0018"
down_revision = "20260517_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE ai_job_type ADD VALUE IF NOT EXISTS 'insight_generator'")


def downgrade() -> None:
    # PostgreSQL enum values are not removed safely without rebuilding dependent columns.
    pass
