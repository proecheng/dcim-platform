# 热模型配置项参考手册

> Epic 29 (热模型与温度预测) 涉及的所有配置项汇总

## 1. SystemConfig 表配置项 (THM 相关)

通过 `GET/PUT /api/v1/system/config` 管理，应用启动时自动初始化默认值。

| 配置键 | 默认值 | 取值范围 | 用途 |
|--------|--------|---------|------|
| `thm_safety_factor` | 0.8 | 0.7-0.9 | THM 模式安全系数，限制制冷转移比例 |
| `thm_absolute_max_ratio` | 0.6 | 0.4-0.8 | THM 模式绝对最大转移比例 |
| `thm_min_headroom_celsius` | 2.0 | 1.0-3.0 | 温度安全裕度红线（低于此值禁止转移） |

**THM 公式:** `ratio = (T_max - T_current_max) / (T_max - T_supply) × safety_factor`

**初始化位置:** `backend/app/main.py:222-244`

---

## 2. CoolingZone 表扩展字段 (热参数)

位于 `backend/app/models/topology_config.py`，存储制冷区域物理参数。

| 字段名 | 类型 | 默认值 | 取值范围 | 用途 |
|--------|------|--------|---------|------|
| `area_m2` | Float | NULL | > 0 | 冷通道面积（m²） |
| `height_m` | Float | 3.0 | > 0 | 冷通道层高（m） |
| `thermal_R` | Float | NULL | 0.01-0.05 °C/kW | 热阻标定值 |
| `thermal_C` | Float | NULL | 0.04 kWh/°C/m² (参考) | 热容标定值（总热容） |
| `bypass_beta` | Float | 0.1 | 0.0-0.3 | 气流短路系数 |
| `r_calibrated_at` | DateTime | NULL | - | R/C 最近标定时间 |

**注意:** `thermal_R` 和 `thermal_C` 为 NULL 表示未标定，系统自动使用 THM 模式。

---

## 3. ThermalParameter 表 (热参数版本管理)

位于 `backend/app/models/thermal.py`，存储 R/C 参数历史版本。

| 字段名 | 类型 | 默认值 | 用途 |
|--------|------|--------|------|
| `thermal_R` | Float | NULL | 热阻标定值（°C/kW） |
| `thermal_C` | Float | NULL | 热容标定值（kWh/°C） |
| `fitting_r_squared` | Float | NULL | 拟合优度 R² |
| `fitting_method` | String | "manual" | 标定方法: auto_fit/manual/default |
| `sample_count` | Integer | NULL | 标定样本数 |
| `is_active` | Boolean | True | 是否为当前生效参数 |

**唯一约束:** 每个 zone 只能有一个 `is_active=True` 的记录。

---

## 4. CoolingLinkageConfig 表 (预冷控制)

位于 `backend/app/models/load_shift.py:374-421`，控制预冷功能和制冷联动。

### 预冷相关字段

| 字段名 | 类型 | 默认值 | 用途 |
|--------|------|--------|------|
| `precool_enabled` | Boolean | False | 预冷功能总开关（特性开关） |
| `precool_target_temp` | Float | NULL | 预冷目标温度（°C） |

### 制冷联动参数

| 字段名 | 默认值 | 取值范围 | 用途 |
|--------|--------|---------|------|
| `lag_time_minutes` | 20 | > 0 | 制冷滞后时间（分钟） |
| `target_cop` | 3.0 | 2.0-4.5 | 目标 COP |
| `target_supply_temp` | 10.0 | 5.0-15.0 | 供水温度目标值（°C） |
| `target_return_temp` | 15.0 | 10.0-20.0 | 回水温度目标值（°C） |
| `min_cooling_power` | 100.0 | > 0 | 最小制冷功率（kW） |
| `max_cooling_power` | 2000.0 | > 0 | 最大制冷功率（kW） |

---

## 5. thermal_model.py 核心常量

位于 `backend/app/services/precool/thermal_model.py`。

| 常量 | 值 | 用途 |
|------|------|------|
| `dt` | 5/60 小时 (5 分钟) | Euler 离散化时间步长 |
| `steps` | hours × 12 | 预测步数 |
| 默认 `beta` | 0.1 | bypass_beta 为 NULL 时的默认值 |
| 默认 `COP` | 3.5 | 室外温度不可用时的默认 COP |
| 稳定性条件 | dt < 2RC | Euler 显式格式稳定约束 |
| 温度有效范围 | [0, 50] °C | 预测越界时终止 |

### COP 季节修正

| 室外温度 | COP | 季节 |
|---------|-----|------|
| ≥ 30°C | 2.8 | 夏季 |
| 15-30°C | 3.5 | 过渡季 |
| < 15°C | 4.0 | 冬季 |
| 不可用 | 3.5 | 默认 |

---

## 6. accuracy_monitor.py 精度监控常量

位于 `backend/app/services/precool/accuracy_monitor.py`。

### MAE 精度阈值

| 常量 | 值 | 用途 |
|------|------|------|
| `MAE_EXCELLENT_1H` | 1.0 °C | 1h 预测优秀标准 |
| `MAE_ACCEPTABLE_3H` | 2.0 °C | 3h 预测合格标准 |
| `MAX_DEVIATION_SAFE` | 3.0 °C | 最大安全偏差 |

### 自动回退配置

| 常量 | 值 | 用途 |
|------|------|------|
| `CONSECUTIVE_ERROR_THRESHOLD` | 2.0 °C | 单次误差阈值 |
| `CONSECUTIVE_ERROR_COUNT` | 3 | 连续超阈值次数触发回退 |
| `SENTINEL_VALUE` | -999.0 | 数据不可用哨兵值 |
| `BACKFILL_BATCH_SIZE` | 100 | 每次回填最大处理条数 |
| `BACKFILL_TIMEOUT_HOURS` | 1 | 超时标记哨兵值（小时） |

### 每日精度退化警告

| 常量 | 值 | 触发条件 |
|------|------|---------|
| `DAILY_MAE_1H_WARNING` | 1.5 °C | mae_1h > 1.5 时记录 error 日志 |
| `DAILY_MAE_3H_WARNING` | 3.0 °C | mae_3h > 3.0 时记录 error 日志 |

---

## 7. datacenter_shift_strategy.py 温度约束常量

位于 `backend/app/services/datacenter_shift_strategy.py:49-73`。

| 常量 | 值 | 用途 |
|------|------|------|
| `TEMP_RECOMMENDED_MIN` | 18.0 °C | ASHRAE 推荐下限 |
| `TEMP_RECOMMENDED_MAX` | 27.0 °C | ASHRAE 推荐上限 (THM T_max) |
| `TEMP_ALLOWABLE_MIN` | 15.0 °C | ASHRAE 允许下限 |
| `TEMP_ALLOWABLE_MAX` | 32.0 °C | ASHRAE 允许上限 |
| `TEMP_SAFETY_MARGIN` | 2.0 °C | 温度安全裕度 |
| `SAFETY_FACTOR` | 0.9 | 通用安全系数 |

---

## 8. 配置优先级与覆盖关系

```
constraint_checker.py
└── _get_dynamic_cooling_ratio(zone_id)
    ├── 检查 CoolingLinkageConfig.precool_enabled (特性开关)
    │   └── False → 回退固定 0.4
    └── True → calculate_shiftable_power_for_zone(zone_id)
        ├── 检查 ThermalParameter.is_active
        │   └── 有活跃参数 → TCL 模式 (RC 模型)
        └── 无活跃参数 → THM 模式 (温度裕度法)
            ├── SystemConfig.thm_safety_factor
            ├── SystemConfig.thm_absolute_max_ratio
            └── SystemConfig.thm_min_headroom_celsius
```

---

*最后更新: 2026-03-11*
*关联 Epic: Epic 29 (热模型与温度预测)*
