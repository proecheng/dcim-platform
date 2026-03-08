"""
诊断引擎 — 规则匹配与置信度计算
Story 9-3: 智能故障诊断
"""

import asyncio
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import select, func

from ..core.database import async_session
from ..models.alarm import Alarm
from ..models.diagnosis import DiagnosisRule, DiagnosisResult
from ..services.websocket import ws_manager
from ..services.diagnosis.result_store import DiagnosisResultStore
from ..services.diagnosis.push_service import DiagnosisPushService
from .event_bus import Event

logger = logging.getLogger(__name__)

# alarm_level -> 置信度加成
_LEVEL_BOOST = {
    "critical": 15,
    "major": 10,
    "minor": 5,
    "info": 0,
}


class DiagnosisEngine:
    """诊断引擎 — 核心类"""

    DEDUP_WINDOW = 60  # 去重窗口（秒）

    def __init__(self) -> None:
        # 规则缓存: {device_type: [rule_dict, ...]}，"*" 为通配
        self._rule_cache: Dict[str, List[dict]] = {}
        # 去重缓存: {alarm_id: timestamp}
        self._recent: Dict[int, float] = {}
        # 内存告警计数器: {"alarm_type:device_type": [timestamp, ...]}
        self._alarm_counter: Dict[str, List[float]] = defaultdict(list)
        self._loaded = False

    async def load_rules(self) -> int:
        """从数据库加载启用的诊断规则到内存缓存"""
        async with async_session() as session:
            result = await session.execute(
                select(DiagnosisRule).where(DiagnosisRule.is_enabled == True)  # noqa: E712
            )
            rules = result.scalars().all()

            # copy-on-write: 构建新缓存
            new_cache: Dict[str, List[dict]] = defaultdict(list)
            for r in rules:
                rule_dict = {
                    "id": r.id,
                    "rule_code": r.rule_code,
                    "name": r.name,
                    "category": r.category,
                    "trigger_condition": r.trigger_condition or {},
                    "diagnosis_logic": r.diagnosis_logic or {},
                    "priority": r.priority or 0,
                }
                # 按 device_type 索引
                device_types = (r.trigger_condition or {}).get("device_type", ["*"])
                for dt in device_types:
                    new_cache[dt].append(rule_dict)

            # 每个 device_type 列表按 priority 降序
            for dt in new_cache:
                new_cache[dt].sort(key=lambda x: x["priority"], reverse=True)

            self._rule_cache = dict(new_cache)
            self._loaded = True
            count = sum(len(v) for v in self._rule_cache.values())
            logger.info("诊断引擎: 已加载 %d 条规则索引（%d 个 device_type 分组）", count, len(self._rule_cache))
            return len(rules)

    async def reload_rules(self) -> int:
        """重载规则缓存"""
        return await self.load_rules()

    async def on_alarm_event(self, event: Event) -> None:
        """事件总线 handler — 用 create_task 不阻塞联动引擎"""
        if not self._loaded:
            return
        if event.event_type != "alarm.triggered":
            return
        # 记录告警计数器
        payload = event.payload
        counter_key = f"{payload.get('alarm_type', '')}:{payload.get('device_type', '')}"
        self._alarm_counter[counter_key].append(time.time())

        # 后台执行诊断，不阻塞联动引擎
        asyncio.create_task(self._safe_diagnose(payload))

    async def _safe_diagnose(self, payload: dict) -> None:
        """安全执行诊断（捕获所有异常）"""
        try:
            await self._do_diagnose(payload)
        except Exception as e:
            logger.error("诊断引擎异常: %s", e, exc_info=True)

    async def _do_diagnose(self, payload: dict) -> None:
        """执行诊断流程"""
        alarm_id = payload.get("alarm_id")
        if alarm_id is None:
            return

        # 去重检查
        now = time.time()
        last_time = self._recent.get(alarm_id)
        if last_time is not None and (now - last_time) < self.DEDUP_WINDOW:
            return
        self._recent[alarm_id] = now

        # 清理过期去重缓存
        expired = [k for k, v in self._recent.items() if (now - v) > self.DEDUP_WINDOW * 2]
        for k in expired:
            del self._recent[k]

        start_ms = time.monotonic()

        # 匹配规则
        device_type = payload.get("device_type", "")
        matched_rules = []
        if device_type:
            matched_rules.extend(self._rule_cache.get(device_type, []))
        # 通配规则
        matched_rules.extend(self._rule_cache.get("*", []))

        # 去重（同一规则可能在 device_type 和 "*" 中都出现）
        seen_ids = set()
        unique_rules = []
        for r in matched_rules:
            if r["id"] not in seen_ids:
                seen_ids.add(r["id"])
                unique_rules.append(r)

        if not unique_rules:
            return

        # 过滤匹配条件
        alarm_type = payload.get("alarm_type", "")
        alarm_level = payload.get("alarm_level", "")
        threshold_type = payload.get("threshold_type", "")

        all_causes: List[dict] = []
        matched_rule_id = None
        matched_rule_code = None

        for rule in unique_rules:
            tc = rule["trigger_condition"]

            # 检查 alarm_type
            tc_alarm_types = tc.get("alarm_type", [])
            if tc_alarm_types and alarm_type not in tc_alarm_types:
                continue

            # 检查 alarm_level
            tc_alarm_levels = tc.get("alarm_level", [])
            if tc_alarm_levels and alarm_level not in tc_alarm_levels:
                continue

            # 检查 threshold_type
            tc_threshold_types = tc.get("threshold_type", [])
            if tc_threshold_types and threshold_type and threshold_type not in tc_threshold_types:
                continue

            # 规则匹配成功，计算置信度
            if matched_rule_id is None:
                matched_rule_id = rule["id"]
                matched_rule_code = rule["rule_code"]

            logic = rule["diagnosis_logic"]
            possible_causes = logic.get("possible_causes", [])

            for cause_data in possible_causes:
                confidence = await self._calculate_confidence(cause_data, alarm_level, payload)
                all_causes.append(
                    {
                        "cause": cause_data.get("cause", ""),
                        "confidence": confidence,
                        "suggested_actions": cause_data.get("suggested_actions", []),
                        "rule_code": rule["rule_code"],
                    }
                )

        if not all_causes:
            return

        # 按置信度降序排列，去重（同名原因取最高置信度）
        all_causes.sort(key=lambda x: x["confidence"], reverse=True)

        elapsed_ms = int((time.monotonic() - start_ms) * 1000)

        # 最高置信度（引擎返回整数 0-100，转为 0.0-1.0）
        top = all_causes[0] if all_causes else {}
        top_confidence_int = top.get("confidence", 0)
        top_confidence = top_confidence_int / 100.0 if top_confidence_int > 1 else float(top_confidence_int)
        # start_time 根据 elapsed_ms 反推，end_time 取当前时间
        end_dt = datetime.now()
        from datetime import timedelta
        start_dt = end_dt - timedelta(milliseconds=elapsed_ms)

        # 使用 DiagnosisResultStore 统一存储
        try:
            session_id, result_id = await DiagnosisResultStore.save_complete(
                trigger_alarm_id=alarm_id,
                device_id=payload.get("device_id"),
                engine_level="L1",
                status="success",
                max_confidence=top_confidence,
                start_time=start_dt,
                end_time=end_dt,
                inference_time_ms=elapsed_ms,
                alarm_id=alarm_id,
                alarm_no=payload.get("alarm_no", ""),
                rule_id=matched_rule_id,
                rule_code=matched_rule_code,
                device_type=device_type,
                zone=payload.get("zone", ""),
                causes=all_causes,
                diagnosis_level="L1",
                matched=True,
                conclusion=top.get("cause", ""),
                confidence=top_confidence,
                suggested_actions=top.get("suggested_actions"),
                root_cause=top.get("cause", ""),
                input_data=payload,
                output_data={"causes": all_causes, "elapsed_ms": elapsed_ms},
            )

            # Story 25.1: 级联分析 - 分析受影响的下游设备
            cascade_impact = None
            if device_type in ["transformer", "panel", "circuit", "device"]:
                try:
                    from ..services.diagnosis.power_topology_service import analyze_downstream_impact
                    device_id = payload.get("device_id")
                    if device_id:
                        # 构建节点 ID
                        node_prefix = {
                            "transformer": "T",
                            "panel": "P",
                            "circuit": "C",
                            "device": "D"
                        }.get(device_type, "D")
                        fault_node_id = f"{node_prefix}-{device_id}"

                        # 执行级联分析
                        cascade_impact = await analyze_downstream_impact(fault_node_id)

                        # 将级联分析结果添加到输出数据
                        if cascade_impact and "error" not in cascade_impact:
                            output_data = {"causes": all_causes, "elapsed_ms": elapsed_ms, "cascade_impact": cascade_impact}
                            # 更新诊断结果的输出数据
                            async with async_session() as db:
                                from ..models.diagnosis import DiagnosisResult
                                result = await db.execute(
                                    select(DiagnosisResult).where(DiagnosisResult.id == result_id)
                                )
                                diagnosis_result = result.scalar_one_or_none()
                                if diagnosis_result:
                                    diagnosis_result.output_data = output_data
                                    await db.commit()

                            logger.info(f"级联分析完成: 故障节点 {fault_node_id}, 受影响设备 {len(cascade_impact.get('affected_devices', []))} 个")

                except ImportError:
                    logger.debug("级联分析服务不可用，跳过级联分析")
                except Exception as e:
                    logger.warning(f"级联分析失败: {e}")

            # 分级推送
            push_status = await DiagnosisPushService.push_diagnosis_result(
                session_id=session_id,
                device_id=payload.get("device_id"),
                device_type=device_type,
                engine_level="L1",
                confidence=top_confidence,
                conclusion=top.get("cause", ""),
                root_cause=top.get("cause", ""),
                suggested_actions=top.get("suggested_actions"),
            )
            await DiagnosisResultStore.update_push_status(session_id, push_status)

        except Exception as e:
            logger.error("诊断结果存储/推送失败: %s", e, exc_info=True)

    async def _calculate_confidence(self, cause_data: dict, alarm_level: str, payload: dict) -> int:
        """
        计算置信度

        Story 25.5: 集成传感器精度权重调整
        """
        base = cause_data.get("base_confidence", 50)

        # alarm_level 加成
        base += _LEVEL_BOOST.get(alarm_level, 0)

        # 历史频率加成
        history_check = cause_data.get("history_check")
        if history_check:
            boost = await self._check_history(
                payload.get("alarm_type", ""),
                payload.get("device_type", ""),
                history_check.get("time_window_hours", 24),
                history_check.get("min_occurrences", 3),
                history_check.get("confidence_boost", 10),
            )
            base += boost

        # Story 25.5: 传感器精度权重调整
        # 如果告警关联点位，应用传感器权重调整置信度
        point_id = payload.get("point_id")
        if point_id:
            try:
                from ..services.diagnosis.sensor_metadata_service import get_sensor_weight, apply_evidence_weight
                sensor_weight = get_sensor_weight(point_id)
                # 使用收缩公式调整置信度
                # 将置信度视为观测概率，50 作为先验
                prior = 50.0
                base = apply_evidence_weight(prior, float(base), sensor_weight / 1.0) if sensor_weight != 0.85 else base
            except Exception as e:
                logger.warning(f"传感器权重调整失败，使用默认权重: {e}")
                # 降级策略：使用默认权重，不影响诊断流程

        return min(int(base), 100)

    async def _check_history(
        self,
        alarm_type: str,
        device_type: str,
        time_window_hours: int,
        min_occurrences: int,
        confidence_boost: int,
    ) -> int:
        """检查历史告警频率 — 优先内存计数器，回退数据库"""
        counter_key = f"{alarm_type}:{device_type}"
        now = time.time()
        cutoff = now - time_window_hours * 3600

        # 清理过期计数
        timestamps = self._alarm_counter.get(counter_key, [])
        valid = [t for t in timestamps if t > cutoff]
        self._alarm_counter[counter_key] = valid

        if len(valid) >= min_occurrences:
            return confidence_boost

        # 内存计数不足，回退数据库查询
        try:
            since = datetime.now() - timedelta(hours=time_window_hours)
            async with async_session() as session:
                result = await session.execute(
                    select(func.count(Alarm.id)).where(
                        Alarm.alarm_type == alarm_type,
                        Alarm.created_at >= since,
                    )
                )
                db_count = result.scalar() or 0
                if db_count >= min_occurrences:
                    return confidence_boost
        except Exception as e:
            logger.warning("诊断引擎历史查询失败: %s", e)

        return 0

    async def manual_diagnose(self, alarm_id: int) -> Optional[dict]:
        """手动触发诊断（从 Alarm 表读取数据）"""
        async with async_session() as session:
            result = await session.execute(select(Alarm).where(Alarm.id == alarm_id))
            alarm = result.scalar_one_or_none()
            if alarm is None:
                return None

            # 获取点位信息
            from ..models.point import Point

            point_result = await session.execute(select(Point).where(Point.id == alarm.point_id))
            point = point_result.scalar_one_or_none()

            payload = {
                "alarm_id": alarm.id,
                "alarm_no": alarm.alarm_no,
                "alarm_level": alarm.alarm_level,
                "alarm_type": alarm.alarm_type or "threshold",
                "alarm_message": alarm.alarm_message,
                "point_id": alarm.point_id,
                "trigger_value": alarm.trigger_value,
                "threshold_value": alarm.threshold_value,
                "device_type": point.device_type if point is not None and point.device_type is not None else "",
                "zone": point.area_code if point is not None and point.area_code is not None else "default",
            }

        # 清除去重缓存以允许重新诊断
        self._recent.pop(alarm_id, None)
        await self._do_diagnose(payload)
        return payload


# 全局单例
diagnosis_engine = DiagnosisEngine()
