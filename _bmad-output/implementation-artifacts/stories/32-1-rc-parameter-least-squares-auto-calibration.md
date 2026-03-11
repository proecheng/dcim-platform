# Story 32.1: R/C 参数最小二乘自动校准

Status: done

## Story

As a 系统运维人员,
I want 系统自动基于历史温度数据校准 R 和 C 参数,
So that 热模型预测越来越精准。

## 依赖

- Story 29.1（数据模型，ThermalParameter 表）— done
- Story 29.2（RC 模型核心算法，thermal_model.py）— done

## Acceptance Criteria

1. Given 制冷区域已积累 ≥ 48 小时温度历史数据
   When 触发自动校准（每月定时 + 手动触发）
   Then 系统利用自然发生的功率变化事件（群控切换、故障恢复、定时启停）数据进行拟合
   And **禁止在生产环境主动制造功率扰动**

2. Given 事件检测逻辑
   When 从 CoolingLinkageRecord 表提取校准数据
   Then 通过 `CoolingLinkageRecord → ShiftExecution → ShiftPlan.selected_devices` 关联链过滤目标 zone 的事件
   And 监控 `event_type='adjust'|'recovery'` 记录中 `power_change` 绝对值 > 10% 的事件
   And 异常值过滤（3σ 原则过滤温度异常值、排除 power_change > 50% 的极端事件、排除环境温度 < 10°C 或 > 35°C）
   And 过滤后数据点 < 20 个时拒绝校准返回 `{error: "insufficient_data", valid_samples: N}`

3. Given 最小二乘拟合
   When 执行 R/C 参数校准
   Then 使用温度响应模型 `T(t) = T_steady + (T0 - T_steady) × e^(-t/τ)`，τ=RC
   And 校准数据窗口为最近 7 天（可配置 `CALIBRATION_WINDOW_DAYS`）
   And 使用 `scipy.optimize.curve_fit` 拟合 R 和 C

4. Given 校准结果
   When 物理合理性检查
   Then R > 0, C > 0, 时间常数 τ=RC 在 0.5-8 小时范围
   And 拟合 R² ≥ 0.7 时标记为成功，R² < 0.7 保留旧参数返回 `{error: "fitting_quality_low", r_squared: N}`
   And 校准通过后在同一事务中：先 UPDATE 旧记录 is_active=False → flush → INSERT 新记录 is_active=True
   And 同步更新 CoolingZone.thermal_R / thermal_C / r_calibrated_at
   And 校准失败时保留旧参数，记录失败原因
   And 保留最近 10 次校准记录（超出的自动清理）

5. Given 定时触发
   When 系统每月 1 日 03:37 自动触发全区域校准（避开 03:00 的其他定时任务）
   Then 通过 APScheduler CronTrigger 注册定时任务
   And 遍历所有非 demo 的 CoolingZone 逐一校准
   And 单个 zone 校准失败不中断其他 zone，记录 WARNING 日志
   And 校准结果写入 ThermalParameter 表 + 操作日志

## Tasks / Subtasks

- [ ] Task 1: 校准服务核心 (AC: #1-4)
  - [ ] 1.1 新建 `backend/app/services/precool/calibrator.py`
  - [ ] 1.2 实现 `RCCalibrator` 类：`calibrate(zone_id)` 主方法
  - [ ] 1.3 实现 `_collect_calibration_events()` — 从 CoolingLinkageRecord 提取事件数据
  - [ ] 1.4 实现 `_filter_outliers()` — 3σ 过滤 + 极端事件过滤 + 环境温度过滤
  - [ ] 1.5 实现 `_fit_rc_parameters()` — scipy.optimize.curve_fit 拟合
  - [ ] 1.6 实现 `_validate_result()` — 物理合理性检查
  - [ ] 1.7 实现 `_save_calibration()` — 保存到 ThermalParameter + 更新 CoolingZone + 清理旧记录

- [ ] Task 2: APScheduler 定时校准 (AC: #5)
  - [ ] 2.1 在 `backend/app/main.py` 注册月度校准定时任务
  - [ ] 2.2 实现 `run_monthly_calibration()` 遍历所有非 demo zone，逐一校准，单 zone 失败不中断

- [ ] Task 3: 单元测试 (AC: #1-5)
  - [ ] 3.1 新建 `backend/tests/services/precool/test_calibrator.py`
  - [ ] 3.2 测试事件数据收集（正常/不足/空数据）
  - [ ] 3.3 测试异常值过滤（3σ/极端事件/环境温度）
  - [ ] 3.4 测试拟合算法（正常拟合/拟合失败）
  - [ ] 3.5 测试物理合理性检查（通过/R=0/C=0/τ越界）
  - [ ] 3.6 测试保存逻辑（新建记录/停用旧记录/清理超过10条）
  - [ ] 3.7 测试整体校准流程（成功/数据不足/拟合失败/验证失败）

## Dev Notes

### 核心算法：温度响应曲线拟合

RC 热力学模型的阶跃响应为指数衰减：

```
T(t) = T_steady + (T0 - T_steady) × e^(-t/τ)
```

其中：
- `T_steady = T_ambient + Q_IT × R` — 稳态温度
- `T0` — 初始温度（功率变化前）
- `τ = R × C` — 时间常数（小时）
- `t` — 时间（小时）

拟合目标：已知 `(t, T(t), T_ambient, Q_IT)` 序列，拟合 `R` 和 `C`。

### 数据收集策略

**⚠️ Zone 关联方式：** `CoolingLinkageRecord` 无直接 `cooling_zone_id` 字段，需通过关联链过滤：
`CoolingLinkageRecord.execution_id → ShiftExecution.plan_id → ShiftPlan.selected_devices (JSON)`

实现方式：先查所有符合条件的 CoolingLinkageRecord，再通过应用层过滤关联到目标 zone。

```python
from app.models.load_shift import CoolingLinkageRecord, ShiftExecution, ShiftPlan

# 1. 查询最近 7 天内 adjust/recovery 事件（JOIN 到 ShiftExecution）
query = (
    select(CoolingLinkageRecord, ShiftExecution.plan_id)
    .join(ShiftExecution, CoolingLinkageRecord.execution_id == ShiftExecution.id)
    .where(CoolingLinkageRecord.event_type.in_(['adjust', 'recovery']))
    .where(CoolingLinkageRecord.timestamp >= cutoff_date)
    .where(CoolingLinkageRecord.before_power > 0)  # 避免除零
    .where(func.abs(CoolingLinkageRecord.power_change) / CoolingLinkageRecord.before_power > 0.1)
)

# 2. 通过 plan_id 批量查询 ShiftPlan.selected_devices，应用层过滤含目标 zone 的事件
# selected_devices 是 JSON list，检查是否包含目标 zone 关联的设备
```

**关键字段映射：**
- `before_power` / `after_power` — 功率变化前后值 (kW)
- `power_change` — 功率变化量 (kW)
- `return_temp_before` / `return_temp_after` — 回水温度 ≈ T_ambient 近似
- `supply_temp_before` / `supply_temp_after` — 送风温度
- `cop_before` / `cop_after` — COP 值
- `timestamp` — 事件时间

**温度轨迹采集：** 每个事件后需从 PointHistory 提取后续温度轨迹（30-120 分钟）用于拟合。
温度 point_id 通过 `CoolingZoneCabinet → CabinetTemperatureSensor` 关联获取回风温度点位（`sensor_type='return_air'`）。

```python
from app.models.topology_config import CoolingZoneCabinet, CabinetTemperatureSensor
from app.models.history import PointHistory

# 获取 zone 关联的回风温度 point_id 列表
sensor_query = (
    select(CabinetTemperatureSensor.point_id)
    .join(CoolingZoneCabinet, CabinetTemperatureSensor.cabinet_id == CoolingZoneCabinet.cabinet_id)
    .where(CoolingZoneCabinet.cooling_zone_id == zone_id)
    .where(CabinetTemperatureSensor.sensor_type == 'return_air')
)

# 查询事件后 30-120 分钟的温度时序
temp_query = (
    select(PointHistory.recorded_at, func.avg(PointHistory.value).label('avg_temp'))
    .where(PointHistory.point_id.in_(point_ids))
    .where(PointHistory.recorded_at.between(event_time, event_time + timedelta(minutes=120)))
    .group_by(PointHistory.recorded_at)
    .order_by(PointHistory.recorded_at)
)
```

### scipy.optimize.curve_fit 使用

```python
from scipy.optimize import curve_fit

def temp_response(t, R, C):
    tau = R * C
    return T_steady + (T0 - T_steady) * np.exp(-t / tau)

popt, pcov = curve_fit(
    temp_response, t_data, T_data,
    p0=[0.03, 2.0],            # 初始猜测
    bounds=([0.001, 0.1], [0.2, 50.0]),  # R: 0.001-0.2, C: 0.1-50
    maxfev=5000
)
R_fit, C_fit = popt
```

**注意：** `scipy>=1.11.0` 已在 requirements.txt 中。

### ThermalParameter 保存模式

```python
# 1. 停用当前活跃参数
await session.execute(
    update(ThermalParameter)
    .where(ThermalParameter.cooling_zone_id == zone_id)
    .where(ThermalParameter.is_active == True)
    .values(is_active=False)
)
await session.flush()  # 确保 UPDATE 先到数据库，避免唯一约束冲突

# 2. 创建新参数记录
param = ThermalParameter(
    cooling_zone_id=zone_id,
    thermal_R=R_fit,
    thermal_C=C_fit,
    fitting_r_squared=r_squared,
    fitting_method="auto_fit",
    sample_count=len(valid_samples),
    calibrated_at=datetime.now(),
    is_active=True,
    is_demo=False,
)
session.add(param)

# 3. 同步更新 CoolingZone
await session.execute(
    update(CoolingZone)
    .where(CoolingZone.id == zone_id)
    .values(thermal_R=R_fit, thermal_C=C_fit, r_calibrated_at=datetime.now())
)

# 4. 清理旧记录（保留最近 10 条）
old_params = await session.execute(
    select(ThermalParameter.id)
    .where(ThermalParameter.cooling_zone_id == zone_id)
    .order_by(ThermalParameter.created_at.desc())
    .offset(10)
)
old_ids = [r[0] for r in old_params.all()]
if old_ids:
    await session.execute(
        delete(ThermalParameter).where(ThermalParameter.id.in_(old_ids))
    )
```

**唯一约束注意:** `uq_thermal_params_zone_active` 约束 `(cooling_zone_id, is_active)` — 必须先停用旧参数再创建新参数。操作顺序：先 UPDATE is_active=False → `await session.flush()` → INSERT is_active=True。flush 确保 UPDATE 先到数据库，避免唯一约束冲突。整个流程在同一事务中执行，失败自动回滚。

### APScheduler 定时任务注册

参考 `executor.py` 中 APScheduler 集成模式：

```python
# main.py lifespan 中追加
from app.services.precool.calibrator import rc_calibrator

scheduler.add_job(
    rc_calibrator.run_monthly_calibration,
    CronTrigger(day=1, hour=3, minute=37),  # 每月1日 03:37（避开 03:00 时间窗口调参任务）
    id="monthly_rc_calibration",
    max_instances=1,
    replace_existing=True,
)
```

### R² 计算与质量检查

```python
ss_res = np.sum((T_actual - T_predicted) ** 2)
ss_tot = np.sum((T_actual - np.mean(T_actual)) ** 2)
r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0

# 质量门槛：R² >= 0.7 才接受校准结果
MIN_R_SQUARED = 0.7
if r_squared < MIN_R_SQUARED:
    return {"error": "fitting_quality_low", "r_squared": r_squared}
```

### scipy 条件导入

```python
try:
    from scipy.optimize import curve_fit
    import numpy as np
    _scipy_available = True
except ImportError:
    _scipy_available = False
    logger.warning("scipy 未安装，RC 参数自动校准功能不可用")

# calibrate() 方法开头检查
if not _scipy_available:
    return {"error": "scipy_not_installed"}
```

main.py 中注册定时任务时也需 try/except 包裹，scipy 缺失时跳过注册。

### CoolingLinkageRecord 模型位置

- 模型定义：`backend/app/models/load_shift.py` (第 424-459 行)
- 表名：`cooling_linkage_records`
- 外键：`execution_id` → `shift_executions`

### 异常值过滤策略

```python
# 1. 3σ 过滤温度异常值
mean_temp = np.mean(temps)
std_temp = np.std(temps)
mask_3sigma = np.abs(temps - mean_temp) <= 3 * std_temp

# 2. 极端事件过滤（power_change > 50%）
mask_power = np.abs(power_changes / before_powers) <= 0.5

# 3. 环境温度过滤
mask_env = (env_temps >= 10) & (env_temps <= 35)

# 组合过滤
valid_mask = mask_3sigma & mask_power & mask_env
```

### Project Structure Notes

- 新建文件：`backend/app/services/precool/calibrator.py`
- 新建文件：`backend/tests/services/precool/test_calibrator.py`
- 修改文件：`backend/app/main.py` — 追加月度校准定时任务
- 现有文件不需要修改 `thermal_model.py`（校准结果写入 ThermalParameter + CoolingZone 后，thermal_model 下次加载自动使用新参数）

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 32, Story 32.1]
- [Source: _bmad-output/planning-artifacts/architecture.md — Section 21.3 ThermalParameter 表, Section 21.4.1 calibrate_rc_parameters]
- [Source: backend/app/models/thermal.py — ThermalParameter 模型定义]
- [Source: backend/app/models/load_shift.py — CoolingLinkageRecord 模型]
- [Source: backend/app/models/topology_config.py — CoolingZone 热模型字段]
- [Source: backend/app/services/precool/thermal_model.py — RC 离散方程实现]
- [Source: backend/app/services/precool/executor.py — APScheduler 集成模式]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Completion Notes List

- R1 审查发现 3P0+8P1: zone关联(CoolingLinkageRecord无zone_id)、温度点位查找(CabinetTemperatureSensor)、UniqueConstraint并发保护
- R2 审查修复代码示例中缺失的flush()调用
- 代码审查修复: CronTrigger→'cron'字符串(与现有模式一致)、非demo zone过滤、DISTINCT温度传感器查询、commit异常处理
- UniqueConstraint(cooling_zone_id, is_active)限制每zone最多2条记录(1 active + 1 inactive)，无法保留10条历史，需未来修改约束
- 31个单元测试全部通过(scipy安装后)

### File List

- `backend/app/services/precool/calibrator.py` — 自动校准服务（新建）
- `backend/tests/services/precool/test_calibrator.py` — 校准服务测试（新建）
- `backend/app/main.py` — 追加月度校准定时任务
- `_bmad-output/implementation-artifacts/stories/32-1-rc-parameter-least-squares-auto-calibration.md` — Story 文档
