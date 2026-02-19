"""
Pytest 配置和 fixtures
"""
import pytest
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from httpx import AsyncClient, ASGITransport
from jose import jwt as jose_jwt

from app.core.database import Base, get_db
from app.core.security import get_password_hash, create_access_token
from app.core.config import get_settings

# 确保所有模型在 create_all 之前被导入
import app.models  # noqa: F401


# ==================== 同步 fixtures (旧测试文件依赖，迁移后移除) ====================

@pytest.fixture(scope="session")
def engine():
    """创建同步测试数据库引擎"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(engine):
    """创建同步数据库会话"""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def auth_token():
    """模拟认证 token（旧测试使用）"""
    return "test_token_12345"


# ==================== 异步 fixtures (新增) ====================

TEST_DB_URL = "sqlite+aiosqlite://"

# 测试专用密码（与生产环境无关）
TEST_PASSWORD = "test_secure_pwd_!@#"


def _create_test_token(username: str, jti: str) -> str:
    """生成测试用 JWT token（集中管理 token 生成逻辑）"""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jose_jwt.encode(
        {"sub": username, "exp": expire, "jti": jti},
        settings.secret_key,
        algorithm="HS256",
    )


async def _create_user_with_token(async_db, username, role, real_name, email):
    """创建测试用户并返回 (user, token) — 内部工厂函数"""
    from app.models.user import User, UserSession

    user = User(
        username=username,
        password_hash=get_password_hash(TEST_PASSWORD),
        real_name=real_name,
        email=email,
        role=role,
        is_active=True,
    )
    async_db.add(user)
    await async_db.flush()

    jti = uuid.uuid4().hex
    session_record = UserSession(
        user_id=user.id,
        token_jti=jti,
        is_active=True,
    )
    async_db.add(session_record)
    await async_db.flush()

    token = _create_test_token(username, jti)
    return user, token


@pytest.fixture(scope="function")
async def async_engine():
    """创建异步测试数据库引擎（function 级别，避免事件循环 scope 不匹配）"""
    _engine = create_async_engine(
        TEST_DB_URL,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    await _engine.dispose()


@pytest.fixture(scope="function")
async def async_db(async_engine):
    """每个测试函数独立的异步数据库会话（使用 savepoint 实现自动回滚）"""
    conn = await async_engine.connect()
    trans = await conn.begin()
    session = AsyncSession(bind=conn, expire_on_commit=False)

    # 让 session.commit() 实际上只提交到 savepoint，不提交外层事务
    nested = await conn.begin_nested()

    @event.listens_for(session.sync_session, "after_transaction_end")
    def restart_savepoint(session_sync, transaction):
        nonlocal nested
        if transaction.nested and not transaction._parent.nested:
            nested = conn.sync_connection.begin_nested()

    yield session

    await session.close()
    await trans.rollback()
    await conn.close()


@pytest.fixture(scope="function")
async def client(async_db):
    """异步 HTTP 测试客户端（注入测试数据库，不触发 lifespan）"""
    from app.main import app
    from app.api.deps import get_db as deps_get_db

    async def override_get_db():
        yield async_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[deps_get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def admin_user(async_db):
    """创建测试管理员用户并返回 (user, token)"""
    return await _create_user_with_token(
        async_db, "test_admin", "admin", "测试管理员", "admin@test.local"
    )


@pytest.fixture(scope="function")
async def operator_user(async_db):
    """创建测试操作员用户并返回 (user, token)"""
    return await _create_user_with_token(
        async_db, "test_operator", "operator", "测试操作员", "operator@test.local"
    )


@pytest.fixture(scope="function")
async def viewer_user(async_db):
    """创建测试只读用户并返回 (user, token)"""
    return await _create_user_with_token(
        async_db, "test_viewer", "viewer", "测试只读用户", "viewer@test.local"
    )


def auth_headers(token: str) -> dict:
    """生成认证请求头"""
    return {"Authorization": f"Bearer {token}"}
