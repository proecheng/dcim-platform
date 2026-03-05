"""add source tracking columns

Revision ID: b28_1_source_tracking
Revises: 1e866a5d60a6
Create Date: 2026-03-05

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b28_1_source_tracking"
down_revision: Union[str, None] = "1e866a5d60a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite 兼容：使用 batch mode
    with op.batch_alter_table("points") as batch_op:
        batch_op.add_column(
            sa.Column("source", sa.String(20), server_default="manual")
        )
    with op.batch_alter_table("point_realtime") as batch_op:
        batch_op.add_column(
            sa.Column("source", sa.String(20), server_default="unknown")
        )
    with op.batch_alter_table("point_history") as batch_op:
        batch_op.add_column(
            sa.Column("source", sa.String(20), server_default="unknown")
        )
    with op.batch_alter_table("point_data_latest") as batch_op:
        batch_op.add_column(
            sa.Column("source", sa.String(20), server_default="unknown")
        )
    with op.batch_alter_table("alarms") as batch_op:
        batch_op.add_column(
            sa.Column("data_source", sa.String(20), server_default="unknown")
        )

    # Data migration: 现有 demo 点位的 source 修正
    # 安全条件：仅在全量 demo 数据库中执行（无真实网关点位时）
    op.execute(
        """
        UPDATE points SET source = 'demo'
        WHERE source = 'manual'
        AND NOT EXISTS (
            SELECT 1 FROM point_data_latest WHERE gateway_id IS NOT NULL AND gateway_id != ''
        )
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("alarms") as batch_op:
        batch_op.drop_column("data_source")
    with op.batch_alter_table("point_data_latest") as batch_op:
        batch_op.drop_column("source")
    with op.batch_alter_table("point_history") as batch_op:
        batch_op.drop_column("source")
    with op.batch_alter_table("point_realtime") as batch_op:
        batch_op.drop_column("source")
    with op.batch_alter_table("points") as batch_op:
        batch_op.drop_column("source")
