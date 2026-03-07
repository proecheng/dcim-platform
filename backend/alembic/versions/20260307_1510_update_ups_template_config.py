"""update UPS device template with rated parameters and init soh_weights

Revision ID: 20260307_1510
Revises: 20260307_1500
Create Date: 2026-03-07 15:10:00

Story 25.3: UPS电池SOH预测
为 UPS 设备模板添加额定参数，并初始化 SOH 权重配置
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
import json


# revision identifiers, used by Alembic.
revision: str = '20260307_1510'
down_revision: Union[str, None] = '20260307_1500'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    初始化 system_configs 表的 SOH 相关配置：
    1. soh_weights: SOH 计算权重配置
    2. ups_rated_params: UPS 设备额定参数（默认值）
    """
    conn = op.get_bind()

    # Part 1: 初始化 system_configs 的 soh_weights 配置
    result = conn.execute(text(
        "SELECT id FROM system_configs WHERE config_group = 'diagnosis' AND config_key = 'soh_weights'"
    ))
    existing_config = result.scalar_one_or_none()

    if existing_config:
        print("system_configs 中已存在 soh_weights 配置，跳过初始化")
    else:
        # 插入默认配置
        default_weights = {"w_r": 0.6, "w_c": 0.4, "version": "v1.0"}
        conn.execute(
            text("""
                INSERT INTO system_configs (config_group, config_key, config_value, value_type, description, is_editable)
                VALUES (:group, :key, :value, :type, :description, :editable)
            """),
            {
                "group": "diagnosis",
                "key": "soh_weights",
                "value": json.dumps(default_weights),
                "type": "json",
                "description": "UPS电池SOH计算权重配置",
                "editable": True
            }
        )
        print("system_configs 中 soh_weights 配置已初始化")

    # Part 2: 初始化 system_configs 的 ups_rated_params 配置
    result = conn.execute(text(
        "SELECT id FROM system_configs WHERE config_group = 'diagnosis' AND config_key = 'ups_rated_params'"
    ))
    existing_params = result.scalar_one_or_none()

    if existing_params:
        print("system_configs 中已存在 ups_rated_params 配置，跳过初始化")
    else:
        # 插入默认额定参数
        default_params = {
            "rated_resistance_mohm": 50.0,
            "rated_cycle_count": 1200,
            "description": "UPS电池默认额定参数，可通过 API 为每台设备单独配置"
        }
        conn.execute(
            text("""
                INSERT INTO system_configs (config_group, config_key, config_value, value_type, description, is_editable)
                VALUES (:group, :key, :value, :type, :description, :editable)
            """),
            {
                "group": "diagnosis",
                "key": "ups_rated_params",
                "value": json.dumps(default_params),
                "type": "json",
                "description": "UPS电池额定参数默认值",
                "editable": True
            }
        )
        print("system_configs 中 ups_rated_params 配置已初始化")


def downgrade() -> None:
    """
    删除 system_configs 中的 SOH 相关配置
    """
    conn = op.get_bind()

    # 删除 soh_weights 配置
    conn.execute(text(
        "DELETE FROM system_configs WHERE config_group = 'diagnosis' AND config_key = 'soh_weights'"
    ))
    print("system_configs 中 soh_weights 配置已删除")

    # 删除 ups_rated_params 配置
    conn.execute(text(
        "DELETE FROM system_configs WHERE config_group = 'diagnosis' AND config_key = 'ups_rated_params'"
    ))
    print("system_configs 中 ups_rated_params 配置已删除")
