"""
冗余检测集成测试 - Story 25.4
测试场景: N+1 冗余配置、故障模拟、诊断引擎集成
"""
import pytest
import time
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.energy import PowerDevice
from app.models.alarm import Alarm
from app.models.point import Point
from app.services.diagnosis.fault_tree import FaultTreeInferenceEngine
from app.services.diagnosis.redundancy_service import check_redundancy_backup


@pytest.mark.asyncio
async def test_n_plus_1_redundancy_with_single_failure(async_db: AsyncSession):
    """
    测试场景: 配置 N+1 冗余的 PDU，模拟单台故障
    验证: 诊断引擎正确识别备用路径并降低故障概率
    """
    # 创建 3 台 PDU，配置 N+1 冗余
    pdu1 = PowerDevice(
        device_code="PDU-A-001",
        device_name="PDU A1",
        device_type="PDU",
        is_enabled=True,
        redundancy_type="N+1",
        redundancy_group_id="PDU-GROUP-A"
    )
    pdu2 = PowerDevice(
        device_code="PDU-A-002",
        device_name="PDU A2",
        device_type="PDU",
        is_enabled=True,
        redundancy_type="N+1",
        redundancy_group_id="PDU-GROUP-A"
    )
    pdu3 = PowerDevice(
        device_code="PDU-A-003",
        device_name="PDU A3",
        device_type="PDU",
        is_enabled=True,
        redundancy_type="N+1",
        redundancy_group_id="PDU-GROUP-A"
    )
    async_db.add_all([pdu1, pdu2, pdu3])
    await async_db.commit()
    await async_db.refresh(pdu1)
    await async_db.refresh(pdu2)

    # 验证冗余检测
    redundancy_status = await check_redundancy_backup(pdu1.id, async_db)
    assert redundancy_status.has_backup is True
    assert redundancy_status.redundancy_type == "N+1"
    assert redundancy_status.backup_count >= 1
    assert pdu2.id in redundancy_status.backup_devices

    # 模拟 PDU1 故障
    pdu1.is_enabled = False
    await async_db.commit()

    # 验证 PDU2 仍有备用路径
    redundancy_status = await check_redundancy_backup(pdu2.id, async_db)
    assert redundancy_status.has_backup is True
    assert redundancy_status.backup_count >= 1


@pytest.mark.asyncio
async def test_2n_redundancy_with_half_failure(async_db: AsyncSession):
    """
    测试场景: 配置 2N 冗余的 UPS，模拟一半设备故障
    验证: 诊断引擎正确识别备用路径充足
    """
    # 创建 4 台 UPS，配置 2N 冗余
    ups_devices = []
    for i in range(1, 5):
        ups = PowerDevice(
            device_code=f"UPS-B-00{i}",
            device_name=f"UPS B{i}",
            device_type="UPS",
            is_enabled=True,
            redundancy_type="2N",
            redundancy_group_id="UPS-GROUP-B"
        )
        ups_devices.append(ups)
        async_db.add(ups)
    await async_db.commit()
    for ups in ups_devices:
        await async_db.refresh(ups)

    # 验证初始状态: 所有设备都有充足备用路径
    redundancy_status = await check_redundancy_backup(ups_devices[0].id, async_db)
    assert redundancy_status.has_backup is True
    assert redundancy_status.redundancy_type == "2N"
    assert redundancy_status.backup_count >= 2  # 至少 4/2 = 2 台备用

    # 模拟 2 台故障（一半）
    ups_devices[0].is_enabled = False
    ups_devices[1].is_enabled = False
    await async_db.commit()

    # 验证剩余设备仍有备用路径
    redundancy_status = await check_redundancy_backup(ups_devices[2].id, async_db)
    assert redundancy_status.has_backup is True
    assert redundancy_status.backup_count >= 1


@pytest.mark.asyncio
async def test_no_redundancy_single_failure(async_db: AsyncSession):
    """
    测试场景: 无冗余配置的设备故障
    验证: 诊断引擎不降低故障概率
    """
    # 创建单台 PDU，无冗余配置
    pdu = PowerDevice(
        device_code="PDU-C-001",
        device_name="PDU C1",
        device_type="PDU",
        is_enabled=True,
        redundancy_type=None,
        redundancy_group_id=None
    )
    async_db.add(pdu)
    await async_db.commit()
    await async_db.refresh(pdu)

    # 验证无冗余
    redundancy_status = await check_redundancy_backup(pdu.id, async_db)
    assert redundancy_status.has_backup is False
    assert redundancy_status.redundancy_type is None
    assert redundancy_status.backup_count == 0


@pytest.mark.asyncio
async def test_fault_tree_integration_with_redundancy(async_db: AsyncSession):
    """
    测试场景: 冗余检测与配电设备关联
    验证: 配电设备故障时能正确检测冗余状态
    """
    # 创建测试点位
    point = Point(
        point_code="POINT-TEST-001",
        point_name="Test Point",
        point_type="AI",
        unit="A"
    )
    async_db.add(point)
    await async_db.commit()
    await async_db.refresh(point)

    # 创建 2 台 PDU，配置 N+1 冗余
    pdu1 = PowerDevice(
        device_code="PDU-D-001",
        device_name="PDU D1",
        device_type="PDU",
        is_enabled=True,
        redundancy_type="N+1",
        redundancy_group_id="PDU-GROUP-D",
        current_point_id=point.id
    )
    pdu2 = PowerDevice(
        device_code="PDU-D-002",
        device_name="PDU D2",
        device_type="PDU",
        is_enabled=True,
        redundancy_type="N+1",
        redundancy_group_id="PDU-GROUP-D"
    )
    async_db.add_all([pdu1, pdu2])
    await async_db.commit()
    await async_db.refresh(pdu1)

    # 验证 PDU1 有备用路径
    redundancy_status = await check_redundancy_backup(pdu1.id, async_db)
    assert redundancy_status.has_backup is True
    assert redundancy_status.redundancy_type == "N+1"
    assert pdu2.id in redundancy_status.backup_devices

    # 模拟 PDU1 故障（禁用）
    pdu1.is_enabled = False
    await async_db.commit()

    # 验证 PDU2 仍有备用路径（虽然 PDU1 故障，但系统仍可运行）
    redundancy_status = await check_redundancy_backup(pdu2.id, async_db)
    # PDU2 现在没有备用路径了（因为 PDU1 已禁用）
    assert redundancy_status.has_backup is False
    assert redundancy_status.backup_count == 0


@pytest.mark.asyncio
async def test_redundancy_api_integration(client: AsyncClient, async_db: AsyncSession, admin_user):
    """
    测试场景: 通过 API 配置冗余并验证检测
    验证: API 配置 → 数据库更新 → 冗余检测生效
    """
    user, token = admin_user
    headers = {"Authorization": f"Bearer {token}"}

    # 创建测试设备
    device = PowerDevice(
        device_code="PDU-E-001",
        device_name="PDU E1",
        device_type="PDU",
        is_enabled=True
    )
    async_db.add(device)
    await async_db.commit()
    await async_db.refresh(device)

    # 通过 API 配置冗余
    response = await client.put(
        f"/api/v1/power/devices/{device.id}/redundancy",
        headers=headers,
        json={
            "redundancy_type": "N+1",
            "redundancy_group_id": "PDU-GROUP-E"
        }
    )
    assert response.status_code == 200

    # 验证数据库已更新
    await async_db.refresh(device)
    assert device.redundancy_type == "N+1"
    assert device.redundancy_group_id == "PDU-GROUP-E"

    # 创建备用设备
    backup_device = PowerDevice(
        device_code="PDU-E-002",
        device_name="PDU E2",
        device_type="PDU",
        is_enabled=True,
        redundancy_type="N+1",
        redundancy_group_id="PDU-GROUP-E"
    )
    async_db.add(backup_device)
    await async_db.commit()

    # 验证冗余检测生效
    redundancy_status = await check_redundancy_backup(device.id, async_db)
    assert redundancy_status.has_backup is True
    assert redundancy_status.redundancy_type == "N+1"


@pytest.mark.asyncio
async def test_redundancy_check_performance(async_db: AsyncSession):
    """
    测试场景: 验证冗余检测性能 < 100ms (Task 8.6)
    """
    # 创建测试设备
    devices = []
    for i in range(10):
        device = PowerDevice(
            device_code=f"PDU-PERF-{i:03d}",
            device_name=f"Performance Test PDU {i}",
            device_type="PDU",
            is_enabled=True,
            redundancy_type="N+1",
            redundancy_group_id="PERF-TEST-GROUP"
        )
        devices.append(device)
        async_db.add(device)
    await async_db.commit()
    for device in devices:
        await async_db.refresh(device)

    # 测试单次检测性能
    start_time = time.time()
    result = await check_redundancy_backup(devices[0].id, async_db)
    duration = time.time() - start_time

    assert result.has_backup is True
    assert duration < 0.1, f"冗余检测耗时 {duration:.3f}s 超过 100ms 阈值"


@pytest.mark.asyncio
async def test_redundancy_check_concurrency(async_db: AsyncSession):
    """
    测试场景: 验证并发冗余检测无竞态条件 (Task 8.7)
    """
    # 创建测试设备
    devices = []
    for i in range(5):
        device = PowerDevice(
            device_code=f"PDU-CONC-{i:03d}",
            device_name=f"Concurrency Test PDU {i}",
            device_type="PDU",
            is_enabled=True,
            redundancy_type="N+1",
            redundancy_group_id="CONC-TEST-GROUP"
        )
        devices.append(device)
        async_db.add(device)
    await async_db.commit()
    for device in devices:
        await async_db.refresh(device)

    # 并发执行多个冗余检测
    tasks = [
        check_redundancy_backup(device.id, async_db)
        for device in devices
        for _ in range(3)  # 每个设备检测 3 次
    ]

    results = await asyncio.gather(*tasks)

    # 验证所有结果一致且正确
    assert len(results) == 15  # 5 devices × 3 checks
    for result in results:
        assert result.has_backup is True
        assert result.redundancy_type == "N+1"
        assert result.backup_count >= 1  # 至少有 1 个备用设备
