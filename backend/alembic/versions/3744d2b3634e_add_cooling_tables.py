"""add cooling tables

Revision ID: 3744d2b3634e
Revises: 46e4ea651319
Create Date: 2026-02-15 09:22:16.738050

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3744d2b3634e"
down_revision: Union[str, None] = "46e4ea651319"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create cooling_groups table
    op.create_table(
        "cooling_groups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("group_name", sa.String(length=100), nullable=False, comment="群控组名称"),
        sa.Column("group_mode", sa.String(length=20), nullable=True, comment="模式: independent/linked"),
        sa.Column("description", sa.Text(), nullable=True, comment="描述"),
        sa.Column("created_at", sa.DateTime(), nullable=True, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=True, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create cooling_units table
    op.create_table(
        "cooling_units",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False, comment="关联设备ID"),
        sa.Column("unit_type", sa.String(length=20), nullable=True, comment="类型: indoor/outdoor"),
        sa.Column("cooling_capacity_kw", sa.Float(), nullable=True, comment="制冷量(kW)"),
        sa.Column("refrigerant_type", sa.String(length=20), nullable=True, comment="制冷剂类型"),
        sa.Column("compressor_count", sa.Integer(), nullable=True, comment="压缩机数量"),
        sa.Column("fan_count", sa.Integer(), nullable=True, comment="风机数量"),
        sa.Column("group_id", sa.Integer(), nullable=True, comment="群控组ID"),
        sa.Column("description", sa.Text(), nullable=True, comment="描述"),
        sa.Column("created_at", sa.DateTime(), nullable=True, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=True, comment="更新时间"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["group_id"], ["cooling_groups.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create cold_aisles table
    op.create_table(
        "cold_aisles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False, comment="关联设备ID"),
        sa.Column("aisle_code", sa.String(length=50), nullable=True, comment="通道编码"),
        sa.Column("aisle_name", sa.String(length=100), nullable=True, comment="通道名称"),
        sa.Column("skylight_count", sa.Integer(), nullable=True, comment="天窗数量"),
        sa.Column("location", sa.String(length=100), nullable=True, comment="位置描述"),
        sa.Column("description", sa.Text(), nullable=True, comment="描述"),
        sa.Column("created_at", sa.DateTime(), nullable=True, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=True, comment="更新时间"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("cold_aisles")
    op.drop_table("cooling_units")
    op.drop_table("cooling_groups")
