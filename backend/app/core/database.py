"""
数据库连接模块
支持 SQLite（开发）和 PostgreSQL+TimescaleDB（生产）
通过环境变量 DATABASE_URL 切换
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from .config import get_settings

settings = get_settings()


def _build_engine_kwargs() -> dict:
    """根据数据库类型构建引擎参数"""
    url = settings.database_url
    kwargs: dict = {
        "echo": settings.debug,
        "future": True,
    }
    if url.startswith("postgresql") or url.startswith("postgres"):
        # PostgreSQL 连接池配置
        kwargs.update(
            {
                "pool_size": 10,
                "max_overflow": 20,
                "pool_timeout": 30,
                "pool_recycle": 1800,  # 30 分钟回收连接
                "pool_pre_ping": True,  # 连接健康检查
            }
        )
    elif url.startswith("sqlite"):
        # SQLite 并发优化配置 + WAL 模式
        # aiosqlite 使用 NullPool，不支持 pool_size/max_overflow
        kwargs.update(
            {
                "connect_args": {
                    "timeout": 60,  # 增加超时时间到 60 秒
                    "check_same_thread": False,
                },
            }
        )
    return kwargs


# 创建异步引擎
engine = create_async_engine(settings.database_url, **_build_engine_kwargs())

# 创建异步会话工厂
async_session = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, autocommit=False, autoflush=False
)


class Base(DeclarativeBase):
    """SQLAlchemy 基类"""

    pass


async def get_db():
    """获取数据库会话"""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """初始化数据库 — 创建所有表并启用 SQLite WAL 模式"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # 如果是 SQLite，启用 WAL 模式以支持并发读写
        if settings.database_url.startswith("sqlite"):
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA synchronous=NORMAL"))
            await conn.execute(text("PRAGMA cache_size=-64000"))  # 64MB 缓存
            await _ensure_sqlite_legacy_columns(conn)


async def _ensure_sqlite_legacy_columns(conn):
    """补齐旧 SQLite 数据库缺失的后续迁移字段。

    Base.metadata.create_all 只会创建新表，不会为既有表补列。开发/演示环境常直接
    启动旧 dcim.db，因此这里用白名单补齐已知兼容字段，避免页面接口因缺列返回 500。
    """
    additions = {
        "alarms": [
            ("source", "VARCHAR(100)"),
        ],
        "datasources": [
            ("parent_datasource_id", "INTEGER"),
        ],
        "device_health_scores": [
            ("score_factors", "TEXT"),
            ("data_sufficiency", "VARCHAR(20) DEFAULT 'minimal'"),
            ("degradation_score", "FLOAT"),
        ],
        "device_templates": [
            ("extra_config", "JSON"),
        ],
        "system_configs": [
            ("version", "INTEGER NOT NULL DEFAULT 1"),
        ],
        "cooling_zones": [
            ("site_id", "INTEGER"),
            ("area_m2", "FLOAT"),
            ("height_m", "FLOAT DEFAULT 3.0"),
            ("thermal_R", "FLOAT"),
            ("thermal_C", "FLOAT"),
            ("bypass_beta", "FLOAT DEFAULT 0.1"),
            ("r_calibrated_at", "DATETIME"),
        ],
        "cooling_linkage_configs": [
            ("cooling_zone_id", "INTEGER"),
            ("precool_target_temp", "FLOAT"),
            ("precool_enabled", "BOOLEAN DEFAULT 0"),
        ],
    }

    table_rows = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
    existing_tables = {row[0] for row in table_rows.fetchall()}

    for table_name, columns in additions.items():
        if table_name not in existing_tables:
            continue

        column_rows = await conn.execute(text(f"PRAGMA table_info({table_name})"))
        existing_columns = {row[1] for row in column_rows.fetchall()}
        for column_name, column_sql in columns:
            if column_name not in existing_columns:
                await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}"))

    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_alarms_source ON alarms (source)"))
    await conn.execute(
        text("CREATE INDEX IF NOT EXISTS ix_datasources_parent_id ON datasources (parent_datasource_id)")
    )

    try:
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_device_health_scores_device_id ON device_health_scores (device_id)"
            )
        )
    except Exception:
        # 旧库如果已有重复 device_id，保留数据优先；业务读写仍可使用新增列。
        pass


def is_postgresql() -> bool:
    """判断当前是否使用 PostgreSQL"""
    url = settings.database_url
    return url.startswith("postgresql") or url.startswith("postgres")
