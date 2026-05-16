"""create chronos foundation tables

Revision ID: 20260516_0001
Revises:
Create Date: 2026-05-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260516_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


planning_preference = sa.Enum("light", "normal", "sprint", name="planning_preference")
ai_strategy_preference = sa.Enum(
    "balanced",
    "high_value_first",
    "energy_aware",
    name="ai_strategy_preference",
)
value_level = sa.Enum("low", "medium", "high", name="value_level")
goal_status = sa.Enum("active", "completed", "archived", name="goal_status")
task_status = sa.Enum("active", "in_focus", "completed", "postponed", "archived", name="task_status")
task_source = sa.Enum("manual", "capture", "ai", "email", "calendar", name="task_source")
entity_type = sa.Enum(
    "task",
    "goal",
    "capture",
    "inbox",
    "daily_plan",
    "focus_session",
    "ai_job",
    "report",
    name="entity_type",
)
actor_type = sa.Enum("user", "ai", "system", name="actor_type")
event_source = sa.Enum("api", "worker", "scheduler", name="event_source")
ai_job_type = sa.Enum(
    "capture_parser",
    "daily_planner",
    "task_breakdown",
    "daily_report_generator",
    name="ai_job_type",
)
ai_job_status = sa.Enum(
    "queued",
    "running",
    "succeeded",
    "succeeded_with_fallback",
    "failed",
    "canceled",
    name="ai_job_status",
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("notification_enabled", sa.Boolean(), nullable=False),
        sa.Column("focus_mode_default_minutes", sa.Integer(), nullable=False),
        sa.Column("planning_preference", planning_preference, nullable=False),
        sa.Column("ai_strategy_preference", ai_strategy_preference, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "goals",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("value_level", value_level, nullable=False),
        sa.Column("status", goal_status, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_goals_user_id"), "goals", ["user_id"], unique=False)

    op.create_table(
        "tasks",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("goal_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("estimated_duration_min", sa.Integer(), nullable=True),
        sa.Column("actual_duration_min", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("value_level", value_level, nullable=False),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("progress", sa.Numeric(3, 2), nullable=False),
        sa.Column("status", task_status, nullable=False),
        sa.Column("source", task_source, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tasks_goal_id"), "tasks", ["goal_id"], unique=False)
    op.create_index(op.f("ix_tasks_user_id"), "tasks", ["user_id"], unique=False)

    op.create_table(
        "task_steps",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_completed", sa.Boolean(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_task_steps_task_id"), "task_steps", ["task_id"], unique=False)

    op.create_table(
        "activity_events",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", entity_type, nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("related_task_id", sa.Uuid(), nullable=True),
        sa.Column("related_daily_plan_id", sa.Uuid(), nullable=True),
        sa.Column("related_focus_session_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("actor_type", actor_type, nullable=False),
        sa.Column("source", event_source, nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["related_task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        "ix_activity_events_user_occurred_at",
        "activity_events",
        ["user_id", "occurred_at"],
        unique=False,
    )
    op.create_index(op.f("ix_activity_events_entity_id"), "activity_events", ["entity_id"], unique=False)
    op.create_index(op.f("ix_activity_events_event_type"), "activity_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_activity_events_user_id"), "activity_events", ["user_id"], unique=False)

    op.create_table(
        "ai_jobs",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("job_type", ai_job_type, nullable=False),
        sa.Column("status", ai_job_status, nullable=False),
        sa.Column("input_entity_type", sa.String(length=80), nullable=False),
        sa.Column("input_entity_id", sa.Uuid(), nullable=False),
        sa.Column("result_entity_type", sa.String(length=80), nullable=True),
        sa.Column("result_entity_id", sa.Uuid(), nullable=True),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("provider", sa.String(length=80), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("prompt_version", sa.String(length=80), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_jobs_celery_task_id"), "ai_jobs", ["celery_task_id"], unique=False)
    op.create_index(op.f("ix_ai_jobs_input_entity_id"), "ai_jobs", ["input_entity_id"], unique=False)
    op.create_index(op.f("ix_ai_jobs_status"), "ai_jobs", ["status"], unique=False)
    op.create_index(op.f("ix_ai_jobs_user_id"), "ai_jobs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_jobs_user_id"), table_name="ai_jobs")
    op.drop_index(op.f("ix_ai_jobs_status"), table_name="ai_jobs")
    op.drop_index(op.f("ix_ai_jobs_input_entity_id"), table_name="ai_jobs")
    op.drop_index(op.f("ix_ai_jobs_celery_task_id"), table_name="ai_jobs")
    op.drop_table("ai_jobs")

    op.drop_index(op.f("ix_activity_events_user_id"), table_name="activity_events")
    op.drop_index(op.f("ix_activity_events_event_type"), table_name="activity_events")
    op.drop_index(op.f("ix_activity_events_entity_id"), table_name="activity_events")
    op.drop_index("ix_activity_events_user_occurred_at", table_name="activity_events")
    op.drop_table("activity_events")

    op.drop_index(op.f("ix_task_steps_task_id"), table_name="task_steps")
    op.drop_table("task_steps")

    op.drop_index(op.f("ix_tasks_user_id"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_goal_id"), table_name="tasks")
    op.drop_table("tasks")

    op.drop_index(op.f("ix_goals_user_id"), table_name="goals")
    op.drop_table("goals")

    op.drop_table("user_settings")

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

    ai_job_status.drop(op.get_bind())
    ai_job_type.drop(op.get_bind())
    event_source.drop(op.get_bind())
    actor_type.drop(op.get_bind())
    entity_type.drop(op.get_bind())
    task_source.drop(op.get_bind())
    task_status.drop(op.get_bind())
    goal_status.drop(op.get_bind())
    value_level.drop(op.get_bind())
    ai_strategy_preference.drop(op.get_bind())
    planning_preference.drop(op.get_bind())
