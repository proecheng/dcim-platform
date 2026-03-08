import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Add parent directory to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# 从 Settings 读取 DATABASE_URL（支持环境变量切换）
# Alembic 需要同步 URL，将 async driver 转换为同步 driver
from app.core.config import get_settings

_settings = get_settings()
_db_url = _settings.database_url

# 异步 driver → 同步 driver 转换
if "+aiosqlite" in _db_url:
    _sync_url = _db_url.replace("+aiosqlite", "")
elif "+asyncpg" in _db_url:
    _sync_url = _db_url.replace("+asyncpg", "+psycopg2")
else:
    _sync_url = _db_url

config.set_main_option("sqlalchemy.url", _sync_url)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# Import all models to register them with the Base metadata
from app.core.database import Base
from app.models import *  # noqa: F401, F403 - 导入所有模型以注册到 Base.metadata

# Import energy models directly that are not in __init__

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
