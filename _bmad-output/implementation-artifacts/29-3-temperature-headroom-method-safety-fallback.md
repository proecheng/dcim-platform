# Story 29.3: 温度裕度法 (THM) 安全兜底

Status: ready-for-dev

## Story

As a 系统运维人员,
I want 在 RC 模型未校准时系统自动使用 THM 方法估算可转移功率,
So that 系统上线初期也能安全地参与负荷转移。

## Acceptance Criteria

1. Given 制冷区域 RC 参数未校准（thermal_parameters 表中无 is_active=True 记录）
   When 请求可转移功率估算（新增 `calculate_shiftable_power_for_zone(zone_id)` 方法）
   Then 系统自动使用 THM 公式：`ratio = (T_max - T_current_max) / (T_max - T_supply) × safety_factor`
   - T_max = 27°C（ASHRAE A2 类上限，常量 TEMP_RECOMMENDED_MAX）
   - T_supply = 12°C（精密空调送风温度，通过 CoolingZone → CoolingZoneUnit → CoolingUnit → Device → Point(`{device_code}_supply_temp`) → PointHistory 获取最近 5 分钟数据，对所有有数据的 Unit 求平均值，如果所有 Unit 都无数据，使用固定值 12°C 并记录警告日志）
   - safety_factor = 0.8（默认值，范围 0.7~0.9，通过 SystemConfig 表 `thm_safety_factor` 配置项获取，value 存储为浮点数字符串如 `"0.8"`，读取后用 `float()` 解析）
   - ratio 绝对上限 0.6（absolute_max_ratio，通过 SystemConfig 表 `thm_absolute_max_ratio` 配置项获取），即最多转移 60% 制冷功率
   - **THM 公式除零保护**: 如果 T_max - T_supply ≤ 0（异常情况，送风温度 ≥ 最高温度），ratio = 0 并返回错误 `{error: "invalid_supply_temp", T_supply: X}`
   - **温度裕度红线**: 当 headroom = T_max - T_current_max < 2.0°C 时，ratio = 0（禁止转移），红线阈值通过 SystemConfig 表 `thm_min_headroom_celsius` 配置项获取（默认 2.0）
   - **热缓冲时间校验**: 同时校验热缓冲时间 ≥ 制冷滞后时间 × 1.5（30 分钟），热缓冲时间 = headroom / 温升速率（单位：小时），温升速率通过最近 1 小时温度数据手动实现最小二乘线性回归计算斜率（不依赖 numpy/scipy，避免新增依赖），**异常点过滤**: 回归前先过滤温度突变点（相邻点变化 > 3°C），如果数据不足 < 12 个点或过滤后 < 6 个点，使用保守估计 0.5°C/h，**除零保护**: 如果温升速率 ≤ 0（温度稳定或下降），热缓冲时间设为无穷大（跳过热缓冲时间校验）
   - T_current_max（最热机柜进风温度）通过复用 `datacenter_shift_strategy.py` 现有链路获取：CoolingZone → CoolingZoneCabinet → Cabinet → CabinetTemperatureSensor(sensor_location='inlet') → PointHistory（查询最近 5 分钟数据，取最大值）
   - **数据质量检查**: 如果 T_current_max 数据缺失（无任何历史数据）或传感器离线（最新数据时间戳 > 1 小时前），拒绝转移并返回错误 `{error: "sensor_offline", zone_id: X}`
   - **日志记录**: 记录当前使用 THM 模式、裕度值 headroom、计算结果 ratio、T_current_max、T_supply、温升速率、热缓冲时间（仅记录到日志，不返回给调用方）
   - **模式切换**: RC 模型校准完成后（thermal_parameters 表中存在 is_active=True 记录），自动切换到 TCL 模式（调用 `ThermalModel.predict_temperature()` 预测 1 小时后温度，如果预测温度 < T_max - 2°C，ratio = 0.4，否则 ratio = 0）

2. And **THM 方法实现位置**:
   - 新增 `calculate_shiftable_power_for_zone(zone_id: int, session: AsyncSession)` 公共方法
   - 在方法开始时检查 RC 参数是否校准：
     ```python
     # 检查 thermal_parameters 表（修复 SQLAlchemy 2.0 语法）
     thermal_param = (await session.execute(
         select(ThermalParameter)
         .where(ThermalParameter.cooling_zone_id == zone_id)
         .where(ThermalParameter.is_active == True)
     )).scalar_one_or_none()

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
     - `thm_safety_factor`: 安全系数（默认 0.8，范围 0.7~0.9），value 存储为浮点数字符串 `"0.8"`
     - `thm_absolute_max_ratio`: 绝对上限（默认 0.6，范围 0.4~0.8），value 存储为浮点数字符串 `"0.6"`
     - `thm_min_headroom_celsius`: 最小温度裕度（默认 2.0，范围 1.0~3.0），value 存储为浮点数字符串 `"2.0"`
   - 配置项通过 `SystemConfig` 表存储，key 格式为 `thm_*`，value 为浮点数字符串（不是 JSON，直接用 `float(value)` 解析）
   - 如果配置项不存在，使用默认值并记录警告日志
   - 读取后进行范围校验，超出范围时使用边界值（如 safety_factor=0.95 → 0.9，safety_factor=0.6 → 0.7）并记录警告日志
   - **配置项初始化**: 在系统启动时（`app/main.py` 的 `lifespan` 事件）自动创建缺失的配置项，避免每次调用都记录警告

4. And **温升速率计算**:
   - 查询最近 1 小时的 T_current_max 数据（CabinetTemperatureSensor → PointHistory），按 5 分钟间隔聚合，期望 12 个数据点
   - **异常点过滤**: 回归前先过滤温度突变点（相邻点变化 > 3°C，参考 ASHRAE TC9.9 数据中心温度变化率建议），过滤后如果数据点 < 6 个，使用保守估计 0.5°C/h 并记录警告日志
   - 使用手动实现的最小二乘线性回归计算温升速率斜率（°C/h）：对时间戳（转换为小时）和温度值进行最小二乘拟合，斜率即为温升速率，**不依赖 numpy/scipy**，避免新增依赖
   - **数据不足处理**: 如果原始数据点 < 12 个（1 小时），使用保守估计 0.5°C/h 并记录警告日志
   - **异常值过滤**: 如果回归后温升速率 > 2°C/h（数据中心温度变化率通常 < 1°C/h，参考 ASHRAE TC9.9）或 < -1°C/h（异常降温），使用保守估计 0.5°C/h 并记录警告日志
   - **除零保护**: 如果温升速率 ≤ 0（温度稳定或下降），热缓冲时间设为无穷大（float('inf')），跳过热缓冲时间校验（不限制转移）
   - 热缓冲时间 = headroom / 温升速率（单位：小时），仅当温升速率 > 0 时计算
   - 制冷滞后时间 = 20 分钟 = 1/3 小时（固定值）
   - 如果热缓冲时间 < 制冷滞后时间 × 1.5（0.5 小时 = 30 分钟），ratio = 0（禁止转移）

5. And **返回值格式**:
   - 成功时返回:
     ```python
     {
         "zone_id": int,
         "shiftable_ratio": float,  # 0.0~0.6
         "method": "THM",  # 或 "TCL"
         "headroom_celsius": float,  # 温度裕度，用于前端展示
         "T_current_max": float  # 当前最热机柜温度，用于前端告警展示
     }
     ```
   - 失败时返回:
     ```python
     {
         "error": str,  # "sensor_offline", "insufficient_data", "zone_not_found", "system_config_missing", "invalid_supply_temp"
         "zone_id": int,
         "details": str  # 详细错误信息
     }
     ```
   - **注意**: safety_factor, absolute_max_ratio, min_headroom_celsius, thermal_buffer_hours, temperature_rise_rate, T_supply 等中间计算值仅记录到日志，不返回给调用方（避免返回值冗余）

6. And **依赖检查**: 模块导入时（`datacenter_shift_strategy.py` 顶部）检查 Story 29.1 和 Story 29.2 完成状态：
   - 尝试导入 `ThermalParameter` 类，如果失败则记录错误日志（不抛出异常，避免阻塞模块导入）
   - 尝试导入 `ThermalModel` 类，如果失败则记录错误日志
   - 在 `calculate_shiftable_power_for_zone()` 方法调用时，如果依赖未满足，返回错误 `{error: "dependencies_not_met", details: "Story 29.1/29.2 not completed"}`
   - 验证 `SystemConfig`, `CoolingZone`, `CoolingZoneCabinet`, `CabinetTemperatureSensor` 等表存在（通过尝试查询验证）

## Tasks / Subtasks

- [ ] 实现 THM 方法核心逻辑 (AC: #1, #2)
  - [ ] 在 `datacenter_shift_strategy.py` 中新增 `calculate_shiftable_power_for_zone(zone_id, session)` 公共方法
  - [ ] 新增 `_calculate_shiftable_power_thm()` 私有方法
  - [ ] 实现 THM 公式计算逻辑
  - [ ] 实现 THM 公式除零保护（T_max - T_supply ≤ 0 时返回错误）
  - [ ] 实现温度裕度红线检查（headroom < 2.0°C 时 ratio = 0）
  - [ ] 实现 ratio 绝对上限检查（max 0.6）
  - [ ] 实现 T_current_max 数据质量检查（缺失/离线时拒绝转移）
  - [ ] 实现 T_supply 查询逻辑（CoolingZone → CoolingZoneUnit → CoolingUnit → Point → PointHistory，对所有有数据的 Unit 求平均值）
  - [ ] 实现日志记录（THM 模式、裕度值、计算结果、中间变量）

- [ ] 实现 SystemConfig 配置项读取 (AC: #3)
  - [ ] 新增 `_get_thm_config()` 辅助方法读取 3 个配置项
  - [ ] 实现默认值回退逻辑（配置项不存在时使用默认值）
  - [ ] 实现配置项范围校验（超出范围时使用边界值）
  - [ ] 在 `app/main.py` 的 `lifespan` 事件中新增配置项初始化逻辑

- [ ] 实现温升速率计算和热缓冲时间校验 (AC: #4)
  - [ ] 新增 `_calculate_temperature_rise_rate()` 辅助方法
  - [ ] 查询最近 1 小时 T_current_max 数据（期望 12 个数据点）
  - [ ] 实现异常点过滤（相邻点变化 > 3°C）
  - [ ] 手动实现最小二乘线性回归计算温升速率斜率（°C/h），不依赖 numpy/scipy
  - [ ] 实现数据不足处理（< 12 个数据点或过滤后 < 6 个点时使用保守估计 0.5°C/h）
  - [ ] 实现异常值过滤（回归后温升速率 > 2°C/h 或 < -1°C/h 时使用保守估计）
  - [ ] 实现除零保护（温升速率 ≤ 0 时热缓冲时间设为无穷大）
  - [ ] 计算热缓冲时间并校验（< 0.5 小时时 ratio = 0）

- [ ] 实现 RC 参数校准检查和模式切换 (AC: #1, #2)
  - [ ] 在 `calculate_shiftable_power_for_zone()` 开始时检查 thermal_parameters 表
  - [ ] 如果未校准，调用 `_calculate_shiftable_power_thm()`
  - [ ] 如果已校准，调用 `_calculate_shiftable_power_tcl()`（新增方法，调用 `ThermalModel.predict_temperature()`）
  - [ ] 实现 `_calculate_shiftable_power_tcl()` 方法：调用 ThermalModel 预测 1 小时后温度，如果预测温度 < T_max - 2°C，ratio = 0.4，否则 ratio = 0，并转换为统一返回格式

- [ ] 实现返回值格式化 (AC: #5)
  - [ ] 成功时返回包含 method="THM" 的字典
  - [ ] 失败时返回包含 error 字段的字典
  - [ ] 确保返回值格式与 AC#5 一致

- [ ] 编写单元测试 (AC: #1-#6)
  - [ ] 新建 `backend/tests/services/test_datacenter_shift_strategy_thm.py`
  - [ ] 测试 THM 方法基本功能（未校准时使用 THM）
  - [ ] 测试 THM 公式除零保护（T_supply = T_max 时返回错误）
  - [ ] 测试温度裕度红线（headroom < 2.0°C 时 ratio = 0）
  - [ ] 测试 ratio 绝对上限（max 0.6）
  - [ ] 测试数据质量检查（传感器离线时拒绝转移）
  - [ ] 测试温升速率计算（数据不足/异常值/异常点过滤时使用保守估计）
  - [ ] 测试线性回归计算准确性（给定已知斜率的数据，验证计算结果）
  - [ ] 测试热缓冲时间校验（< 30 分钟时 ratio = 0）
  - [ ] 测试除零保护（温升速率 ≤ 0 时跳过热缓冲时间校验）
  - [ ] 测试模式切换（RC 校准后使用 TCL 模式）
  - [ ] 测试 SystemConfig 配置项读取（默认值回退、范围校验）
  - [ ] 测试 T_supply 平均值计算（部分 Unit 有数据、部分无数据）

- [ ] 依赖检查 (AC: #6)
  - [ ] 在模块导入时尝试导入 ThermalParameter 和 ThermalModel 类
  - [ ] 导入失败时记录错误日志（不抛出异常）
  - [ ] 在方法调用时检查依赖，未满足时返回错误
  - [ ] 验证 SystemConfig, CoolingZone, CoolingZoneCabinet, CabinetTemperatureSensor 等表存在

## Dev Notes

### 架构约束

**数据源复用** (datacenter_shift_strategy.py 现有实现):
- T_current_max 通过现有链路获取，避免重复实现
- 链路: CoolingZone → CoolingZoneCabinet → Cabinet → CabinetTemperatureSensor(inlet) → PointHistory
- 查询最近 5 分钟数据，取最大值（保守估计）

**THM 方法定位** (docs/空调可转移功率算法调研与改进方案.md Section 5):
- THM 是 TCL 模型的安全兜底方案，不是替代方案
- 系统上线初期（RC 参数未校准）使用 THM，校准完成后自动切换到 TCL
- THM 更保守（safety_factor=0.8, absolute_max_ratio=0.6），TCL 更精确（基于物理模型预测）

**配置项管理** (SystemConfig 表):
- 所有 THM 参数通过 SystemConfig 表配置，支持运行时调整
- 配置项 key 格式: `thm_*`（如 `thm_safety_factor`）
- 配置项 value 为浮点数字符串（如 `"0.8"`），读取后用 `float()` 解析
- 如果配置项不存在，使用默认值并记录警告日志
- 读取后进行范围校验，超出范围时使用默认值并记录警告日志

**温升速率计算** (docs/空调可转移功率算法调研与改进方案.md Section 5):
- 查询最近 1 小时数据，期望 12 个数据点（5 分钟间隔）
- **异常点过滤**: 回归前先过滤温度突变点（相邻点变化 > 3°C），避免传感器故障影响回归结果
- 手动实现最小二乘线性回归计算温升速率斜率（°C/h），不依赖 numpy/scipy，避免新增依赖
- 数据不足（< 12 个数据点或过滤后 < 6 个点）时使用保守估计 0.5°C/h
- 异常值（回归后温升速率 > 2°C/h 或 < -1°C/h，参考 ASHRAE TC9.9 数据中心温度变化率 < 1°C/h）时使用保守估计 0.5°C/h
- 除零保护：温升速率 ≤ 0 时热缓冲时间设为无穷大（跳过热缓冲时间校验）
- 热缓冲时间 = headroom / 温升速率（单位：小时）
- 制冷滞后时间 = 20 分钟 = 1/3 小时（固定值）

**数据质量保障** (Story 29.2 经验):
- T_current_max 数据缺失或传感器离线（> 1 小时无数据）时，拒绝转移并返回错误
- 温升速率异常时，使用保守估计并记录警告日志
- 所有数据质量问题都应记录到日志，便于后续分析

**T_supply 数据源** (新增):
- 通过 CoolingZone → CoolingZoneUnit → CoolingUnit → Device → Point(`{device_code}_supply_temp`) → PointHistory 获取
- 查询最近 5 分钟数据，取所有 Unit 的平均值（多个空调送风温度可能不同）
- 如果所有 Unit 都无数据，使用固定值 12°C 并记录警告日志

### 涉及文件

**核心实现**:
- `backend/app/services/datacenter_shift_strategy.py` — 主要修改文件
  - 新增 `calculate_shiftable_power_for_zone(zone_id, session)` 公共方法（入口方法）
  - 新增 `_calculate_shiftable_power_thm(zone_id, session)` 私有方法（THM 逻辑）
  - 新增 `_calculate_shiftable_power_tcl(zone_id, session)` 私有方法（TCL 逻辑）
  - 新增 `_get_thm_config(session)` 辅助方法（读取 SystemConfig）
  - 新增 `_calculate_temperature_rise_rate(zone_id, session)` 辅助方法（温升速率计算）
  - 新增 `_get_zone_supply_temperature(zone_id, session)` 辅助方法（T_supply 查询）

**依赖文件**:
- `backend/app/services/precool/thermal_model.py` — 依赖 Story 29.2，调用 `ThermalModel.predict_temperature()`
- `backend/app/models/precool.py` — 依赖 Story 29.1，查询 `ThermalParameter` 表
- `backend/app/models/system_config.py` — 读取 SystemConfig 配置项

**测试文件**:
- `backend/tests/services/test_datacenter_shift_strategy_thm.py` — 新建，THM 方法单元测试

### 测试标准

**单元测试覆盖率** (Story 29.2 测试标准):
- 核心方法覆盖率 ≥ 90%
- 边界条件测试: headroom = 2.0°C（临界值）, ratio = 0.6（上限）, 温升速率 = 0（除零保护）, T_supply = T_max（THM 公式除零保护）
- 异常场景测试: 传感器离线、数据不足、异常值、异常点过滤、配置项缺失、配置项超出范围
- 模式切换测试: RC 未校准 → THM, RC 已校准 → TCL
- 线性回归准确性测试: 给定已知斜率的数据，验证计算结果误差 < 5%

**性能要求** (Story 29.2 性能标准):
- 单区计算耗时 < 300ms（考虑 5 个数据源查询 + 线性回归计算，比初始估计 200ms 更现实）
- 温升速率计算耗时 < 150ms（查询 1 小时数据 + 异常点过滤 + 线性回归）

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
- [Source: _bmad-output/planning-artifacts/epics.md#Story 29.3 - 温度裕度法安全兜底]
- [Source: backend/app/services/datacenter_shift_strategy.py - 现有温度查询链路]
- [Source: backend/app/services/precool/thermal_model.py - ThermalModel 类]
- [Source: backend/app/models/precool.py - ThermalParameter 表]
- [Source: backend/app/models/system_config.py - SystemConfig 表]

## 第一轮对抗性审查修复记录

修复了以下 14 个问题：

1. ✅ **温升速率计算逻辑明确化** - 改为使用手动实现的最小二乘线性回归计算斜率，不依赖 numpy/scipy
2. ✅ **热缓冲时间除零保护** - 当温升速率 ≤ 0 时，热缓冲时间设为无穷大，跳过热缓冲时间校验
3. ✅ **T_supply 数据源明确化** - 通过 CoolingZone → CoolingZoneUnit → CoolingUnit → Point → PointHistory 获取所有有数据的 Unit 的平均值
4. ✅ **SQLAlchemy 2.0 语法修复** - 改为 `(await session.execute(...)).scalar_one_or_none()`
5. ✅ **配置项 value 类型明确化** - value 存储为浮点数字符串（如 `"0.8"`），读取后用 `float()` 解析
6. ✅ **数据不足阈值修正** - 改为 < 12 个数据点（1 小时），而不是 < 6 个（30 分钟）
7. ✅ **异常值过滤阈值修正** - 改为 > 2°C/h 或 < -1°C/h（参考 ASHRAE TC9.9 数据中心温度变化率 < 1°C/h）
8. ✅ **返回值字段精简** - 移除冗余字段（safety_factor, absolute_max_ratio 等），仅保留 zone_id, shiftable_ratio, method, headroom_celsius, T_current_max
9. ✅ **依赖检查补充** - 新增 SystemConfig 表和 CoolingZone 相关表的检查
10. ✅ **Tasks 补充 T_supply 实现** - 新增 `_get_zone_supply_temperature()` 辅助方法
11. ✅ **Tasks 补充除零保护** - 在温升速率计算中新增除零保护逻辑
12. ✅ **架构文档引用修正** - 移除虚构的 Section 21 引用，改为引用实际存在的文档
13. ✅ **性能要求修正** - THM 方法改为 < 300ms（考虑 5 个数据源查询 + 线性回归计算）
14. ✅ **方法命名明确化** - 新增 `calculate_shiftable_power_for_zone()` 公共方法作为入口，避免与现有 `calculate_shift_recommendation()` 冲突

## 第二轮对抗性审查修复记录

修复了以下 14 个问题：

1. ✅ **线性回归实现方案明确化** - 手动实现最小二乘线性回归，不依赖 numpy/scipy，避免新增依赖
2. ✅ **T_supply 平均值计算逻辑明确化** - 对所有有数据的 Unit 求平均值，所有 Unit 都无数据才使用固定值 12°C
3. ✅ **THM 公式除零保护** - 当 T_max - T_supply ≤ 0 时，ratio = 0 并返回错误 `invalid_supply_temp`
4. ✅ **TCL 模式实现逻辑明确化** - 调用 ThermalModel 预测 1 小时后温度，如果预测温度 < T_max - 2°C，ratio = 0.4，否则 ratio = 0
5. ✅ **配置项范围校验逻辑明确化** - 超出范围时使用边界值（如 0.95 → 0.9），而不是默认值
6. ✅ **异常点过滤** - 回归前先过滤温度突变点（相邻点变化 > 3°C），避免传感器故障影响回归结果
7. ✅ **返回值补充 T_current_max** - 新增 T_current_max 字段，用于前端告警展示
8. ✅ **依赖检查时机明确化** - 在模块导入时尝试导入，导入失败时记录错误日志，在方法调用时检查依赖
9. ✅ **Tasks 补充线性回归实现** - 新增"手动实现最小二乘线性回归"子任务
10. ✅ **Tasks 补充异常点过滤** - 新增"实现异常点过滤（相邻点变化 > 3°C）"子任务
11. ✅ **性能要求修正** - 改为 < 300ms（考虑 5 个数据源查询 + 线性回归计算，更现实）
12. ✅ **测试标准补充线性回归测试** - 新增"测试线性回归计算准确性"测试用例
13. ✅ **TCL 模式返回值格式统一** - 明确 `_calculate_shiftable_power_tcl()` 需要转换为统一返回格式
14. ✅ **配置项初始化逻辑** - 在 `app/main.py` 的 `lifespan` 事件中自动创建缺失的配置项

## Dev Agent Record

### Agent Model Used

(待填写)

### Debug Log References

(待填写)

### Completion Notes List

(待填写)

### File List

(待填写)
