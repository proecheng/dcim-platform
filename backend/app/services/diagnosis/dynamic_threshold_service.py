"""
动态阈值服务
Story 25.6: 动态告警阈值

根据环境上下文和规则配置动态调整告警阈值
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.models.config import SystemConfig
from app.services.diagnosis.condition_parser import parse_and_evaluate
from app.services.diagnosis.environment_context_service import EnvironmentContextService

logger = logging.getLogger(__name__)


class DynamicThresholdRule:
    """动态阈值规则"""
    def __init__(
        self,
        condition: str,
        adjustment: str,
        description: str,
        priority: int
    ):
        self.condition = condition
        self.adjustment = adjustment
        self.description = description
        self.priority = priority

    def evaluate(self, context: Dict[str, Any]) -> bool:
        """评估规则条件是否满足"""
        return parse_and_evaluate(self.condition, context)

    def get_adjustment_value(self) -> float:
        """获取调整值"""
        try:
            # 支持 +1.0, -0.5 等格式
            return float(self.adjustment)
        except ValueError:
            return 0.0


class DynamicThresholdService:
    """动态阈值服务"""

    # 缓存
    _rules_cache: List[DynamicThresholdRule] = []
    _config_cache: Dict[str, Any] = {}
    _cache_lock = asyncio.Lock()
    _cache_version: Optional[int] = None

    @classmethod
    async def calculate_dynamic_threshold(
        cls,
        point_id: int,
        point_type: str,
        static_threshold: float,
        threshold_direction: str
    ) -> Dict[str, Any]:
        """
        计算动态阈值

        Args:
            point_id: 点位 ID
            point_type: 点位类型 (temperature/humidity/...)
            static_threshold: 静态阈值
            threshold_direction: 阈值方向 (high/low)

        Returns:
            Dict[str, Any]: 包含:
                - dynamic_threshold: 动态阈值
                - adjustment: 调整值
                - applied_rules: 应用的规则列表
                - is_enabled: 是否启用动态阈值
        """
        # 检查特性开关
        is_enabled = await cls._is_feature_enabled()
        if not is_enabled:
            return {
                "dynamic_threshold": static_threshold,
                "adjustment": 0.0,
                "applied_rules": [],
                "is_enabled": False
            }

        # 检查点位类型是否适用
        applicable_types = await cls._get_applicable_point_types()
        if point_type not in applicable_types:
            return {
                "dynamic_threshold": static_threshold,
                "adjustment": 0.0,
                "applied_rules": [],
                "is_enabled": True
            }

        # 获取环境上下文
        context = await EnvironmentContextService.get_context()

        # 加载规则
        rules = await cls._load_rules()

        # 评估规则并计算调整值
        applied_rules = []
        total_adjustment = 0.0

        for rule in rules:
            if rule.evaluate(context):
                adjustment = rule.get_adjustment_value()
                total_adjustment += adjustment
                applied_rules.append({
                    "condition": rule.condition,
                    "adjustment": adjustment,
                    "description": rule.description,
                    "priority": rule.priority
                })

        # 应用安全边界
        safety_boundary = await cls._get_safety_boundary_percent()
        max_adjustment = abs(static_threshold * safety_boundary / 100.0)
        total_adjustment = max(-max_adjustment, min(max_adjustment, total_adjustment))

        # 计算动态阈值（根据方向）
        if threshold_direction == "high":
            dynamic_threshold = static_threshold + total_adjustment
        else:  # low
            dynamic_threshold = static_threshold - total_adjustment

        return {
            "dynamic_threshold": dynamic_threshold,
            "adjustment": total_adjustment,
            "applied_rules": applied_rules,
            "is_enabled": True
        }

    @classmethod
    async def _is_feature_enabled(cls) -> bool:
        """检查动态阈值特性是否启用"""
        config = await cls._get_config("DYNAMIC_THRESHOLDS_ENABLED")
        if config and config.value_type == "boolean":
            return config.config_value.lower() == "true"
        return False

    @classmethod
    async def _get_applicable_point_types(cls) -> List[str]:
        """获取适用的点位类型列表"""
        config = await cls._get_config("dynamic_threshold_applicable_point_types")
        if config and config.value_type == "json":
            try:
                return json.loads(config.config_value)
            except json.JSONDecodeError:
                return []
        return []

    @classmethod
    async def _get_safety_boundary_percent(cls) -> float:
        """获取安全边界百分比"""
        config = await cls._get_config("dynamic_threshold_safety_boundary_percent")
        if config and config.value_type == "number":
            try:
                return float(config.config_value)
            except ValueError:
                return 20.0
        return 20.0

    @classmethod
    async def _load_rules(cls) -> List[DynamicThresholdRule]:
        """加载动态阈值规则"""
        async with cls._cache_lock:
            # 检查缓存版本
            current_version = await cls._get_config_version()
            if cls._rules_cache and cls._cache_version == current_version:
                return cls._rules_cache

            # 重新加载规则
            config = await cls._get_config("dynamic_threshold_rules")
            if not config or config.value_type != "json":
                cls._rules_cache = []
                cls._cache_version = current_version
                return []

            try:
                rules_data = json.loads(config.config_value)
                rules = [
                    DynamicThresholdRule(
                        condition=r["condition"],
                        adjustment=r["adjustment"],
                        description=r["description"],
                        priority=r.get("priority", 0)
                    )
                    for r in rules_data
                ]
                # 按优先级排序（高优先级先执行）
                rules.sort(key=lambda x: x.priority, reverse=True)
                cls._rules_cache = rules
                cls._cache_version = current_version
                return rules

            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"解析动态阈值规则失败: {e}")
                cls._rules_cache = []
                cls._cache_version = current_version
                return []

    @classmethod
    async def _get_config(cls, config_key: str) -> Optional[SystemConfig]:
        """获取配置项"""
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(SystemConfig).where(
                        SystemConfig.config_group == "alarm",
                        SystemConfig.config_key == config_key
                    )
                )
                return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"查询配置 {config_key} 失败: {e}")
            return None

    @classmethod
    async def _get_config_version(cls) -> Optional[int]:
        """获取配置版本号"""
        config = await cls._get_config("dynamic_threshold_rules")
        return config.version if config else None

    @classmethod
    async def clear_cache(cls):
        """清除缓存（用于测试或配置更新后）"""
        async with cls._cache_lock:
            cls._rules_cache = []
            cls._config_cache = {}
            cls._cache_version = None
