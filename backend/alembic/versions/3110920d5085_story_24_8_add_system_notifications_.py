"""Story 24.8: Add system_notifications table

Revision ID: 3110920d5085
Revises: c3d2198f1065
Create Date: 2026-03-06 19:07:11.094611

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3110920d5085'
down_revision: Union[str, None] = 'c3d2198f1065'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create system_notifications table
    op.create_table(
        'system_notifications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False, comment='通知标题'),
        sa.Column('content', sa.Text(), nullable=False, comment='通知内容'),
        sa.Column('notification_type', sa.String(length=50), nullable=False, comment='通知类型'),
        sa.Column('target_role', sa.String(length=20), nullable=False, comment='目标角色: admin/operator/viewer'),
        sa.Column('data', sa.JSON(), nullable=True, comment='附加数据'),
        sa.Column('is_read', sa.Boolean(), nullable=True, comment='是否已读'),
        sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_system_notifications_target_role', 'system_notifications', ['target_role'])
    op.create_index('ix_system_notifications_is_read', 'system_notifications', ['is_read'])
    op.create_index('ix_system_notifications_created_at', 'system_notifications', ['created_at'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_system_notifications_created_at', table_name='system_notifications')
    op.drop_index('ix_system_notifications_is_read', table_name='system_notifications')
    op.drop_index('ix_system_notifications_target_role', table_name='system_notifications')

    # Drop table
    op.drop_table('system_notifications')
