"""Story 25.5: Add sensor_metadata table for accuracy weighting

Revision ID: d20698c35b80
Revises: 20260307_1600
Create Date: 2026-03-07 21:14:35.468426

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = 'd20698c35b80'
down_revision: Union[str, None] = '20260307_1600'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 sensor_metadata 表"""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    # 幂等性检查：如果表已存在则跳过
    if 'sensor_metadata' in tables:
        print("sensor_metadata table already exists, skipping creation")
        return

    # 创建 sensor_metadata 表
    op.create_table(
        'sensor_metadata',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('point_id', sa.Integer(), nullable=False),
        sa.Column('ct_pt_ratio', sa.Float(), nullable=True),
        sa.Column('accuracy_class', sa.Float(), nullable=False),
        sa.Column('calibration_date', sa.Date(), nullable=True),
        sa.Column('calibration_interval_days', sa.Integer(), nullable=False, server_default='365'),
        sa.Column('calibration_result', sa.String(500), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['point_id'], ['points.id'], ondelete='CASCADE'),
        sa.CheckConstraint('accuracy_class IN (0.2, 0.5, 1.0)', name='check_accuracy_class'),
        sa.CheckConstraint('calibration_interval_days > 0', name='check_calibration_interval')
    )

    # 创建唯一索引
    op.create_index('idx_sensor_metadata_point_id', 'sensor_metadata', ['point_id'], unique=True)


def downgrade() -> None:
    """删除 sensor_metadata 表"""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    # 幂等性检查：如果表不存在则跳过
    if 'sensor_metadata' not in tables:
        print("sensor_metadata table does not exist, skipping deletion")
        return

    # 删除索引和表
    op.drop_index('idx_sensor_metadata_point_id', table_name='sensor_metadata')
    op.drop_table('sensor_metadata')
