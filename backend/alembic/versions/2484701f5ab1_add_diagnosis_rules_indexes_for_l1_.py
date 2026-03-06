"""add diagnosis rules indexes for l1 engine

Revision ID: 2484701f5ab1
Revises: b74705769037
Create Date: 2026-03-06 10:39:27.229367

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2484701f5ab1'
down_revision: Union[str, None] = 'b74705769037'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 添加索引加速 L1 引擎查询
    op.create_index('ix_diagnosis_rules_category_enabled', 'diagnosis_rules', ['category', 'is_enabled'])
    op.create_index('ix_diagnosis_rules_priority_enabled', 'diagnosis_rules', ['priority', 'is_enabled'])


def downgrade() -> None:
    op.drop_index('ix_diagnosis_rules_priority_enabled', table_name='diagnosis_rules')
    op.drop_index('ix_diagnosis_rules_category_enabled', table_name='diagnosis_rules')
