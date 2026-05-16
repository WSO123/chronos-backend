"""create today daily plan tables

Revision ID: 20260516_0003
Revises: 20260516_0002
Create Date: 2026-05-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260516_0003"
down_revision: Union[str, None] = "20260516_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


daily_plan_status = sa.Enum("draft", "active", "closed", name="daily_plan_status")
plan_revision_trigger = sa.Enum(
    "initial",
    "replan",
    "manual_adjust",
    "system_refresh",
    name="plan_revision_trigger",
)
daily_plan_item_section = sa.Enum(
    "pinned",
    "recommended",
    "low_priority",
    "rolled_over",
    name="daily_plan_item_section",
)
daily_plan_item_status = sa.Enum(
    "planned",
    "completed",
    "postponed",
    "skipped",
    name="daily_plan_item_status",
)
actor_type = sa.Enum("user", "ai", "system", name="actor_type", create_type=False)
planning_preference = sa.Enum("light", "normal", "sprint", name="planning_preference", create_type=False)


def upgrade() -> None:
    op.create_table(
        "daily_plans",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("status", daily_plan_status, nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("current_revision_id", sa.Uuid(), nullable=True),
        sa.Column("total_estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("completed_count", sa.Integer(), nullable=False),
        sa.Column("focus_minutes", sa.Integer(), nullable=False),
        sa.Column("created_by", actor_type, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "plan_date", "status", name="uq_daily_plans_user_date_status"),
    )
    op.create_index(op.f("ix_daily_plans_plan_date"), "daily_plans", ["plan_date"], unique=False)
    op.create_index(op.f("ix_daily_plans_status"), "daily_plans", ["status"], unique=False)
    op.create_index(op.f("ix_daily_plans_user_id"), "daily_plans", ["user_id"], unique=False)

    op.create_table(
        "plan_revisions",
        sa.Column("daily_plan_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("trigger", plan_revision_trigger, nullable=False),
        sa.Column("created_by", actor_type, nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("diff_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["daily_plan_id"], ["daily_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("daily_plan_id", "version", name="uq_plan_revisions_daily_plan_version"),
    )
    op.create_index(op.f("ix_plan_revisions_daily_plan_id"), "plan_revisions", ["daily_plan_id"], unique=False)

    op.create_table(
        "strategy_snapshots",
        sa.Column("daily_plan_id", sa.Uuid(), nullable=False),
        sa.Column("plan_revision_id", sa.Uuid(), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("mode", planning_preference, nullable=False),
        sa.Column("primary_reason", sa.String(length=500), nullable=False),
        sa.Column("score_factors", sa.JSON(), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("prompt_version", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["daily_plan_id"], ["daily_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_revision_id"], ["plan_revisions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_strategy_snapshots_daily_plan_id"), "strategy_snapshots", ["daily_plan_id"], unique=False)
    op.create_index(
        op.f("ix_strategy_snapshots_plan_revision_id"),
        "strategy_snapshots",
        ["plan_revision_id"],
        unique=False,
    )

    op.create_table(
        "daily_plan_items",
        sa.Column("daily_plan_id", sa.Uuid(), nullable=False),
        sa.Column("plan_revision_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("section", daily_plan_item_section, nullable=False),
        sa.Column("recommendation_reason", sa.String(length=500), nullable=False),
        sa.Column("estimated_duration_min", sa.Integer(), nullable=True),
        sa.Column("status", daily_plan_item_status, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["daily_plan_id"], ["daily_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_revision_id"], ["plan_revisions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_daily_plan_items_daily_plan_id"), "daily_plan_items", ["daily_plan_id"], unique=False)
    op.create_index(op.f("ix_daily_plan_items_plan_revision_id"), "daily_plan_items", ["plan_revision_id"], unique=False)
    op.create_index(op.f("ix_daily_plan_items_section"), "daily_plan_items", ["section"], unique=False)
    op.create_index(op.f("ix_daily_plan_items_status"), "daily_plan_items", ["status"], unique=False)
    op.create_index(op.f("ix_daily_plan_items_task_id"), "daily_plan_items", ["task_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_daily_plan_items_task_id"), table_name="daily_plan_items")
    op.drop_index(op.f("ix_daily_plan_items_status"), table_name="daily_plan_items")
    op.drop_index(op.f("ix_daily_plan_items_section"), table_name="daily_plan_items")
    op.drop_index(op.f("ix_daily_plan_items_plan_revision_id"), table_name="daily_plan_items")
    op.drop_index(op.f("ix_daily_plan_items_daily_plan_id"), table_name="daily_plan_items")
    op.drop_table("daily_plan_items")

    op.drop_index(op.f("ix_strategy_snapshots_plan_revision_id"), table_name="strategy_snapshots")
    op.drop_index(op.f("ix_strategy_snapshots_daily_plan_id"), table_name="strategy_snapshots")
    op.drop_table("strategy_snapshots")

    op.drop_index(op.f("ix_plan_revisions_daily_plan_id"), table_name="plan_revisions")
    op.drop_table("plan_revisions")

    op.drop_index(op.f("ix_daily_plans_user_id"), table_name="daily_plans")
    op.drop_index(op.f("ix_daily_plans_status"), table_name="daily_plans")
    op.drop_index(op.f("ix_daily_plans_plan_date"), table_name="daily_plans")
    op.drop_table("daily_plans")

    daily_plan_item_status.drop(op.get_bind())
    daily_plan_item_section.drop(op.get_bind())
    plan_revision_trigger.drop(op.get_bind())
    daily_plan_status.drop(op.get_bind())
