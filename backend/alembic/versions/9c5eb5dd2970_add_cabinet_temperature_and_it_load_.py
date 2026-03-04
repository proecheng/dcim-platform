"""add_cabinet_temperature_and_it_load_monitoring

Revision ID: 9c5eb5dd2970
Revises: d27a98f5eea8
Create Date: 2026-03-03 01:16:29.663037

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c5eb5dd2970'
down_revision: Union[str, None] = 'd27a98f5eea8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建 cabinet_temperature_sensors 表
    op.create_table(
        'cabinet_temperature_sensors',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('cabinet_id', sa.Integer(), nullable=False, comment='机柜ID'),
        sa.Column('point_id', sa.Integer(), nullable=True, comment='温度点位ID'),
        sa.Column('sensor_location', sa.String(length=20), nullable=False, comment='传感器位置: inlet/outlet/ambient'),
        sa.Column('temp_warning_threshold', sa.Float(), nullable=True, comment='温度告警阈值(℃)'),
        sa.Column('temp_critical_threshold', sa.Float(), nullable=True, comment='温度严重告警阈值(℃)'),
        sa.Column('description', sa.Text(), nullable=True, comment='描述'),
        sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
        sa.ForeignKeyConstraint(['cabinet_id'], ['cabinets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['point_id'], ['points.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cabinet_id', 'sensor_location', name='uq_cabinet_sensor_location')
    )
    
    # 创建 cabinet_it_loads 表
    op.create_table(
        'cabinet_it_loads',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('cabinet_id', sa.Integer(), nullable=False, comment='机柜ID'),
        sa.Column('power_point_id', sa.Integer(), nullable=True, comment='功率点位ID'),
        sa.Column('rated_power_kw', sa.Float(), nullable=True, comment='额定功率(kW)'),
        sa.Column('design_load_kw', sa.Float(), nullable=True, comment='设计负载(kW)'),
        sa.Column('description', sa.Text(), nullable=True, comment='描述'),
        sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
        sa.ForeignKeyConstraint(['cabinet_id'], ['cabinets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['power_point_id'], ['points.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cabinet_id', name='uq_cabinet_it_load')
    )
    
    # 为 cooling_zone_units 表添加 is_primary 字段（如果不存在）
    # 注意：SQLite 不支持 ADD COLUMN IF NOT EXISTS，需要先检查
    try:
        op.add_column('cooling_zone_units', sa.Column('is_primary', sa.Integer(), nullable=True, comment='是否主空调: 1=主, 0=备'))
        op.add_column('cooling_zone_units', sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'))
        op.add_column('cooling_zone_units', sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'))
    except:
        pass  # 字段已存在


def downgrade() -> None:
    # 删除表
    op.drop_table('cabinet_it_loads')
    op.drop_table('cabinet_temperature_sensors')
    
    # 删除 cooling_zone_units 的新字段
    try:
        op.drop_column('cooling_zone_units', 'updated_at')
        op.drop_column('cooling_zone_units', 'created_at')
        op.drop_column('cooling_zone_units', 'is_primary')
    except:
        pass
