"""
RC 参数最小二乘自动校准服务

Story 32.1: 基于历史温度数据自动校准制冷区域的 R 和 C 参数
利用自然发生的功率变化事件（群控切换、故障恢复、定时启停）数据进行拟合
禁止在生产环境主动制造功率扰动

核心算法：T(t) = T_steady + (T0 - T_steady) × e^(-t/τ)，τ=RC
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session

logger = logging.getLogger(__name__)

# scipy 条件导入
try:
    from scipy.optimize import curve_fit
    import numpy as np

    _scipy_available = True
except ImportError:
    _scipy_available = False
    logger.warning("scipy 未安装，RC 参数自动校准功能不可用")

# 校准配置常量
CALIBRATION_WINDOW_DAYS = 7  # 校准数据窗口（天）
MIN_VALID_SAMPLES = 20  # 最小有效样本数
MIN_R_SQUARED = 0.7  # R² 质量门槛
MIN_POWER_CHANGE_RATIO = 0.1  # 最小功率变化比（10%）
MAX_POWER_CHANGE_RATIO = 0.5  # 最大功率变化比（50%，极端事件）
ENV_TEMP_LOWER = 10.0  # 环境温度下限
ENV_TEMP_UPPER = 35.0  # 环境温度上限
TAU_MIN_HOURS = 0.5  # τ 最小值（小时）
TAU_MAX_HOURS = 8.0  # τ 最大值（小时）
TEMP_TRAJECTORY_MINUTES = 120  # 事件后温度轨迹采样窗口
MAX_RECORDS_KEPT = 10  # 最大保留校准记录数


class RCCalibrator:
    """RC 参数自动校准器"""

    async def calibrate(self, zone_id: int) -> dict[str, Any]:
        """校准指定制冷区域的 R/C 参数

        Args:
            zone_id: 制冷区域 ID

        Returns:
            dict: 校准结果，包含 R, C, r_squared, sample_count 或 error 信息
        """
        if not _scipy_available:
            return {"error": "scipy_not_installed"}

        async with async_session() as session:
            try:
                # 1. 收集校准事件数据
                events = await self._collect_calibration_events(zone_id, session)
                if not events:
                    return {"error": "no_events", "valid_samples": 0}

                # 2. 获取温度传感器 point_id
                point_ids = await self._get_temperature_point_ids(zone_id, session)
                if not point_ids:
                    return {"error": "no_temperature_sensors"}

                # 3. 为每个事件提取温度轨迹
                samples = await self._build_fitting_samples(
                    events, point_ids, session
                )

                # 4. 异常值过滤
                filtered = self._filter_outliers(samples)
                if len(filtered) < MIN_VALID_SAMPLES:
                    return {
                        "error": "insufficient_data",
                        "valid_samples": len(filtered),
                    }

                # 5. 拟合 R/C 参数
                fit_result = self._fit_rc_parameters(filtered)
                if "error" in fit_result:
                    return fit_result

                # 6. 物理合理性检查
                validation = self._validate_result(
                    fit_result["R"], fit_result["C"]
                )
                if "error" in validation:
                    return validation

                # 7. R² 质量检查
                if fit_result["r_squared"] < MIN_R_SQUARED:
                    return {
                        "error": "fitting_quality_low",
                        "r_squared": fit_result["r_squared"],
                    }

                # 8. 保存校准结果
                await self._save_calibration(
                    zone_id,
                    fit_result["R"],
                    fit_result["C"],
                    fit_result["r_squared"],
                    len(filtered),
                    session,
                )
                try:
                    await session.commit()
                except Exception as e:
                    logger.error(f"Zone {zone_id} 校准保存提交失败: {e}")
                    return {"error": "commit_failed", "detail": str(e)}

                logger.info(
                    f"Zone {zone_id} 校准成功: R={fit_result['R']:.6f}, "
                    f"C={fit_result['C']:.4f}, R²={fit_result['r_squared']:.4f}, "
                    f"samples={len(filtered)}"
                )

                return {
                    "success": True,
                    "R": fit_result["R"],
                    "C": fit_result["C"],
                    "r_squared": fit_result["r_squared"],
                    "sample_count": len(filtered),
                }

            except Exception as e:
                logger.error(f"Zone {zone_id} 校准异常: {e}", exc_info=True)
                return {"error": "calibration_exception", "detail": str(e)}

    async def _collect_calibration_events(
        self, zone_id: int, session: AsyncSession
    ) -> list[dict]:
        """从 CoolingLinkageRecord 提取校准事件数据

        通过 CoolingLinkageRecord → ShiftExecution → ShiftPlan.selected_devices
        关联链过滤目标 zone 的事件
        """
        from app.models.load_shift import (
            CoolingLinkageRecord,
            ShiftExecution,
            ShiftPlan,
        )
        from app.models.topology_config import CoolingZoneUnit

        cutoff_date = datetime.now() - timedelta(days=CALIBRATION_WINDOW_DAYS)

        # 获取 zone 关联的空调设备 ID
        unit_result = await session.execute(
            select(CoolingZoneUnit.cooling_unit_id).where(
                CoolingZoneUnit.zone_id == zone_id
            )
        )
        zone_unit_ids = {r[0] for r in unit_result.all()}
        if not zone_unit_ids:
            logger.warning(f"Zone {zone_id} 无关联空调设备")
            return []

        # 查询 adjust/recovery 事件（JOIN ShiftExecution）
        query = (
            select(
                CoolingLinkageRecord,
                ShiftExecution.plan_id,
            )
            .join(
                ShiftExecution,
                CoolingLinkageRecord.execution_id == ShiftExecution.id,
            )
            .where(
                CoolingLinkageRecord.event_type.in_(["adjust", "recovery"])
            )
            .where(CoolingLinkageRecord.timestamp >= cutoff_date)
            .where(CoolingLinkageRecord.before_power > 0)
            .order_by(CoolingLinkageRecord.timestamp)
        )

        result = await session.execute(query)
        rows = result.all()

        if not rows:
            return []

        # 批量查询 ShiftPlan 获取 selected_devices
        plan_ids = {r[1] for r in rows}
        plan_result = await session.execute(
            select(ShiftPlan.id, ShiftPlan.selected_devices).where(
                ShiftPlan.id.in_(plan_ids)
            )
        )
        plan_devices = {r[0]: r[1] for r in plan_result.all()}

        # 应用层过滤：检查 selected_devices 是否包含 zone 关联的设备
        events = []
        for record, plan_id in rows:
            devices = plan_devices.get(plan_id, [])
            if not devices:
                continue

            # selected_devices 是 JSON list of dicts with device_id
            device_ids_in_plan = set()
            if isinstance(devices, list):
                for d in devices:
                    if isinstance(d, dict) and "device_id" in d:
                        device_ids_in_plan.add(d["device_id"])
                    elif isinstance(d, (int, float)):
                        device_ids_in_plan.add(int(d))

            # 检查是否与 zone 关联
            if not zone_unit_ids.intersection(device_ids_in_plan):
                continue

            # 过滤功率变化比 > 10%
            power_ratio = abs(record.power_change / record.before_power)
            if power_ratio < MIN_POWER_CHANGE_RATIO:
                continue

            events.append(
                {
                    "timestamp": record.timestamp,
                    "before_power": record.before_power,
                    "after_power": record.after_power,
                    "power_change": record.power_change,
                    "return_temp_before": record.return_temp_before,
                    "return_temp_after": record.return_temp_after,
                    "supply_temp_before": record.supply_temp_before,
                    "supply_temp_after": record.supply_temp_after,
                    "cop_before": record.cop_before,
                    "cop_after": record.cop_after,
                }
            )

        logger.info(
            f"Zone {zone_id} 收集到 {len(events)} 个校准事件 "
            f"(窗口: {CALIBRATION_WINDOW_DAYS} 天)"
        )
        return events

    async def _get_temperature_point_ids(
        self, zone_id: int, session: AsyncSession
    ) -> list[int]:
        """获取 zone 关联的回风温度传感器 point_id 列表"""
        from app.models.topology_config import (
            CoolingZoneCabinet,
            CabinetTemperatureSensor,
        )

        result = await session.execute(
            select(CabinetTemperatureSensor.point_id)
            .join(
                CoolingZoneCabinet,
                CabinetTemperatureSensor.cabinet_id
                == CoolingZoneCabinet.cabinet_id,
            )
            .where(CoolingZoneCabinet.zone_id == zone_id)
            .where(CabinetTemperatureSensor.sensor_location == "ambient")
            .where(CabinetTemperatureSensor.point_id.isnot(None))
            .distinct()
        )
        point_ids = [r[0] for r in result.all()]
        if not point_ids:
            logger.warning(f"Zone {zone_id} 无 ambient 温度传感器点位")
        return point_ids

    async def _build_fitting_samples(
        self,
        events: list[dict],
        point_ids: list[int],
        session: AsyncSession,
    ) -> list[dict]:
        """为每个事件提取后续温度轨迹，构建拟合样本"""
        from app.models.history import PointHistory

        samples = []

        for event in events:
            event_time = event["timestamp"]
            end_time = event_time + timedelta(minutes=TEMP_TRAJECTORY_MINUTES)

            # 查询事件后的温度时序（按时间聚合平均温度）
            result = await session.execute(
                select(
                    PointHistory.recorded_at,
                    func.avg(PointHistory.value).label("avg_temp"),
                )
                .where(PointHistory.point_id.in_(point_ids))
                .where(
                    PointHistory.recorded_at.between(event_time, end_time)
                )
                .group_by(PointHistory.recorded_at)
                .order_by(PointHistory.recorded_at)
            )
            temp_series = result.all()

            if len(temp_series) < 3:
                continue

            # 构建样本：t（小时）和 T（温度）
            t0 = temp_series[0][0]
            t_data = []
            T_data = []
            for ts, temp in temp_series:
                dt_hours = (ts - t0).total_seconds() / 3600.0
                t_data.append(dt_hours)
                T_data.append(float(temp))

            samples.append(
                {
                    "t_data": t_data,
                    "T_data": T_data,
                    "T0": T_data[0],
                    "T_ambient": event.get("return_temp_before", T_data[0]),
                    "Q_IT": abs(event.get("before_power", 0)),
                    "power_change": event.get("power_change", 0),
                    "before_power": event.get("before_power", 0),
                    "env_temp": event.get("return_temp_before", 20.0),
                }
            )

        logger.info(f"构建了 {len(samples)} 个拟合样本")
        return samples

    def _filter_outliers(self, samples: list[dict]) -> list[dict]:
        """异常值过滤：3σ + 极端事件 + 环境温度"""
        if not samples:
            return []

        # 提取数据用于统计
        env_temps = np.array([s["env_temp"] for s in samples])
        power_changes = np.array([abs(s["power_change"]) for s in samples])
        before_powers = np.array(
            [max(s["before_power"], 0.01) for s in samples]
        )

        # 1. 3σ 过滤环境温度异常值
        if len(env_temps) > 2:
            mean_temp = np.mean(env_temps)
            std_temp = np.std(env_temps)
            if std_temp > 0:
                mask_3sigma = np.abs(env_temps - mean_temp) <= 3 * std_temp
            else:
                mask_3sigma = np.ones(len(env_temps), dtype=bool)
        else:
            mask_3sigma = np.ones(len(env_temps), dtype=bool)

        # 2. 极端事件过滤（power_change > 50%）
        mask_power = (power_changes / before_powers) <= MAX_POWER_CHANGE_RATIO

        # 3. 环境温度范围过滤
        mask_env = (env_temps >= ENV_TEMP_LOWER) & (
            env_temps <= ENV_TEMP_UPPER
        )

        # 组合过滤
        valid_mask = mask_3sigma & mask_power & mask_env

        filtered = [s for s, valid in zip(samples, valid_mask) if valid]

        removed = len(samples) - len(filtered)
        if removed > 0:
            logger.info(f"异常值过滤移除 {removed} 个样本，保留 {len(filtered)} 个")

        return filtered

    def _fit_rc_parameters(self, samples: list[dict]) -> dict[str, Any]:
        """使用 scipy.optimize.curve_fit 拟合 R 和 C 参数

        将所有样本的温度轨迹合并拟合，得到全局 R/C
        """
        # 合并所有样本的时间-温度数据
        all_t = []
        all_T = []
        all_T0 = []
        all_T_ambient = []
        all_Q_IT = []

        for sample in samples:
            t_arr = np.array(sample["t_data"])
            T_arr = np.array(sample["T_data"])
            n = len(t_arr)

            all_t.extend(t_arr.tolist())
            all_T.extend(T_arr.tolist())
            all_T0.extend([sample["T0"]] * n)
            all_T_ambient.extend([sample["T_ambient"]] * n)
            all_Q_IT.extend([sample["Q_IT"]] * n)

        t_data = np.array(all_t)
        T_data = np.array(all_T)
        T0_arr = np.array(all_T0)
        T_amb_arr = np.array(all_T_ambient)
        Q_IT_arr = np.array(all_Q_IT)

        def temp_response(t, R, C):
            """温度响应模型: T(t) = T_steady + (T0 - T_steady) × e^(-t/τ)"""
            tau = R * C
            tau = np.maximum(tau, 1e-6)  # 避免除零
            T_steady = T_amb_arr + Q_IT_arr * R
            return T_steady + (T0_arr - T_steady) * np.exp(-t / tau)

        try:
            popt, pcov = curve_fit(
                temp_response,
                t_data,
                T_data,
                p0=[0.03, 2.0],
                bounds=([0.001, 0.1], [0.2, 50.0]),
                maxfev=5000,
            )
            R_fit, C_fit = popt

            # 计算 R²
            T_predicted = temp_response(t_data, R_fit, C_fit)
            ss_res = np.sum((T_data - T_predicted) ** 2)
            ss_tot = np.sum((T_data - np.mean(T_data)) ** 2)
            r_squared = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

            return {
                "R": float(R_fit),
                "C": float(C_fit),
                "r_squared": r_squared,
            }

        except (RuntimeError, ValueError) as e:
            logger.warning(f"curve_fit 拟合失败: {e}")
            return {"error": "fitting_failed", "detail": str(e)}

    def _validate_result(self, R: float, C: float) -> dict[str, Any]:
        """物理合理性检查"""
        if R <= 0:
            return {"error": "invalid_R", "R": R}
        if C <= 0:
            return {"error": "invalid_C", "C": C}

        tau = R * C
        if tau < TAU_MIN_HOURS or tau > TAU_MAX_HOURS:
            return {
                "error": "tau_out_of_range",
                "tau": tau,
                "range": f"[{TAU_MIN_HOURS}, {TAU_MAX_HOURS}]",
            }

        return {"valid": True}

    async def _save_calibration(
        self,
        zone_id: int,
        R: float,
        C: float,
        r_squared: float,
        sample_count: int,
        session: AsyncSession,
    ) -> None:
        """保存校准结果到 ThermalParameter 表并更新 CoolingZone"""
        from app.models.thermal import ThermalParameter
        from app.models.topology_config import CoolingZone

        now = datetime.now()

        # 1. 清理旧的 is_active=False 记录（UniqueConstraint 限制每 zone 只能有一个 False）
        await session.execute(
            delete(ThermalParameter)
            .where(ThermalParameter.cooling_zone_id == zone_id)
            .where(ThermalParameter.is_active == False)  # noqa: E712
        )

        # 2. 停用当前活跃参数
        await session.execute(
            update(ThermalParameter)
            .where(ThermalParameter.cooling_zone_id == zone_id)
            .where(ThermalParameter.is_active == True)  # noqa: E712
            .values(is_active=False)
        )
        await session.flush()  # 确保 UPDATE 先到数据库，避免唯一约束冲突

        # 3. 创建新参数记录
        param = ThermalParameter(
            cooling_zone_id=zone_id,
            thermal_R=R,
            thermal_C=C,
            fitting_r_squared=r_squared,
            fitting_method="auto_fit",
            sample_count=sample_count,
            calibrated_at=now,
            is_active=True,
            is_demo=False,
        )
        session.add(param)

        # 4. 同步更新 CoolingZone
        await session.execute(
            update(CoolingZone)
            .where(CoolingZone.id == zone_id)
            .values(thermal_R=R, thermal_C=C, r_calibrated_at=now)
        )

    async def run_monthly_calibration(self) -> dict[str, Any]:
        """月度全区域校准（APScheduler 定时任务调用）

        遍历所有非 demo 的 CoolingZone 逐一校准
        单个 zone 校准失败不中断其他 zone
        """
        from app.models.topology_config import CoolingZone
        from app.models.thermal import ThermalParameter

        logger.info("开始月度 RC 参数自动校准...")
        results = {"success": [], "failed": [], "skipped": []}

        async with async_session() as session:
            # 获取所有非 demo zone
            # 排除有 is_demo=True 活跃参数的 zone
            demo_zone_subq = (
                select(ThermalParameter.cooling_zone_id)
                .where(ThermalParameter.is_demo == True)  # noqa: E712
                .where(ThermalParameter.is_active == True)  # noqa: E712
            )
            zone_result = await session.execute(
                select(CoolingZone.id).where(
                    CoolingZone.id.notin_(demo_zone_subq)
                )
            )
            zone_ids = [r[0] for r in zone_result.all()]

        for zone_id in zone_ids:
            try:
                result = await self.calibrate(zone_id)
                if result.get("success"):
                    results["success"].append(
                        {"zone_id": zone_id, **result}
                    )
                elif result.get("error") in (
                    "no_events",
                    "insufficient_data",
                    "no_temperature_sensors",
                ):
                    results["skipped"].append(
                        {"zone_id": zone_id, **result}
                    )
                    logger.warning(
                        f"Zone {zone_id} 校准跳过: {result.get('error')}"
                    )
                else:
                    results["failed"].append(
                        {"zone_id": zone_id, **result}
                    )
                    logger.warning(
                        f"Zone {zone_id} 校准失败: {result.get('error')}"
                    )
            except Exception as e:
                results["failed"].append(
                    {"zone_id": zone_id, "error": str(e)}
                )
                logger.error(
                    f"Zone {zone_id} 校准异常: {e}", exc_info=True
                )

        logger.info(
            f"月度校准完成: 成功={len(results['success'])}, "
            f"跳过={len(results['skipped'])}, "
            f"失败={len(results['failed'])}"
        )
        return results


# 模块级单例
rc_calibrator = RCCalibrator()
