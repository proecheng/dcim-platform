"""add alarm process fields

Revision ID: e4d8fd809e06
Revises: dcc5c9c7516c
Create Date: 2026-02-16 11:01:55.527315

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4d8fd809e06'
down_revision: Union[str, None] = 'dcc5c9c7516c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('alarms', sa.Column('process_remark', sa.Text(), nullable=True, comment='处理备注'))
    op.add_column('alarms', sa.Column('processed_by', sa.Integer(), nullable=True, comment='处理人'))
    op.add_column('alarms', sa.Column('processed_at', sa.DateTime(), nullable=True, comment='处理时间'))


def downgrade() -> None:
    op.drop_column('alarms', 'processed_at')
    op.drop_column('alarms', 'processed_by')
    op.drop_column('alarms', 'process_remark')
