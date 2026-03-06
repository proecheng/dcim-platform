"""add_fault_tree_tables

Revision ID: 4cbe2c1df9bb
Revises: baa346182fce
Create Date: 2026-03-06 12:53:55.108713

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4cbe2c1df9bb'
down_revision: Union[str, None] = 'baa346182fce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 故障树元数据表
    op.create_table(
        'fault_trees',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_fault_trees_id'), 'fault_trees', ['id'], unique=False)
    op.create_index(op.f('ix_fault_trees_status'), 'fault_trees', ['status'], unique=False)

    # 故障树节点表
    op.create_table(
        'fault_tree_nodes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tree_id', sa.Integer(), nullable=False),
        sa.Column('node_type', sa.String(length=20), nullable=False),
        sa.Column('gate_type', sa.String(length=10), nullable=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('prior_probability', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('evidence_point_id', sa.Integer(), nullable=True),
        sa.Column('config', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint('prior_probability >= 0.0 AND prior_probability <= 1.0', name='check_prior_probability'),
        sa.ForeignKeyConstraint(['evidence_point_id'], ['points.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['tree_id'], ['fault_trees.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fault_tree_nodes_id'), 'fault_tree_nodes', ['id'], unique=False)
    op.create_index(op.f('ix_fault_tree_nodes_tree_id'), 'fault_tree_nodes', ['tree_id'], unique=False)
    op.create_index(op.f('ix_fault_tree_nodes_node_type'), 'fault_tree_nodes', ['node_type'], unique=False)

    # 故障树边表
    op.create_table(
        'fault_tree_edges',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tree_id', sa.Integer(), nullable=False),
        sa.Column('parent_node_id', sa.Integer(), nullable=False),
        sa.Column('child_node_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint('parent_node_id != child_node_id', name='check_no_self_loop'),
        sa.ForeignKeyConstraint(['child_node_id'], ['fault_tree_nodes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_node_id'], ['fault_tree_nodes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tree_id'], ['fault_trees.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tree_id', 'parent_node_id', 'child_node_id', name='uq_tree_edge')
    )
    op.create_index(op.f('ix_fault_tree_edges_id'), 'fault_tree_edges', ['id'], unique=False)
    op.create_index(op.f('ix_fault_tree_edges_tree_id'), 'fault_tree_edges', ['tree_id'], unique=False)
    op.create_index(op.f('ix_fault_tree_edges_parent_node_id'), 'fault_tree_edges', ['parent_node_id'], unique=False)
    op.create_index(op.f('ix_fault_tree_edges_child_node_id'), 'fault_tree_edges', ['child_node_id'], unique=False)

    # 故障树设备映射表
    op.create_table(
        'fault_tree_device_mapping',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tree_id', sa.Integer(), nullable=False),
        sa.Column('device_type', sa.String(length=50), nullable=False),
        sa.Column('alarm_type', sa.String(length=100), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['tree_id'], ['fault_trees.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tree_id', 'device_type', 'alarm_type', name='uq_tree_device_alarm')
    )
    op.create_index(op.f('ix_fault_tree_device_mapping_id'), 'fault_tree_device_mapping', ['id'], unique=False)
    op.create_index(op.f('ix_fault_tree_device_mapping_device_type'), 'fault_tree_device_mapping', ['device_type', 'alarm_type'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_fault_tree_device_mapping_device_type'), table_name='fault_tree_device_mapping')
    op.drop_index(op.f('ix_fault_tree_device_mapping_id'), table_name='fault_tree_device_mapping')
    op.drop_table('fault_tree_device_mapping')

    op.drop_index(op.f('ix_fault_tree_edges_child_node_id'), table_name='fault_tree_edges')
    op.drop_index(op.f('ix_fault_tree_edges_parent_node_id'), table_name='fault_tree_edges')
    op.drop_index(op.f('ix_fault_tree_edges_tree_id'), table_name='fault_tree_edges')
    op.drop_index(op.f('ix_fault_tree_edges_id'), table_name='fault_tree_edges')
    op.drop_table('fault_tree_edges')

    op.drop_index(op.f('ix_fault_tree_nodes_node_type'), table_name='fault_tree_nodes')
    op.drop_index(op.f('ix_fault_tree_nodes_tree_id'), table_name='fault_tree_nodes')
    op.drop_index(op.f('ix_fault_tree_nodes_id'), table_name='fault_tree_nodes')
    op.drop_table('fault_tree_nodes')

    op.drop_index(op.f('ix_fault_trees_status'), table_name='fault_trees')
    op.drop_index(op.f('ix_fault_trees_id'), table_name='fault_trees')
    op.drop_table('fault_trees')
