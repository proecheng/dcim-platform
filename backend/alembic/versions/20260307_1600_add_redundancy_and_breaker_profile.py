"""add redundancy and breaker profile support

Revision ID: 20260307_1600
Revises: 20260307_1530
Create Date: 2026-03-07 16:00:00

Story 25.4: N+X冗余拓扑与断路器保护逻辑
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '20260307_1600'
down_revision: Union[str, None] = '20260307_1530'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    为 power_devices 表添加冗余配置字段，创建 breaker_profiles 表
    """
    conn = op.get_bind()

    # 验证 power_devices 表是否存在 circuit_id 字段（Epic 8 前置依赖）
    result = conn.execute(text(
        "SELECT name FROM pragma_table_info('power_devices') WHERE name='circuit_id'"
    ))
    if not result.scalar():
        raise RuntimeError(
            "前置依赖未满足: power_devices 表缺少 circuit_id 字段。"
            "请确保 Epic 8 (机房物理拓扑) 已完成实施。"
        )

    # 检查 redundancy_type 字段是否已存在
    result = conn.execute(text(
        "SELECT name FROM pragma_table_info('power_devices') WHERE name='redundancy_type'"
    ))
    if not result.scalar():
        # 为 power_devices 表添加冗余配置字段
        op.add_column('power_devices', sa.Column('redundancy_type', sa.String(10), nullable=True, comment='冗余类型: N+1/2N/NULL'))
        op.add_column('power_devices', sa.Column('redundancy_group_id', sa.String(50), nullable=True, comment='冗余组标识'))
        print("[OK] power_devices 表已添加冗余配置字段")
    else:
        print("[SKIP] power_devices 表的冗余配置字段已存在")

    # 检查 breaker_profiles 表是否已存在
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='breaker_profiles'"
    ))
    if not result.scalar():
        # 创建 breaker_profiles 表
        op.create_table(
            'breaker_profiles',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('breaker_device_id', sa.Integer(), nullable=False, comment='断路器设备ID'),
            sa.Column('trip_curve_type', sa.String(1), nullable=False, comment='脱扣曲线类型: B/C/D'),
            sa.Column('rated_current', sa.Float(), nullable=False, comment='额定电流 A'),
            sa.Column('created_at', sa.DateTime(), nullable=False, comment='创建时间'),
            sa.Column('updated_at', sa.DateTime(), nullable=False, comment='更新时间'),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['breaker_device_id'], ['power_devices.id'], ondelete='CASCADE'),
            sa.CheckConstraint("trip_curve_type IN ('B', 'C', 'D')", name='ck_breaker_profiles_trip_curve_type'),
            sa.CheckConstraint('rated_current > 0', name='ck_breaker_profiles_rated_current')
        )

        # 创建唯一索引
        op.create_index('idx_breaker_profiles_device_id', 'breaker_profiles', ['breaker_device_id'], unique=True)
        print("[OK] breaker_profiles 表已创建")
    else:
        print("[SKIP] breaker_profiles 表已存在")


def downgrade() -> None:
    """
    删除 breaker_profiles 表，删除 power_devices 的冗余配置字段
    """
    # 删除 breaker_profiles 表
    op.drop_index('idx_breaker_profiles_device_id', table_name='breaker_profiles')
    op.drop_table('breaker_profiles')

    # 删除 power_devices 的冗余配置字段
    op.drop_column('power_devices', 'redundancy_group_id')
    op.drop_column('power_devices', 'redundancy_type')

    print("[OK] breaker_profiles 表已删除")
    print("[OK] power_devices 表的冗余配置字段已删除")
