"""
动态制冷比例替换测试

Story 29.7: 替换 constraint_checker 固定 0.4 制冷比例
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.load_shift.algorithms.constraint_checker import ConstraintChecker


class TestGetDynamicCoolingRatio:
    """_get_dynamic_cooling_ratio 方法测试"""

    def _make_checker(self, mock_session=None):
        """创建 ConstraintChecker 实例"""
        session = mock_session or AsyncMock()
        return ConstraintChecker(db=session)

    @pytest.mark.asyncio
    async def test_none_zone_id_returns_none(self):
        """zone_id 为 None 时返回 None"""
        checker = self._make_checker()
        result = await checker._get_dynamic_cooling_ratio(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_zone_id_returns_none(self):
        """zone_id 无法转为 int 时返回 None"""
        checker = self._make_checker()
        result = await checker._get_dynamic_cooling_ratio("abc")
        assert result is None

    @pytest.mark.asyncio
    async def test_no_linkage_config_returns_none(self):
        """无 CoolingLinkageConfig 记录时返回 None"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        checker = self._make_checker(mock_session)
        result = await checker._get_dynamic_cooling_ratio(1)
        assert result is None

    @pytest.mark.asyncio
    async def test_precool_disabled_returns_none(self):
        """precool_enabled=False 时返回 None"""
        mock_config = MagicMock()
        mock_config.precool_enabled = False

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_session.execute = AsyncMock(return_value=mock_result)

        checker = self._make_checker(mock_session)
        result = await checker._get_dynamic_cooling_ratio(1)
        assert result is None

    @pytest.mark.asyncio
    async def test_precool_enabled_dynamic_success(self):
        """precool_enabled=True + 动态计算成功 → 返回 shiftable_ratio"""
        mock_config = MagicMock()
        mock_config.precool_enabled = True

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_session.execute = AsyncMock(return_value=mock_result)

        checker = self._make_checker(mock_session)

        with patch(
            "app.services.datacenter_shift_strategy.calculate_shiftable_power_for_zone",
            new_callable=AsyncMock,
            return_value={"zone_id": 1, "shiftable_ratio": 0.35, "method": "THM"}
        ):
            result = await checker._get_dynamic_cooling_ratio(1)
            assert result == 0.35

    @pytest.mark.asyncio
    async def test_precool_enabled_dynamic_error_returns_none(self):
        """precool_enabled=True + 动态计算返回 error → 返回 None"""
        mock_config = MagicMock()
        mock_config.precool_enabled = True

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_session.execute = AsyncMock(return_value=mock_result)

        checker = self._make_checker(mock_session)

        with patch(
            "app.services.datacenter_shift_strategy.calculate_shiftable_power_for_zone",
            new_callable=AsyncMock,
            return_value={"error": "sensor_offline", "zone_id": 1, "details": "No data"}
        ):
            result = await checker._get_dynamic_cooling_ratio(1)
            assert result is None

    @pytest.mark.asyncio
    async def test_query_exception_returns_none(self):
        """查询异常时返回 None（不传播异常）"""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=Exception("DB error"))

        checker = self._make_checker(mock_session)
        result = await checker._get_dynamic_cooling_ratio(1)
        assert result is None

    @pytest.mark.asyncio
    async def test_string_zone_id_converted(self):
        """zone_id 为字符串时正确转为 int"""
        mock_config = MagicMock()
        mock_config.precool_enabled = True

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_session.execute = AsyncMock(return_value=mock_result)

        checker = self._make_checker(mock_session)

        with patch(
            "app.services.datacenter_shift_strategy.calculate_shiftable_power_for_zone",
            new_callable=AsyncMock,
            return_value={"zone_id": 2, "shiftable_ratio": 0.25, "method": "TCL"}
        ):
            result = await checker._get_dynamic_cooling_ratio("2")
            assert result == 0.25

    @pytest.mark.asyncio
    async def test_tcl_method_returns_ratio(self):
        """TCL 方法返回的 ratio 正确传递"""
        mock_config = MagicMock()
        mock_config.precool_enabled = True

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_session.execute = AsyncMock(return_value=mock_result)

        checker = self._make_checker(mock_session)

        with patch(
            "app.services.datacenter_shift_strategy.calculate_shiftable_power_for_zone",
            new_callable=AsyncMock,
            return_value={"zone_id": 1, "shiftable_ratio": 0.4, "method": "TCL", "headroom_celsius": 5.0}
        ):
            result = await checker._get_dynamic_cooling_ratio(1)
            assert result == 0.4

    @pytest.mark.asyncio
    async def test_zero_ratio_returned(self):
        """shiftable_ratio=0 也应正确返回（不被误判为 None）"""
        mock_config = MagicMock()
        mock_config.precool_enabled = True

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_session.execute = AsyncMock(return_value=mock_result)

        checker = self._make_checker(mock_session)

        with patch(
            "app.services.datacenter_shift_strategy.calculate_shiftable_power_for_zone",
            new_callable=AsyncMock,
            return_value={"zone_id": 1, "shiftable_ratio": 0.0, "method": "TCL"}
        ):
            result = await checker._get_dynamic_cooling_ratio(1)
            assert result == 0.0
