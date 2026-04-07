"""
VPP 可调容量计算服务

Story 33.1: 计算各制冷区域的分向可调容量（向下=削峰/向上=填谷），
供外部 VPP 平台查询。使用 Redis 缓存 + APScheduler 5 分钟定时刷新。
"""

import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import async_session
from ...core.redis import redis_service

logger = logging.getLogger(__name__)

# ASHRAE TC9.9 Class A1 温度范围（与 constraints.py 一致）
TEMP_MAX = 27.0  # °C
TEMP_MIN = 18.0  # °C

# 容量计算阈值
HEADROOM_DOWN_THRESHOLD = 1.0  # °C，向下可调最小裕度
HEADROOM_UP_THRESHOLD = 0.5  # °C，向上可调最小裕度

# 默认响应窗口
DEFAULT_RESPONSE_WINDOW = 1.0  # 小时

# 负载率假设
DEFAULT_LOAD_FACTOR = 0.7  # 稳态近似: 制冷功率 ≈ 额定容量 × 70%
Q_MIN_RATIO = 0.3  # 安全下限: 保留 30% 制冷

# 默认 COP
DEFAULT_COP = 3.5

# Redis 缓存
REDIS_KEY = "vpp:capacity"
REDIS_TTL = 600  # 10 分钟


class VppCapacityService:
    """VPP 可调容量计算服务"""

    async def calculate_capacity(self) -> dict:
        """
        计算所有已标定区域的聚合可调容量

        Returns:
            VppCapacityResponse 格式的 dict
        """
        async with async_session() as session:
            # 1. 查询所有已标定区域（thermal_R/C 非 NULL）
            from ...models.topology_config import CoolingZone

            result = await session.execute(
                select(CoolingZone).where(
                    CoolingZone.thermal_R.isnot(None),
                    CoolingZone.thermal_C.isnot(None),
                )
            )
            zones = result.scalars().all()

            if not zones:
                return {
                    "down_adjustable_kw": 0.0,
                    "up_adjustable_kw": 0.0,
                    "down_adjustable_thermal_kw": 0.0,
                    "up_adjustable_thermal_kw": 0.0,
                    "T_current": None,
                    "headroom_down": 0.0,
                    "headroom_up": 0.0,
                    "response_window_hours": DEFAULT_RESPONSE_WINDOW,
                    "zones": [],
                    "cached_at": None,
                }

            # 2. 逐区域计算
            zone_results: List[dict] = []
            for zone in zones:
                try:
                    zone_cap = await self._calculate_zone_capacity(zone, session)
                    if zone_cap is not None:
                        zone_results.append(zone_cap)
                except Exception as e:
                    logger.warning(f"Zone {zone.id} 容量计算失败: {e}")

            # 3. 聚合
            total_down_kw = sum(z["down_adjustable_kw"] for z in zone_results)
            total_up_kw = sum(z["up_adjustable_kw"] for z in zone_results)
            total_down_thermal = sum(z["down_adjustable_thermal_kw"] for z in zone_results)
            total_up_thermal = sum(z["up_adjustable_thermal_kw"] for z in zone_results)

            # T_current: 所有区域中的最高温度
            temps = [z["T_current"] for z in zone_results if z["T_current"] is not None]
            t_current_agg = max(temps) if temps else None

            # headroom: 各区域最小裕度（最保守）
            headroom_downs = [z["headroom_down"] for z in zone_results]
            headroom_ups = [z["headroom_up"] for z in zone_results]
            min_headroom_down = min(headroom_downs) if headroom_downs else 0.0
            min_headroom_up = min(headroom_ups) if headroom_ups else 0.0

            return {
                "down_adjustable_kw": round(total_down_kw, 2),
                "up_adjustable_kw": round(total_up_kw, 2),
                "down_adjustable_thermal_kw": round(total_down_thermal, 2),
                "up_adjustable_thermal_kw": round(total_up_thermal, 2),
                "T_current": round(t_current_agg, 2) if t_current_agg is not None else None,
                "headroom_down": round(min_headroom_down, 2),
                "headroom_up": round(min_headroom_up, 2),
                "response_window_hours": DEFAULT_RESPONSE_WINDOW,
                "zones": zone_results,
                "cached_at": None,
            }

    async def _calculate_zone_capacity(self, zone, session: AsyncSession) -> Optional[dict]:
        """
        单区域容量计算

        Returns:
            VppZoneCapacity 格式的 dict，或 None（温度数据不可用时跳过）
        """
        from ...models.topology_config import (
            CoolingZoneCabinet,
            CabinetTemperatureSensor,
            CoolingZoneUnit,
        )
        from ...models.cooling import CoolingUnit
        from ...models.point import Point
        from ...models.point import PointRealtime

        zone_id = zone.id
        R = zone.thermal_R
        C = zone.thermal_C

        # R/C 必须 > 0
        if not R or R <= 0 or not C or C <= 0:
            logger.warning(f"Zone {zone_id}: R={R}, C={C} 无效，跳过")
            return None

        # 1. 获取当前温度（进风最高值）— PointRealtime
        t_current = await self._get_current_temperature(
            zone_id, session, CoolingZoneCabinet, CabinetTemperatureSensor, Point, PointRealtime
        )
        if t_current is None:
            logger.warning(f"Zone {zone_id}: 温度数据不可用，跳过")
            return None

        # 2. 获取 Q_total（额定制冷功率总和）
        q_total = await self._get_total_cooling_capacity(zone_id, session, CoolingZoneUnit, CoolingUnit)
        if q_total is None or q_total <= 0:
            logger.warning(f"Zone {zone_id}: 无制冷功率数据，跳过")
            return None

        # 3. 估算当前制冷功率和安全上下限
        q_cool_est = q_total * DEFAULT_LOAD_FACTOR  # 70% 负载率
        q_max = q_total
        q_min = q_total * Q_MIN_RATIO  # 30% 安全下限

        # 4. 获取 COP（季节修正）
        cop = await self._get_cop(zone_id, session, CoolingZoneUnit, CoolingUnit)

        # 5. 计算向下裕度（减少制冷 → 温度上升 → 需要到 TEMP_MAX 的空间）
        headroom_down = TEMP_MAX - t_current
        if headroom_down <= HEADROOM_DOWN_THRESHOLD:
            down_thermal = 0.0
        else:
            down_thermal = min(
                q_cool_est - q_min,
                C * (headroom_down - HEADROOM_DOWN_THRESHOLD) / DEFAULT_RESPONSE_WINDOW,
            )
            down_thermal = max(0.0, down_thermal)

        # 6. 计算向上裕度（增加制冷 → 温度下降 → 需要到 TEMP_MIN 的空间）
        headroom_up = t_current - TEMP_MIN
        if headroom_up <= HEADROOM_UP_THRESHOLD:
            up_thermal = 0.0
        else:
            up_thermal = min(
                q_max - q_cool_est,
                C * (headroom_up - HEADROOM_UP_THRESHOLD) / DEFAULT_RESPONSE_WINDOW,
            )
            up_thermal = max(0.0, up_thermal)

        # 7. 转换为电功率
        down_kw = down_thermal / cop
        up_kw = up_thermal / cop

        return {
            "zone_id": zone_id,
            "zone_name": zone.zone_name,
            "T_current": round(t_current, 2),
            "headroom_down": round(headroom_down, 2),
            "headroom_up": round(headroom_up, 2),
            "down_adjustable_thermal_kw": round(down_thermal, 2),
            "up_adjustable_thermal_kw": round(up_thermal, 2),
            "down_adjustable_kw": round(down_kw, 2),
            "up_adjustable_kw": round(up_kw, 2),
            "cop": round(cop, 2),
        }

    async def _get_current_temperature(
        self, zone_id, session, CoolingZoneCabinet, CabinetTemperatureSensor, Point, PointRealtime
    ) -> Optional[float]:
        """获取 zone 内最高进风温度（PointRealtime）"""
        try:
            query = (
                select(func.max(PointRealtime.value))
                .join(Point, PointRealtime.point_id == Point.id)
                .join(CabinetTemperatureSensor, CabinetTemperatureSensor.point_id == Point.id)
                .join(CoolingZoneCabinet, CoolingZoneCabinet.cabinet_id == CabinetTemperatureSensor.cabinet_id)
                .where(
                    CoolingZoneCabinet.zone_id == zone_id,
                    CabinetTemperatureSensor.sensor_location == "inlet",
                )
            )
            result = await session.execute(query)
            return result.scalar()
        except Exception as e:
            logger.error(f"Zone {zone_id}: 查询温度失败: {e}")
            return None

    async def _get_total_cooling_capacity(self, zone_id, session, CoolingZoneUnit, CoolingUnit) -> Optional[float]:
        """获取 zone 总额定制冷功率"""
        try:
            query = (
                select(func.sum(CoolingUnit.cooling_capacity_kw))
                .join(CoolingZoneUnit, CoolingZoneUnit.cooling_unit_id == CoolingUnit.id)
                .where(CoolingZoneUnit.zone_id == zone_id)
            )
            result = await session.execute(query)
            return result.scalar()
        except Exception as e:
            logger.error(f"Zone {zone_id}: 查询制冷功率失败: {e}")
            return None

    async def _get_cop(self, zone_id, session, CoolingZoneUnit, CoolingUnit) -> float:
        """获取 COP（季节修正），复用 thermal_model._get_seasonal_cop 逻辑"""
        try:
            from ...models.device import Device
            from ...models.point import Point
            from ...models.point import PointRealtime

            # 查询室外温度: CoolingZoneUnit → CoolingUnit → Device → Point → PointRealtime
            query = (
                select(PointRealtime.value)
                .join(Point, PointRealtime.point_id == Point.id)
                .join(Device, Point.device_id == Device.id)
                .join(CoolingUnit, Device.id == CoolingUnit.device_id)
                .join(CoolingZoneUnit, CoolingUnit.id == CoolingZoneUnit.cooling_unit_id)
                .where(
                    CoolingZoneUnit.zone_id == zone_id,
                    Point.point_code.like("%_ambient_temp"),
                )
                .limit(1)
            )
            result = await session.execute(query)
            t_outdoor = result.scalar()

            return self._seasonal_cop(t_outdoor)
        except Exception as e:
            logger.warning(f"Zone {zone_id}: COP 查询失败，使用默认值 {DEFAULT_COP}: {e}")
            return DEFAULT_COP

    @staticmethod
    def _seasonal_cop(t_outdoor: Optional[float]) -> float:
        """根据室外温度返回季节 COP"""
        if t_outdoor is None:
            return DEFAULT_COP
        if t_outdoor >= 30.0:
            return 2.8  # 夏季
        elif t_outdoor >= 15.0:
            return 3.5  # 过渡季
        else:
            return 4.0  # 冬季

    async def get_cached_capacity(self) -> Optional[dict]:
        """从 Redis 读取缓存的容量数据"""
        return await redis_service.get_json(REDIS_KEY)

    async def refresh_capacity_cache(self) -> dict:
        """刷新 Redis 缓存"""
        result = await self.calculate_capacity()
        result["cached_at"] = datetime.now().isoformat()
        await redis_service.set_json(REDIS_KEY, result, ttl=REDIS_TTL)
        logger.info("VPP 容量缓存已刷新")
        return result


# 全局单例
vpp_capacity_service = VppCapacityService()
