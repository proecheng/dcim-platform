"""story_25_6_add_dynamic_threshold_config

Revision ID: 8574ebeb7faa
Revises: d20698c35b80
Create Date: 2026-03-07 22:48:11.521477

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8574ebeb7faa'
down_revision: Union[str, None] = 'd20698c35b80'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 添加 version 字段到 system_configs 表（如果不存在）
    conn = op.get_bind()

    # 检查 version 字段是否已存在（SQLite 兼容）
    result = conn.execute(sa.text("PRAGMA table_info(system_configs)"))
    columns = [row[1] for row in result.fetchall()]

    if 'version' not in columns:
        op.add_column('system_configs', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))

    # 2. 创建 config_history 表
    op.create_table(
        'config_history',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('config_id', sa.Integer(), sa.ForeignKey('system_configs.id'), nullable=False),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('operation_type', sa.String(50), nullable=False, server_default='update'),
        sa.Column('updated_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text("(datetime('now'))")),
    )

    # 3. 创建索引
    op.create_index('idx_config_history_config_id', 'config_history', ['config_id'])
    op.create_index('idx_config_history_version', 'config_history', ['version'])

    # 4. 插入动态阈值规则配置
    conn.execute(sa.text("""
        INSERT INTO system_configs (config_group, config_key, config_value, value_type, description, version)
        VALUES
        (
            'alarm',
            'dynamic_threshold_rules',
            '[
                {"condition": "outdoor_temp >= 35", "adjustment": "+1.0", "description": "夏季室外高温允许回风温度升高", "priority": 10},
                {"condition": "it_load_percent > 80", "adjustment": "+0.5", "description": "高负载时允许温度升高", "priority": 5},
                {"condition": "season == ''winter''", "adjustment": "-0.5", "description": "冬季降低温度上限", "priority": 3}
            ]',
            'json',
            '动态告警阈值规则配置',
            1
        )
        ON CONFLICT DO NOTHING
    """))

    # 5. 插入安全边界配置
    conn.execute(sa.text("""
        INSERT INTO system_configs (config_group, config_key, config_value, value_type, description, version)
        VALUES
        (
            'alarm',
            'dynamic_threshold_safety_boundary_percent',
            '20',
            'number',
            '动态阈值调整的安全边界百分比',
            1
        )
        ON CONFLICT DO NOTHING
    """))

    # 6. 插入特性开关配置
    conn.execute(sa.text("""
        INSERT INTO system_configs (config_group, config_key, config_value, value_type, description, version)
        VALUES
        (
            'alarm',
            'DYNAMIC_THRESHOLDS_ENABLED',
            'false',
            'boolean',
            '动态阈值特性开关（默认关闭）',
            1
        )
        ON CONFLICT DO NOTHING
    """))

    # 7. 插入适用点位类型配置
    conn.execute(sa.text("""
        INSERT INTO system_configs (config_group, config_key, config_value, value_type, description, version)
        VALUES
        (
            'alarm',
            'dynamic_threshold_applicable_point_types',
            '["temperature", "humidity"]',
            'json',
            '动态阈值适用的点位类型列表',
            1
        )
        ON CONFLICT DO NOTHING
    """))


def downgrade() -> None:
    # 删除配置记录
    conn = op.get_bind()
    conn.execute(sa.text("""
        DELETE FROM system_configs
        WHERE config_group = 'alarm'
        AND config_key IN (
            'dynamic_threshold_rules',
            'dynamic_threshold_safety_boundary_percent',
            'DYNAMIC_THRESHOLDS_ENABLED',
            'dynamic_threshold_applicable_point_types'
        )
    """))

    # 删除索引
    op.drop_index('idx_config_history_version', 'config_history')
    op.drop_index('idx_config_history_config_id', 'config_history')

    # 删除 config_history 表
    op.drop_table('config_history')

    # 删除 version 字段（如果存在）（SQLite 兼容）
    result = conn.execute(sa.text("PRAGMA table_info(system_configs)"))
    columns = [row[1] for row in result.fetchall()]

    if 'version' in columns:
        op.drop_column('system_configs', 'version')
