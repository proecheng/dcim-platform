"""网关状态监控测试 — Story 2.2"""
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.gateway import Gateway, DataSource, DataSourcePoint, GatewayEvent
from app.services.gateway_monitor import (
    record_status_change,
    check_resource_warnings,
    RESOURCE_WARNING_COOLDOWN,
)
from app.services.gateway_registration import (
    handle_gateway_status,
    check_gateway_heartbeats,
    HEARTBEAT_TIMEOUT_SECONDS,
)


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

class TestGatewayMonitorService:
    """网关监控服务测试"""

    async def test_record_status_change(self, db_session):
        """记录状态变更事件"""
        await record_status_change("gw-001", "offline", "online", db_session)
        await db_session.commit()

        result = await db_session.execute(
            select(GatewayEvent).where(GatewayEvent.gateway_id == "gw-001")
        )
        event = result.scalar_one()
        assert event.event_type == "status_change"
        assert event.old_status == "offline"
        assert event.new_status == "online"

    async def test_check_resource_warnings_over_threshold(self, db_session):
        """CPU 超阈值触发资源告警"""
        await check_resource_warnings("gw-002", {"cpu": 95.0, "mem": 50.0}, db_session)
        await db_session.commit()

        result = await db_session.execute(
            select(GatewayEvent).where(
                GatewayEvent.gateway_id == "gw-002",
                GatewayEvent.event_type == "resource_warning",
            )
        )
        event = result.scalar_one()
        assert "cpu" in event.detail["warnings"]
        assert event.detail["warnings"]["cpu"] == 95.0

    async def test_check_resource_warnings_under_threshold(self, db_session):
        """资源未超阈值不产生事件"""
        await check_resource_warnings("gw-003", {"cpu": 50.0, "mem": 60.0, "disk": 30.0}, db_session)
        await db_session.commit()

        result = await db_session.execute(
            select(GatewayEvent).where(GatewayEvent.gateway_id == "gw-003")
        )
        assert result.scalar_one_or_none() is None

    async def test_check_resource_warnings_cooldown_dedup(self, db_session):
        """冷却期内不重复告警"""
        await check_resource_warnings("gw-004", {"cpu": 95.0}, db_session)
        await db_session.commit()

        # 第二次调用应被去重
        await check_resource_warnings("gw-004", {"cpu": 96.0}, db_session)
        await db_session.commit()

        result = await db_session.execute(
            select(GatewayEvent).where(
                GatewayEvent.gateway_id == "gw-004",
                GatewayEvent.event_type == "resource_warning",
            )
        )
        events = result.scalars().all()
        assert len(events) == 1

    async def test_check_resource_warnings_after_cooldown(self, db_session):
        """冷却期过后可再次告警"""
        await check_resource_warnings("gw-005", {"cpu": 95.0}, db_session)
        await db_session.commit()

        # 将第一条事件的 created_at 改为 6 分钟前
        result = await db_session.execute(
            select(GatewayEvent).where(GatewayEvent.gateway_id == "gw-005")
        )
        event = result.scalar_one()
        event.created_at = datetime.now() - timedelta(seconds=RESOURCE_WARNING_COOLDOWN + 60)
        await db_session.commit()

        # 再次调用应产生新事件
        await check_resource_warnings("gw-005", {"mem": 92.0}, db_session)
        await db_session.commit()

        result = await db_session.execute(
            select(GatewayEvent).where(
                GatewayEvent.gateway_id == "gw-005",
                GatewayEvent.event_type == "resource_warning",
            )
        )
        events = result.scalars().all()
        assert len(events) == 2


# ============================================================
# 集成测试
# ============================================================

class TestGatewayMonitorIntegration:
    """网关监控集成测试"""

    async def test_handle_gateway_status_new_records_event(self, db_session):
        """新网关注册产生 status_change 事件 (none→online)"""
        payload = {
            "gw_id": "gw-int-001",
            "name": "集成测试网关",
            "ip": "10.0.0.1",
            "cpu": 30.0,
            "mem": 40.0,
            "disk": 20.0,
        }
        await handle_gateway_status(payload, db_session)

        result = await db_session.execute(
            select(GatewayEvent).where(
                GatewayEvent.gateway_id == "gw-int-001",
                GatewayEvent.event_type == "status_change",
            )
        )
        event = result.scalar_one()
        assert event.old_status == "none"
        assert event.new_status == "online"

    async def test_handle_gateway_status_offline_to_online_records_event(self, db_session):
        """离线网关上线产生 status_change 事件"""
        gw = Gateway(
            gateway_id="gw-int-002",
            name="离线网关",
            ip_address="10.0.0.2",
            status="offline",
            last_heartbeat=datetime.now() - timedelta(minutes=5),
        )
        db_session.add(gw)
        await db_session.commit()

        payload = {
            "gw_id": "gw-int-002",
            "name": "离线网关",
            "ip": "10.0.0.2",
            "cpu": 30.0,
        }
        await handle_gateway_status(payload, db_session)

        result = await db_session.execute(
            select(GatewayEvent).where(
                GatewayEvent.gateway_id == "gw-int-002",
                GatewayEvent.event_type == "status_change",
            )
        )
        event = result.scalar_one()
        assert event.old_status == "offline"
        assert event.new_status == "online"

    async def test_check_heartbeats_records_offline_event(self, db_session):
        """心跳超时产生 status_change 事件 (online→offline)"""
        gw = Gateway(
            gateway_id="gw-int-003",
            name="超时网关",
            status="online",
            last_heartbeat=datetime.now() - timedelta(seconds=HEARTBEAT_TIMEOUT_SECONDS + 10),
        )
        db_session.add(gw)
        await db_session.commit()

        count = await check_gateway_heartbeats(db_session)
        assert count == 1

        result = await db_session.execute(
            select(GatewayEvent).where(
                GatewayEvent.gateway_id == "gw-int-003",
                GatewayEvent.event_type == "status_change",
            )
        )
        event = result.scalar_one()
        assert event.old_status == "online"
        assert event.new_status == "offline"


# ============================================================
# API 测试
# ============================================================

@pytest_asyncio.fixture
async def api_client():
    """创建 API 测试客户端"""
    from app.main import app
    from app.api.deps import get_db, require_viewer, require_operator, require_admin, get_current_user, get_user_site_ids
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
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_user_site_ids] = lambda: None

    # 预填测试数据
    async with session_factory() as session:
        gw1 = Gateway(
            gateway_id="gw-api-001", name="测试网关A", ip_address="192.168.1.1",
            status="online", last_heartbeat=datetime.now(),
        )
        gw2 = Gateway(
            gateway_id="gw-api-002", name="测试网关B", ip_address="10.0.0.1",
            status="offline",
        )
        session.add_all([gw1, gw2])
        await session.commit()

        # 为 gw1 添加数据源和点位
        ds = DataSource(
            name="数据源1", protocol_type="modbus_tcp", gateway_id=gw1.id,
            connection_config={"host": "127.0.0.1", "port": 502},
        )
        session.add(ds)
        await session.commit()

        pt1 = DataSourcePoint(datasource_id=ds.id, address="40001")
        pt2 = DataSourcePoint(datasource_id=ds.id, address="40002")
        session.add_all([pt1, pt2])

        # 添加事件
        evt = GatewayEvent(
            gateway_id="gw-api-001", event_type="status_change",
            old_status="offline", new_status="online",
        )
        session.add(evt)
        await session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client, session_factory

    app.dependency_overrides.clear()
    await engine.dispose()


class TestGatewayMonitorAPI:
    """网关监控 API 测试"""

    async def test_gateway_summary_api(self, api_client):
        """GET /summary 返回正确计数"""
        client, _ = api_client
        resp = await client.get("/api/v1/gateways/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["online"] == 1
        assert data["offline"] == 1

    async def test_gateway_detail_with_counts(self, api_client):
        """GET /{id} 返回 datasource_count 和 point_count"""
        client, session_factory = api_client
        # 查找 gw1 的 id
        async with session_factory() as session:
            result = await session.execute(
                select(Gateway).where(Gateway.gateway_id == "gw-api-001")
            )
            gw = result.scalar_one()
            gw_id = gw.id

        resp = await client.get(f"/api/v1/gateways/{gw_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["datasource_count"] == 1
        assert data["point_count"] == 2

    async def test_gateway_events_api(self, api_client):
        """GET /{id}/events 返回分页事件"""
        client, session_factory = api_client
        async with session_factory() as session:
            result = await session.execute(
                select(Gateway).where(Gateway.gateway_id == "gw-api-001")
            )
            gw = result.scalar_one()
            gw_id = gw.id

        resp = await client.get(f"/api/v1/gateways/{gw_id}/events")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1
        assert data["items"][0]["event_type"] == "status_change"

    async def test_gateway_list_keyword_search(self, api_client):
        """GET /gateways?keyword=xxx 按名称/IP 过滤"""
        client, _ = api_client

        # 按名称搜索
        resp = await client.get("/api/v1/gateways", params={"keyword": "网关A"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "测试网关A"

        # 按 IP 搜索
        resp = await client.get("/api/v1/gateways", params={"keyword": "10.0.0"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["gateway_id"] == "gw-api-002"
