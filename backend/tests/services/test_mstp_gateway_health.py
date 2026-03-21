"""Story 35.2: 双层故障隔离 — MS/TP 网关健康检查测试"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from app.core.database import Base
from app.models.gateway import DataSource
from app.services.gateway_monitor import check_mstp_gateway_health
from app.services.communication_monitor import check_communication_status


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
        is_enabled=False,  # 网关本身不采集
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


# ─── Test 4.1: 网关故障级联 ─────────────────────────────────


@pytest.mark.asyncio
@patch("app.services.gateway_monitor.BacnetIpAdapter")
async def test_gateway_offline_cascade(MockAdapter, db_session):
    """网关探测连续失败达阈值 → 网关+子设备均变 gateway_offline"""
    MockAdapter.return_value = _mock_adapter_factory(connect_result=False).return_value

    gw, children = await _create_gateway_with_children(
        db_session, gw_status="disconnected", gw_failures=2  # 还差1次达阈值3
    )
    await db_session.commit()

    await check_mstp_gateway_health(db_session)

    # 重新查询
    result = await db_session.execute(select(DataSource).where(DataSource.id == gw.id))
    gw_updated = result.scalar_one()
    assert gw_updated.status == "gateway_offline"
    assert gw_updated.consecutive_failures == 3

    for child in children:
        result = await db_session.execute(select(DataSource).where(DataSource.id == child.id))
        c = result.scalar_one()
        assert c.status == "gateway_offline"


# ─── Test 4.2: 设备单独离线 ─────────────────────────────────


@pytest.mark.asyncio
async def test_device_offline_only(db_session):
    """网关在线，单设备 consecutive_failures 达阈值 → device_offline"""
    gw, children = await _create_gateway_with_children(
        db_session, gw_status="connected", child_count=2,
        child_status="connected", child_failures=0
    )
    # 让子设备1失败达阈值
    children[0].consecutive_failures = 5
    children[0].retry_max_failures = 5
    await db_session.commit()

    # mock ws_manager 避免 WebSocket 报错
    with patch("app.services.communication_monitor.ws_manager"):
        await check_communication_status(db_session)

    result = await db_session.execute(select(DataSource).where(DataSource.id == children[0].id))
    c0 = result.scalar_one()
    assert c0.status == "device_offline"

    # 子设备2不受影响
    result = await db_session.execute(select(DataSource).where(DataSource.id == children[1].id))
    c1 = result.scalar_one()
    assert c1.status == "connected"

    # 网关不受影响
    result = await db_session.execute(select(DataSource).where(DataSource.id == gw.id))
    gw_updated = result.scalar_one()
    assert gw_updated.status == "connected"


# ─── Test 4.3: 网关恢复 ─────────────────────────────────────


@pytest.mark.asyncio
@patch("app.services.gateway_monitor.BacnetIpAdapter")
async def test_gateway_recovery(MockAdapter, db_session):
    """网关恢复 → connected，子设备从 gateway_offline → disconnected"""
    MockAdapter.return_value = _mock_adapter_factory(connect_result=True, test_success=True).return_value

    gw, children = await _create_gateway_with_children(
        db_session, gw_status="gateway_offline", gw_failures=5,
        child_status="gateway_offline"
    )
    await db_session.commit()

    await check_mstp_gateway_health(db_session)

    result = await db_session.execute(select(DataSource).where(DataSource.id == gw.id))
    gw_updated = result.scalar_one()
    assert gw_updated.status == "connected"
    assert gw_updated.consecutive_failures == 0

    for child in children:
        result = await db_session.execute(select(DataSource).where(DataSource.id == child.id))
        c = result.scalar_one()
        assert c.status == "disconnected"


# ─── Test 4.4: 无网关配置 ───────────────────────────────────


@pytest.mark.asyncio
async def test_no_gateway_noop(db_session):
    """无 parent_datasource_id 时立即返回，不报错"""
    ds = DataSource(
        name="普通数据源",
        protocol_type="modbus_tcp",
        connection_config={"host": "10.0.0.1", "port": 502},
        status="connected",
        is_enabled=True,
    )
    db_session.add(ds)
    await db_session.commit()

    # 不 patch BacnetIpAdapter，确保函数直接返回（不会尝试探测）
    await check_mstp_gateway_health(db_session)

    result = await db_session.execute(select(DataSource).where(DataSource.id == ds.id))
    updated = result.scalar_one()
    assert updated.status == "connected"


# ─── Test 4.5: communication_monitor 跳过 gateway_offline ───


@pytest.mark.asyncio
async def test_communication_monitor_skips_gateway_offline(db_session):
    """communication_monitor 跳过父网关为 gateway_offline 的子设备"""
    gw, children = await _create_gateway_with_children(
        db_session, gw_status="gateway_offline", gw_failures=5,
        child_status="gateway_offline", child_failures=10
    )
    # 启用子设备使其被 communication_monitor 查询到
    await db_session.commit()

    with patch("app.services.communication_monitor.ws_manager"):
        await check_communication_status(db_session)

    # 子设备应该保持 gateway_offline（被跳过）
    for child in children:
        result = await db_session.execute(select(DataSource).where(DataSource.id == child.id))
        c = result.scalar_one()
        assert c.status == "gateway_offline"


# ─── Test 4.6: device_offline → 网关故障 → gateway_offline → 恢复 → disconnected ─


@pytest.mark.asyncio
@patch("app.services.gateway_monitor.BacnetIpAdapter")
async def test_device_offline_then_gateway_cascade_then_recovery(MockAdapter, db_session):
    """子设备先 device_offline → 网关故障级联 gateway_offline → 网关恢复 → disconnected"""
    # 阶段1：子设备已 device_offline
    gw, children = await _create_gateway_with_children(
        db_session, gw_status="disconnected", gw_failures=2,
        child_count=2
    )
    children[0].status = "device_offline"
    children[1].status = "connected"
    await db_session.commit()

    # 阶段2：网关探测失败，级联覆盖
    MockAdapter.return_value = _mock_adapter_factory(connect_result=False).return_value
    await check_mstp_gateway_health(db_session)

    for child in children:
        result = await db_session.execute(select(DataSource).where(DataSource.id == child.id))
        c = result.scalar_one()
        assert c.status == "gateway_offline", f"子设备 {child.name} 应为 gateway_offline"

    # 阶段3：网关恢复
    MockAdapter.return_value = _mock_adapter_factory(connect_result=True, test_success=True).return_value

    # 需要刷新 gw_ds.status 以反映 gateway_offline
    result = await db_session.execute(select(DataSource).where(DataSource.id == gw.id))
    gw_refreshed = result.scalar_one()
    assert gw_refreshed.status == "gateway_offline"

    await check_mstp_gateway_health(db_session)

    result = await db_session.execute(select(DataSource).where(DataSource.id == gw.id))
    gw_recovered = result.scalar_one()
    assert gw_recovered.status == "connected"

    for child in children:
        result = await db_session.execute(select(DataSource).where(DataSource.id == child.id))
        c = result.scalar_one()
        assert c.status == "disconnected", f"子设备 {child.name} 恢复后应为 disconnected"
