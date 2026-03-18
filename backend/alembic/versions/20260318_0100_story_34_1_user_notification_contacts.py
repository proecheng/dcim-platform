"""story_34_1_user_notification_contacts

Revision ID: 20260318_0100
Revises: 20260314_0200
Create Date: 2026-03-18

Story 34.1: 用户通知联系方式管理 — 创建 user_notification_contacts 表
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "20260318_0100"
down_revision: Union[str, None] = "20260314_0200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "user_notification_contacts" not in existing_tables:
        op.create_table(
            "user_notification_contacts",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID"),
            sa.Column("channel_type", sa.String(20), nullable=False, comment="渠道类型: sms|im|voice|email"),
            sa.Column("platform", sa.String(20), nullable=True, comment="平台: dingtalk|wecom|null"),
            sa.Column("contact_value", sa.String(200), nullable=False, comment="联系方式值"),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1"), comment="是否启用"),
            sa.Column("created_at", sa.DateTime(), nullable=True, comment="创建时间"),
            sa.Column("updated_at", sa.DateTime(), nullable=True, comment="更新时间"),
        )
        op.create_index("ix_unc_user_id", "user_notification_contacts", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_unc_user_id", table_name="user_notification_contacts")
    op.drop_table("user_notification_contacts")
