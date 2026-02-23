"""告警引擎单元测试 — Story 5.2"""

import time
import pytest
from app.engines.alarm_engine import AlarmEngine, ThresholdCache


@pytest.fixture
def engine():
    """创建测试用告警引擎"""
    e = AlarmEngine()
    e._loaded = True
    return e


@pytest.fixture
def sample_thresholds():
    """示例 4 级阈值配置（点位 100）"""
    return [
        ThresholdCache(
            id=1,
            point_id=100,
            threshold_type="high_high",
            threshold_value=50.0,
            alarm_level="critical",
            alarm_message="温度超高",
            delay_seconds=0,
            dead_band=0,
            priority=4,
        ),
        ThresholdCache(
            id=2,
            point_id=100,
            threshold_type="high",
            threshold_value=40.0,
            alarm_level="major",
            alarm_message="温度偏高",
            delay_seconds=0,
            dead_band=0,
            priority=3,
        ),
        ThresholdCache(
            id=3,
            point_id=100,
            threshold_type="low",
            threshold_value=10.0,
            alarm_level="minor",
            alarm_message="温度偏低",
            delay_seconds=0,
            dead_band=0,
            priority=2,
        ),
        ThresholdCache(
            id=4,
            point_id=100,
            threshold_type="low_low",
            threshold_value=5.0,
            alarm_level="info",
            alarm_message="温度超低",
            delay_seconds=0,
            dead_band=0,
            priority=1,
        ),
    ]


class TestEvaluate:
    """测试阈值检测"""

    def test_high_high_trigger(self, engine, sample_thresholds):
        """值超过 high_high 阈值应触发 critical 告警"""
        engine._thresholds = {100: sample_thresholds}
        results = engine.evaluate(100, 55.0, "AI")
        levels = [r.alarm_level for r in results]
        assert "critical" in levels

    def test_high_trigger(self, engine, sample_thresholds):
        """值超过 high 阈值应触发 major 告警"""
        engine._thresholds = {100: sample_thresholds}
        results = engine.evaluate(100, 42.0, "AI")
        levels = [r.alarm_level for r in results]
        assert "major" in levels

    def test_low_trigger(self, engine, sample_thresholds):
        """值低于 low 阈值应触发 minor 告警"""
        engine._thresholds = {100: sample_thresholds}
        results = engine.evaluate(100, 8.0, "AI")
        levels = [r.alarm_level for r in results]
        assert "minor" in levels

    def test_low_low_trigger(self, engine, sample_thresholds):
        """值低于 low_low 阈值应触发 info 告警"""
        engine._thresholds = {100: sample_thresholds}
        results = engine.evaluate(100, 3.0, "AI")
        levels = [r.alarm_level for r in results]
        assert "info" in levels

    def test_normal_no_trigger(self, engine, sample_thresholds):
        """正常值不应触发告警"""
        engine._thresholds = {100: sample_thresholds}
        results = engine.evaluate(100, 25.0, "AI")
        assert len(results) == 0

    def test_equal_trigger(self, engine):
        """equal 类型阈值检测"""
        engine._thresholds = {
            200: [
                ThresholdCache(
                    id=10,
                    point_id=200,
                    threshold_type="equal",
                    threshold_value=1.0,
                    alarm_level="major",
                    alarm_message="状态异常",
                    delay_seconds=0,
                    dead_band=0,
                    priority=3,
                ),
            ]
        }
        results = engine.evaluate(200, 1.0, "DI")
        assert len(results) == 1
        assert results[0].alarm_level == "major"

    def test_change_trigger(self, engine):
        """change 类型阈值检测 — 变化量超过阈值"""
        engine._thresholds = {
            500: [
                ThresholdCache(
                    id=50,
                    point_id=500,
                    threshold_type="change",
                    threshold_value=5.0,
                    alarm_level="minor",
                    alarm_message="变化过大",
                    delay_seconds=0,
                    dead_band=0,
                    priority=2,
                ),
            ]
        }
        # 首次无前值，不触发
        results1 = engine.evaluate(500, 20.0, "AI")
        assert len(results1) == 0
        # 清除风暴防护
        engine._last_alarm_time.clear()
        # 变化量 10 > 5，应触发
        results2 = engine.evaluate(500, 30.0, "AI")
        assert len(results2) == 1
        assert results2[0].threshold_type == "change"

    def test_change_no_trigger_small_delta(self, engine):
        """change 类型 — 变化量小于阈值不触发"""
        engine._thresholds = {
            500: [
                ThresholdCache(
                    id=50,
                    point_id=500,
                    threshold_type="change",
                    threshold_value=5.0,
                    alarm_level="minor",
                    alarm_message="变化过大",
                    delay_seconds=0,
                    dead_band=0,
                    priority=2,
                ),
            ]
        }
        engine.evaluate(500, 20.0, "AI")
        engine._last_alarm_time.clear()
        results = engine.evaluate(500, 22.0, "AI")
        assert len(results) == 0

    def test_no_thresholds_no_trigger(self, engine):
        """无阈值配置的点位不触发"""
        results = engine.evaluate(999, 100.0, "AI")
        assert len(results) == 0

    def test_not_loaded_no_trigger(self):
        """引擎未加载时不触发"""
        e = AlarmEngine()
        e._thresholds = {
            100: [
                ThresholdCache(
                    id=1,
                    point_id=100,
                    threshold_type="high",
                    threshold_value=40.0,
                    alarm_level="major",
                    alarm_message="test",
                    delay_seconds=0,
                    dead_band=0,
                    priority=3,
                ),
            ]
        }
        results = e.evaluate(100, 50.0, "AI")
        assert len(results) == 0


class TestStormProtection:
    """测试风暴防护"""

    def test_suppress_within_60s(self, engine, sample_thresholds):
        """同一点位+阈值 60 秒内第二次越限应被抑制"""
        engine._thresholds = {100: sample_thresholds}
        results1 = engine.evaluate(100, 55.0, "AI")
        assert len(results1) > 0
        # 立即再次检测 — 应被抑制
        results2 = engine.evaluate(100, 56.0, "AI")
        assert len(results2) == 0

    def test_allow_after_60s(self, engine, sample_thresholds):
        """60 秒后应允许再次触发"""
        engine._thresholds = {100: sample_thresholds}
        results1 = engine.evaluate(100, 55.0, "AI")
        assert len(results1) > 0
        # 模拟 61 秒后（清除所有风暴时间戳）
        for key in list(engine._last_alarm_time.keys()):
            engine._last_alarm_time[key] = time.time() - 61
        results2 = engine.evaluate(100, 55.0, "AI")
        assert len(results2) > 0

    def test_different_points_independent(self, engine):
        """不同点位的风暴防护互不影响"""
        th_a = [
            ThresholdCache(
                id=1,
                point_id=100,
                threshold_type="high",
                threshold_value=40.0,
                alarm_level="major",
                alarm_message="A高",
                delay_seconds=0,
                dead_band=0,
                priority=3,
            )
        ]
        th_b = [
            ThresholdCache(
                id=2,
                point_id=200,
                threshold_type="high",
                threshold_value=40.0,
                alarm_level="major",
                alarm_message="B高",
                delay_seconds=0,
                dead_band=0,
                priority=3,
            )
        ]
        engine._thresholds = {100: th_a, 200: th_b}
        r1 = engine.evaluate(100, 50.0, "AI")
        assert len(r1) == 1
        # 点位 200 不受点位 100 风暴影响
        r2 = engine.evaluate(200, 50.0, "AI")
        assert len(r2) == 1


class TestDeadBand:
    """测试死区回差"""

    def test_dead_band_no_retrigger(self, engine):
        """触发后值仍在死区范围内不应重复触发"""
        engine._thresholds = {
            300: [
                ThresholdCache(
                    id=20,
                    point_id=300,
                    threshold_type="high",
                    threshold_value=40.0,
                    alarm_level="major",
                    alarm_message="温度偏高",
                    delay_seconds=0,
                    dead_band=2.0,
                    priority=3,
                ),
            ]
        }
        # 首次越限触发
        results1 = engine.evaluate(300, 45.0, "AI")
        assert len(results1) == 1
        # 清除风暴防护以测试死区
        engine._last_alarm_time.clear()
        # 值仍高于阈值但在死区内 — 不应触发
        results2 = engine.evaluate(300, 41.0, "AI")
        assert len(results2) == 0

    def test_dead_band_recovery_retrigger(self, engine):
        """值回到安全区域后再次越限应触发"""
        engine._thresholds = {
            300: [
                ThresholdCache(
                    id=20,
                    point_id=300,
                    threshold_type="high",
                    threshold_value=40.0,
                    alarm_level="major",
                    alarm_message="温度偏高",
                    delay_seconds=0,
                    dead_band=2.0,
                    priority=3,
                ),
            ]
        }
        engine.evaluate(300, 45.0, "AI")
        engine._last_alarm_time.clear()
        # 值回到安全区域（< 40 - 2 = 38）
        engine.evaluate(300, 37.0, "AI")
        engine._last_alarm_time.clear()
        # 再次越限 — 应触发
        results = engine.evaluate(300, 45.0, "AI")
        assert len(results) == 1

    def test_dead_band_low_threshold(self, engine):
        """低限死区：触发后需回到 threshold + dead_band 以上才能恢复"""
        engine._thresholds = {
            300: [
                ThresholdCache(
                    id=21,
                    point_id=300,
                    threshold_type="low",
                    threshold_value=10.0,
                    alarm_level="minor",
                    alarm_message="温度偏低",
                    delay_seconds=0,
                    dead_band=2.0,
                    priority=2,
                ),
            ]
        }
        # 首次越限触发
        results1 = engine.evaluate(300, 8.0, "AI")
        assert len(results1) == 1
        engine._last_alarm_time.clear()
        # 值仍低于阈值，在死区内 — 不应触发
        results2 = engine.evaluate(300, 9.0, "AI")
        assert len(results2) == 0
        # 值回到安全区域（> 10 + 2 = 12）
        engine.evaluate(300, 13.0, "AI")
        engine._last_alarm_time.clear()
        # 再次越限 — 应触发
        results3 = engine.evaluate(300, 8.0, "AI")
        assert len(results3) == 1


class TestDelaySeconds:
    """测试延迟触发"""

    def test_delay_not_trigger_immediately(self, engine):
        """首次越限不应立即触发（开始计时）"""
        engine._thresholds = {
            400: [
                ThresholdCache(
                    id=30,
                    point_id=400,
                    threshold_type="high",
                    threshold_value=40.0,
                    alarm_level="major",
                    alarm_message="温度偏高",
                    delay_seconds=10,
                    dead_band=0,
                    priority=3,
                ),
            ]
        }
        results = engine.evaluate(400, 45.0, "AI")
        assert len(results) == 0
        assert (400, 30) in engine._delay_first_exceed

    def test_delay_trigger_after_elapsed(self, engine):
        """持续越限超过 delay_seconds 后应触发"""
        engine._thresholds = {
            400: [
                ThresholdCache(
                    id=30,
                    point_id=400,
                    threshold_type="high",
                    threshold_value=40.0,
                    alarm_level="major",
                    alarm_message="温度偏高",
                    delay_seconds=10,
                    dead_band=0,
                    priority=3,
                ),
            ]
        }
        engine.evaluate(400, 45.0, "AI")
        # 模拟 11 秒后
        engine._delay_first_exceed[(400, 30)] = time.time() - 11
        results = engine.evaluate(400, 45.0, "AI")
        assert len(results) == 1

    def test_delay_reset_on_recovery(self, engine):
        """值恢复正常后延迟计时器应重置"""
        engine._thresholds = {
            400: [
                ThresholdCache(
                    id=30,
                    point_id=400,
                    threshold_type="high",
                    threshold_value=40.0,
                    alarm_level="major",
                    alarm_message="温度偏高",
                    delay_seconds=10,
                    dead_band=0,
                    priority=3,
                ),
            ]
        }
        engine.evaluate(400, 45.0, "AI")
        assert (400, 30) in engine._delay_first_exceed
        # 值恢复正常
        engine.evaluate(400, 35.0, "AI")
        assert (400, 30) not in engine._delay_first_exceed


class TestMassAlarm:
    """测试大面积告警检测"""

    def test_mass_alarm_detected(self, engine):
        """超过 50% 点位越限应检测为大面积告警"""
        engine._device_type_points = {"TH": {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}}
        engine._current_cycle_triggered = {"TH": {1, 2, 3, 4, 5, 6}}
        assert engine.check_mass_alarm("TH") is True

    def test_mass_alarm_not_detected(self, engine):
        """低于 50% 点位越限不应检测为大面积告警"""
        engine._device_type_points = {"TH": {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}}
        engine._current_cycle_triggered = {"TH": {1, 2, 3}}
        assert engine.check_mass_alarm("TH") is False

    def test_mass_alarm_zero_total(self, engine):
        """无点位时不应检测为大面积告警"""
        assert engine.check_mass_alarm("UNKNOWN") is False

    def test_mass_alarm_exactly_50_percent(self, engine):
        """恰好 50% 不应触发（需要 >50%）"""
        engine._device_type_points = {"TH": {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}}
        engine._current_cycle_triggered = {"TH": {1, 2, 3, 4, 5}}
        assert engine.check_mass_alarm("TH") is False


class TestIsValueSafe:
    """测试安全值判断（用于自动恢复）"""

    def test_safe_value(self, engine, sample_thresholds):
        """正常值应判定为安全"""
        engine._thresholds = {100: sample_thresholds}
        assert engine.is_value_safe(100, 25.0) is True

    def test_unsafe_high(self, engine, sample_thresholds):
        """超高值应判定为不安全"""
        engine._thresholds = {100: sample_thresholds}
        assert engine.is_value_safe(100, 55.0) is False

    def test_unsafe_low(self, engine, sample_thresholds):
        """超低值应判定为不安全"""
        engine._thresholds = {100: sample_thresholds}
        assert engine.is_value_safe(100, 3.0) is False

    def test_no_thresholds_always_safe(self, engine):
        """无阈值配置的点位始终安全"""
        assert engine.is_value_safe(999, 100.0) is True


class TestResetCycleStats:
    """测试周期统计重置"""

    def test_reset_clears_triggered(self, engine):
        """重置后本轮越限记录应清空"""
        engine._current_cycle_triggered = {"TH": {1, 2, 3}}
        engine.reset_cycle_stats()
        assert len(engine._current_cycle_triggered) == 0

    def test_evaluate_populates_cycle_stats(self, engine):
        """evaluate 触发后应记录到本轮统计"""
        engine._thresholds = {
            100: [
                ThresholdCache(
                    id=1,
                    point_id=100,
                    threshold_type="high",
                    threshold_value=40.0,
                    alarm_level="major",
                    alarm_message="test",
                    delay_seconds=0,
                    dead_band=0,
                    priority=3,
                ),
            ]
        }
        engine._point_device_type = {100: "TH"}
        engine._device_type_points = {"TH": {100, 200}}
        engine.evaluate(100, 50.0, "AI")
        assert 100 in engine._current_cycle_triggered.get("TH", set())
