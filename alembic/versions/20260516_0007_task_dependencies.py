"""create task dependencies table

Revision ID: 20260516_0007
Revises: 20260516_0006
Create Date: 2026-05-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260516_0007"
down_revision: Union[str, None] = "20260516_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_dependencies",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("dependent_task_id", sa.Uuid(), nullable=False),
        sa.Column("prerequisite_task_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dependent_task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prerequisite_task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dependent_task_id", "prerequisite_task_id", name="uq_task_dependencies_edge"),
    )
    op.create_index(op.f("ix_task_dependencies_dependent_task_id"), "task_dependencies", ["dependent_task_id"], unique=False)
    op.create_index(
        op.f("ix_task_dependencies_prerequisite_task_id"),
        "task_dependencies",
        ["prerequisite_task_id"],
        unique=False,
    )
    op.create_index(op.f("ix_task_dependencies_user_id"), "task_dependencies", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_task_dependencies_user_id"), table_name="task_dependencies")
    op.drop_index(op.f("ix_task_dependencies_prerequisite_task_id"), table_name="task_dependencies")
    op.drop_index(op.f("ix_task_dependencies_dependent_task_id"), table_name="task_dependencies")
    op.drop_table("task_dependencies")
