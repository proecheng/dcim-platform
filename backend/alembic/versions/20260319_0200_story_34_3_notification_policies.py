"""story_34_3_notification_policies

Revision ID: 20260319_0200
Revises: 20260319_0100
Create Date: 2026-03-19

Story 34.3: 通知策略配置 — 创建 notification_policies 表 + seed 4 条默认策略
"""

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "20260319_0200"
down_revision: Union[str, None] = "20260319_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "notification_policies" not in existing_tables:
        op.create_table(
            "notification_policies",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(100), nullable=False, comment="策略名称"),
            sa.Column(
                "site_id",
                sa.Integer(),
                sa.ForeignKey("sites.id", ondelete="CASCADE"),
                nullable=True,
                comment="站点ID, NULL=全局默认",
            ),
            sa.Column(
                "alarm_level",
                sa.String(20),
                nullable=False,
                comment="告警级别: critical|major|minor|info",
            ),
            sa.Column(
                "time_range_start",
                sa.String(5),
                nullable=True,
                comment="时段开始 HH:MM, NULL=全天",
            ),
            sa.Column(
                "time_range_end",
                sa.String(5),
                nullable=True,
                comment="时段结束 HH:MM",
            ),
            sa.Column(
                "channels",
                sa.JSON(),
                nullable=False,
                comment='渠道组合: ["im","sms"]',
            ),
            sa.Column(
                "notify_user_ids",
                sa.JSON(),
                nullable=False,
                comment="通知对象: [1,2,3]",
            ),
            sa.Column(
                "channel_escalation_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
                comment="是否启用渠道升级",
            ),
            sa.Column(
                "escalation_timeout_minutes",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("5"),
                comment="渠道升级超时(分钟)",
            ),
            sa.Column(
                "escalation_channel_order",
                sa.JSON(),
                nullable=True,
                comment='升级顺序: ["im","sms","voice"]',
            ),
            sa.Column(
                "is_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("1"),
                comment="是否启用",
            ),
            sa.Column(
                "is_default",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
                comment="是否为系统默认(不可删除)",
            ),
            sa.Column("created_at", sa.DateTime(), nullable=True, comment="创建时间"),
            sa.Column("updated_at", sa.DateTime(), nullable=True, comment="更新时间"),
        )
        op.create_index("ix_np_site_level", "notification_policies", ["site_id", "alarm_level"])

    # Seed 4 条全局默认策略（幂等）
    count = conn.execute(
        sa.text("SELECT COUNT(*) FROM notification_policies WHERE is_default = 1")
    ).scalar()

    if count == 0:
        default_policies = [
            ("全局紧急告警默认策略", "critical", ["im", "sms"]),
            ("全局重要告警默认策略", "major", ["im"]),
            ("全局次要告警默认策略", "minor", ["im"]),
            ("全局信息告警默认策略", "info", ["im"]),
        ]
        for name, level, channels in default_policies:
            conn.execute(
                sa.text(
                    "INSERT INTO notification_policies "
                    "(name, site_id, alarm_level, time_range_start, time_range_end, "
                    "channels, notify_user_ids, channel_escalation_enabled, "
                    "escalation_timeout_minutes, escalation_channel_order, "
                    "is_enabled, is_default, created_at, updated_at) "
                    "VALUES (:name, NULL, :level, NULL, NULL, "
                    ":channels, :user_ids, 0, 5, NULL, 1, 1, "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {
                    "name": name,
                    "level": level,
                    "channels": json.dumps(channels),
                    "user_ids": json.dumps([]),
                },
            )


def downgrade() -> None:
    op.drop_index("ix_np_site_level", table_name="notification_policies")
    op.drop_table("notification_policies")
