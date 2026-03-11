# Story 30.1: ASHRAE 温度硬约束与功率限制

Status: done

## Story

As a 系统管理员,
I want 系统在所有制冷操作中强制执行 ASHRAE 温度限制和功率上限,
So that 设备始终在安全范围内运行。

## 依赖

- Epic 29（全部完成）— 热模型基础
  - Story 29.2（RC 模型）— done
  - Story 29.3（THM 兜底）— done
  - Story 29.7（动态制冷比例集成）— done

## Acceptance Criteria

1. Given 制冷调度或预冷操作正在执行
   When 温度或功率达到约束边界
   Then ASHRAE TC9.9 Class A1 硬约束 18°C ≤ T ≤ 27°C 始终生效
   - 进风温度超过 27°C 时，约束检查返回违规状态
   - 进风温度低于 18°C 时，约束检查返回违规状态

2. Given 制冷功率调整操作
   When 计算可转移功率
   Then 制冷功率上限约束 Q_cool ≤ 1.5 × Q_rated 强制执行
   - Q_rated 从 CoolingZone 关联的 CoolingUnit.cooling_capacity_kw 获取（求和所有关联 Unit）
   - 如 CoolingUnit 无数据，回退到 CoolingLinkageConfig.max_cooling_power
   - 超过上限时返回约束违规并记录日志
   - 注意：功率约束是"提议动作验证"，需传入 q_cool 参数，不在综合温度检查中调用

3. Given 温度历史数据可用
   When 计算温度变化速率
   Then 温变速率约束 |dT/dt| ≤ 5°C/hour 自动检测
   - 复用 `_calculate_temperature_rise_rate` 方法（基于最近 1 小时数据，最小二乘回归）
   - 超过速率限制时返回约束违规

4. Given 任一约束被违反
   When 约束检查引擎检测到违规
   Then 立即返回违规详情（约束类型、当前值、阈值、zone_id）并记录日志
   - 日志级别: WARNING（接近阈值）或 ERROR（超过阈值）
   - 每次违规生成结构化日志，包含时间戳和上下文

5. Given 系统管理员需要调整约束参数
   When 修改系统配置
   Then 约束参数可通过 SystemConfig 表修改（预留可配置性）
   - 温度上下限、功率倍数、速率阈值均可配置
   - 配置变更即时生效（下次检查时使用新值）

6. Given 已有 ASHRAE 常量定义
   When 实现约束检查引擎
   Then 约束默认值与 `datacenter_shift_strategy.py` 的 ASHRAE 常量保持一致
   - `DEFAULT_TEMP_MAX = 27.0`（对应 TEMP_RECOMMENDED_MAX）
   - `DEFAULT_TEMP_MIN = 18.0`（对应 TEMP_RECOMMENDED_MIN）
   - 因循环导入限制，constraints.py 独立定义默认值，运行时从 SystemConfig 读取覆盖
   - 温变速率检查通过 lazy import 复用 `_calculate_temperature_rise_rate` 方法

## Tasks / Subtasks

- [x] Task 1: 创建约束检查引擎 `constraints.py` (AC: #1, #2, #3)
  - [x] 1.1 定义 `ConstraintViolation` 数据类（约束类型枚举、当前值、阈值、zone_id、时间戳）
  - [x] 1.2 实现 `check_temperature_constraints(zone_id, session)` — ASHRAE 温度范围检查（查询最热机柜进风温度）
  - [x] 1.3 实现 `check_power_constraint(zone_id, q_cool, session)` — 功率上限检查（独立调用，不在综合检查中）
  - [x] 1.4 实现 `check_rate_of_change(zone_id, session)` — 温变速率检查（复用 `_calculate_temperature_rise_rate`）
  - [x] 1.5 实现 `check_all_constraints(zone_id, session)` — 综合检查入口（仅含温度+速率检查）
  - [x] 1.6 实现 `_load_constraint_config(session)` — 从 SystemConfig 读取可配置约束参数
  - [x] 1.7 实现 `_get_zone_rated_power(zone_id, session)` — 获取 zone 总额定功率
- [x] Task 2: 添加可配置约束参数到 SystemConfig (AC: #5)
  - [x] 2.1 在 `main.py` 初始化逻辑中添加约束相关默认配置项（参照 THM 配置初始化模式）
- [x] Task 3: 集成约束检查到现有链路 (AC: #4, #6)
  - [x] 3.1 在 `calculate_shiftable_power_for_zone` 中调用约束检查（预转移检查）
  - [x] 3.2 约束违规时返回 `{"error": "constraint_violated", ...}` 格式
  - [x] 3.3 添加结构化日志记录
- [x] Task 4: 编写单元测试 (AC: #1-#6)
  - [x] 4.1 温度约束测试（正常范围、超上限、超下限、边界值）
  - [x] 4.2 功率约束测试（正常、超限、Q_rated 获取失败回退）
  - [x] 4.3 温变速率测试（正常、超限、数据不足回退）
  - [x] 4.4 综合检查测试（多约束同时违反）
  - [x] 4.5 配置可修改性测试

## Dev Notes

### 架构约束

- **新建文件**: `backend/app/services/precool/constraints.py` — 约束检查引擎
- **修改文件**: `backend/app/services/datacenter_shift_strategy.py` — 在 `calculate_shiftable_power_for_zone` 中集成约束前置检查
- **修改文件**: `backend/app/main.py` — 添加约束配置项初始化
- **新建文件**: `backend/tests/services/precool/test_constraints.py` — 单元测试

### ASHRAE 常量复用

**关键**: 不要重复定义 ASHRAE 常量！复用 `datacenter_shift_strategy.py` 中已定义的：

```python
# datacenter_shift_strategy.py:49-73 已定义
TEMP_RECOMMENDED_MIN = 18.0      # 推荐最低温度
TEMP_RECOMMENDED_MAX = 27.0      # 推荐最高温度
TEMP_ALLOWABLE_MIN = 15.0        # 允许最低温度
TEMP_ALLOWABLE_MAX = 32.0        # 允许最高温度
TEMP_SAFETY_MARGIN = 2.0         # 安全裕度
SAFETY_FACTOR = 0.9              # 通用安全系数
```

**循环导入解决方案**: `constraints.py` 不能直接 import `datacenter_shift_strategy`（因为后者也需导入 `constraints`）。
有两种方案：
- **方案 A（推荐）**: 在 `constraints.py` 中直接定义默认值常量，同时从 SystemConfig 读取可配置值。ASHRAE 常量作为默认值硬编码，SystemConfig 值覆盖默认值。
- **方案 B**: 将常量抽取到共享模块（如 `precool/constants.py`）。但增加了文件数量，不推荐。

采用方案 A:
```python
# constraints.py — 默认值（与 datacenter_shift_strategy.py 保持一致）
DEFAULT_TEMP_MAX = 27.0   # ASHRAE TC9.9 Class A1 推荐上限
DEFAULT_TEMP_MIN = 18.0   # ASHRAE TC9.9 Class A1 推荐下限
DEFAULT_POWER_MULTIPLIER = 1.5
DEFAULT_RATE_LIMIT = 5.0  # °C/h

# 运行时从 SystemConfig 读取，若无记录则使用默认值
```

在 `datacenter_shift_strategy.py` 中集成时使用 **lazy import**:
```python
# 在 calculate_shiftable_power_for_zone 函数体内
from app.services.precool.constraints import check_all_constraints
```

### 约束检查引擎设计

```python
# constraints.py 核心结构

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class ConstraintType(str, Enum):
    TEMPERATURE_HIGH = "temperature_high"
    TEMPERATURE_LOW = "temperature_low"
    POWER_OVER_LIMIT = "power_over_limit"
    RATE_OF_CHANGE = "rate_of_change"

@dataclass
class ConstraintViolation:
    constraint_type: ConstraintType
    current_value: float
    threshold: float
    zone_id: int
    message: str
    severity: str  # "warning" | "error"

async def check_all_constraints(
    zone_id: int, session: AsyncSession
) -> List[ConstraintViolation]:
    """综合约束检查入口 — 仅含温度+速率检查（功率检查需单独调用）"""
    config = await _load_constraint_config(session)
    violations = []
    violations.extend(await check_temperature_constraints(zone_id, session, config))
    violations.extend(await check_rate_of_change(zone_id, session, config))
    return violations

async def check_power_constraint(
    zone_id: int, q_cool: float, session: AsyncSession
) -> Optional[ConstraintViolation]:
    """检查制冷功率是否超限（独立调用，需传入当前/提议的 q_cool 值）"""
    ...
```

### 温度数据获取路径

复用 Epic 29 已建立的温度数据链路：
- **进风温度**: `CoolingZoneCabinet → Cabinet → CabinetTemperatureSensor(inlet) → Point → PointHistory`
- 温度查询参照 `_calculate_shiftable_power_thm` 函数中的内联实现（datacenter_shift_strategy.py:955-967）
- 查询最近 5 分钟的 `func.max(PointHistory.value)`，通过 `CoolingZoneCabinet.cooling_zone_id` 过滤
- **注意**: CoolingZoneUnit 的 FK 字段是 `zone_id`（非 `cooling_zone_id`），而 CoolingZoneCabinet 的 FK 字段是 `cooling_zone_id`，注意区分

### 温变速率计算

**决策: 使用 lazy import 复用** `_calculate_temperature_rise_rate`（datacenter_shift_strategy.py:837-930）：
- 已实现最小二乘线性回归，返回 °C/h 速率
- 包含异常值过滤和数据不足保守估计（回退到 0.5°C/h）
- 在 `constraints.py` 中通过 lazy import 调用：`from app.services.datacenter_shift_strategy import _calculate_temperature_rise_rate`
- 注意：这不会触发循环导入，因为 `constraints.py` 只在函数调用时 import（而非模块加载时）

### 功率上限获取

Q_rated 获取路径：
- `CoolingZone → CoolingZoneUnit(zone_id) → CoolingUnit.cooling_capacity_kw`
- 对 zone 内所有 CoolingUnit 的 `cooling_capacity_kw` 求和得到总额定制冷功率
- 如果无 CoolingUnit 数据，回退到 `CoolingLinkageConfig.max_cooling_power`（默认 2000 kW）
- **字段名注意**: CoolingUnit 的字段是 `cooling_capacity_kw`（非 `rated_cooling_power`），CoolingZoneUnit 的 FK 是 `zone_id`（非 `cooling_zone_id`）

### SystemConfig 约束配置项

在 `main.py` 初始化中添加（参照 THM 配置项模式，行 222-244）。
**注意**: 这些 SystemConfig 值是运行时可调的，覆盖 `constraints.py` 中的默认常量。
`datacenter_shift_strategy.py` 中的 ASHRAE 常量（`TEMP_RECOMMENDED_MAX` 等）保持不变，仅用于 THM 计算。约束检查引擎统一从 SystemConfig 读取。

| 配置键 | 默认值 | 取值范围 | 用途 |
|--------|--------|---------|------|
| `constraint_temp_max` | 27.0 | 25.0-32.0 | ASHRAE 温度上限 |
| `constraint_temp_min` | 18.0 | 15.0-20.0 | ASHRAE 温度下限 |
| `constraint_power_multiplier` | 1.5 | 1.0-2.0 | 制冷功率倍数上限 |
| `constraint_rate_limit` | 5.0 | 3.0-10.0 | 温变速率限制 °C/h |

### 集成点

在 `calculate_shiftable_power_for_zone` 函数中，约束检查应在计算转移比例之前执行：

```python
async def calculate_shiftable_power_for_zone(zone_id, session):
    # 新增：前置约束检查
    from app.services.precool.constraints import check_all_constraints
    violations = await check_all_constraints(zone_id, session)
    if violations:
        error_violations = [v for v in violations if v.severity == "error"]
        if error_violations:
            return {
                "error": "constraint_violated",
                "zone_id": zone_id,
                "violations": [
                    {"type": v.constraint_type.value, "value": v.current_value,
                     "threshold": v.threshold, "message": v.message}
                    for v in error_violations
                ]
            }
    # warning 级别违规仅记录日志（不阻断），让调用方了解接近约束
    warning_violations = [v for v in violations if v.severity == "warning"]
    for w in warning_violations:
        logger.warning(f"Zone {zone_id} approaching constraint: {w.constraint_type.value} = {w.current_value} (threshold: {w.threshold})")
    # 原有逻辑继续...
```

### 测试模式

参照 `test_thermal_model_core.py` 和 `test_precool_integration.py` 的纯 mock 模式：
- Mock `AsyncSession` 和 ORM 查询
- Mock 温度查询结果和 `_calculate_temperature_rise_rate` 等方法
- 不依赖真实数据库

### 警告与接近阈值的分级

| 状态 | 温度条件 | severity |
|------|---------|----------|
| 正常 | T < 25°C (T_max - 2°C) | — |
| 接近约束 | 25°C ≤ T < 27°C | warning |
| 约束违反 | T ≥ 27°C | error |

对功率和速率同理：接近阈值 90% 为 warning，超过为 error。

### Project Structure Notes

- `backend/app/services/precool/` 目录已存在，包含 `thermal_model.py` 和 `accuracy_monitor.py`
- 新增 `constraints.py` 符合现有模块组织
- 测试文件放在 `backend/tests/services/precool/test_constraints.py`

### Lazy Import 注意事项

从 Epic 29 经验：如果 `constraints.py` 被 `datacenter_shift_strategy.py` 导入，注意避免循环依赖。如果存在循环导入，使用 lazy import（方法体内 import）并在测试中 mock 原始模块路径。

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic30-Story30.1] — AC 定义
- [Source: _bmad-output/planning-artifacts/architecture.md#Section21] — 约束条件体系（行 1999-2022）
- [Source: _bmad-output/planning-artifacts/architecture.md#Section21] — 7 项回退保护（行 2011-2022）
- [Source: backend/app/services/datacenter_shift_strategy.py:49-73] — ASHRAE 常量定义
- [Source: backend/app/services/datacenter_shift_strategy.py:782-835] — _get_zone_supply_temperature
- [Source: backend/app/services/datacenter_shift_strategy.py:837-930] — _calculate_temperature_rise_rate
- [Source: backend/app/services/datacenter_shift_strategy.py:679-722] — calculate_shiftable_power_for_zone
- [Source: docs/project-knowledge/thermal-config-reference.md] — 配置项参考手册
- [Source: _bmad-output/implementation-artifacts/29-7-replace-constraint-checker-fixed-cooling-ratio.md] — 前序 Story 模式参考
- [Source: _bmad-output/implementation-artifacts/epic-29-retrospective.md] — Epic 29 回顾经验

### Previous Story Intelligence

**从 Story 29.7 学到的关键经验：**
1. **Lazy import 模式**: 如果存在循环依赖，在方法体内 import，mock 时 target 原始模块路径
2. **Mock 模式**: 使用 `patch.object(instance, "method_name")` mock 内部方法，避免 mock SQLAlchemy session
3. **特性开关**: `precool_enabled` 控制是否启用动态计算，保持向后兼容
4. **错误处理**: 动态计算失败时返回 None，调用方回退到固定值

**从 Epic 29 回顾：**
- 测试覆盖要全面（核心算法 + 边界条件 + 集成）
- 数据质量检查前置
- 多层安全防线设计

## NFR 追溯

- **NFR-TCL-4**: 约束检查响应时间 — 内存中比较运算，< 100ms
- **FR-TCL-4**: ASHRAE 温度硬约束 (18-27°C)
- **FR-TCL-5**: 制冷功率上限 (Q_cool ≤ 1.5 × Q_rated)
- **FR-TCL-6**: 温变速率限制 (|dT/dt| ≤ 5°C/h)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Completion Notes List

- 约束检查引擎完整实现，包含温度/功率/速率三类检查
- 循环导入通过方案A解决（独立默认值 + SystemConfig覆盖 + lazy import）
- 33个单元测试全部通过
- 集成到 calculate_shiftable_power_for_zone 作为前置安全检查
- 代码审查修复：添加 _get_max_inlet_temperature 错误处理、移除未使用的 asdict 导入、check_all_constraints 独立错误隔离

### Change Log

- 2026-03-11: 实施完成，33测试通过
- 2026-03-11: 代码审查修复 3 HIGH + 2 MEDIUM 问题

### File List

- `backend/app/services/precool/constraints.py` — 新建，约束检查引擎
- `backend/tests/services/precool/test_constraints.py` — 新建，33个单元测试
- `backend/app/services/datacenter_shift_strategy.py` — 修改，集成约束前置检查（行 709-730）
- `backend/app/main.py` — 修改，添加约束配置项初始化（行 248-279）
