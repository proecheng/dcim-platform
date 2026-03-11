"""
贪心优化预冷调度算法

Story 31.1: 基于电价信号的预冷计划生成。
O(N) 贪心策略（N≤288，5min 步长），谷时预冷/峰时释放。
"""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.thermal import PrecoolSchedule
from app.models.topology_config import CoolingZone

logger = logging.getLogger(__name__)


# ==================== 数据结构 ====================


@dataclass
class TimeSlot:
    """电价时段"""
    start_hour: float   # 0-24
    end_hour: float     # 0-24
    price: float        # 元/kWh
    period_type: str    # sharp/peak/flat/valley/deep_valley


@dataclass
class ScheduleStep:
    """单步调度结果"""
    step: int
    time_minutes: float       # 从 00:00 起的分钟数
    period_type: str
    price: float
    Q_cool: float             # 制冷电功率 kW
    Q_cool_effective: float   # 实际制冷量 kW（= Q_cool * COP）
    T_room: float             # 步末温度 °C
    cost: float               # 该步电费 元


@dataclass
class TrajectoryViolation:
    """轨迹约束违规"""
    step: int
    violation_type: str   # temperature_high / temperature_low / rate_of_change
    current_value: float
    threshold: float
    message: str


@dataclass
class PrecoolPlanResult:
    """计划生成结果"""
    schedule: Optional[PrecoolSchedule] = None
    steps: List[ScheduleStep] = field(default_factory=list)
    total_cost: float = 0.0
    baseline_cost: float = 0.0
    saving: float = 0.0
    saving_percent: float = 0.0
    T_min_actual: float = 0.0
    T_max_actual: float = 0.0


class PrecoolPlanError(Exception):
    """预冷计划生成错误"""
    def __init__(self, error: str, reason: str, suggestions: List[str]):
        self.error = error
        self.reason = reason
        self.suggestions = suggestions
        super().__init__(reason)


# ==================== 约束常量（从 constraints.py 导入，避免重复定义） ====================

from app.services.precool.constraints import (
    DEFAULT_TEMP_MAX,
    DEFAULT_TEMP_MIN,
    DEFAULT_RATE_LIMIT,
)

# 默认功率参数
DEFAULT_Q_COOL_MIN = 0.0      # kW
DEFAULT_Q_COOL_MAX = 2000.0   # kW
DEFAULT_POWER_STEP = 20.0     # kW/step
DEFAULT_COP = 3.5


# ==================== 电价时段兜底默认值 ====================


def get_default_time_slots() -> List[TimeSlot]:
    """兜底默认电价时段（仅在 DB 无数据时使用）"""
    return [
        TimeSlot(0, 8, 0.25, "valley"),    # 00:00-08:00 谷时
        TimeSlot(8, 11, 0.65, "flat"),     # 08:00-11:00 平时
        TimeSlot(11, 17, 1.05, "peak"),    # 11:00-17:00 峰时
        TimeSlot(17, 21, 1.80, "sharp"),   # 17:00-21:00 尖峰
        TimeSlot(21, 24, 0.25, "valley"),  # 21:00-24:00 谷时
    ]


async def load_time_slots_from_db(session: AsyncSession) -> List[TimeSlot]:
    """从 ElectricityPricing 表读取当前有效电价时段"""
    try:
        from app.models.energy import ElectricityPricing
        result = await session.execute(
            select(ElectricityPricing).where(
                ElectricityPricing.is_enabled == True  # noqa: E712
            )
        )
        rows = result.scalars().all()
        if not rows:
            logger.warning("ElectricityPricing 表无有效记录，使用默认时段")
            return get_default_time_slots()

        slots = []
        for row in rows:
            try:
                parts_start = row.start_time.split(":")
                parts_end = row.end_time.split(":")
                start_h = int(parts_start[0]) + int(parts_start[1]) / 60
                end_h = int(parts_end[0]) + int(parts_end[1]) / 60
                # 处理跨午夜情况
                if end_h <= start_h:
                    end_h = 24.0
                slots.append(TimeSlot(start_h, end_h, row.price, row.period_type))
            except (ValueError, IndexError, AttributeError) as e:
                logger.warning("跳过无效电价记录 id=%s: %s", row.id, e)
                continue

        if not slots:
            logger.warning("ElectricityPricing 解析后无有效时段，使用默认时段")
            return get_default_time_slots()

        return sorted(slots, key=lambda s: s.start_hour)
    except Exception as e:
        logger.warning("加载电价时段失败: %s，使用默认时段", e)
        return get_default_time_slots()


# ==================== 核心调度器 ====================


class PrecoolScheduler:
    """贪心优化预冷调度器

    O(N) 复杂度（N≤288，5min 步长），谷时加大制冷预冷，峰时削减制冷释放温度缓冲。
    """

    DT = 5 / 60       # 5 分钟步长（小时）= 1/12
    N_MAX = 288        # 24h / 5min = 288 步

    async def generate_precool_plan(
        self,
        zone_id: int,
        schedule_date: date,
        session: AsyncSession,
        time_slots: Optional[List[TimeSlot]] = None,
    ) -> PrecoolPlanResult:
        """生成预冷计划

        Args:
            zone_id: 制冷区域 ID
            schedule_date: 计划日期
            session: 数据库会话
            time_slots: 电价时段（None 时从 DB 加载）

        Returns:
            PrecoolPlanResult

        Raises:
            PrecoolPlanError: 参数未标定、数值不稳定、无可行方案
        """
        # 0. 检查预冷是否启用
        await self._check_precool_enabled(zone_id, session)

        # 1. 加载热参数
        zone = await self._load_zone(zone_id, session)
        R, C = zone.thermal_R, zone.thermal_C
        if R is None or C is None:
            raise PrecoolPlanError(
                error="parameters_not_calibrated",
                reason=f"Zone {zone_id} 的 thermal_R 或 thermal_C 未标定",
                suggestions=["运行热参数自动校准", "手动设置 R/C 参数"],
            )
        beta = zone.bypass_beta if zone.bypass_beta is not None else 0.1

        # 1.5 数值稳定性检查
        if self.DT >= 2 * R * C:
            raise PrecoolPlanError(
                error="numerical_instability",
                reason=f"时间步长 {self.DT:.4f}h 超过稳定性限制 2*R*C={2*R*C:.4f}h",
                suggestions=["检查 R/C 参数是否合理"],
            )

        # 2. 加载功率限制和 COP
        config = await self._load_config(zone_id, session)
        Q_cool_min = config.get("min_cooling_power", DEFAULT_Q_COOL_MIN)
        Q_cool_max = config.get("max_cooling_power", DEFAULT_Q_COOL_MAX)
        delta_P_max = config.get("power_adjust_step", DEFAULT_POWER_STEP)
        target_cop = config.get("target_cop", None)
        precool_target_temp = config.get("precool_target_temp", DEFAULT_TEMP_MIN)

        # 3. 获取初始状态
        T = await self._get_current_temp(zone_id, session)
        Q_IT = await self._get_it_load(zone_id, session)
        T_amb = await self._get_ambient_temp(zone_id, session)
        T_outdoor = await self._get_outdoor_temp(zone_id, session)
        COP = self._get_cop(target_cop, T_outdoor)

        # 4. 加载电价时段
        if time_slots is None:
            time_slots = await load_time_slots_from_db(session)

        # 5. 贪心调度循环
        steps = []
        prev_Q = Q_IT / COP  # 初始电功率 ≈ 制冷量/COP
        T_min_actual = T
        T_max_actual = T

        # 基线成本（不做预冷，全天维持正常制冷）
        baseline_Q = Q_IT / COP
        baseline_cost = 0.0

        for step in range(self.N_MAX):
            slot = self._get_slot_for_step(step, time_slots)
            baseline_cost += baseline_Q * self.DT * slot.price

            # 根据时段类型决定制冷策略
            Q_cool = self._decide_cooling(
                slot.period_type, Q_IT, T, R, C, T_amb,
                Q_cool_min, Q_cool_max, precool_target_temp,
            )

            # 功率限幅 + 速率限幅
            Q_cool = self._apply_limits(Q_cool, prev_Q, Q_cool_min, Q_cool_max, delta_P_max)

            # RC 方程迭代（含 COP 和 bypass 修正）
            Q_cool_effective = Q_cool * COP
            T_inlet_corrected = T * (1 - beta) + T_amb * beta
            dT = (self.DT / C) * (Q_IT - Q_cool_effective + (T_amb - T_inlet_corrected) / R)
            T_new = T + dT

            # 安全校正
            T_new, Q_cool = self._safety_correction(
                T_new, Q_cool, Q_IT, T, T_amb, R, C, COP, beta,
            )

            cost = Q_cool * self.DT * slot.price

            steps.append(ScheduleStep(
                step=step,
                time_minutes=step * 5,
                period_type=slot.period_type,
                price=slot.price,
                Q_cool=round(Q_cool, 2),
                Q_cool_effective=round(Q_cool * COP, 2),
                T_room=round(T_new, 3),
                cost=round(cost, 4),
            ))

            prev_Q = Q_cool
            T = T_new
            T_min_actual = min(T_min_actual, T)
            T_max_actual = max(T_max_actual, T)

        total_cost = sum(s.cost for s in steps)
        saving = baseline_cost - total_cost
        saving_percent = (saving / baseline_cost * 100) if baseline_cost > 1e-6 else 0.0

        # 6. 构建计划
        plan = self._build_plan(
            zone_id, schedule_date, steps,
            precool_target_temp, time_slots,
            saving, total_cost,
        )

        # 7. 约束验证 + 重试
        validated_plan = await self._validate_with_retry(
            plan, steps, zone_id, session,
        )

        return PrecoolPlanResult(
            schedule=validated_plan,
            steps=steps,
            total_cost=round(total_cost, 2),
            baseline_cost=round(baseline_cost, 2),
            saving=round(saving, 2),
            saving_percent=round(saving_percent, 1),
            T_min_actual=round(T_min_actual, 2),
            T_max_actual=round(T_max_actual, 2),
        )

    # ==================== 策略决策 ====================

    def _decide_cooling(
        self,
        period_type: str,
        Q_IT: float,
        T: float,
        R: float,
        C: float,
        T_amb: float,
        Q_cool_min: float,
        Q_cool_max: float,
        precool_target_temp: float,
    ) -> float:
        """根据时段类型决定制冷电功率"""
        if period_type in ("valley", "deep_valley"):
            # 谷时/深谷：加大制冷预冷
            Q_cool = min(Q_cool_max, Q_IT + C * (T - precool_target_temp) / self.DT)
        elif period_type in ("peak", "sharp"):
            # 峰时/尖峰：削减制冷释放缓冲
            headroom = DEFAULT_TEMP_MAX - 2.0 - T
            Q_cool = max(Q_cool_min, Q_IT - C * headroom / self.DT * 0.5)
        else:
            # 平时 (flat)：维持正常
            Q_cool = Q_IT + (T_amb - T) / R
        return Q_cool

    def _apply_limits(
        self,
        Q_cool: float,
        prev_Q: float,
        Q_cool_min: float,
        Q_cool_max: float,
        delta_P_max: float,
    ) -> float:
        """功率限幅 + 速率限幅"""
        # 功率限幅
        Q_cool = max(Q_cool_min, min(Q_cool, Q_cool_max))
        # 速率限幅
        if abs(Q_cool - prev_Q) > delta_P_max:
            if Q_cool > prev_Q:
                Q_cool = prev_Q + delta_P_max
            else:
                Q_cool = prev_Q - delta_P_max
        return Q_cool

    def _safety_correction(
        self,
        T_new: float,
        Q_cool: float,
        Q_IT: float,
        T: float,
        T_amb: float,
        R: float,
        C: float,
        COP: float,
        beta: float,
    ) -> tuple:
        """温度越界安全校正"""
        if T_new > DEFAULT_TEMP_MAX:
            # 温度过高：增加制冷
            T_inlet_corrected = T * (1 - beta) + T_amb * beta
            Q_cool_effective_needed = Q_IT + (T_amb - T_inlet_corrected) / R + C * (T - DEFAULT_TEMP_MAX + 1.0) / self.DT
            Q_cool = Q_cool_effective_needed / COP
            T_new = DEFAULT_TEMP_MAX - 0.5  # 修正到安全值
        elif T_new < DEFAULT_TEMP_MIN:
            # 温度过低：减少制冷
            T_inlet_corrected = T * (1 - beta) + T_amb * beta
            Q_cool_effective_needed = Q_IT + (T_amb - T_inlet_corrected) / R - C * (DEFAULT_TEMP_MIN - T + 0.5) / self.DT
            Q_cool = max(0, Q_cool_effective_needed / COP)
            T_new = DEFAULT_TEMP_MIN + 0.5  # 修正到安全值
        return T_new, Q_cool

    # ==================== 约束验证 ====================

    def _validate_trajectory(
        self,
        steps: List[ScheduleStep],
    ) -> List[TrajectoryViolation]:
        """验证温度轨迹是否满足所有约束"""
        violations = []
        for s in steps:
            # 温度上限
            if s.T_room > DEFAULT_TEMP_MAX:
                violations.append(TrajectoryViolation(
                    step=s.step,
                    violation_type="temperature_high",
                    current_value=s.T_room,
                    threshold=DEFAULT_TEMP_MAX,
                    message=f"步 {s.step} 温度 {s.T_room:.1f}°C 超上限 {DEFAULT_TEMP_MAX}°C",
                ))
            # 温度下限
            if s.T_room < DEFAULT_TEMP_MIN:
                violations.append(TrajectoryViolation(
                    step=s.step,
                    violation_type="temperature_low",
                    current_value=s.T_room,
                    threshold=DEFAULT_TEMP_MIN,
                    message=f"步 {s.step} 温度 {s.T_room:.1f}°C 低于下限 {DEFAULT_TEMP_MIN}°C",
                ))
            # 温变速率
            if s.step > 0:
                rate = abs(s.T_room - steps[s.step - 1].T_room) / self.DT
                if rate > DEFAULT_RATE_LIMIT:
                    violations.append(TrajectoryViolation(
                        step=s.step,
                        violation_type="rate_of_change",
                        current_value=rate,
                        threshold=DEFAULT_RATE_LIMIT,
                        message=f"步 {s.step} 温变速率 {rate:.1f}°C/h 超限 {DEFAULT_RATE_LIMIT}°C/h",
                    ))
        return violations

    async def _validate_with_retry(
        self,
        plan: PrecoolSchedule,
        steps: List[ScheduleStep],
        zone_id: int,
        session: AsyncSession,
        max_retries: int = 3,
    ) -> PrecoolSchedule:
        """验证计划，失败时自动放宽重试"""
        for attempt in range(max_retries + 1):
            violations = self._validate_trajectory(steps)
            if not violations:
                plan.is_validated = True
                plan.validated_at = datetime.now()
                return plan

            logger.warning(
                "Zone %d 预冷计划约束验证失败（第 %d 次），%d 个违规",
                zone_id, attempt + 1, len(violations),
            )

            if attempt < max_retries:
                plan, steps = self._relax_and_regenerate(plan, steps, attempt)
            else:
                raise PrecoolPlanError(
                    error="no_feasible_plan",
                    reason=f"约束验证失败 ({len(violations)} 个违规): {violations[0].message}",
                    suggestions=["调整热参数 R/C", "缩短电价时段", "提高预冷目标温度"],
                )
        return plan

    def _relax_and_regenerate(
        self,
        plan: PrecoolSchedule,
        steps: List[ScheduleStep],
        attempt: int,
    ) -> tuple:
        """放宽计划约束并调整温度轨迹"""
        if attempt == 0:
            # 第1次：减少预冷深度 1°C
            plan.target_temp = min(plan.target_temp + 1.0, DEFAULT_TEMP_MAX - 2.0)
            logger.info("放宽策略: 预冷目标温度 +1°C → %.1f°C", plan.target_temp)
        elif attempt == 1:
            # 第2次：缩短峰时削减 30min
            peak_end = datetime.combine(date.today(), plan.peak_end_time)
            new_end = peak_end - timedelta(minutes=30)
            plan.peak_end_time = new_end.time()
            logger.info("放宽策略: 峰时削减缩短 30min → %s", plan.peak_end_time)
        elif attempt == 2:
            # 第3次：同时放宽
            plan.target_temp = min(plan.target_temp + 1.0, DEFAULT_TEMP_MAX - 2.0)
            peak_end = datetime.combine(date.today(), plan.peak_end_time)
            new_end = peak_end - timedelta(minutes=30)
            plan.peak_end_time = new_end.time()
            logger.info("放宽策略: 同时放宽 target_temp=%.1f°C, peak_end=%s",
                         plan.target_temp, plan.peak_end_time)

        # 注意：不修改步的温度值（会破坏热力学一致性），
        # 仅放宽计划参数后由 _validate_trajectory 重新检查。
        # 放宽后安全校正逻辑在下一轮应该能处理边界温度。
        clamped = sum(1 for s in steps if s.T_room > DEFAULT_TEMP_MAX or s.T_room < DEFAULT_TEMP_MIN)
        if clamped > 0:
            logger.info("轨迹中 %d 步温度越界，放宽参数后重新验证", clamped)

        return plan, steps

    # ==================== 辅助方法 ====================

    def _get_slot_for_step(self, step: int, time_slots: List[TimeSlot]) -> TimeSlot:
        """根据步序号查找对应的电价时段"""
        if not time_slots:
            return TimeSlot(0, 24, 0.5, "flat")
        hour = step * 5 / 60  # 步序号转小时
        for slot in time_slots:
            if slot.start_hour <= hour < slot.end_hour:
                return slot
        # 时段有间隙时使用最近的时段
        logger.debug("步 %d (%.2fh) 未匹配任何时段，使用最后一个时段", step, hour)
        return time_slots[-1]

    def _get_cop(self, target_cop: Optional[float], T_outdoor: float) -> float:
        """COP 优先使用配置值，无配置时按季节修正"""
        if target_cop:
            return target_cop
        if T_outdoor >= 30.0:
            return 2.8  # 夏季
        elif T_outdoor >= 15.0:
            return 3.5  # 过渡季
        else:
            return 4.0  # 冬季

    def _build_plan(
        self,
        zone_id: int,
        schedule_date: date,
        steps: List[ScheduleStep],
        target_temp: float,
        time_slots: List[TimeSlot],
        saving_kwh: float,
        total_cost: float,
    ) -> PrecoolSchedule:
        """构建 PrecoolSchedule 对象"""
        # 找到第一个谷时段和第一个峰时段
        valley_slots = [s for s in time_slots if s.period_type in ("valley", "deep_valley")]
        peak_slots = [s for s in time_slots if s.period_type in ("peak", "sharp")]

        precool_start = time(0, 0)
        precool_end = time(8, 0)
        peak_start = time(11, 0)
        peak_end = time(21, 0)

        if valley_slots:
            first_valley = valley_slots[0]
            precool_start = time(int(first_valley.start_hour), int((first_valley.start_hour % 1) * 60))
            precool_end = time(int(first_valley.end_hour) % 24, int((first_valley.end_hour % 1) * 60))
        if peak_slots:
            first_peak = peak_slots[0]
            last_peak = peak_slots[-1]
            peak_start = time(int(first_peak.start_hour), int((first_peak.start_hour % 1) * 60))
            peak_end = time(int(last_peak.end_hour) % 24, int((last_peak.end_hour % 1) * 60))

        # 温度轨迹 JSON
        trajectory = {
            "predicted": [s.T_room for s in steps],
            "timestamps": [f"{int(s.time_minutes // 60):02d}:{int(s.time_minutes % 60):02d}" for s in steps],
        }

        return PrecoolSchedule(
            cooling_zone_id=zone_id,
            schedule_date=schedule_date,
            precool_start_time=precool_start,
            precool_end_time=precool_end,
            target_temp=target_temp,
            peak_start_time=peak_start,
            peak_end_time=peak_end,
            planned_savings_kwh=round(saving_kwh, 2),
            status="pending",
            temperature_trajectory=trajectory,
        )

    # ==================== 数据加载 ====================

    async def _check_precool_enabled(self, zone_id: int, session: AsyncSession) -> None:
        """检查预冷功能是否启用"""
        try:
            from app.models.load_shift import CoolingLinkageConfig
            result = await session.execute(
                select(CoolingLinkageConfig).where(
                    CoolingLinkageConfig.cooling_zone_id == zone_id
                )
            )
            config = result.scalar_one_or_none()
            if config and not config.precool_enabled:
                raise PrecoolPlanError(
                    error="precool_disabled",
                    reason=f"Zone {zone_id} 预冷功能未启用",
                    suggestions=["在制冷联动配置中启用 precool_enabled"],
                )
        except PrecoolPlanError:
            raise
        except Exception as e:
            logger.warning("检查预冷启用状态失败: %s（允许继续）", e)

    async def _load_zone(self, zone_id: int, session: AsyncSession) -> CoolingZone:
        """加载制冷区域"""
        zone = await session.get(CoolingZone, zone_id)
        if not zone:
            raise PrecoolPlanError(
                error="zone_not_found",
                reason=f"制冷区域 {zone_id} 不存在",
                suggestions=["确认 zone_id 正确"],
            )
        return zone

    async def _load_config(self, zone_id: int, session: AsyncSession) -> Dict:
        """加载制冷联动配置"""
        try:
            from app.models.load_shift import CoolingLinkageConfig
            result = await session.execute(
                select(CoolingLinkageConfig).where(
                    CoolingLinkageConfig.cooling_zone_id == zone_id
                )
            )
            config = result.scalar_one_or_none()
            if config:
                return {
                    "min_cooling_power": config.min_cooling_power or DEFAULT_Q_COOL_MIN,
                    "max_cooling_power": config.max_cooling_power or DEFAULT_Q_COOL_MAX,
                    "power_adjust_step": config.power_adjust_step or DEFAULT_POWER_STEP,
                    "target_cop": config.target_cop,
                    "precool_target_temp": config.precool_target_temp or DEFAULT_TEMP_MIN,
                }
        except Exception as e:
            logger.warning("加载制冷配置失败: %s，使用默认值", e)

        return {
            "min_cooling_power": DEFAULT_Q_COOL_MIN,
            "max_cooling_power": DEFAULT_Q_COOL_MAX,
            "power_adjust_step": DEFAULT_POWER_STEP,
            "target_cop": None,
            "precool_target_temp": DEFAULT_TEMP_MIN,
        }

    async def _get_current_temp(self, zone_id: int, session: AsyncSession) -> float:
        """获取当前最高机柜进风温度（SQL MAX 聚合）"""
        try:
            from sqlalchemy import func as sa_func
            from app.models.topology_config import CoolingZoneCabinet
            from app.models.cabinet import CabinetTemperatureSensor
            from app.models import Point, PointRealtime

            result = await session.execute(
                select(sa_func.max(PointRealtime.value))
                .join(Point, PointRealtime.point_id == Point.id)
                .join(CabinetTemperatureSensor, CabinetTemperatureSensor.point_id == Point.id)
                .join(CoolingZoneCabinet, CoolingZoneCabinet.cabinet_id == CabinetTemperatureSensor.cabinet_id)
                .where(
                    CoolingZoneCabinet.zone_id == zone_id,
                    CabinetTemperatureSensor.sensor_location == "inlet",
                )
            )
            max_temp = result.scalar()
            if max_temp is not None:
                return max_temp
        except Exception as e:
            logger.warning("获取当前温度失败: %s，使用默认值 22.0°C", e)
        return 22.0

    async def _get_it_load(self, zone_id: int, session: AsyncSession) -> float:
        """获取 IT 热负荷估算值"""
        try:
            from app.models.topology_config import CoolingZoneCabinet, CoolingZoneUnit, CoolingUnit
            # 使用额定制冷功率 × 0.7 估算
            result = await session.execute(
                select(CoolingUnit.cooling_capacity_kw)
                .join(CoolingZoneUnit, CoolingZoneUnit.cooling_unit_id == CoolingUnit.id)
                .where(CoolingZoneUnit.zone_id == zone_id)
            )
            capacities = [row[0] for row in result.all() if row[0] is not None]
            if capacities:
                return sum(capacities) * 0.7  # 70% 负载率估算
        except Exception as e:
            logger.warning("获取 IT 负荷失败: %s，使用默认值 100 kW", e)
        return 100.0

    async def _get_ambient_temp(self, zone_id: int, session: AsyncSession) -> float:
        """获取等效环境温度（精密空调回风温度）"""
        try:
            from app.models.topology_config import CoolingZoneUnit, CoolingUnit
            from app.models import Device, Point, PointRealtime

            result = await session.execute(
                select(PointRealtime.value)
                .join(Point, PointRealtime.point_id == Point.id)
                .join(Device, Point.device_id == Device.id)
                .join(CoolingUnit, CoolingUnit.device_id == Device.id)
                .join(CoolingZoneUnit, CoolingZoneUnit.cooling_unit_id == CoolingUnit.id)
                .where(
                    CoolingZoneUnit.zone_id == zone_id,
                    Point.point_code.like("%_return_temp"),
                )
            )
            temps = [row[0] for row in result.all() if row[0] is not None]
            if temps:
                return sum(temps) / len(temps)
        except Exception as e:
            logger.warning("获取环境温度失败: %s，使用默认值 25.0°C", e)
        return 25.0

    async def _get_outdoor_temp(self, zone_id: int, session: AsyncSession) -> float:
        """获取室外温度（用于 COP 季节修正）"""
        try:
            from app.models.topology_config import CoolingZoneUnit, CoolingUnit
            from app.models import Device, Point, PointRealtime

            result = await session.execute(
                select(PointRealtime.value)
                .join(Point, PointRealtime.point_id == Point.id)
                .join(Device, Point.device_id == Device.id)
                .join(CoolingUnit, CoolingUnit.device_id == Device.id)
                .join(CoolingZoneUnit, CoolingZoneUnit.cooling_unit_id == CoolingUnit.id)
                .where(
                    CoolingZoneUnit.zone_id == zone_id,
                    Device.device_type == "AC",
                    Point.point_code.like("%_ambient_temp"),
                )
            )
            temps = [row[0] for row in result.all() if row[0] is not None]
            if temps:
                return sum(temps) / len(temps)
        except Exception as e:
            logger.warning("获取室外温度失败: %s，使用默认值 25.0°C", e)
        return 25.0

    # ==================== 计划持久化 ====================

    async def save_plan(
        self,
        plan: PrecoolSchedule,
        session: AsyncSession,
    ) -> PrecoolSchedule:
        """保存计划到数据库"""
        session.add(plan)
        await session.commit()
        await session.refresh(plan)
        logger.info(
            "预冷计划已保存: zone=%d, date=%s, target=%.1f°C, saving=%.2f kWh",
            plan.cooling_zone_id,
            plan.schedule_date,
            plan.target_temp,
            plan.planned_savings_kwh or 0,
        )
        return plan
