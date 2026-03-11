# Story 29.3: 温度裕度法 (THM) 安全兜底

Status: ready-for-dev

## Story

As a 系统运维人员,
I want 在 RC 模型未校准时系统自动使用 THM 方法估算可转移功率,
So that 系统上线初期也能安全地参与负荷转移。

## Acceptance Criteria

1. Given 制冷区域 RC 参数未校准（thermal_parameters 表中无 is_active=True 记录，或 CoolingZone 表中 thermal_R/thermal_C 为 NULL）
   When 请求可转移功率估算（调用 `datacenter_shift_strategy.py` 的 `calculate_shiftable_power()`）
   Then 系统自动使用 THM 公式：`ratio = (T_max - T_current_max) / (T_max - T_supply) × safety_factor`
   - T_max = 27°C（ASHRAE A2 类上限，参考架构文档 21.2.1）
   - T_supply = 12°C（精密空调送风温度，通过 `{device_code}_supply_temp` 点位获取，如果不存在或数据为空，使用固定值 12°C）
   - safety_factor = 0.8（默认值，范围 0.7~0.9，通过 SystemConfig 表 `thm_safety_factor` 配置项获取）
   - ratio 绝对上限 0.6（absolute_max_ratio，通过 SystemConfig 表 `thm_absolute_max_ratio` 配置项获取），即最多转移 60% 制冷功率
   - **温度裕度红线**: 当 headroom = T_max - T_current_max < 2.0°C 时，ratio = 0（禁止转移），红线阈值通过 SystemConfig 表 `thm_min_headroom_celsius` 配置项获取（默认 2.0）
   - **热缓冲时间校验**: 同时校验热缓冲时间 ≥ 制冷滞后时间 × 1.5（约 30 分钟），热缓冲时间 = headroom / 温升速率，温升速率通过最近 1 小时温度变化计算（如果数据不足，使用保守估计 0.5°C/h）
   - T_current_max（最热机柜进风温度）通过复用 `datacenter_shift_strategy.py` 现有链路获取：CoolingZone → CoolingZoneCabinet → Cabinet → CabinetTemperatureSensor(sensor_location='inlet') → PointHistory（查询最近 5 分钟数据，取最大值）
   - **数据质量检查**: 如果 T_current_max 数据缺失（无任何历史数据）或传感器离线（最新数据时间戳 > 1 小时前），拒绝转移并返回错误 `{error: "sensor_offline", zone_id: X}`
   - **日志记录**: 记录当前使用 THM 模式、裕度值 headroom、计算结果 ratio、T_current_max、T_supply、safety_factor、absolute_max_ratio、min_headroom_celsius
   - **模式切换**: RC 模型校准完成后（thermal_parameters 表中存在 is_active=True 记录），自动切换到 TCL 模式（调用 `ThermalModel.predict_temperature()`）

2. And **THM 方法实现位置**:
   - 在 `datacenter_shift_strategy.py` 的 `calculate_shiftable_power()` 方法中实现
   - 在方法开始时检查 RC 参数是否校准：
     ```python
     # 检查 thermal_parameters 表
     thermal_param = await session.execute(
         select(ThermalParameter)
         .where(ThermalParameter.cooling_zone_id == zone_id)
         .where(ThermalParameter.is_active == True)
     )
     thermal_param = thermal_param.scalar_one_or_none()

     # 如果未校准，使用 THM 方法
     if thermal_param is None:
         return await _calculate_shiftable_power_thm(zone_id, session)
     else:
         # 使用 TCL 模型（调用 ThermalModel.predict_temperature()）
         return await _calculate_shiftable_power_tcl(zone_id, session)
     ```
   - 新增 `_calculate_shiftable_power_thm()` 私有方法实现 THM 逻辑
   - 新增 `_calculate_shiftable_power_tcl()` 私有方法实现 TCL 逻辑（调用 `ThermalModel.predict_temperature()`）

3. And **SystemConfig 配置项**:
   - 新增 3 个配置项（如果不存在则使用默认值）:
     - `thm_safety_factor`: 安全系数（默认 0.8，范围 0.7~0.9）
     - `thm_absolute_max_ratio`: 绝对上限（默认 0.6，范围 0.4~0.8）
     - `thm_min_headroom_celsius`: 最小温度裕度（默认 2.0，范围 1.0~3.0）
   - 配置项通过 `SystemConfig` 表存储，key 格式为 `thm_*`，value 为 JSON 字符串
   - 如果配置项不存在，使用默认值并记录警告日志

4. And **温升速率计算**:
   - 查询最近 1 小时的 T_current_max 数据（CabinetTemperatureSensor → PointHistory）
   - 计算温升速率 = (最新温度 - 1小时前温度) / 1.0（单位：°C/h）
   - **数据不足处理**: 如果数据点 < 6 个（30 分钟），使用保守估计 0.5°C/h 并记录警告日志
   - **异常值过滤**: 如果温升速率 > 5°C/h（异常快）或 < -2°C/h（异常降温），使用保守估计 0.5°C/h 并记录警告日志
   - 热缓冲时间 = headroom / 温升速率（单位：小时）
   - 制冷滞后时间 = 20 分钟（固定值，参考架构文档 21.2.1）
   - 如果热缓冲时间 < 制冷滞后时间 × 1.5（30 分钟），ratio = 0（禁止转移）

5. And **返回值格式**:
   - 成功时返回:
     ```python
     {
         "zone_id": int,
         "shiftable_ratio": float,  # 0.0~0.6
         "method": "THM",  # 或 "TCL"
         "headroom_celsius": float,
         "T_current_max": float,
         "T_supply": float,
         "safety_factor": float,
         "absolute_max_ratio": float,
         "min_headroom_celsius": float,
         "thermal_buffer_hours": float,
         "temperature_rise_rate_celsius_per_hour": float
     }
     ```
   - 失败时返回:
     ```python
     {
         "error": str,  # "sensor_offline", "insufficient_data", "zone_not_found"
         "zone_id": int,
         "details": str  # 详细错误信息
     }
     ```

6. And **依赖检查**: 实现前检查 Story 29.1 和 Story 29.2 完成状态：
   - 验证 `thermal_parameters` 表存在
   - 验证 `ThermalModel` 类存在且可导入
   - 验证 `datacenter_shift_strategy.py` 中 `calculate_shiftable_power()` 方法存在
   - 如果依赖未满足，抛出 RuntimeError 并提示先完成 Story 29.1 和 Story 29.2

## Tasks / Subtasks

- [ ] 实现 THM 方法核心逻辑 (AC: #1, #2)
  - [ ] 在 `datacenter_shift_strategy.py` 中新增 `_calculate_shiftable_power_thm()` 私有方法
  - [ ] 实现 THM 公式计算逻辑
  - [ ] 实现温度裕度红线检查（headroom < 2.0°C 时 ratio = 0）
  - [ ] 实现 ratio 绝对上限检查（max 0.6）
  - [ ] 实现 T_current_max 数据质量检查（缺失/离线时拒绝转移）
  - [ ] 实现日志记录（THM 模式、裕度值、计算结果）

- [ ] 实现 SystemConfig 配置项读取 (AC: #3)
  - [ ] 新增 `_get_thm_config()` 辅助方法读取 3 个配置项
  - [ ] 实现默认值回退逻辑（配置项不存在时使用默认值）
  - [ ] 实现配置项范围校验（safety_factor: 0.7~0.9, absolute_max_ratio: 0.4~0.8, min_headroom: 1.0~3.0）

- [ ] 实现温升速率计算和热缓冲时间校验 (AC: #4)
  - [ ] 新增 `_calculate_temperature_rise_rate()` 辅助方法
  - [ ] 查询最近 1 小时 T_current_max 数据
  - [ ] 计算温升速率（°C/h）
  - [ ] 实现数据不足处理（< 6 个数据点时使用保守估计 0.5°C/h）
  - [ ] 实现异常值过滤（> 5°C/h 或 < -2°C/h 时使用保守估计）
  - [ ] 计算热缓冲时间并校验（< 30 分钟时 ratio = 0）

- [ ] 实现 RC 参数校准检查和模式切换 (AC: #1, #2)
  - [ ] 在 `calculate_shiftable_power()` 开始时检查 thermal_parameters 表
  - [ ] 如果未校准，调用 `_calculate_shiftable_power_thm()`
  - [ ] 如果已校准，调用 `_calculate_shiftable_power_tcl()`（新增方法，调用 `ThermalModel.predict_temperature()`）
  - [ ] 实现 `_calculate_shiftable_power_tcl()` 方法（调用 ThermalModel 并转换返回格式）

- [ ] 实现返回值格式化 (AC: #5)
  - [ ] 成功时返回包含 method="THM" 的字典
  - [ ] 失败时返回包含 error 字段的字典
  - [ ] 确保返回值格式与 AC#5 一致

- [ ] 编写单元测试 (AC: #1-#6)
  - [ ] 新建 `backend/tests/services/test_datacenter_shift_strategy_thm.py`
  - [ ] 测试 THM 方法基本功能（未校准时使用 THM）
  - [ ] 测试温度裕度红线（headroom < 2.0°C 时 ratio = 0）
  - [ ] 测试 ratio 绝对上限（max 0.6）
  - [ ] 测试数据质量检查（传感器离线时拒绝转移）
  - [ ] 测试温升速率计算（数据不足/异常值时使用保守估计）
  - [ ] 测试热缓冲时间校验（< 30 分钟时 ratio = 0）
  - [ ] 测试模式切换（RC 校准后使用 TCL 模式）
  - [ ] 测试 SystemConfig 配置项读取（默认值回退）

- [ ] 依赖检查 (AC: #6)
  - [ ] 验证 thermal_parameters 表存在
  - [ ] 验证 ThermalModel 类可导入
  - [ ] 验证 calculate_shiftable_power() 方法存在

## Dev Notes

### 架构约束

**数据源复用** (Architecture V4.2.0 Section 21.2.1):
- T_current_max 通过 `datacenter_shift_strategy.py` 现有链路获取，避免重复实现
- 链路: CoolingZone → CoolingZoneCabinet → Cabinet → CabinetTemperatureSensor(inlet) → PointHistory
- 查询最近 5 分钟数据，取最大值（保守估计）

**THM 方法定位** (Architecture V4.2.0 Section 21.3.1):
- THM 是 TCL 模型的安全兜底方案，不是替代方案
- 系统上线初期（RC 参数未校准）使用 THM，校准完成后自动切换到 TCL
- THM 更保守（safety_factor=0.8, absolute_max_ratio=0.6），TCL 更精确（基于物理模型预测）

**配置项管理** (Architecture V4.2.0 Section 21.3.2):
- 所有 THM 参数通过 SystemConfig 表配置，支持运行时调整
- 配置项 key 格式: `thm_*`（如 `thm_safety_factor`）
- 配置项 value 为 JSON 字符串（如 `"0.8"`）
- 如果配置项不存在，使用默认值并记录警告日志

**温升速率计算** (Architecture V4.2.0 Section 21.3.3):
- 查询最近 1 小时数据，计算温升速率（°C/h）
- 数据不足（< 6 个数据点）时使用保守估计 0.5°C/h
- 异常值（> 5°C/h 或 < -2°C/h）时使用保守估计 0.5°C/h
- 热缓冲时间 = headroom / 温升速率（单位：小时）
- 制冷滞后时间 = 20 分钟（固定值）

**数据质量保障** (Architecture V4.2.0 Section 21.3.4):
- T_current_max 数据缺失或传感器离线（> 1 小时无数据）时，拒绝转移并返回错误
- 温升速率异常时，使用保守估计并记录警告日志
- 所有数据质量问题都应记录到日志，便于后续分析

### 涉及文件

**核心实现**:
- `backend/app/services/datacenter_shift_strategy.py` — 主要修改文件
  - 修改 `calculate_shiftable_power()` 方法，增加 RC 参数校准检查
  - 新增 `_calculate_shiftable_power_thm()` 私有方法（THM 逻辑）
  - 新增 `_calculate_shiftable_power_tcl()` 私有方法（TCL 逻辑）
  - 新增 `_get_thm_config()` 辅助方法（读取 SystemConfig）
  - 新增 `_calculate_temperature_rise_rate()` 辅助方法（温升速率计算）

**依赖文件**:
- `backend/app/services/precool/thermal_model.py` — 依赖 Story 29.2，调用 `ThermalModel.predict_temperature()`
- `backend/app/models/precool.py` — 依赖 Story 29.1，查询 `ThermalParameter` 表
- `backend/app/models/system_config.py` — 读取 SystemConfig 配置项

**测试文件**:
- `backend/tests/services/test_datacenter_shift_strategy_thm.py` — 新建，THM 方法单元测试

### 测试标准

**单元测试覆盖率** (Architecture V4.2.0 Section 21.4):
- 核心方法覆盖率 ≥ 90%
- 边界条件测试: headroom = 2.0°C（临界值）, ratio = 0.6（上限）
- 异常场景测试: 传感器离线、数据不足、异常值
- 模式切换测试: RC 未校准 → THM, RC 已校准 → TCL

**性能要求** (Architecture V4.2.0 Section 21.4):
- 单区计算耗时 < 500ms（包含数据库查询）
- 温升速率计算耗时 < 200ms（查询 1 小时数据）

### Project Structure Notes

**命名约定**:
- 私有方法使用 `_` 前缀（如 `_calculate_shiftable_power_thm()`）
- 配置项 key 使用 `thm_` 前缀（如 `thm_safety_factor`）
- 返回值字段使用 snake_case（如 `shiftable_ratio`, `T_current_max`）

**代码组织**:
- THM 逻辑封装在独立的私有方法中，便于测试和维护
- 配置项读取封装在 `_get_thm_config()` 中，避免重复代码
- 温升速率计算封装在 `_calculate_temperature_rise_rate()` 中，便于复用

**错误处理**:
- 数据质量问题返回错误字典（包含 error 字段）
- 配置项缺失使用默认值并记录警告日志
- 依赖未满足抛出 RuntimeError

### References

- [Source: docs/空调可转移功率算法调研与改进方案.md#5-原推荐改进方案温度裕度法热缓冲时间法]
- [Source: docs/空调可转移功率算法调研与改进方案.md#6-预冷-tcl-模型详解推荐采用]
- [Source: _bmad-output/planning-artifacts/architecture.md#Section 21.2.1 - THM 方法定位]
- [Source: _bmad-output/planning-artifacts/architecture.md#Section 21.3.1 - 配置项管理]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 29.3 - 温度裕度法安全兜底]
- [Source: backend/app/services/datacenter_shift_strategy.py - 现有温度查询链路]
- [Source: backend/app/services/precool/thermal_model.py - ThermalModel 类]

## Dev Agent Record

### Agent Model Used

(待填写)

### Debug Log References

(待填写)

### Completion Notes List

(待填写)

### File List

(待填写)
