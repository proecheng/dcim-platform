"""数据源 API CRUD 测试 — Story 1.1 Task 7.7"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.api.deps import get_db
from app.main import app


# 使用内存 SQLite 异步引擎
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_db():
    """创建测试用异步数据库"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    yield session_factory
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(async_db):
    """创建测试 HTTP 客户端（跳过认证）"""
    # 覆盖认证依赖
    from app.api.deps import require_viewer, require_operator, require_admin, get_current_user, get_user_site_ids
    from app.models.user import User

    mock_user = User(id=1, username="test_admin", role="admin", is_active=True)

    app.dependency_overrides[require_viewer] = lambda: mock_user
    app.dependency_overrides[require_operator] = lambda: mock_user
    app.dependency_overrides[require_admin] = lambda: mock_user
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_user_site_ids] = lambda: None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


class TestDataSourceAPI:
    """数据源 CRUD API 测试"""

    @pytest.mark.asyncio
    async def test_create_datasource(self, client: AsyncClient):
        """创建数据源"""
        payload = {
            "name": "测试数据源",
            "protocol_type": "modbus_tcp",
            "connection_config": {"ip": "192.168.1.1", "port": 502},
            "collection_interval": 10,
        }
        resp = await client.post("/api/v1/datasources", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "测试数据源"
        assert data["protocol_type"] == "modbus_tcp"
        assert data["collection_interval"] == 10
        assert data["status"] == "disconnected"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_list_datasources(self, client: AsyncClient):
        """获取数据源列表"""
        # 先创建一个
        await client.post("/api/v1/datasources", json={
            "name": "ds-list-test",
            "protocol_type": "snmp_v2c",
            "connection_config": {"community": "public"},
        })
        resp = await client.get("/api/v1/datasources")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    @pytest.mark.asyncio
    async def test_get_datasource(self, client: AsyncClient):
        """获取数据源详情"""
        create_resp = await client.post("/api/v1/datasources", json={
            "name": "ds-get-test",
            "protocol_type": "modbus_tcp",
            "connection_config": {"ip": "10.0.0.1"},
        })
        ds_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/datasources/{ds_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "ds-get-test"

    @pytest.mark.asyncio
    async def test_get_datasource_not_found(self, client: AsyncClient):
        """获取不存在的数据源返回 404"""
        resp = await client.get("/api/v1/datasources/99999")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_datasource(self, client: AsyncClient):
        """更新数据源"""
        create_resp = await client.post("/api/v1/datasources", json={
            "name": "ds-update-test",
            "protocol_type": "modbus_tcp",
            "connection_config": {"ip": "10.0.0.1"},
        })
        ds_id = create_resp.json()["id"]

        resp = await client.put(f"/api/v1/datasources/{ds_id}", json={
            "name": "ds-updated",
            "collection_interval": 30,
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "ds-updated"
        assert resp.json()["collection_interval"] == 30

    @pytest.mark.asyncio
    async def test_delete_datasource(self, client: AsyncClient):
        """删除数据源"""
        create_resp = await client.post("/api/v1/datasources", json={
            "name": "ds-delete-test",
            "protocol_type": "modbus_tcp",
            "connection_config": {"ip": "10.0.0.1"},
        })
        ds_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/v1/datasources/{ds_id}")
        assert resp.status_code == 200

        # 确认已删除
        resp = await client.get(f"/api/v1/datasources/{ds_id}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_datasource_invalid_protocol(self, client: AsyncClient):
        """创建数据源时使用未知协议类型返回 400"""
        payload = {
            "name": "bad-proto-test",
            "protocol_type": "foobar",
            "connection_config": {"ip": "10.0.0.1"},
        }
        resp = await client.post("/api/v1/datasources", json=payload)
        assert resp.status_code == 400
        assert "不支持的协议类型" in resp.json()["detail"]


class TestGatewayAPI:
    """网关 CRUD API 测试"""

    @pytest.mark.asyncio
    async def test_create_gateway(self, client: AsyncClient):
        """创建网关"""
        payload = {
            "gateway_id": "gw-create-test",
            "name": "测试网关",
            "ip_address": "192.168.1.100",
        }
        resp = await client.post("/api/v1/gateways", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["gateway_id"] == "gw-create-test"
        assert data["name"] == "测试网关"
        assert data["status"] == "offline"

    @pytest.mark.asyncio
    async def test_create_duplicate_gateway(self, client: AsyncClient):
        """创建重复 gateway_id 返回 400"""
        payload = {
            "gateway_id": "gw-dup",
            "name": "网关1",
        }
        await client.post("/api/v1/gateways", json=payload)
        resp = await client.post("/api/v1/gateways", json={
            "gateway_id": "gw-dup",
            "name": "网关2",
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_list_gateways(self, client: AsyncClient):
        """获取网关列表"""
        await client.post("/api/v1/gateways", json={
            "gateway_id": "gw-list",
            "name": "列表测试",
        })
        resp = await client.get("/api/v1/gateways")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_delete_gateway(self, client: AsyncClient):
        """删除网关"""
        create_resp = await client.post("/api/v1/gateways", json={
            "gateway_id": "gw-del",
            "name": "删除测试",
        })
        gw_id = create_resp.json()["id"]
        resp = await client.delete(f"/api/v1/gateways/{gw_id}")
        assert resp.status_code == 200
