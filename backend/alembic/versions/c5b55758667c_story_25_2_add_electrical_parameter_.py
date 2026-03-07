"""Story 25.2: Add electrical parameter fields to fault_tree_nodes

Revision ID: c5b55758667c
Revises: 3110920d5085
Create Date: 2026-03-07 13:44:02.265126

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = 'c5b55758667c'
down_revision: Union[str, None] = '3110920d5085'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """添加电气参数字段到 fault_tree_nodes 表"""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    # 如果 fault_tree_nodes 表不存在，先创建它（兼容性处理）
    if 'fault_tree_nodes' not in tables:
        # 创建 fault_trees 表
        op.create_table(
            'fault_trees',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(200), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
            sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
            sa.Column('created_by', sa.Integer(), nullable=True),
            sa.Column('updated_by', sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_fault_trees_id', 'fault_trees', ['id'])

        # 创建 fault_tree_nodes 表
        op.create_table(
            'fault_tree_nodes',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('tree_id', sa.Integer(), nullable=False),
            sa.Column('node_type', sa.String(20), nullable=False),
            sa.Column('gate_type', sa.String(10), nullable=True),
            sa.Column('name', sa.String(200), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('prior_probability', sa.Float(), nullable=False, server_default='0.5'),
            sa.Column('evidence_point_id', sa.Integer(), nullable=True),
            sa.Column('config', sa.Text(), nullable=True),
            sa.Column('threshold_type', sa.String(10), nullable=True),
            sa.Column('threshold_value', sa.Float(), nullable=True),
            sa.Column('sigmoid_k', sa.Float(), nullable=True, server_default=sa.text('2.0')),
            sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['tree_id'], ['fault_trees.id'], ondelete='CASCADE'),
            sa.CheckConstraint('prior_probability >= 0.0 AND prior_probability <= 1.0', name='check_prior_probability')
        )
        op.create_index('ix_fault_tree_nodes_id', 'fault_tree_nodes', ['id'])
        op.create_index('ix_fault_tree_nodes_tree_id', 'fault_tree_nodes', ['tree_id'])
        op.create_index('ix_fault_tree_nodes_node_type', 'fault_tree_nodes', ['node_type'])

        # 创建 fault_tree_edges 表
        op.create_table(
            'fault_tree_edges',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('tree_id', sa.Integer(), nullable=False),
            sa.Column('parent_node_id', sa.Integer(), nullable=False),
            sa.Column('child_node_id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['tree_id'], ['fault_trees.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['parent_node_id'], ['fault_tree_nodes.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['child_node_id'], ['fault_tree_nodes.id'], ondelete='CASCADE'),
            sa.CheckConstraint('parent_node_id != child_node_id', name='check_no_self_loop')
        )
        op.create_index('ix_fault_tree_edges_id', 'fault_tree_edges', ['id'])
        op.create_index('ix_fault_tree_edges_tree_id', 'fault_tree_edges', ['tree_id'])

        # 创建 fault_tree_device_mapping 表
        op.create_table(
            'fault_tree_device_mapping',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('tree_id', sa.Integer(), nullable=False),
            sa.Column('device_type', sa.String(50), nullable=False),
            sa.Column('alarm_type', sa.String(100), nullable=True),
            sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['tree_id'], ['fault_trees.id'], ondelete='CASCADE')
        )
        op.create_index('ix_fault_tree_device_mapping_device_type', 'fault_tree_device_mapping', ['device_type'])

        # 创建 fault_tree_versions 表
        op.create_table(
            'fault_tree_versions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('tree_id', sa.Integer(), nullable=False),
            sa.Column('version_number', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
            sa.Column('snapshot', sa.Text(), nullable=False),
            sa.Column('hmac_signature', sa.String(64), nullable=True),
            sa.Column('created_by', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
            sa.Column('reviewed_by', sa.Integer(), nullable=True),
            sa.Column('reviewed_at', sa.TIMESTAMP(), nullable=True),
            sa.Column('activated_at', sa.TIMESTAMP(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['tree_id'], ['fault_trees.id'], ondelete='CASCADE'),
            sa.CheckConstraint("status IN ('draft', 'reviewed', 'active', 'archived')", name='check_status'),
            sa.CheckConstraint('version_number > 0', name='check_version_number_positive')
        )
        op.create_index('ix_fault_tree_versions_tree_id', 'fault_tree_versions', ['tree_id'])
        op.create_index('ix_fault_tree_versions_status', 'fault_tree_versions', ['status'])
    else:
        # 表已存在，只添加新字段
        columns = [col['name'] for col in inspector.get_columns('fault_tree_nodes')]

        if 'threshold_type' not in columns:
            op.add_column('fault_tree_nodes',
                sa.Column('threshold_type', sa.String(10), nullable=True))

        if 'threshold_value' not in columns:
            op.add_column('fault_tree_nodes',
                sa.Column('threshold_value', sa.Float(), nullable=True))

        if 'sigmoid_k' not in columns:
            op.add_column('fault_tree_nodes',
                sa.Column('sigmoid_k', sa.Float(), nullable=True, server_default=sa.text('2.0')))


def downgrade() -> None:
    """
    安全回滚策略：
    1. 检查表是否存在
    2. 备份数据（可选，生产环境建议手动备份）
    3. 删除列

    注意：downgrade 会丢失这些列的数据，生产环境执行前务必备份！
    """
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if 'fault_tree_nodes' not in tables:
        # 表不存在，无需回滚
        return

    columns = [col['name'] for col in inspector.get_columns('fault_tree_nodes')]

    # 按相反顺序删除列
    if 'sigmoid_k' in columns:
        op.drop_column('fault_tree_nodes', 'sigmoid_k')

    if 'threshold_value' in columns:
        op.drop_column('fault_tree_nodes', 'threshold_value')

    if 'threshold_type' in columns:
        op.drop_column('fault_tree_nodes', 'threshold_type')
