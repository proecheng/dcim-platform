"""
动态阈值服务
Story 25.6: 动态告警阈值

根据环境上下文和规则配置动态调整告警阈值
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.core.redis import redis_service
from app.models.config import SystemConfig
from app.models.point import Point
from app.services.diagnosis.condition_parser import parse_and_evaluate
from app.services.diagnosis.environment_context_service import EnvironmentContextService

logger = logging.getLogger(__name__)

# 全局事件循环（用于同步调用）
_event_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_lock = asyncio.Lock()


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
    def calculate_dynamic_threshold_sync(
        cls,
        point_id: int,
        static_threshold: float,
        threshold_direction: str
    ) -> Tuple[float, Dict[str, Any]]:
        """
        计算动态阈值（同步版本，用于告警引擎）

        Args:
            point_id: 点位 ID
            static_threshold: 静态阈值
            threshold_direction: 阈值方向 (high/low/high_high/low_low)

        Returns:
            Tuple[float, Dict[str, Any]]: (调整后的阈值, 元数据)
        """
        try:
            # 尝试获取或创建事件循环
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # 没有运行中的事件循环，创建新的
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    cls.calculate_dynamic_threshold(point_id, static_threshold, threshold_direction)
                )
                loop.close()
                return result
            else:
                # 已有运行中的事件循环，使用 run_coroutine_threadsafe
                import concurrent.futures
                future = asyncio.run_coroutine_threadsafe(
                    cls.calculate_dynamic_threshold(point_id, static_threshold, threshold_direction),
                    loop
                )
                return future.result(timeout=5.0)  # 5秒超时
        except Exception as e:
            logger.error(f"同步调用动态阈值失败: {e}")
            return static_threshold, {"is_enabled": False, "error": str(e)}

    @classmethod
    async def calculate_dynamic_threshold(
        cls,
        point_id: int,
        static_threshold: float,
        threshold_direction: str
    ) -> Tuple[float, Dict[str, Any]]:
        """
        计算动态阈值

        Args:
            point_id: 点位 ID
            static_threshold: 静态阈值
            threshold_direction: 阈值方向 (high/low/high_high/low_low)

        Returns:
            Tuple[float, Dict[str, Any]]: (调整后的阈值, 元数据)
                元数据包含:
                - original_threshold: 原始静态阈值
                - adjustment: 调整值
                - adjusted_threshold: 最终阈值
                - matched_rules: 匹配的规则列表
                - context: 环境上下文
                - rule_version: 规则配置版本号
                - is_enabled: 是否启用动态阈值
        """
        start_time = time.time()

        try:
            # 检查特性开关
            is_enabled = await cls._is_feature_enabled()
            if not is_enabled:
                return static_threshold, {"is_enabled": False}

            # 检查点位类型是否适用
            point_type = await cls._get_point_type(point_id)
            applicable_types = await cls._get_applicable_point_types()

            if not point_type or point_type not in applicable_types:
                await cls._record_metrics("skipped", point_id, 0.0, time.time() - start_time)
                return static_threshold, {
                    "is_enabled": True,
                    "skipped": True,
                    "reason": f"Point type '{point_type}' not applicable"
                }

            # 获取环境上下文
            context_start = time.time()
            context = await EnvironmentContextService.get_context()
            context_time = time.time() - context_start

            # 加载规则
            rules = await cls._load_rules()
            rule_version = cls._cache_version

            # 评估规则并计算调整值
            eval_start = time.time()
            matched_rules = []
            total_adjustment = 0.0

            for rule in rules:
                if rule.evaluate(context):
                    adjustment = rule.get_adjustment_value()
                    total_adjustment += adjustment
                    matched_rules.append({
                        "condition": rule.condition,
                        "adjustment": adjustment,
                        "description": rule.description,
                        "priority": rule.priority
                    })
                    # 记录规则匹配
                    await cls._record_rule_match(rule.condition, rule.priority)

            eval_time = time.time() - eval_start

            # 应用安全边界
            safety_boundary = await cls._get_safety_boundary_percent()
            max_adjustment = abs(static_threshold * safety_boundary / 100.0)
            total_adjustment = max(-max_adjustment, min(max_adjustment, total_adjustment))

            # 计算动态阈值（根据方向）
            if threshold_direction in ("high", "high_high"):
                adjusted_threshold = static_threshold + total_adjustment
            else:  # low, low_low
                adjusted_threshold = static_threshold - total_adjustment

            # 记录监控指标
            total_time = time.time() - start_time
            await cls._record_metrics(
                "adjusted",
                point_id,
                total_adjustment,
                total_time,
                context_time=context_time,
                eval_time=eval_time,
                matched_count=len(matched_rules)
            )

            # 构建元数据
            metadata = {
                "original_threshold": static_threshold,
                "adjustment": total_adjustment,
                "adjusted_threshold": adjusted_threshold,
                "matched_rules": matched_rules,
                "context": context,
                "rule_version": rule_version,
                "is_enabled": True
            }

            return adjusted_threshold, metadata

        except Exception as e:
            logger.error(f"动态阈值调整失败: {e}，降级到静态阈值")
            await cls._record_metrics("degraded", point_id, 0.0, time.time() - start_time, error=str(e))
            return static_threshold, {"is_enabled": True, "degraded": True, "error": str(e)}

    @classmethod
    async def _get_point_type(cls, point_id: int) -> Optional[str]:
        """
        获取点位类型（根据 unit 字段判断）

        Args:
            point_id: 点位 ID

        Returns:
            Optional[str]: 点位类型 (temperature/humidity/...)，无法判断返回 None
        """
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(Point.unit).where(Point.id == point_id)
                )
                unit = result.scalar_one_or_none()

                if not unit:
                    return None

                # 根据单位判断类型
                unit_lower = unit.lower()
                if "℃" in unit or "°c" in unit_lower or "celsius" in unit_lower:
                    return "temperature"
                elif "%rh" in unit_lower or ("%" in unit and "rh" in unit_lower):
                    return "humidity"
                else:
                    return None

        except Exception as e:
            logger.error(f"查询点位 {point_id} 类型失败: {e}")
            return None

    @classmethod
    async def _record_metrics(
        cls,
        status: str,
        point_id: int,
        adjustment: float,
        total_time: float,
        context_time: float = 0.0,
        eval_time: float = 0.0,
        matched_count: int = 0,
        error: Optional[str] = None
    ):
        """
        记录监控指标到 Redis

        Args:
            status: 状态 (adjusted/skipped/degraded)
            point_id: 点位 ID
            adjustment: 调整值
            total_time: 总耗时（秒）
            context_time: 上下文查询耗时（秒）
            eval_time: 规则评估耗时（秒）
            matched_count: 匹配的规则数量
            error: 错误信息（降级时）
        """
        try:
            timestamp = int(time.time())

            # 记录调整次数（按点位统计）
            await redis_service.set(
                f"dynamic_threshold:count:{point_id}:{status}",
                str(timestamp),
                ttl=86400  # 24小时
            )

            # 记录调整幅度（用于 P50/P95/P99 分析）
            if status == "adjusted":
                await redis_service.set(
                    f"dynamic_threshold:adjustment:{point_id}:{timestamp}",
                    str(adjustment),
                    ttl=3600  # 1小时
                )

            # 记录性能耗时
            perf_data = {
                "total_time": total_time,
                "context_time": context_time,
                "eval_time": eval_time,
                "matched_count": matched_count
            }
            await redis_service.set_json(
                f"dynamic_threshold:perf:{timestamp}",
                perf_data,
                ttl=3600
            )

            # 记录降级次数
            if status == "degraded" and error:
                await redis_service.set(
                    f"dynamic_threshold:degraded:{timestamp}",
                    error,
                    ttl=86400
                )

        except Exception as e:
            logger.warning(f"记录监控指标失败: {e}")

    @classmethod
    async def _record_rule_match(cls, condition: str, priority: int):
        """
        记录规则匹配次数

        Args:
            condition: 规则条件
            priority: 规则优先级
        """
        try:
            # 使用条件的哈希值作为 key（避免特殊字符）
            rule_hash = str(hash(condition))
            key = f"dynamic_threshold:rule_match:{rule_hash}"

            # 递增匹配计数
            if redis_service.is_available:
                await redis_service._pool.incr(key)
                await redis_service._pool.expire(key, 86400)  # 24小时

        except Exception as e:
            logger.warning(f"记录规则匹配失败: {e}")

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
