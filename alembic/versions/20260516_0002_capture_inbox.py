"""create capture and inbox tables

Revision ID: 20260516_0002
Revises: 20260516_0001
Create Date: 2026-05-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260516_0002"
down_revision: Union[str, None] = "20260516_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


capture_input_type = sa.Enum("text", "voice", "image", "external", name="capture_input_type")
capture_source = sa.Enum("manual", "voice", "image", "email", "calendar", name="capture_source")
capture_status = sa.Enum("received", "parsing", "parsed", "failed", "archived", name="capture_status")
parse_result_type = sa.Enum(
    "task",
    "goal",
    "idea",
    "calendar_item",
    "unknown",
    name="parse_result_type",
)
inbox_item_type = sa.Enum("task", "goal", "idea", "unknown", name="inbox_item_type")
inbox_item_status = sa.Enum("pending", "confirmed", "edited", "discarded", name="inbox_item_status")


def upgrade() -> None:
    op.create_table(
        "capture_inputs",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("input_type", capture_input_type, nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("attachment_url", sa.String(length=500), nullable=True),
        sa.Column("source", capture_source, nullable=False),
        sa.Column("status", capture_status, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_capture_inputs_status"), "capture_inputs", ["status"], unique=False)
    op.create_index(op.f("ix_capture_inputs_user_id"), "capture_inputs", ["user_id"], unique=False)

    op.create_table(
        "ai_parse_results",
        sa.Column("capture_input_id", sa.Uuid(), nullable=False),
        sa.Column("result_type", parse_result_type, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("estimated_duration_min", sa.Integer(), nullable=True),
        sa.Column("suggested_priority", sa.Integer(), nullable=True),
        sa.Column("suggested_deadline", sa.Date(), nullable=True),
        sa.Column("suggested_goal_id", sa.Uuid(), nullable=True),
        sa.Column("confidence", sa.Numeric(3, 2), nullable=False),
        sa.Column("raw_model_output", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["capture_input_id"], ["capture_inputs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["suggested_goal_id"], ["goals.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_parse_results_capture_input_id"), "ai_parse_results", ["capture_input_id"], unique=False)
    op.create_index(op.f("ix_ai_parse_results_result_type"), "ai_parse_results", ["result_type"], unique=False)

    op.create_table(
        "inbox_items",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("capture_input_id", sa.Uuid(), nullable=False),
        sa.Column("parse_result_id", sa.Uuid(), nullable=False),
        sa.Column("item_type", inbox_item_type, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("suggested_goal_id", sa.Uuid(), nullable=True),
        sa.Column("suggested_priority", sa.Integer(), nullable=True),
        sa.Column("suggested_deadline", sa.Date(), nullable=True),
        sa.Column("status", inbox_item_status, nullable=False),
        sa.Column("result_entity_type", sa.String(length=80), nullable=True),
        sa.Column("result_entity_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["capture_input_id"], ["capture_inputs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parse_result_id"], ["ai_parse_results.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["suggested_goal_id"], ["goals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_inbox_items_capture_input_id"), "inbox_items", ["capture_input_id"], unique=False)
    op.create_index(op.f("ix_inbox_items_item_type"), "inbox_items", ["item_type"], unique=False)
    op.create_index(op.f("ix_inbox_items_parse_result_id"), "inbox_items", ["parse_result_id"], unique=False)
    op.create_index(op.f("ix_inbox_items_status"), "inbox_items", ["status"], unique=False)
    op.create_index(op.f("ix_inbox_items_user_id"), "inbox_items", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_inbox_items_user_id"), table_name="inbox_items")
    op.drop_index(op.f("ix_inbox_items_status"), table_name="inbox_items")
    op.drop_index(op.f("ix_inbox_items_parse_result_id"), table_name="inbox_items")
    op.drop_index(op.f("ix_inbox_items_item_type"), table_name="inbox_items")
    op.drop_index(op.f("ix_inbox_items_capture_input_id"), table_name="inbox_items")
    op.drop_table("inbox_items")

    op.drop_index(op.f("ix_ai_parse_results_result_type"), table_name="ai_parse_results")
    op.drop_index(op.f("ix_ai_parse_results_capture_input_id"), table_name="ai_parse_results")
    op.drop_table("ai_parse_results")

    op.drop_index(op.f("ix_capture_inputs_user_id"), table_name="capture_inputs")
    op.drop_index(op.f("ix_capture_inputs_status"), table_name="capture_inputs")
    op.drop_table("capture_inputs")

    inbox_item_status.drop(op.get_bind())
    inbox_item_type.drop(op.get_bind())
    parse_result_type.drop(op.get_bind())
    capture_status.drop(op.get_bind())
    capture_source.drop(op.get_bind())
    capture_input_type.drop(op.get_bind())
