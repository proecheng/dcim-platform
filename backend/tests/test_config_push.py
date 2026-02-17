"""配置下发测试 — Story 2.3"""
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.gateway import Gateway, DataSource, DataSourcePoint, ConfigPushRecord
from app.services.config_push import build_gateway_config, push_config_to_gateway
from gateway.config_receiver import ConfigReceiver


# ============================================================
# Fixtures
# ============================================================

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite://", echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


# ============================================================
# Service 层测试
# ============================================================

class TestConfigPushService:
    """配置构建与下发服务测试"""

    async def test_build_gateway_config(self, db_session):
        """构建网关配置 JSON 结构正确"""
        gw = Gateway(gateway_id="gw-cfg-001", name="配置测试网关", site_id=1)
        db_session.add(gw)
        await db_session.flush()

        ds = DataSource(
            name="数据源1", protocol_type="modbus_tcp", gateway_id=gw.id,
            connection_config={"host": "127.0.0.1", "port": 502},
            collection_interval=5, write_enabled=False, is_enabled=True,
        )
        db_session.add(ds)
        await db_session.flush()

        pt = DataSourcePoint(
            datasource_id=ds.id, point_id=100, address="40001",
            data_type="float32", scale=1.0, offset=0.0,
        )
        db_session.add(pt)
        await db_session.commit()

        config = await build_gateway_config(gw.id, db_session)

        assert config["gateway_id"] == "gw-cfg-001"
        assert len(config["datasources"]) == 1
        ds_cfg = config["datasources"][0]
        assert ds_cfg["protocol_type"] == "modbus_tcp"
        assert ds_cfg["connection_params"] == {"host": "127.0.0.1", "port": 502}
        assert len(ds_cfg["points"]) == 1
        assert ds_cfg["points"][0]["address"] == "40001"

    async def test_build_gateway_config_no_datasources(self, db_session):
        """无数据源时返回空列表"""
        gw = Gateway(gateway_id="gw-cfg-002", name="空网关", site_id=1)
        db_session.add(gw)
        await db_session.commit()

        config = await build_gateway_config(gw.id, db_session)

        assert config["gateway_id"] == "gw-cfg-002"
        assert config["datasources"] == []

    async def test_push_config_success(self, db_session):
        """MQTT 下发成功，记录状态为 delivered"""
        gw = Gateway(gateway_id="gw-push-001", name="下发测试网关", site_id=1)
        db_session.add(gw)
        await db_session.flush()

        ds = DataSource(
            name="DS1", protocol_type="modbus_tcp", gateway_id=gw.id,
            connection_config={"host": "10.0.0.1", "port": 502}, is_enabled=True,
        )
        db_session.add(ds)
        await db_session.commit()

        mock_publish = AsyncMock()
        record = await push_config_to_gateway(gw.id, mock_publish, db_session)

        assert record.status == "delivered"
        assert record.gateway_id == "gw-push-001"
        assert record.config_snapshot is not None
        assert record.error_message is None
        mock_publish.assert_called_once()

    async def test_push_config_mqtt_failure(self, db_session):
        """MQTT 下发失败，记录状态为 failed"""
        gw = Gateway(gateway_id="gw-push-002", name="失败测试网关", site_id=1)
        db_session.add(gw)
        await db_session.commit()

        mock_publish = AsyncMock(side_effect=RuntimeError("MQTT 未连接"))
        record = await push_config_to_gateway(gw.id, mock_publish, db_session)

        assert record.status == "failed"
        assert "MQTT 未连接" in record.error_message


# ============================================================
# API 测试
# ============================================================

@pytest_asyncio.fixture
async def api_client():
    """创建 API 测试客户端"""
    from app.main import app
    from app.api.deps import get_db, require_viewer, require_operator, require_admin
    from app.models.user import User

    engine = create_async_engine("sqlite+aiosqlite://", echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    mock_user = User(id=1, username="test", role="admin")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_viewer] = lambda: mock_user
    app.dependency_overrides[require_operator] = lambda: mock_user
    app.dependency_overrides[require_admin] = lambda: mock_user

    # 预填测试数据
    async with session_factory() as session:
        gw = Gateway(
            gateway_id="gw-api-cfg-001", name="API配置测试网关",
            ip_address="192.168.1.1", status="online", site_id=1,
            last_heartbeat=datetime.now(),
        )
        session.add(gw)
        await session.flush()

        ds = DataSource(
            name="数据源1", protocol_type="modbus_tcp", gateway_id=gw.id,
            connection_config={"host": "127.0.0.1", "port": 502}, is_enabled=True,
        )
        session.add(ds)
        await session.flush()

        pt = DataSourcePoint(datasource_id=ds.id, address="40001", data_type="float32")
        session.add(pt)

        # 预填配置下发记录
        rec = ConfigPushRecord(
            gateway_id="gw-api-cfg-001",
            config_snapshot={"gateway_id": "gw-api-cfg-001", "datasources": []},
            status="delivered",
        )
        session.add(rec)
        await session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client, session_factory

    app.dependency_overrides.clear()
    await engine.dispose()


class TestConfigPushAPI:
    """配置下发 API 测试"""

    async def test_push_config_api_success(self, api_client):
        """POST /push-config 成功下发"""
        client, session_factory = api_client

        async with session_factory() as session:
            result = await session.execute(
                select(Gateway).where(Gateway.gateway_id == "gw-api-cfg-001")
            )
            gw = result.scalar_one()
            gw_id = gw.id

        with patch("app.mqtt.mqtt_service") as mock_svc:
            mock_svc._client = MagicMock()  # 模拟已连接
            mock_svc.publish = AsyncMock()
            resp = await client.post(f"/api/v1/gateways/{gw_id}/push-config")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "delivered"
        assert data["gateway_id"] == "gw-api-cfg-001"

    async def test_push_config_api_mqtt_unavailable(self, api_client):
        """POST /push-config MQTT 未连接返回 503"""
        client, session_factory = api_client

        async with session_factory() as session:
            result = await session.execute(
                select(Gateway).where(Gateway.gateway_id == "gw-api-cfg-001")
            )
            gw = result.scalar_one()
            gw_id = gw.id

        with patch("app.mqtt.mqtt_service") as mock_svc:
            mock_svc._client = None  # 模拟未连接
            resp = await client.post(f"/api/v1/gateways/{gw_id}/push-config")

        assert resp.status_code == 503

    async def test_config_history_api(self, api_client):
        """GET /config-history 返回分页记录"""
        client, session_factory = api_client

        async with session_factory() as session:
            result = await session.execute(
                select(Gateway).where(Gateway.gateway_id == "gw-api-cfg-001")
            )
            gw = result.scalar_one()
            gw_id = gw.id

        resp = await client.get(f"/api/v1/gateways/{gw_id}/config-history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1
        assert data["items"][0]["status"] == "delivered"
        assert "config_snapshot" in data["items"][0]


# ============================================================
# Gateway 侧测试
# ============================================================

class TestConfigReceiver:
    """远程配置接收器测试"""

    def test_config_receiver_parse_valid(self):
        """有效 JSON 解析为 DataSourceConfig 列表"""
        receiver = ConfigReceiver(gateway_id="gw-001")
        payload = json.dumps({
            "gateway_id": "gw-001",
            "datasources": [
                {
                    "datasource_id": "ds-1",
                    "protocol_type": "modbus_tcp",
                    "connection_params": {"host": "10.0.0.1", "port": 502},
                    "collection_interval": 10,
                    "write_enabled": True,
                    "points": [
                        {
                            "point_id": "pt-1",
                            "address": "40001",
                            "data_type": "float32",
                            "scale": 1.5,
                            "offset": 0.1,
                        }
                    ],
                }
            ],
        })

        configs = receiver.handle_message(payload)

        assert len(configs) == 1
        assert configs[0].datasource_id == "ds-1"
        assert configs[0].protocol_type == "modbus_tcp"
        assert configs[0].collection_interval == 10
        assert configs[0].write_enabled is True
        assert len(configs[0].points) == 1
        assert configs[0].points[0].point_id == "pt-1"
        assert configs[0].points[0].address == "40001"
        assert configs[0].points[0].scale == 1.5

    def test_config_receiver_parse_invalid_json(self):
        """无效 JSON 返回空列表"""
        receiver = ConfigReceiver(gateway_id="gw-001")
        configs = receiver.handle_message("not-json{{{")
        assert configs == []

    def test_config_receiver_callback(self):
        """回调函数被正确调用"""
        received = []

        def on_config(configs):
            received.extend(configs)

        receiver = ConfigReceiver(
            gateway_id="gw-001",
            on_config_received=on_config,
        )
        payload = json.dumps({
            "gateway_id": "gw-001",
            "datasources": [
                {
                    "datasource_id": "ds-cb",
                    "protocol_type": "bacnet",
                    "connection_params": {},
                    "points": [],
                }
            ],
        })

        configs = receiver.handle_message(payload)

        assert len(configs) == 1
        assert len(received) == 1
        assert received[0].datasource_id == "ds-cb"
