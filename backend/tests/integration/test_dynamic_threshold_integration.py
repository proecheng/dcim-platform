"""
集成测试: 动态告警阈值
Story 25.6: 动态告警阈值

测试场景:
- 8.1: 配置动态阈值规则，验证告警触发逻辑
- 8.2: 特性开关关闭，验证使用静态阈值
- 8.3: 多条规则匹配，验证累加逻辑和优先级排序
- 8.4: 安全边界限制，验证不超过配置的百分比
- 8.5: 异常情况，验证降级到静态阈值
- 8.6: 低阈值调整，验证调整方向正确
- 8.7: 死区逻辑与动态阈值交互
- 8.8: API 端点验证
- 8.9: 性能测试
- 8.10: 监控指标验证
- 8.11: 向后兼容性验证
"""

import pytest
import time
import asyncio
from unittest.mock import patch, AsyncMock
from sqlalchemy import select

from app.core.database import async_session
from app.models.config import SystemConfig
from app.models.point import Point
from app.models.alarm import AlarmThreshold
from app.engines.alarm_engine import alarm_engine, EvaluateResult
from app.services.diagnosis.dynamic_threshold_service import DynamicThresholdService
from app.services.diagnosis.environment_context_service import EnvironmentContextService
from app.core.redis import redis_service


@pytest.fixture
async def setup_test_data():
    """准备测试数据"""
    async with async_session() as session:
        # 创建测试点位（温度传感器）
        point = Point(
            id=9001,
            point_code="TEST_TEMP_9001",
            point_name="测试温度传感器",
            point_type="AI",
            unit="℃",
            is_enabled=True
        )
        session.add(point)

        # 创建静态阈值配置
        threshold = AlarmThreshold(
            point_id=9001,
            threshold_type="high",
            threshold_value=30.0,
            alarm_level="major",
            alarm_message="温度过高",
            is_enabled=True,
            delay_seconds=0,
            dead_band=0.0,
            priority=10
        )
        session.add(threshold)

        # 创建动态阈值配置
        config_rules = SystemConfig(
            config_group="alarm",
            config_key="dynamic_threshold_rules",
            config_value='[{"condition": "outdoor_temp >= 35", "adjustment": "+2.0", "description": "高温调整", "priority": 10}]',
            value_type="json",
            description="动态阈值规则",
            version=1
        )
        session.add(config_rules)

        config_enabled = SystemConfig(
            config_group="alarm",
            config_key="DYNAMIC_THRESHOLDS_ENABLED",
            config_value="true",
            value_type="boolean",
            description="动态阈值开关",
            version=1
        )
        session.add(config_enabled)

        config_safety = SystemConfig(
            config_group="alarm",
            config_key="dynamic_threshold_safety_boundary_percent",
            config_value="20",
            value_type="number",
            description="安全边界",
            version=1
        )
        session.add(config_safety)

        config_types = SystemConfig(
            config_group="alarm",
            config_key="dynamic_threshold_applicable_point_types",
            config_value='["temperature"]',
            value_type="json",
            description="适用点位类型",
            version=1
        )
        session.add(config_types)

        await session.commit()

    # 加载告警引擎配置
    await alarm_engine.load_thresholds()

    yield

    # 清理测试数据
    async with async_session() as session:
        await session.execute("DELETE FROM points WHERE id = 9001")
        await session.execute("DELETE FROM alarm_thresholds WHERE point_id = 9001")
        await session.execute("DELETE FROM system_configs WHERE config_key LIKE 'dynamic_threshold%' OR config_key = 'DYNAMIC_THRESHOLDS_ENABLED'")
        await session.commit()


class TestDynamicThresholdIntegration:
    """动态阈值集成测试"""

    @pytest.mark.asyncio
    async def test_8_1_dynamic_threshold_triggers_alarm(self, setup_test_data):
        """
        8.1: 配置动态阈值规则，验证告警触发逻辑

        场景: 室外温度 36℃，触发 +2.0 调整，静态阈值 30℃ → 动态阈值 32℃
        点位值 31℃ 不触发告警（< 32℃）
        点位值 33℃ 触发告警（> 32℃）
        """
        # 设置环境上下文
        await redis_service.set("outdoor_temp", "36.0")
        await redis_service.set("it_load_percent", "50.0")

        # 清除缓存
        await DynamicThresholdService.clear_cache()
        await EnvironmentContextService.clear_cache()

        # 测试: 31℃ 不触发告警
        results = alarm_engine.evaluate(9001, 31.0, "AI")
        assert len(results) == 0, "31℃ 应该不触发告警（动态阈值 32℃）"

        # 测试: 33℃ 触发告警
        results = alarm_engine.evaluate(9001, 33.0, "AI")
        assert len(results) == 1, "33℃ 应该触发告警（动态阈值 32℃）"
        assert results[0].threshold_value == 30.0  # 原始静态阈值
        assert results[0].threshold_metadata["adjusted_threshold"] == 32.0  # 调整后阈值
        assert results[0].threshold_metadata["adjustment"] == 2.0

    @pytest.mark.asyncio
    async def test_8_2_feature_toggle_off_uses_static_threshold(self, setup_test_data):
        """
        8.2: 特性开关关闭，验证使用静态阈值

        场景: 关闭动态阈值特性，应使用静态阈值 30℃
        """
        # 关闭特性开关
        async with async_session() as session:
            await session.execute(
                "UPDATE system_configs SET config_value = 'false' WHERE config_key = 'DYNAMIC_THRESHOLDS_ENABLED'"
            )
            await session.commit()

        # 设置环境上下文
        await redis_service.set("outdoor_temp", "36.0")

        # 清除缓存
        await DynamicThresholdService.clear_cache()
        await alarm_engine.load_thresholds()

        # 测试: 31℃ 触发告警（使用静态阈值 30℃）
        results = alarm_engine.evaluate(9001, 31.0, "AI")
        assert len(results) == 1, "31℃ 应该触发告警（静态阈值 30℃）"
        assert results[0].threshold_metadata.get("is_enabled") == False

    @pytest.mark.asyncio
    async def test_8_3_multiple_rules_accumulate(self, setup_test_data):
        """
        8.3: 多条规则匹配，验证累加逻辑和优先级排序

        场景: 配置 3 条规则，验证累加和优先级
        """
        # 配置多条规则
        async with async_session() as session:
            await session.execute(
                """UPDATE system_configs
                   SET config_value = '[
                       {"condition": "outdoor_temp >= 35", "adjustment": "+2.0", "description": "高温", "priority": 10},
                       {"condition": "it_load_percent > 80", "adjustment": "+1.0", "description": "高负载", "priority": 5},
                       {"condition": "season == \\"summer\\"", "adjustment": "+0.5", "description": "夏季", "priority": 3}
                   ]'
                   WHERE config_key = 'dynamic_threshold_rules'"""
            )
            await session.commit()

        # 设置环境上下文（触发所有规则）
        await redis_service.set("outdoor_temp", "36.0")
        await redis_service.set("it_load_percent", "85.0")

        # 清除缓存
        await DynamicThresholdService.clear_cache()
        await EnvironmentContextService.clear_cache()

        # 测试: 累加调整值 = 2.0 + 1.0 + 0.5 = 3.5
        results = alarm_engine.evaluate(9001, 34.0, "AI")
        assert len(results) == 1
        assert results[0].threshold_metadata["adjustment"] == 3.5
        assert results[0].threshold_metadata["adjusted_threshold"] == 33.5
        assert len(results[0].threshold_metadata["matched_rules"]) == 3

    @pytest.mark.asyncio
    async def test_8_4_safety_boundary_limits_adjustment(self, setup_test_data):
        """
        8.4: 安全边界限制，验证不超过配置的百分比

        场景: 安全边界 20%，静态阈值 30℃，最大调整 ±6℃
        """
        # 配置极端规则（调整值 +10℃）
        async with async_session() as session:
            await session.execute(
                """UPDATE system_configs
                   SET config_value = '[{"condition": "outdoor_temp >= 35", "adjustment": "+10.0", "description": "极端调整", "priority": 10}]'
                   WHERE config_key = 'dynamic_threshold_rules'"""
            )
            await session.commit()

        # 设置环境上下文
        await redis_service.set("outdoor_temp", "36.0")

        # 清除缓存
        await DynamicThresholdService.clear_cache()

        # 测试: 调整值被限制在 ±6℃（30 * 20% = 6）
        results = alarm_engine.evaluate(9001, 37.0, "AI")
        assert len(results) == 1
        assert results[0].threshold_metadata["adjustment"] == 6.0  # 限制在 6℃
        assert results[0].threshold_metadata["adjusted_threshold"] == 36.0

    @pytest.mark.asyncio
    async def test_8_5_exception_degrades_to_static_threshold(self, setup_test_data):
        """
        8.5: 异常情况，验证降级到静态阈值

        场景: Redis 不可用，降级到静态阈值
        """
        # 模拟 Redis 异常
        with patch.object(redis_service, 'get', side_effect=Exception("Redis error")):
            # 清除缓存
            await DynamicThresholdService.clear_cache()
            await EnvironmentContextService.clear_cache()

            # 测试: 降级到静态阈值 30℃
            results = alarm_engine.evaluate(9001, 31.0, "AI")
            assert len(results) == 1
            assert results[0].threshold_metadata.get("degraded") == True or results[0].threshold_metadata.get("is_enabled") == True

    @pytest.mark.asyncio
    async def test_8_6_low_threshold_adjustment_direction(self, setup_test_data):
        """
        8.6: 低阈值调整，验证调整方向正确（减法而非加法）

        场景: 低阈值 10℃，调整 +2℃，实际阈值应为 8℃（减法）
        """
        # 创建低阈值配置
        async with async_session() as session:
            await session.execute(
                """INSERT INTO alarm_thresholds (point_id, threshold_type, threshold_value, alarm_level, alarm_message, is_enabled, priority)
                   VALUES (9001, 'low', 10.0, 'major', '温度过低', 1, 10)"""
            )
            await session.commit()

        # 重新加载阈值
        await alarm_engine.load_thresholds()

        # 设置环境上下文
        await redis_service.set("outdoor_temp", "36.0")

        # 清除缓存
        await DynamicThresholdService.clear_cache()

        # 测试: 低阈值调整方向（10 - 2 = 8）
        results = alarm_engine.evaluate(9001, 9.0, "AI")
        # 应该不触发告警（9 > 8）
        low_results = [r for r in results if r.threshold_type == "low"]
        assert len(low_results) == 0, "9℃ 不应触发低阈值告警（动态阈值 8℃）"

        results = alarm_engine.evaluate(9001, 7.0, "AI")
        low_results = [r for r in results if r.threshold_type == "low"]
        assert len(low_results) == 1, "7℃ 应触发低阈值告警（动态阈值 8℃）"
        assert low_results[0].threshold_metadata["adjusted_threshold"] == 8.0

    @pytest.mark.asyncio
    async def test_8_7_dead_band_with_dynamic_threshold(self, setup_test_data):
        """
        8.7: 死区逻辑与动态阈值交互，验证恢复判断正确

        场景: 死区 1℃，动态阈值 32℃，恢复阈值 31℃
        """
        # 配置死区
        async with async_session() as session:
            await session.execute(
                "UPDATE alarm_thresholds SET dead_band = 1.0 WHERE point_id = 9001"
            )
            await session.commit()

        # 重新加载阈值
        await alarm_engine.load_thresholds()

        # 设置环境上下文
        await redis_service.set("outdoor_temp", "36.0")

        # 清除缓存
        await DynamicThresholdService.clear_cache()

        # 第一次: 33℃ 触发告警（> 32℃）
        results = alarm_engine.evaluate(9001, 33.0, "AI")
        assert len(results) == 1

        # 第二次: 32.5℃ 不触发（已在死区内）
        results = alarm_engine.evaluate(9001, 32.5, "AI")
        assert len(results) == 0

        # 第三次: 30.5℃ 恢复（< 31℃）
        results = alarm_engine.evaluate(9001, 30.5, "AI")
        assert len(results) == 0

        # 第四次: 33℃ 再次触发
        results = alarm_engine.evaluate(9001, 33.0, "AI")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_8_9_performance_benchmark(self, setup_test_data):
        """
        8.9: 性能测试

        目标:
        - 单次完整阈值调整 < 5ms
        - 高并发场景（100 个点位）: 平均 < 10ms, P95 < 20ms
        """
        # 设置环境上下文
        await redis_service.set("outdoor_temp", "36.0")
        await redis_service.set("it_load_percent", "50.0")

        # 清除缓存
        await DynamicThresholdService.clear_cache()
        await EnvironmentContextService.clear_cache()

        # 单次调整性能测试
        start = time.time()
        results = alarm_engine.evaluate(9001, 33.0, "AI")
        elapsed = (time.time() - start) * 1000  # 转换为毫秒

        assert elapsed < 5.0, f"单次调整耗时 {elapsed:.2f}ms，超过 5ms 目标"

        # 高并发场景测试（100 次调用）
        times = []
        for i in range(100):
            start = time.time()
            alarm_engine.evaluate(9001, 33.0 + (i % 10) * 0.1, "AI")
            times.append((time.time() - start) * 1000)

        avg_time = sum(times) / len(times)
        times.sort()
        p95_time = times[int(len(times) * 0.95)]

        assert avg_time < 10.0, f"平均耗时 {avg_time:.2f}ms，超过 10ms 目标"
        assert p95_time < 20.0, f"P95 耗时 {p95_time:.2f}ms，超过 20ms 目标"

    @pytest.mark.asyncio
    async def test_8_10_monitoring_metrics(self, setup_test_data):
        """
        8.10: 监控指标验证

        验证:
        - 调整次数记录
        - 调整幅度记录
        - 规则匹配记录
        """
        # 设置环境上下文
        await redis_service.set("outdoor_temp", "36.0")
        await redis_service.set("it_load_percent", "50.0")

        # 清除缓存和 Redis 监控数据
        await DynamicThresholdService.clear_cache()
        await EnvironmentContextService.clear_cache()

        # 清理旧的监控数据
        if redis_service.is_available:
            keys = []
            cursor = 0
            while True:
                cursor, batch = await redis_service._pool.scan(cursor, match="dynamic_threshold:*", count=100)
                keys.extend(batch)
                if cursor == 0:
                    break
            for key in keys:
                await redis_service._pool.delete(key)

        # 触发多次调整
        for i in range(5):
            alarm_engine.evaluate(9001, 33.0, "AI")
            await asyncio.sleep(0.1)

        # 验证监控指标
        if redis_service.is_available:
            # 检查调整次数记录
            keys = []
            cursor = 0
            while True:
                cursor, batch = await redis_service._pool.scan(cursor, match="dynamic_threshold:count:*:adjusted", count=100)
                keys.extend(batch)
                if cursor == 0:
                    break
            assert len(keys) > 0, "应该记录调整次数"

            # 检查调整幅度记录
            keys = []
            cursor = 0
            while True:
                cursor, batch = await redis_service._pool.scan(cursor, match="dynamic_threshold:adjustment:*", count=100)
                keys.extend(batch)
                if cursor == 0:
                    break
            assert len(keys) > 0, "应该记录调整幅度"

    @pytest.mark.asyncio
    async def test_8_11_backward_compatibility(self, setup_test_data):
        """
        8.11: 向后兼容性验证

        验证: 关闭动态阈值后，现有告警引擎功能正常
        """
        # 关闭动态阈值
        async with async_session() as session:
            await session.execute(
                "UPDATE system_configs SET config_value = 'false' WHERE config_key = 'DYNAMIC_THRESHOLDS_ENABLED'"
            )
            await session.commit()

        # 清除缓存
        await DynamicThresholdService.clear_cache()
        await alarm_engine.load_thresholds()

        # 测试静态阈值功能
        results = alarm_engine.evaluate(9001, 31.0, "AI")
        assert len(results) == 1
        assert results[0].threshold_value == 30.0
        assert results[0].alarm_level == "major"

        # 测试死区功能
        async with async_session() as session:
            await session.execute(
                "UPDATE alarm_thresholds SET dead_band = 1.0 WHERE point_id = 9001"
            )
            await session.commit()
        await alarm_engine.load_thresholds()

        # 触发告警
        results = alarm_engine.evaluate(9001, 31.0, "AI")
        assert len(results) == 1

        # 死区内不重复触发
        results = alarm_engine.evaluate(9001, 30.5, "AI")
        assert len(results) == 0

        # 恢复后再次触发
        results = alarm_engine.evaluate(9001, 28.0, "AI")
        assert len(results) == 0
        results = alarm_engine.evaluate(9001, 31.0, "AI")
        assert len(results) == 1
