"""power_device_flexibility_fields

Revision ID: 20260707_0100
Revises: 20260322_0200
Create Date: 2026-07-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "20260707_0100"
down_revision: Union[str, None] = "20260322_0200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = {c["name"] for c in inspector.get_columns("power_devices")}

    if "load_subtype" not in columns:
        op.add_column("power_devices", sa.Column("load_subtype", sa.String(50), nullable=True, comment="负荷细分类型"))
    if "controllable_params" not in columns:
        op.add_column("power_devices", sa.Column("controllable_params", sa.JSON(), nullable=True, comment="可控参数/控制能力画像"))
    if "thermal_storage_config" not in columns:
        op.add_column("power_devices", sa.Column("thermal_storage_config", sa.JSON(), nullable=True, comment="蓄冷系统配置"))
    if "flexibility_factor" not in columns:
        op.add_column("power_devices", sa.Column("flexibility_factor", sa.Float(), nullable=True, comment="人工修正柔性系数"))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = {c["name"] for c in inspector.get_columns("power_devices")}

    for column_name in ["flexibility_factor", "thermal_storage_config", "controllable_params", "load_subtype"]:
        if column_name in columns:
            op.drop_column("power_devices", column_name)
