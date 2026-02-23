"""MQTT 数据上报链路测试 — Story 2.5"""

import json
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.database import Base
from app.models.gateway import PointDataLatest
from app.services.point_data import handle_point_data
from gateway.adapters.base import NormalizedReading, DataQuality
from gateway.mqtt_client import format_point_data, GatewayMqttClient


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite://", echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


# ---- 1. format_point_data 格式验证 ----


def test_format_point_data():
    readings = [
        NormalizedReading(
            point_id="p001",
            value=25.6,
            raw_value=25.6,
            quality=DataQuality.NORMAL,
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            datasource_id="ds-1",
        ),
    ]
    msg = format_point_data("gw-001", readings)
    assert msg["gw_id"] == "gw-001"
    assert len(msg["points"]) == 1
    assert msg["points"][0]["id"] == "p001"
    assert msg["points"][0]["v"] == 25.6
    assert msg["points"][0]["q"] == 0
    assert "ts" in msg


# ---- 2. format_point_data 空列表 ----


def test_format_point_data_empty():
    msg = format_point_data("gw-001", [])
    assert msg["points"] == []


# ---- 3. 连接状态下 publish 调用 client ----


async def test_gateway_mqtt_client_publish_connected():
    client = GatewayMqttClient(gateway_id="gw-001")
    mock_mqtt = AsyncMock()
    client.set_connected(mock_mqtt)
    await client.publish("topic", "payload")
    mock_mqtt.publish.assert_called_once_with("topic", "payload", qos=1)


# ---- 4. 断开状态下 publish 降级到缓存 ----


async def test_gateway_mqtt_client_publish_disconnected_with_cache():
    mock_cache = AsyncMock()
    client = GatewayMqttClient(gateway_id="gw-001", cache=mock_cache)
    await client.publish("topic", "payload")
    mock_cache.enqueue.assert_called_once_with("topic", "payload")


# ---- 5. 新点位插入 ----


async def test_handle_point_data_new_points(db_session):
    payload = {
        "gw_id": "gw-001",
        "ts": int(time.time()),
        "points": [
            {"id": "p001", "v": 25.6, "q": 0, "t": int(time.time())},
            {"id": "p002", "v": 1, "q": 0, "t": int(time.time())},
        ],
    }
    count = await handle_point_data(payload, db_session)
    assert count == 2
    result = await db_session.execute(select(PointDataLatest))
    all_records = result.scalars().all()
    assert len(all_records) == 2


# ---- 6. 已有点位更新 ----


async def test_handle_point_data_update_existing(db_session):
    # First insert
    payload1 = {"gw_id": "gw-001", "points": [{"id": "p001", "v": 10.0, "q": 0, "t": int(time.time())}]}
    await handle_point_data(payload1, db_session)
    # Update
    payload2 = {"gw_id": "gw-001", "points": [{"id": "p001", "v": 20.0, "q": 0, "t": int(time.time())}]}
    await handle_point_data(payload2, db_session)
    result = await db_session.execute(select(PointDataLatest).where(PointDataLatest.point_id == "p001"))
    record = result.scalar_one()
    assert record.value == "20.0"


# ---- 7. 无效 payload 返回 0 ----


async def test_handle_point_data_invalid_payload(db_session):
    count = await handle_point_data({"points": []}, db_session)
    assert count == 0


# ---- 8. MqttService data topic 路由 ----


async def test_mqtt_service_data_topic_routing():
    """验证 MqttService 将 data topic 路由到 handle_point_data"""
    from app.mqtt.client import MqttService

    service = MqttService()
    message = MagicMock()
    message.topic = "dcim/1/gw/gw-001/data"
    message.payload = json.dumps({"gw_id": "gw-001", "points": [{"id": "p1", "v": 1.0, "q": 0, "t": 1000}]}).encode()

    with patch("app.mqtt.client.handle_point_data", new_callable=AsyncMock) as mock_handler:
        with patch("app.mqtt.client.async_session") as mock_session_factory:
            mock_db = AsyncMock()
            mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            await service._handle_message(message)
            mock_handler.assert_called_once()
