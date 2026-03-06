"""add_fault_tree_versions_table

Revision ID: 5f3a9c2b1d7e
Revises: 4cbe2c1df9bb
Create Date: 2026-03-06 14:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '5f3a9c2b1d7e'
down_revision: Union[str, None] = '4cbe2c1df9bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'fault_tree_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tree_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('snapshot', sa.Text(), nullable=False),
        sa.Column('hmac_signature', sa.String(length=64), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('activated_at', sa.TIMESTAMP(), nullable=True),
        sa.CheckConstraint("status IN ('draft', 'reviewed', 'active', 'archived')", name='check_status'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['tree_id'], ['fault_trees.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tree_id', 'version_number', name='uq_tree_version')
    )
    op.create_index(op.f('ix_fault_tree_versions_id'), 'fault_tree_versions', ['id'], unique=False)
    op.create_index(op.f('ix_fault_tree_versions_tree_id'), 'fault_tree_versions', ['tree_id'], unique=False)
    op.create_index(op.f('ix_fault_tree_versions_status'), 'fault_tree_versions', ['status'], unique=False)
    op.create_index('ix_fault_tree_versions_tree_status', 'fault_tree_versions', ['tree_id', 'status'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_fault_tree_versions_tree_status', table_name='fault_tree_versions')
    op.drop_index(op.f('ix_fault_tree_versions_status'), table_name='fault_tree_versions')
    op.drop_index(op.f('ix_fault_tree_versions_tree_id'), table_name='fault_tree_versions')
    op.drop_index(op.f('ix_fault_tree_versions_id'), table_name='fault_tree_versions')
    op.drop_table('fault_tree_versions')
