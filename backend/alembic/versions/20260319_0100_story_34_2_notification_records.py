"""story_34_2_notification_records

Revision ID: 20260319_0100
Revises: 20260318_0100
Create Date: 2026-03-19

Story 34.2: 通知渠道适配器框架 — 创建 notification_records 表
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "20260319_0100"
down_revision: Union[str, None] = "20260318_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "notification_records" not in existing_tables:
        op.create_table(
            "notification_records",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("alarm_id", sa.Integer(), sa.ForeignKey("alarms.id", ondelete="SET NULL"), nullable=True, comment="关联告警"),
            sa.Column("policy_id", sa.Integer(), nullable=True, comment="触发策略ID"),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="通知对象"),
            sa.Column("channel_type", sa.String(20), nullable=False, comment="渠道类型: sms|im|voice|email"),
            sa.Column("platform", sa.String(20), nullable=True, comment="平台: dingtalk|wecom|null"),
            sa.Column("contact_value", sa.String(200), nullable=False, comment="实际发送的联系方式"),
            sa.Column("content_summary", sa.String(500), nullable=True, comment="发送内容摘要"),
            sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'"), comment="状态: pending|sent|failed|retrying"),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0"), comment="已重试次数"),
            sa.Column("max_retries", sa.Integer(), nullable=False, server_default=sa.text("3"), comment="最大重试次数"),
            sa.Column("sent_at", sa.DateTime(), nullable=True, comment="发送成功时间"),
            sa.Column("error_message", sa.Text(), nullable=True, comment="错误信息"),
            sa.Column("created_at", sa.DateTime(), nullable=True, comment="创建时间"),
        )
        op.create_index("ix_nr_alarm_id", "notification_records", ["alarm_id"])
        op.create_index("ix_nr_status", "notification_records", ["status"])
        op.create_index("ix_nr_created_at", "notification_records", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_nr_created_at", table_name="notification_records")
    op.drop_index("ix_nr_status", table_name="notification_records")
    op.drop_index("ix_nr_alarm_id", table_name="notification_records")
    op.drop_table("notification_records")
