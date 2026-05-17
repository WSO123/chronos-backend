"""add auth password and refresh tokens

Revision ID: 20260517_0019
Revises: 20260517_0018
Create Date: 2026-05-17 00:19:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260517_0019"
down_revision: Union[str, None] = "20260517_0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.create_table(
        "auth_refresh_tokens",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_auth_refresh_tokens_token_hash"), "auth_refresh_tokens", ["token_hash"], unique=True)
    op.create_index(op.f("ix_auth_refresh_tokens_user_id"), "auth_refresh_tokens", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_auth_refresh_tokens_user_id"), table_name="auth_refresh_tokens")
    op.drop_index(op.f("ix_auth_refresh_tokens_token_hash"), table_name="auth_refresh_tokens")
    op.drop_table("auth_refresh_tokens")
    op.drop_column("users", "password_hash")
