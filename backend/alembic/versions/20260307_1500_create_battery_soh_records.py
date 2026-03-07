"""create battery_soh_records table

Revision ID: 20260307_1500
Revises: b74705769037
Create Date: 2026-03-07 15:00:00

Story 25.3: UPS电池SOH预测
创建 battery_soh_records 表用于存储 UPS 电池健康度计算结果
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = '20260307_1500'
down_revision: Union[str, None] = ('b74705769037', 'c5b55758667c')  # Merge two heads
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    创建 battery_soh_records 表

    数据保留策略：建议保留 1 年数据，超过 1 年的记录可通过定期任务清理
    """
    # 检查表是否已存在
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if 'battery_soh_records' in tables:
        print("表 battery_soh_records 已存在，跳过创建")
        return

    # 创建表
    op.create_table(
        'battery_soh_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=False),
        sa.Column('soh_percent', sa.Float(), nullable=False),
        sa.Column('resistance_mohm', sa.Float(), nullable=True),
        sa.Column('cycle_count', sa.Integer(), nullable=True),
        sa.Column('weights_version', sa.String(50), nullable=True),
        sa.Column('calculated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='CASCADE')
    )

    # 创建索引
    op.create_index('idx_battery_soh_device_id', 'battery_soh_records', ['device_id'])
    op.create_index('idx_battery_soh_calculated_at', 'battery_soh_records', ['calculated_at'])
    # 复合索引用于查询最新记录（不使用 DESC，在查询时指定排序）
    op.create_index('idx_battery_soh_device_time', 'battery_soh_records', ['device_id', 'calculated_at'])

    # 创建唯一约束（每天每设备只有一条记录）
    # 注意: SQLite 不支持函数索引，需要在应用层保证幂等性
    # PostgreSQL 可使用: CREATE UNIQUE INDEX ON battery_soh_records (device_id, DATE(calculated_at))
    # 这里使用应用层幂等性检查（calculate_soh 函数中）

    print("表 battery_soh_records 创建成功")


def downgrade() -> None:
    """
    安全回滚策略：
    1. 检查表是否存在
    2. 删除索引
    3. 删除表

    注意：downgrade 会丢失所有 SOH 历史数据，生产环境执行前务必备份！
    """
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if 'battery_soh_records' not in tables:
        print("表 battery_soh_records 不存在，跳过删除")
        return

    # 删除索引
    op.drop_index('idx_battery_soh_device_time', 'battery_soh_records')
    op.drop_index('idx_battery_soh_calculated_at', 'battery_soh_records')
    op.drop_index('idx_battery_soh_device_id', 'battery_soh_records')

    # 删除表
    op.drop_table('battery_soh_records')

    print("表 battery_soh_records 已删除")
