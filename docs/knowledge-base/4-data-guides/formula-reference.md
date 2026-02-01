# 计算公式大全

> DCIM系统核心计算公式及数据来源说明

---

## 目录

1. [能效指标](#1-能效指标)
2. [节能收益](#2-节能收益)
3. [负荷转移](#3-负荷转移)
4. [效果评估](#4-效果评估)
5. [RL奖励函数](#5-rl奖励函数)

---

## 1. 能效指标

### 1.1 PUE (Power Usage Effectiveness)

**定义**: 数据中心能源效率核心指标

```
PUE = 数据中心总能耗 / IT设备能耗

     Total_Energy
   = ────────────────
     IT_Energy
```

**数据来源**:
| 变量 | 来源表 | 字段 | 单位 |
|------|--------|------|------|
| Total_Energy | `energy_daily` | `total_energy` | kWh |
| IT_Energy | `energy_daily` | `it_energy` | kWh |

**参考值**:
| PUE范围 | 评级 | 说明 |
|---------|------|------|
| < 1.4 | 优秀 | 世界领先水平 |
| 1.4 - 1.6 | 良好 | 国内先进水平 |
| 1.6 - 1.8 | 一般 | 行业平均水平 |
| > 1.8 | 较差 | 需要优化 |

### 1.2 CLF (Cooling Load Factor)

**定义**: 制冷负荷因子

```
CLF = 制冷系统能耗 / IT设备能耗

     Cooling_Energy
   = ────────────────
     IT_Energy
```

**优化目标**: CLF < 0.4 (即制冷能耗占IT负载的40%以下)

### 1.3 负载率

**定义**: 设备实际负载与额定容量的比值

```
负载率 = 实际功率 / 额定功率 × 100%

        P_actual
      = ───────── × 100%
        P_rated
```

**数据来源**:
| 变量 | 来源表 | 字段 |
|------|--------|------|
| P_actual | `energy_hourly` | `avg_power` |
| P_rated | `power_devices` | `rated_power` |

---

## 2. 节能收益

### 2.1 年度节能金额

**基础公式**:

```
年度节能金额 = 日均节能量 × 平均电价 × 365

             = ΔP × H × Price_avg × 365
```

**详细计算**:

```
ΔP = P_before - P_after      # 功率差 (kW)
H = 运行小时数/天             # 通常取 8-24 小时
Price_avg = 加权平均电价      # 元/kWh

示例:
ΔP = 50 kW
H = 12 小时/天
Price_avg = 0.65 元/kWh

年度节能 = 50 × 12 × 0.65 × 365 = 142,350 元 ≈ 14.2 万元
```

### 2.2 峰谷转移节省

**定义**: 通过将高价时段负荷转移到低价时段获得的成本节省

```
日节省 = 转移功率 × 转移时长 × 电价差

       = P_shift × T_shift × (Price_peak - Price_valley)
```

**数据来源**:
| 变量 | 来源 | 说明 |
|------|------|------|
| P_shift | `device_shift_configs.shiftable_power_ratio × rated_power` | 可转移功率 |
| T_shift | 用户配置 | 通常 4-8 小时 |
| Price_peak | 电价配置 | 峰时电价 (约 1.0-1.4 元) |
| Price_valley | 电价配置 | 谷时电价 (约 0.2-0.35 元) |

**前端计算示例** (ShiftPlanBuilder.vue):

```javascript
function calculateRuleDailySaving(rule) {
  const priceDiff = periodPrices[rule.sourcePeriod] - periodPrices[rule.targetPeriod];
  return rule.power * rule.hours * priceDiff;
}

// 年节省 = 日节省 × 工作日
const yearlySaving = dailySaving * 250;
```

### 2.3 需量优化节省

**定义**: 通过削减最大需量避免超容罚款或降低基本电费

```
需量节省 = 削减需量 × 需量单价 × 12个月

         = ΔD × Price_demand × 12
```

**参考值**:
- 需量单价: 约 20-40 元/kW·月
- 削减目标: 通常控制在合同容量的 90% 以内

---

## 3. 负荷转移

### 3.1 可转移功率 (shiftable_power)

**核心公式**:

```
可转移功率 = 额定功率 × 可转移比例

           = rated_power × shiftable_power_ratio
```

**数据来源**:
| 变量 | 来源表 | 字段 |
|------|--------|------|
| rated_power | `power_devices` | `rated_power` |
| shiftable_power_ratio | `device_shift_configs` | `shiftable_power_ratio` |

**设备类型默认比例**:
| 设备类型 | ratio | 说明 |
|----------|-------|------|
| PUMP | 0.40 | 水泵可变频调速 |
| AC | 0.30 | 空调有舒适度约束 |
| HVAC | 0.35 | 暖通柔性中等 |
| LIGHTING | 0.50 | 照明可分区调光 |
| CHILLER | 0.25 | 冷水机有温度约束 |
| UPS | 0.00 | 关键负荷不可转移 |
| IT_SERVER | 0.00 | IT设备不可转移 |

### 3.2 基于历史数据的ratio推荐算法

**推荐公式**:

```
recommended_ratio = min(
    1 - (min_power / rated_power),           # 最低功率约束
    (max_power - avg_power) / rated_power,   # 负荷波动空间
    peak_ratio × flexibility_factor,          # 峰时可转移比例
    type_max_ratio                            # 设备类型上限
) × safety_factor
```

**参数说明**:
| 参数 | 来源 | 说明 |
|------|------|------|
| min_power | `energy_hourly` 30天最小值 | 设备最低运行功率 |
| max_power | `energy_hourly` 30天最大值 | 设备最大功率 |
| avg_power | `energy_hourly` 30天平均值 | 设备平均功率 |
| peak_ratio | `energy_daily` 计算 | 峰时用电占比 |
| flexibility_factor | 按设备类型 | 0.4-0.8 |
| safety_factor | 固定值 | 0.85 |

---

## 4. 效果评估

### 4.1 效果达成率 (专利S4d)

**公式**:

```
效果达成率 = 实际节能收益 / 预期节能收益 × 100%

            Actual_Saving
          = ───────────────── × 100%
            Expected_Saving
```

**计算步骤**:

```python
# 1. 获取预期收益 (按比例折算)
expected_annual = proposal.total_benefit * 10000  # 万元→元
expected_period = expected_annual * days / 365

# 2. 计算实际收益
actual_cost = sum(measure.actual_cost_saved for measure in measures)

# 3. 计算达成率
achievement_rate = (actual_cost / expected_period) * 100
```

### 4.2 实际节能量计算 (专利S4c)

**公式**:

```
实际节能量 = Σ(基准功率 - 执行后功率) × 监测间隔

           = Σ(P_baseline - P_current) × Δt
```

**数据来源**:
| 变量 | 来源表 | 字段 |
|------|--------|------|
| P_baseline | `measure_baseline` | `power_avg` |
| P_current | `monitoring_record` | `power_current` |
| Δt | 固定值 | 0.25 小时 (15分钟间隔) |

---

## 5. RL奖励函数

### 5.1 基础奖励 (专利S5)

**公式**:

```
R = 达成率 - λ1 × 舒适度违规 - λ2 × 安全违规

  = achievement_rate - λ1 × comfort_violation - λ2 × safety_violation
```

**参数说明**:
| 参数 | 取值范围 | 默认值 |
|------|----------|--------|
| λ1 (舒适度惩罚系数) | 0.1 - 0.3 | 0.2 |
| λ2 (安全惩罚系数) | 0.3 - 0.5 | 0.4 |
| comfort_violation | 0 - 1 | 温度偏差/阈值 |
| safety_violation | 0 - 1 | 告警次数/阈值 |

### 5.2 探索率衰减

**公式**:

```
ε(t) = max(ε_min, ε_initial × decay^t)
```

**参数**:
| 参数 | 值 | 说明 |
|------|-----|------|
| ε_initial | 0.3 | 初始探索率 |
| ε_min | 0.05 | 最小探索率 |
| decay | 0.995 | 衰减系数 |

---

## 快速参考卡片

```
┌─────────────────────────────────────────────────────────────┐
│                    常用公式速查                               │
├─────────────────────────────────────────────────────────────┤
│ PUE = Total_Energy / IT_Energy                              │
│                                                             │
│ 可转移功率 = rated_power × shiftable_power_ratio            │
│                                                             │
│ 日节省 = P_shift × T_shift × (Price_peak - Price_valley)    │
│                                                             │
│ 年节省 = 日节省 × 工作日数 (通常250天)                        │
│                                                             │
│ 达成率 = 实际节能 / 预期节能 × 100%                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 相关文档

- [数据字典](./data-dictionary.md)
- [API调用示例](./api-cookbook.md)
- [节能方案流程](../3-workflows/energy-saving-flow.md)
