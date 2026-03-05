"""add_is_demo_column_to_core_tables

Revision ID: b74705769037
Revises: c25eed11c006
Create Date: 2026-03-06 01:27:22.965968

为核心数据表添加 is_demo 列，用于标记 demo 数据和用户自定义数据
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b74705769037'
down_revision: Union[str, None] = 'c25eed11c006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(table_name: str, column_name: str) -> bool:
    """检查列是否存在"""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """添加 is_demo 列到核心表"""

    # 需要添加 is_demo 列的表列表
    tables = [
        # 设备相关
        'devices',
        'points',

        # 空间相关
        'sites',
        'floors',
        'rooms',
        'rows',

        # 配电相关
        'transformers',
        'meter_points',
        'distribution_panels',
        'distribution_circuits',
        'power_devices',

        # 制冷相关
        'cooling_groups',
        'cooling_units',
        'cold_aisles',

        # 告警相关
        'alarm_thresholds',

        # 其他
        'floor_maps',
        'electricity_pricing',  # 注意：单数形式
    ]

    # 为每个表添加 is_demo 列（如果不存在）
    for table_name in tables:
        if not column_exists(table_name, 'is_demo'):
            # 使用 batch_alter_table 确保 SQLite 兼容性
            with op.batch_alter_table(table_name, schema=None) as batch_op:
                batch_op.add_column(
                    sa.Column('is_demo', sa.Boolean(), nullable=False, server_default='0', comment='是否为演示数据')
                )

    # 将现有数据标记为 demo 数据（假设当前全部是 demo 数据）
    # 注意：这里使用 server_default='0' (False)，因为我们希望新创建的数据默认不是 demo
    # 但现有数据需要手动标记为 True
    connection = op.get_bind()
    for table_name in tables:
        if column_exists(table_name, 'is_demo'):
            connection.execute(
                sa.text(f"UPDATE {table_name} SET is_demo = 1")
            )


def downgrade() -> None:
    """移除 is_demo 列"""

    tables = [
        'devices',
        'points',
        'sites',
        'floors',
        'rooms',
        'rows',
        'transformers',
        'meter_points',
        'distribution_panels',
        'distribution_circuits',
        'power_devices',
        'cooling_groups',
        'cooling_units',
        'cold_aisles',
        'alarm_thresholds',
        'floor_maps',
        'electricity_pricing',
    ]

    for table_name in tables:
        if column_exists(table_name, 'is_demo'):
            with op.batch_alter_table(table_name, schema=None) as batch_op:
                batch_op.drop_column('is_demo')
