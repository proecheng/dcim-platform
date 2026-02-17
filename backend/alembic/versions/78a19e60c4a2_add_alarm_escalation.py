"""add_alarm_escalation

Revision ID: 78a19e60c4a2
Revises: e4d8fd809e06
Create Date: 2026-02-16 12:38:30.165159

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '78a19e60c4a2'
down_revision: Union[str, None] = 'e4d8fd809e06'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建告警升级规则表
    op.create_table('alarm_escalations',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('rule_name', sa.String(length=100), nullable=False, comment='规则名称'),
    sa.Column('source_level', sa.String(length=20), nullable=False, comment='源告警级别'),
    sa.Column('timeout_minutes', sa.Integer(), nullable=False, comment='超时时间(分钟)'),
    sa.Column('target_level', sa.String(length=20), nullable=False, comment='升级后告警级别'),
    sa.Column('notify_user_ids', sa.String(length=500), nullable=True, comment='通知对象(逗号分隔用户ID)'),
    sa.Column('is_enabled', sa.Boolean(), nullable=True, comment='是否启用'),
    sa.Column('description', sa.Text(), nullable=True, comment='规则描述'),
    sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
    sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
    sa.PrimaryKeyConstraint('id')
    )
    # 告警表新增升级相关字段
    op.add_column('alarms', sa.Column('escalation_count', sa.Integer(), nullable=True, comment='升级次数'))
    op.add_column('alarms', sa.Column('escalated_from', sa.String(length=20), nullable=True, comment='升级前告警级别'))
    op.add_column('alarms', sa.Column('escalation_remark', sa.Text(), nullable=True, comment='升级备注'))


def downgrade() -> None:
    op.drop_column('alarms', 'escalation_remark')
    op.drop_column('alarms', 'escalated_from')
    op.drop_column('alarms', 'escalation_count')
    op.drop_table('alarm_escalations')
