"""story_26_9_training_data_audits

Revision ID: 20260314_0100
Revises: 20260311_0200
Create Date: 2026-03-14

Story 26.9: 训练数据异常检测 — 创建 training_data_audits 表 + contamination 配置
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '20260314_0100'
down_revision: Union[str, None] = '20260311_0200'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()

    if "training_data_audits" not in existing_tables:
        op.create_table(
            "training_data_audits",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("run_date", sa.DateTime(), nullable=False),
            sa.Column("total_samples", sa.Integer(), nullable=False),
            sa.Column("anomaly_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("anomaly_rate", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("contamination", sa.Float(), nullable=False, server_default="0.05"),
            sa.Column("action_taken", sa.String(50), nullable=False),
            sa.Column("anomaly_sample_ids", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )

    # 插入 contamination 默认配置
    op.execute(
        "INSERT INTO system_configs (config_group, config_key, config_value, value_type, description, is_editable) "
        "SELECT 'diagnosis', 'anomaly_contamination', '0.05', 'number', "
        "'IsolationForest contamination 参数（异常率预设）', 1 "
        "WHERE NOT EXISTS (SELECT 1 FROM system_configs WHERE config_group='diagnosis' AND config_key='anomaly_contamination')"
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM system_configs WHERE config_group='diagnosis' AND config_key='anomaly_contamination'"
    )
    op.drop_table("training_data_audits")
