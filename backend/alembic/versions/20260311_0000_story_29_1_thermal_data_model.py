"""story_29_1_thermal_data_model

Revision ID: 20260311_0000
Revises: 20260308_0200
Create Date: 2026-03-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision: str = '20260311_0000'
down_revision: Union[str, None] = 'cb105f51fc2b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级数据库架构 - 添加热动力学数据模型"""
    bind = op.get_bind()
    inspector = inspect(bind)
    db_type = bind.dialect.name  # 'postgresql' or 'sqlite'

    # ========== 1. 扩展 cooling_zones 表 ==========
    if 'cooling_zones' in inspector.get_table_names():
        existing_columns = [col['name'] for col in inspector.get_columns('cooling_zones')]

        # 添加 site_id 外键（如果不存在）
        if 'site_id' not in existing_columns:
            op.add_column('cooling_zones', sa.Column('site_id', sa.Integer(), nullable=True, comment='所属站点'))
            # 注意：外键约束在 SQLite 中需要重建表，这里简化处理
            if db_type == 'postgresql':
                op.create_foreign_key('fk_cooling_zones_site_id', 'cooling_zones', 'sites', ['site_id'], ['id'], ondelete='SET NULL')

        # 修改 room_id ondelete 行为（SQLite 不支持 ALTER COLUMN，跳过）
        # PostgreSQL 可以使用 ALTER TABLE ... ALTER CONSTRAINT

        # 添加热模型字段
        if 'area_m2' not in existing_columns:
            op.add_column('cooling_zones', sa.Column('area_m2', sa.Float(), nullable=True, comment='冷通道面积 m²，用于计算热容'))
        if 'height_m' not in existing_columns:
            op.add_column('cooling_zones', sa.Column('height_m', sa.Float(), server_default='3.0', comment='冷通道层高 m'))
        if 'thermal_R' not in existing_columns:
            op.add_column('cooling_zones', sa.Column('thermal_R', sa.Float(), nullable=True, comment='热阻标定值 °C/kW，NULL=未标定'))
        if 'thermal_C' not in existing_columns:
            op.add_column('cooling_zones', sa.Column('thermal_C', sa.Float(), nullable=True, comment='热容标定值 kWh/°C（总热容），NULL=未标定'))
        if 'bypass_beta' not in existing_columns:
            op.add_column('cooling_zones', sa.Column('bypass_beta', sa.Float(), server_default='0.1', comment='气流短路系数 0~0.3，应用层验证范围'))
        if 'r_calibrated_at' not in existing_columns:
            op.add_column('cooling_zones', sa.Column('r_calibrated_at', sa.DateTime(), nullable=True, comment='R/C 最近标定时间'))
    else:
        # 创建 cooling_zones 表（如果不存在）
        op.create_table(
            'cooling_zones',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('zone_code', sa.String(length=50), nullable=False, comment='区域编码'),
            sa.Column('zone_name', sa.String(length=100), nullable=False, comment='区域名称'),
            sa.Column('room_id', sa.Integer(), nullable=True, comment='所属房间ID'),
            sa.Column('site_id', sa.Integer(), nullable=True, comment='所属站点'),
            sa.Column('design_capacity_kw', sa.Float(), nullable=True, comment='设计制冷量(kW)'),
            sa.Column('description', sa.Text(), nullable=True, comment='描述'),
            sa.Column('area_m2', sa.Float(), nullable=True, comment='冷通道面积 m²，用于计算热容'),
            sa.Column('height_m', sa.Float(), server_default='3.0', comment='冷通道层高 m'),
            sa.Column('thermal_R', sa.Float(), nullable=True, comment='热阻标定值 °C/kW，NULL=未标定'),
            sa.Column('thermal_C', sa.Float(), nullable=True, comment='热容标定值 kWh/°C（总热容），NULL=未标定'),
            sa.Column('bypass_beta', sa.Float(), server_default='0.1', comment='气流短路系数 0~0.3，应用层验证范围'),
            sa.Column('r_calibrated_at', sa.DateTime(), nullable=True, comment='R/C 最近标定时间'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
            sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('zone_code'),
        )
        if db_type == 'postgresql':
            op.create_foreign_key('fk_cooling_zones_room_id', 'cooling_zones', 'rooms', ['room_id'], ['id'], ondelete='SET NULL')
            op.create_foreign_key('fk_cooling_zones_site_id', 'cooling_zones', 'sites', ['site_id'], ['id'], ondelete='SET NULL')

    # ========== 2. 扩展 cooling_linkage_configs 表 ==========
    if 'cooling_linkage_configs' in inspector.get_table_names():
        existing_columns = [col['name'] for col in inspector.get_columns('cooling_linkage_configs')]

        # 添加 cooling_zone_id 外键（如果不存在）
        if 'cooling_zone_id' not in existing_columns:
            op.add_column('cooling_linkage_configs', sa.Column('cooling_zone_id', sa.Integer(), nullable=False, comment='关联制冷区域'))
            if db_type == 'postgresql':
                op.create_foreign_key('fk_cooling_linkage_configs_zone_id', 'cooling_linkage_configs', 'cooling_zones', ['cooling_zone_id'], ['id'], ondelete='CASCADE')

        # 添加预冷字段
        if 'precool_target_temp' not in existing_columns:
            op.add_column('cooling_linkage_configs', sa.Column('precool_target_temp', sa.Float(), nullable=True, comment='预冷目标温度 °C'))
        if 'precool_enabled' not in existing_columns:
            op.add_column('cooling_linkage_configs', sa.Column('precool_enabled', sa.Boolean(), server_default='0', comment='是否启用预冷功能'))
    else:
        # 创建 cooling_linkage_configs 表（如果不存在）
        op.create_table(
            'cooling_linkage_configs',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('cooling_zone_id', sa.Integer(), nullable=False, comment='关联制冷区域'),
            sa.Column('enabled', sa.Boolean(), server_default='1', comment='是否启用制冷联动'),
            sa.Column('precool_target_temp', sa.Float(), nullable=True, comment='预冷目标温度 °C'),
            sa.Column('precool_enabled', sa.Boolean(), server_default='0', comment='是否启用预冷功能'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
            sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
            sa.PrimaryKeyConstraint('id'),
        )
        if db_type == 'postgresql':
            op.create_foreign_key('fk_cooling_linkage_configs_zone_id', 'cooling_linkage_configs', 'cooling_zones', ['cooling_zone_id'], ['id'], ondelete='CASCADE')

    # ========== 3. 创建 thermal_parameters 表 ==========
    if 'thermal_parameters' not in inspector.get_table_names():
        op.create_table(
            'thermal_parameters',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('cooling_zone_id', sa.Integer(), nullable=False, comment='关联制冷区域ID'),
            sa.Column('thermal_R', sa.Float(), nullable=True, comment='热阻标定值 °C/kW'),
            sa.Column('thermal_C', sa.Float(), nullable=True, comment='热容标定值 kWh/°C（总热容，非单位面积）'),
            sa.Column('fitting_r_squared', sa.Float(), nullable=True, comment='拟合 R² 值'),
            sa.Column('fitting_method', sa.String(length=20), nullable=True, server_default='manual', comment='标定方法: auto_fit/manual/default'),
            sa.Column('sample_count', sa.Integer(), nullable=True, comment='样本数'),
            sa.Column('calibrated_at', sa.DateTime(), nullable=True, comment='标定时间'),
            sa.Column('is_active', sa.Boolean(), server_default='1', comment='是否为当前生效参数'),
            sa.Column('is_demo', sa.Boolean(), server_default='0', comment='是否为 demo 数据'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
            sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
            sa.ForeignKeyConstraint(['cooling_zone_id'], ['cooling_zones.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        # 创建复合索引
        op.create_index('ix_thermal_params_zone_active', 'thermal_parameters', ['cooling_zone_id', 'is_active'], unique=False)

        # 创建部分唯一约束（仅 PostgreSQL 支持）
        if db_type == 'postgresql':
            # PostgreSQL 支持部分唯一索引
            bind.execute(text(
                "CREATE UNIQUE INDEX uq_thermal_params_zone_active "
                "ON thermal_parameters (cooling_zone_id, is_active) "
                "WHERE is_active = TRUE"
            ))

    # ========== 4. 创建 temperature_prediction_logs 表 ==========
    if 'temperature_prediction_logs' not in inspector.get_table_names():
        op.create_table(
            'temperature_prediction_logs',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('cooling_zone_id', sa.Integer(), nullable=False, comment='关联制冷区域ID'),
            sa.Column('predicted_temp', sa.Float(), nullable=False, comment='预测温度 °C'),
            sa.Column('actual_temp', sa.Float(), nullable=True, comment='实际温度 °C'),
            sa.Column('prediction_horizon_min', sa.Integer(), nullable=False, comment='预测时长 分钟'),
            sa.Column('deviation', sa.Float(), nullable=True, comment='偏差 = actual - predicted'),
            sa.Column('model_version', sa.String(length=50), nullable=False, comment='模型参数版本'),
            sa.Column('created_at', sa.DateTime(), nullable=False, comment='记录时间'),
            sa.ForeignKeyConstraint(['cooling_zone_id'], ['cooling_zones.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        # 创建复合索引（created_at DESC）
        op.create_index('ix_temp_pred_zone_time', 'temperature_prediction_logs', ['cooling_zone_id', sa.text('created_at DESC')], unique=False)

        # TimescaleDB hypertable 转换（仅 PostgreSQL）
        if db_type == 'postgresql':
            try:
                bind.execute(text(
                    "SELECT create_hypertable('temperature_prediction_logs', 'created_at', "
                    "chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE)"
                ))
            except Exception as e:
                # TimescaleDB 扩展可能未安装，跳过
                print(f"Warning: TimescaleDB hypertable creation skipped: {e}")

    # ========== 5. 数据清理：删除孤立的 cooling_zone_id 引用 ==========
    # 注意：这里假设 thermal_parameters 和 temperature_prediction_logs 是新表，无需清理
    # 如果 cooling_linkage_configs 已存在且有数据，需要清理孤立引用
    if 'cooling_linkage_configs' in inspector.get_table_names():
        try:
            bind.execute(text(
                "DELETE FROM cooling_linkage_configs "
                "WHERE cooling_zone_id IS NOT NULL "
                "AND cooling_zone_id NOT IN (SELECT id FROM cooling_zones)"
            ))
        except Exception:
            pass  # 如果 cooling_zone_id 列不存在，跳过


def downgrade() -> None:
    """回滚数据库架构 - 删除热动力学数据模型"""
    # WARNING: 回滚将丢失 thermal_parameters 和 temperature_prediction_logs 数据

    bind = op.get_bind()
    inspector = inspect(bind)
    db_type = bind.dialect.name

    # ========== 1. 删除 temperature_prediction_logs 表 ==========
    if 'temperature_prediction_logs' in inspector.get_table_names():
        # TimescaleDB hypertable 删除（仅 PostgreSQL）
        if db_type == 'postgresql':
            try:
                # 先清理 chunks
                bind.execute(text("SELECT drop_chunks('temperature_prediction_logs', older_than => INTERVAL '0 seconds')"))
            except Exception:
                pass  # TimescaleDB 可能未安装

        # 删除索引
        try:
            op.drop_index('ix_temp_pred_zone_time', table_name='temperature_prediction_logs')
        except Exception:
            pass

        # 删除表
        op.drop_table('temperature_prediction_logs')

    # ========== 2. 删除 thermal_parameters 表 ==========
    if 'thermal_parameters' in inspector.get_table_names():
        # 删除索引
        try:
            op.drop_index('ix_thermal_params_zone_active', table_name='thermal_parameters')
        except Exception:
            pass

        # 删除部分唯一索引（仅 PostgreSQL）
        if db_type == 'postgresql':
            try:
                bind.execute(text("DROP INDEX IF EXISTS uq_thermal_params_zone_active"))
            except Exception:
                pass

        # 删除表
        op.drop_table('thermal_parameters')

    # ========== 3. 删除 cooling_linkage_configs 新增字段 ==========
    if 'cooling_linkage_configs' in inspector.get_table_names():
        existing_columns = [col['name'] for col in inspector.get_columns('cooling_linkage_configs')]

        if 'precool_enabled' in existing_columns:
            op.drop_column('cooling_linkage_configs', 'precool_enabled')
        if 'precool_target_temp' in existing_columns:
            op.drop_column('cooling_linkage_configs', 'precool_target_temp')
        if 'cooling_zone_id' in existing_columns:
            # 删除外键约束（仅 PostgreSQL）
            if db_type == 'postgresql':
                try:
                    op.drop_constraint('fk_cooling_linkage_configs_zone_id', 'cooling_linkage_configs', type_='foreignkey')
                except Exception:
                    pass
            op.drop_column('cooling_linkage_configs', 'cooling_zone_id')

    # ========== 4. 删除 cooling_zones 新增字段 ==========
    if 'cooling_zones' in inspector.get_table_names():
        existing_columns = [col['name'] for col in inspector.get_columns('cooling_zones')]

        if 'r_calibrated_at' in existing_columns:
            op.drop_column('cooling_zones', 'r_calibrated_at')
        if 'bypass_beta' in existing_columns:
            op.drop_column('cooling_zones', 'bypass_beta')
        if 'thermal_C' in existing_columns:
            op.drop_column('cooling_zones', 'thermal_C')
        if 'thermal_R' in existing_columns:
            op.drop_column('cooling_zones', 'thermal_R')
        if 'height_m' in existing_columns:
            op.drop_column('cooling_zones', 'height_m')
        if 'area_m2' in existing_columns:
            op.drop_column('cooling_zones', 'area_m2')
        if 'site_id' in existing_columns:
            # 删除外键约束（仅 PostgreSQL）
            if db_type == 'postgresql':
                try:
                    op.drop_constraint('fk_cooling_zones_site_id', 'cooling_zones', type_='foreignkey')
                except Exception:
                    pass
            op.drop_column('cooling_zones', 'site_id')
