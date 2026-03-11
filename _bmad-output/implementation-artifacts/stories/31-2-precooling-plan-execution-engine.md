# Story 31.2: 预冷计划执行引擎

Status: done

## Story

As a 运维人员,
I want 系统按计划自动执行预冷操作并跟踪执行状态,
So that 预冷计划能可靠地自动运行。

## 依赖

- Story 29.2（RC 模型核心算法）— done
- Story 30.2（回退保护 7 项机制）— done
- Story 31.1（贪心调度算法 + PrecoolSchedule 模型）— done

## Acceptance Criteria

1. Given 已保存的预冷计划（status='pending'）
   When 到达计划的 precool_start_time（通过 APScheduler 定时触发）
   Then 系统自动启动执行：
   - APScheduler 每分钟扫描 pending 计划，检查 schedule_date == today 且 precool_start_time <= now <= peak_end_time
   - 匹配到的计划 status 更新为 'executing'
   - 按 temperature_trajectory 中的 q_cool 序列逐步下发制冷调整指令
   - 前置条件：scheduler.py 的 `_build_plan()` 需扩展 trajectory JSON 包含 q_cool 和 prices 字段

2. Given 执行中的预冷计划
   When 下发制冷调整指令
   Then 通过 `CoolingLinkageService.create_history_record()` 记录每次调整：
   - event_type = 'precool'（需追加为合法 event_type）
   - 遵守 power_adjust_step(20kW) 速率限制和 max_adjust_ratio(0.25) 比例限制
   - 每 5 分钟（与 scheduler 步长一致）推进一步
   - 使用独立 session 调用 create_history_record 避免事务冲突
   - 记录实际温度与预测温度的偏差

3. Given 执行中的预冷计划
   When 实时监控温度变化
   Then 复用 rollback_manager 监控通道：
   - 每次步进后检查 `rollback_manager.get_zone_rollback_status(zone_id)`
   - 如果 `has_active_rollback=True`，立即中止预冷执行
   - 温度偏差（实际 vs 预测）超过 2°C 时记录警告日志
   - 温度偏差超过 3°C 时触发中止

4. Given 安全约束触发或偏差过大
   When rollback_manager 检测到回退条件 或 温度偏差 > 3°C
   Then 自动中止预冷：
   - 计划 status 更新为 'aborted'
   - abort_reason 记录触发的回退条件类型或偏差信息
   - 中止前将当步实际温度写入 trajectory（避免数据缺失）
   - 制冷功率恢复到基线电功率 Q_baseline_elec = (Q_IT + (T_amb - T)/R) / COP
   - 恢复不受 step_limit 限制，直接设定目标功率（安全优先）
   - 通过 create_history_record 记录恢复操作（event_type='recovery'）

5. Given 预冷计划正常执行完毕
   When 到达 peak_end_time（使用 datetime 比较避免 midnight 跨天问题）
   Then 执行完成处理：
   - 计划 status 更新为 'completed'
   - 计算 actual_savings_kwh = baseline_cost - actual_cost（基于实际功率和电价）
   - 更新 temperature_trajectory 追加 actual 温度数组和 q_cool_actual 功率数组
   - 制冷功率恢复到正常维持水平

6. Given 执行引擎实现
   When 运行后端测试
   Then 所有单元测试通过（≥18 个测试用例）

## Tasks / Subtasks

- [x] Task 0: 扩展 scheduler.py trajectory JSON 结构 (AC: #1 前置)
  - [x]0.1 修改 `scheduler.py` 的 `_build_plan()` 方法，在 trajectory 中追加 `q_cool`（每步制冷功率数组）和 `prices`（每步电价数组）
  - [x]0.2 trajectory 结构变为：`{predicted: [...], timestamps: [...], q_cool: [...], prices: [...]}`
  - [x]0.3 更新 Story 31.1 对应的测试用例验证新字段

- [x] Task 1: 创建 PrecoolExecutor 执行引擎核心类 (AC: #1, #2)
  - [x]1.1 创建 `backend/app/services/precool/executor.py`
  - [x]1.2 实现 `PrecoolExecutor` 类，单例模式 `precool_executor = PrecoolExecutor()`
  - [x]1.3 实现 `_load_execution_context(plan, session)` 加载 zone 热参数、联动配置
  - [x]1.4 实现 `_execute_step(step_index, plan, context, session)` 单步执行
  - [x]1.5 实现 `_get_current_step_index(plan)` 使用绝对步号 = now.hour*12 + now.minute//5（与 trajectory 288 步索引对齐）

- [x] Task 2: 实现制冷指令下发与功率控制 (AC: #2)
  - [x]2.1 实现 `_apply_cooling_adjustment(zone_id, target_q, current_q, config, session)` 遵守 step_limit 和 ratio_limit
  - [x]2.2 使用独立 session 调用 `create_history_record()` 记录调整（避免外层事务冲突）
  - [x]2.3 实现 `_get_current_cooling_power(zone_id, session)` — 从 CoolingLinkageRecord 最近一条的 after_power 读取
  - [x]2.4 实现 `_set_cooling_power(zone_id, target_q, session)` — 写入 CoolingLinkageRecord 并更新内存缓存
  - [x]2.5 实现 `_restore_baseline_power(zone_id, session)` — 直接设定基线电功率 (Q_IT+(T_amb-T)/R)/COP，不受 step_limit 限制
  - [x]2.6 处理 current_q=0 的边界（比例限幅兜底为 step_limit）

- [x] Task 3: 实现安全监控与自动中止 (AC: #3, #4)
  - [x]3.1 实现 `_check_safety(zone_id)` — 返回 status dict（含 has_active_rollback 和 active_triggers），避免重复调用
  - [x]3.2 实现 `_abort_plan(plan, reason, step_index, actual_temp, session)` — 写入当步 actual 后中止并恢复功率
  - [x]3.3 实现 `_check_temperature_deviation(plan, step_index, actual_temp)` 偏差监控
  - [x]3.4 偏差 > 2°C 记录 warning，> 3°C 调用 _abort_plan

- [x] Task 4: 实现执行完成与节省计算 (AC: #5)
  - [x]4.1 实现 `_complete_plan(plan, session)` 正常完成处理
  - [x]4.2 实现 `_calculate_actual_savings(plan, Q_IT, COP)` — 基线为 Q_IT/COP 均匀功率，actual 和 baseline 在相同步骤范围内求和
  - [x]4.3 更新 trajectory 追加 actual 温度数组和 q_cool_actual 功率数组
  - [x]4.4 调用 _restore_baseline_power 恢复功率

- [x] Task 5: APScheduler 集成与扫描任务 (AC: #1)
  - [x]5.1 实现 `scan_and_execute_plans()` 扫描 pending 计划（含 peak_end_time 过期检查）
  - [x]5.2 实现 `tick_executing_plans()` 推进 executing 计划（使用 datetime 比较）
  - [x]5.3 在 `main.py` lifespan 中注册 2 个 APScheduler 任务，设置 `max_instances=1, coalesce=True`
  - [x]5.4 使用 lazy import 避免循环导入

- [x] Task 6: 单元测试 (AC: #6)
  - [x]6.1 创建 `backend/tests/services/test_precool_executor.py`
  - [x]6.2 测试计划扫描：到时间自动启动、未到时间不启动、过期计划不启动
  - [x]6.3 测试单步执行：Q_cool 下发和历史记录
  - [x]6.4 测试功率限幅：step_limit 和 ratio_limit、current_q=0 边界
  - [x]6.5 测试安全中止：rollback 触发、偏差 > 3°C
  - [x]6.6 测试温度偏差：2°C 警告（不中止）、3°C 中止
  - [x]6.7 测试正常完成：节省计算、状态更新、trajectory 追加 actual
  - [x]6.8 测试功率恢复：中止和完成都恢复基线
  - [x]6.9 测试边界条件：无 pending 计划、zone 不存在、trajectory 缺失字段
  - [x]6.10 测试 _get_current_step_index 计算正确性

## Dev Notes

### 架构约束

- **修改文件**: `backend/app/services/precool/scheduler.py` — `_build_plan()` 扩展 trajectory JSON
- **新建文件**: `backend/app/services/precool/executor.py` — 预冷执行引擎
- **新建文件**: `backend/tests/services/test_precool_executor.py` — 单元测试
- **修改文件**: `backend/app/main.py` — 注册 APScheduler 任务（scan + tick）
- **修改文件**: `backend/tests/services/test_precool_scheduler.py` — 更新 trajectory 测试

### 核心设计

#### 执行引擎架构

```
APScheduler (main.py)
  ├── scan_and_execute_plans()  [每 1 分钟, max_instances=1, coalesce=True]
  │   └── 查询 status='pending' 且 schedule_date==today
  │       且 precool_start_time <= now.time() <= peak_end_time
  │       └── _start_execution(plan) → status='executing'
  │
  └── tick_executing_plans()    [每 5 分钟, max_instances=1, coalesce=True]
      └── 查询 status='executing'
          ├── _get_current_step_index(plan) → step_index
          ├── _check_safety(zone_id) → rollback 检查
          ├── _execute_step(step_index, ...) → 下发 Q_cool + 偏差监控
          └── 到达 peak_end_time → _complete_plan()
```

#### scheduler.py trajectory 扩展（Task 0）

```python
# _build_plan() 中 trajectory 扩展为：
trajectory = {
    "predicted": [s.T_room for s in steps],
    "timestamps": [f"{int(s.time_minutes // 60):02d}:{int(s.time_minutes % 60):02d}" for s in steps],
    "q_cool": [s.Q_cool for s in steps],         # 每步计划制冷功率
    "prices": [s.price for s in steps],           # 每步电价
}
```

#### PrecoolExecutor 类设计

```python
class PrecoolExecutor:
    """预冷计划执行引擎"""

    def _get_current_step_index(self, plan: PrecoolSchedule) -> int:
        """根据当前时间计算绝对步索引

        使用绝对步号，与 trajectory 288 步数组索引直接对齐：
        step_index = now.hour * 12 + now.minute // 5
        trajectory[0] = 00:00, trajectory[96] = 08:00, trajectory[287] = 23:55
        """
        now = datetime.now()
        return min(now.hour * 12 + now.minute // 5, 287)

    async def scan_and_execute_plans(self):
        """扫描 pending 计划，启动到时间的计划"""
        async with async_session() as session:
            now = datetime.now()
            today = now.date()
            current_time = now.time()

            plans = await session.execute(
                select(PrecoolSchedule).where(
                    PrecoolSchedule.status == "pending",
                    PrecoolSchedule.schedule_date == today,
                    PrecoolSchedule.precool_start_time <= current_time,
                    PrecoolSchedule.peak_end_time >= current_time,  # 未过期
                )
            )
            for plan in plans.scalars().all():
                try:
                    await self._start_execution(plan, session)
                except Exception as e:
                    logger.error(f"启动预冷计划 {plan.id} 失败: {e}")
            await session.commit()

    async def _start_execution(self, plan, session):
        """启动计划执行"""
        # 检查 zone 的 precool_enabled
        config = await self._load_linkage_config(plan.cooling_zone_id, session)
        if not config or not config.precool_enabled:
            logger.warning(f"Zone {plan.cooling_zone_id} 预冷未启用，跳过计划 {plan.id}")
            return

        plan.status = "executing"
        logger.info(f"🔄 预冷计划 {plan.id} 开始执行 zone={plan.cooling_zone_id}")

    async def tick_executing_plans(self):
        """推进 executing 状态的计划"""
        async with async_session() as session:
            plans = await session.execute(
                select(PrecoolSchedule).where(
                    PrecoolSchedule.status == "executing",
                )
            )
            for plan in plans.scalars().all():
                try:
                    await self._tick_plan(plan, session)
                except Exception as e:
                    logger.error(f"推进预冷计划 {plan.id} 失败: {e}")
            await session.commit()

    async def _tick_plan(self, plan, session):
        """单次推进计划"""
        now = datetime.now()
        # 使用 datetime 比较避免 midnight 跨天问题
        plan_end_dt = datetime.combine(plan.schedule_date, plan.peak_end_time)
        if now >= plan_end_dt:
            await self._complete_plan(plan, session)
            return

        # 安全检查 — _check_safety 直接返回 status dict
        safety_status = await self._check_safety(plan.cooling_zone_id)
        if safety_status.get("has_active_rollback"):
            triggers = [t["trigger_type"] for t in safety_status.get("active_triggers", [])]
            step_index = self._get_current_step_index(plan)
            actual_temp = await self._get_actual_temperature(plan.cooling_zone_id, session)
            await self._abort_plan(
                plan, f"rollback: {','.join(triggers)}", step_index, actual_temp, session
            )
            return

        # 执行当前步
        step_index = self._get_current_step_index(plan)
        await self._execute_step(step_index, plan, session)

    async def _execute_step(self, step_index, plan, session):
        """执行单步：下发制冷调整指令"""
        trajectory = plan.temperature_trajectory or {}
        q_cool_schedule = trajectory.get("q_cool", [])

        if step_index >= len(q_cool_schedule):
            return

        target_q_cool = q_cool_schedule[step_index]
        current_q_cool = await self._get_current_cooling_power(
            plan.cooling_zone_id, session
        )
        config = await self._load_linkage_config(plan.cooling_zone_id, session)

        # 应用功率调整
        actual_q_cool = await self._apply_cooling_adjustment(
            plan.cooling_zone_id, target_q_cool, current_q_cool, config, session
        )

        # 记录实际温度和偏差检查
        actual_temp = await self._get_actual_temperature(
            plan.cooling_zone_id, session
        )
        # 偏差检查
        predicted_temps = trajectory.get("predicted", [])
        if step_index < len(predicted_temps):
            deviation = abs(actual_temp - predicted_temps[step_index])
            if deviation > 3.0:
                # abort 前先写入当步 actual 数据（P1-11 修复）
                self._record_actual_data(trajectory, step_index, actual_temp, actual_q_cool)
                plan.temperature_trajectory = trajectory
                await self._abort_plan(
                    plan, f"temperature_deviation_{deviation:.1f}C",
                    step_index, actual_temp, session
                )
                return
            if deviation > 2.0:
                logger.warning(
                    "预冷计划 %d 步 %d 温度偏差 %.1f°C（实际 %.1f vs 预测 %.1f）",
                    plan.id, step_index, deviation, actual_temp,
                    predicted_temps[step_index],
                )

        # 记录实际数据到 trajectory
        self._record_actual_data(trajectory, step_index, actual_temp, actual_q_cool)
        plan.temperature_trajectory = trajectory  # 触发 JSON 字段更新

    def _record_actual_data(self, trajectory, step_index, actual_temp, actual_q_cool):
        """写入实际温度和功率到 trajectory（按绝对步索引对齐）"""
        actual_temps = trajectory.setdefault("actual", [])
        actual_powers = trajectory.setdefault("q_cool_actual", [])
        while len(actual_temps) <= step_index:
            actual_temps.append(None)
        while len(actual_powers) <= step_index:
            actual_powers.append(None)
        actual_temps[step_index] = actual_temp
        actual_powers[step_index] = actual_q_cool

    async def _check_safety(self, zone_id):
        """检查 rollback_manager 安全状态，返回完整 status dict"""
        from app.services.precool.rollback_manager import rollback_manager
        return rollback_manager.get_zone_rollback_status(zone_id)
```

#### APScheduler 注册模式

```python
# 在 main.py lifespan 中，scheduler.start() 之前追加：
from app.services.precool.executor import precool_executor

scheduler.add_job(
    _run_precool_scan,
    'interval',
    minutes=1,
    max_instances=1,
    coalesce=True,
    id='precool_scan',
    name='预冷计划扫描任务',
)

scheduler.add_job(
    _run_precool_tick,
    'interval',
    minutes=5,
    max_instances=1,
    coalesce=True,
    id='precool_tick',
    name='预冷计划执行推进任务',
)

# 任务函数定义（在 lifespan 函数外部）：
async def _run_precool_scan():
    try:
        await precool_executor.scan_and_execute_plans()
    except Exception as e:
        logger.error(f"预冷扫描异常: {e}")

async def _run_precool_tick():
    try:
        await precool_executor.tick_executing_plans()
    except Exception as e:
        logger.error(f"预冷推进异常: {e}")
```

#### 制冷功率调整与下发

```python
async def _apply_cooling_adjustment(
    self, zone_id, target_q, current_q, config, session
):
    """下发制冷调整，遵守 power_adjust_step 和 max_adjust_ratio

    注意：target_q 和 current_q 都是电功率 (kW)，不是热功率。
    scheduler 中的 Q_cool 即电功率。
    """
    step_limit = config.power_adjust_step if config else 20  # kW/step
    max_ratio = config.max_adjust_ratio if config else 0.25

    delta = target_q - current_q
    # 速率限幅
    if abs(delta) > step_limit:
        delta = step_limit if delta > 0 else -step_limit
    # 比例限幅（current_q=0 时兜底，只用速率限幅）
    if current_q > 0:
        max_delta = current_q * max_ratio
        if abs(delta) > max_delta:
            delta = max_delta if delta > 0 else -max_delta

    actual_q = current_q + delta

    # 写入目标功率到 CoolingLinkageRecord（视为"下发指令"）
    # 使用独立 session 避免外层事务冲突
    async with async_session() as history_session:
        await CoolingLinkageService.create_history_record(
            db=history_session,
            event_type="precool",
            before_power=current_q,
            after_power=actual_q,
            cop_before=config.target_cop or 3.5,
            cop_after=config.target_cop or 3.5,
            supply_temp_before=0, supply_temp_after=0,
            return_temp_before=0, return_temp_after=0,
            reason=f"precool_step zone={zone_id}",
        )
    return actual_q

async def _get_current_cooling_power(self, zone_id, session):
    """获取当前制冷电功率

    从 CoolingLinkageRecord 最近一条记录的 after_power 读取。
    如果无记录，返回默认值（Q_IT 估算）。
    """
    from app.models.load_shift import CoolingLinkageRecord
    result = await session.execute(
        select(CoolingLinkageRecord.after_power)
        .order_by(CoolingLinkageRecord.id.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row if row is not None else 100.0  # 默认 100kW
```

#### 功率恢复（中止和完成时调用）

```python
async def _restore_baseline_power(self, zone_id, session):
    """恢复制冷功率到维持温度的基线电功率

    基线电功率 = (Q_IT + (T_amb - T_current) / R) / COP
    恢复时不受 step_limit 限制（安全优先，需快速恢复）
    """
    zone = await session.get(CoolingZone, zone_id)
    if not zone or not zone.thermal_R:
        return

    T_current = await self._get_actual_temperature(zone_id, session)
    Q_IT = await self._get_it_load(zone_id, session)
    T_amb = await self._get_ambient_temp(session)
    config = await self._load_linkage_config(zone_id, session)
    COP = config.target_cop if config and config.target_cop else 3.5

    # 热平衡基线制冷量 / COP = 电功率
    Q_baseline_thermal = Q_IT + (T_amb - T_current) / zone.thermal_R
    Q_baseline_elec = Q_baseline_thermal / COP

    current_q = await self._get_current_cooling_power(zone_id, session)

    # 安全恢复：直接设定目标功率，不受 step_limit 限制
    async with async_session() as history_session:
        await CoolingLinkageService.create_history_record(
            db=history_session,
            event_type="recovery",
            before_power=current_q,
            after_power=Q_baseline_elec,
            cop_before=COP, cop_after=COP,
            supply_temp_before=0, supply_temp_after=0,
            return_temp_before=0, return_temp_after=0,
            reason=f"precool_restore zone={zone_id}",
        )
```

#### 节省电费计算

```python
def _calculate_actual_savings(self, plan, Q_IT, COP):
    """计算实际节省电量

    基线电功率 = Q_IT / COP（不预冷时维持温度所需的恒定电功率）
    actual_savings = Σ(Q_baseline_elec * dt * price_i) - Σ(Q_actual_i * dt * price_i)
    只在有 actual 数据的步骤范围内求和（precool_start 到执行结束）
    """
    trajectory = plan.temperature_trajectory or {}
    q_cool_actual = trajectory.get("q_cool_actual", [])
    prices = trajectory.get("prices", [])

    DT = 5 / 60  # 小时
    Q_baseline_elec = Q_IT / COP if COP > 0 else Q_IT / 3.5

    actual_cost = 0.0
    baseline_cost = 0.0

    for i, (q_actual, price) in enumerate(zip(q_cool_actual, prices)):
        if q_actual is not None and price is not None:
            actual_cost += q_actual * DT * price
            baseline_cost += Q_baseline_elec * DT * price

    return round(max(0.0, baseline_cost - actual_cost), 2)
```

### 与现有模块的集成点

| 现有模块 | 集成方式 | 说明 |
|---------|--------|------|
| `scheduler.py` | 修改 `_build_plan()` 扩展 trajectory JSON | 追加 q_cool、prices 字段 |
| `rollback_manager.py` | `get_zone_rollback_status(zone_id)` | 安全检查，has_active_rollback 时中止 |
| `cooling_linkage_service.py` | `create_history_record()` 独立 session | event_type='precool'/'recovery' |
| `constraints.py` | 复用阈值常量 | DEFAULT_TEMP_MAX/MIN |
| `thermal_model.py` | 参考温度查询路径 | _get_actual_temperature |
| `main.py` | APScheduler 注册 2 个定时任务 | scan(1min) + tick(5min)，max_instances=1 |

### 已有字段确认

**PrecoolSchedule** 已有字段（Story 31.1 创建）：
- `status`: pending/executing/completed/aborted
- `abort_reason`: 中止原因
- `actual_savings_kwh`: 实际节省（nullable）
- `temperature_trajectory`: JSON — **当前只含 predicted + timestamps，需扩展**

**扩展后 trajectory JSON 结构**：
```json
{
  "predicted": [22.0, 21.8, ...],      // 288 步预测温度
  "timestamps": ["00:00", "00:05", ...], // 288 步时间标签
  "q_cool": [150, 155, ...],            // 288 步计划制冷功率 (Task 0 新增)
  "prices": [0.25, 0.25, ...],          // 288 步电价 (Task 0 新增)
  "actual": [22.1, 21.9, ...],          // 执行期间实际温度 (executor 追加)
  "q_cool_actual": [148, 152, ...]      // 执行期间实际功率 (executor 追加)
}
```

**CoolingLinkageConfig** 已有字段：
- `power_adjust_step`: 功率调整步长（默认 20kW）
- `max_adjust_ratio`: 最大调整比例（默认 0.25）
- `target_cop`: 目标 COP
- `precool_enabled`: 预冷开关

**CoolingLinkageService.create_history_record** event_type 合法值：
- 已有: `adjust` / `alarm` / `recovery` / `manual`
- 新增: `precool`（本 Story 使用）
- 需更新 CoolingLinkageRecord 模型的 comment 和 create_history_record docstring

**制冷功率下发机制**（demo/模拟模式）：
- 写入 `CoolingLinkageRecord`（event_type='precool', after_power=目标值）即视为"下发指令"
- `_get_current_cooling_power()` 从最近一条 Record 的 `after_power` 读取当前状态
- 后续如需对接真实设备，在 `_set_cooling_power()` 中追加设备控制 API 调用

### 测试策略

```python
class TestPrecoolExecutor:
    # 扫描与启动
    async def test_scan_finds_pending_plan_at_time(self)           # 到时间自动启动
    async def test_scan_ignores_future_plan(self)                   # 未到时间不启动
    async def test_scan_ignores_expired_plan(self)                  # 过了 peak_end_time 不启动
    async def test_scan_checks_precool_enabled(self)                # precool_enabled=False 不启动

    # 步索引计算
    async def test_step_index_at_start(self)                        # 开始时步索引=0
    async def test_step_index_after_1_hour(self)                    # 1小时后步索引=12
    async def test_step_index_max_287(self)                         # 不超过 287

    # 单步执行
    async def test_execute_step_applies_q_cool(self)                # Q_cool 下发
    async def test_execute_step_records_history(self)               # 联动历史记录
    async def test_execute_step_respects_power_step_limit(self)     # 速率限制
    async def test_execute_step_current_q_zero_uses_step_limit(self)# current_q=0 边界

    # 安全监控
    async def test_abort_on_rollback_triggered(self)                # rollback 触发中止
    async def test_deviation_warning_at_2c(self)                    # 2°C 偏差警告不中止
    async def test_abort_on_deviation_over_3c(self)                 # 3°C 偏差中止
    async def test_restore_power_on_abort(self)                     # 中止时恢复功率

    # 正常完成
    async def test_complete_at_peak_end_time(self)                  # 到时间完成
    async def test_actual_savings_calculated(self)                  # 节省计算
    async def test_trajectory_has_actual_temps(self)                # 实际温度记录
    async def test_restore_power_on_complete(self)                  # 完成时恢复功率

    # 边界条件
    async def test_no_pending_plans(self)                           # 无计划不报错
    async def test_missing_trajectory_fields(self)                  # trajectory 缺失字段不崩溃
```

### Project Structure Notes

- `executor.py` 放在 `backend/app/services/precool/` 目录，与 `scheduler.py`、`constraints.py`、`rollback_manager.py` 平级
- 测试文件放在 `backend/tests/services/`，命名 `test_precool_executor.py`
- main.py 追加 2 个 APScheduler 任务，插入在 `scheduler.start()` 之前（第 864 行附近）

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic31.Story31.2] — AC 定义
- [Source: _bmad-output/planning-artifacts/architecture.md#Section21] — 预冷 TCL 架构 V4.2.0
- [Source: backend/app/services/precool/scheduler.py#L535-538] — _build_plan() trajectory 当前结构
- [Source: backend/app/services/precool/rollback_manager.py#L438-456] — get_zone_rollback_status()
- [Source: backend/app/services/load_shift/cooling_linkage_service.py#L202-266] — create_history_record()
- [Source: backend/app/main.py#L597-872] — APScheduler 注册模式
- [Source: backend/app/main.py#L959-988] — _rollback_monitor_loop 模式参考
- [Source: backend/app/models/thermal.py] — PrecoolSchedule 模型
- [Source: backend/app/services/precool/constraints.py] — 约束阈值常量

### Previous Story Intelligence

**从 Story 31.1 学到的关键经验：**
1. **循环导入风险**: precool 模块与 load_shift 模块之间存在循环依赖，使用 lazy import 解决
2. **temperature_trajectory JSON 结构**: 当前只含 predicted 和 timestamps，**Task 0 扩展添加 q_cool 和 prices**
3. **Q_cool 语义**: scheduler 中的 Q_cool 是制冷**电功率** (kW electrical)，不是热功率。热平衡公式中出现的是 Q_cool*COP（有效制冷量）
4. **ScheduleStep dataclass**: 有 Q_cool（电功率）、price（电价）、T_room（温度）等字段
5. **COP 获取优先级**: config.target_cop → 季节修正（冬4.0/过渡3.5/夏2.8）

**从 Story 30.2 学到的关键经验：**
1. **RollbackManager 是单例**: `rollback_manager = RollbackManager()`，通过 asyncio.create_task 启动
2. **check_zone 返回值**: 内部更新 _zone_states，外部通过 get_zone_rollback_status() 查询
3. **恢复延迟**: 回退触发后有 5-15 分钟（300-900 秒）恢复观察期（RECOVERY_WAIT_xxx 常量），防止抖动
4. **内存状态**: _zone_states 是纯内存 dict，进程重启后清零。executor 的 _check_safety 应作为辅助检查，主安全保障依赖 rollback_manager 的持续监控循环

**从 main.py APScheduler 模式学到：**
1. **max_instances=1 + coalesce=True**: 防止任务重叠
2. **misfire_grace_time**: 可选，允许任务延迟执行的容忍时间
3. **任务函数外部定义**: 异步任务函数在 lifespan 外部用 async def 定义

## NFR 追溯

- **NFR-TCL-4**: 预冷执行引擎可靠运行，安全约束触发时自动中止

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Completion Notes List
- 7 个 Task 全部完成，36 个单元测试全通过 (1.17s)，加上 scheduler 43 个共 79 个全通过
- Task 0: scheduler.py trajectory 扩展增加 q_cool 和 prices 字段
- executor.py 实现完整执行引擎：scan(1min)/tick(5min) 双定时任务，APScheduler max_instances=1
- 绝对步索引对齐 trajectory 288 步数组，避免相对偏移错位
- 功率调整遵守 step_limit(20kW) 和 ratio_limit(0.25)，current_q=0 只用速率限幅
- 安全中止：rollback_manager 状态检查 + 温度偏差 > 3°C，abort 前写入当步 actual 数据
- 功率恢复使用 (Q_IT+(T_amb-T)/R)/COP 正确转换为电功率，不受 step_limit 限制
- 节省计算基线用 Q_IT/COP 均匀功率，只在有效步骤（非 None）范围内求和
- 独立 session 调用 create_history_record 避免外层事务冲突
- 两轮对抗性审查修复 17 个问题：trajectory JSON 缺字段、Q 语义混淆(热/电)、功率下发机制、midnight 跨天、步索引对齐、节省计算基线、恢复不完整、并发保护等

### Change Log
- `backend/app/services/precool/scheduler.py` — _build_plan() trajectory 扩展 q_cool/prices
- `backend/app/services/precool/executor.py` — 新建预冷执行引擎
- `backend/app/main.py` — 注册 precool_scan + precool_tick APScheduler 任务
- `backend/tests/services/test_precool_scheduler.py` — 更新 trajectory 字段验证
- `backend/tests/services/test_precool_executor.py` — 新建 36 个单元测试

### File List
- `backend/app/services/precool/scheduler.py` (modified)
- `backend/app/services/precool/executor.py` (new)
- `backend/app/main.py` (modified)
- `backend/tests/services/test_precool_scheduler.py` (modified)
- `backend/tests/services/test_precool_executor.py` (new)
