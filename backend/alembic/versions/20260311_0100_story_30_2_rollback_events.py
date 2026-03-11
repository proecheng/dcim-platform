"""story_30_2_rollback_events

Revision ID: 20260311_0100
Revises: 20260311_0000
Create Date: 2026-03-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '20260311_0100'
down_revision: Union[str, None] = '20260311_0000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 rollback_events 表"""
    bind = op.get_bind()
    inspector = inspect(bind)

    if 'rollback_events' not in inspector.get_table_names():
        op.create_table(
            'rollback_events',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('zone_id', sa.Integer(), sa.ForeignKey('cooling_zones.id'), nullable=False),
            sa.Column('trigger_type', sa.String(30), nullable=False),
            sa.Column('trigger_value', sa.Float(), nullable=True),
            sa.Column('threshold', sa.Float(), nullable=True),
            sa.Column('action', sa.String(100), nullable=False),
            sa.Column('status', sa.String(20), server_default='active'),
            sa.Column('context_json', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('resolved_at', sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    """删除 rollback_events 表"""
    op.drop_table('rollback_events')
