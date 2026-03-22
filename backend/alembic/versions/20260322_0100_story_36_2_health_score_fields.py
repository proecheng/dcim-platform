"""story_36_2_health_score_fields

Revision ID: 20260322_0100
Revises: 20260321_0100
Create Date: 2026-03-22

Story 36.2: DeviceHealthScore 新增 score_factors, data_sufficiency, degradation_score 字段 + device_id 唯一约束
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "20260322_0100"
down_revision: Union[str, None] = "20260321_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    existing_columns = {c["name"] for c in inspector.get_columns("device_health_scores")}

    if "score_factors" not in existing_columns:
        op.add_column("device_health_scores",
                       sa.Column("score_factors", sa.Text(), comment="评分因子详情(JSON)"))

    if "data_sufficiency" not in existing_columns:
        op.add_column("device_health_scores",
                       sa.Column("data_sufficiency", sa.String(20), server_default="minimal",
                                 comment="数据充分度: full/partial/minimal"))

    if "degradation_score" not in existing_columns:
        op.add_column("device_health_scores",
                       sa.Column("degradation_score", sa.Float(), comment="劣化趋势评分 0-100"))

    # device_id 唯一约束
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("device_health_scores")}
    if "uq_device_health_scores_device_id" not in existing_indexes:
        try:
            op.create_index(
                "uq_device_health_scores_device_id",
                "device_health_scores",
                ["device_id"],
                unique=True,
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                "unique index creation skipped (may already exist): %s", e
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    existing_indexes = {idx["name"] for idx in inspector.get_indexes("device_health_scores")}
    if "uq_device_health_scores_device_id" in existing_indexes:
        op.drop_index("uq_device_health_scores_device_id", table_name="device_health_scores")

    existing_columns = {c["name"] for c in inspector.get_columns("device_health_scores")}

    for col in ["degradation_score", "data_sufficiency", "score_factors"]:
        if col in existing_columns:
            op.drop_column("device_health_scores", col)
