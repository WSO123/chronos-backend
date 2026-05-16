"""create external capture imports table

Revision ID: 20260517_0009
Revises: 20260516_0008
Create Date: 2026-05-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260517_0009"
down_revision: Union[str, None] = "20260516_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


capture_source = postgresql.ENUM(
    "manual",
    "voice",
    "image",
    "email",
    "calendar",
    name="capture_source",
    create_type=False,
)


def upgrade() -> None:
    op.create_table(
        "external_capture_imports",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("data_source_connection_id", sa.Uuid(), nullable=True),
        sa.Column("source", capture_source, nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("external_item_id", sa.String(length=255), nullable=False),
        sa.Column("external_item_type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("external_payload", sa.JSON(), nullable=False),
        sa.Column("capture_input_id", sa.Uuid(), nullable=True),
        sa.Column("inbox_item_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["capture_input_id"], ["capture_inputs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["data_source_connection_id"], ["data_source_connections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["inbox_item_id"], ["inbox_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "source",
            "provider",
            "external_item_id",
            name="uq_external_capture_imports_external_item",
        ),
    )
    op.create_index(
        op.f("ix_external_capture_imports_capture_input_id"),
        "external_capture_imports",
        ["capture_input_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_external_capture_imports_data_source_connection_id"),
        "external_capture_imports",
        ["data_source_connection_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_external_capture_imports_inbox_item_id"),
        "external_capture_imports",
        ["inbox_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_external_capture_imports_source"),
        "external_capture_imports",
        ["source"],
        unique=False,
    )
    op.create_index(
        op.f("ix_external_capture_imports_user_id"),
        "external_capture_imports",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_external_capture_imports_user_id"), table_name="external_capture_imports")
    op.drop_index(op.f("ix_external_capture_imports_source"), table_name="external_capture_imports")
    op.drop_index(op.f("ix_external_capture_imports_inbox_item_id"), table_name="external_capture_imports")
    op.drop_index(op.f("ix_external_capture_imports_data_source_connection_id"), table_name="external_capture_imports")
    op.drop_index(op.f("ix_external_capture_imports_capture_input_id"), table_name="external_capture_imports")
    op.drop_table("external_capture_imports")
