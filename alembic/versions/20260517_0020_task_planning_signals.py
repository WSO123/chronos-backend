"""add task semantic planning signals

Revision ID: 20260517_0020
Revises: 20260517_0019
Create Date: 2026-05-17 00:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260517_0020"
down_revision: Union[str, None] = "20260517_0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE ai_job_type ADD VALUE IF NOT EXISTS 'task_semantic_planning'")
    op.execute("ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'task_planning_signal'")

    op.create_table(
        "task_planning_signals",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("ai_job_id", sa.Uuid(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("complexity", sa.String(length=16), nullable=False),
        sa.Column("cognitive_load", sa.String(length=16), nullable=False),
        sa.Column("energy_fit", sa.String(length=32), nullable=False),
        sa.Column("blocking_risk", sa.String(length=16), nullable=False),
        sa.Column("estimated_duration_min", sa.Integer(), nullable=True),
        sa.Column("duration_confidence", sa.Float(), nullable=False),
        sa.Column("goal_alignment_score", sa.Float(), nullable=False),
        sa.Column("semantic_priority_score", sa.Float(), nullable=False),
        sa.Column("breakdown_recommended", sa.Boolean(), nullable=False),
        sa.Column("minimum_viable_step", sa.String(length=255), nullable=True),
        sa.Column("semantic_summary", sa.String(length=500), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ai_job_id"], ["ai_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_task_planning_signals_ai_job_id"), "task_planning_signals", ["ai_job_id"], unique=False)
    op.create_index(op.f("ix_task_planning_signals_task_id"), "task_planning_signals", ["task_id"], unique=False)
    op.create_index(op.f("ix_task_planning_signals_user_id"), "task_planning_signals", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_task_planning_signals_user_id"), table_name="task_planning_signals")
    op.drop_index(op.f("ix_task_planning_signals_task_id"), table_name="task_planning_signals")
    op.drop_index(op.f("ix_task_planning_signals_ai_job_id"), table_name="task_planning_signals")
    op.drop_table("task_planning_signals")
    # PostgreSQL enum values are intentionally kept to avoid unsafe enum rewrites.
