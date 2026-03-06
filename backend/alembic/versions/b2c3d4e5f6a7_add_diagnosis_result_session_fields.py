"""add_diagnosis_result_session_fields

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-06 16:01:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 仅新增 4 个字段（confidence/evidence 等字段已在 Story 24.2 迁移中创建）
    op.add_column('diagnosis_results', sa.Column('session_id', sa.Integer(), nullable=True, comment='诊断会话ID'))
    op.add_column('diagnosis_results', sa.Column('root_cause', sa.String(500), nullable=True, comment='根因描述'))
    op.add_column('diagnosis_results', sa.Column('reasoning_path', sa.JSON(), nullable=True, comment='推理路径'))
    op.add_column('diagnosis_results', sa.Column('fault_tree_version', sa.String(50), nullable=True, comment='故障树版本号'))

    # 添加外键约束（SQLite 不支持 ALTER TABLE ADD FOREIGN KEY，使用 batch 模式）
    with op.batch_alter_table('diagnosis_results') as batch_op:
        batch_op.create_foreign_key(
            'fk_diagnosis_results_session_id',
            'diagnosis_sessions',
            ['session_id'],
            ['id'],
        )


def downgrade() -> None:
    with op.batch_alter_table('diagnosis_results') as batch_op:
        batch_op.drop_constraint('fk_diagnosis_results_session_id', type_='foreignkey')

    op.drop_column('diagnosis_results', 'fault_tree_version')
    op.drop_column('diagnosis_results', 'reasoning_path')
    op.drop_column('diagnosis_results', 'root_cause')
    op.drop_column('diagnosis_results', 'session_id')
