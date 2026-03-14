"""
单元测试：温度约束计算逻辑
"""
import pytest
import asyncio
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.datacenter_shift_strategy import (
    _calculate_temperature_constraint,
    TemperatureConstraint,
    TEMP_WARNING,
    TEMP_SAFETY_MARGIN
)
from app.models import PowerDevice, CoolingUnit


class TestTemperatureConstraint:
    """温度约束计算测试"""
    
    @pytest.mark.asyncio
    async def test_no_cooling_unit(self):
        """测试：设备没有关联的制冷单元"""
        # Mock session
        session = AsyncMock(spec=AsyncSession)

        # Mock device
        device = PowerDevice(
            id=1,
            device_code="AC-001",
            device_name="空调1",
            device_type="AC",
            rated_power=50.0,
            area_code="A1"
        )

        # Mock query result: no cooling unit (使用 MagicMock 因为 scalar_one_or_none 是同步方法)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        # Execute
        constraint = await _calculate_temperature_constraint(session, device, 0.3)

        # Assert
        assert constraint.max_reduction_ratio == 0.5  # 保守估计
        assert "未找到制冷单元配置" in constraint.reason
    
    @pytest.mark.asyncio
    async def test_no_cooling_zone(self):
        """测试：制冷单元没有配置制冷区域"""
        session = AsyncMock(spec=AsyncSession)

        device = PowerDevice(
            id=1,
            device_code="AC-001",
            device_name="空调1",
            device_type="AC",
            rated_power=50.0,
            area_code="A1"
        )

        # Mock cooling unit exists
        cooling_unit = CoolingUnit(
            id=1,
            device_id=1,
            cooling_capacity_kw=100.0
        )

        # 使用 side_effect 列表：每次 await session.execute() 返回不同的结果
        result1 = MagicMock()  # cooling_unit query
        result1.scalar_one_or_none.return_value = cooling_unit

        result2 = MagicMock()  # zone_units query -> empty
        result2.scalars.return_value.all.return_value = []

        result3 = MagicMock()  # cabinets query (fallback to area_code) -> empty
        result3.scalars.return_value.all.return_value = []

        session.execute = AsyncMock(side_effect=[result1, result2, result3])

        # Execute
        constraint = await _calculate_temperature_constraint(session, device, 0.3)

        # Assert
        assert constraint.max_reduction_ratio == 0.5
        assert "未找到关联机柜" in constraint.reason or "未配置制冷区域" in constraint.reason
    
    @pytest.mark.asyncio
    async def test_temperature_within_limit(self):
        """测试：当前温度在安全范围内"""
        # 这个测试需要完整的mock链，暂时跳过
        # 实际项目中应该使用测试数据库
        pass
    
    @pytest.mark.asyncio
    async def test_temperature_exceeds_limit(self):
        """测试：当前温度接近上限"""
        # 这个测试需要完整的mock链，暂时跳过
        pass
    
    def test_temperature_constraint_structure(self):
        """测试：TemperatureConstraint数据结构"""
        constraint = TemperatureConstraint()
        
        # 检查默认值
        assert constraint.max_reduction_ratio == 1.0
        assert constraint.affected_cabinets == []
        assert constraint.current_temps == {}
        assert constraint.predicted_temps == {}
        assert constraint.is_safe == True
        assert constraint.reason == ""
        
        # 检查可以设置值
        constraint.max_reduction_ratio = 0.5
        constraint.reason = "测试原因"
        constraint.is_safe = False
        
        assert constraint.max_reduction_ratio == 0.5
        assert constraint.reason == "测试原因"
        assert constraint.is_safe == False


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
