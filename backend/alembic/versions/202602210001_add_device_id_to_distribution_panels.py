"""add device_id to distribution_panels

Revision ID: 202602210001
Revises:
Create Date: 2026-02-21 13:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '202602210001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('distribution_panels', sa.Column('device_id', sa.Integer(), nullable=True, comment='关联动环设备ID'))
    # SQLite 不支持 ALTER TABLE ADD CONSTRAINT，跳过外键约束
    # op.create_foreign_key('fk_distribution_panels_device_id_devices', 'distribution_panels', 'devices', ['device_id'], ['id'])


def downgrade() -> None:
    op.drop_column('distribution_panels', 'device_id')
