"""Story 35.3: 网关离线告警与前端展示 — 告警创建/恢复/API 测试"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from app.core.database import Base
from app.models.gateway import DataSource
from app.models.alarm import Alarm
from app.services.gateway_monitor import check_mstp_gateway_health, _probe_gateway
from app.services.communication_monitor import check_communication_status
from app.services.datasource_alarm import (
    create_datasource_alarm,
    resolve_datasource_alarm,
    resolve_datasource_alarms_batch,
)


@pytest.fixture
async def db_session():
    """每个测试创建独立的内存数据库"""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


def _mock_adapter_factory(connect_result: bool = False, test_success: bool = False):
    """创建 mock BacnetIpAdapter"""
    mock_cls = MagicMock()
    mock_inst = MagicMock()
    mock_inst.connect = AsyncMock(return_value=connect_result)
    mock_inst.disconnect = AsyncMock()
    if connect_result:
        result = MagicMock()
        result.success = test_success
        mock_inst.test_connection = AsyncMock(return_value=result)
    else:
        mock_inst.test_connection = AsyncMock()
    mock_cls.return_value = mock_inst
    return mock_cls


async def _create_gateway_with_children(session, *, gw_status="disconnected",
                                        gw_failures=0, child_count=2,
                                        child_status="disconnected",
                                        child_failures=0):
    """创建网关 DataSource 及子设备"""
    gw = DataSource(
        name="BACnet 网关",
        protocol_type="bacnet_ip",
        connection_config={"host": "192.168.1.1", "port": 47808, "device_instance": 1000},
        status=gw_status,
        is_enabled=False,
        consecutive_failures=gw_failures,
        retry_max_failures=3,
    )
    session.add(gw)
    await session.flush()

    children = []
    for i in range(child_count):
        child = DataSource(
            name=f"MS/TP 设备 {i + 1}",
            protocol_type="bacnet_mstp",
            connection_config={"host": "192.168.1.1", "mac_address": 10 + i},
            status=child_status,
            is_enabled=True,
            consecutive_failures=child_failures,
            retry_max_failures=5,
            parent_datasource_id=gw.id,
        )
        session.add(child)
        children.append(child)
    await session.flush()
    return gw, children


# ─── 5.1 网关离线告警创建 ─────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.services.gateway_monitor.BacnetIpAdapter")
async def test_gateway_offline_alarm_created(MockAdapter, db_session):
    """网关 consecutive_failures >= 阈值 → 创建 mstp_gateway_offline 告警（major）"""
    MockAdapter.side_effect = lambda: _mock_adapter_factory(False, False).return_value
    gw, children = await _create_gateway_with_children(db_session, gw_failures=2)

    # 第3次失败达到阈值(retry_max_failures=3)
    broadcasts = await _probe_gateway(gw, db_session)
    await db_session.commit()

    # 验证告警已创建
    result = await db_session.execute(
        select(Alarm).where(Alarm.source == f"datasource:{gw.id}", Alarm.status == "active")
    )
    alarm = result.scalar_one_or_none()
    assert alarm is not None
    assert alarm.alarm_type == "mstp_gateway_offline"
    assert alarm.alarm_level == "major"
    assert alarm.point_id is None
    assert "影响 2 台 MS/TP 设备" in alarm.alarm_message
    assert "MS/TP 设备 1" in alarm.alarm_message

    # 验证有 WebSocket 推送消息
    assert any(b.get("action") == "new" for b in broadcasts)


# ─── 5.2 设备离线告警创建 ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_device_offline_alarm_created(db_session):
    """设备 consecutive_failures >= 阈值且网关在线 → 创建 mstp_device_offline 告警（minor）"""
    gw, children = await _create_gateway_with_children(
        db_session, gw_status="connected", child_failures=5
    )
    await db_session.commit()

    alarm = await create_datasource_alarm(
        db_session, children[0], "mstp_device_offline", "minor",
        f"MS/TP 设备 {children[0].name} 离线（网关正常）",
    )
    await db_session.commit()

    assert alarm is not None
    assert alarm.alarm_type == "mstp_device_offline"
    assert alarm.alarm_level == "minor"
    assert alarm.source == f"datasource:{children[0].id}"


# ─── 5.3 网关恢复自动关闭告警 ─────────────────────────────────────

@pytest.mark.asyncio
@patch("app.services.gateway_monitor.BacnetIpAdapter")
async def test_gateway_recovery_resolves_alarm(MockAdapter, db_session):
    """网关恢复 → 关闭 active 告警（status=resolved, resolve_type=auto）"""
    # 先创建网关离线状态 + 告警
    MockAdapter.side_effect = lambda: _mock_adapter_factory(False, False).return_value
    gw, children = await _create_gateway_with_children(
        db_session, gw_status="gateway_offline", gw_failures=5
    )
    alarm = Alarm(
        alarm_no="ALM20260321000001test01",
        point_id=None,
        alarm_level="major",
        alarm_type="mstp_gateway_offline",
        alarm_message="测试告警",
        source=f"datasource:{gw.id}",
        status="active",
        data_source="bridge",
    )
    db_session.add(alarm)
    await db_session.flush()

    # 网关恢复
    MockAdapter.side_effect = lambda: _mock_adapter_factory(True, True).return_value
    broadcasts = await _probe_gateway(gw, db_session)
    await db_session.commit()

    # 验证告警已关闭
    result = await db_session.execute(
        select(Alarm).where(Alarm.source == f"datasource:{gw.id}")
    )
    resolved_alarm = result.scalar_one()
    assert resolved_alarm.status == "resolved"
    assert resolved_alarm.resolve_type == "auto"
    assert resolved_alarm.resolved_at is not None

    # 验证有 resolve 推送
    assert any(b.get("action") == "resolve" for b in broadcasts)


# ─── 5.4 设备恢复自动关闭告警 ─────────────────────────────────────

@pytest.mark.asyncio
async def test_device_recovery_resolves_alarm(db_session):
    """设备恢复（consecutive_failures=0）→ 关闭 device_offline 告警"""
    gw, children = await _create_gateway_with_children(
        db_session, gw_status="connected", child_status="device_offline",
    )
    # 创建一条 active 告警
    alarm = Alarm(
        alarm_no="ALM20260321000002test02",
        point_id=None,
        alarm_level="minor",
        alarm_type="mstp_device_offline",
        alarm_message="设备离线",
        source=f"datasource:{children[0].id}",
        status="active",
        data_source="bridge",
    )
    db_session.add(alarm)
    await db_session.commit()

    # 恢复告警
    now = datetime.now()
    count = await resolve_datasource_alarm(db_session, children[0].id, now)
    await db_session.commit()

    assert count == 1
    result = await db_session.execute(
        select(Alarm).where(Alarm.source == f"datasource:{children[0].id}")
    )
    resolved = result.scalar_one()
    assert resolved.status == "resolved"
    assert resolved.duration_seconds is not None


# ─── 5.5 API parent_datasource_id 过滤 ───────────────────────────

@pytest.mark.asyncio
async def test_datasource_api_parent_filter(db_session):
    """parent_datasource_id 查询参数过滤子设备"""
    gw, children = await _create_gateway_with_children(db_session, child_count=3)
    # 创建一个无父设备的数据源
    standalone = DataSource(
        name="独立设备",
        protocol_type="modbus_tcp",
        connection_config={"host": "192.168.1.2"},
        status="connected",
        is_enabled=True,
    )
    db_session.add(standalone)
    await db_session.commit()

    # 用 parent_datasource_id 过滤
    result = await db_session.execute(
        select(DataSource).where(DataSource.parent_datasource_id == gw.id)
    )
    filtered = result.scalars().all()
    assert len(filtered) == 3
    assert all(ds.parent_datasource_id == gw.id for ds in filtered)


# ─── 5.6 重复告警幂等测试 ────────────────────────────────────────

@pytest.mark.asyncio
async def test_alarm_idempotent(db_session):
    """已有 active 告警时，create_datasource_alarm 跳过创建"""
    gw, _ = await _create_gateway_with_children(db_session)
    await db_session.commit()

    # 第一次创建
    alarm1 = await create_datasource_alarm(
        db_session, gw, "mstp_gateway_offline", "major", "测试告警",
    )
    assert alarm1 is not None

    # 第二次创建 — 应返回 None（幂等）
    alarm2 = await create_datasource_alarm(
        db_session, gw, "mstp_gateway_offline", "major", "测试告警",
    )
    assert alarm2 is None

    # 验证只有一条告警
    result = await db_session.execute(
        select(Alarm).where(Alarm.source == f"datasource:{gw.id}", Alarm.status == "active")
    )
    assert len(result.scalars().all()) == 1


# ─── 5.7 网关恢复级联关闭子设备告警 ──────────────────────────────

@pytest.mark.asyncio
async def test_gateway_recovery_batch_resolves_children(db_session):
    """网关恢复时，批量关闭所有子设备的 active 告警"""
    gw, children = await _create_gateway_with_children(
        db_session, gw_status="gateway_offline", child_count=3,
        child_status="gateway_offline",
    )
    # 为每个子设备创建告警
    for child in children:
        alarm = Alarm(
            alarm_no=f"ALM20260321test{child.id:04d}",
            point_id=None,
            alarm_level="minor",
            alarm_type="mstp_device_offline",
            alarm_message=f"设备 {child.name} 离线",
            source=f"datasource:{child.id}",
            status="active",
            data_source="bridge",
        )
        db_session.add(alarm)
    await db_session.flush()

    # 批量关闭
    child_ids = [c.id for c in children]
    count = await resolve_datasource_alarms_batch(db_session, child_ids)
    await db_session.commit()

    assert count == 3

    # 验证全部已关闭
    result = await db_session.execute(
        select(Alarm).where(Alarm.status == "active")
    )
    assert len(result.scalars().all()) == 0


# ─── 5.8 communication_monitor 回归测试 ──────────────────────────

@pytest.mark.asyncio
@patch("app.services.communication_monitor.ws_manager")
async def test_communication_monitor_interrupted_unchanged(mock_ws, db_session):
    """无 parent_datasource_id 的设备仍使用 interrupted 状态（回归）"""
    # 创建一个独立设备，consecutive_failures 超阈值
    ds = DataSource(
        name="Modbus 设备",
        protocol_type="modbus_tcp",
        connection_config={"host": "10.0.0.1"},
        status="connected",
        is_enabled=True,
        consecutive_failures=5,
        retry_max_failures=3,
    )
    db_session.add(ds)
    await db_session.commit()

    mock_ws.broadcast_system = AsyncMock()
    mock_ws.broadcast_alarm = AsyncMock()
    await check_communication_status(db_session)

    # 验证状态为 interrupted（非 device_offline）
    result = await db_session.execute(select(DataSource).where(DataSource.id == ds.id))
    updated = result.scalar_one()
    assert updated.status == "interrupted"

    # 验证没有创建数据源告警（只有有父网关的设备才创建）
    alarm_result = await db_session.execute(
        select(Alarm).where(Alarm.source == f"datasource:{ds.id}")
    )
    assert alarm_result.scalar_one_or_none() is None
