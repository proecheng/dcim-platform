"""
RC 热动力学模型核心算法

实现一阶 RC 热力学模型用于数据中心制冷区域温度预测
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import async_session
from ...models.topology_config import CoolingZone, CabinetTemperatureSensor, CabinetITLoad, CoolingZoneUnit, CoolingZoneCabinet
from ...models.thermal import ThermalParameter, TemperaturePredictionLog
from ...models.point import Point
from ...models.history import PointHistory
from ...models.asset import Cabinet
from ...models.cooling import CoolingUnit
from ...models.device import Device

logger = logging.getLogger(__name__)


class ThermalModel:
    """
    RC 热动力学模型

    使用一阶 RC 方程预测制冷区域温度变化：
    C × dT/dt = Q_IT - Q_cool + (T_ambient - T) / R

    离散化（Euler 显式）：
    T(k+1) = T(k) + (Δt/C) × [Q_IT(k) - Q_cool(k) + (T_amb(k) - T(k)) / R]
    """

    def __init__(self):
        self._dependencies_checked = False


    async def predict_temperature(
        self,
        zone_id: int,
        hours: float = 1.0,
        q_cool_schedule: Optional[List[float]] = None
    ) -> Dict:
        """
        预测制冷区域温度变化

        Args:
            zone_id: 制冷区域 ID
            hours: 预测时长（小时），默认 1.0，最长 24.0
            q_cool_schedule: 制冷功率计划（kW），长度必须等于 steps = hours × 12

        Returns:
            成功时:
            {
                "zone_id": 1,
                "predicted_temp": 25.5,
                "prediction_horizon_min": 60,
                "temperature_trajectory": [24.0, 24.2, ...],
                "time_steps": ["2026-03-11T12:00:00", ...],
                "model_version": "RC-v123",
                "data_quality": {...}
            }

            失败时:
            {
                "error": "parameters_not_calibrated" | "insufficient_data" | "numerical_instability" | ...,
                "zone_id": 1,
                "details": {...}
            }
        """
        # 1. 依赖检查（仅首次调用时执行）
        if not self._dependencies_checked:
            dep_check = await self._check_dependencies()
            if dep_check.get("error"):
                return dep_check
            self._dependencies_checked = True

        # 2. 加载 RC 参数
        async with async_session() as session:
            zone_result = await self._get_zone(session, zone_id)
            if zone_result.get("error"):
                return zone_result

            zone = zone_result["zone"]

            if zone.thermal_R is None or zone.thermal_C is None:
                return {
                    "error": "parameters_not_calibrated",
                    "zone_id": zone_id,
                    "details": "thermal_R or thermal_C is NULL"
                }

            R = zone.thermal_R  # °C/kW
            C = zone.thermal_C  # kWh/°C
            beta = zone.bypass_beta if zone.bypass_beta is not None else 0.1  # 气流短路系数

            # 3. 数值稳定性检查
            dt = 5 / 60  # 5 分钟 = 1/12 小时
            if dt >= 2 * R * C:
                max_hours = max(0.5, 2 * R * C * 12)  # 最大安全预测时长，最小 0.5 小时
                return {
                    "error": "numerical_instability",
                    "zone_id": zone_id,
                    "details": f"Requested {hours}h exceeds stability limit",
                    "suggested_max_hours": round(max_hours, 2)
                }

            # 4. 验证 q_cool_schedule
            steps = int(hours * 12)  # 5 分钟一步
            if q_cool_schedule is not None:
                if len(q_cool_schedule) != steps:
                    return {
                        "error": "invalid_q_cool_schedule",
                        "zone_id": zone_id,
                        "details": f"Expected length {steps}, got {len(q_cool_schedule)}"
                    }

            # 5. 加载历史数据
            try:
                data_result = await self._load_historical_data(session, zone_id, hours)
                if data_result.get("error"):
                    return data_result

                q_it = data_result["q_it"]
                t_ambient = data_result["t_ambient"]
                t_current = data_result["t_current"]
                t_outlet = data_result.get("t_outlet")
                t_outdoor = data_result.get("t_outdoor")

            except Exception as e:
                logger.error(f"Failed to load historical data for zone {zone_id}: {e}")
                return {
                    "error": "data_fetch_failed",
                    "zone_id": zone_id,
                    "details": str(e)
                }

            # 6. 数据质量检查
            quality_result = await self._check_data_quality(session, zone_id, q_it, t_ambient, t_current)
            if quality_result.get("error"):
                return quality_result

            # 7. 获取当前制冷功率（如果 q_cool_schedule 为 None）
            if q_cool_schedule is None:
                current_cooling_result = await self._get_current_cooling(session, zone_id)
                if current_cooling_result.get("error"):
                    # 如果无法获取当前制冷功率，使用默认值
                    logger.warning(f"Cannot get current cooling for zone {zone_id}, using default 100 kW")
                    current_cooling = 100.0
                else:
                    current_cooling = current_cooling_result["value"]

            # 8. 温度预测循环
            T = [t_current]  # 初始温度
            time_steps = [datetime.now()]

            for k in range(steps):
                # 8.1 获取当前时刻的 Q_IT 和 Q_cool
                Q_IT_k = q_it[k] if k < len(q_it) else q_it[-1]
                Q_cool_k = q_cool_schedule[k] if q_cool_schedule else current_cooling

                # 8.2 COP 季节修正
                cop = self._get_seasonal_cop(t_outdoor) if t_outdoor else 3.5
                Q_cool_effective = Q_cool_k * cop  # 制冷量 = 电功率 × COP

                # 8.3 bypass 系数校正（应用到进风温度）
                T_amb_k = t_ambient[k] if k < len(t_ambient) else t_ambient[-1]
                T_outlet_k = t_outlet if t_outlet else T_amb_k
                T_inlet_corrected = T[k] * (1 - beta) + T_outlet_k * beta

                # 8.4 RC 方程计算
                dT = (dt / C) * (Q_IT_k - Q_cool_effective + (T_amb_k - T_inlet_corrected) / R)
                T_next = T[k] + dT

                # 8.5 边界条件检查
                if T_next < 0 or T_next > 50:
                    return {
                        "error": "temperature_out_of_bounds",
                        "zone_id": zone_id,
                        "step": k,
                        "temperature": T_next
                    }

                T.append(T_next)
                time_steps.append(time_steps[0] + timedelta(minutes=(k+1)*5))

            # 9. 写入预测日志
            thermal_param_result = await self._get_active_thermal_param(session, zone_id)
            model_version = f"RC-v{thermal_param_result['id']}" if thermal_param_result.get("id") else "RC-v0"

            try:
                await self._log_prediction(session, zone_id, T[-1], int(hours * 60), model_version)
            except Exception as e:
                # 数据库写入失败不影响预测结果返回
                logger.error(f"Failed to log prediction for zone {zone_id}: {e}")

            return {
                "zone_id": zone_id,
                "predicted_temp": T[-1],
                "prediction_horizon_min": int(hours * 60),
                "temperature_trajectory": T,
                "time_steps": [ts.isoformat() for ts in time_steps],
                "model_version": model_version,
                "data_quality": quality_result
            }


    async def _check_dependencies(self) -> Dict:
        """检查 Story 29.1 的依赖是否满足"""
        async with async_session() as session:
            try:
                # 检查 thermal_parameters 表
                await session.execute(select(ThermalParameter).limit(1))

                # 检查 temperature_prediction_logs 表
                await session.execute(select(TemperaturePredictionLog).limit(1))

                # 检查 CoolingZone 表字段
                zone = await session.execute(select(CoolingZone).limit(1))
                if zone.scalar_one_or_none():
                    z = zone.scalar_one()
                    if not hasattr(z, 'thermal_R') or not hasattr(z, 'thermal_C') or not hasattr(z, 'bypass_beta'):
                        raise RuntimeError("CoolingZone table missing required fields")

                return {"success": True}

            except Exception as e:
                logger.error(f"Dependency check failed: {e}")
                return {
                    "error": "dependencies_not_met",
                    "details": "Story 29.1 (thermodynamic data model) must be completed first"
                }


    async def _get_zone(self, session: AsyncSession, zone_id: int) -> Dict:
        """获取制冷区域"""
        result = await session.execute(
            select(CoolingZone).where(CoolingZone.id == zone_id)
        )
        zone = result.scalar_one_or_none()

        if not zone:
            return {
                "error": "zone_not_found",
                "zone_id": zone_id
            }

        return {"zone": zone}


    async def _load_historical_data(self, session: AsyncSession, zone_id: int, hours: float) -> Dict:
        """
        加载历史数据

        Returns:
            {
                "q_it": List[float],  # IT 热负荷（kW）
                "t_ambient": List[float],  # 等效环境温度（°C）
                "t_current": float,  # 当前温度（°C）
                "t_outlet": Optional[float],  # 出风温度（°C）
                "t_outdoor": Optional[float]  # 室外温度（°C）
            }
        """
        # 实现数据加载逻辑（下一步实现）
        return {
            "error": "not_implemented",
            "details": "Data loading not yet implemented"
        }


    async def _check_data_quality(
        self,
        session: AsyncSession,
        zone_id: int,
        q_it: List[float],
        t_ambient: List[float],
        t_current: float
    ) -> Dict:
        """
        检查数据质量

        Returns:
            成功时:
            {
                "error": None,
                "missing_fields": [],
                "q_it_quality": "good" | "estimated" | "stale",
                "t_ambient_quality": "good" | "warning",
                "t_current_quality": "good"
            }

            失败时:
            {
                "error": "insufficient_data" | "invalid_temperature" | "sensor_offline",
                "missing_fields": [...],
                "zone_id": zone_id,
                "details": "..."
            }
        """
        # 实现数据质量检查逻辑（下一步实现）
        return {
            "error": None,
            "missing_fields": [],
            "q_it_quality": "good",
            "t_ambient_quality": "good",
            "t_current_quality": "good"
        }


    async def _get_current_cooling(self, session: AsyncSession, zone_id: int) -> Dict:
        """获取当前制冷功率"""
        # 实现当前制冷功率获取逻辑（下一步实现）
        return {
            "error": "not_implemented",
            "details": "Current cooling power retrieval not yet implemented"
        }


    def _get_seasonal_cop(self, t_outdoor: Optional[float]) -> float:
        """
        根据室外温度计算 COP 季节修正因子

        Args:
            t_outdoor: 室外温度（°C）

        Returns:
            COP 值
        """
        if t_outdoor is None:
            return 3.5  # 默认过渡季

        if t_outdoor >= 30.0:
            return 2.8  # 夏季
        elif t_outdoor >= 15.0:
            return 3.5  # 过渡季
        else:
            return 4.0  # 冬季


    async def _get_active_thermal_param(self, session: AsyncSession, zone_id: int) -> Dict:
        """获取当前生效的热参数"""
        result = await session.execute(
            select(ThermalParameter).where(
                ThermalParameter.cooling_zone_id == zone_id,
                ThermalParameter.is_active == True
            )
        )
        param = result.scalar_one_or_none()

        if param:
            return {"id": param.id}
        else:
            return {}


    async def _log_prediction(
        self,
        session: AsyncSession,
        zone_id: int,
        predicted_temp: float,
        prediction_horizon_min: int,
        model_version: str
    ):
        """写入预测日志"""
        log = TemperaturePredictionLog(
            cooling_zone_id=zone_id,
            predicted_temp=predicted_temp,
            prediction_horizon_min=prediction_horizon_min,
            model_version=model_version,
            created_at=datetime.now()
        )
        session.add(log)
        await session.commit()
