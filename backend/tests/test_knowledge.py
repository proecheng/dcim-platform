"""知识库管理 API 测试 — 知识库文章 CRUD"""
import pytest

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

from app.core.database import Base
from app.models.operation import KnowledgeBase
from app.models.user import User
from app.api.deps import get_db, require_admin, require_operator, require_viewer


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture(scope="module")
def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        await session.execute(delete(KnowledgeBase))
        await session.commit()
        yield session


@pytest.fixture
def mock_admin():
    user = User()
    user.id = 1
    user.username = "test_admin"
    user.role = "admin"
    user.is_active = True
    return user


@pytest.fixture
async def app(db_session, mock_admin):
    from app.main import app as _app

    async def override_get_db():
        yield db_session

    async def override_require_admin():
        return mock_admin

    async def override_require_operator():
        return mock_admin

    async def override_require_viewer():
        return mock_admin

    _app.dependency_overrides[get_db] = override_get_db
    _app.dependency_overrides[require_admin] = override_require_admin
    _app.dependency_overrides[require_operator] = override_require_operator
    _app.dependency_overrides[require_viewer] = override_require_viewer
    yield _app
    _app.dependency_overrides.clear()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ============================================================
# Constants & Helpers
# ============================================================

BASE_URL = "/api/v1/operation/knowledge"

KNOWLEDGE_PAYLOAD = {
    "title": "测试文章",
    "category": "故障处理",
    "content": "这是测试内容",
    "tags": "测试,故障",
    "author": "张三",
    "is_published": True,
}


async def _create_knowledge(client: AsyncClient) -> dict:
    """通过 API 创建一篇知识库文章并返回响应 JSON"""
    resp = await client.post(BASE_URL, json=KNOWLEDGE_PAYLOAD)
    assert resp.status_code == 200
    return resp.json()


# ============================================================
# Tests
# ============================================================

@pytest.mark.anyio
async def test_create_knowledge(client):
    """POST /knowledge 创建文章，验证 title、category、view_count"""
    data = await _create_knowledge(client)
    assert data["title"] == "测试文章"
    assert data["category"] == "故障处理"
    assert data["view_count"] == 0
    assert "id" in data


@pytest.mark.anyio
async def test_list_knowledge(client):
    """GET /knowledge 返回 {code, data: {items, total}}"""
    await _create_knowledge(client)
    resp = await client.get(BASE_URL)
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert "data" in data
    assert "items" in data["data"]
    assert "total" in data["data"]
    assert data["data"]["total"] >= 1
    assert len(data["data"]["items"]) >= 1


@pytest.mark.anyio
async def test_list_knowledge_filter_category(client):
    """GET /knowledge?category=故障处理 按分类过滤"""
    await _create_knowledge(client)
    resp = await client.get(BASE_URL, params={"category": "故障处理"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["total"] >= 1
    for item in data["data"]["items"]:
        assert item["category"] == "故障处理"


@pytest.mark.anyio
async def test_list_knowledge_search_keyword(client):
    """GET /knowledge?keyword=测试 关键词搜索"""
    await _create_knowledge(client)
    resp = await client.get(BASE_URL, params={"keyword": "测试"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["total"] >= 1


@pytest.mark.anyio
async def test_get_knowledge_detail(client):
    """GET /knowledge/{id} 获取详情，验证 view_count 自增"""
    created = await _create_knowledge(client)
    article_id = created["id"]

    # 第一次访问，view_count 应为 1
    resp = await client.get(f"{BASE_URL}/{article_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == article_id
    assert data["view_count"] == 1

    # 第二次访问，view_count 应为 2
    resp = await client.get(f"{BASE_URL}/{article_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["view_count"] == 2


@pytest.mark.anyio
async def test_update_knowledge(client):
    """PUT /knowledge/{id} 更新文章标题"""
    created = await _create_knowledge(client)
    article_id = created["id"]

    resp = await client.put(f"{BASE_URL}/{article_id}", json={"title": "更新后的标题"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "更新后的标题"
    assert data["id"] == article_id


@pytest.mark.anyio
async def test_delete_knowledge(client):
    """DELETE /knowledge/{id} 删除后 GET 返回 404"""
    created = await _create_knowledge(client)
    article_id = created["id"]

    resp = await client.delete(f"{BASE_URL}/{article_id}")
    assert resp.status_code == 200

    resp = await client.get(f"{BASE_URL}/{article_id}")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_delete_knowledge_not_found(client):
    """DELETE /knowledge/99999 不存在返回 404"""
    resp = await client.delete(f"{BASE_URL}/99999")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_list_knowledge_pagination(client):
    """GET /knowledge?page=1&page_size=1 分页验证"""
    # 创建两篇文章
    await _create_knowledge(client)
    payload2 = {**KNOWLEDGE_PAYLOAD, "title": "第二篇文章"}
    resp = await client.post(BASE_URL, json=payload2)
    assert resp.status_code == 200

    resp = await client.get(BASE_URL, params={"page": 1, "page_size": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["total"] >= 2
    assert len(data["data"]["items"]) == 1


@pytest.mark.anyio
async def test_get_knowledge_not_found(client):
    """GET /knowledge/99999 不存在返回 404"""
    resp = await client.get(f"{BASE_URL}/99999")
    assert resp.status_code == 404
