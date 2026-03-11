# Story 31.1: 贪心优化预冷调度算法

Status: done

## Story

As a 运维人员,
I want 系统根据电价信号自动生成最优预冷计划,
So that 在保证温度安全的前提下最大化电费节省。

## 依赖

- Story 29.1（数据模型，CoolingZone 热参数字段）— done
- Story 29.2（RC 模型核心算法）— done
- Story 29.3（THM 模式，未校准区域兜底）— done
- Story 30.1（约束检查 constraints.py）— done

## Acceptance Criteria

1. Given 电价信号（峰/谷/平/尖峰时段）和制冷区域热参数
   When 触发预冷计划生成
   Then 系统创建 `precool_schedules` 表（Alembic 迁移），包含字段：
   - `id` (PK), `cooling_zone_id` (FK→cooling_zones), `schedule_date` (Date)
   - `precool_start_time` (Time), `precool_end_time` (Time), `target_temp` (Float, °C)
   - `peak_start_time` (Time), `peak_end_time` (Time)
   - `planned_savings_kwh` (Float), `actual_savings_kwh` (Float, nullable)
   - `status` (String: pending|executing|completed|aborted), `abort_reason` (String, nullable)
   - `temperature_trajectory` (JSON: 预测温度轨迹), `created_at`, `updated_at`

2. Given 贪心优化算法实现
   When 调用 `generate_precool_plan(zone_id, schedule_date, time_slots)`
   Then 算法使用 O(N) 贪心策略（N≤288，5min 步长 dt=1/12h）：
   - 谷时（valley/deep_valley）：加大制冷 `Q_cool = min(Q_cool_max, Q_IT + C*(T - T_min)/dt)`
   - 峰时/尖峰（peak/sharp）：削减制冷 `Q_cool = max(Q_cool_min, Q_IT - C*(T_max-2-T)/dt*0.5)`
   - 平时（flat）：维持正常 `Q_cool = Q_IT + (T_amb - T)/R`
   - RC 方程迭代（含 COP 和 bypass 修正）：`Q_eff = Q_cool*COP; T_corr = T*(1-β)+T_out*β; T_new = T + (dt/C)*[Q_IT - Q_eff + (T_amb - T_corr)/R]`
   - 功率限幅 `clamp(Q_cool, Q_cool_min, Q_cool_max)` + 速率限幅 `|ΔQ| ≤ ΔP_max`

3. Given 算法生成计划
   When 约束验证
   Then 预冷目标温度不低于 ASHRAE 下限 18°C
   And 遵循所有约束：温度上下限(18-27°C)、冷通道级约束(T_inlet ≤ T_max-2°C)、功率上下限、功率调整速率、温变速率 ≤ 5°C/h

4. Given 约束验证失败
   When 可行性验证（3 次重试）
   Then 第1次：减少预冷深度 1°C（target_temp += 1.0）
   And 第2次：缩短峰时削减时长 30min
   And 第3次：同时放宽两者
   And 3次重试仍失败时返回 `{error: "no_feasible_plan", reason: "...", suggestions: [...]}`
   And 验证通过的计划标记 `is_validated=True` 并记录验证时间戳

5. Given 计划生成成功
   When 返回结果
   Then 包含：precool 时段、peak 削减时段、目标温度、预期节省 kWh/金额、288 步温度轨迹
   And 计划存入 precool_schedules 表，status='pending'
   And 计划生成耗时 < 5s

6. Given 调度算法实现
   When 运行后端测试
   Then 所有单元测试通过（≥20 个测试用例）

## Tasks / Subtasks

- [x] Task 1: 创建 PrecoolSchedule 数据模型和 Alembic 迁移 (AC: #1)
  - [x]1.1 在 `backend/app/models/thermal.py` 追加 `PrecoolSchedule` ORM 模型，含所有字段
  - [x]1.2 创建 Alembic 迁移脚本 `20260311_0200_story_31_1_precool_schedules.py`
  - [x]1.3 在 `backend/app/models/__init__.py` 确认导出 PrecoolSchedule

- [x] Task 2: 创建电价时段数据结构和加载逻辑 (AC: #2)
  - [x]2.1 在 `scheduler.py` 定义 `TimeSlot` dataclass（start_hour, end_hour, price, period_type）
  - [x]2.2 定义 `PeriodType` 枚举（valley/deep_valley/flat/peak/sharp）— 与 ElectricityPricing.period_type 对齐
  - [x]2.3 实现 `load_time_slots_from_db(session)` 从 `ElectricityPricing` 表读取当前有效电价时段（通过 PricingService 或直接查询）
  - [x]2.4 提供 `get_default_time_slots()` 作为 DB 无数据时的兜底配置

- [x] Task 3: 实现贪心优化预冷调度核心算法 (AC: #2, #3)
  - [x]3.1 创建 `backend/app/services/precool/scheduler.py`
  - [x]3.2 实现 `PrecoolScheduler` 类，核心方法 `async generate_precool_plan(zone_id, schedule_date, time_slots, session)`
  - [x]3.3 实现贪心调度循环：遍历 288 步，按时段类型决定 Q_cool
  - [x]3.4 实现 RC 方程温度迭代 `T_new = T + (dt/C) * [Q_IT - Q_cool + (T_amb-T)/R]`
  - [x]3.5 实现功率限幅 + 速率限幅 + 温度越界安全校正
  - [x]3.6 实现节省电费计算：`saving = baseline_cost - actual_cost`

- [x] Task 4: 实现约束验证和可行性重试 (AC: #3, #4)
  - [x]4.1 实现 `_validate_trajectory()` 轨迹验证方法 — 逐步检查 288 步温度是否在 ASHRAE 范围、功率是否在限幅内、温变速率是否 ≤ 5°C/h（注意：`constraints.py` 的 `check_all_constraints()` 检查实时温度，不适用于预测轨迹验证，需自行实现轨迹级验证逻辑，复用 constraints.py 的阈值常量）
  - [x]4.2 实现温度轨迹全路径约束验证（非单点验证）
  - [x]4.3 实现 3 次重试逻辑：放宽预冷深度 → 缩短峰时削减 → 同时放宽
  - [x]4.4 验证失败返回 `no_feasible_plan` 错误结构

- [x] Task 5: 计划持久化和结果封装 (AC: #5)
  - [x]5.1 将验证通过的计划写入 precool_schedules 表
  - [x]5.2 生成 temperature_trajectory JSON（288 步预测温度 + 时间戳）
  - [x]5.3 返回 `PrecoolPlanResult` 结构（schedule, total_cost, baseline_cost, saving, saving_percent, T_min/T_max_actual）

- [x] Task 6: 单元测试 (AC: #6)
  - [x]6.1 创建 `backend/tests/services/test_precool_scheduler.py`
  - [x]6.2 测试正常场景：谷时预冷 → 峰时释放 → 温度在安全范围
  - [x]6.3 测试约束验证通过/失败场景
  - [x]6.4 测试 3 次重试逻辑：逐步放宽直到可行
  - [x]6.5 测试边界条件：全谷时、全峰时、极端温度、R/C 未标定时使用 THM 兜底
  - [x]6.6 测试 PrecoolSchedule 模型 CRUD 操作
  - [x]6.7 测试电费节省计算正确性
  - [x]6.8 测试算法性能（< 5s）

## Dev Notes

### 架构约束

- **新建文件**: `backend/app/services/precool/scheduler.py` — 贪心调度算法服务
- **新建文件**: `backend/tests/services/test_precool_scheduler.py` — 单元测试
- **新建文件**: `backend/alembic/versions/20260311_0200_story_31_1_precool_schedules.py` — 迁移脚本
- **修改文件**: `backend/app/models/thermal.py` — 追加 PrecoolSchedule 模型
- **修改文件**: `backend/app/models/__init__.py` — 导出新模型

### 核心算法设计

#### 贪心调度伪代码

```python
class PrecoolScheduler:
    DT = 1/12  # 5 分钟步长 (小时)
    N_MAX = 288  # 24h / 5min

    async def generate_precool_plan(
        self,
        zone_id: int,
        schedule_date: date,
        time_slots: List[TimeSlot],
        session: AsyncSession,
    ) -> PrecoolPlanResult:
        # 1. 加载热参数 (R, C, T_initial, Q_IT, T_amb)
        zone = await session.get(CoolingZone, zone_id)
        R, C = zone.thermal_R, zone.thermal_C
        if R is None or C is None:
            raise PrecoolPlanError(
                error="parameters_not_calibrated",
                reason=f"Zone {zone_id} 的 thermal_R 或 thermal_C 未标定",
                suggestions=["运行热参数自动校准", "手动设置 R/C 参数"]
            )
        beta = zone.bypass_beta if zone.bypass_beta is not None else 0.1

        # 1.5 数值稳定性检查（与 thermal_model.py 一致）
        if self.DT >= 2 * R * C:
            raise PrecoolPlanError(
                error="numerical_instability",
                reason=f"时间步长 {self.DT}h 超过稳定性限制 2*R*C={2*R*C:.4f}h",
                suggestions=["检查 R/C 参数是否合理"]
            )

        # 2. 加载功率限制
        config = await self._load_config(zone_id, session)
        Q_cool_min = config.min_cooling_power or 0
        Q_cool_max = config.max_cooling_power or 2000
        delta_P_max = config.power_adjust_step or 20  # kW/step

        # 3. 获取当前温度和 IT 负荷
        T = await self._get_current_temp(zone_id, session) or 22.0
        Q_IT = await self._get_it_load(zone_id, session) or 100.0
        T_amb = await self._get_ambient_temp(session) or 25.0

        # 4. 贪心循环
        schedule_steps = []
        prev_Q = Q_IT  # 初始制冷 = IT 负荷
        for step in range(self.N_MAX):
            slot = self._get_slot_for_step(step, time_slots)
            Q_cool = self._decide_cooling(slot.period_type, Q_IT, T, R, C, T_amb,
                                           Q_cool_min, Q_cool_max)
            Q_cool = self._apply_limits(Q_cool, prev_Q, Q_cool_min, Q_cool_max, delta_P_max)
            # RC 方程：Q_cool_effective = Q_cool * COP（制冷量 = 电功率 × COP）
            COP = self._get_cop(config, T_amb)
            Q_cool_effective = Q_cool * COP
            # bypass 修正：T_inlet_corrected = T*(1-beta) + T_outlet*beta
            T_inlet_corrected = T * (1 - beta) + T_amb * beta  # T_outlet 近似 T_amb
            T_new = T + (self.DT / C) * (Q_IT - Q_cool_effective + (T_amb - T_inlet_corrected) / R)
            T_new, Q_cool = self._safety_correction(T_new, Q_cool, Q_IT, T, T_amb, R, C)

            schedule_steps.append(ScheduleStep(
                step=step, period_type=slot.period_type, price=slot.price,
                Q_cool=Q_cool, T_room=T_new, cost=Q_cool/COP*self.DT*slot.price
            ))
            prev_Q = Q_cool
            T = T_new

        # 5. 约束验证 + 重试
        plan = self._build_plan(zone_id, schedule_date, schedule_steps)
        validated_plan = await self._validate_with_retry(plan, zone_id, session)
        return validated_plan
```

#### 电价时段加载（优先从数据库读取）

```python
async def load_time_slots_from_db(session: AsyncSession) -> List[TimeSlot]:
    """从 ElectricityPricing 表读取当前有效电价时段"""
    from app.models.energy import ElectricityPricing
    result = await session.execute(
        select(ElectricityPricing).where(
            ElectricityPricing.is_enabled == True
        )
    )
    rows = result.scalars().all()
    if not rows:
        return get_default_time_slots()  # 兜底
    slots = []
    for row in rows:
        start_h = int(row.start_time.split(":")[0]) + int(row.start_time.split(":")[1]) / 60
        end_h = int(row.end_time.split(":")[0]) + int(row.end_time.split(":")[1]) / 60
        slots.append(TimeSlot(start_h, end_h, row.price, row.period_type))
    return sorted(slots, key=lambda s: s.start_hour)
```

#### 电价时段兜底默认配置

```python
DEFAULT_TIME_SLOTS = [
    TimeSlot(0, 8, 0.25, "valley"),      # 00:00-08:00 谷时
    TimeSlot(8, 11, 0.65, "flat"),        # 08:00-11:00 平时
    TimeSlot(11, 17, 1.05, "peak"),       # 11:00-17:00 峰时
    TimeSlot(17, 21, 1.80, "sharp"),      # 17:00-21:00 尖峰
    TimeSlot(21, 24, 0.25, "valley"),     # 21:00-24:00 谷时
]
```

#### COP 获取（优先使用配置值）

```python
def _get_cop(self, config: CoolingLinkageConfig, T_ambient: float) -> float:
    """COP 优先从 CoolingLinkageConfig.target_cop 读取，无配置时按季节修正"""
    if config and config.target_cop:
        return config.target_cop
    # 季节修正兜底
    if T_ambient < 15:
        return 4.0  # 冬季
    elif T_ambient <= 30:
        return 3.5  # 过渡季
    else:
        return 2.8  # 夏季
```

### 数据模型设计

#### PrecoolSchedule 模型

```python
class PrecoolSchedule(Base):
    __tablename__ = "precool_schedules"

    id = Column(Integer, primary_key=True, index=True)
    cooling_zone_id = Column(Integer, ForeignKey("cooling_zones.id"), nullable=False, index=True)
    schedule_date = Column(Date, nullable=False)

    # 预冷时段
    precool_start_time = Column(Time, nullable=False)
    precool_end_time = Column(Time, nullable=False)
    target_temp = Column(Float, nullable=False)  # 预冷目标温度 °C

    # 峰时削减时段
    peak_start_time = Column(Time, nullable=False)
    peak_end_time = Column(Time, nullable=False)

    # 能效指标
    planned_savings_kwh = Column(Float, default=0.0)
    actual_savings_kwh = Column(Float, nullable=True)

    # 执行状态
    status = Column(String(20), default="pending", index=True)
    abort_reason = Column(String(500), nullable=True)

    # 温度轨迹 JSON
    temperature_trajectory = Column(JSON, nullable=True)

    # 验证信息
    is_validated = Column(Boolean, default=False)
    validated_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 联合唯一约束
    __table_args__ = (
        UniqueConstraint("cooling_zone_id", "schedule_date", name="uq_zone_schedule_date"),
    )
```

### 约束验证集成

```python
async def _validate_with_retry(self, plan, zone_id, session, max_retries=3):
    """验证计划是否满足所有约束，失败时自动放宽重试"""
    for attempt in range(max_retries + 1):
        violations = await self._validate_trajectory(plan, zone_id, session)
        if not violations:
            plan.is_validated = True
            plan.validated_at = datetime.utcnow()
            return plan

        if attempt < max_retries:
            plan = self._relax_plan(plan, attempt)
        else:
            raise PrecoolPlanError(
                error="no_feasible_plan",
                reason=f"约束验证失败 ({len(violations)} 个违规): {violations[0].message}",
                suggestions=["调整热参数 R/C", "缩短电价时段", "提高预冷目标温度"]
            )
    return plan

def _relax_plan(self, plan, attempt):
    """逐步放宽计划"""
    if attempt == 0:
        plan.target_temp += 1.0  # 减少预冷深度 1°C
    elif attempt == 1:
        plan.peak_end_time -= timedelta(minutes=30)  # 缩短峰时 30min
    elif attempt == 2:
        plan.target_temp += 1.0
        plan.peak_end_time -= timedelta(minutes=30)
    return plan
```

### 与现有模块的集成点

| 现有模块 | 集成方式 | 说明 |
|---------|--------|------|
| `constraints.py` | 复用阈值常量（DEFAULT_TEMP_MAX/MIN 等） | 轨迹验证复用相同阈值，但需自行实现逐步检查 |
| `thermal_model.py` | 复用 RC 方程参数和数据查询路径 | ThermalModel._load_historical_data() 可参考 |
| `CoolingZone` 模型 | 读取 thermal_R, thermal_C, area_m2 | 热参数已在 Story 29.1 添加 |
| `CoolingLinkageConfig` | 读取 power_adjust_step, max_cooling_power, target_cop, precool_enabled | 功率限制+COP+预冷开关 |
| `ElectricityPricing` 模型 | 读取当前有效电价时段 | 已有 period_type/start_time/end_time/price |
| `SystemConfig` | 读取约束阈值 | ASHRAE 温度限制等 |

### 已有字段确认

**CoolingLinkageConfig** 已有 `precool_enabled` 和 `precool_target_temp` 字段（Story 29.1 添加），scheduler 应检查 `precool_enabled=True` 才生成计划。

**CoolingZone** 已有 `thermal_R`, `thermal_C`, `area_m2`, `height_m`, `bypass_beta`, `r_calibrated_at` 字段（Story 29.1 添加）。

### 测试策略

```python
# 测试用例分组
class TestPrecoolScheduler:
    # 正常流程
    async def test_generate_plan_normal_scenario(self)       # 标准24h, 谷-平-峰-尖峰-谷
    async def test_valley_precooling_lowers_temp(self)        # 谷时温度下降到 target_temp
    async def test_peak_shedding_raises_temp(self)            # 峰时温度上升但不超限
    async def test_savings_calculation_positive(self)          # 节省电费 > 0

    # 约束验证
    async def test_temperature_stays_within_ashrae(self)       # 18 ≤ T ≤ 27
    async def test_power_within_limits(self)                   # Q_cool_min ≤ Q ≤ Q_cool_max
    async def test_rate_of_change_within_limit(self)           # |dT/dt| ≤ 5°C/h
    async def test_inlet_temp_constraint(self)                 # T_inlet ≤ T_max - 2

    # 重试逻辑
    async def test_retry_relaxes_target_temp(self)             # 第1次重试 +1°C
    async def test_retry_shortens_peak_duration(self)          # 第2次重试 -30min
    async def test_retry_both_relaxations(self)                # 第3次两者同时
    async def test_no_feasible_plan_error(self)                # 3次失败报错

    # 边界条件
    async def test_all_valley_slots(self)                      # 全谷时（持续预冷）
    async def test_all_peak_slots(self)                        # 全峰时（无预冷收益）
    async def test_uncalibrated_zone_raises_error(self)        # R/C 为 None 时抛出 parameters_not_calibrated
    async def test_numerical_instability_check(self)           # dt >= 2*R*C 时抛出错误
    async def test_precool_disabled_zone_rejected(self)        # precool_enabled=False 时拒绝

    # 数据模型
    async def test_precool_schedule_crud(self)                 # 创建/查询/更新
    async def test_unique_constraint_zone_date(self)           # 联合唯一约束

    # 性能
    async def test_algorithm_completes_within_5s(self)         # 耗时 < 5s
```

### Project Structure Notes

- `PrecoolSchedule` 模型追加到 `backend/app/models/thermal.py`，与 `ThermalParameter`/`TemperaturePredictionLog` 同文件，保持预冷热模型相关模型集中
- `scheduler.py` 放在 `backend/app/services/precool/` 目录，与 `constraints.py`、`rollback_manager.py`、`thermal_model.py` 平级
- 测试文件放在 `backend/tests/services/`，遵循 `test_precool_*.py` 命名模式
- Alembic 迁移命名遵循 `YYYYMMDD_HHMM_story_XX_X_description.py` 模式

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic31.Story31.1] — AC 定义
- [Source: _bmad-output/planning-artifacts/architecture.md#Section21] — 预冷 TCL 架构 V4.2.0
- [Source: docs/空调可转移功率算法调研与改进方案.md] — V4.0 算法规范
- [Source: backend/app/services/precool/constraints.py] — 约束检查引擎（复用）
- [Source: backend/app/services/precool/thermal_model.py] — RC 模型（参数来源）
- [Source: backend/app/models/thermal.py] — ThermalParameter, TemperaturePredictionLog 模型
- [Source: backend/app/models/topology_config.py#CoolingZone] — 热参数字段
- [Source: backend/app/models/load_shift.py#CoolingLinkageConfig] — precool_enabled/precool_target_temp
- [Source: backend/app/services/precool/rollback_manager.py] — 回退保护（Story 31.2 集成）
- [Source: backend/app/models/energy.py#ElectricityPricing] — 电价时段数据模型（period_type: sharp/peak/flat/valley/deep_valley）
- [Source: backend/app/services/pricing_service.py] — 电价查询服务

### Previous Story Intelligence

**从 Story 30.1 学到的关键经验：**
1. **循环导入风险**: precool 模块与 load_shift 模块之间存在循环依赖，使用 lazy import 解决
2. **SystemConfig 读取模式**: 约束阈值通过 `SystemConfig` 表读取，支持运行时修改
3. **默认值策略**: 每个约束参数都有独立默认值，不依赖其他模块的常量

**从 Story 30.4 学到的关键经验：**
1. **API 响应格式**: `{"code": 200, "message": "success", "data": ...}`
2. **前后端数据传递**: 优先通过 props 从父组件传入，而非组件内部 API 调用

**从 Epic 30 回顾延续的行动项：**
- ⚠️ rollback_manager 条件 2 使用固定 2.0°C/h 占位符（需在 Story 31.2 替换为实际预测速率）

## NFR 追溯

- **NFR-TCL-1**: 贪心调度算法 O(N) 复杂度，计划生成耗时 < 5s

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Completion Notes List
- 6 个 Task 全部完成，43 个单元测试全通过 (1.09s)
- PrecoolSchedule 模型追加到 thermal.py，含联合唯一约束 (cooling_zone_id, schedule_date)
- Alembic 迁移成功创建 precool_schedules 表（SQLite 兼容：UniqueConstraint 在 create_table 内定义）
- scheduler.py 实现完整贪心调度算法：谷时预冷/峰时释放/平时维持，RC 方程含 COP 和 bypass 修正
- 电价时段优先从 ElectricityPricing 表读取，兜底使用默认 5 时段配置
- 约束验证实现轨迹级逐步检查（温度上下限+温变速率），3 次重试自动放宽策略
- 两轮对抗性审查修复 10 个问题：PeriodType 枚举对齐、DB 电价读取、COP 配置优先、bypass 修正、数值稳定性检查、R/C 未标定处理

### Change Log
- `backend/app/models/thermal.py` — 追加 PrecoolSchedule 模型（含 Date/Time/JSON 导入）
- `backend/app/models/__init__.py` — 导出 PrecoolSchedule
- `backend/alembic/versions/20260311_0200_story_31_1_precool_schedules.py` — 新建迁移脚本
- `backend/app/services/precool/scheduler.py` — 新建贪心调度算法服务
- `backend/tests/services/test_precool_scheduler.py` — 新建 43 个单元测试

### File List
- `backend/app/models/thermal.py` (modified)
- `backend/app/models/__init__.py` (modified)
- `backend/alembic/versions/20260311_0200_story_31_1_precool_schedules.py` (new)
- `backend/app/services/precool/scheduler.py` (new)
- `backend/tests/services/test_precool_scheduler.py` (new)
