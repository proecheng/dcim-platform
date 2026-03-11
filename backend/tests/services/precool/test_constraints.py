"""
约束检查引擎单元测试（纯 mock）

Story 30.1: ASHRAE 温度硬约束与功率限制
覆盖温度范围、功率上限、温变速率、综合检查、配置可修改性
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.precool.constraints import (
    ConstraintType,
    ConstraintViolation,
    check_temperature_constraints,
    check_power_constraint,
    check_rate_of_change,
    check_all_constraints,
    _load_constraint_config,
    _get_zone_rated_power,
    _get_max_inlet_temperature,
    DEFAULT_TEMP_MAX,
    DEFAULT_TEMP_MIN,
    DEFAULT_POWER_MULTIPLIER,
    DEFAULT_RATE_LIMIT,
)


# ==================== 辅助函数 ====================

def _default_config():
    """默认约束配置"""
    return {
        "temp_max": DEFAULT_TEMP_MAX,
        "temp_min": DEFAULT_TEMP_MIN,
        "power_multiplier": DEFAULT_POWER_MULTIPLIER,
        "rate_limit": DEFAULT_RATE_LIMIT,
    }


def _mock_session():
    """创建 mock session"""
    return AsyncMock()


# ==================== ConstraintViolation 测试 ====================

class TestConstraintViolation:
    """约束违规数据类"""

    def test_to_dict_serialization(self):
        """to_dict 正确序列化枚举值"""
        v = ConstraintViolation(
            constraint_type=ConstraintType.TEMPERATURE_HIGH,
            current_value=28.0,
            threshold=27.0,
            zone_id=1,
            message="test",
            severity="error",
        )
        d = v.to_dict()
        assert d["type"] == "temperature_high"  # 枚举值而非枚举对象
        assert d["current_value"] == 28.0
        assert d["severity"] == "error"

    def test_constraint_type_values(self):
        """枚举值定义正确"""
        assert ConstraintType.TEMPERATURE_HIGH.value == "temperature_high"
        assert ConstraintType.TEMPERATURE_LOW.value == "temperature_low"
        assert ConstraintType.POWER_OVER_LIMIT.value == "power_over_limit"
        assert ConstraintType.RATE_OF_CHANGE.value == "rate_of_change"


# ==================== 温度约束测试 ====================

class TestTemperatureConstraints:
    """ASHRAE 温度范围检查"""

    @pytest.mark.asyncio
    async def test_normal_temperature_no_violation(self):
        """正常温度范围内无违规"""
        session = _mock_session()
        config = _default_config()

        with patch(
            "app.services.precool.constraints._get_max_inlet_temperature",
            new_callable=AsyncMock,
            return_value=22.0,
        ):
            violations = await check_temperature_constraints(1, session, config)
            assert len(violations) == 0

    @pytest.mark.asyncio
    async def test_temperature_exceeds_upper_limit(self):
        """温度超过上限 → error"""
        session = _mock_session()
        config = _default_config()

        with patch(
            "app.services.precool.constraints._get_max_inlet_temperature",
            new_callable=AsyncMock,
            return_value=28.5,
        ):
            violations = await check_temperature_constraints(1, session, config)
            assert len(violations) == 1
            assert violations[0].constraint_type == ConstraintType.TEMPERATURE_HIGH
            assert violations[0].severity == "error"
            assert violations[0].current_value == 28.5

    @pytest.mark.asyncio
    async def test_temperature_at_upper_limit_boundary(self):
        """温度恰好等于上限 → error"""
        session = _mock_session()
        config = _default_config()

        with patch(
            "app.services.precool.constraints._get_max_inlet_temperature",
            new_callable=AsyncMock,
            return_value=27.0,
        ):
            violations = await check_temperature_constraints(1, session, config)
            assert len(violations) == 1
            assert violations[0].severity == "error"

    @pytest.mark.asyncio
    async def test_temperature_approaching_upper_limit(self):
        """温度接近上限（25-27°C）→ warning"""
        session = _mock_session()
        config = _default_config()

        with patch(
            "app.services.precool.constraints._get_max_inlet_temperature",
            new_callable=AsyncMock,
            return_value=26.0,
        ):
            violations = await check_temperature_constraints(1, session, config)
            assert len(violations) == 1
            assert violations[0].severity == "warning"

    @pytest.mark.asyncio
    async def test_temperature_below_lower_limit(self):
        """温度低于下限 → error"""
        session = _mock_session()
        config = _default_config()

        with patch(
            "app.services.precool.constraints._get_max_inlet_temperature",
            new_callable=AsyncMock,
            return_value=16.0,
        ):
            violations = await check_temperature_constraints(1, session, config)
            assert len(violations) == 1
            assert violations[0].constraint_type == ConstraintType.TEMPERATURE_LOW
            assert violations[0].severity == "error"

    @pytest.mark.asyncio
    async def test_temperature_at_lower_limit_boundary(self):
        """温度恰好等于下限 → error"""
        session = _mock_session()
        config = _default_config()

        with patch(
            "app.services.precool.constraints._get_max_inlet_temperature",
            new_callable=AsyncMock,
            return_value=18.0,
        ):
            violations = await check_temperature_constraints(1, session, config)
            assert len(violations) == 1
            assert violations[0].severity == "error"

    @pytest.mark.asyncio
    async def test_no_temperature_data_no_violation(self):
        """无温度数据时不产生违规"""
        session = _mock_session()
        config = _default_config()

        with patch(
            "app.services.precool.constraints._get_max_inlet_temperature",
            new_callable=AsyncMock,
            return_value=None,
        ):
            violations = await check_temperature_constraints(1, session, config)
            assert len(violations) == 0

    @pytest.mark.asyncio
    async def test_just_below_warning_threshold(self):
        """温度刚好低于 warning 阈值（24.9°C）→ 无违规"""
        session = _mock_session()
        config = _default_config()

        with patch(
            "app.services.precool.constraints._get_max_inlet_temperature",
            new_callable=AsyncMock,
            return_value=24.9,
        ):
            violations = await check_temperature_constraints(1, session, config)
            assert len(violations) == 0


# ==================== 功率约束测试 ====================

class TestPowerConstraint:
    """制冷功率上限检查"""

    @pytest.mark.asyncio
    async def test_normal_power_no_violation(self):
        """正常功率范围内无违规"""
        session = _mock_session()
        config = _default_config()

        with patch(
            "app.services.precool.constraints._get_zone_rated_power",
            new_callable=AsyncMock,
            return_value=1000.0,
        ):
            violation = await check_power_constraint(1, 1200.0, session, config)
            assert violation is None

    @pytest.mark.asyncio
    async def test_power_exceeds_limit(self):
        """功率超过上限 → error"""
        session = _mock_session()
        config = _default_config()

        with patch(
            "app.services.precool.constraints._get_zone_rated_power",
            new_callable=AsyncMock,
            return_value=1000.0,  # Q_max = 1000 * 1.5 = 1500
        ):
            violation = await check_power_constraint(1, 1600.0, session, config)
            assert violation is not None
            assert violation.constraint_type == ConstraintType.POWER_OVER_LIMIT
            assert violation.severity == "error"
            assert violation.threshold == 1500.0

    @pytest.mark.asyncio
    async def test_power_approaching_limit(self):
        """功率接近上限（>90%）→ warning"""
        session = _mock_session()
        config = _default_config()

        with patch(
            "app.services.precool.constraints._get_zone_rated_power",
            new_callable=AsyncMock,
            return_value=1000.0,  # Q_max = 1500, 90% = 1350
        ):
            violation = await check_power_constraint(1, 1400.0, session, config)
            assert violation is not None
            assert violation.severity == "warning"

    @pytest.mark.asyncio
    async def test_power_at_exact_limit(self):
        """功率恰好等于上限 → 无违规（<=）"""
        session = _mock_session()
        config = _default_config()

        with patch(
            "app.services.precool.constraints._get_zone_rated_power",
            new_callable=AsyncMock,
            return_value=1000.0,
        ):
            # Q_max = 1500, q_cool = 1500 → 不超限但超过 90%
            violation = await check_power_constraint(1, 1500.0, session, config)
            # 1500 > 1500*0.9=1350 → warning
            assert violation is not None
            assert violation.severity == "warning"

    @pytest.mark.asyncio
    async def test_rated_power_fallback_to_linkage_config(self):
        """CoolingUnit 无数据时回退到 CoolingLinkageConfig"""
        session = _mock_session()

        # 模拟 CoolingUnit 无数据 (sum 返回 None)
        mock_result_1 = MagicMock()
        mock_result_1.scalar.return_value = None

        # 模拟 CoolingLinkageConfig 返回 max_cooling_power
        mock_result_2 = MagicMock()
        mock_result_2.scalar_one_or_none.return_value = 1500.0

        session.execute = AsyncMock(side_effect=[mock_result_1, mock_result_2])

        rated = await _get_zone_rated_power(1, session)
        assert rated == 1500.0

    @pytest.mark.asyncio
    async def test_rated_power_final_fallback(self):
        """所有数据源都失败时回退到 2000kW"""
        session = _mock_session()

        mock_result = MagicMock()
        mock_result.scalar.return_value = None

        mock_result_2 = MagicMock()
        mock_result_2.scalar_one_or_none.return_value = None

        session.execute = AsyncMock(side_effect=[mock_result, mock_result_2])

        rated = await _get_zone_rated_power(1, session)
        assert rated == 2000.0


# ==================== 温变速率测试 ====================

class TestRateOfChange:
    """温变速率约束检查"""

    @pytest.mark.asyncio
    async def test_normal_rate_no_violation(self):
        """正常速率无违规"""
        session = _mock_session()
        config = _default_config()

        with patch(
            "app.services.datacenter_shift_strategy._calculate_temperature_rise_rate",
            new_callable=AsyncMock,
            return_value=1.5,
        ):
            violations = await check_rate_of_change(1, session, config)
            assert len(violations) == 0

    @pytest.mark.asyncio
    async def test_rate_exceeds_limit(self):
        """速率超限 → error"""
        session = _mock_session()
        config = _default_config()

        with patch(
            "app.services.datacenter_shift_strategy._calculate_temperature_rise_rate",
            new_callable=AsyncMock,
            return_value=6.0,
        ):
            violations = await check_rate_of_change(1, session, config)
            assert len(violations) == 1
            assert violations[0].constraint_type == ConstraintType.RATE_OF_CHANGE
            assert violations[0].severity == "error"
            assert violations[0].current_value == 6.0

    @pytest.mark.asyncio
    async def test_negative_rate_exceeds_limit(self):
        """负速率超限（降温过快）→ error"""
        session = _mock_session()
        config = _default_config()

        with patch(
            "app.services.datacenter_shift_strategy._calculate_temperature_rise_rate",
            new_callable=AsyncMock,
            return_value=-6.0,
        ):
            violations = await check_rate_of_change(1, session, config)
            assert len(violations) == 1
            assert violations[0].severity == "error"
            assert violations[0].current_value == 6.0  # 取绝对值

    @pytest.mark.asyncio
    async def test_rate_approaching_limit(self):
        """速率接近限制（>90%）→ warning"""
        session = _mock_session()
        config = _default_config()

        with patch(
            "app.services.datacenter_shift_strategy._calculate_temperature_rise_rate",
            new_callable=AsyncMock,
            return_value=4.6,  # > 5.0 * 0.9 = 4.5
        ):
            violations = await check_rate_of_change(1, session, config)
            assert len(violations) == 1
            assert violations[0].severity == "warning"

    @pytest.mark.asyncio
    async def test_rate_below_warning_threshold(self):
        """速率低于 warning 阈值（4.4°C/h）→ 无违规"""
        session = _mock_session()
        config = _default_config()

        with patch(
            "app.services.datacenter_shift_strategy._calculate_temperature_rise_rate",
            new_callable=AsyncMock,
            return_value=4.4,
        ):
            violations = await check_rate_of_change(1, session, config)
            assert len(violations) == 0


# ==================== 综合检查测试 ====================

class TestCheckAllConstraints:
    """综合约束检查"""

    @pytest.mark.asyncio
    async def test_all_constraints_pass(self):
        """所有约束通过"""
        session = _mock_session()

        with patch(
            "app.services.precool.constraints._load_constraint_config",
            new_callable=AsyncMock,
            return_value=_default_config(),
        ), patch(
            "app.services.precool.constraints._get_max_inlet_temperature",
            new_callable=AsyncMock,
            return_value=22.0,
        ), patch(
            "app.services.datacenter_shift_strategy._calculate_temperature_rise_rate",
            new_callable=AsyncMock,
            return_value=1.0,
        ):
            violations = await check_all_constraints(1, session)
            assert len(violations) == 0

    @pytest.mark.asyncio
    async def test_multiple_violations(self):
        """多约束同时违反"""
        session = _mock_session()

        with patch(
            "app.services.precool.constraints._load_constraint_config",
            new_callable=AsyncMock,
            return_value=_default_config(),
        ), patch(
            "app.services.precool.constraints._get_max_inlet_temperature",
            new_callable=AsyncMock,
            return_value=28.0,  # 温度超上限
        ), patch(
            "app.services.datacenter_shift_strategy._calculate_temperature_rise_rate",
            new_callable=AsyncMock,
            return_value=6.0,  # 速率超限
        ):
            violations = await check_all_constraints(1, session)
            assert len(violations) == 2
            types = {v.constraint_type for v in violations}
            assert ConstraintType.TEMPERATURE_HIGH in types
            assert ConstraintType.RATE_OF_CHANGE in types

    @pytest.mark.asyncio
    async def test_power_check_not_included(self):
        """综合检查不包含功率检查"""
        session = _mock_session()

        with patch(
            "app.services.precool.constraints._load_constraint_config",
            new_callable=AsyncMock,
            return_value=_default_config(),
        ), patch(
            "app.services.precool.constraints._get_max_inlet_temperature",
            new_callable=AsyncMock,
            return_value=22.0,
        ), patch(
            "app.services.datacenter_shift_strategy._calculate_temperature_rise_rate",
            new_callable=AsyncMock,
            return_value=1.0,
        ):
            violations = await check_all_constraints(1, session)
            # 即使有功率问题，综合检查也不包含
            power_violations = [v for v in violations if v.constraint_type == ConstraintType.POWER_OVER_LIMIT]
            assert len(power_violations) == 0


# ==================== 配置可修改性测试 ====================

class TestConstraintConfig:
    """约束参数可配置"""

    @pytest.mark.asyncio
    async def test_custom_temp_max(self):
        """自定义温度上限"""
        session = _mock_session()
        config = _default_config()
        config["temp_max"] = 30.0  # 放宽到 30°C

        with patch(
            "app.services.precool.constraints._get_max_inlet_temperature",
            new_callable=AsyncMock,
            return_value=28.0,
        ):
            # 28°C < 30°C → 接近阈值 warning（28 >= 30-2=28）
            violations = await check_temperature_constraints(1, session, config)
            assert len(violations) == 1
            assert violations[0].severity == "warning"

    @pytest.mark.asyncio
    async def test_custom_rate_limit(self):
        """自定义速率限制"""
        session = _mock_session()
        config = _default_config()
        config["rate_limit"] = 10.0  # 放宽到 10°C/h

        with patch(
            "app.services.datacenter_shift_strategy._calculate_temperature_rise_rate",
            new_callable=AsyncMock,
            return_value=6.0,
        ):
            # 6°C/h < 10°C/h → 无违规
            violations = await check_rate_of_change(1, session, config)
            assert len(violations) == 0

    @pytest.mark.asyncio
    async def test_custom_power_multiplier(self):
        """自定义功率倍数"""
        session = _mock_session()
        config = _default_config()
        config["power_multiplier"] = 2.0  # 放宽到 2x

        with patch(
            "app.services.precool.constraints._get_zone_rated_power",
            new_callable=AsyncMock,
            return_value=1000.0,  # Q_max = 2000
        ):
            # 1600 < 2000 → 无违规
            violation = await check_power_constraint(1, 1600.0, session, config)
            assert violation is None

    @pytest.mark.asyncio
    async def test_load_config_from_systemconfig(self):
        """从 SystemConfig 读取配置"""
        session = _mock_session()

        # 模拟 4 次查询返回自定义配置
        mock_results = []
        for value in ["30.0", "15.0", "2.0", "8.0"]:
            mock_result = MagicMock()
            mock_obj = MagicMock()
            mock_obj.config_value = value
            mock_result.scalar_one_or_none.return_value = mock_obj
            mock_results.append(mock_result)

        session.execute = AsyncMock(side_effect=mock_results)

        config = await _load_constraint_config(session)
        assert config["temp_max"] == 30.0
        assert config["temp_min"] == 15.0
        assert config["power_multiplier"] == 2.0
        assert config["rate_limit"] == 8.0

    @pytest.mark.asyncio
    async def test_load_config_uses_defaults_when_missing(self):
        """SystemConfig 无记录时使用默认值"""
        session = _mock_session()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        config = await _load_constraint_config(session)
        assert config["temp_max"] == DEFAULT_TEMP_MAX
        assert config["temp_min"] == DEFAULT_TEMP_MIN
        assert config["power_multiplier"] == DEFAULT_POWER_MULTIPLIER
        assert config["rate_limit"] == DEFAULT_RATE_LIMIT


# ==================== 默认常量验证 ====================

class TestDefaultConstants:
    """默认值与 ASHRAE 标准一致"""

    def test_default_temp_max(self):
        assert DEFAULT_TEMP_MAX == 27.0

    def test_default_temp_min(self):
        assert DEFAULT_TEMP_MIN == 18.0

    def test_default_power_multiplier(self):
        assert DEFAULT_POWER_MULTIPLIER == 1.5

    def test_default_rate_limit(self):
        assert DEFAULT_RATE_LIMIT == 5.0
