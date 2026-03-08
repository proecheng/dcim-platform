"""Story 25.7: Trend Analysis and Multi-Sensor Fusion

Revision ID: 20260308_1000
Revises: d20698c35b80
Create Date: 2026-03-08 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = '20260308_1000'
down_revision: Union[str, None] = 'd20698c35b80'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Story 25.7 数据库变更:
    1. points 表新增 height_level 字段
    2. 创建 trend_warnings 表
    3. 创建 sensor_fusion_records 表
    4. 创建 TimescaleDB 连续聚合视图
    5. 添加配置项到 system_configs
    """
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    # 1. 在 points 表添加 height_level 字段
    columns = [col['name'] for col in inspector.get_columns('points')]
    if 'height_level' not in columns:
        op.add_column('points', sa.Column('height_level', sa.Float(), nullable=True, server_default='1.5'))
        print("Added height_level column to points table")
    else:
        print("height_level column already exists in points table")

    # 2. 创建 trend_warnings 表
    if 'trend_warnings' not in tables:
        op.create_table(
            'trend_warnings',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('point_id', sa.Integer(), nullable=False),
            sa.Column('trend_type', sa.String(20), nullable=False),
            sa.Column('start_value', sa.Float(), nullable=False),
            sa.Column('end_value', sa.Float(), nullable=False),
            sa.Column('total_change', sa.Float(), nullable=False),
            sa.Column('message', sa.Text(), nullable=False),
            sa.Column('level', sa.String(20), nullable=False, server_default='info'),
            sa.Column('detected_at', sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
            sa.Column('acknowledged', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('acknowledged_by', sa.Integer(), nullable=True),
            sa.Column('acknowledged_at', sa.TIMESTAMP(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['point_id'], ['points.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['acknowledged_by'], ['users.id'], ondelete='SET NULL')
        )

        # 创建索引
        op.create_index('idx_trend_warnings_point_time', 'trend_warnings', ['point_id', 'detected_at'], postgresql_ops={'detected_at': 'DESC'})
        op.create_index('idx_trend_warnings_ack', 'trend_warnings', ['acknowledged', 'detected_at'], postgresql_ops={'detected_at': 'DESC'})
        print("Created trend_warnings table with indexes")
    else:
        print("trend_warnings table already exists")

    # 3. 创建 sensor_fusion_records 表
    if 'sensor_fusion_records' not in tables:
        op.create_table(
            'sensor_fusion_records',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('zone_id', sa.Integer(), nullable=False),
            sa.Column('sensor_count', sa.Integer(), nullable=False),
            sa.Column('std_dev', sa.Float(), nullable=True),
            sa.Column('evidence_type', sa.String(50), nullable=False),
            sa.Column('is_evidence', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('probability', sa.Float(), nullable=True),
            sa.Column('message', sa.Text(), nullable=True),
            sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['zone_id'], ['zones.id'], ondelete='CASCADE')
        )

        # 创建索引
        op.create_index('idx_sensor_fusion_zone_time', 'sensor_fusion_records', ['zone_id', 'created_at'], postgresql_ops={'created_at': 'DESC'})
        print("Created sensor_fusion_records table with index")
    else:
        print("sensor_fusion_records table already exists")

    # 4. 创建 TimescaleDB 连续聚合视图
    # 注意：这些视图依赖 TimescaleDB 扩展，如果使用 SQLite 则跳过
    if conn.dialect.name == 'postgresql':
        try:
            # 检查视图是否已存在
            result = conn.execute(sa.text("""
                SELECT COUNT(*) FROM pg_matviews WHERE matviewname = 'temp_7d_avg'
            """))
            if result.scalar() == 0:
                # 创建温度 7 天移动平均连续聚合视图
                conn.execute(sa.text("""
                    CREATE MATERIALIZED VIEW temp_7d_avg
                    WITH (timescaledb.continuous) AS
                    SELECT
                        time_bucket('1 day', ph.time) AS day,
                        ph.point_id,
                        AVG(ph.value) AS avg_value,
                        COUNT(*) AS sample_count
                    FROM point_history ph
                    JOIN points p ON ph.point_id = p.id
                    WHERE (p.unit LIKE '%℃%' OR p.unit LIKE '%°C%')
                      AND p.enabled = true
                      AND (ph.quality_flag IS NULL OR ph.quality_flag != 'poor')
                    GROUP BY day, ph.point_id
                    HAVING COUNT(*) >= 10
                """))

                # 设置连续聚合刷新策略
                conn.execute(sa.text("""
                    SELECT add_continuous_aggregate_policy('temp_7d_avg',
                        start_offset => INTERVAL '7 days',
                        end_offset => INTERVAL '2 hours',
                        schedule_interval => INTERVAL '1 hour')
                """))

                # 设置 materialized_only=false
                conn.execute(sa.text("""
                    ALTER MATERIALIZED VIEW temp_7d_avg SET (timescaledb.materialized_only=false)
                """))

                # 创建索引
                conn.execute(sa.text("""
                    CREATE INDEX idx_temp_7d_avg_point_day ON temp_7d_avg (point_id, day DESC)
                """))
                print("Created temp_7d_avg continuous aggregate view")
            else:
                print("temp_7d_avg view already exists")

            # 创建湿度 7 天移动平均连续聚合视图
            result = conn.execute(sa.text("""
                SELECT COUNT(*) FROM pg_matviews WHERE matviewname = 'humidity_7d_avg'
            """))
            if result.scalar() == 0:
                conn.execute(sa.text("""
                    CREATE MATERIALIZED VIEW humidity_7d_avg
                    WITH (timescaledb.continuous) AS
                    SELECT
                        time_bucket('1 day', ph.time) AS day,
                        ph.point_id,
                        AVG(ph.value) AS avg_value,
                        COUNT(*) AS sample_count
                    FROM point_history ph
                    JOIN points p ON ph.point_id = p.id
                    WHERE (p.unit LIKE '%RH%' OR p.unit LIKE '%湿度%')
                      AND p.enabled = true
                      AND (ph.quality_flag IS NULL OR ph.quality_flag != 'poor')
                    GROUP BY day, ph.point_id
                    HAVING COUNT(*) >= 10
                """))

                # 设置连续聚合刷新策略
                conn.execute(sa.text("""
                    SELECT add_continuous_aggregate_policy('humidity_7d_avg',
                        start_offset => INTERVAL '7 days',
                        end_offset => INTERVAL '2 hours',
                        schedule_interval => INTERVAL '1 hour')
                """))

                # 设置 materialized_only=false
                conn.execute(sa.text("""
                    ALTER MATERIALIZED VIEW humidity_7d_avg SET (timescaledb.materialized_only=false)
                """))

                # 创建索引
                conn.execute(sa.text("""
                    CREATE INDEX idx_humidity_7d_avg_point_day ON humidity_7d_avg (point_id, day DESC)
                """))
                print("Created humidity_7d_avg continuous aggregate view")
            else:
                print("humidity_7d_avg view already exists")
        except Exception as e:
            print(f"Warning: Failed to create TimescaleDB continuous aggregate views: {e}")
            print("This is expected if TimescaleDB extension is not installed")
    else:
        print("Skipping TimescaleDB continuous aggregate views (not PostgreSQL)")

    # 5. 添加配置项到 system_configs
    if 'system_configs' in tables:
        # 检查配置是否已存在
        result = conn.execute(sa.text("""
            SELECT COUNT(*) FROM system_configs
            WHERE config_group = 'diagnosis' AND config_key = 'trend_threshold_temperature'
        """))
        if result.scalar() == 0:
            conn.execute(sa.text("""
                INSERT INTO system_configs (config_group, config_key, config_value, value_type, description)
                VALUES
                    ('diagnosis', 'trend_threshold_temperature', '0.5', 'number', '温度趋势预警阈值（℃）'),
                    ('diagnosis', 'trend_threshold_humidity', '3.0', 'number', '湿度趋势预警阈值（%RH）'),
                    ('diagnosis', 'trend_analysis_enabled', 'true', 'boolean', '趋势分析特性开关'),
                    ('diagnosis', 'sensor_fusion_enabled', 'true', 'boolean', '多传感器融合特性开关'),
                    ('diagnosis', 'airflow_variance_threshold', '5.0', 'number', '气流不均匀标准差阈值（℃）')
            """))
            print("Added trend analysis configuration to system_configs")
        else:
            print("Trend analysis configuration already exists in system_configs")
    else:
        print("system_configs table does not exist, skipping configuration")


def downgrade() -> None:
    """回滚 Story 25.7 数据库变更"""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    # 删除配置项
    if 'system_configs' in tables:
        conn.execute(sa.text("""
            DELETE FROM system_configs
            WHERE config_group = 'diagnosis'
            AND config_key IN (
                'trend_threshold_temperature',
                'trend_threshold_humidity',
                'trend_analysis_enabled',
                'sensor_fusion_enabled',
                'airflow_variance_threshold'
            )
        """))
        print("Removed trend analysis configuration from system_configs")

    # 删除 TimescaleDB 连续聚合视图
    if conn.dialect.name == 'postgresql':
        result = conn.execute(sa.text("""
            SELECT COUNT(*) FROM pg_matviews WHERE matviewname = 'temp_7d_avg'
        """))
        if result.scalar() > 0:
            conn.execute(sa.text("DROP MATERIALIZED VIEW IF EXISTS temp_7d_avg CASCADE"))
            print("Dropped temp_7d_avg view")

        result = conn.execute(sa.text("""
            SELECT COUNT(*) FROM pg_matviews WHERE matviewname = 'humidity_7d_avg'
        """))
        if result.scalar() > 0:
            conn.execute(sa.text("DROP MATERIALIZED VIEW IF EXISTS humidity_7d_avg CASCADE"))
            print("Dropped humidity_7d_avg view")

    # 删除 sensor_fusion_records 表
    if 'sensor_fusion_records' in tables:
        op.drop_index('idx_sensor_fusion_zone_time', table_name='sensor_fusion_records')
        op.drop_table('sensor_fusion_records')
        print("Dropped sensor_fusion_records table")

    # 删除 trend_warnings 表
    if 'trend_warnings' in tables:
        op.drop_index('idx_trend_warnings_ack', table_name='trend_warnings')
        op.drop_index('idx_trend_warnings_point_time', table_name='trend_warnings')
        op.drop_table('trend_warnings')
        print("Dropped trend_warnings table")

    # 删除 points 表的 height_level 字段
    columns = [col['name'] for col in inspector.get_columns('points')]
    if 'height_level' in columns:
        op.drop_column('points', 'height_level')
        print("Dropped height_level column from points table")
