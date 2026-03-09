"""add ab testing tables

Revision ID: 1dca16dbc64e
Revises: e5fbbe704523
Create Date: 2026-03-09 11:05:46.086601

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '1dca16dbc64e'
down_revision: Union[str, None] = 'e5fbbe704523'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建 ab_test_configs 表
    op.create_table(
        'ab_test_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('fault_tree_id', sa.Integer(), nullable=False),
        sa.Column('version_a_id', sa.Integer(), nullable=False),
        sa.Column('version_b_id', sa.Integer(), nullable=False),
        sa.Column('strategy', sa.String(length=50), nullable=False),
        sa.Column('strategy_params', postgresql.JSONB(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('min_duration_hours', sa.Integer(), nullable=False, server_default='168'),
        sa.Column('min_sample_size', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('completed_at', sa.TIMESTAMP(), nullable=True),
        sa.CheckConstraint("status IN ('active', 'paused', 'completed')", name='check_ab_test_status'),
        sa.CheckConstraint('version_a_id != version_b_id', name='check_version_different'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['fault_tree_id'], ['fault_trees.id'], ),
        sa.ForeignKeyConstraint(['version_a_id'], ['fault_tree_versions.id'], ),
        sa.ForeignKeyConstraint(['version_b_id'], ['fault_tree_versions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_ab_test_configs_fault_tree', 'ab_test_configs', ['fault_tree_id'])
    op.create_index('idx_ab_test_configs_status', 'ab_test_configs', ['status'])
    op.execute("""
        CREATE UNIQUE INDEX unique_active_ab_test
        ON ab_test_configs(fault_tree_id, status)
        WHERE status = 'active'
    """)

    # 创建 ab_test_device_assignments 表
    op.create_table(
        'ab_test_device_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ab_test_id', sa.Integer(), nullable=False),
        sa.Column('device_id', sa.String(length=255), nullable=False),
        sa.Column('assigned_version_id', sa.Integer(), nullable=False),
        sa.Column('assigned_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['ab_test_id'], ['ab_test_configs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assigned_version_id'], ['fault_tree_versions.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ab_test_id', 'device_id', name='unique_device_assignment')
    )
    op.create_index('idx_ab_test_device_assignments_ab_test', 'ab_test_device_assignments', ['ab_test_id'])
    op.create_index('idx_ab_test_device_assignments_device', 'ab_test_device_assignments', ['device_id'])

    # 创建 ab_test_archives 表
    op.create_table(
        'ab_test_archives',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ab_test_id', sa.Integer(), nullable=False),
        sa.Column('version_a_stats', postgresql.JSONB(), nullable=False),
        sa.Column('version_b_stats', postgresql.JSONB(), nullable=False),
        sa.Column('statistical_test_result', postgresql.JSONB(), nullable=False),
        sa.Column('decision', sa.String(length=50), nullable=False),
        sa.Column('archived_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('archived_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['ab_test_id'], ['ab_test_configs.id'], ),
        sa.ForeignKeyConstraint(['archived_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_ab_test_archives_ab_test', 'ab_test_archives', ['ab_test_id'])


def downgrade() -> None:
    op.drop_index('idx_ab_test_archives_ab_test', table_name='ab_test_archives')
    op.drop_table('ab_test_archives')
    op.drop_index('idx_ab_test_device_assignments_device', table_name='ab_test_device_assignments')
    op.drop_index('idx_ab_test_device_assignments_ab_test', table_name='ab_test_device_assignments')
    op.drop_table('ab_test_device_assignments')
    op.execute("DROP INDEX IF EXISTS unique_active_ab_test")
    op.drop_index('idx_ab_test_configs_status', table_name='ab_test_configs')
    op.drop_index('idx_ab_test_configs_fault_tree', table_name='ab_test_configs')
    op.drop_table('ab_test_configs')
