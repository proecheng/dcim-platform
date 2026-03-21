"""story_35_3_alarm_source_field

Revision ID: 20260321_0100
Revises: 20260319_0300
Create Date: 2026-03-21

Story 35.3: 网关离线告警 — Alarm 新增 source 字段, 创建索引
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "20260321_0100"
down_revision: Union[str, None] = "20260319_0300"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    alarm_columns = [c["name"] for c in inspector.get_columns("alarms")]
    if "source" not in alarm_columns:
        op.add_column(
            "alarms",
            sa.Column("source", sa.String(100), nullable=True, comment="告警来源标识(如 datasource:123)"),
        )
        op.create_index("ix_alarms_source", "alarms", ["source"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    alarm_columns = [c["name"] for c in inspector.get_columns("alarms")]
    if "source" in alarm_columns:
        op.drop_index("ix_alarms_source", "alarms")
        op.drop_column("alarms", "source")
