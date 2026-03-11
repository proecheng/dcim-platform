"""
回退保护管理器 — 7 项自动回退保护机制

Story 30.2: 持续监控 CoolingZone 安全状态，检测异常条件并触发自动回退。

触发条件：
1. 任一机柜 T_inlet > 26°C
2. 温升速率超预测 150%
3. 温度变化超 5°C/h
4. 空调故障告警
5. 温度传感器离线
6. 市电中断切 UPS
7. 预冷时湿度接近露点
"""

import json
import math
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rollback import RollbackEvent, RollbackTriggerType

logger = logging.getLogger(__name__)

# 回退触发阈值默认值
DEFAULT_TEMP_ROLLBACK = 26.0       # 条件1: 进风温度回退阈值 °C
DEFAULT_PREDICTED_RATE = 2.0       # 条件2: 基准温升速率 °C/h
DEFAULT_RATE_MULTIPLIER = 1.5      # 条件2: 超预测倍数
DEFAULT_RATE_LIMIT = 5.0           # 条件3: 温变速率限制 °C/h
DEFAULT_DEW_POINT_MARGIN = 3.0     # 条件7: 送风温度与露点最小差值 °C

# 自动恢复等待时间（秒）
RECOVERY_WAIT_TEMP = 15 * 60       # 条件1/2: 15 分钟
RECOVERY_WAIT_SENSOR = 10 * 60     # 条件5: 10 分钟
RECOVERY_WAIT_UPS = 5 * 60         # 条件6: 5 分钟
RECOVERY_WAIT_AC = 10 * 60         # 条件4: 10 分钟
RECOVERY_WAIT_HUMIDITY = 10 * 60   # 条件7: 10 分钟
RECOVERY_TEMP_HEADROOM = 4.0       # 恢复条件: 温度裕度 > 4°C


class RollbackManager:
    """回退保护管理器 — 持续监控 CoolingZone 安全状态"""

    def __init__(self):
        self._zone_states: Dict[int, Dict[str, dict]] = {}

    async def check_zone(self, zone_id: int, session: AsyncSession):
        """对单个 zone 执行全部 7 项检测 + 已触发项的恢复检测"""
        if zone_id not in self._zone_states:
            self._zone_states[zone_id] = {}

        checks = [
            (RollbackTriggerType.TEMP_OVER_LIMIT, self._check_temp_over_limit),
            (RollbackTriggerType.RATE_OVER_PREDICTED, self._check_rate_over_predicted),
            (RollbackTriggerType.RATE_OVER_LIMIT, self._check_rate_over_limit),
            (RollbackTriggerType.AC_FAULT, self._check_ac_fault),
            (RollbackTriggerType.SENSOR_OFFLINE, self._check_sensor_offline),
            (RollbackTriggerType.UPS_ACTIVE, self._check_ups_active),
            (RollbackTriggerType.HUMIDITY_DEW_POINT, self._check_humidity_dew_point),
        ]

        for trigger_type, check_fn in checks:
            try:
                result = await check_fn(zone_id, session)
                state = self._zone_states[zone_id].get(trigger_type.value)

                if result is not None:
                    # 条件触发
                    if state is None or not state.get("active"):
                        await self._trigger_rollback(
                            zone_id, trigger_type, result, session
                        )
                    # 条件仍然触发，清除恢复计时
                    if state and state.get("recovery_start"):
                        state["recovery_start"] = None
                else:
                    # 条件未触发，检查是否需要恢复
                    if state and state.get("active"):
                        await self._try_recovery(
                            zone_id, trigger_type, session
                        )
            except Exception as e:
                logger.error(f"Zone {zone_id} 检测 {trigger_type.value} 异常: {e}")

    # ==================== 7 项触发检测 ====================

    async def _check_temp_over_limit(
        self, zone_id: int, session: AsyncSession
    ) -> Optional[dict]:
        """条件1: 任一机柜 T_inlet > 26°C"""
        from app.services.precool.constraints import _get_max_inlet_temperature

        t_max = await _get_max_inlet_temperature(zone_id, session)
        if t_max is not None and t_max > DEFAULT_TEMP_ROLLBACK:
            return {
                "value": t_max,
                "threshold": DEFAULT_TEMP_ROLLBACK,
                "action": f"恢复正常制冷（T_inlet={t_max:.1f}°C > {DEFAULT_TEMP_ROLLBACK}°C）",
            }
        return None

    async def _check_rate_over_predicted(
        self, zone_id: int, session: AsyncSession
    ) -> Optional[dict]:
        """条件2: 温升速率超预测 150%"""
        from app.services.datacenter_shift_strategy import _calculate_temperature_rise_rate

        rate = await _calculate_temperature_rise_rate(zone_id, session)
        if rate <= 0:
            return None  # 降温或无变化不触发

        predicted_rate = await self._get_predicted_rate_from_schedule(zone_id, session)
        threshold = predicted_rate * DEFAULT_RATE_MULTIPLIER

        if rate > threshold:
            return {
                "value": rate,
                "threshold": threshold,
                "action": f"恢复正常制冷（温升 {rate:.2f}°C/h > 预测 {predicted_rate:.1f} × {DEFAULT_RATE_MULTIPLIER}）",
            }
        return None

    async def _get_predicted_rate_from_schedule(
        self, zone_id: int, session: AsyncSession
    ) -> float:
        """从活跃 PrecoolSchedule 的 trajectory 动态计算预测温升速率。

        在 trajectory["predicted"] 中找到当前时间对应的步骤索引，
        用相邻步骤的温度差计算速率（°C/h）。
        若无活跃计划或数据不足，回退到 SystemConfig / DEFAULT_PREDICTED_RATE。
        """
        try:
            from app.models.thermal import PrecoolSchedule

            result = await session.execute(
                select(PrecoolSchedule)
                .where(PrecoolSchedule.cooling_zone_id == zone_id)
                .where(PrecoolSchedule.status == "executing")
                .order_by(PrecoolSchedule.schedule_date.desc())
                .limit(1)
            )
            schedule = result.scalar_one_or_none()

            if schedule and schedule.temperature_trajectory:
                traj = schedule.temperature_trajectory
                predicted = traj.get("predicted", [])
                if len(predicted) >= 2:
                    now = datetime.now()
                    # 每步 5 分钟，计算当前步骤索引
                    minutes_since_midnight = now.hour * 60 + now.minute
                    step_idx = minutes_since_midnight // 5
                    step_idx = min(step_idx, len(predicted) - 1)

                    # 用当前步与前一步（或后一步）计算温升速率
                    if step_idx > 0:
                        dt_celsius = predicted[step_idx] - predicted[step_idx - 1]
                    else:
                        dt_celsius = predicted[1] - predicted[0]

                    # 5 分钟 → 每小时：× 12
                    predicted_rate = dt_celsius * 12.0
                    if predicted_rate > 0:
                        return predicted_rate
        except Exception as e:
            logger.warning(f"Zone {zone_id} 从 PrecoolSchedule 获取预测速率失败: {e}")

        # 回退: SystemConfig → 硬编码默认值
        return await self._get_config_value(
            session, "rollback_predicted_rate", DEFAULT_PREDICTED_RATE
        )

    async def _check_rate_over_limit(
        self, zone_id: int, session: AsyncSession
    ) -> Optional[dict]:
        """条件3: 温度变化超 5°C/h"""
        from app.services.datacenter_shift_strategy import _calculate_temperature_rise_rate

        rate = await _calculate_temperature_rise_rate(zone_id, session)
        abs_rate = abs(rate)

        if abs_rate > DEFAULT_RATE_LIMIT:
            return {
                "value": abs_rate,
                "threshold": DEFAULT_RATE_LIMIT,
                "action": f"限制功率调整速度（|dT/dt|={abs_rate:.2f}°C/h > {DEFAULT_RATE_LIMIT}°C/h）",
            }
        return None

    async def _check_ac_fault(
        self, zone_id: int, session: AsyncSession
    ) -> Optional[dict]:
        """条件4: 空调故障告警"""
        from app.models.topology_config import CoolingZoneUnit
        from app.models.cooling import CoolingUnit
        from app.models.point import Point, PointRealtime

        try:
            query = (
                select(PointRealtime.status, Point.point_name)
                .join(Point, Point.id == PointRealtime.point_id)
                .where(Point.device_id.in_(
                    select(CoolingUnit.device_id)
                    .join(CoolingZoneUnit, CoolingZoneUnit.cooling_unit_id == CoolingUnit.id)
                    .where(CoolingZoneUnit.zone_id == zone_id)
                ))
                .where(Point.device_type == 'AC')
                .where(PointRealtime.status.in_(['alarm', 'fault']))
            )
            result = await session.execute(query)
            fault_points = result.all()

            if fault_points:
                names = [r[1] for r in fault_points[:3]]
                return {
                    "value": len(fault_points),
                    "threshold": 0,
                    "action": f"停止功率转移（空调故障: {', '.join(names)}）",
                }
        except Exception as e:
            logger.warning(f"Zone {zone_id} 空调故障检测异常: {e}")

        return None

    async def _check_sensor_offline(
        self, zone_id: int, session: AsyncSession
    ) -> Optional[dict]:
        """条件5: 温度传感器离线"""
        from app.models.topology_config import CoolingZoneCabinet, CabinetTemperatureSensor
        from app.models.point import Point, PointRealtime

        try:
            query = (
                select(func.count())
                .select_from(PointRealtime)
                .join(Point, Point.id == PointRealtime.point_id)
                .join(CabinetTemperatureSensor, CabinetTemperatureSensor.point_id == Point.id)
                .join(CoolingZoneCabinet, CoolingZoneCabinet.cabinet_id == CabinetTemperatureSensor.cabinet_id)
                .where(CoolingZoneCabinet.zone_id == zone_id)
                .where(CabinetTemperatureSensor.sensor_location == 'inlet')
                .where(PointRealtime.status == 'offline')
            )
            result = await session.execute(query)
            offline_count = result.scalar() or 0

            if offline_count > 0:
                return {
                    "value": offline_count,
                    "threshold": 0,
                    "action": f"切回固定保守比例 0.2（{offline_count} 个进风传感器离线）",
                }
        except Exception as e:
            logger.warning(f"Zone {zone_id} 传感器离线检测异常: {e}")

        return None

    async def _check_ups_active(
        self, zone_id: int, session: AsyncSession
    ) -> Optional[dict]:
        """条件6: 市电中断切 UPS（查询 UPS DI 点位，值=1 表示电池模式）"""
        from app.models.point import Point, PointRealtime

        try:
            query = (
                select(PointRealtime.value, Point.point_name)
                .join(Point, Point.id == PointRealtime.point_id)
                .where(Point.device_type == 'UPS')
                .where(Point.point_type == 'DI')
                .where(PointRealtime.value == 1)  # 1 = 电池模式
            )
            result = await session.execute(query)
            ups_battery = result.first()

            if ups_battery:
                return {
                    "value": 1,
                    "threshold": 0,
                    "action": f"T_max 收紧到 25°C（UPS 电池模式: {ups_battery[1]}）",
                }
        except Exception as e:
            logger.warning(f"Zone {zone_id} UPS 状态检测异常: {e}")

        return None

    async def _check_humidity_dew_point(
        self, zone_id: int, session: AsyncSession
    ) -> Optional[dict]:
        """条件7: 湿度接近露点（送风温度 ≥ 露点 + 3°C）"""
        from app.models.point import Point, PointRealtime

        try:
            # 查询 TH 设备的湿度和温度点位
            query = (
                select(Point.point_name, PointRealtime.value, Point.unit)
                .join(PointRealtime, PointRealtime.point_id == Point.id)
                .where(Point.device_type == 'TH')
                .where(Point.is_enabled == True)
            )
            result = await session.execute(query)
            th_points = result.all()

            if not th_points:
                return None

            # 分离温度和湿度点位
            temps = [r[1] for r in th_points if r[2] and '°' in r[2]]
            humidities = [r[1] for r in th_points if r[2] and '%' in r[2]]

            if not temps or not humidities:
                return None

            t_supply = min(temps)  # 送风温度取最低
            rh = max(humidities)  # 湿度取最高

            if rh <= 0 or rh > 100:
                return None

            # Magnus 公式计算露点
            a, b = 17.625, 243.04
            gamma = math.log(rh / 100.0) + (a * t_supply) / (b + t_supply)
            dew_point = (b * gamma) / (a - gamma)

            margin = t_supply - dew_point
            if margin < DEFAULT_DEW_POINT_MARGIN:
                return {
                    "value": margin,
                    "threshold": DEFAULT_DEW_POINT_MARGIN,
                    "action": f"停止降温防结露（送风{t_supply:.1f}°C - 露点{dew_point:.1f}°C = {margin:.1f}°C < {DEFAULT_DEW_POINT_MARGIN}°C）",
                }
        except Exception as e:
            logger.warning(f"Zone {zone_id} 湿度/露点检测异常: {e}")

        return None

    # ==================== 回退触发与恢复 ====================

    async def _trigger_rollback(
        self,
        zone_id: int,
        trigger_type: RollbackTriggerType,
        result: dict,
        session: AsyncSession,
    ):
        """触发回退：记录事件 + 推送告警"""
        event = RollbackEvent(
            zone_id=zone_id,
            trigger_type=trigger_type.value,
            trigger_value=result.get("value"),
            threshold=result.get("threshold"),
            action=result["action"],
            status="active",
            context_json=json.dumps(result, ensure_ascii=False),
        )
        session.add(event)
        await session.flush()

        # 更新内存状态
        if zone_id not in self._zone_states:
            self._zone_states[zone_id] = {}
        self._zone_states[zone_id][trigger_type.value] = {
            "active": True,
            "since": datetime.now(),
            "event_id": event.id,
            "recovery_start": None,
        }

        logger.error(
            f"🛡️ Zone {zone_id} 回退触发: {trigger_type.value} — {result['action']}"
        )

        # WebSocket 推送
        try:
            from app.services.websocket import ws_manager
            await ws_manager.broadcast_alarm({
                "action": "rollback",
                "id": event.id,
                "zone_id": zone_id,
                "trigger_type": trigger_type.value,
                "trigger_value": result.get("value"),
                "threshold": result.get("threshold"),
                "rollback_action": result["action"],
                "timestamp": datetime.now().isoformat(),
            })
        except Exception as e:
            logger.warning(f"回退事件 WebSocket 推送失败: {e}")

    async def _try_recovery(
        self,
        zone_id: int,
        trigger_type: RollbackTriggerType,
        session: AsyncSession,
    ):
        """检查是否满足恢复条件"""
        state = self._zone_states[zone_id].get(trigger_type.value)
        if not state or not state.get("active"):
            return

        now = datetime.now()

        # 确定恢复等待时间
        wait_times = {
            RollbackTriggerType.TEMP_OVER_LIMIT.value: RECOVERY_WAIT_TEMP,
            RollbackTriggerType.RATE_OVER_PREDICTED.value: RECOVERY_WAIT_TEMP,
            RollbackTriggerType.RATE_OVER_LIMIT.value: RECOVERY_WAIT_TEMP,
            RollbackTriggerType.AC_FAULT.value: RECOVERY_WAIT_AC,
            RollbackTriggerType.SENSOR_OFFLINE.value: RECOVERY_WAIT_SENSOR,
            RollbackTriggerType.UPS_ACTIVE.value: RECOVERY_WAIT_UPS,
            RollbackTriggerType.HUMIDITY_DEW_POINT.value: RECOVERY_WAIT_HUMIDITY,
        }

        wait_seconds = wait_times.get(trigger_type.value, RECOVERY_WAIT_TEMP)

        # 首次检测到条件消失，记录恢复开始时间
        if state.get("recovery_start") is None:
            state["recovery_start"] = now
            logger.info(
                f"Zone {zone_id} {trigger_type.value} 条件消失，开始恢复计时（等待 {wait_seconds}s）"
            )
            return

        # 检查是否等待足够时间
        elapsed = (now - state["recovery_start"]).total_seconds()
        if elapsed >= wait_seconds:
            await self._execute_recovery(zone_id, trigger_type, state, session)

    async def _execute_recovery(
        self,
        zone_id: int,
        trigger_type: RollbackTriggerType,
        state: dict,
        session: AsyncSession,
    ):
        """执行恢复"""
        event_id = state.get("event_id")
        if event_id:
            event = (await session.execute(
                select(RollbackEvent).where(RollbackEvent.id == event_id)
            )).scalar_one_or_none()

            if event:
                event.status = "resolved"
                event.resolved_at = datetime.now()

        # 清除内存状态
        state["active"] = False
        state["recovery_start"] = None

        logger.info(
            f"🛡️ Zone {zone_id} 回退恢复: {trigger_type.value}"
        )

        # WebSocket 推送恢复通知
        try:
            from app.services.websocket import ws_manager
            await ws_manager.broadcast_alarm({
                "action": "rollback_recovery",
                "id": event_id,
                "zone_id": zone_id,
                "trigger_type": trigger_type.value,
                "timestamp": datetime.now().isoformat(),
            })
        except Exception as e:
            logger.warning(f"恢复通知 WebSocket 推送失败: {e}")

    # ==================== 辅助方法 ====================

    async def _get_config_value(
        self, session: AsyncSession, key: str, default: float
    ) -> float:
        """从 SystemConfig 读取单个配置值"""
        try:
            from app.models.config import SystemConfig
            result = (await session.execute(
                select(SystemConfig).where(SystemConfig.config_key == key)
            )).scalar_one_or_none()
            if result:
                return float(result.config_value)
        except Exception:
            pass
        return default

    def get_zone_rollback_status(self, zone_id: int) -> dict:
        """返回 zone 当前回退状态"""
        states = self._zone_states.get(zone_id, {})
        active_triggers = []

        for trigger_type, state in states.items():
            if state.get("active"):
                active_triggers.append({
                    "trigger_type": trigger_type,
                    "since": state["since"].isoformat() if state.get("since") else None,
                    "event_id": state.get("event_id"),
                    "recovering": state.get("recovery_start") is not None,
                })

        return {
            "zone_id": zone_id,
            "has_active_rollback": len(active_triggers) > 0,
            "active_triggers": active_triggers,
        }

    def get_all_statuses(self) -> List[dict]:
        """返回所有 zone 的回退状态"""
        return [
            self.get_zone_rollback_status(zone_id)
            for zone_id in self._zone_states
        ]


# 模块级全局实例
rollback_manager = RollbackManager()
