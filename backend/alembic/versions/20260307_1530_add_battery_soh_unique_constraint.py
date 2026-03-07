"""add unique constraint for battery_soh_records idempotency

Revision ID: 20260307_1530
Revises: 20260307_1520
Create Date: 2026-03-07 15:30:00

Story 25.3: UPS电池SOH预测 - 幂等性约束
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260307_1530'
down_revision: Union[str, None] = '20260307_1520'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    为 battery_soh_records 添加唯一约束：同一设备同一天（UTC 日期）只保留一条记录
    """
    # SQLite 不支持直接添加唯一约束，需要重建表
    # 但为了简化，使用唯一索引实现相同效果
    op.create_index(
        'idx_battery_soh_device_date_unique',
        'battery_soh_records',
        [sa.text('device_id'), sa.text('DATE(calculated_at)')],
        unique=True
    )


def downgrade() -> None:
    """
    删除唯一索引
    """
    op.drop_index('idx_battery_soh_device_date_unique', table_name='battery_soh_records')
