"""add data_source field to models for Story 28.2

Revision ID: c25eed11c006
Revises: b28_1_source_tracking
Create Date: 2026-03-05 23:07:01.831809

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c25eed11c006'
down_revision: Union[str, None] = 'b28_1_source_tracking'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 为多个表添加 data_source 字段（长度 50，带索引）
    tables = ['sites', 'floors', 'rooms', 'pricing_schemes', 'devices', 'points']

    for table in tables:
        # 添加字段
        op.add_column(table, sa.Column('data_source', sa.String(50), nullable=True))
        # 创建索引
        op.create_index(f'ix_{table}_data_source', table, ['data_source'])


def downgrade() -> None:
    # 删除索引和字段
    tables = ['sites', 'floors', 'rooms', 'pricing_schemes', 'devices', 'points']

    for table in tables:
        op.drop_index(f'ix_{table}_data_source', table_name=table)
        op.drop_column(table, 'data_source')
