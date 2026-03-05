"""负荷转移设备接口测试"""

from types import SimpleNamespace

import pytest

from app.api.v1.shift import get_shiftable_devices
from app.models.energy import DeviceShiftConfig, PowerDevice


@pytest.mark.asyncio
async def test_get_shiftable_devices_returns_real_data(async_db):
    """/devices/shiftable 应返回设备列表与可转移潜力。"""
    d1 = PowerDevice(
        device_code="UPS-T-001",
        device_name="测试UPS",
        device_type="UPS",
        rated_power=200,
        avg_load_rate=50,
        is_enabled=True,
    )
    d2 = PowerDevice(
        device_code="AC-T-001",
        device_name="测试空调",
        device_type="AC",
        rated_power=100,
        avg_load_rate=60,
        is_enabled=True,
    )
    async_db.add_all([d1, d2])
    await async_db.flush()

    async_db.add(
        DeviceShiftConfig(
            device_id=d1.id,
            is_shiftable=True,
            shiftable_power_ratio=0.3,
            is_critical=True,
        )
    )
    await async_db.commit()

    items = await get_shiftable_devices(db=async_db, current_user=SimpleNamespace(id=1))

    assert len(items) >= 2
    # 返回为 Pydantic 对象（使用 device_name 匹配）
    ups = next(x for x in items if x.device_name == "测试UPS")
    assert ups.is_shiftable is True
    assert ups.shift_potential > 0
    assert any("critical_device" in c for c in ups.constraints)
