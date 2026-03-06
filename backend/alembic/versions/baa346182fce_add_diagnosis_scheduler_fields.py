"""add diagnosis scheduler fields

Revision ID: baa346182fce
Revises: c6818ff61a90
Create Date: 2026-03-06 12:01:47.596529

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'baa346182fce'
down_revision: Union[str, None] = 'c6818ff61a90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 添加 Story 24.2 需要的字段（SQLite 不支持添加外键，只添加列和索引）
    op.add_column('diagnosis_results', sa.Column('device_id', sa.Integer(), nullable=True))
    op.add_column('diagnosis_results', sa.Column('diagnosis_level', sa.String(length=10), nullable=True))
    op.add_column('diagnosis_results', sa.Column('matched', sa.Boolean(), nullable=True, server_default='0'))
    op.add_column('diagnosis_results', sa.Column('conclusion', sa.Text(), nullable=True))
    op.add_column('diagnosis_results', sa.Column('confidence', sa.Float(), nullable=True))
    op.add_column('diagnosis_results', sa.Column('suggested_actions', sa.JSON(), nullable=True))
    op.add_column('diagnosis_results', sa.Column('evidence', sa.JSON(), nullable=True))
    op.add_column('diagnosis_results', sa.Column('inference_time_ms', sa.Integer(), nullable=True))
    op.add_column('diagnosis_results', sa.Column('error_message', sa.Text(), nullable=True))

    # 添加索引
    op.create_index('ix_diagnosis_results_device_id', 'diagnosis_results', ['device_id'])
    op.create_index('ix_diagnosis_results_diagnosis_level', 'diagnosis_results', ['diagnosis_level'])


def downgrade() -> None:
    # 删除索引
    op.drop_index('ix_diagnosis_results_diagnosis_level', table_name='diagnosis_results')
    op.drop_index('ix_diagnosis_results_device_id', table_name='diagnosis_results')

    # 删除列
    op.drop_column('diagnosis_results', 'error_message')
    op.drop_column('diagnosis_results', 'inference_time_ms')
    op.drop_column('diagnosis_results', 'evidence')
    op.drop_column('diagnosis_results', 'suggested_actions')
    op.drop_column('diagnosis_results', 'confidence')
    op.drop_column('diagnosis_results', 'conclusion')
    op.drop_column('diagnosis_results', 'matched')
    op.drop_column('diagnosis_results', 'diagnosis_level')
    op.drop_column('diagnosis_results', 'device_id')
