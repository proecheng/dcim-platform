"""
Story 33.1: VPP 可调容量计算服务 — 单元测试

测试 VppCapacityService 的所有功能：
- calculate_capacity: 聚合多区域可调容量
- _calculate_zone_capacity: 单区域容量计算
- _seasonal_cop: COP 季节修正
- get_cached_capacity / refresh_capacity_cache: Redis 缓存
"""

from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from app.services.precool.vpp_capacity import (
    VppCapacityService,
    TEMP_MAX,
    TEMP_MIN,
    HEADROOM_DOWN_THRESHOLD,
    HEADROOM_UP_THRESHOLD,
    DEFAULT_RESPONSE_WINDOW,
    DEFAULT_LOAD_FACTOR,
    Q_MIN_RATIO,
    DEFAULT_COP,
    REDIS_KEY,
    REDIS_TTL,
)


# ==================== Fixtures ====================


@pytest.fixture
def service():
    """创建 VppCapacityService 实例"""
    return VppCapacityService()


def _make_zone(zone_id=1, zone_name="Zone-A", thermal_R=0.05, thermal_C=500.0):
    """创建模拟的 CoolingZone 对象"""
    zone = MagicMock()
    zone.id = zone_id
    zone.zone_name = zone_name
    zone.thermal_R = thermal_R
    zone.thermal_C = thermal_C
    return zone


# ==================== TestSeasonalCop ====================


class TestSeasonalCop:
    """测试 _seasonal_cop 静态方法"""

    def test_summer_cop(self):
        assert VppCapacityService._seasonal_cop(35.0) == 2.8

    def test_summer_boundary(self):
        assert VppCapacityService._seasonal_cop(30.0) == 2.8

    def test_transition_cop(self):
        assert VppCapacityService._seasonal_cop(20.0) == 3.5

    def test_transition_boundary(self):
        assert VppCapacityService._seasonal_cop(15.0) == 3.5

    def test_winter_cop(self):
        assert VppCapacityService._seasonal_cop(5.0) == 4.0

    def test_none_returns_default(self):
        assert VppCapacityService._seasonal_cop(None) == DEFAULT_COP


# ==================== TestCalculateZoneCapacity ====================


class TestCalculateZoneCapacity:
    """测试 _calculate_zone_capacity 方法"""

    @pytest.mark.asyncio
    async def test_normal_zone_with_headroom(self, service):
        """正常区域：温度 23°C，有充足裕度"""
        zone = _make_zone(thermal_R=0.05, thermal_C=500.0)
        session = AsyncMock()

        # Mock 温度 = 23.0°C
        with patch.object(service, '_get_current_temperature', return_value=23.0), \
             patch.object(service, '_get_total_cooling_capacity', return_value=1000.0), \
             patch.object(service, '_get_cop', return_value=3.5):

            result = await service._calculate_zone_capacity(zone, session)

        assert result is not None
        assert result["zone_id"] == 1
        assert result["T_current"] == 23.0

        # headroom_down = TEMP_MAX - T_current = 27 - 23 = 4.0
        assert result["headroom_down"] == 4.0
        # headroom_up = T_current - TEMP_MIN = 23 - 18 = 5.0
        assert result["headroom_up"] == 5.0

        # down_thermal = min(Q_cool_est - Q_min, C * (headroom_down - 1.0) / response_window)
        # Q_cool_est = 1000 * 0.7 = 700, Q_min = 1000 * 0.3 = 300
        # = min(700 - 300, 500 * (4.0 - 1.0) / 1.0) = min(400, 1500) = 400
        assert result["down_adjustable_thermal_kw"] == 400.0
        # down_kw = 400 / 3.5 ≈ 114.29
        assert abs(result["down_adjustable_kw"] - 114.29) < 0.1

        # up_thermal = min(Q_max - Q_cool_est, C * (headroom_up - 0.5) / response_window)
        # = min(1000 - 700, 500 * (5.0 - 0.5) / 1.0) = min(300, 2250) = 300
        assert result["up_adjustable_thermal_kw"] == 300.0
        # up_kw = 300 / 3.5 ≈ 85.71
        assert abs(result["up_adjustable_kw"] - 85.71) < 0.1

    @pytest.mark.asyncio
    async def test_zone_near_temp_max(self, service):
        """温度接近上限 26.5°C — headroom_down <= 1.0，向下可调 = 0"""
        zone = _make_zone()
        session = AsyncMock()

        with patch.object(service, '_get_current_temperature', return_value=26.5), \
             patch.object(service, '_get_total_cooling_capacity', return_value=1000.0), \
             patch.object(service, '_get_cop', return_value=3.5):

            result = await service._calculate_zone_capacity(zone, session)

        assert result is not None
        # headroom_down = 27 - 26.5 = 0.5 <= 1.0 → down = 0
        assert result["down_adjustable_thermal_kw"] == 0.0
        assert result["down_adjustable_kw"] == 0.0
        # headroom_up = 26.5 - 18 = 8.5 > 0.5 → up > 0
        assert result["up_adjustable_thermal_kw"] > 0

    @pytest.mark.asyncio
    async def test_zone_near_temp_min(self, service):
        """温度接近下限 18.3°C — headroom_up <= 0.5，向上可调 = 0"""
        zone = _make_zone()
        session = AsyncMock()

        with patch.object(service, '_get_current_temperature', return_value=18.3), \
             patch.object(service, '_get_total_cooling_capacity', return_value=1000.0), \
             patch.object(service, '_get_cop', return_value=3.5):

            result = await service._calculate_zone_capacity(zone, session)

        assert result is not None
        # headroom_up = 18.3 - 18 = 0.3 <= 0.5 → up = 0
        assert result["up_adjustable_thermal_kw"] == 0.0
        assert result["up_adjustable_kw"] == 0.0
        # headroom_down = 27 - 18.3 = 8.7 > 1.0 → down > 0
        assert result["down_adjustable_thermal_kw"] > 0

    @pytest.mark.asyncio
    async def test_temperature_unavailable_returns_none(self, service):
        """温度不可用时跳过该区域"""
        zone = _make_zone()
        session = AsyncMock()

        with patch.object(service, '_get_current_temperature', return_value=None):
            result = await service._calculate_zone_capacity(zone, session)

        assert result is None

    @pytest.mark.asyncio
    async def test_no_cooling_capacity_returns_none(self, service):
        """无制冷功率数据时跳过该区域"""
        zone = _make_zone()
        session = AsyncMock()

        with patch.object(service, '_get_current_temperature', return_value=23.0), \
             patch.object(service, '_get_total_cooling_capacity', return_value=None):
            result = await service._calculate_zone_capacity(zone, session)

        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_rc_parameters_returns_none(self, service):
        """R/C 为 0 时跳过该区域"""
        zone = _make_zone(thermal_R=0, thermal_C=500.0)
        session = AsyncMock()

        result = await service._calculate_zone_capacity(zone, session)
        assert result is None

    @pytest.mark.asyncio
    async def test_cop_applied_correctly(self, service):
        """验证 COP 正确应用于电功率转换"""
        zone = _make_zone(thermal_R=0.05, thermal_C=500.0)
        session = AsyncMock()

        # 夏季 COP=2.8
        with patch.object(service, '_get_current_temperature', return_value=23.0), \
             patch.object(service, '_get_total_cooling_capacity', return_value=1000.0), \
             patch.object(service, '_get_cop', return_value=2.8):

            result = await service._calculate_zone_capacity(zone, session)

        assert result["cop"] == 2.8
        # 相同热功率，COP 越小 → 电功率越大
        # down_thermal = 400, down_kw = 400 / 2.8 ≈ 142.86
        assert abs(result["down_adjustable_kw"] - 142.86) < 0.1

    @pytest.mark.asyncio
    async def test_headroom_boundary_exactly_at_threshold(self, service):
        """headroom 恰好等于阈值时返回 0"""
        zone = _make_zone()
        session = AsyncMock()

        # T = 26.0 → headroom_down = 27 - 26 = 1.0 = THRESHOLD → down = 0
        with patch.object(service, '_get_current_temperature', return_value=26.0), \
             patch.object(service, '_get_total_cooling_capacity', return_value=1000.0), \
             patch.object(service, '_get_cop', return_value=3.5):

            result = await service._calculate_zone_capacity(zone, session)

        assert result["down_adjustable_thermal_kw"] == 0.0

    @pytest.mark.asyncio
    async def test_c_limits_down_capacity(self, service):
        """当 C 很小时，热容量限制向下可调容量"""
        zone = _make_zone(thermal_R=0.05, thermal_C=50.0)  # 小 C
        session = AsyncMock()

        with patch.object(service, '_get_current_temperature', return_value=23.0), \
             patch.object(service, '_get_total_cooling_capacity', return_value=1000.0), \
             patch.object(service, '_get_cop', return_value=3.5):

            result = await service._calculate_zone_capacity(zone, session)

        # down_thermal = min(400, 50 * (4.0 - 1.0) / 1.0) = min(400, 150) = 150
        assert result["down_adjustable_thermal_kw"] == 150.0


# ==================== TestCalculateCapacity ====================


class TestCalculateCapacity:
    """测试 calculate_capacity 聚合方法"""

    @pytest.mark.asyncio
    async def test_no_calibrated_zones(self, service):
        """无已标定区域时返回空结果"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        with patch("app.services.precool.vpp_capacity.async_session") as mock_async_session:
            mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await service.calculate_capacity()

        assert result["down_adjustable_kw"] == 0.0
        assert result["up_adjustable_kw"] == 0.0
        assert result["zones"] == []
        assert result["T_current"] is None

    @pytest.mark.asyncio
    async def test_aggregates_multiple_zones(self, service):
        """多区域聚合"""
        zone1 = _make_zone(zone_id=1, zone_name="Zone-A")
        zone2 = _make_zone(zone_id=2, zone_name="Zone-B")

        zone1_result = {
            "zone_id": 1, "zone_name": "Zone-A",
            "T_current": 23.0, "headroom_down": 4.0, "headroom_up": 5.0,
            "down_adjustable_thermal_kw": 400.0, "up_adjustable_thermal_kw": 300.0,
            "down_adjustable_kw": 114.29, "up_adjustable_kw": 85.71, "cop": 3.5,
        }
        zone2_result = {
            "zone_id": 2, "zone_name": "Zone-B",
            "T_current": 25.0, "headroom_down": 2.0, "headroom_up": 7.0,
            "down_adjustable_thermal_kw": 200.0, "up_adjustable_thermal_kw": 150.0,
            "down_adjustable_kw": 57.14, "up_adjustable_kw": 42.86, "cop": 3.5,
        }

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [zone1, zone2]
        mock_session.execute.return_value = mock_result

        with patch("app.services.precool.vpp_capacity.async_session") as mock_async_session, \
             patch.object(service, '_calculate_zone_capacity', side_effect=[zone1_result, zone2_result]):
            mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await service.calculate_capacity()

        # 聚合: 114.29 + 57.14 = 171.43
        assert abs(result["down_adjustable_kw"] - 171.43) < 0.01
        # 聚合: 85.71 + 42.86 = 128.57
        assert abs(result["up_adjustable_kw"] - 128.57) < 0.01
        # T_current = max(23.0, 25.0) = 25.0
        assert result["T_current"] == 25.0
        # headroom_down = min(4.0, 2.0) = 2.0
        assert result["headroom_down"] == 2.0
        # headroom_up = min(5.0, 7.0) = 5.0
        assert result["headroom_up"] == 5.0
        assert len(result["zones"]) == 2

    @pytest.mark.asyncio
    async def test_skips_failed_zones(self, service):
        """跳过计算失败的区域"""
        zone1 = _make_zone(zone_id=1, zone_name="Zone-A")
        zone2 = _make_zone(zone_id=2, zone_name="Zone-B")

        zone1_result = {
            "zone_id": 1, "zone_name": "Zone-A",
            "T_current": 23.0, "headroom_down": 4.0, "headroom_up": 5.0,
            "down_adjustable_thermal_kw": 400.0, "up_adjustable_thermal_kw": 300.0,
            "down_adjustable_kw": 114.29, "up_adjustable_kw": 85.71, "cop": 3.5,
        }

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [zone1, zone2]
        mock_session.execute.return_value = mock_result

        # zone2 返回 None（温度不可用）
        with patch("app.services.precool.vpp_capacity.async_session") as mock_async_session, \
             patch.object(service, '_calculate_zone_capacity', side_effect=[zone1_result, None]):
            mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await service.calculate_capacity()

        assert len(result["zones"]) == 1
        assert result["down_adjustable_kw"] == 114.29


# ==================== TestRedisCache ====================


class TestRedisCache:
    """测试 Redis 缓存相关方法"""

    @pytest.mark.asyncio
    async def test_get_cached_capacity_returns_cached_data(self, service):
        """缓存命中时返回缓存数据"""
        cached_data = {"down_adjustable_kw": 100.0, "cached_at": "2026-03-13T10:00:00"}

        with patch("app.services.precool.vpp_capacity.redis_service") as mock_redis:
            mock_redis.get_json = AsyncMock(return_value=cached_data)
            result = await service.get_cached_capacity()

        assert result == cached_data
        mock_redis.get_json.assert_called_once_with(REDIS_KEY)

    @pytest.mark.asyncio
    async def test_get_cached_capacity_returns_none_on_miss(self, service):
        """缓存未命中时返回 None"""
        with patch("app.services.precool.vpp_capacity.redis_service") as mock_redis:
            mock_redis.get_json = AsyncMock(return_value=None)
            result = await service.get_cached_capacity()

        assert result is None

    @pytest.mark.asyncio
    async def test_refresh_capacity_cache_writes_to_redis(self, service):
        """刷新缓存时写入 Redis"""
        calc_result = {
            "down_adjustable_kw": 100.0,
            "up_adjustable_kw": 50.0,
            "cached_at": None,
            "zones": [],
        }

        with patch.object(service, 'calculate_capacity', return_value=calc_result), \
             patch("app.services.precool.vpp_capacity.redis_service") as mock_redis:
            mock_redis.set_json = AsyncMock()
            result = await service.refresh_capacity_cache()

        assert result["cached_at"] is not None
        mock_redis.set_json.assert_called_once()
        call_args = mock_redis.set_json.call_args
        assert call_args[0][0] == REDIS_KEY
        assert call_args[1]["ttl"] == REDIS_TTL


# ==================== TestEdgeCases ====================


class TestEdgeCases:
    """边界情况测试"""

    @pytest.mark.asyncio
    async def test_zone_exception_handled_gracefully(self, service):
        """单区域异常不影响其他区域计算"""
        zone1 = _make_zone(zone_id=1, zone_name="Zone-A")
        zone2 = _make_zone(zone_id=2, zone_name="Zone-B")

        zone2_result = {
            "zone_id": 2, "zone_name": "Zone-B",
            "T_current": 23.0, "headroom_down": 4.0, "headroom_up": 5.0,
            "down_adjustable_thermal_kw": 400.0, "up_adjustable_thermal_kw": 300.0,
            "down_adjustable_kw": 114.29, "up_adjustable_kw": 85.71, "cop": 3.5,
        }

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [zone1, zone2]
        mock_session.execute.return_value = mock_result

        # zone1 抛出异常
        with patch("app.services.precool.vpp_capacity.async_session") as mock_async_session, \
             patch.object(service, '_calculate_zone_capacity', side_effect=[Exception("db error"), zone2_result]):
            mock_async_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await service.calculate_capacity()

        assert len(result["zones"]) == 1
        assert result["zones"][0]["zone_id"] == 2

    def test_constants_are_consistent(self):
        """验证常量一致性"""
        assert TEMP_MAX == 27.0
        assert TEMP_MIN == 18.0
        assert HEADROOM_DOWN_THRESHOLD == 1.0
        assert HEADROOM_UP_THRESHOLD == 0.5
        assert DEFAULT_RESPONSE_WINDOW == 1.0
        assert DEFAULT_LOAD_FACTOR == 0.7
        assert Q_MIN_RATIO == 0.3
        assert DEFAULT_COP == 3.5
        assert REDIS_TTL == 600

    @pytest.mark.asyncio
    async def test_both_directions_zero_when_temp_at_midpoint_with_tiny_c(self, service):
        """极小 C 值时，热容量限制两个方向的可调量"""
        zone = _make_zone(thermal_R=0.05, thermal_C=1.0)
        session = AsyncMock()

        with patch.object(service, '_get_current_temperature', return_value=22.5), \
             patch.object(service, '_get_total_cooling_capacity', return_value=1000.0), \
             patch.object(service, '_get_cop', return_value=3.5):

            result = await service._calculate_zone_capacity(zone, session)

        # C=1.0, headroom_down=4.5, down_thermal = min(400, 1*(4.5-1)/1) = min(400, 3.5) = 3.5
        assert result["down_adjustable_thermal_kw"] == 3.5
        # C=1.0, headroom_up=4.5, up_thermal = min(300, 1*(4.5-0.5)/1) = min(300, 4.0) = 4.0
        assert result["up_adjustable_thermal_kw"] == 4.0
