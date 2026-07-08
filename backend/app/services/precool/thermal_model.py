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
from ...models.topology_config import (
    CoolingZone,
    CabinetTemperatureSensor,
    CabinetITLoad,
    CoolingZoneUnit,
    CoolingZoneCabinet,
)
from ...models.thermal import ThermalParameter, TemperaturePredictionLog
from ...models.point import Point
from ...models.history import PointHistory
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
        self, zone_id: int, hours: float = 1.0, q_cool_schedule: Optional[List[float]] = None
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

        # 2. 验证 q_cool_schedule（参数检查优先）
        steps = int(hours * 12)  # 5 分钟一步
        if q_cool_schedule is not None:
            if len(q_cool_schedule) != steps:
                return {
                    "error": "invalid_q_cool_schedule",
                    "zone_id": zone_id,
                    "details": f"Expected length {steps}, got {len(q_cool_schedule)}",
                }

        # 3. 加载 RC 参数
        async with async_session() as session:
            zone_result = await self._get_zone(session, zone_id)
            if zone_result.get("error"):
                return zone_result

            zone = zone_result["zone"]

            if zone.thermal_R is None or zone.thermal_C is None:
                return {
                    "error": "parameters_not_calibrated",
                    "zone_id": zone_id,
                    "details": "thermal_R or thermal_C is NULL",
                }

            R = zone.thermal_R  # °C/kW
            C = zone.thermal_C  # kWh/°C
            beta = zone.bypass_beta if zone.bypass_beta is not None else 0.1  # 气流短路系数

            # 除零错误保护
            if R <= 0 or C <= 0:
                return {
                    "error": "invalid_parameters",
                    "zone_id": zone_id,
                    "details": f"thermal_R and thermal_C must be positive (R={R}, C={C})",
                }

            # 4. 数值稳定性检查
            dt = 5 / 60  # 5 分钟 = 1/12 小时
            if dt >= 2 * R * C:
                max_hours = max(0.5, 2 * R * C * 12)  # 最大安全预测时长，最小 0.5 小时
                return {
                    "error": "numerical_instability",
                    "zone_id": zone_id,
                    "details": f"Requested {hours}h exceeds stability limit",
                    "suggested_max_hours": round(max_hours, 2),
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
                return {"error": "data_fetch_failed", "zone_id": zone_id, "details": str(e)}

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
                    return {"error": "temperature_out_of_bounds", "zone_id": zone_id, "step": k, "temperature": T_next}

                T.append(T_next)
                time_steps.append(time_steps[0] + timedelta(minutes=(k + 1) * 5))

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
                "data_quality": quality_result,
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
                zone = (await session.execute(select(CoolingZone).limit(1))).scalar_one_or_none()
                if zone:
                    if (
                        not hasattr(zone, "thermal_R")
                        or not hasattr(zone, "thermal_C")
                        or not hasattr(zone, "bypass_beta")
                    ):
                        raise RuntimeError("CoolingZone table missing required fields")

                return {"success": True}

            except Exception as e:
                logger.error(f"Dependency check failed: {e}")
                return {
                    "error": "dependencies_not_met",
                    "details": "Story 29.1 (thermodynamic data model) must be completed first",
                }

    async def _get_zone(self, session: AsyncSession, zone_id: int) -> Dict:
        """获取制冷区域"""
        result = await session.execute(select(CoolingZone).where(CoolingZone.id == zone_id))
        zone = result.scalar_one_or_none()

        if not zone:
            return {"error": "zone_not_found", "zone_id": zone_id}

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
        from sqlalchemy import and_

        now = datetime.now()
        lookback_hours = max(24, hours)  # 至少查询 24 小时历史数据
        start_time = now - timedelta(hours=lookback_hours)

        # 1. 获取 IT 热负荷 Q_IT
        # 路径：CoolingZone → CoolingZoneCabinet → CabinetITLoad → Point → PointHistory
        q_it_query = (
            select(PointHistory.recorded_at, PointHistory.value)
            .join(Point, PointHistory.point_id == Point.id)
            .join(CabinetITLoad, Point.id == CabinetITLoad.power_point_id)
            .join(CoolingZoneCabinet, CabinetITLoad.cabinet_id == CoolingZoneCabinet.cabinet_id)
            .where(
                and_(
                    CoolingZoneCabinet.zone_id == zone_id,
                    PointHistory.recorded_at >= start_time
                )
            )
            .order_by(PointHistory.recorded_at.desc())
        )

        q_it_result = await session.execute(q_it_query)
        q_it_rows = q_it_result.fetchall()

        if len(q_it_rows) < 6:  # 最小 30 分钟数据（6 条，5分钟间隔）
            return {
                "error": "insufficient_history",
                "field": "Q_IT",
                "available_minutes": len(q_it_rows) * 5,
                "zone_id": zone_id,
            }

        # 聚合到 5 分钟间隔（平均值）
        q_it_data = self._aggregate_timeseries(q_it_rows, interval_minutes=5, agg_func="mean")

        # 应用线性插值（填补间隔 > 10 分钟的缺失点）
        q_it_timestamps = [row[0] for row in q_it_rows]
        q_it_timestamps_interp, q_it_data = self._interpolate_timeseries(q_it_timestamps, q_it_data, interval_minutes=5)

        # 2. 获取等效环境温度 T_ambient（精密空调回风温度）
        # 路径：CoolingZone → CoolingZoneUnit → CoolingUnit → Device → Point → PointHistory
        t_ambient_query = (
            select(PointHistory.recorded_at, PointHistory.value)
            .join(Point, PointHistory.point_id == Point.id)
            .join(Device, Point.device_id == Device.id)
            .join(CoolingUnit, Device.id == CoolingUnit.device_id)
            .join(CoolingZoneUnit, CoolingUnit.id == CoolingZoneUnit.cooling_unit_id)
            .where(
                and_(
                    CoolingZoneUnit.zone_id == zone_id,
                    Point.point_code.like('%_return_temp'),
                    PointHistory.recorded_at >= start_time
                )
            )
            .order_by(PointHistory.recorded_at.desc())
        )

        t_ambient_result = await session.execute(t_ambient_query)
        t_ambient_rows = t_ambient_result.fetchall()

        if not t_ambient_rows:
            return {"error": "insufficient_data", "missing_fields": ["T_ambient"], "zone_id": zone_id}

        # 聚合到 5 分钟间隔（平均值）
        t_ambient_data = self._aggregate_timeseries(t_ambient_rows, interval_minutes=5, agg_func="mean")

        # 应用线性插值
        t_ambient_timestamps = [row[0] for row in t_ambient_rows]
        t_ambient_timestamps_interp, t_ambient_data = self._interpolate_timeseries(
            t_ambient_timestamps, t_ambient_data, interval_minutes=5
        )

        # 3. 获取当前温度 T_current（进风温度传感器）
        # 路径：CoolingZone → CoolingZoneCabinet → CabinetTemperatureSensor(inlet) → Point → PointHistory
        # 聚合策略：取最大值（保守估计安全裕度）
        t_current_query = (
            select(PointHistory.recorded_at, PointHistory.value)
            .join(Point, PointHistory.point_id == Point.id)
            .join(CabinetTemperatureSensor, Point.id == CabinetTemperatureSensor.point_id)
            .join(CoolingZoneCabinet, CabinetTemperatureSensor.cabinet_id == CoolingZoneCabinet.cabinet_id)
            .where(
                and_(
                    CoolingZoneCabinet.zone_id == zone_id,
                    CabinetTemperatureSensor.sensor_location == 'inlet',
                    PointHistory.recorded_at >= now - timedelta(minutes=5)
                )
            )
            .order_by(PointHistory.recorded_at.desc())
        )

        t_current_result = await session.execute(t_current_query)
        t_current_rows = t_current_result.fetchall()

        if not t_current_rows:
            return {"error": "insufficient_data", "missing_fields": ["T_current"], "zone_id": zone_id}

        # 聚合到 5 分钟间隔，取最大值（保守估计）
        t_current_data = self._aggregate_timeseries(t_current_rows, interval_minutes=5, agg_func="max")
        t_current = t_current_data[0] if t_current_data else t_current_rows[0][1]

        # 4. 获取出风温度 T_outlet（可选）
        t_outlet_query = (
            select(PointHistory.value)
            .join(Point, PointHistory.point_id == Point.id)
            .join(CabinetTemperatureSensor, Point.id == CabinetTemperatureSensor.point_id)
            .join(CoolingZoneCabinet, CabinetTemperatureSensor.cabinet_id == CoolingZoneCabinet.cabinet_id)
            .where(
                and_(
                    CoolingZoneCabinet.zone_id == zone_id,
                    CabinetTemperatureSensor.sensor_location == 'outlet',
                    PointHistory.recorded_at >= now - timedelta(minutes=5)
                )
            )
            .order_by(PointHistory.recorded_at.desc())
            .limit(10)
        )

        t_outlet_result = await session.execute(t_outlet_query)
        t_outlet_rows = t_outlet_result.fetchall()

        t_outlet = None
        if t_outlet_rows:
            t_outlet = sum(row[0] for row in t_outlet_rows) / len(t_outlet_rows)
        else:
            logger.warning(f"Zone {zone_id}: outlet temperature sensor not found, will use T_ambient as fallback")

        # 5. 获取室外温度 T_outdoor（可选，用于 COP 季节修正）
        # 通过精密空调室外机环境温度点位（{device_code}_ambient_temp）
        # 注意：使用点位命名约定识别室外机温度，避免匹配室内环境温度
        t_outdoor_query = (
            select(PointHistory.value)
            .join(Point, PointHistory.point_id == Point.id)
            .join(Device, Point.device_id == Device.id)
            .join(CoolingUnit, Device.id == CoolingUnit.device_id)
            .join(CoolingZoneUnit, CoolingUnit.id == CoolingZoneUnit.cooling_unit_id)
            .where(
                and_(
                    CoolingZoneUnit.zone_id == zone_id,
                    Point.point_code.like('%_ambient_temp'),
                    Device.device_type == 'AC',  # 精密空调设备
                    PointHistory.recorded_at >= now - timedelta(minutes=5)
                )
            )
            .order_by(PointHistory.recorded_at.desc())
            .limit(10)
        )

        t_outdoor_result = await session.execute(t_outdoor_query)
        t_outdoor_rows = t_outdoor_result.fetchall()

        t_outdoor = None
        if t_outdoor_rows:
            t_outdoor = sum(row[0] for row in t_outdoor_rows) / len(t_outdoor_rows)
        else:
            logger.warning(f"Zone {zone_id}: outdoor temperature not found, will use default COP=3.5")

        # 6. 数据插值和 forward fill
        steps = int(hours * 12)
        q_it_filled = self._fill_timeseries(q_it_data, steps)
        t_ambient_filled = self._fill_timeseries(t_ambient_data, steps)

        return {
            "q_it": q_it_filled,
            "t_ambient": t_ambient_filled,
            "t_current": t_current,
            "t_outlet": t_outlet,
            "t_outdoor": t_outdoor,
        }

    def _aggregate_timeseries(self, rows: list, interval_minutes: int, agg_func: str) -> List[float]:
        """
        将时间序列数据聚合到指定间隔

        Args:
            rows: [(timestamp, value), ...]
            interval_minutes: 聚合间隔（分钟）
            agg_func: 聚合函数 "mean" | "max" | "min"

        Returns:
            聚合后的值列表（从最新到最旧）
        """
        if not rows:
            return []

        from collections import defaultdict

        # 按时间间隔分组
        buckets = defaultdict(list)
        for timestamp, value in rows:
            # 计算时间桶（向下取整到 interval_minutes）
            bucket_time = timestamp.replace(second=0, microsecond=0)
            bucket_minutes = (bucket_time.minute // interval_minutes) * interval_minutes
            bucket_time = bucket_time.replace(minute=bucket_minutes)
            buckets[bucket_time].append(value)

        # 聚合每个桶
        aggregated = []
        for bucket_time in sorted(buckets.keys(), reverse=True):
            values = buckets[bucket_time]
            if agg_func == "mean":
                agg_value = sum(values) / len(values)
            elif agg_func == "max":
                agg_value = max(values)
            elif agg_func == "min":
                agg_value = min(values)
            else:
                agg_value = sum(values) / len(values)

            aggregated.append(agg_value)

        return aggregated

    def _fill_timeseries(self, data: List[float], target_length: int) -> List[float]:
        """
        填充时间序列数据到目标长度

        使用策略：
        1. 如果数据足够，截取到目标长度
        2. 如果数据不足，使用 forward fill（最后一个有效值）

        Args:
            data: 原始数据（从最新到最旧）
            target_length: 目标长度

        Returns:
            填充后的数据
        """
        if not data:
            return []

        if len(data) >= target_length:
            return data[:target_length]

        # Forward fill
        filled = data.copy()
        last_value = data[-1]
        while len(filled) < target_length:
            filled.append(last_value)

        logger.warning(f"Data insufficient: {len(data)} points, filled to {target_length} using forward fill")

        return filled

    def _interpolate_timeseries(
        self, timestamps: List[datetime], values: List[float], interval_minutes: int = 5
    ) -> tuple[List[datetime], List[float]]:
        """
        对时间序列数据进行线性插值，填补间隔 > 10 分钟的缺失点

        Args:
            timestamps: 时间戳列表（从最新到最旧）
            values: 数据值列表
            interval_minutes: 目标时间间隔（分钟）

        Returns:
            (插值后的时间戳列表, 插值后的数据值列表)
        """
        if not timestamps or not values or len(timestamps) != len(values):
            return timestamps, values

        # 反转为从旧到新（便于插值）
        timestamps = list(reversed(timestamps))
        values = list(reversed(values))

        interpolated_timestamps = [timestamps[0]]
        interpolated_values = [values[0]]

        for i in range(1, len(timestamps)):
            prev_time = timestamps[i - 1]
            curr_time = timestamps[i]
            prev_value = values[i - 1]
            curr_value = values[i]

            # 计算时间间隔（分钟）
            time_diff_minutes = (curr_time - prev_time).total_seconds() / 60

            # 如果间隔 > 10 分钟，进行线性插值
            if time_diff_minutes > 10:
                num_points = int(time_diff_minutes / interval_minutes) - 1
                for j in range(1, num_points + 1):
                    # 线性插值
                    ratio = j / (num_points + 1)
                    interp_time = prev_time + timedelta(minutes=j * interval_minutes)
                    interp_value = prev_value + ratio * (curr_value - prev_value)
                    interpolated_timestamps.append(interp_time)
                    interpolated_values.append(interp_value)

            interpolated_timestamps.append(curr_time)
            interpolated_values.append(curr_value)

        # 反转回从新到旧
        return list(reversed(interpolated_timestamps)), list(reversed(interpolated_values))

    async def _check_data_quality(
        self, session: AsyncSession, zone_id: int, q_it: List[float], t_ambient: List[float], t_current: float
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
        missing_fields = []

        # 1. 检查温度数据（必需）
        if not t_ambient or len(t_ambient) == 0:
            missing_fields.append("T_ambient")
        if t_current is None:
            missing_fields.append("T_current")

        if missing_fields:
            return {"error": "insufficient_data", "missing_fields": missing_fields, "zone_id": zone_id}

        # 2. 温度异常检查
        if t_current < 0 or t_current > 50:
            return {"error": "invalid_temperature", "field": "T_current", "value": t_current, "zone_id": zone_id}

        for i, t in enumerate(t_ambient):
            if t < 0 or t > 50:
                return {
                    "error": "invalid_temperature",
                    "field": "T_ambient",
                    "index": i,
                    "value": t,
                    "zone_id": zone_id,
                }

        # 3. 温度突变检查（警告）
        t_ambient_quality = "good"
        for i in range(1, len(t_ambient)):
            if abs(t_ambient[i] - t_ambient[i - 1]) > 3.0:
                logger.warning(f"Zone {zone_id}: Temperature spike detected: {t_ambient[i - 1]} -> {t_ambient[i]}")
                t_ambient_quality = "warning"

        # 4. 传感器离线检查
        latest_temp_time = await self._get_latest_temp_timestamp(session, zone_id)
        if latest_temp_time and (datetime.now() - latest_temp_time).total_seconds() > 3600:
            return {
                "error": "sensor_offline",
                "sensor": "inlet",
                "last_update": latest_temp_time.isoformat(),
                "zone_id": zone_id,
            }

        # 5. 检查 Q_IT 数据（可估算）
        q_it_quality = "good"
        if not q_it or len(q_it) < 6:  # < 30 分钟
            # 使用估算值
            rated_power = await self._get_rated_power(session, zone_id)
            if rated_power:
                q_it_estimated = [rated_power * 0.7] * max(6, len(q_it) if q_it else 0)
                q_it.clear()
                q_it.extend(q_it_estimated)
                q_it_quality = "estimated"
                logger.warning(f"Zone {zone_id}: Q_IT data insufficient, using estimated value {rated_power * 0.7} kW")
            else:
                return {
                    "error": "insufficient_history",
                    "field": "Q_IT",
                    "available_minutes": len(q_it) * 5 if q_it else 0,
                    "zone_id": zone_id,
                }
        else:
            # 检查 Q_IT 过期
            latest_q_it_time = await self._get_latest_q_it_timestamp(session, zone_id)
            if latest_q_it_time and (datetime.now() - latest_q_it_time).total_seconds() > 86400:
                # 触发告警
                logger.error(f"Zone {zone_id}: Q_IT data stale (last update: {latest_q_it_time})")
                return {"error": "q_it_data_stale", "last_update": latest_q_it_time.isoformat(), "zone_id": zone_id}

            # 检查 Q_IT 异常
            rated_power = await self._get_rated_power(session, zone_id)
            if rated_power:
                for i, q in enumerate(q_it):
                    if q < 0 or q > rated_power * 1.5:
                        logger.warning(
                            f"Zone {zone_id}: Q_IT anomaly detected at index {i}: {q} kW (rated: {rated_power} kW)"
                        )
                        q_it[i] = rated_power * 0.7  # 使用估算值
                        q_it_quality = "estimated"

        return {
            "error": None,
            "missing_fields": [],
            "q_it_quality": q_it_quality,
            "t_ambient_quality": t_ambient_quality,
            "t_current_quality": "good",
        }

    async def _get_latest_temp_timestamp(self, session: AsyncSession, zone_id: int) -> Optional[datetime]:
        """获取最新温度数据时间戳"""
        from sqlalchemy import func

        query = (
            select(func.max(PointHistory.recorded_at))
            .join(Point, PointHistory.point_id == Point.id)
            .join(CabinetTemperatureSensor, Point.id == CabinetTemperatureSensor.point_id)
            .join(CoolingZoneCabinet, CabinetTemperatureSensor.cabinet_id == CoolingZoneCabinet.cabinet_id)
            .where(
                CoolingZoneCabinet.zone_id == zone_id,
                CabinetTemperatureSensor.sensor_location == 'inlet'
            )
        )

        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def _get_latest_q_it_timestamp(self, session: AsyncSession, zone_id: int) -> Optional[datetime]:
        """获取最新 Q_IT 数据时间戳"""
        from sqlalchemy import func

        query = (
            select(func.max(PointHistory.recorded_at))
            .join(Point, PointHistory.point_id == Point.id)
            .join(CabinetITLoad, Point.id == CabinetITLoad.power_point_id)
            .join(CoolingZoneCabinet, CabinetITLoad.cabinet_id == CoolingZoneCabinet.cabinet_id)
            .where(CoolingZoneCabinet.zone_id == zone_id)
        )

        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def _get_rated_power(self, session: AsyncSession, zone_id: int) -> Optional[float]:
        """获取机柜额定功率总和"""
        from sqlalchemy import func

        query = (
            select(func.sum(CabinetITLoad.rated_power_kw))
            .join(CoolingZoneCabinet, CabinetITLoad.cabinet_id == CoolingZoneCabinet.cabinet_id)
            .where(CoolingZoneCabinet.zone_id == zone_id)
        )

        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def _get_current_cooling(self, session: AsyncSession, zone_id: int) -> Dict:
        """
        获取当前制冷功率

        路径：CoolingZone → CoolingZoneUnit → CoolingUnit → Device → Point → PointHistory

        Returns:
            成功时: {"value": float}
            失败时: {"error": str, "details": str}
        """
        from sqlalchemy import and_

        now = datetime.now()

        query = (
            select(PointHistory.value)
            .join(Point, PointHistory.point_id == Point.id)
            .join(Device, Point.device_id == Device.id)
            .join(CoolingUnit, Device.id == CoolingUnit.device_id)
            .join(CoolingZoneUnit, CoolingUnit.id == CoolingZoneUnit.cooling_unit_id)
            .where(
                and_(
                    CoolingZoneUnit.zone_id == zone_id,
                    Point.point_code.like('%_power'),
                    PointHistory.recorded_at >= now - timedelta(minutes=5)
                )
            )
            .order_by(PointHistory.recorded_at.desc())
            .limit(10)
        )

        result = await session.execute(query)
        rows = result.fetchall()

        if not rows:
            logger.warning(f"Zone {zone_id}: current cooling power not found")
            return {"error": "current_cooling_not_found", "details": "No recent cooling power data available"}

        # 取平均值
        avg_power = sum(row[0] for row in rows) / len(rows)

        return {"value": avg_power}

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
                ThermalParameter.cooling_zone_id == zone_id, ThermalParameter.is_active == True
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
        model_version: str,
    ):
        """写入预测日志"""
        log = TemperaturePredictionLog(
            cooling_zone_id=zone_id,
            predicted_temp=predicted_temp,
            prediction_horizon_min=prediction_horizon_min,
            model_version=model_version,
            created_at=datetime.now(),
        )
        session.add(log)
        await session.commit()
