"""
数据库连接模块
支持 SQLite（开发）和 PostgreSQL+TimescaleDB（生产）
通过环境变量 DATABASE_URL 切换
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
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
    """初始化数据库 — 创建所有表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def is_postgresql() -> bool:
    """判断当前是否使用 PostgreSQL"""
    url = settings.database_url
    return url.startswith("postgresql") or url.startswith("postgres")
