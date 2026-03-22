"""story_36_3_maintenance_advice

Revision ID: 20260322_0200
Revises: 20260322_0100
Create Date: 2026-03-22

Story 36.3: 新增 maintenance_advices 表
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "20260322_0200"
down_revision: Union[str, None] = "20260322_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "maintenance_advices" not in existing_tables:
        op.create_table(
            "maintenance_advices",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("device_id", sa.Integer(), nullable=False, comment="设备ID"),
            sa.Column("device_name", sa.String(100), comment="设备名称"),
            sa.Column("device_type", sa.String(50), comment="设备类型"),
            sa.Column("health_score", sa.Float(), comment="触发时健康度评分"),
            sa.Column("urgency", sa.String(20), comment="紧急度: high/medium"),
            sa.Column("reason", sa.Text(), comment="劣化原因描述"),
            sa.Column("suggested_action", sa.Text(), comment="建议维护措施"),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending",
                       comment="状态: pending/converted/rejected/auto_closed"),
            sa.Column("feedback", sa.Text(), comment="误报反馈原因"),
            sa.Column("work_order_id", sa.Integer(), nullable=True, comment="关联工单ID"),
            sa.Column("created_at", sa.DateTime(), comment="创建时间"),
            sa.Column("updated_at", sa.DateTime(), comment="更新时间"),
            sa.Column("confirmed_at", sa.DateTime(), comment="确认时间"),
            sa.Column("confirmed_by", sa.Integer(), nullable=True, comment="确认人"),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
            sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"]),
            sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"]),
        )
        op.create_index(
            "ix_maintenance_advices_device_status",
            "maintenance_advices",
            ["device_id", "status"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if "maintenance_advices" in existing_tables:
        op.drop_index("ix_maintenance_advices_device_status", table_name="maintenance_advices")
        op.drop_table("maintenance_advices")
