"""create counterfactual_analyses table

Revision ID: 20260308_1600
Revises: 8574ebeb7faa
Create Date: 2026-03-08 16:00:00.000000

Story 26.1: 反事实分析
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260308_1600'
down_revision = '8574ebeb7faa'
branch_labels = None
depends_on = None


def upgrade():
    # 幂等性检查
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'counterfactual_analyses' in inspector.get_table_names():
        return

    # 创建 counterfactual_analyses 表
    op.create_table(
        'counterfactual_analyses',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('session_id', sa.Integer(), nullable=False, comment='诊断会话ID'),
        sa.Column('original_root_cause', sa.String(500), nullable=True, comment='原始根因'),
        sa.Column('original_confidence', sa.Float(), nullable=True, comment='原始置信度'),
        sa.Column('top_evidences', sa.JSON(), nullable=False, comment='Top证据列表'),
        sa.Column('analysis_results', sa.JSON(), nullable=False, comment='分析结果'),
        sa.Column('analysis_time_ms', sa.Integer(), nullable=False, server_default='0', comment='分析耗时(毫秒)'),
        sa.Column('fault_tree_version', sa.String(50), nullable=True, comment='故障树版本号'),
        sa.Column('config_version', sa.String(50), nullable=True, comment='配置版本号'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True, comment='软删除时间'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), comment='更新时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['diagnosis_sessions.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('session_id', name='uq_counterfactual_session_id')
    )

    # 创建索引
    op.create_index('idx_counterfactual_session', 'counterfactual_analyses', ['session_id'])
    op.create_index('idx_counterfactual_created', 'counterfactual_analyses', ['created_at'])
    op.create_index('idx_counterfactual_confidence', 'counterfactual_analyses', ['original_confidence'])
    op.create_index('idx_counterfactual_time', 'counterfactual_analyses', ['analysis_time_ms'])
    op.create_index('idx_counterfactual_deleted', 'counterfactual_analyses', ['deleted_at'])


def downgrade():
    # 删除索引
    op.drop_index('idx_counterfactual_deleted', table_name='counterfactual_analyses')
    op.drop_index('idx_counterfactual_time', table_name='counterfactual_analyses')
    op.drop_index('idx_counterfactual_confidence', table_name='counterfactual_analyses')
    op.drop_index('idx_counterfactual_created', table_name='counterfactual_analyses')
    op.drop_index('idx_counterfactual_session', table_name='counterfactual_analyses')

    # 删除表
    op.drop_table('counterfactual_analyses')
