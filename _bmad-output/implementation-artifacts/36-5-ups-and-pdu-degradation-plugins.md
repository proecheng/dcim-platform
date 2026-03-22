# Story 36.5: UPS 主机与 PDU 劣化分析插件

Status: in-progress

## Story

As a 运维工程师,
I want UPS 主机和 PDU 也有劣化趋势分析，与空调一起在仪表盘统一展示,
So that 所有关键设备类型都纳入预测性维护体系。

## Acceptance Criteria

1. **Given** UPS 主机有输入/输出电压历史数据 **When** 执行劣化分析 **Then** 输出 UPS 劣化评分（电压稳定性趋势、效率下降趋势、切换次数异常）
2. **Given** PDU 有负载率和电压历史数据 **When** 执行劣化分析 **Then** 输出 PDU 劣化评分（负载率高位趋势、谐波畸变率上升、温升异常）
3. **Given** 电池组已有 SOH 数据 **When** 劣化分析 **Then** BatteryDegradationPlugin 从 point_history 中读取 SOH 虚拟注入数据，不重复计算
4. **Given** 新插件注册 **When** 系统启动 **Then** DegradationAnalyzer 自动发现并加载 UPS/PDU/Battery 插件
5. **Given** 数据点位不足 **When** 仅有必需点位 **Then** data_sufficiency 正确标记为 partial/minimal

## Tasks / Subtasks

- [ ] Task 1: 共享工具提取 + config 更新
  - [ ] 1.1 提取 `_linear_regression_slope` 到 `base.py`，hvac_plugin 保留 re-export
  - [ ] 1.2 提取 `_find_point_data` 到 `DegradationPlugin` 基类方法
  - [ ] 1.3 新增 `UPS_CONFIG`/`PDU_CONFIG`/`BATTERY_CONFIG` 到 `config.py`
  - [ ] 1.4 新增 `"BATTERY": "battery"` 到 `DEVICE_TYPE_MAP`，移除 UPS/PDU 的 TODO 注释
- [ ] Task 2: UPS 劣化分析插件 (AC: #1, #4, #5)
  - [ ] 2.1 新建 `ups_plugin.py` — UPSDegradationPlugin（电压稳定性+效率+切换次数+温度）
  - [ ] 2.2 电压分段标准差：window/7段，最少3段才做趋势
- [ ] Task 3: PDU 劣化分析插件 (AC: #2, #4, #5)
  - [ ] 3.1 新建 `pdu_plugin.py` — PDUDegradationPlugin（负载率+电压稳定性+谐波+温升）
  - [ ] 3.2 零负载保护：load_percentage 均值 < 1% 时标记 partial，不评分
  - [ ] 3.3 PDU 电压阈值独立：voltage_std_threshold = 0.5V（区别于 UPS 的 2.0V）
- [ ] Task 4: Battery 劣化分析插件 (AC: #3, #4, #5)
  - [ ] 4.1 Analyzer `_fetch_point_history` 对 battery 插件注入 BatterySOHRecord 虚拟数据
  - [ ] 4.2 新建 `battery_plugin.py` — BatteryDegradationPlugin（SOH映射+内阻趋势+温度）
  - [ ] 4.3 SOH 为空时返回 partial/minimal，不报错
- [ ] Task 5: 插件注册 + 导入 (AC: #4)
  - [ ] 5.1 更新 `__init__.py` 导入 ups/pdu/battery 插件
- [ ] Task 6: 测试 (AC: #1-#5)
  - [ ] 6.1 UPS 插件测试（full/partial/minimal + 各指标）
  - [ ] 6.2 PDU 插件测试（full/partial/minimal + 零负载保护）
  - [ ] 6.3 Battery 插件测试（SOH 虚拟数据 + 内阻趋势 + 无 SOH 降级）
  - [ ] 6.4 插件注册表验证（ups/pdu/battery 均已注册）
  - [ ] 6.5 Analyzer 集成测试（UPS/PDU/BATTERY 设备自动路由到正确插件）

## Dev Notes

### 关键设计决策

**1. Battery SOH 数据注入方式（R1+R2 审查修正）：**

不修改 DegradationPlugin ABC 签名。改为在 `DegradationAnalyzer._fetch_point_history()` 中，当 `plugin_key == "battery"` 时，额外查询 `BatterySOHRecord` 表，将 SOH 数据作为虚拟 point_history 条目注入：

```python
# 在 analyzer.py _fetch_point_history 后追加
if plugin_key == "battery":
    soh_records = await db.execute(
        select(BatterySOHRecord)
        .where(BatterySOHRecord.device_id == device_id)
        .order_by(BatterySOHRecord.calculated_at)
    )
    for r in soh_records.scalars():
        day_offset = (r.calculated_at - cutoff).total_seconds() / 86400
        point_history.setdefault("soh_percent", []).append((round(day_offset, 2), r.soh_percent))
```

Battery 插件 analyze() 仅使用标准 point_history dict，与其他插件完全一致。

**2. UPS 插件（ups_plugin.py）：**

```python
UPS_CONFIG = {
    "required_point_suffixes": ["input_voltage", "output_voltage"],
    "optional_point_suffixes": ["efficiency", "transfer_count", "temperature"],
    "weights": {
        "voltage_stability": 0.35,
        "efficiency_trend": 0.25,
        "transfer_count": 0.20,
        "temperature": 0.20,
    },
    "voltage_std_threshold": 2.0,
    "efficiency_slope_threshold_per_month": -0.5,
    "transfer_count_threshold": 5,
    "voltage_segment_count": 7,       # 分段数
    "min_segments_for_trend": 3,      # 最少段数才做趋势
}
```

电压稳定性分析：将 window 数据分为 7 段，每段计算标准差，检查标准差是否有增大趋势（线性回归）。

切换次数：统计 transfer_count 数据中非零值（脉冲型）或差值增量（累计型），>5次/月为劣化。

**3. PDU 插件（pdu_plugin.py）：**

```python
PDU_CONFIG = {
    "required_point_suffixes": ["load_percentage", "voltage"],
    "optional_point_suffixes": ["thd", "temperature_rise"],
    "weights": {
        "load_trend": 0.35,
        "voltage_stability": 0.25,
        "thd_trend": 0.20,
        "temperature_rise": 0.20,
    },
    "load_high_threshold": 80.0,
    "thd_slope_threshold_per_month": 0.5,
    "voltage_std_threshold": 0.5,     # PDU 电压阈值独立（低于 UPS 的 2.0V）
}
```

零负载保护：load_percentage 均值 < 1% 时不评分负载率，标记 data_sufficiency = partial。

**4. Battery 插件（battery_plugin.py）：**

```python
BATTERY_CONFIG = {
    "required_point_suffixes": ["internal_resistance"],
    "optional_point_suffixes": ["cycle_count", "temperature"],
    "virtual_point_suffixes": ["soh_percent"],  # 由 Analyzer 注入
    "weights": {
        "soh": 0.50,
        "resistance_trend": 0.30,
        "temperature": 0.20,
    },
}
```

SOH 评分映射：soh_percent 直接映射为分数（100% → 100分, 80% → 80分, 60% → 40分非线性）。
无 SOH 数据时：降级为 partial（有内阻数据）或 minimal（无数据）。

**5. 共享工具提取：**

- `_linear_regression_slope` → `base.py` 模块级函数
- `_find_point_data` → `DegradationPlugin` 基类方法（非抽象）
- `hvac_plugin.py` 保留 `from .base import _linear_regression_slope` re-export（兼容现有测试导入）

**6. _determine_sufficiency 不提取**：各插件各自实现（HVAC 检查回风温度，UPS 检查电压数据，PDU 检查负载率，Battery 检查 SOH），逻辑差异大。

### 现有代码关键引用

| 文件 | 说明 | 关键点 |
|------|------|--------|
| `backend/app/services/predictive_maintenance/base.py` | DegradationPlugin ABC + DegradationResult | analyze() 签名不含 db |
| `backend/app/services/predictive_maintenance/registry.py` | 装饰器注册表 | @register_degradation_plugin("key") |
| `backend/app/services/predictive_maintenance/config.py` | DEVICE_TYPE_MAP + HVAC_CONFIG | UPS/PDU TODO 待移除 |
| `backend/app/services/predictive_maintenance/hvac_plugin.py` | HVAC 参考实现 | _linear_regression_slope, _find_point_data |
| `backend/app/services/predictive_maintenance/analyzer.py` | 调度器 | _fetch_point_history, analyze_device |
| `backend/app/services/predictive_maintenance/health_calculator.py` | 健康度计算器 | WEIGHT_CONFIG 已含 ups/pdu/battery |
| `backend/app/models/diagnosis.py:143-160` | BatterySOHRecord 表 | soh_percent, resistance_mohm, cycle_count |
| `backend/tests/services/test_degradation_plugin.py` | HVAC 插件测试参考 | 导入 _linear_regression_slope from hvac_plugin |

### Project Structure Notes

**新建文件：**
```
backend/app/services/predictive_maintenance/ups_plugin.py
backend/app/services/predictive_maintenance/pdu_plugin.py
backend/app/services/predictive_maintenance/battery_plugin.py
backend/tests/services/test_ups_pdu_battery_plugins.py
```

**修改文件：**
```
backend/app/services/predictive_maintenance/config.py          # UPS_CONFIG/PDU_CONFIG/BATTERY_CONFIG + BATTERY映射
backend/app/services/predictive_maintenance/__init__.py        # 导入新插件
backend/app/services/predictive_maintenance/base.py            # 提取共享工具方法
backend/app/services/predictive_maintenance/hvac_plugin.py     # 使用 base 共享方法
backend/app/services/predictive_maintenance/analyzer.py        # Battery SOH 注入
```

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Completion Notes List

- Battery SOH 数据通过 Analyzer 注入 point_history（不修改 ABC 签名）
- DEVICE_TYPE_MAP 新增 "BATTERY": "battery"
- _linear_regression_slope 提取到 base.py，hvac_plugin 保留 re-export 兼容
- _determine_sufficiency 各插件独立实现
- PDU 电压阈值 0.5V 独立于 UPS 的 2.0V
- PDU 零负载保护（均值 < 1%）
- UPS 电压分段策略（7段，最少3段趋势）
- Battery 无 SOH 时优雅降级

### File List

**新建：**
- `backend/app/services/predictive_maintenance/ups_plugin.py`
- `backend/app/services/predictive_maintenance/pdu_plugin.py`
- `backend/app/services/predictive_maintenance/battery_plugin.py`
- `backend/tests/services/test_ups_pdu_battery_plugins.py`

**修改：**
- `backend/app/services/predictive_maintenance/config.py`
- `backend/app/services/predictive_maintenance/__init__.py`
- `backend/app/services/predictive_maintenance/base.py`
- `backend/app/services/predictive_maintenance/hvac_plugin.py`
- `backend/app/services/predictive_maintenance/analyzer.py`
