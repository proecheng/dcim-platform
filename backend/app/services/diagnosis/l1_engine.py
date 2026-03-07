"""
L1 规则引擎 - Story 24.1
基于内存规则匹配的快速诊断引擎
Story 25.4: 集成冗余检测与断路器保护判定
"""

import json
import time
import logging
from typing import Dict, List, Optional
from app.models.diagnosis import DiagnosisRule
from app.models.alarm import Alarm
from app.core.database import async_session
from app.core.config import get_settings
from sqlalchemy import select
from prometheus_client import Counter, REGISTRY

logger = logging.getLogger(__name__)
settings = get_settings()

# Prometheus 监控指标（条件注册）- Story 25.4
try:
    redundancy_check_total = Counter(
        'redundancy_check_total',
        'Total redundancy checks performed',
        ['has_backup']
    )
except ValueError:
    redundancy_check_total = REGISTRY._names_to_collectors['redundancy_check_total']

try:
    breaker_action_check_total = Counter(
        'breaker_action_check_total',
        'Total breaker action checks performed',
        ['action_type']
    )
except ValueError:
    breaker_action_check_total = REGISTRY._names_to_collectors['breaker_action_check_total']


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
        Story 25.4: 集成冗余检测与断路器保护判定

        Args:
            alarm_event: {
                "device_id": "xxx",
                "device_category": "power/ups",  # 对应 category 字段
                "alarm_level": "critical",
                "point_id": "xxx",
                "id": alarm_id  # Story 25.4: 用于断路器判定
            }

        Returns:
            {
                "matched": True/False,
                "conclusion": "...",
                "confidence": 0.85,
                "suggested_actions": [...],
                "rule_code": "R001",
                "inference_time_ms": 123,
                "redundancy_status": {...},  # Story 25.4
                "breaker_action": {...}      # Story 25.4
            }
        """
        start_time = time.time()

        # Story 25.4: 冗余检测（针对 power 类设备）
        redundancy_status = None
        if alarm_event.get("device_category") == "power" and alarm_event.get("device_id"):
            redundancy_status = await self._check_redundancy(alarm_event["device_id"])

        # Story 25.4: 断路器保护判定（针对过流告警）
        breaker_action = None
        if alarm_event.get("id") and self._is_overcurrent_alarm(alarm_event):
            breaker_action = await self._check_breaker_action(alarm_event["id"])

        # 1. 查找候选规则
        category = alarm_event.get("device_category", "general")
        candidate_rules = self.rule_index.get(category, [])

        if not candidate_rules:
            result = {
                "matched": False,
                "conclusion": "L1未匹配到规则",
                "confidence": 0.0,
                "inference_time_ms": int((time.time() - start_time) * 1000)
            }
            # Story 25.4: 附加冗余和断路器信息
            if redundancy_status:
                result["redundancy_status"] = redundancy_status
            if breaker_action:
                result["breaker_action"] = breaker_action
            return result

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
                result = {
                    "matched": True,
                    "conclusion": diagnosis_logic.get("conclusion", "未知故障"),
                    "confidence": diagnosis_logic.get("confidence", 0.5),
                    "suggested_actions": diagnosis_logic.get("suggested_actions", []),
                    "rule_code": rule.rule_code,
                    "inference_time_ms": int((time.time() - start_time) * 1000)
                }
                # Story 25.4: 附加冗余和断路器信息
                if redundancy_status:
                    result["redundancy_status"] = redundancy_status
                if breaker_action:
                    result["breaker_action"] = breaker_action
                return result

        # 5. 无规则匹配
        result = {
            "matched": False,
            "conclusion": "L1未匹配到规则",
            "confidence": 0.0,
            "inference_time_ms": int((time.time() - start_time) * 1000)
        }
        # Story 25.4: 附加冗余和断路器信息
        if redundancy_status:
            result["redundancy_status"] = redundancy_status
        if breaker_action:
            result["breaker_action"] = breaker_action
        return result

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

    # ==================== Story 25.4: 冗余检测与断路器保护 ====================

    async def _check_redundancy(self, device_id: int) -> Optional[dict]:
        """
        检查设备冗余状态

        Args:
            device_id: 设备ID

        Returns:
            冗余状态字典或 None（检查失败）
        """
        try:
            from app.services.diagnosis.redundancy_service import check_redundancy_backup

            async with async_session() as session:
                redundancy_status = await check_redundancy_backup(device_id, session)

            # 记录监控指标
            redundancy_check_total.labels(
                has_backup=str(redundancy_status.has_backup)
            ).inc()

            return {
                "has_backup": redundancy_status.has_backup,
                "redundancy_type": redundancy_status.redundancy_type,
                "backup_count": redundancy_status.backup_count,
                "backup_devices": redundancy_status.backup_devices,
                "error": redundancy_status.error
            }
        except Exception as e:
            logger.error(f"冗余检测失败 device_id={device_id}: {e}")
            return None

    async def _check_breaker_action(self, alarm_id: int) -> Optional[dict]:
        """
        检查断路器保护动作

        Args:
            alarm_id: 告警ID

        Returns:
            断路器动作判定结果字典或 None（检查失败）
        """
        try:
            from app.services.diagnosis.breaker_service import check_breaker_action

            async with async_session() as session:
                # 查询告警对象
                result = await session.execute(
                    select(Alarm).where(Alarm.id == alarm_id)
                )
                alarm = result.scalar_one_or_none()

                if not alarm:
                    logger.warning(f"告警不存在 alarm_id={alarm_id}")
                    return None

                breaker_result = await check_breaker_action(alarm, session)

            # 记录监控指标
            breaker_action_check_total.labels(
                action_type=breaker_result.action_type
            ).inc()

            return {
                "action_type": breaker_result.action_type,
                "confidence": breaker_result.confidence,
                "explanation": breaker_result.explanation,
                "overload_ratio": breaker_result.overload_ratio,
                "expected_time_range": breaker_result.expected_time_range,
                "actual_time": breaker_result.actual_time,
                "error": breaker_result.error
            }
        except Exception as e:
            logger.error(f"断路器判定失败 alarm_id={alarm_id}: {e}")
            return None

    def _is_overcurrent_alarm(self, alarm_event: dict) -> bool:
        """
        判断是否为过流告警

        Args:
            alarm_event: 告警事件

        Returns:
            是否为过流告警
        """
        # 必须是阈值类型告警
        alarm_type = alarm_event.get("alarm_type", "")
        if alarm_type != "threshold":
            return False

        # 检查点位类型是否与电流相关
        point_type = alarm_event.get("point_type", "").lower()
        overcurrent_keywords = ["current", "overcurrent", "过流", "电流", "过载", "overload"]

        return any(keyword in point_type for keyword in overcurrent_keywords)
