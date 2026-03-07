"""
测试冗余检测服务 - Story 25.4
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.diagnosis.redundancy_service import check_redundancy_backup
from app.models.energy import PowerDevice


@pytest.mark.asyncio
async def test_check_redundancy_backup_n_plus_1_with_backup(db_session: AsyncSession):
    """测试 N+1 冗余，有备用设备"""
    # 创建冗余组设备
    device1 = PowerDevice(
        device_code="PDU-001",
        device_name="PDU-1",
        device_type="PDU",
        redundancy_type="N+1",
        redundancy_group_id="group-a",
        is_enabled=True
    )
    device2 = PowerDevice(
        device_code="PDU-002",
        device_name="PDU-2",
        device_type="PDU",
        redundancy_type="N+1",
        redundancy_group_id="group-a",
        is_enabled=True
    )
    db_session.add_all([device1, device2])
    await db_session.commit()
    await db_session.refresh(device1)
    await db_session.refresh(device2)

    # 检查 device1 的冗余状态
    result = await check_redundancy_backup(device1.id, db_session)

    assert result.has_backup is True
    assert result.redundancy_type == "N+1"
    assert result.backup_count == 1
    assert device2.id in result.backup_devices


@pytest.mark.asyncio
async def test_check_redundancy_backup_no_redundancy_type(db_session: AsyncSession):
    """测试无冗余配置"""
    device = PowerDevice(
        device_code="PDU-003",
        device_name="PDU-3",
        device_type="PDU",
        redundancy_type=None,
        is_enabled=True
    )
    db_session.add(device)
    await db_session.commit()
    await db_session.refresh(device)

    result = await check_redundancy_backup(device.id, db_session)

    assert result.has_backup is False
    assert result.redundancy_type is None


@pytest.mark.asyncio
async def test_check_redundancy_backup_device_not_found(db_session: AsyncSession):
    """测试设备不存在"""
    result = await check_redundancy_backup(99999, db_session)

    assert result.has_backup is False
    assert result.error is not None
    assert "not found" in result.error

