"""
动态阈值服务单元测试
Story 25.6: 动态告警阈值
"""

import pytest
import json
from datetime import datetime
from app.services.diagnosis.dynamic_threshold_service import (
    DynamicThresholdService,
    DynamicThresholdRule
)
from app.services.diagnosis.environment_context_service import EnvironmentContextService
from app.models.config import SystemConfig


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

    async def test_feature_disabled(self, async_db):
        """测试特性关闭时返回静态阈值"""
        # 创建配置：特性关闭
        config = SystemConfig(
            config_group="alarm",
            config_key="DYNAMIC_THRESHOLDS_ENABLED",
            config_value="false",
            value_type="boolean",
            description="动态阈值特性开关",
            version=1
        )
        async_db.add(config)
        await async_db.commit()

        # 清除缓存
        await DynamicThresholdService.clear_cache()

        # 计算动态阈值
        result = await DynamicThresholdService.calculate_dynamic_threshold(
            point_id=1,
            point_type="temperature",
            static_threshold=28.0,
            threshold_direction="high"
        )

        assert result["is_enabled"] is False
        assert result["dynamic_threshold"] == 28.0
        assert result["adjustment"] == 0.0
        assert result["applied_rules"] == []

    async def test_point_type_not_applicable(self, async_db):
        """测试点位类型不适用时返回静态阈值"""
        # 创建配置：特性开启
        config1 = SystemConfig(
            config_group="alarm",
            config_key="DYNAMIC_THRESHOLDS_ENABLED",
            config_value="true",
            value_type="boolean",
            description="动态阈值特性开关",
            version=1
        )
        # 创建配置：适用点位类型
        config2 = SystemConfig(
            config_group="alarm",
            config_key="dynamic_threshold_applicable_point_types",
            config_value='["temperature", "humidity"]',
            value_type="json",
            description="适用点位类型",
            version=1
        )
        async_db.add_all([config1, config2])
        await async_db.commit()

        # 清除缓存
        await DynamicThresholdService.clear_cache()

        # 计算动态阈值（pressure 不在适用列表中）
        result = await DynamicThresholdService.calculate_dynamic_threshold(
            point_id=1,
            point_type="pressure",
            static_threshold=100.0,
            threshold_direction="high"
        )

        assert result["is_enabled"] is True
        assert result["dynamic_threshold"] == 100.0
        assert result["adjustment"] == 0.0
        assert result["applied_rules"] == []

    async def test_single_rule_applied(self, async_db):
        """测试单条规则应用"""
        # 创建配置
        config1 = SystemConfig(
            config_group="alarm",
            config_key="DYNAMIC_THRESHOLDS_ENABLED",
            config_value="true",
            value_type="boolean",
            description="动态阈值特性开关",
            version=1
        )
        config2 = SystemConfig(
            config_group="alarm",
            config_key="dynamic_threshold_applicable_point_types",
            config_value='["temperature"]',
            value_type="json",
            description="适用点位类型",
            version=1
        )
        config3 = SystemConfig(
            config_group="alarm",
            config_key="dynamic_threshold_safety_boundary_percent",
            config_value="20",
            value_type="number",
            description="安全边界百分比",
            version=1
        )
        config4 = SystemConfig(
            config_group="alarm",
            config_key="dynamic_threshold_rules",
            config_value=json.dumps([
                {
                    "condition": "outdoor_temp >= 35",
                    "adjustment": "+1.0",
                    "description": "夏季高温调整",
                    "priority": 10
                }
            ]),
            value_type="json",
            description="动态阈值规则",
            version=1
        )
        async_db.add_all([config1, config2, config3, config4])
        await async_db.commit()

        # 清除缓存
        await DynamicThresholdService.clear_cache()
        await EnvironmentContextService.clear_cache()

        # Mock 环境上下文
        EnvironmentContextService._cache = {
            "outdoor_temp": 36.0,
            "it_load_percent": 70.0,
            "season": "summer",
            "humidity": 60.0,
            "timestamp": datetime.now()
        }

        # 计算动态阈值（high 方向）
        result = await DynamicThresholdService.calculate_dynamic_threshold(
            point_id=1,
            point_type="temperature",
            static_threshold=28.0,
            threshold_direction="high"
        )

        assert result["is_enabled"] is True
        assert result["dynamic_threshold"] == 29.0  # 28 + 1
        assert result["adjustment"] == 1.0
        assert len(result["applied_rules"]) == 1
        assert result["applied_rules"][0]["adjustment"] == 1.0

    async def test_multiple_rules_applied(self, async_db):
        """测试多条规则应用"""
        # 创建配置
        config1 = SystemConfig(
            config_group="alarm",
            config_key="DYNAMIC_THRESHOLDS_ENABLED",
            config_value="true",
            value_type="boolean",
            description="动态阈值特性开关",
            version=1
        )
        config2 = SystemConfig(
            config_group="alarm",
            config_key="dynamic_threshold_applicable_point_types",
            config_value='["temperature"]',
            value_type="json",
            description="适用点位类型",
            version=1
        )
        config3 = SystemConfig(
            config_group="alarm",
            config_key="dynamic_threshold_safety_boundary_percent",
            config_value="20",
            value_type="number",
            description="安全边界百分比",
            version=1
        )
        config4 = SystemConfig(
            config_group="alarm",
            config_key="dynamic_threshold_rules",
            config_value=json.dumps([
                {
                    "condition": "outdoor_temp >= 35",
                    "adjustment": "+1.0",
                    "description": "夏季高温调整",
                    "priority": 10
                },
                {
                    "condition": "it_load_percent > 80",
                    "adjustment": "+0.5",
                    "description": "高负载调整",
                    "priority": 5
                }
            ]),
            value_type="json",
            description="动态阈值规则",
            version=1
        )
        async_db.add_all([config1, config2, config3, config4])
        await async_db.commit()

        # 清除缓存
        await DynamicThresholdService.clear_cache()
        await EnvironmentContextService.clear_cache()

        # Mock 环境上下文（两条规则都满足）
        EnvironmentContextService._cache = {
            "outdoor_temp": 36.0,
            "it_load_percent": 85.0,
            "season": "summer",
            "humidity": 60.0,
            "timestamp": datetime.now()
        }

        # 计算动态阈值
        result = await DynamicThresholdService.calculate_dynamic_threshold(
            point_id=1,
            point_type="temperature",
            static_threshold=28.0,
            threshold_direction="high"
        )

        assert result["is_enabled"] is True
        assert result["dynamic_threshold"] == 29.5  # 28 + 1.0 + 0.5
        assert result["adjustment"] == 1.5
        assert len(result["applied_rules"]) == 2

    async def test_safety_boundary_limit(self, async_db):
        """测试安全边界限制"""
        # 创建配置
        config1 = SystemConfig(
            config_group="alarm",
            config_key="DYNAMIC_THRESHOLDS_ENABLED",
            config_value="true",
            value_type="boolean",
            description="动态阈值特性开关",
            version=1
        )
        config2 = SystemConfig(
            config_group="alarm",
            config_key="dynamic_threshold_applicable_point_types",
            config_value='["temperature"]',
            value_type="json",
            description="适用点位类型",
            version=1
        )
        config3 = SystemConfig(
            config_group="alarm",
            config_key="dynamic_threshold_safety_boundary_percent",
            config_value="20",
            value_type="number",
            description="安全边界百分比",
            version=1
        )
        config4 = SystemConfig(
            config_group="alarm",
            config_key="dynamic_threshold_rules",
            config_value=json.dumps([
                {
                    "condition": "outdoor_temp >= 35",
                    "adjustment": "+10.0",  # 超过安全边界
                    "description": "极端调整",
                    "priority": 10
                }
            ]),
            value_type="json",
            description="动态阈值规则",
            version=1
        )
        async_db.add_all([config1, config2, config3, config4])
        await async_db.commit()

        # 清除缓存
        await DynamicThresholdService.clear_cache()
        await EnvironmentContextService.clear_cache()

        # Mock 环境上下文
        EnvironmentContextService._cache = {
            "outdoor_temp": 36.0,
            "it_load_percent": 70.0,
            "season": "summer",
            "humidity": 60.0,
            "timestamp": datetime.now()
        }

        # 计算动态阈值
        result = await DynamicThresholdService.calculate_dynamic_threshold(
            point_id=1,
            point_type="temperature",
            static_threshold=28.0,
            threshold_direction="high"
        )

        # 安全边界: 28 * 20% = 5.6
        # 调整值应被限制为 5.6
        assert result["is_enabled"] is True
        assert result["dynamic_threshold"] == 33.6  # 28 + 5.6
        assert result["adjustment"] == 5.6

    async def test_low_threshold_direction(self, async_db):
        """测试 low 方向阈值调整"""
        # 创建配置
        config1 = SystemConfig(
            config_group="alarm",
            config_key="DYNAMIC_THRESHOLDS_ENABLED",
            config_value="true",
            value_type="boolean",
            description="动态阈值特性开关",
            version=1
        )
        config2 = SystemConfig(
            config_group="alarm",
            config_key="dynamic_threshold_applicable_point_types",
            config_value='["temperature"]',
            value_type="json",
            description="适用点位类型",
            version=1
        )
        config3 = SystemConfig(
            config_group="alarm",
            config_key="dynamic_threshold_safety_boundary_percent",
            config_value="20",
            value_type="number",
            description="安全边界百分比",
            version=1
        )
        config4 = SystemConfig(
            config_group="alarm",
            config_key="dynamic_threshold_rules",
            config_value=json.dumps([
                {
                    "condition": "season == 'winter'",
                    "adjustment": "+0.5",  # 正值调整
                    "description": "冬季调整",
                    "priority": 10
                }
            ]),
            value_type="json",
            description="动态阈值规则",
            version=1
        )
        async_db.add_all([config1, config2, config3, config4])
        await async_db.commit()

        # 清除缓存
        await DynamicThresholdService.clear_cache()
        await EnvironmentContextService.clear_cache()

        # Mock 环境上下文
        EnvironmentContextService._cache = {
            "outdoor_temp": 5.0,
            "it_load_percent": 70.0,
            "season": "winter",
            "humidity": 40.0,
            "timestamp": datetime.now()
        }

        # 计算动态阈值（low 方向）
        result = await DynamicThresholdService.calculate_dynamic_threshold(
            point_id=1,
            point_type="temperature",
            static_threshold=15.0,
            threshold_direction="low"
        )

        # low 方向使用减法: 15 - 0.5 = 14.5
        assert result["is_enabled"] is True
        assert result["dynamic_threshold"] == 14.5
        assert result["adjustment"] == 0.5
