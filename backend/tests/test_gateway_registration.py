"""网关自动注册测试 — Story 2.1"""

from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.gateway import Gateway
from app.services.gateway_registration import (
    HEARTBEAT_TIMEOUT_SECONDS,
    check_gateway_heartbeats,
    handle_gateway_status,
    sign_gateway_payload,
    verify_gateway_signature,
)
from app.mqtt.client import MqttService
from gateway.status_reporter import StatusReporter


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
# StatusReporter 测试
# ============================================================


class TestStatusReporter:
    """StatusReporter 单元测试"""

    @patch("gateway.status_reporter._HAS_PSUTIL", True)
    @patch("gateway.status_reporter.psutil", create=True)
    def test_collect_metrics_with_psutil(self, mock_psutil):
        """有 psutil 时返回 cpu/mem/disk 浮点数"""
        mock_psutil.cpu_percent.return_value = 45.2
        mock_psutil.virtual_memory.return_value = MagicMock(percent=62.1)
        mock_psutil.disk_usage.return_value = MagicMock(percent=38.5)
        reporter = StatusReporter(gateway_id="gw-001")
        metrics = reporter.collect_metrics()
        assert metrics["cpu"] == 45.2
        assert metrics["mem"] == 62.1
        assert metrics["disk"] == 38.5

    @patch("gateway.status_reporter._HAS_PSUTIL", False)
    def test_collect_metrics_without_psutil(self):
        """无 psutil 时返回全 None"""
        reporter = StatusReporter(gateway_id="gw-001")
        metrics = reporter.collect_metrics()
        assert metrics["cpu"] is None
        assert metrics["mem"] is None
        assert metrics["disk"] is None

    @patch("gateway.status_reporter._HAS_PSUTIL", False)
    def test_build_status_message(self):
        """构建消息包含所有必需字段"""
        reporter = StatusReporter(
            gateway_id="gw-001",
            name="测试网关",
            version="2.0.0",
            capabilities=["modbus_tcp"],
        )
        msg = reporter.build_status_message()
        assert msg["gw_id"] == "gw-001"
        assert msg["name"] == "测试网关"
        assert "ip" in msg
        assert msg["version"] == "2.0.0"
        assert msg["capabilities"] == ["modbus_tcp"]
        assert "cpu" in msg
        assert "mem" in msg
        assert "disk" in msg
        assert "ts" in msg
        assert isinstance(msg["ts"], int)
        assert verify_gateway_signature(msg, msg["signature"])

    async def test_status_reporter_stop_without_start(self):
        """未启动时调用 stop 不应抛出异常"""
        reporter = StatusReporter(gateway_id="gw-001")
        await reporter.stop()  # 不应抛出


# ============================================================
# gateway_registration 服务测试
# ============================================================


class TestGatewayRegistration:
    """网关自动注册服务测试"""

    async def test_handle_gateway_status_new_gateway(self, db_session):
        """新网关自动注册"""
        payload = {
            "gw_id": "gw-new-001",
            "name": "新网关",
            "ip": "192.168.1.100",
            "version": "1.0.0",
            "capabilities": ["modbus_tcp"],
            "cpu": 30.0,
            "mem": 50.0,
            "disk": 20.0,
        }
        payload["signature"] = sign_gateway_payload(payload)
        await handle_gateway_status(payload, db_session)

        result = await db_session.execute(select(Gateway).where(Gateway.gateway_id == "gw-new-001"))
        gw = result.scalar_one()
        assert gw.status == "online"
        assert gw.name == "新网关"
        assert gw.ip_address == "192.168.1.100"
        assert gw.last_heartbeat is not None

    async def test_handle_gateway_status_existing_gateway(self, db_session):
        """已有网关更新心跳"""
        # 先创建一个网关
        gw = Gateway(
            gateway_id="gw-exist-001",
            name="旧名称",
            ip_address="10.0.0.1",
            status="offline",
            last_heartbeat=datetime.now() - timedelta(minutes=5),
        )
        db_session.add(gw)
        await db_session.commit()

        payload = {
            "gw_id": "gw-exist-001",
            "name": "新名称",
            "ip": "10.0.0.2",
            "version": "2.0.0",
            "cpu": 55.0,
            "mem": 70.0,
            "disk": 40.0,
        }
        payload["signature"] = sign_gateway_payload(payload)
        await handle_gateway_status(payload, db_session)

        result = await db_session.execute(select(Gateway).where(Gateway.gateway_id == "gw-exist-001"))
        updated = result.scalar_one()
        assert updated.status == "online"
        assert updated.name == "新名称"
        assert updated.ip_address == "10.0.0.2"
        assert updated.version == "2.0.0"
        assert updated.cpu_usage == 55.0
        assert updated.memory_usage == 70.0
        assert updated.disk_usage == 40.0

    async def test_handle_gateway_status_invalid_payload(self, db_session):
        """缺少 gw_id 不崩溃"""
        payload = {"name": "无ID网关"}
        await handle_gateway_status(payload, db_session)

        result = await db_session.execute(select(Gateway))
        assert result.scalars().all() == []

    async def test_handle_gateway_status_capabilities_list(self, db_session):
        """capabilities 列表正确存储"""
        payload = {
            "gw_id": "gw-cap-001",
            "name": "能力网关",
            "capabilities": ["modbus_tcp", "bacnet"],
        }
        payload["signature"] = sign_gateway_payload(payload)
        await handle_gateway_status(payload, db_session)

        result = await db_session.execute(select(Gateway).where(Gateway.gateway_id == "gw-cap-001"))
        gw = result.scalar_one()
        assert gw.capabilities == ["modbus_tcp", "bacnet"]

    async def test_check_heartbeats_stale_gateway(self, db_session):
        """心跳超时的网关标记为 offline"""
        gw = Gateway(
            gateway_id="gw-stale-001",
            name="过期网关",
            status="online",
            last_heartbeat=datetime.now() - timedelta(seconds=HEARTBEAT_TIMEOUT_SECONDS + 10),
        )
        db_session.add(gw)
        await db_session.commit()

        count = await check_gateway_heartbeats(db_session)
        assert count == 1

        result = await db_session.execute(select(Gateway).where(Gateway.gateway_id == "gw-stale-001"))
        updated = result.scalar_one()
        assert updated.status == "offline"

    async def test_check_heartbeats_fresh_gateway(self, db_session):
        """心跳正常的网关保持 online"""
        gw = Gateway(
            gateway_id="gw-fresh-001",
            name="正常网关",
            status="online",
            last_heartbeat=datetime.now(),
        )
        db_session.add(gw)
        await db_session.commit()

        count = await check_gateway_heartbeats(db_session)
        assert count == 0

        result = await db_session.execute(select(Gateway).where(Gateway.gateway_id == "gw-fresh-001"))
        gw = result.scalar_one()
        assert gw.status == "online"

    async def test_check_heartbeats_null_last_heartbeat(self, db_session):
        """last_heartbeat 为 NULL 的在线网关标记为 offline"""
        gw = Gateway(
            gateway_id="gw-null-hb",
            name="无心跳网关",
            status="online",
            last_heartbeat=None,
        )
        db_session.add(gw)
        await db_session.commit()

        count = await check_gateway_heartbeats(db_session)
        assert count == 1

        result = await db_session.execute(select(Gateway).where(Gateway.gateway_id == "gw-null-hb"))
        updated = result.scalar_one()
        assert updated.status == "offline"


# ============================================================
# MqttService 测试
# ============================================================


class TestMqttService:
    """MqttService 单元测试"""

    def test_parse_topic_valid(self):
        """有效 topic 解析"""
        result = MqttService.parse_topic("dcim/1/gw/gw-001/status")
        assert result == {"site_id": "1", "gw_id": "gw-001", "type": "status"}

    def test_parse_topic_invalid(self):
        """无效 topic 返回 None"""
        result = MqttService.parse_topic("invalid/topic")
        assert result is None


# ============================================================
# Settings 测试
# ============================================================


class TestMqttSettings:
    """MQTT 配置默认值测试"""

    def test_mqtt_settings_defaults(self):
        """Settings 包含 MQTT 默认配置"""
        from app.core.config import Settings

        s = Settings()
        assert s.mqtt_enabled is True
        assert s.mqtt_host == "localhost"
        assert s.mqtt_port == 1883
        assert s.mqtt_username == ""
        assert s.mqtt_password == ""
        assert s.mqtt_client_id == "dcim-backend"
