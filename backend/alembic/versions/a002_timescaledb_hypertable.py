"""TimescaleDB hypertable for point_history

Revision ID: a002_timescaledb_hypertable
Revises: a001_full_schema
Create Date: 2026-02-18

Converts point_history to a TimescaleDB hypertable (partitioned by recorded_at).
- Chunk interval: 1 day
- Compression policy: auto-compress after 7 days
- Retention policy: auto-drop after 90 days
Only runs on PostgreSQL + TimescaleDB; skipped on SQLite.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a002_timescaledb_hypertable"
down_revision = "a001_full_schema"
branch_labels = None
depends_on = None


def _is_timescaledb(connection) -> bool:
    """检测当前数据库是否安装了 TimescaleDB 扩展"""
    try:
        result = connection.execute(sa.text("SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'"))
        return result.fetchone() is not None
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect != "postgresql":
        # SQLite: 不支持 TimescaleDB，跳过
        return

    # 启用 TimescaleDB 扩展（如果尚未启用）
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")

    # 检查 point_history 表是否已经是 hypertable
    result = bind.execute(
        sa.text("SELECT 1 FROM timescaledb_information.hypertables WHERE hypertable_name = 'point_history'")
    )
    if result.fetchone():
        # 已经是 hypertable，跳过
        return

    # point_history 表需要移除自增主键约束才能创建 hypertable
    # TimescaleDB 要求分区列（recorded_at）必须包含在主键/唯一约束中
    # 策略: 删除旧主键，添加复合主键 (id, recorded_at)
    op.execute("ALTER TABLE point_history DROP CONSTRAINT IF EXISTS point_history_pkey")
    op.execute("ALTER TABLE point_history ADD PRIMARY KEY (id, recorded_at)")

    # 转换为 hypertable — chunk 间隔 1 天
    op.execute(
        "SELECT create_hypertable('point_history', 'recorded_at', "
        "chunk_time_interval => INTERVAL '1 day', "
        "migrate_data => true, "
        "if_not_exists => true)"
    )

    # 启用压缩 — 按 point_id 分段压缩，按 recorded_at 排序
    op.execute(
        "ALTER TABLE point_history SET ("
        "timescaledb.compress, "
        "timescaledb.compress_segmentby = 'point_id', "
        "timescaledb.compress_orderby = 'recorded_at DESC'"
        ")"
    )

    # 添加压缩策略 — 7 天后自动压缩
    op.execute("SELECT add_compression_policy('point_history', INTERVAL '7 days', if_not_exists => true)")

    # 添加数据保留策略 — 90 天后自动删除
    op.execute("SELECT add_retention_policy('point_history', INTERVAL '90 days', if_not_exists => true)")


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect != "postgresql":
        return

    # 移除保留策略
    try:
        op.execute("SELECT remove_retention_policy('point_history', if_exists => true)")
    except Exception:
        pass

    # 移除压缩策略
    try:
        op.execute("SELECT remove_compression_policy('point_history', if_exists => true)")
    except Exception:
        pass

    # 注意: 无法将 hypertable 转回普通表，降级仅移除策略
