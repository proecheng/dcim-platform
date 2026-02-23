"""
设备控制服务测试

覆盖:
  - ControlResult / ControlInterface: 枚举值
  - DeviceControlService.validate_control_permission: 控制权限验证
  - DeviceControlService.get_control_status: 设备控制状态
  - DeviceControlService.control_device_regulation: 设备调节控制
  - DeviceControlService._get_control_interface: 控制接口判断
  - DeviceControlService._execute_simulated_control: 模拟控制
  - DeviceControlService.batch_control: 批量控制
  - DeviceControlService.execute_scheduled_control: 定时控制（未实现）
"""

import pytest

from app.services.device_control_service import (
    ControlResult,
    ControlInterface,
    DeviceControlService,
)
from app.models.energy import PowerDevice, LoadRegulationConfig


class TestControlEnums:
    """枚举值测试"""

    def test_control_result_values(self):
        """控制结果枚举"""
        assert ControlResult.SUCCESS == "success"
        assert ControlResult.FAILED == "failed"
        assert ControlResult.SIMULATED == "simulated"
        assert ControlResult.PENDING == "pending"

    def test_control_interface_values(self):
        """控制接口枚举"""
        assert ControlInterface.BMS == "bms"
        assert ControlInterface.MANUAL == "manual"
        assert ControlInterface.SIMULATED == "simulated"


class TestValidateControlPermission:
    """控制权限验证测试"""

    @pytest.mark.asyncio
    async def test_no_config_found(self, async_db):
        """无调节配置时拒绝"""
        svc = DeviceControlService(async_db)
        result = await svc.validate_control_permission(99999, "temperature", 25.0)
        assert result["is_allowed"] is False
        assert "未找到" in result["reasons"][0]

    @pytest.mark.asyncio
    async def test_config_disabled(self, async_db):
        """配置禁用时拒绝"""
        device = PowerDevice(
            device_code="DEV-001",
            device_name="测试空调",
            device_type="ac",
            rated_power=50.0,
            is_enabled=True,
        )
        async_db.add(device)
        await async_db.flush()

        config = LoadRegulationConfig(
            device_id=device.id,
            regulation_type="temperature",
            min_value=18,
            max_value=28,
            default_value=24,
            unit="℃",
            is_enabled=False,
        )
        async_db.add(config)
        await async_db.flush()

        svc = DeviceControlService(async_db)
        result = await svc.validate_control_permission(device.id, "temperature", 25.0)
        assert result["is_allowed"] is False
        assert "禁用" in result["reasons"][0]

    @pytest.mark.asyncio
    async def test_value_out_of_range(self, async_db):
        """目标值超出范围时拒绝"""
        device = PowerDevice(
            device_code="DEV-002",
            device_name="测试空调2",
            device_type="ac",
            rated_power=50.0,
            is_enabled=True,
        )
        async_db.add(device)
        await async_db.flush()

        config = LoadRegulationConfig(
            device_id=device.id,
            regulation_type="temperature",
            min_value=18,
            max_value=28,
            default_value=24,
            unit="℃",
            is_enabled=True,
        )
        async_db.add(config)
        await async_db.flush()

        svc = DeviceControlService(async_db)
        # 超过最大值
        result = await svc.validate_control_permission(device.id, "temperature", 35.0)
        assert result["is_allowed"] is False
        assert any("大于最大值" in r for r in result["reasons"])

        # 低于最小值
        result = await svc.validate_control_permission(device.id, "temperature", 10.0)
        assert result["is_allowed"] is False
        assert any("小于最小值" in r for r in result["reasons"])

    @pytest.mark.asyncio
    async def test_valid_control(self, async_db):
        """合法控制请求通过验证"""
        device = PowerDevice(
            device_code="DEV-003",
            device_name="测试空调3",
            device_type="ac",
            rated_power=50.0,
            is_enabled=True,
        )
        async_db.add(device)
        await async_db.flush()

        config = LoadRegulationConfig(
            device_id=device.id,
            regulation_type="temperature",
            min_value=18,
            max_value=28,
            default_value=24,
            unit="℃",
            is_enabled=True,
        )
        async_db.add(config)
        await async_db.flush()

        svc = DeviceControlService(async_db)
        result = await svc.validate_control_permission(device.id, "temperature", 26.0)
        assert result["is_allowed"] is True

    @pytest.mark.asyncio
    async def test_force_ignores_range(self, async_db):
        """force=True 忽略范围限制"""
        device = PowerDevice(
            device_code="DEV-004",
            device_name="强制空调",
            device_type="ac",
            rated_power=50.0,
            is_enabled=True,
        )
        async_db.add(device)
        await async_db.flush()

        config = LoadRegulationConfig(
            device_id=device.id,
            regulation_type="temperature",
            min_value=18,
            max_value=28,
            default_value=24,
            unit="℃",
            is_enabled=True,
        )
        async_db.add(config)
        await async_db.flush()

        svc = DeviceControlService(async_db)
        result = await svc.validate_control_permission(device.id, "temperature", 35.0, force=True)
        assert result["is_allowed"] is True
        assert len(result["warnings"]) > 0


class TestGetControlStatus:
    """设备控制状态测试"""

    @pytest.mark.asyncio
    async def test_device_not_found(self, async_db):
        """设备不存在"""
        svc = DeviceControlService(async_db)
        result = await svc.get_control_status(99999)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_device_with_regulations(self, async_db):
        """设备有调节配置"""
        device = PowerDevice(
            device_code="DEV-005",
            device_name="状态测试空调",
            device_type="ac",
            rated_power=50.0,
            is_enabled=True,
        )
        async_db.add(device)
        await async_db.flush()

        config = LoadRegulationConfig(
            device_id=device.id,
            regulation_type="temperature",
            min_value=18,
            max_value=28,
            default_value=24,
            current_value=24,
            unit="℃",
            is_enabled=True,
            is_auto=True,
        )
        async_db.add(config)
        await async_db.flush()

        svc = DeviceControlService(async_db)
        result = await svc.get_control_status(device.id)
        assert result["device_name"] == "状态测试空调"
        assert result["control_count"] == 1
        assert len(result["regulations"]) == 1


class TestControlDeviceRegulation:
    """设备调节控制测试"""

    @pytest.mark.asyncio
    async def test_device_not_found(self, async_db):
        """设备不存在时返回失败"""
        svc = DeviceControlService(async_db)
        action = await svc.control_device_regulation(99999, "temperature", 25.0)
        assert action.result == ControlResult.FAILED
        assert "不存在" in action.message

    @pytest.mark.asyncio
    async def test_simulated_control(self, async_db):
        """模拟控制执行"""
        device = PowerDevice(
            device_code="DEV-006",
            device_name="模拟控制空调",
            device_type="other",
            rated_power=50.0,
            is_enabled=True,
        )
        async_db.add(device)
        await async_db.flush()

        config = LoadRegulationConfig(
            device_id=device.id,
            regulation_type="temperature",
            min_value=18,
            max_value=28,
            default_value=24,
            current_value=24,
            unit="℃",
            is_enabled=True,
            is_auto=True,
        )
        async_db.add(config)
        await async_db.flush()

        svc = DeviceControlService(async_db)
        action = await svc.control_device_regulation(device.id, "temperature", 26.0)
        assert action.result == ControlResult.SIMULATED
        assert "模拟" in action.message


class TestExecuteScheduledControl:
    """定时控制测试"""

    @pytest.mark.asyncio
    async def test_not_implemented(self, async_db):
        """定时控制尚未实现"""
        svc = DeviceControlService(async_db)
        with pytest.raises(NotImplementedError):
            await svc.execute_scheduled_control(1)
