"""add fault_tree_version_id to diagnosis_results

Revision ID: ad615c658978
Revises: 1dca16dbc64e
Create Date: 2026-03-09 11:07:29.882417

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ad615c658978'
down_revision: Union[str, None] = '1dca16dbc64e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 添加 fault_tree_version_id 字段到 diagnosis_results 表
    op.add_column('diagnosis_results', sa.Column('fault_tree_version_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_diagnosis_results_fault_tree_version_id',
        'diagnosis_results',
        'fault_tree_versions',
        ['fault_tree_version_id'],
        ['id']
    )
    op.create_index('idx_diagnosis_results_fault_tree_version', 'diagnosis_results', ['fault_tree_version_id'])


def downgrade() -> None:
    op.drop_index('idx_diagnosis_results_fault_tree_version', table_name='diagnosis_results')
    op.drop_constraint('fk_diagnosis_results_fault_tree_version_id', 'diagnosis_results', type_='foreignkey')
    op.drop_column('diagnosis_results', 'fault_tree_version_id')
