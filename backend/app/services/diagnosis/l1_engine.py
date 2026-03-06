"""
L1 规则引擎 - Story 24.1
基于内存规则匹配的快速诊断引擎
"""

import json
import time
import logging
from typing import Dict, List, Optional
from app.models.diagnosis import DiagnosisRule
from app.core.database import async_session
from app.core.config import get_settings
from sqlalchemy import select

logger = logging.getLogger(__name__)
settings = get_settings()


class L1RuleEngine:
    """L1 规则引擎 - 基于内存规则匹配"""

    def __init__(self, redis_service):
        """
        初始化 L1 引擎

        Args:
            redis_service: RedisService 实例
        """
        # 规则索引: {category: [DiagnosisRule, ...]}
        self.rule_index: Dict[str, List[DiagnosisRule]] = {}
        self.redis_service = redis_service

    async def load_rules(self):
        """服务启动时从 DB 加载规则到内存（使用 copy-on-write 避免竞态条件）"""
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(DiagnosisRule)
                    .where(DiagnosisRule.is_enabled == True)
                    .order_by(DiagnosisRule.priority.asc())  # 数字越小优先级越高
                )
                rules = result.scalars().all()

                # 构建新索引（不影响旧索引）
                new_index: Dict[str, List[DiagnosisRule]] = {}
                for rule in rules:
                    category = rule.category or "general"
                    if category not in new_index:
                        new_index[category] = []
                    new_index[category].append(rule)

                # 原子替换索引（copy-on-write）
                self.rule_index = new_index
                logger.info(f"L1 引擎加载了 {len(rules)} 条规则，{len(new_index)} 个类别")
        except Exception as e:
            logger.error(f"L1 引擎加载规则失败: {e}")
            raise

    async def match_rules(self, alarm_event: dict) -> dict:
        """
        匹配规则并返回诊断结果

        Args:
            alarm_event: {
                "device_id": "xxx",
                "device_category": "power/ups",  # 对应 category 字段
                "alarm_level": "critical",
                "point_id": "xxx"
            }

        Returns:
            {
                "matched": True/False,
                "conclusion": "...",
                "confidence": 0.85,
                "suggested_actions": [...],
                "rule_code": "R001",
                "inference_time_ms": 123
            }
        """
        start_time = time.time()

        # 1. 查找候选规则
        category = alarm_event.get("device_category", "general")
        candidate_rules = self.rule_index.get(category, [])

        if not candidate_rules:
            return {
                "matched": False,
                "conclusion": "L1未匹配到规则",
                "confidence": 0.0,
                "inference_time_ms": int((time.time() - start_time) * 1000)
            }

        # 2. 收集所有需要的点位 ID
        point_ids = set()
        for rule in candidate_rules:
            trigger_cond = rule.trigger_condition or {}
            conditions = trigger_cond.get("conditions", [])
            for condition in conditions:
                if "point_id" in condition:
                    point_ids.add(condition["point_id"])

        # 3. 批量从 Redis 读取点位值（一次 MGET）
        if point_ids:
            redis_keys = [f"point:{pid}:value" for pid in point_ids]
            values = await self.redis_service.mget(redis_keys)
            # Redis 返回可能是 None，需要处理
            point_values = {}
            for pid, val in zip(point_ids, values):
                if val is not None:
                    point_values[pid] = str(val)
                else:
                    point_values[pid] = None
        else:
            point_values = {}

        # 4. 逐规则匹配
        for rule in candidate_rules:
            if self._evaluate_rule(rule, point_values):
                diagnosis_logic = rule.diagnosis_logic or {}
                return {
                    "matched": True,
                    "conclusion": diagnosis_logic.get("conclusion", "未知故障"),
                    "confidence": diagnosis_logic.get("confidence", 0.5),
                    "suggested_actions": diagnosis_logic.get("suggested_actions", []),
                    "rule_code": rule.rule_code,
                    "inference_time_ms": int((time.time() - start_time) * 1000)
                }

        # 5. 无规则匹配
        return {
            "matched": False,
            "conclusion": "L1未匹配到规则",
            "confidence": 0.0,
            "inference_time_ms": int((time.time() - start_time) * 1000)
        }

    def _evaluate_rule(self, rule: DiagnosisRule, point_values: dict) -> bool:
        """评估单条规则是否匹配"""
        trigger_cond = rule.trigger_condition or {}
        logic = trigger_cond.get("logic", "AND")
        conditions = trigger_cond.get("conditions", [])

        if not conditions:
            return False

        results = []
        for condition in conditions:
            point_id = condition.get("point_id")
            operator = condition.get("operator")
            threshold = condition.get("value")

            if not point_id or not operator or threshold is None:
                results.append(False)
                continue

            if point_id not in point_values or point_values[point_id] is None:
                results.append(False)
                continue

            try:
                current_value = float(point_values[point_id])
                threshold_value = float(threshold)
            except (ValueError, TypeError):
                # 非数字值，尝试字符串比较
                current_value = str(point_values[point_id])
                threshold_value = str(threshold)

            # 执行比较
            try:
                if operator == "<":
                    results.append(current_value < threshold_value)
                elif operator == ">":
                    results.append(current_value > threshold_value)
                elif operator == "==":
                    results.append(current_value == threshold_value)
                elif operator == "<=":
                    results.append(current_value <= threshold_value)
                elif operator == ">=":
                    results.append(current_value >= threshold_value)
                elif operator == "!=":
                    results.append(current_value != threshold_value)
                else:
                    results.append(False)
            except Exception:
                results.append(False)

        # 根据 logic 组合结果
        if logic == "AND":
            return all(results) if results else False
        elif logic == "OR":
            return any(results) if results else False
        else:
            return False
