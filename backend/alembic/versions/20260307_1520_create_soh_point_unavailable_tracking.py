"""create soh_point_unavailable_tracking table

Revision ID: 20260307_1520
Revises: 20260307_1510
Create Date: 2026-03-07 15:20:00

Story 25.3: UPS电池SOH预测 - 点位长期不可用追踪
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260307_1520'
down_revision: Union[str, None] = '20260307_1510'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    创建 soh_point_unavailable_tracking 表，用于追踪点位连续不可用天数
    """
    op.create_table(
        'soh_point_unavailable_tracking',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=False, comment='设备ID'),
        sa.Column('consecutive_days', sa.Integer(), nullable=False, default=0, comment='连续不可用天数'),
        sa.Column('last_unavailable_date', sa.Date(), nullable=False, comment='最后一次不可用日期'),
        sa.Column('alarm_triggered', sa.Boolean(), nullable=False, default=False, comment='是否已触发告警'),
        sa.Column('created_at', sa.DateTime(), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, comment='更新时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='CASCADE')
    )
    op.create_index('idx_soh_unavailable_device_id', 'soh_point_unavailable_tracking', ['device_id'], unique=True)


def downgrade() -> None:
    """
    删除 soh_point_unavailable_tracking 表
    """
    op.drop_index('idx_soh_unavailable_device_id', table_name='soh_point_unavailable_tracking')
    op.drop_table('soh_point_unavailable_tracking')
