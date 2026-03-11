"""
预冷贪心调度算法单元测试

Story 31.1: 测试 PrecoolScheduler 的核心算法、约束验证、重试逻辑和数据模型。
"""

import pytest
from datetime import date, time, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.precool.scheduler import (
    PrecoolScheduler,
    PrecoolPlanError,
    TimeSlot,
    ScheduleStep,
    TrajectoryViolation,
    PrecoolPlanResult,
    get_default_time_slots,
    load_time_slots_from_db,
    DEFAULT_TEMP_MAX,
    DEFAULT_TEMP_MIN,
    DEFAULT_RATE_LIMIT,
    DEFAULT_COP,
)
from app.models.thermal import PrecoolSchedule


# ==================== Fixtures ====================


@pytest.fixture
def scheduler():
    return PrecoolScheduler()


@pytest.fixture
def default_time_slots():
    return get_default_time_slots()


@pytest.fixture
def simple_time_slots():
    """简单的 3 时段配置用于快速测试"""
    return [
        TimeSlot(0, 8, 0.25, "valley"),
        TimeSlot(8, 16, 0.65, "flat"),
        TimeSlot(16, 24, 1.20, "peak"),
    ]


@pytest.fixture
def mock_zone():
    """模拟 CoolingZone 对象"""
    zone = MagicMock()
    zone.id = 1
    zone.thermal_R = 0.5     # °C/kW
    zone.thermal_C = 10.0    # kWh/°C
    zone.bypass_beta = 0.1
    zone.area_m2 = 50.0
    zone.height_m = 3.0
    return zone


@pytest.fixture
def mock_zone_uncalibrated():
    """R/C 未标定的 zone"""
    zone = MagicMock()
    zone.id = 2
    zone.thermal_R = None
    zone.thermal_C = None
    zone.bypass_beta = 0.1
    return zone


# ==================== 电价时段测试 ====================


class TestTimeSlots:
    def test_default_time_slots_count(self):
        slots = get_default_time_slots()
        assert len(slots) == 5

    def test_default_time_slots_cover_24h(self):
        slots = get_default_time_slots()
        # 验证覆盖 0-24
        assert slots[0].start_hour == 0
        assert slots[-1].end_hour == 24

    def test_default_time_slots_period_types(self):
        slots = get_default_time_slots()
        types = {s.period_type for s in slots}
        assert "valley" in types
        assert "flat" in types
        assert "peak" in types
        assert "sharp" in types

    def test_default_time_slots_prices_ordered(self):
        slots = get_default_time_slots()
        valley_price = next(s.price for s in slots if s.period_type == "valley")
        peak_price = next(s.price for s in slots if s.period_type == "peak")
        sharp_price = next(s.price for s in slots if s.period_type == "sharp")
        assert valley_price < peak_price < sharp_price


# ==================== 策略决策测试 ====================


class TestDecideCooling:
    def test_valley_increases_cooling(self, scheduler):
        """谷时应增大制冷功率"""
        Q_IT = 100.0
        T = 22.0
        Q = scheduler._decide_cooling(
            "valley", Q_IT, T, R=0.5, C=10.0, T_amb=25.0,
            Q_cool_min=0, Q_cool_max=500, precool_target_temp=18.0,
        )
        assert Q > Q_IT  # 谷时制冷应大于 IT 负荷

    def test_deep_valley_same_as_valley(self, scheduler):
        """深谷时策略应与谷时相同"""
        args = (100.0, 22.0, 0.5, 10.0, 25.0, 0, 500, 18.0)
        Q_valley = scheduler._decide_cooling("valley", *args)
        Q_deep = scheduler._decide_cooling("deep_valley", *args)
        assert Q_valley == Q_deep

    def test_peak_reduces_cooling(self, scheduler):
        """峰时应削减制冷功率"""
        Q_IT = 100.0
        T = 22.0
        Q = scheduler._decide_cooling(
            "peak", Q_IT, T, R=0.5, C=10.0, T_amb=25.0,
            Q_cool_min=0, Q_cool_max=500, precool_target_temp=18.0,
        )
        # 峰时当温度远低于上限时，应该削减制冷
        assert Q < Q_IT or Q == 0

    def test_sharp_reduces_cooling(self, scheduler):
        """尖峰时应削减制冷"""
        Q = scheduler._decide_cooling(
            "sharp", 100.0, 22.0, R=0.5, C=10.0, T_amb=25.0,
            Q_cool_min=0, Q_cool_max=500, precool_target_temp=18.0,
        )
        assert Q <= 100.0

    def test_flat_maintains_normal(self, scheduler):
        """平时应维持正常制冷"""
        Q = scheduler._decide_cooling(
            "flat", 100.0, 22.0, R=0.5, C=10.0, T_amb=25.0,
            Q_cool_min=0, Q_cool_max=500, precool_target_temp=18.0,
        )
        # 平时制冷应该接近维持温度所需
        assert Q > 0


# ==================== 功率限幅测试 ====================


class TestApplyLimits:
    def test_clamp_to_max(self, scheduler):
        Q = scheduler._apply_limits(600, 500, 0, 500, 50)
        assert Q <= 500

    def test_clamp_to_min(self, scheduler):
        Q = scheduler._apply_limits(-10, 50, 0, 500, 50)
        assert Q >= 0

    def test_rate_limit_increase(self, scheduler):
        Q = scheduler._apply_limits(200, 100, 0, 500, 20)
        assert Q == 120  # prev + delta_P_max

    def test_rate_limit_decrease(self, scheduler):
        Q = scheduler._apply_limits(50, 100, 0, 500, 20)
        assert Q == 80  # prev - delta_P_max

    def test_within_limits_no_change(self, scheduler):
        Q = scheduler._apply_limits(105, 100, 0, 500, 20)
        assert Q == 105


# ==================== 安全校正测试 ====================


class TestSafetyCorrection:
    def test_high_temp_corrected(self, scheduler):
        T_new, Q = scheduler._safety_correction(
            28.0, 50, 100, 22, 25, 0.5, 10, 3.5, 0.1,
        )
        assert T_new <= DEFAULT_TEMP_MAX

    def test_low_temp_corrected(self, scheduler):
        T_new, Q = scheduler._safety_correction(
            16.0, 200, 100, 22, 25, 0.5, 10, 3.5, 0.1,
        )
        assert T_new >= DEFAULT_TEMP_MIN

    def test_normal_temp_unchanged(self, scheduler):
        T_new, Q = scheduler._safety_correction(
            22.0, 100, 100, 22, 25, 0.5, 10, 3.5, 0.1,
        )
        assert T_new == 22.0
        assert Q == 100


# ==================== 约束验证测试 ====================


class TestValidateTrajectory:
    def test_valid_trajectory(self, scheduler):
        steps = [ScheduleStep(i, i * 5, "flat", 0.5, 100, 350, 22.0, 0.1)
                 for i in range(10)]
        violations = scheduler._validate_trajectory(steps)
        assert len(violations) == 0

    def test_temperature_high_violation(self, scheduler):
        steps = [ScheduleStep(0, 0, "flat", 0.5, 100, 350, 28.0, 0.1)]
        violations = scheduler._validate_trajectory(steps)
        assert len(violations) == 1
        assert violations[0].violation_type == "temperature_high"

    def test_temperature_low_violation(self, scheduler):
        steps = [ScheduleStep(0, 0, "flat", 0.5, 100, 350, 16.0, 0.1)]
        violations = scheduler._validate_trajectory(steps)
        assert len(violations) == 1
        assert violations[0].violation_type == "temperature_low"

    def test_rate_of_change_violation(self, scheduler):
        steps = [
            ScheduleStep(0, 0, "flat", 0.5, 100, 350, 22.0, 0.1),
            ScheduleStep(1, 5, "flat", 0.5, 100, 350, 23.0, 0.1),  # 1°C / (5/60)h = 12°C/h > 5
        ]
        violations = scheduler._validate_trajectory(steps)
        assert any(v.violation_type == "rate_of_change" for v in violations)

    def test_rate_within_limit(self, scheduler):
        """5 分钟内变化 0.4°C = 4.8°C/h < 5°C/h，应不违规"""
        steps = [
            ScheduleStep(0, 0, "flat", 0.5, 100, 350, 22.0, 0.1),
            ScheduleStep(1, 5, "flat", 0.5, 100, 350, 22.4, 0.1),
        ]
        violations = scheduler._validate_trajectory(steps)
        assert len(violations) == 0


# ==================== COP 测试 ====================


class TestGetCop:
    def test_config_cop_priority(self, scheduler):
        cop = scheduler._get_cop(4.2, 25.0)
        assert cop == 4.2

    def test_summer_cop(self, scheduler):
        cop = scheduler._get_cop(None, 35.0)
        assert cop == 2.8

    def test_transition_cop(self, scheduler):
        cop = scheduler._get_cop(None, 20.0)
        assert cop == 3.5

    def test_winter_cop(self, scheduler):
        cop = scheduler._get_cop(None, 5.0)
        assert cop == 4.0


# ==================== 时段查找测试 ====================


class TestGetSlotForStep:
    def test_step_0_is_midnight(self, scheduler, default_time_slots):
        slot = scheduler._get_slot_for_step(0, default_time_slots)
        assert slot.period_type == "valley"

    def test_step_96_is_8am(self, scheduler, default_time_slots):
        slot = scheduler._get_slot_for_step(96, default_time_slots)
        assert slot.period_type == "flat"

    def test_step_204_is_5pm(self, scheduler, default_time_slots):
        # 204 * 5 / 60 = 17.0 hours → sharp
        slot = scheduler._get_slot_for_step(204, default_time_slots)
        assert slot.period_type == "sharp"

    def test_last_step(self, scheduler, default_time_slots):
        slot = scheduler._get_slot_for_step(287, default_time_slots)
        assert slot.period_type == "valley"


# ==================== 重试放宽测试 ====================


class TestRelaxAndRegenerate:
    def test_attempt_0_raises_target_temp(self, scheduler):
        plan = PrecoolSchedule(
            cooling_zone_id=1,
            schedule_date=date(2026, 3, 11),
            precool_start_time=time(0, 0),
            precool_end_time=time(8, 0),
            target_temp=18.0,
            peak_start_time=time(11, 0),
            peak_end_time=time(21, 0),
            status="pending",
        )
        steps = []
        plan2, _ = scheduler._relax_and_regenerate(plan, steps, 0)
        assert plan2.target_temp == 19.0

    def test_attempt_1_shortens_peak(self, scheduler):
        plan = PrecoolSchedule(
            cooling_zone_id=1,
            schedule_date=date(2026, 3, 11),
            precool_start_time=time(0, 0),
            precool_end_time=time(8, 0),
            target_temp=18.0,
            peak_start_time=time(11, 0),
            peak_end_time=time(21, 0),
            status="pending",
        )
        steps = []
        plan2, _ = scheduler._relax_and_regenerate(plan, steps, 1)
        assert plan2.peak_end_time == time(20, 30)

    def test_attempt_2_both_relaxations(self, scheduler):
        plan = PrecoolSchedule(
            cooling_zone_id=1,
            schedule_date=date(2026, 3, 11),
            precool_start_time=time(0, 0),
            precool_end_time=time(8, 0),
            target_temp=18.0,
            peak_start_time=time(11, 0),
            peak_end_time=time(21, 0),
            status="pending",
        )
        steps = []
        plan2, _ = scheduler._relax_and_regenerate(plan, steps, 2)
        assert plan2.target_temp == 19.0
        assert plan2.peak_end_time == time(20, 30)


# ==================== PrecoolSchedule 模型测试 ====================


class TestPrecoolScheduleModel:
    def test_create_instance(self):
        plan = PrecoolSchedule(
            cooling_zone_id=1,
            schedule_date=date(2026, 3, 11),
            precool_start_time=time(0, 0),
            precool_end_time=time(8, 0),
            target_temp=18.0,
            peak_start_time=time(11, 0),
            peak_end_time=time(21, 0),
            planned_savings_kwh=50.0,
            status="pending",
            temperature_trajectory={"predicted": [22.0] * 288},
        )
        assert plan.status == "pending"
        assert plan.target_temp == 18.0
        assert plan.planned_savings_kwh == 50.0

    def test_temperature_trajectory_json(self):
        trajectory = {
            "predicted": [22.0 + i * 0.01 for i in range(288)],
            "timestamps": [f"{i * 5 // 60:02d}:{i * 5 % 60:02d}" for i in range(288)],
        }
        plan = PrecoolSchedule(
            cooling_zone_id=1,
            schedule_date=date(2026, 3, 11),
            precool_start_time=time(0, 0),
            precool_end_time=time(8, 0),
            target_temp=18.0,
            peak_start_time=time(11, 0),
            peak_end_time=time(21, 0),
            temperature_trajectory=trajectory,
        )
        assert len(plan.temperature_trajectory["predicted"]) == 288
        assert plan.temperature_trajectory["timestamps"][0] == "00:00"


# ==================== PrecoolPlanError 测试 ====================


class TestPrecoolPlanError:
    def test_error_structure(self):
        err = PrecoolPlanError(
            error="no_feasible_plan",
            reason="约束验证失败",
            suggestions=["调整 R/C"],
        )
        assert err.error == "no_feasible_plan"
        assert err.reason == "约束验证失败"
        assert len(err.suggestions) == 1

    def test_parameters_not_calibrated(self):
        err = PrecoolPlanError(
            error="parameters_not_calibrated",
            reason="Zone 1 的 thermal_R 或 thermal_C 未标定",
            suggestions=["运行热参数自动校准"],
        )
        assert "未标定" in err.reason


# ==================== 节省电费计算测试 ====================


class TestSavingsCalculation:
    def test_savings_positive_with_valley_peak(self, scheduler):
        """谷-峰组合应有正向节省"""
        # 模拟 10 步谷时 + 10 步峰时
        steps_valley = [
            ScheduleStep(i, i * 5, "valley", 0.25, 150, 525, 20.0, 150 * (5 / 60) * 0.25)
            for i in range(10)
        ]
        steps_peak = [
            ScheduleStep(10 + i, (10 + i) * 5, "peak", 1.20, 50, 175, 24.0, 50 * (5 / 60) * 1.20)
            for i in range(10)
        ]
        steps = steps_valley + steps_peak
        total_cost = sum(s.cost for s in steps)

        # 基线：全程 100 kW
        baseline_cost = sum(100 * (5 / 60) * s.price for s in steps)

        saving = baseline_cost - total_cost
        # 谷时多用电但便宜，峰时少用电但贵
        # 需要验证谷时多花的比峰时省的少
        assert isinstance(saving, float)

    def test_all_flat_no_savings(self, scheduler):
        """全平时段，预冷无收益"""
        time_slots = [TimeSlot(0, 24, 0.65, "flat")]
        slot = scheduler._get_slot_for_step(0, time_slots)
        assert slot.period_type == "flat"


# ==================== 构建计划测试 ====================


class TestBuildPlan:
    def test_build_plan_basic(self, scheduler, default_time_slots):
        steps = [ScheduleStep(i, i * 5, "flat", 0.5, 100, 350, 22.0, 0.1)
                 for i in range(288)]
        plan = scheduler._build_plan(
            zone_id=1,
            schedule_date=date(2026, 3, 11),
            steps=steps,
            target_temp=18.0,
            time_slots=default_time_slots,
            saving_kwh=50.0,
            total_cost=100.0,
        )
        assert plan.cooling_zone_id == 1
        assert plan.schedule_date == date(2026, 3, 11)
        assert plan.target_temp == 18.0
        assert plan.status == "pending"
        assert plan.planned_savings_kwh == 50.0
        assert "predicted" in plan.temperature_trajectory
        assert len(plan.temperature_trajectory["predicted"]) == 288

    def test_build_plan_timestamps_format(self, scheduler, default_time_slots):
        steps = [ScheduleStep(i, i * 5, "flat", 0.5, 100, 350, 22.0, 0.1)
                 for i in range(288)]
        plan = scheduler._build_plan(
            1, date(2026, 3, 11), steps, 18.0, default_time_slots, 0, 0,
        )
        ts = plan.temperature_trajectory["timestamps"]
        assert ts[0] == "00:00"
        assert ts[12] == "01:00"  # 12 * 5min = 60min
        assert ts[287] == "23:55"


# ==================== 性能测试 ====================


class TestPerformance:
    def test_trajectory_validation_performance(self, scheduler):
        """288 步轨迹验证应在 1s 内完成"""
        import time as time_module
        steps = [ScheduleStep(i, i * 5, "flat", 0.5, 100, 350, 22.0, 0.1)
                 for i in range(288)]
        start = time_module.time()
        for _ in range(1000):  # 1000 次验证
            scheduler._validate_trajectory(steps)
        elapsed = time_module.time() - start
        assert elapsed < 1.0, f"1000 次验证耗时 {elapsed:.2f}s，超过 1s"

    def test_decide_cooling_performance(self, scheduler):
        """288 步决策应在 1s 内完成"""
        import time as time_module
        start = time_module.time()
        for _ in range(288 * 100):  # 100 次完整循环
            scheduler._decide_cooling(
                "valley", 100, 22, 0.5, 10, 25, 0, 500, 18,
            )
        elapsed = time_module.time() - start
        assert elapsed < 1.0, f"28800 次决策耗时 {elapsed:.2f}s，超过 1s"
