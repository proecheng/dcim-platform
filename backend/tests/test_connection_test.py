"""连接测试功能测试 — Story 1.5"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app
from gateway.adapters.base import (
    AdapterState,
    AdapterStatus,
    ConnectionResult,
)

# ============================================================
# Service 层测试
# ============================================================

SERVICE_MODULE = "app.services.connection_test"


def _make_mock_adapter():
    """创建一个标准 mock 适配器"""
    adapter = AsyncMock()
    adapter.connect = AsyncMock(return_value=True)
    adapter.disconnect = AsyncMock()
    adapter.test_connection = AsyncMock(
        return_value=ConnectionResult(
            success=True,
            message="连接成功",
            latency_ms=12.5,
            sample_data={"device_id": "test-001"},
        )
    )
    adapter.get_status = MagicMock(
        return_value=AdapterStatus(
            state=AdapterState.DISCONNECTED,
            error_message="某个错误",
        )
    )
    return adapter


def _setup_registry(mock_registry, protocol, mock_adapter):
    """配置 mock_registry 的 __contains__ 和 __getitem__"""
    mock_registry.__contains__ = lambda self, k: k == protocol
    mock_registry.__getitem__ = lambda self, k: lambda: mock_adapter


class TestConnectionTestService:
    """连接测试服务层测试"""

    @patch(f"{SERVICE_MODULE}.ADAPTER_REGISTRY")
    async def test_connection_success(self, mock_registry):
        """连接成功 — connect=True, test_connection 返回成功"""
        mock_adapter = _make_mock_adapter()
        _setup_registry(mock_registry, "modbus_tcp", mock_adapter)

        from app.services.connection_test import test_datasource_connection

        result = await test_datasource_connection("modbus_tcp", {"ip": "1.2.3.4", "port": 502})

        assert result["success"] is True
        assert result["message"] == "连接成功"
        assert result["latency_ms"] == 12.5
        assert result["sample_data"] == {"device_id": "test-001"}

    @patch(f"{SERVICE_MODULE}.ADAPTER_REGISTRY")
    async def test_connection_failure(self, mock_registry):
        """连接成功但 test_connection 返回失败"""
        mock_adapter = _make_mock_adapter()
        mock_adapter.test_connection = AsyncMock(
            return_value=ConnectionResult(
                success=False,
                message="设备无响应",
            )
        )
        _setup_registry(mock_registry, "modbus_tcp", mock_adapter)

        from app.services.connection_test import test_datasource_connection

        result = await test_datasource_connection("modbus_tcp", {"ip": "1.2.3.4", "port": 502})

        assert result["success"] is False
        assert result["message"] == "设备无响应"

    @patch(f"{SERVICE_MODULE}.ADAPTER_REGISTRY")
    async def test_connect_fails(self, mock_registry):
        """connect 返回 False — 使用 get_status 的 error_message"""
        mock_adapter = _make_mock_adapter()
        mock_adapter.connect = AsyncMock(return_value=False)
        _setup_registry(mock_registry, "modbus_tcp", mock_adapter)

        from app.services.connection_test import test_datasource_connection

        result = await test_datasource_connection("modbus_tcp", {"ip": "1.2.3.4", "port": 502})

        assert result["success"] is False
        assert result["message"] == "某个错误"

    @patch(f"{SERVICE_MODULE}.ADAPTER_REGISTRY")
    async def test_connect_fails_no_error_message(self, mock_registry):
        """connect 返回 False, get_status.error_message 为 None → 回退到 '连接失败'"""
        mock_adapter = _make_mock_adapter()
        mock_adapter.connect = AsyncMock(return_value=False)
        mock_adapter.get_status = MagicMock(
            return_value=AdapterStatus(
                state=AdapterState.DISCONNECTED,
                error_message=None,
            )
        )
        _setup_registry(mock_registry, "modbus_tcp", mock_adapter)

        from app.services.connection_test import test_datasource_connection

        result = await test_datasource_connection("modbus_tcp", {"ip": "1.2.3.4", "port": 502})

        assert result["success"] is False
        assert result["message"] == "连接失败"

    @patch(f"{SERVICE_MODULE}.asyncio.wait_for", side_effect=asyncio.TimeoutError)
    @patch(f"{SERVICE_MODULE}.ADAPTER_REGISTRY")
    async def test_timeout(self, mock_registry, mock_wait_for):
        """连接测试超时 — asyncio.wait_for 抛出 TimeoutError"""
        mock_adapter = _make_mock_adapter()
        _setup_registry(mock_registry, "modbus_tcp", mock_adapter)

        from app.services.connection_test import test_datasource_connection

        result = await test_datasource_connection("modbus_tcp", {"ip": "1.2.3.4", "port": 502})

        assert result["success"] is False
        assert "超时" in result["message"]

    async def test_unsupported_protocol(self):
        """不支持的协议类型 → ValueError"""
        from app.services.connection_test import test_datasource_connection

        with pytest.raises(ValueError, match="不支持的协议类型"):
            await test_datasource_connection("unknown_proto", {})

    @patch(f"{SERVICE_MODULE}.ADAPTER_REGISTRY")
    async def test_disconnect_called_on_success(self, mock_registry):
        """成功时 finally 中调用 disconnect"""
        mock_adapter = _make_mock_adapter()
        _setup_registry(mock_registry, "modbus_tcp", mock_adapter)

        from app.services.connection_test import test_datasource_connection

        await test_datasource_connection("modbus_tcp", {"ip": "1.2.3.4", "port": 502})

        mock_adapter.disconnect.assert_awaited_once()

    @patch(f"{SERVICE_MODULE}.ADAPTER_REGISTRY")
    async def test_disconnect_called_on_failure(self, mock_registry):
        """connect 失败时 finally 中仍调用 disconnect"""
        mock_adapter = _make_mock_adapter()
        mock_adapter.connect = AsyncMock(return_value=False)
        _setup_registry(mock_registry, "modbus_tcp", mock_adapter)

        from app.services.connection_test import test_datasource_connection

        await test_datasource_connection("modbus_tcp", {"ip": "1.2.3.4", "port": 502})

        mock_adapter.disconnect.assert_awaited_once()

    @patch(f"{SERVICE_MODULE}.asyncio.wait_for", side_effect=asyncio.TimeoutError)
    @patch(f"{SERVICE_MODULE}.ADAPTER_REGISTRY")
    async def test_disconnect_called_on_timeout(self, mock_registry, mock_wait_for):
        """超时时 finally 中仍调用 disconnect"""
        mock_adapter = _make_mock_adapter()
        _setup_registry(mock_registry, "modbus_tcp", mock_adapter)

        from app.services.connection_test import test_datasource_connection

        await test_datasource_connection("modbus_tcp", {"ip": "1.2.3.4", "port": 502})

        mock_adapter.disconnect.assert_awaited_once()

    @patch(f"{SERVICE_MODULE}.ADAPTER_REGISTRY")
    async def test_disconnect_error_suppressed(self, mock_registry):
        """disconnect 抛出异常时应被静默捕获"""
        mock_adapter = _make_mock_adapter()
        mock_adapter.disconnect = AsyncMock(side_effect=RuntimeError("断开连接失败"))
        _setup_registry(mock_registry, "modbus_tcp", mock_adapter)

        from app.services.connection_test import test_datasource_connection

        # 不应抛出异常
        result = await test_datasource_connection("modbus_tcp", {"ip": "1.2.3.4", "port": 502})
        assert result["success"] is True

    @patch(f"{SERVICE_MODULE}.ADAPTER_REGISTRY")
    async def test_exception_during_connect(self, mock_registry):
        """connect 抛出 RuntimeError → {success: False, message: str(e)}"""
        mock_adapter = _make_mock_adapter()
        mock_adapter.connect = AsyncMock(side_effect=RuntimeError("网络不可达"))
        _setup_registry(mock_registry, "modbus_tcp", mock_adapter)

        from app.services.connection_test import test_datasource_connection

        result = await test_datasource_connection("modbus_tcp", {"ip": "1.2.3.4", "port": 502})

        assert result["success"] is False
        assert "网络不可达" in result["message"]

    @patch(f"{SERVICE_MODULE}.ADAPTER_REGISTRY")
    async def test_result_is_dict(self, mock_registry):
        """返回值必须是 dict 且包含正确的 key"""
        mock_adapter = _make_mock_adapter()
        _setup_registry(mock_registry, "modbus_tcp", mock_adapter)

        from app.services.connection_test import test_datasource_connection

        result = await test_datasource_connection("modbus_tcp", {"ip": "1.2.3.4", "port": 502})

        assert isinstance(result, dict)
        assert "success" in result
        assert "message" in result
        assert "latency_ms" in result
        assert "sample_data" in result


# ============================================================
# API 端点测试
# ============================================================

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
    from app.api.deps import (
        AuthenticatedUserContext,
        SiteAccessContext,
        enforce_inventory_authorization,
        get_authenticated_user_context,
        get_site_access_context,
        require_admin,
        require_operator,
        require_viewer,
    )
    from app.models.user import User

    mock_user = User(id=1, username="test_admin", role="admin", is_active=True)
    identity = AuthenticatedUserContext(user=mock_user, jti="test-jti", expires_at=4102444800.0)
    site_context = SiteAccessContext(user_id=1, role="admin", jti="test-jti", site_ids=None)

    app.dependency_overrides[require_viewer] = lambda: mock_user
    app.dependency_overrides[require_operator] = lambda: mock_user
    app.dependency_overrides[require_admin] = lambda: mock_user
    app.dependency_overrides[enforce_inventory_authorization] = lambda: None
    app.dependency_overrides[get_authenticated_user_context] = lambda: identity
    app.dependency_overrides[get_site_access_context] = lambda: site_context

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


class TestConnectionTestAPI:
    """连接测试 API 端点测试"""

    @patch("app.api.v1.datasources.test_datasource_connection", new_callable=AsyncMock)
    @patch("app.api.v1.datasources._ADAPTER_REGISTRY")
    async def test_api_test_connection_success(self, mock_registry, mock_service, client):
        """POST /test-connection 成功"""
        mock_registry.__contains__ = lambda self, k: k == "modbus_tcp"
        mock_service.return_value = {
            "success": True,
            "message": "连接成功",
            "latency_ms": 10.0,
            "sample_data": None,
        }

        resp = await client.post(
            "/api/v1/datasources/test-connection",
            json={
                "protocol_type": "modbus_tcp",
                "connection_config": {"ip": "192.168.1.1", "port": 502},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["message"] == "连接成功"

    @patch("app.api.v1.datasources._ADAPTER_REGISTRY")
    async def test_api_test_connection_unsupported_protocol(self, mock_registry, client):
        """POST /test-connection 不支持的协议 → 400"""
        mock_registry.__contains__ = lambda self, k: False

        resp = await client.post(
            "/api/v1/datasources/test-connection",
            json={
                "protocol_type": "unknown_proto",
                "connection_config": {},
            },
        )
        assert resp.status_code == 400
        assert "不支持的协议类型" in resp.json()["detail"]

    async def test_api_test_connection_requires_operator(self):
        """POST /test-connection 无认证 → 401"""
        # 不设置 dependency_overrides，使用真实认证
        saved = dict(app.dependency_overrides)
        app.dependency_overrides.clear()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/datasources/test-connection",
                json={
                    "protocol_type": "modbus_tcp",
                    "connection_config": {},
                },
            )
        assert resp.status_code == 401

        # 恢复
        app.dependency_overrides.update(saved)

    @patch("app.api.v1.datasources.test_datasource_connection", new_callable=AsyncMock)
    @patch("app.api.v1.datasources._ADAPTER_REGISTRY")
    async def test_api_test_existing_connection_success(self, mock_registry, mock_service, client):
        """POST /{id}/test-connection 成功"""
        mock_registry.__contains__ = lambda self, k: k == "modbus_tcp"
        mock_service.return_value = {
            "success": True,
            "message": "连接成功",
            "latency_ms": 8.0,
            "sample_data": None,
        }

        # 先创建一个数据源
        create_resp = await client.post(
            "/api/v1/datasources",
            json={
                "name": "测试源",
                "protocol_type": "modbus_tcp",
                "connection_config": {"ip": "10.0.0.1", "port": 502},
            },
        )
        ds_id = create_resp.json()["id"]

        resp = await client.post(f"/api/v1/datasources/{ds_id}/test-connection")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    async def test_api_test_existing_connection_not_found(self, client):
        """POST /{id}/test-connection 数据源不存在 → 404"""
        resp = await client.post("/api/v1/datasources/99999/test-connection")
        assert resp.status_code == 404
        assert "数据源不存在" in resp.json()["detail"]

    @patch("app.api.v1.datasources._ADAPTER_REGISTRY")
    async def test_api_test_existing_connection_unsupported_adapter(self, mock_registry, client):
        """POST /{id}/test-connection 协议不在 ADAPTER_REGISTRY → 400"""
        # 创建数据源时用 KNOWN_PROTOCOL_TYPES 白名单通过
        create_resp = await client.post(
            "/api/v1/datasources",
            json={
                "name": "测试源2",
                "protocol_type": "modbus_tcp",
                "connection_config": {"ip": "10.0.0.2", "port": 502},
            },
        )
        ds_id = create_resp.json()["id"]

        # 但 _ADAPTER_REGISTRY 中不包含该协议
        mock_registry.__contains__ = lambda self, k: False

        resp = await client.post(f"/api/v1/datasources/{ds_id}/test-connection")
        assert resp.status_code == 400
        assert "不支持的协议类型" in resp.json()["detail"]

    @patch("app.api.v1.datasources.test_datasource_connection", new_callable=AsyncMock)
    @patch("app.api.v1.datasources._ADAPTER_REGISTRY")
    async def test_api_test_connection_passes_config(self, mock_registry, mock_service, client):
        """验证 API 正确传递 protocol_type 和 connection_config 到 service"""
        mock_registry.__contains__ = lambda self, k: k == "snmp_v2c"
        mock_service.return_value = {
            "success": True,
            "message": "OK",
            "latency_ms": None,
            "sample_data": None,
        }

        await client.post(
            "/api/v1/datasources/test-connection",
            json={
                "protocol_type": "snmp_v2c",
                "connection_config": {"host": "10.0.0.1", "community": "public"},
            },
        )

        mock_service.assert_awaited_once_with(
            "snmp_v2c",
            {"host": "10.0.0.1", "community": "public"},
        )

    @patch("app.api.v1.datasources.test_datasource_connection", new_callable=AsyncMock)
    @patch("app.api.v1.datasources._ADAPTER_REGISTRY")
    async def test_api_test_connection_returns_failure(self, mock_registry, mock_service, client):
        """POST /test-connection 服务返回失败结果"""
        mock_registry.__contains__ = lambda self, k: k == "modbus_tcp"
        mock_service.return_value = {
            "success": False,
            "message": "连接被拒绝",
            "latency_ms": None,
            "sample_data": None,
        }

        resp = await client.post(
            "/api/v1/datasources/test-connection",
            json={
                "protocol_type": "modbus_tcp",
                "connection_config": {"ip": "192.168.1.1", "port": 502},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert data["message"] == "连接被拒绝"

    @patch("app.api.v1.datasources.test_datasource_connection", new_callable=AsyncMock)
    @patch("app.api.v1.datasources._ADAPTER_REGISTRY")
    async def test_api_test_existing_uses_db_config(self, mock_registry, mock_service, client):
        """POST /{id}/test-connection 使用数据库中的 connection_config"""
        mock_registry.__contains__ = lambda self, k: k == "modbus_tcp"
        mock_service.return_value = {
            "success": True,
            "message": "OK",
            "latency_ms": 5.0,
            "sample_data": None,
        }

        # 创建数据源
        create_resp = await client.post(
            "/api/v1/datasources",
            json={
                "name": "DB配置测试",
                "protocol_type": "modbus_tcp",
                "connection_config": {"ip": "172.16.0.1", "port": 503},
            },
        )
        ds_id = create_resp.json()["id"]

        await client.post(f"/api/v1/datasources/{ds_id}/test-connection")

        mock_service.assert_awaited_once_with(
            "modbus_tcp",
            {"ip": "172.16.0.1", "port": 503},
        )

    async def test_api_test_existing_requires_operator(self):
        """POST /{id}/test-connection 无认证 → 401"""
        saved = dict(app.dependency_overrides)
        app.dependency_overrides.clear()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/v1/datasources/1/test-connection")
        assert resp.status_code == 401

        app.dependency_overrides.update(saved)
