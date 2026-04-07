"""
预冷计划执行引擎

Story 31.2: 按 APScheduler 定时触发，执行预冷计划的制冷功率调整，
监控温度偏差和安全约束，自动中止或完成。
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.thermal import PrecoolSchedule

logger = logging.getLogger(__name__)


class PrecoolExecutor:
    """预冷计划执行引擎

    两个定时任务：
    - scan_and_execute_plans(): 每分钟扫描 pending 计划，启动到时间的
    - tick_executing_plans(): 每 5 分钟推进 executing 计划的当前步
    """

    # ==================== 定时任务入口 ====================

    async def scan_and_execute_plans(self):
        """扫描 pending 计划，启动到时间的计划"""
        from app.core.database import async_session

        async with async_session() as session:
            now = datetime.now()
            today = now.date()
            current_time = now.time()

            result = await session.execute(
                select(PrecoolSchedule).where(
                    PrecoolSchedule.status == "pending",
                    PrecoolSchedule.schedule_date == today,
                    PrecoolSchedule.precool_start_time <= current_time,
                    PrecoolSchedule.peak_end_time >= current_time,
                )
            )
            plans = result.scalars().all()

            for plan in plans:
                try:
                    await self._start_execution(plan, session)
                except Exception as e:
                    logger.error(f"启动预冷计划 {plan.id} 失败: {e}")

            await session.commit()

    async def tick_executing_plans(self):
        """推进 executing 状态的计划"""
        from app.core.database import async_session

        async with async_session() as session:
            result = await session.execute(
                select(PrecoolSchedule).where(
                    PrecoolSchedule.status == "executing",
                )
            )
            plans = result.scalars().all()

            for plan in plans:
                try:
                    await self._tick_plan(plan, session)
                except Exception as e:
                    logger.error(f"推进预冷计划 {plan.id} 失败: {e}")

            await session.commit()

    # ==================== 启动执行 ====================

    async def _start_execution(self, plan: PrecoolSchedule, session: AsyncSession):
        """启动计划执行"""
        config = await self._load_linkage_config(plan.cooling_zone_id, session)
        if not config or not getattr(config, "precool_enabled", False):
            logger.warning("Zone %d 预冷未启用，跳过计划 %d", plan.cooling_zone_id, plan.id)
            return

        plan.status = "executing"
        logger.info(
            "🔄 预冷计划 %d 开始执行 zone=%d date=%s",
            plan.id,
            plan.cooling_zone_id,
            plan.schedule_date,
        )

    # ==================== 单次推进 ====================

    async def _tick_plan(self, plan: PrecoolSchedule, session: AsyncSession):
        """单次推进计划"""
        now = datetime.now()

        # 使用 datetime 比较避免 midnight 跨天问题
        plan_end_dt = datetime.combine(plan.schedule_date, plan.peak_end_time)
        if now >= plan_end_dt:
            await self._complete_plan(plan, session)
            return

        # 安全检查
        safety_status = self._check_safety(plan.cooling_zone_id)
        if safety_status.get("has_active_rollback"):
            triggers = [t["trigger_type"] for t in safety_status.get("active_triggers", [])]
            step_index = self._get_current_step_index()
            actual_temp = await self._get_actual_temperature(plan.cooling_zone_id, session)
            await self._abort_plan(
                plan,
                f"rollback: {','.join(triggers)}",
                step_index,
                actual_temp,
                session,
            )
            return

        # 执行当前步
        step_index = self._get_current_step_index()
        await self._execute_step(step_index, plan, session)

    # ==================== 步索引计算 ====================

    def _get_current_step_index(self) -> int:
        """根据当前时间计算绝对步索引

        使用绝对步号，与 trajectory 288 步数组索引直接对齐：
        step_index = now.hour * 12 + now.minute // 5
        trajectory[0] = 00:00, trajectory[96] = 08:00, trajectory[287] = 23:55
        """
        now = datetime.now()
        return min(now.hour * 12 + now.minute // 5, 287)

    # ==================== 单步执行 ====================

    async def _execute_step(self, step_index: int, plan: PrecoolSchedule, session: AsyncSession):
        """执行单步：下发制冷调整指令"""
        trajectory = plan.temperature_trajectory or {}
        q_cool_schedule = trajectory.get("q_cool", [])

        if step_index >= len(q_cool_schedule):
            return

        target_q_cool = q_cool_schedule[step_index]
        current_q_cool = await self._get_current_cooling_power(plan.cooling_zone_id, session)
        config = await self._load_linkage_config(plan.cooling_zone_id, session)

        # 应用功率调整
        actual_q_cool = await self._apply_cooling_adjustment(
            plan.cooling_zone_id, target_q_cool, current_q_cool, config, session
        )

        # 获取实际温度
        actual_temp = await self._get_actual_temperature(plan.cooling_zone_id, session)

        # 偏差检查
        predicted_temps = trajectory.get("predicted", [])
        if step_index < len(predicted_temps):
            deviation = abs(actual_temp - predicted_temps[step_index])
            if deviation > 3.0:
                # abort 前先写入当步 actual 数据
                self._record_actual_data(trajectory, step_index, actual_temp, actual_q_cool)
                plan.temperature_trajectory = trajectory
                await self._abort_plan(
                    plan,
                    f"temperature_deviation_{deviation:.1f}C",
                    step_index,
                    actual_temp,
                    session,
                )
                return
            if deviation > 2.0:
                logger.warning(
                    "预冷计划 %d 步 %d 温度偏差 %.1f°C（实际 %.1f vs 预测 %.1f）",
                    plan.id,
                    step_index,
                    deviation,
                    actual_temp,
                    predicted_temps[step_index],
                )

        # 记录实际数据到 trajectory
        self._record_actual_data(trajectory, step_index, actual_temp, actual_q_cool)
        plan.temperature_trajectory = trajectory

    # ==================== 功率调整 ====================

    async def _apply_cooling_adjustment(
        self,
        zone_id: int,
        target_q: float,
        current_q: float,
        config,
        session: AsyncSession,
    ) -> float:
        """下发制冷调整，遵守 power_adjust_step 和 max_adjust_ratio"""
        from app.core.database import async_session

        step_limit = config.power_adjust_step if config and config.power_adjust_step else 20
        max_ratio = config.max_adjust_ratio if config and config.max_adjust_ratio else 0.25

        delta = target_q - current_q
        # 速率限幅
        if abs(delta) > step_limit:
            delta = step_limit if delta > 0 else -step_limit
        # 比例限幅（current_q=0 时只用速率限幅）
        if current_q > 0:
            max_delta = current_q * max_ratio
            if abs(delta) > max_delta:
                delta = max_delta if delta > 0 else -max_delta

        actual_q = current_q + delta

        # 使用独立 session 记录联动历史
        cop = config.target_cop if config and config.target_cop else 3.5
        async with async_session() as history_session:
            from app.services.load_shift.cooling_linkage_service import (
                CoolingLinkageService,
            )

            await CoolingLinkageService.create_history_record(
                db=history_session,
                event_type="precool",
                before_power=current_q,
                after_power=actual_q,
                cop_before=cop,
                cop_after=cop,
                supply_temp_before=0,
                supply_temp_after=0,
                return_temp_before=0,
                return_temp_after=0,
                reason=f"precool_step zone={zone_id}",
            )

        return actual_q

    async def _get_current_cooling_power(self, zone_id: int, session: AsyncSession) -> float:
        """获取当前制冷电功率

        从 CoolingLinkageRecord 中按 zone_id 过滤，取最新 after_power。
        通过 reason 字段包含 zone=X 来过滤。
        """
        from app.models.load_shift import CoolingLinkageRecord

        result = await session.execute(
            select(CoolingLinkageRecord.after_power)
            .where(CoolingLinkageRecord.reason.like(f"%zone={zone_id}%"))
            .order_by(CoolingLinkageRecord.id.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return float(row) if row is not None else 100.0

    async def _restore_baseline_power(self, zone_id: int, session: AsyncSession):
        """恢复制冷功率到维持温度的基线电功率

        基线电功率 = (Q_IT + (T_amb - T_current) / R) / COP
        安全恢复：不受 step_limit 限制，直接设定目标功率
        """
        from app.core.database import async_session as async_session_factory
        from app.models.topology_config import CoolingZone

        zone = await session.get(CoolingZone, zone_id)
        if not zone or not zone.thermal_R:
            logger.warning("Zone %d 无热参数，跳过功率恢复", zone_id)
            return

        T_current = await self._get_actual_temperature(zone_id, session)
        Q_IT = await self._get_it_load(zone_id, session)
        T_amb = await self._get_ambient_temp(session)
        config = await self._load_linkage_config(zone_id, session)
        cop = config.target_cop if config and config.target_cop else 3.5

        # 热平衡基线制冷量 / COP = 电功率
        Q_baseline_thermal = Q_IT + (T_amb - T_current) / zone.thermal_R
        Q_baseline_elec = max(0.0, Q_baseline_thermal / cop)

        current_q = await self._get_current_cooling_power(zone_id, session)

        # 安全恢复：直接设定，不受 step_limit 限制
        async with async_session_factory() as history_session:
            from app.services.load_shift.cooling_linkage_service import (
                CoolingLinkageService,
            )

            await CoolingLinkageService.create_history_record(
                db=history_session,
                event_type="recovery",
                before_power=current_q,
                after_power=Q_baseline_elec,
                cop_before=cop,
                cop_after=cop,
                supply_temp_before=0,
                supply_temp_after=0,
                return_temp_before=0,
                return_temp_after=0,
                reason=f"precool_restore zone={zone_id}",
            )

        logger.info(
            "功率恢复 zone=%d: %.1f → %.1f kW",
            zone_id,
            current_q,
            Q_baseline_elec,
        )

    # ==================== 安全检查 ====================

    def _check_safety(self, zone_id: int) -> dict:
        """检查 rollback_manager 安全状态，返回完整 status dict"""
        from app.services.precool.rollback_manager import rollback_manager

        return rollback_manager.get_zone_rollback_status(zone_id)

    # ==================== 中止和完成 ====================

    async def abort_plan_by_api(
        self,
        plan: PrecoolSchedule,
        reason: str,
        session: AsyncSession,
    ):
        """API 层调用的公共中止方法（封装内部状态获取）"""
        step_index = self._get_current_step_index()
        actual_temp = await self._get_actual_temperature(plan.cooling_zone_id, session)
        await self._abort_plan(plan, reason, step_index, actual_temp, session)

    async def _abort_plan(
        self,
        plan: PrecoolSchedule,
        reason: str,
        step_index: int,
        actual_temp: float,
        session: AsyncSession,
    ):
        """中止预冷计划并恢复功率"""
        plan.status = "aborted"
        plan.abort_reason = reason[:500]

        # 写入当步实际温度（如果尚未写入）
        trajectory = plan.temperature_trajectory or {}
        actual_list = trajectory.get("actual", [])
        if len(actual_list) <= step_index or (len(actual_list) > step_index and actual_list[step_index] is None):
            self._record_actual_data(trajectory, step_index, actual_temp, None)
            plan.temperature_trajectory = trajectory

        # 恢复功率
        await self._restore_baseline_power(plan.cooling_zone_id, session)

        logger.warning(
            "⚠️ 预冷计划 %d 中止: %s (zone=%d, step=%d, T=%.1f°C)",
            plan.id,
            reason,
            plan.cooling_zone_id,
            step_index,
            actual_temp,
        )

    async def _complete_plan(self, plan: PrecoolSchedule, session: AsyncSession):
        """正常完成预冷计划"""
        plan.status = "completed"

        # 计算实际节省
        Q_IT = await self._get_it_load(plan.cooling_zone_id, session)
        config = await self._load_linkage_config(plan.cooling_zone_id, session)
        cop = config.target_cop if config and config.target_cop else 3.5

        plan.actual_savings_kwh = self._calculate_actual_savings(plan, Q_IT, cop)

        # 恢复功率
        await self._restore_baseline_power(plan.cooling_zone_id, session)

        logger.info(
            "✅ 预冷计划 %d 完成 zone=%d, 计划节省=%.2f kWh, 实际节省=%.2f kWh",
            plan.id,
            plan.cooling_zone_id,
            plan.planned_savings_kwh or 0,
            plan.actual_savings_kwh or 0,
        )

    # ==================== 节省计算 ====================

    def _calculate_actual_savings(self, plan: PrecoolSchedule, Q_IT: float, COP: float) -> float:
        """计算实际节省电量 (kWh)

        基线电功率 = Q_IT / COP（不预冷时维持温度所需的恒定电功率）
        actual_savings_kwh = Σ(Q_baseline - Q_actual) * dt
        只在有 actual 数据的步骤范围内求和
        """
        trajectory = plan.temperature_trajectory or {}
        q_cool_actual = trajectory.get("q_cool_actual", [])

        DT = 5 / 60  # 小时
        Q_baseline_elec = Q_IT / COP if COP > 0 else Q_IT / 3.5

        actual_energy = 0.0
        baseline_energy = 0.0

        for q_actual in q_cool_actual:
            if q_actual is not None:
                actual_energy += q_actual * DT
                baseline_energy += Q_baseline_elec * DT

        return round(max(0.0, baseline_energy - actual_energy), 2)

    # ==================== 数据记录 ====================

    def _record_actual_data(
        self,
        trajectory: dict,
        step_index: int,
        actual_temp: float,
        actual_q_cool: Optional[float],
    ):
        """写入实际温度和功率到 trajectory（按绝对步索引对齐）"""
        actual_temps = trajectory.setdefault("actual", [])
        actual_powers = trajectory.setdefault("q_cool_actual", [])
        while len(actual_temps) <= step_index:
            actual_temps.append(None)
        while len(actual_powers) <= step_index:
            actual_powers.append(None)
        actual_temps[step_index] = actual_temp
        actual_powers[step_index] = actual_q_cool

    # ==================== 数据加载辅助方法 ====================

    async def _load_linkage_config(self, zone_id: int, session: AsyncSession):
        """加载联动配置"""
        from app.models.load_shift import CoolingLinkageConfig

        result = await session.execute(
            select(CoolingLinkageConfig).where(CoolingLinkageConfig.cooling_zone_id == zone_id)
        )
        return result.scalar_one_or_none()

    async def _get_actual_temperature(self, zone_id: int, session: AsyncSession) -> float:
        """获取 zone 当前实际温度

        从 PointHistory 或 PointRealtime 查询进风温度传感器最新值。
        简化实现：返回默认值（后续可对接真实传感器数据）。
        """
        # 复用 thermal_model 的温度查询逻辑
        try:
            from app.services.precool.thermal_model import ThermalModel

            model = ThermalModel()
            temp = await model._get_current_temperature(zone_id, session)
            if temp is not None:
                return temp
        except Exception:
            pass
        return 22.0  # 兜底默认值

    async def _get_it_load(self, zone_id: int, session: AsyncSession) -> float:
        """获取 IT 负荷 kW"""
        try:
            from app.services.precool.thermal_model import ThermalModel

            model = ThermalModel()
            load = await model._get_it_load(zone_id, session)
            if load is not None:
                return load
        except Exception:
            pass
        return 100.0

    async def _get_ambient_temp(self, session: AsyncSession) -> float:
        """获取环境温度"""
        try:
            from app.services.precool.thermal_model import ThermalModel

            model = ThermalModel()
            temp = await model._get_ambient_temperature(session)
            if temp is not None:
                return temp
        except Exception:
            pass
        return 25.0


# 单例
precool_executor = PrecoolExecutor()
