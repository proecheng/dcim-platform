"""story_26_10_hmac_key_rotation_logs

Revision ID: 20260314_0200
Revises: 20260314_0100
Create Date: 2026-03-14

Story 26.10: HMAC 密钥管理 — 创建 hmac_key_rotation_logs 表
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '20260314_0200'
down_revision: Union[str, None] = '20260314_0100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()

    if "hmac_key_rotation_logs" not in existing_tables:
        op.create_table(
            "hmac_key_rotation_logs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("rotated_at", sa.DateTime(), nullable=False),
            sa.Column("rotated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("versions_resigned", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("resigned_version_ids", sa.JSON(), nullable=True),
            sa.Column("new_key_prefix", sa.String(4), nullable=False),
            sa.Column("old_key_prefix", sa.String(4), nullable=True),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("error_detail", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("hmac_key_rotation_logs")
