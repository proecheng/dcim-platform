"""story_31_1_precool_schedules

Revision ID: 20260311_0200
Revises: 20260311_0100
Create Date: 2026-03-11

Story 31.1: 贪心优化预冷调度算法 — 创建 precool_schedules 表
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '20260311_0200'
down_revision: Union[str, None] = '20260311_0100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 检查表是否已存在
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "precool_schedules" not in existing_tables:
        op.create_table(
            "precool_schedules",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "cooling_zone_id",
                sa.Integer(),
                sa.ForeignKey("cooling_zones.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("schedule_date", sa.Date(), nullable=False),
            sa.Column("precool_start_time", sa.Time(), nullable=False,
                      comment="预冷开始时间（谷时）"),
            sa.Column("precool_end_time", sa.Time(), nullable=False,
                      comment="预冷结束时间"),
            sa.Column("target_temp", sa.Float(), nullable=False,
                      comment="预冷目标温度 °C"),
            sa.Column("peak_start_time", sa.Time(), nullable=False,
                      comment="峰时削减开始时间"),
            sa.Column("peak_end_time", sa.Time(), nullable=False,
                      comment="峰时削减结束时间"),
            sa.Column("planned_savings_kwh", sa.Float(), default=0.0,
                      comment="计划节省电量 kWh"),
            sa.Column("actual_savings_kwh", sa.Float(), nullable=True,
                      comment="实际节省电量 kWh"),
            sa.Column("status", sa.String(20), default="pending",
                      comment="状态: pending/executing/completed/aborted"),
            sa.Column("abort_reason", sa.String(500), nullable=True,
                      comment="中止原因"),
            sa.Column("temperature_trajectory", sa.JSON(), nullable=True,
                      comment="温度轨迹 JSON"),
            sa.Column("is_validated", sa.Boolean(), default=False,
                      comment="是否通过约束验证"),
            sa.Column("validated_at", sa.DateTime(), nullable=True,
                      comment="验证时间"),
            sa.Column("created_at", sa.DateTime(),
                      server_default=sa.text("CURRENT_TIMESTAMP"),
                      comment="创建时间"),
            sa.Column("updated_at", sa.DateTime(),
                      server_default=sa.text("CURRENT_TIMESTAMP"),
                      comment="更新时间"),
            # 联合唯一约束（在 create_table 内定义，兼容 SQLite）
            sa.UniqueConstraint("cooling_zone_id", "schedule_date",
                                name="uq_zone_schedule_date"),
        )

        # 索引
        op.create_index(
            "ix_precool_schedules_zone_id",
            "precool_schedules",
            ["cooling_zone_id"],
        )
        op.create_index(
            "ix_precool_schedules_status",
            "precool_schedules",
            ["status"],
        )


def downgrade() -> None:
    op.drop_table("precool_schedules")
