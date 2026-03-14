"""
动态阈值服务单元测试
Story 25.6: 动态告警阈值
"""

import pytest
import json
import time
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.diagnosis.dynamic_threshold_service import (
    DynamicThresholdService,
    DynamicThresholdRule
)
from app.services.diagnosis.environment_context_service import EnvironmentContextService


class TestDynamicThresholdRule:
    """动态阈值规则测试"""

    def test_rule_evaluation_true(self):
        """测试规则评估为真"""
        rule = DynamicThresholdRule(
            condition="outdoor_temp >= 35",
            adjustment="+1.0",
            description="夏季高温调整",
            priority=10
        )
        context = {"outdoor_temp": 36}
        assert rule.evaluate(context) is True

    def test_rule_evaluation_false(self):
        """测试规则评估为假"""
        rule = DynamicThresholdRule(
            condition="outdoor_temp >= 35",
            adjustment="+1.0",
            description="夏季高温调整",
            priority=10
        )
        context = {"outdoor_temp": 34}
        assert rule.evaluate(context) is False

    def test_get_adjustment_value_positive(self):
        """测试获取正调整值"""
        rule = DynamicThresholdRule(
            condition="outdoor_temp >= 35",
            adjustment="+1.0",
            description="夏季高温调整",
            priority=10
        )
        assert rule.get_adjustment_value() == 1.0

    def test_get_adjustment_value_negative(self):
        """测试获取负调整值"""
        rule = DynamicThresholdRule(
            condition="season == 'winter'",
            adjustment="-0.5",
            description="冬季降温调整",
            priority=5
        )
        assert rule.get_adjustment_value() == -0.5


@pytest.mark.asyncio
class TestDynamicThresholdService:
    """动态阈值服务测试"""

    async def test_feature_disabled(self):
        """测试特性关闭时返回静态阈值"""
        # 清除缓存
        await DynamicThresholdService.clear_cache()

        with patch.object(
            DynamicThresholdService, '_is_feature_enabled',
            new_callable=AsyncMock, return_value=False
        ):
            threshold, metadata = await DynamicThresholdService.calculate_dynamic_threshold(
                point_id=1,
                static_threshold=28.0,
                threshold_direction="high"
            )

        assert metadata["is_enabled"] is False
        assert threshold == 28.0

    async def test_point_type_not_applicable(self):
        """测试点位类型不适用时返回静态阈值"""
        await DynamicThresholdService.clear_cache()

        with patch.object(
            DynamicThresholdService, '_is_feature_enabled',
            new_callable=AsyncMock, return_value=True
        ), patch.object(
            DynamicThresholdService, '_get_point_type',
            new_callable=AsyncMock, return_value="pressure"
        ), patch.object(
            DynamicThresholdService, '_get_applicable_point_types',
            new_callable=AsyncMock, return_value=["temperature", "humidity"]
        ), patch.object(
            DynamicThresholdService, '_record_metrics',
            new_callable=AsyncMock
        ):
            threshold, metadata = await DynamicThresholdService.calculate_dynamic_threshold(
                point_id=1,
                static_threshold=100.0,
                threshold_direction="high"
            )

        assert metadata["is_enabled"] is True
        assert threshold == 100.0
        assert metadata.get("skipped") is True

    async def test_single_rule_applied(self):
        """测试单条规则应用"""
        await DynamicThresholdService.clear_cache()
        await EnvironmentContextService.clear_cache()

        rules = [
            DynamicThresholdRule(
                condition="outdoor_temp >= 35",
                adjustment="+1.0",
                description="夏季高温调整",
                priority=10
            )
        ]

        # Mock 环境上下文
        EnvironmentContextService._cache = {
            "outdoor_temp": 36.0,
            "it_load_percent": 70.0,
            "season": "summer",
            "humidity": 60.0,
            "timestamp": time.time()
        }

        with patch.object(
            DynamicThresholdService, '_is_feature_enabled',
            new_callable=AsyncMock, return_value=True
        ), patch.object(
            DynamicThresholdService, '_get_point_type',
            new_callable=AsyncMock, return_value="temperature"
        ), patch.object(
            DynamicThresholdService, '_get_applicable_point_types',
            new_callable=AsyncMock, return_value=["temperature"]
        ), patch.object(
            DynamicThresholdService, '_load_rules',
            new_callable=AsyncMock, return_value=rules
        ), patch.object(
            DynamicThresholdService, '_get_safety_boundary_percent',
            new_callable=AsyncMock, return_value=20.0
        ), patch.object(
            DynamicThresholdService, '_record_metrics',
            new_callable=AsyncMock
        ), patch.object(
            DynamicThresholdService, '_record_rule_match',
            new_callable=AsyncMock
        ):
            threshold, metadata = await DynamicThresholdService.calculate_dynamic_threshold(
                point_id=1,
                static_threshold=28.0,
                threshold_direction="high"
            )

        assert metadata["is_enabled"] is True
        assert threshold == 29.0  # 28 + 1
        assert metadata["adjustment"] == 1.0
        assert len(metadata["matched_rules"]) == 1
        assert metadata["matched_rules"][0]["adjustment"] == 1.0

    async def test_multiple_rules_applied(self):
        """测试多条规则应用"""
        await DynamicThresholdService.clear_cache()
        await EnvironmentContextService.clear_cache()

        rules = [
            DynamicThresholdRule(
                condition="outdoor_temp >= 35",
                adjustment="+1.0",
                description="夏季高温调整",
                priority=10
            ),
            DynamicThresholdRule(
                condition="it_load_percent > 80",
                adjustment="+0.5",
                description="高负载调整",
                priority=5
            )
        ]

        # Mock 环境上下文（两条规则都满足）
        EnvironmentContextService._cache = {
            "outdoor_temp": 36.0,
            "it_load_percent": 85.0,
            "season": "summer",
            "humidity": 60.0,
            "timestamp": time.time()
        }

        with patch.object(
            DynamicThresholdService, '_is_feature_enabled',
            new_callable=AsyncMock, return_value=True
        ), patch.object(
            DynamicThresholdService, '_get_point_type',
            new_callable=AsyncMock, return_value="temperature"
        ), patch.object(
            DynamicThresholdService, '_get_applicable_point_types',
            new_callable=AsyncMock, return_value=["temperature"]
        ), patch.object(
            DynamicThresholdService, '_load_rules',
            new_callable=AsyncMock, return_value=rules
        ), patch.object(
            DynamicThresholdService, '_get_safety_boundary_percent',
            new_callable=AsyncMock, return_value=20.0
        ), patch.object(
            DynamicThresholdService, '_record_metrics',
            new_callable=AsyncMock
        ), patch.object(
            DynamicThresholdService, '_record_rule_match',
            new_callable=AsyncMock
        ):
            threshold, metadata = await DynamicThresholdService.calculate_dynamic_threshold(
                point_id=1,
                static_threshold=28.0,
                threshold_direction="high"
            )

        assert metadata["is_enabled"] is True
        assert threshold == 29.5  # 28 + 1.0 + 0.5
        assert metadata["adjustment"] == 1.5
        assert len(metadata["matched_rules"]) == 2

    async def test_safety_boundary_limit(self):
        """测试安全边界限制"""
        await DynamicThresholdService.clear_cache()
        await EnvironmentContextService.clear_cache()

        rules = [
            DynamicThresholdRule(
                condition="outdoor_temp >= 35",
                adjustment="+10.0",  # 超过安全边界
                description="极端调整",
                priority=10
            )
        ]

        # Mock 环境上下文
        EnvironmentContextService._cache = {
            "outdoor_temp": 36.0,
            "it_load_percent": 70.0,
            "season": "summer",
            "humidity": 60.0,
            "timestamp": time.time()
        }

        with patch.object(
            DynamicThresholdService, '_is_feature_enabled',
            new_callable=AsyncMock, return_value=True
        ), patch.object(
            DynamicThresholdService, '_get_point_type',
            new_callable=AsyncMock, return_value="temperature"
        ), patch.object(
            DynamicThresholdService, '_get_applicable_point_types',
            new_callable=AsyncMock, return_value=["temperature"]
        ), patch.object(
            DynamicThresholdService, '_load_rules',
            new_callable=AsyncMock, return_value=rules
        ), patch.object(
            DynamicThresholdService, '_get_safety_boundary_percent',
            new_callable=AsyncMock, return_value=20.0
        ), patch.object(
            DynamicThresholdService, '_record_metrics',
            new_callable=AsyncMock
        ), patch.object(
            DynamicThresholdService, '_record_rule_match',
            new_callable=AsyncMock
        ):
            threshold, metadata = await DynamicThresholdService.calculate_dynamic_threshold(
                point_id=1,
                static_threshold=28.0,
                threshold_direction="high"
            )

        # 安全边界: 28 * 20% = 5.6
        # 调整值应被限制为 5.6
        assert metadata["is_enabled"] is True
        assert threshold == 33.6  # 28 + 5.6
        assert metadata["adjustment"] == 5.6

    async def test_low_threshold_direction(self):
        """测试 low 方向阈值调整"""
        await DynamicThresholdService.clear_cache()
        await EnvironmentContextService.clear_cache()

        rules = [
            DynamicThresholdRule(
                condition="season == 'winter'",
                adjustment="+0.5",  # 正值调整
                description="冬季调整",
                priority=10
            )
        ]

        # Mock 环境上下文
        EnvironmentContextService._cache = {
            "outdoor_temp": 5.0,
            "it_load_percent": 70.0,
            "season": "winter",
            "humidity": 40.0,
            "timestamp": time.time()
        }

        with patch.object(
            DynamicThresholdService, '_is_feature_enabled',
            new_callable=AsyncMock, return_value=True
        ), patch.object(
            DynamicThresholdService, '_get_point_type',
            new_callable=AsyncMock, return_value="temperature"
        ), patch.object(
            DynamicThresholdService, '_get_applicable_point_types',
            new_callable=AsyncMock, return_value=["temperature"]
        ), patch.object(
            DynamicThresholdService, '_load_rules',
            new_callable=AsyncMock, return_value=rules
        ), patch.object(
            DynamicThresholdService, '_get_safety_boundary_percent',
            new_callable=AsyncMock, return_value=20.0
        ), patch.object(
            DynamicThresholdService, '_record_metrics',
            new_callable=AsyncMock
        ), patch.object(
            DynamicThresholdService, '_record_rule_match',
            new_callable=AsyncMock
        ):
            threshold, metadata = await DynamicThresholdService.calculate_dynamic_threshold(
                point_id=1,
                static_threshold=15.0,
                threshold_direction="low"
            )

        # low 方向使用减法: 15 - 0.5 = 14.5
        assert metadata["is_enabled"] is True
        assert threshold == 14.5
        assert metadata["adjustment"] == 0.5
