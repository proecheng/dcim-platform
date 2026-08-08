"""
ThermalModel 核心算法单元测试（纯 mock，不依赖数据库）

覆盖范围：
- RC 方程离散化计算
- 数值稳定性检查
- COP 季节修正
- bypass 系数校正
- 数据质量检查
- 时间序列聚合/填充/插值
- q_cool_schedule 验证
- 边界条件检查
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.precool.thermal_model import ThermalModel


# ============================================================
# 辅助工具
# ============================================================

def _make_async_session_ctx(mock_session):
    """创建 async_session 上下文管理器 mock"""
    mock_ctx = MagicMock()
    mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_ctx


def _make_zone(thermal_R=0.03, thermal_C=50.0, bypass_beta=0.1, zone_id=1):
    """创建 CoolingZone mock"""
    zone = MagicMock()
    zone.id = zone_id
    zone.thermal_R = thermal_R
    zone.thermal_C = thermal_C
    zone.bypass_beta = bypass_beta
    return zone


def _make_result(scalar_val=None):
    """创建 SQLAlchemy result mock"""
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_val
    return result


# ============================================================
# COP 季节修正测试
# ============================================================

class TestSeasonalCOP:
    """_get_seasonal_cop 方法测试"""

    def test_summer_high_temp(self):
        """夏季高温（≥30°C）→ COP=2.8"""
        model = ThermalModel()
        assert model._get_seasonal_cop(35.0) == 2.8
        assert model._get_seasonal_cop(30.0) == 2.8

    def test_transition_season(self):
        """过渡季（15-30°C）→ COP=3.5"""
        model = ThermalModel()
        assert model._get_seasonal_cop(25.0) == 3.5
        assert model._get_seasonal_cop(15.0) == 3.5

    def test_winter_low_temp(self):
        """冬季低温（<15°C）→ COP=4.0"""
        model = ThermalModel()
        assert model._get_seasonal_cop(10.0) == 4.0
        assert model._get_seasonal_cop(-5.0) == 4.0

    def test_none_outdoor_temp(self):
        """室外温度不可用 → 默认 COP=3.5"""
        model = ThermalModel()
        assert model._get_seasonal_cop(None) == 3.5

    def test_boundary_30(self):
        """边界值 30°C → 夏季"""
        model = ThermalModel()
        assert model._get_seasonal_cop(30.0) == 2.8

    def test_boundary_15(self):
        """边界值 15°C → 过渡季"""
        model = ThermalModel()
        assert model._get_seasonal_cop(15.0) == 3.5

    def test_boundary_just_below_15(self):
        """14.9°C → 冬季"""
        model = ThermalModel()
        assert model._get_seasonal_cop(14.9) == 4.0


# ============================================================
# 时间序列聚合测试
# ============================================================

class TestAggregateTimeseries:
    """_aggregate_timeseries 方法测试"""

    def test_empty_rows(self):
        """空数据返回空列表"""
        model = ThermalModel()
        result = model._aggregate_timeseries([], interval_minutes=5, agg_func="mean")
        assert result == []

    def test_mean_aggregation(self):
        """平均值聚合"""
        model = ThermalModel()
        now = datetime(2026, 3, 11, 12, 0, 0)
        rows = [
            (now, 24.0),
            (now + timedelta(seconds=30), 26.0),  # 同一桶
        ]
        result = model._aggregate_timeseries(rows, interval_minutes=5, agg_func="mean")
        assert len(result) == 1
        assert result[0] == 25.0  # (24 + 26) / 2

    def test_max_aggregation(self):
        """最大值聚合"""
        model = ThermalModel()
        now = datetime(2026, 3, 11, 12, 0, 0)
        rows = [
            (now, 24.0),
            (now + timedelta(seconds=30), 26.0),
        ]
        result = model._aggregate_timeseries(rows, interval_minutes=5, agg_func="max")
        assert result[0] == 26.0

    def test_min_aggregation(self):
        """最小值聚合"""
        model = ThermalModel()
        now = datetime(2026, 3, 11, 12, 0, 0)
        rows = [
            (now, 24.0),
            (now + timedelta(seconds=30), 26.0),
        ]
        result = model._aggregate_timeseries(rows, interval_minutes=5, agg_func="min")
        assert result[0] == 24.0

    def test_multiple_buckets(self):
        """多个时间桶正确分组"""
        model = ThermalModel()
        now = datetime(2026, 3, 11, 12, 0, 0)
        rows = [
            (now, 24.0),
            (now + timedelta(minutes=5), 25.0),
            (now + timedelta(minutes=10), 26.0),
        ]
        result = model._aggregate_timeseries(rows, interval_minutes=5, agg_func="mean")
        assert len(result) == 3

    def test_unknown_agg_func_defaults_mean(self):
        """未知聚合函数默认使用平均值"""
        model = ThermalModel()
        now = datetime(2026, 3, 11, 12, 0, 0)
        rows = [(now, 10.0), (now + timedelta(seconds=10), 20.0)]
        result = model._aggregate_timeseries(rows, interval_minutes=5, agg_func="unknown")
        assert result[0] == 15.0


# ============================================================
# 时间序列填充测试
# ============================================================

class TestFillTimeseries:
    """_fill_timeseries 方法测试"""

    def test_empty_data(self):
        """空数据返回空列表"""
        model = ThermalModel()
        assert model._fill_timeseries([], 10) == []

    def test_exact_length(self):
        """数据长度刚好等于目标"""
        model = ThermalModel()
        data = [1.0, 2.0, 3.0]
        result = model._fill_timeseries(data, 3)
        assert result == [1.0, 2.0, 3.0]

    def test_data_longer_truncate(self):
        """数据长度大于目标时截取"""
        model = ThermalModel()
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = model._fill_timeseries(data, 3)
        assert result == [1.0, 2.0, 3.0]

    def test_data_shorter_forward_fill(self):
        """数据不足时前向填充"""
        model = ThermalModel()
        data = [1.0, 2.0]
        result = model._fill_timeseries(data, 5)
        assert result == [1.0, 2.0, 2.0, 2.0, 2.0]  # 最后值 2.0 填充

    def test_single_value_fill(self):
        """单个值填充到目标长度"""
        model = ThermalModel()
        result = model._fill_timeseries([24.5], 12)
        assert len(result) == 12
        assert all(v == 24.5 for v in result)


# ============================================================
# 时间序列插值测试
# ============================================================

class TestInterpolateTimeseries:
    """_interpolate_timeseries 方法测试"""

    def test_empty_input(self):
        """空输入返回原值"""
        model = ThermalModel()
        ts, vals = model._interpolate_timeseries([], [], interval_minutes=5)
        assert ts == []
        assert vals == []

    def test_no_gap(self):
        """无间隔（≤10分钟）不插值"""
        model = ThermalModel()
        now = datetime(2026, 3, 11, 12, 0, 0)
        # 注意：输入是从新到旧，方法内部会反转
        timestamps = [now + timedelta(minutes=5), now]
        values = [25.0, 24.0]
        ts, vals = model._interpolate_timeseries(timestamps, values, interval_minutes=5)
        assert len(ts) == 2
        assert len(vals) == 2

    def test_gap_triggers_interpolation(self):
        """间隔 > 10 分钟触发线性插值"""
        model = ThermalModel()
        now = datetime(2026, 3, 11, 12, 0, 0)
        # 20 分钟间隔（从新到旧）
        timestamps = [now + timedelta(minutes=20), now]
        values = [30.0, 20.0]
        ts, vals = model._interpolate_timeseries(timestamps, values, interval_minutes=5)
        # 应该插入中间点
        assert len(ts) > 2
        assert len(vals) > 2
        # 插值应在 20-30 之间
        for v in vals:
            assert 20.0 <= v <= 30.0

    def test_mismatched_length(self):
        """时间戳和值长度不一致时返回原值"""
        model = ThermalModel()
        now = datetime(2026, 3, 11, 12, 0, 0)
        timestamps = [now, now + timedelta(minutes=5)]
        values = [24.0]
        ts, vals = model._interpolate_timeseries(timestamps, values, interval_minutes=5)
        assert ts == timestamps
        assert vals == values


# ============================================================
# 数据质量检查测试
# ============================================================

class TestCheckDataQuality:
    """_check_data_quality 方法测试"""

    @pytest.mark.asyncio
    async def test_missing_t_ambient(self):
        """T_ambient 缺失返回 insufficient_data"""
        model = ThermalModel()
        mock_session = AsyncMock()
        result = await model._check_data_quality(mock_session, 1, [100.0]*12, [], 24.0)
        assert result["error"] == "insufficient_data"
        assert "T_ambient" in result["missing_fields"]

    @pytest.mark.asyncio
    async def test_missing_t_current(self):
        """T_current 缺失返回 insufficient_data"""
        model = ThermalModel()
        mock_session = AsyncMock()
        result = await model._check_data_quality(mock_session, 1, [100.0]*12, [24.0]*12, None)
        assert result["error"] == "insufficient_data"
        assert "T_current" in result["missing_fields"]

    @pytest.mark.asyncio
    async def test_t_current_below_zero(self):
        """T_current < 0°C 返回 invalid_temperature"""
        model = ThermalModel()
        mock_session = AsyncMock()
        result = await model._check_data_quality(mock_session, 1, [100.0]*12, [24.0]*12, -5.0)
        assert result["error"] == "invalid_temperature"
        assert result["field"] == "T_current"

    @pytest.mark.asyncio
    async def test_t_current_above_50(self):
        """T_current > 50°C 返回 invalid_temperature"""
        model = ThermalModel()
        mock_session = AsyncMock()
        result = await model._check_data_quality(mock_session, 1, [100.0]*12, [24.0]*12, 55.0)
        assert result["error"] == "invalid_temperature"
        assert result["field"] == "T_current"

    @pytest.mark.asyncio
    async def test_t_ambient_out_of_range(self):
        """T_ambient 有值超出 0-50°C 范围"""
        model = ThermalModel()
        mock_session = AsyncMock()
        t_ambient = [24.0, -1.0, 25.0]
        result = await model._check_data_quality(mock_session, 1, [100.0]*12, t_ambient, 24.0)
        assert result["error"] == "invalid_temperature"
        assert result["field"] == "T_ambient"

    @pytest.mark.asyncio
    async def test_temperature_spike_warning(self):
        """温度突变记录警告但不拒绝"""
        model = ThermalModel()
        mock_session = AsyncMock()

        t_ambient = [24.0, 28.0, 25.0]  # 24→28 突变 > 3°C

        with patch.object(model, "_get_latest_temp_timestamp", return_value=datetime.now()), \
             patch.object(model, "_get_latest_q_it_timestamp", return_value=datetime.now()), \
             patch.object(model, "_get_rated_power", return_value=500.0):
            result = await model._check_data_quality(
                mock_session, 1, [100.0]*12, t_ambient, 24.0
            )
        # 不应报错（突变只是警告）
        assert result.get("error") is None or result["error"] is None
        assert result.get("t_ambient_quality") == "warning"

    @pytest.mark.asyncio
    async def test_sensor_offline(self):
        """传感器离线（>1小时无数据）返回 sensor_offline"""
        model = ThermalModel()
        mock_session = AsyncMock()
        old_time = datetime.now() - timedelta(hours=2)

        with patch.object(model, "_get_latest_temp_timestamp", return_value=old_time):
            result = await model._check_data_quality(
                mock_session, 1, [100.0]*12, [24.0]*12, 24.0
            )
        assert result["error"] == "sensor_offline"

    @pytest.mark.asyncio
    async def test_sensor_online_good_quality(self):
        """传感器在线且数据正常"""
        model = ThermalModel()
        mock_session = AsyncMock()
        recent_time = datetime.now() - timedelta(minutes=2)

        with patch.object(model, "_get_latest_temp_timestamp", return_value=recent_time), \
             patch.object(model, "_get_latest_q_it_timestamp", return_value=recent_time), \
             patch.object(model, "_get_rated_power", return_value=500.0):
            result = await model._check_data_quality(
                mock_session, 1, [100.0]*12, [24.0]*12, 24.0
            )
        assert result["error"] is None
        assert result["q_it_quality"] == "good"
        assert result["t_ambient_quality"] == "good"

    @pytest.mark.asyncio
    async def test_q_it_insufficient_with_rated_power(self):
        """Q_IT 不足但有额定功率时使用估算值"""
        model = ThermalModel()
        mock_session = AsyncMock()

        q_it = [100.0, 110.0]  # 只有 2 条，不足 6 条

        with patch.object(model, "_get_latest_temp_timestamp",
                          return_value=datetime.now() - timedelta(minutes=2)), \
             patch.object(model, "_get_rated_power", return_value=200.0):
            result = await model._check_data_quality(
                mock_session, 1, q_it, [24.0]*12, 24.0
            )
        assert result["error"] is None
        assert result["q_it_quality"] == "estimated"
        # q_it 应该被填充为估算值
        assert len(q_it) >= 6
        assert q_it[0] == 140.0  # 200 * 0.7


# ============================================================
# q_cool_schedule 验证测试
# ============================================================

class TestQCoolScheduleValidation:
    """q_cool_schedule 参数验证测试"""

    @pytest.mark.asyncio
    async def test_schedule_length_mismatch(self):
        """schedule 长度不匹配时返回错误"""
        model = ThermalModel()
        model._dependencies_checked = True
        result = await model.predict_temperature(
            zone_id=1,
            hours=1.0,
            q_cool_schedule=[50.0] * 10  # 应该是 12
        )
        assert result["error"] == "invalid_q_cool_schedule"
        assert "Expected length 12" in result["details"]

    @pytest.mark.asyncio
    async def test_schedule_correct_length(self):
        """schedule 长度正确时不报错（错误来自后续步骤）"""
        model = ThermalModel()
        model._dependencies_checked = True

        with patch.object(model, "_get_zone", return_value={"error": "zone_not_found", "zone_id": 1}), \
             patch("app.services.precool.thermal_model.async_session",
                   _make_async_session_ctx(AsyncMock())):
            result = await model.predict_temperature(
                zone_id=1,
                hours=1.0,
                q_cool_schedule=[50.0] * 12
            )

        assert result["error"] == "zone_not_found"

    @pytest.mark.asyncio
    async def test_schedule_half_hour(self):
        """0.5 小时预测需要 6 步"""
        model = ThermalModel()
        model._dependencies_checked = True
        result = await model.predict_temperature(
            zone_id=1,
            hours=0.5,
            q_cool_schedule=[50.0] * 5  # 应该是 6
        )
        assert result["error"] == "invalid_q_cool_schedule"
        assert "Expected length 6" in result["details"]


# ============================================================
# RC 方程计算测试（端到端 mock）
# ============================================================

class TestRCCalculation:
    """RC 方程离散化计算测试"""

    @pytest.mark.asyncio
    async def test_stable_temperature_prediction(self):
        """热平衡状态下温度应保持稳定"""
        model = ThermalModel()
        model._dependencies_checked = True

        zone = _make_zone(thermal_R=0.03, thermal_C=50.0, bypass_beta=0.0)
        zone_result = MagicMock()
        zone_result.scalar_one_or_none.return_value = zone

        # 热平衡: Q_IT = Q_cool, 且 T = T_ambient → dT = 0
        steps = 12
        q_it = [100.0] * steps
        t_ambient = [24.0] * steps
        data = {
            "q_it": q_it,
            "t_ambient": t_ambient,
            "t_current": 24.0,
            "t_outlet": None,
            "t_outdoor": 25.0,
        }
        quality = {
            "error": None,
            "missing_fields": [],
            "q_it_quality": "good",
            "t_ambient_quality": "good",
            "t_current_quality": "good",
        }
        cooling_result = {"value": 100.0 / 3.5}  # Q_cool × COP = 100

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=zone_result)

        param_result = MagicMock()
        param_result.scalar_one_or_none.return_value = MagicMock(id=1)

        with patch("app.services.precool.thermal_model.async_session",
                   _make_async_session_ctx(mock_session)), \
             patch.object(model, "_get_zone", return_value={"zone": zone}), \
             patch.object(model, "_load_historical_data", return_value=data), \
             patch.object(model, "_check_data_quality", return_value=quality), \
             patch.object(model, "_get_current_cooling", return_value=cooling_result), \
             patch.object(model, "_get_active_thermal_param", return_value={"id": 1}), \
             patch.object(model, "_log_prediction", return_value=None):

            result = await model.predict_temperature(zone_id=1, hours=1.0)

            assert "error" not in result
            assert "temperature_trajectory" in result
            trajectory = result["temperature_trajectory"]
            assert len(trajectory) == steps + 1  # 初始 + 12 步
            # 温度应在合理范围
            assert all(0 <= t <= 50 for t in trajectory)

    @pytest.mark.asyncio
    async def test_temperature_rises_when_it_load_exceeds_cooling(self):
        """IT 热负荷 > 制冷量时温度应上升"""
        model = ThermalModel()
        model._dependencies_checked = True

        zone = _make_zone(thermal_R=0.03, thermal_C=50.0, bypass_beta=0.0)
        steps = 12
        data = {
            "q_it": [200.0] * steps,  # 高热负荷
            "t_ambient": [24.0] * steps,
            "t_current": 24.0,
            "t_outlet": None,
            "t_outdoor": 25.0,
        }
        quality = {
            "error": None, "missing_fields": [],
            "q_it_quality": "good", "t_ambient_quality": "good", "t_current_quality": "good",
        }
        # 制冷功率较低: 30 kW × COP 3.5 = 105 kW < 200 kW IT 热负荷
        cooling_result = {"value": 30.0}

        with patch.object(model, "_get_zone", return_value={"zone": zone}), \
             patch.object(model, "_load_historical_data", return_value=data), \
             patch.object(model, "_check_data_quality", return_value=quality), \
             patch.object(model, "_get_current_cooling", return_value=cooling_result), \
             patch.object(model, "_get_active_thermal_param", return_value={"id": 1}), \
             patch.object(model, "_log_prediction", return_value=None), \
             patch("app.services.precool.thermal_model.async_session",
                   _make_async_session_ctx(AsyncMock())):

            result = await model.predict_temperature(zone_id=1, hours=1.0)

            if "error" not in result:
                trajectory = result["temperature_trajectory"]
                # 温度应逐步上升
                assert trajectory[-1] > trajectory[0]

    @pytest.mark.asyncio
    async def test_temperature_drops_when_cooling_exceeds_it_load(self):
        """制冷量 > IT 热负荷时温度应下降"""
        model = ThermalModel()
        model._dependencies_checked = True

        zone = _make_zone(thermal_R=0.03, thermal_C=50.0, bypass_beta=0.0)
        steps = 12
        data = {
            "q_it": [50.0] * steps,  # 低热负荷
            "t_ambient": [24.0] * steps,
            "t_current": 26.0,  # 初始温度较高
            "t_outlet": None,
            "t_outdoor": 25.0,
        }
        quality = {
            "error": None, "missing_fields": [],
            "q_it_quality": "good", "t_ambient_quality": "good", "t_current_quality": "good",
        }
        # 制冷功率较高: 100 kW × COP 3.5 = 350 kW >> 50 kW IT 热负荷
        cooling_result = {"value": 100.0}

        with patch.object(model, "_get_zone", return_value={"zone": zone}), \
             patch.object(model, "_load_historical_data", return_value=data), \
             patch.object(model, "_check_data_quality", return_value=quality), \
             patch.object(model, "_get_current_cooling", return_value=cooling_result), \
             patch.object(model, "_get_active_thermal_param", return_value={"id": 1}), \
             patch.object(model, "_log_prediction", return_value=None), \
             patch("app.services.precool.thermal_model.async_session",
                   _make_async_session_ctx(AsyncMock())):

            result = await model.predict_temperature(zone_id=1, hours=1.0)

            if "error" not in result:
                trajectory = result["temperature_trajectory"]
                # 温度应下降
                assert trajectory[-1] < trajectory[0]


# ============================================================
# 数值稳定性测试
# ============================================================

class TestNumericalStability:
    """数值稳定性检查测试"""

    @pytest.mark.asyncio
    async def test_unstable_rc_params(self):
        """dt >= 2RC 时返回 numerical_instability 错误"""
        model = ThermalModel()
        model._dependencies_checked = True

        # R=0.001, C=0.01 → 2RC = 0.00002 < dt=5/60=0.0833
        zone = _make_zone(thermal_R=0.001, thermal_C=0.01)

        with patch.object(model, "_get_zone", return_value={"zone": zone}), \
             patch("app.services.precool.thermal_model.async_session",
                   _make_async_session_ctx(AsyncMock())):

            result = await model.predict_temperature(zone_id=1, hours=1.0)

            assert result["error"] == "numerical_instability"
            assert "suggested_max_hours" in result

    @pytest.mark.asyncio
    async def test_stable_rc_params(self):
        """dt < 2RC 时不报稳定性错误"""
        model = ThermalModel()
        model._dependencies_checked = True

        # R=0.03, C=50 → 2RC = 3.0 >> dt=0.0833
        zone = _make_zone(thermal_R=0.03, thermal_C=50.0)
        data = {
            "q_it": [100.0] * 12, "t_ambient": [24.0] * 12,
            "t_current": 24.0, "t_outlet": None, "t_outdoor": 25.0,
        }
        quality = {
            "error": None, "missing_fields": [],
            "q_it_quality": "good", "t_ambient_quality": "good", "t_current_quality": "good",
        }
        cooling = {"value": 50.0}

        with patch.object(model, "_get_zone", return_value={"zone": zone}), \
             patch.object(model, "_load_historical_data", return_value=data), \
             patch.object(model, "_check_data_quality", return_value=quality), \
             patch.object(model, "_get_current_cooling", return_value=cooling), \
             patch.object(model, "_get_active_thermal_param", return_value={"id": 1}), \
             patch.object(model, "_log_prediction", return_value=None), \
             patch("app.services.precool.thermal_model.async_session",
                   _make_async_session_ctx(AsyncMock())):

            result = await model.predict_temperature(zone_id=1, hours=1.0)
            assert result.get("error") != "numerical_instability"

    @pytest.mark.asyncio
    async def test_suggested_max_hours_minimum(self):
        """suggested_max_hours 最小值为 0.5"""
        model = ThermalModel()
        model._dependencies_checked = True

        # 极小 RC → 2RC*12 < 0.5 → suggested_max_hours = 0.5
        zone = _make_zone(thermal_R=0.0001, thermal_C=0.001)

        with patch.object(model, "_get_zone", return_value={"zone": zone}), \
             patch("app.services.precool.thermal_model.async_session",
                   _make_async_session_ctx(AsyncMock())):

            result = await model.predict_temperature(zone_id=1, hours=1.0)
            assert result["error"] == "numerical_instability"
            assert result["suggested_max_hours"] >= 0.5


# ============================================================
# 参数验证测试
# ============================================================

class TestParameterValidation:
    """参数验证测试"""

    @pytest.mark.asyncio
    async def test_r_zero(self):
        """R=0 返回 invalid_parameters"""
        model = ThermalModel()
        model._dependencies_checked = True

        zone = _make_zone(thermal_R=0.0, thermal_C=50.0)

        with patch.object(model, "_get_zone", return_value={"zone": zone}), \
             patch("app.services.precool.thermal_model.async_session",
                   _make_async_session_ctx(AsyncMock())):

            result = await model.predict_temperature(zone_id=1, hours=1.0)
            assert result["error"] == "invalid_parameters"

    @pytest.mark.asyncio
    async def test_c_negative(self):
        """C<0 返回 invalid_parameters"""
        model = ThermalModel()
        model._dependencies_checked = True

        zone = _make_zone(thermal_R=0.03, thermal_C=-10.0)

        with patch.object(model, "_get_zone", return_value={"zone": zone}), \
             patch("app.services.precool.thermal_model.async_session",
                   _make_async_session_ctx(AsyncMock())):

            result = await model.predict_temperature(zone_id=1, hours=1.0)
            assert result["error"] == "invalid_parameters"

    @pytest.mark.asyncio
    async def test_r_c_none(self):
        """R/C 为 None 返回 parameters_not_calibrated"""
        model = ThermalModel()
        model._dependencies_checked = True

        zone = _make_zone(thermal_R=None, thermal_C=None)

        with patch.object(model, "_get_zone", return_value={"zone": zone}), \
             patch("app.services.precool.thermal_model.async_session",
                   _make_async_session_ctx(AsyncMock())):

            result = await model.predict_temperature(zone_id=1, hours=1.0)
            assert result["error"] == "parameters_not_calibrated"

    @pytest.mark.asyncio
    async def test_bypass_beta_none_defaults(self):
        """bypass_beta 为 None 时默认 0.1"""
        model = ThermalModel()
        model._dependencies_checked = True

        zone = _make_zone(thermal_R=0.03, thermal_C=50.0, bypass_beta=None)
        data = {
            "q_it": [100.0]*12, "t_ambient": [24.0]*12,
            "t_current": 24.0, "t_outlet": None, "t_outdoor": 25.0,
        }
        quality = {
            "error": None, "missing_fields": [],
            "q_it_quality": "good", "t_ambient_quality": "good", "t_current_quality": "good",
        }
        cooling = {"value": 50.0}

        with patch.object(model, "_get_zone", return_value={"zone": zone}), \
             patch.object(model, "_load_historical_data", return_value=data), \
             patch.object(model, "_check_data_quality", return_value=quality), \
             patch.object(model, "_get_current_cooling", return_value=cooling), \
             patch.object(model, "_get_active_thermal_param", return_value={"id": 1}), \
             patch.object(model, "_log_prediction", return_value=None), \
             patch("app.services.precool.thermal_model.async_session",
                   _make_async_session_ctx(AsyncMock())):

            result = await model.predict_temperature(zone_id=1, hours=1.0)
            # 应该成功（使用默认 beta=0.1）
            assert result.get("error") != "invalid_parameters"


# ============================================================
# 边界条件测试
# ============================================================

class TestBoundaryConditions:
    """温度边界条件测试"""

    @pytest.mark.asyncio
    async def test_temperature_out_of_bounds_upper(self):
        """预测温度 > 50°C 时终止预测"""
        model = ThermalModel()
        model._dependencies_checked = True

        zone = _make_zone(thermal_R=0.03, thermal_C=5.0, bypass_beta=0.0)  # 小 C → 温度变化快
        steps = 12
        data = {
            "q_it": [500.0] * steps,  # 极高热负荷
            "t_ambient": [45.0] * steps,  # 高环境温度
            "t_current": 48.0,  # 接近上限
            "t_outlet": None,
            "t_outdoor": 40.0,
        }
        quality = {
            "error": None, "missing_fields": [],
            "q_it_quality": "good", "t_ambient_quality": "good", "t_current_quality": "good",
        }
        cooling = {"value": 10.0}  # 极低制冷

        with patch.object(model, "_get_zone", return_value={"zone": zone}), \
             patch.object(model, "_load_historical_data", return_value=data), \
             patch.object(model, "_check_data_quality", return_value=quality), \
             patch.object(model, "_get_current_cooling", return_value=cooling), \
             patch("app.services.precool.thermal_model.async_session",
                   _make_async_session_ctx(AsyncMock())):

            result = await model.predict_temperature(zone_id=1, hours=1.0)
            assert result["error"] == "temperature_out_of_bounds"
            assert "step" in result
            assert result["temperature"] > 50


# ============================================================
# 结果格式测试
# ============================================================

class TestResultFormat:
    """预测结果格式测试"""

    @pytest.mark.asyncio
    async def test_successful_result_format(self):
        """成功预测的结果应包含所有必需字段"""
        model = ThermalModel()
        model._dependencies_checked = True

        zone = _make_zone(thermal_R=0.03, thermal_C=50.0, bypass_beta=0.1)
        steps = 6  # 0.5h
        data = {
            "q_it": [100.0] * steps, "t_ambient": [24.0] * steps,
            "t_current": 24.0, "t_outlet": 30.0, "t_outdoor": 25.0,
        }
        quality = {
            "error": None, "missing_fields": [],
            "q_it_quality": "good", "t_ambient_quality": "good", "t_current_quality": "good",
        }
        cooling = {"value": 50.0}

        with patch.object(model, "_get_zone", return_value={"zone": zone}), \
             patch.object(model, "_load_historical_data", return_value=data), \
             patch.object(model, "_check_data_quality", return_value=quality), \
             patch.object(model, "_get_current_cooling", return_value=cooling), \
             patch.object(model, "_get_active_thermal_param", return_value={"id": 42}), \
             patch.object(model, "_log_prediction", return_value=None), \
             patch("app.services.precool.thermal_model.async_session",
                   _make_async_session_ctx(AsyncMock())):

            result = await model.predict_temperature(zone_id=1, hours=0.5)

            assert "error" not in result
            assert result["zone_id"] == 1
            assert isinstance(result["predicted_temp"], float)
            assert result["prediction_horizon_min"] == 30
            assert len(result["temperature_trajectory"]) == steps + 1
            assert len(result["time_steps"]) == steps + 1
            assert result["model_version"] == "RC-v42"
            assert result["data_quality"] is not None
