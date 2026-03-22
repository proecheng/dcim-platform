# Story 36.2: DeviceHealthScore 增强与加权合并

Status: ready-for-dev

## Story

As a 运维工程师,
I want 设备健康度评分综合考虑劣化趋势、告警频次和维保记录，并按设备类型使用不同权重,
So that 健康度评分更准确地反映设备实际状态。

## Acceptance Criteria

1. **Given** 空调设备有劣化分析结果 **When** 计算健康度评分 **Then** 使用 HVAC 权重（劣化40%+告警30%+维保30%）加权合并
2. **Given** UPS 电池有 SOH 数据 **When** 计算健康度评分 **Then** 使用电池权重（SOH 50%+告警20%+维保30%），兼容现有 battery_soh_service 的调用
3. **Given** 数据充分度="minimal" **When** 计算健康度评分 **Then** 劣化因子权重降为0，仅用告警+维保评分（各50%）
4. **Given** 管理员修改权重配置 **When** 下次计算执行 **Then** 使用新权重
5. **Given** 评分≤40（预警/危险） **When** 健康度计算完成 **Then** 在日志中标记，供 Story 36.3 维护建议引擎消费

## Tasks / Subtasks

- [ ] Task 1: DeviceHealthScore 表扩展 (AC: #1, #2, #3)
  - [ ] 1.1 在 `backend/app/models/report.py` 中为 DeviceHealthScore 添加 `score_factors`(JSON)、`data_sufficiency`(String)、`degradation_score`(Float) 字段
  - [ ] 1.2 新建 Alembic 迁移脚本
- [ ] Task 2: DeviceHealthScoreCalculator 服务 (AC: #1, #2, #3, #4)
  - [ ] 2.1 新建 `backend/app/services/predictive_maintenance/health_calculator.py` — DeviceHealthScoreCalculator 类
  - [ ] 2.2 `_calc_alarm_score()` — 近30天告警频次评分（Alarm 表 JOIN Point 表关联 device_id）
  - [ ] 2.3 `_calc_maintenance_score()` — 最后维保时间评分（WorkOrder 表 status=WorkOrderStatus.completed + device_id 关联）
  - [ ] 2.4 加权合并逻辑 — 按 WEIGHT_CONFIG + data_sufficiency 降级
  - [ ] 2.5 `_load_weight_config()` — 从 SystemConfig 读取动态权重，fallback 到默认值
  - [ ] 2.6 `_score_to_level()` — 评分→健康等级映射（>=80 健康, >=60 关注, >=40 预警, <40 危险）
  - [ ] 2.7 `calculate_all_health_scores()` — 全量设备批量计算
- [ ] Task 3: 修复 battery_soh_service 技术债务 (AC: #2)
  - [ ] 3.1 重写 `update_device_health_score()` — 改为调用 DeviceHealthScoreCalculator，构造 DegradationResult(device_id=device_id, score=soh_percent, confidence=0.8, available_points=1, total_points=1, data_sufficiency="partial") 传入
- [ ] Task 4: 定时任务注册 (AC: #1-#5)
  - [ ] 4.1 在 `main.py` 中注册每日凌晨 02:07 执行 calculate_all_health_scores（APScheduler cron + fallback）
- [ ] Task 5: 测试 (AC: #1-#5)
  - [ ] 5.1 HVAC 权重加权合并测试 — 劣化40%+告警30%+维保30%
  - [ ] 5.2 UPS/Battery 权重测试 — SOH 50%+告警20%+维保30%
  - [ ] 5.3 minimal data_sufficiency 降级测试 — 劣化权重归零
  - [ ] 5.4 动态权重配置测试 — SystemConfig 覆盖默认值
  - [ ] 5.5 告警评分计算测试 — 0~>20 条告警映射到 100~10 分
  - [ ] 5.6 维保评分计算测试 — 距最后维保天数映射到评分
  - [ ] 5.7 calculate_all_health_scores 批量测试 — 多设备类型混合
  - [ ] 5.8 battery_soh_service 兼容测试 — 调用 update_device_health_score 正确写入
  - [ ] 5.9 score_to_level 映射测试 — 边界值验证
  - [ ] 5.10 评分≤40 日志标记测试

## Dev Notes

### 关键设计决策

**1. DeviceHealthScore 表扩展（3个新字段）：**
```python
# backend/app/models/report.py
class DeviceHealthScore(Base):
    # ... 现有字段 ...
    score_factors = Column(Text, comment="评分因子详情(JSON)")      # JSON 存储
    data_sufficiency = Column(String(20), default="minimal", comment="数据充分度: full/partial/minimal")
    degradation_score = Column(Float, comment="劣化趋势评分 0-100")
```
注意：使用 `Text` 存储 JSON（SQLite 兼容），在代码层用 `json.loads/dumps` 处理。

**2. DeviceHealthScoreCalculator 加权合并逻辑：**
```python
WEIGHT_CONFIG = {
    "ups":     {"degradation": 0.4, "alarm": 0.3, "maintenance": 0.3},
    "battery": {"degradation": 0.5, "alarm": 0.2, "maintenance": 0.3},
    "hvac":    {"degradation": 0.4, "alarm": 0.3, "maintenance": 0.3},
    "pdu":     {"degradation": 0.35, "alarm": 0.35, "maintenance": 0.3},
}

# data_sufficiency == "minimal" 时降级
MINIMAL_WEIGHTS = {"degradation": 0, "alarm": 0.5, "maintenance": 0.5}
```

**3. 告警评分计算规则（近30天告警频次）：**
| 告警数 | 评分 |
|--------|------|
| 0      | 100  |
| 1-2    | 85   |
| 3-5    | 70   |
| 6-10   | 50   |
| 11-20  | 30   |
| >20    | 10   |

**查询链路：** Alarm 表无 device_id，需通过 `Alarm.point_id → Point.device_id` 关联。对于 datasource 级告警（point_id=NULL），通过 `Alarm.source = 'datasource:{ds_id}'` + DataSource 关联 Device 查询。本 Story 简化为仅统计有 point_id 的告警。

**4. 维保评分计算规则（距最后维保天数）：**
| 距最后维保天数 | 评分 |
|---------------|------|
| ≤30           | 100  |
| 31-90         | 85   |
| 91-180        | 70   |
| 181-365       | 50   |
| >365          | 30   |
| 无维保记录    | 50   |

**查询链路：** WorkOrder 表有 `device_id` 字段（operation.py:88），查询 `status=WorkOrderStatus.completed`（枚举值为中文"已完成"，必须用枚举而非字符串）最新工单的 `completed_at`。如果 WorkOrder 无数据，查询 MaintenanceRecord 表（通过 Asset.device_id 关联）。本 Story 简化为仅查 WorkOrder。

**5. 健康等级映射（使用 >= 边界）：**
```python
def _score_to_level(score: float) -> str:
    if score >= 80: return "健康"
    if score >= 60: return "关注"
    if score >= 40: return "预警"
    return "危险"
```

**6. battery_soh_service 技术债务修复：**
- 现有代码完全损坏：引用 `total_score`（应为 `score`）、直接操作 `score_factors`（Dict 赋值，但字段类型是 Text）
- 删除全部旧逻辑
- 改为构造 `DegradationResult(device_id=device_id, score=soh_percent, confidence=0.8, available_points=1, total_points=1, data_sufficiency="partial")` 传入 `DeviceHealthScoreCalculator.calculate()`
- 注意 DegradationResult 的 `available_points` 和 `total_points` 是必填参数（无默认值）

**7. 动态权重配置（SystemConfig 表）：**
- config_group: `"predictive_maintenance"`
- config_key: `"weights.hvac"` / `"weights.ups"` / `"weights.battery"` / `"weights.pdu"`
- config_value: JSON 格式 `{"degradation": 0.4, "alarm": 0.3, "maintenance": 0.3}`
- `_load_weight_config()` 优先从 SystemConfig 读取，不存在时使用 WEIGHT_CONFIG 默认值

**8. 定时任务注册（APScheduler cron + fallback）：**
- APScheduler: `scheduler.add_job(func, 'cron', hour=2, minute=7, max_instances=1)`
- Fallback: asyncio.create_task + while True + 日期检查

**9. calculate_all_health_scores 流程：**
1. 查询所有支持的设备（DEVICE_TYPE_MAP 中的类型）
2. **批量预查询**告警计数和维保时间（避免 N+1 查询）
3. 对每个设备调用 `DegradationAnalyzer.analyze_device()` 获取 DegradationResult
4. 如果 analyze_device() 返回 None（设备类型无插件），构造 minimal DegradationResult(score=100, confidence=0, available_points=0, total_points=0, data_sufficiency="minimal")
5. 调用 `DeviceHealthScoreCalculator.calculate()` 计算加权健康度
6. **Upsert** 写入 DeviceHealthScore 记录（按 device_id 查找已有记录，更新而非新增）
7. score ≤ 40 时 logger.warning 标记

**10. 并发写入保护：**
- battery_soh_service 和 calculate_all_health_scores 可能同时写同一设备
- DeviceHealthScore 按 device_id 做 upsert（SELECT → UPDATE/INSERT）
- 使用 `json.dumps()` / `json.loads()` 安全序列化 score_factors Text 字段
- 无维保记录的新设备默认 maintenance_score=50（而非推导出不直观的75分）

### 现有代码关键引用

| 文件 | 说明 | 关键字段/方法 |
|------|------|-------------|
| `app/models/report.py:63-77` | DeviceHealthScore 表 | score, health_level, alarm_count, maintenance_count |
| `app/models/alarm.py:32-71` | Alarm 表 | point_id, status, created_at |
| `app/models/point.py:11-54` | Point 表 | device_id, point_code |
| `app/models/operation.py:69-108` | WorkOrder 表 | device_id, status, completed_at |
| `app/models/config.py:11-25` | SystemConfig 表 | config_group, config_key, config_value |
| `app/services/diagnosis/battery_soh_service.py:584-653` | update_device_health_score | 技术债务：total_score/score_factors 不存在 |
| `app/services/predictive_maintenance/analyzer.py` | DegradationAnalyzer | analyze_device(), analyze_all_devices() |
| `app/services/predictive_maintenance/base.py` | DegradationResult | score, confidence, data_sufficiency |
| `app/services/predictive_maintenance/config.py` | DEVICE_TYPE_MAP | AC/PRECISION_AC_*/UPS/PDU 映射 |

### Project Structure Notes

**新建文件清单：**
```
backend/app/services/predictive_maintenance/health_calculator.py  # DeviceHealthScoreCalculator
backend/alembic/versions/20260322_story_36_2_health_score_fields.py  # 迁移脚本
backend/tests/services/test_health_calculator.py  # 10 个测试
```

**修改文件清单：**
```
backend/app/models/report.py  # DeviceHealthScore 添加3个字段
backend/app/services/diagnosis/battery_soh_service.py  # 修复技术债务
backend/app/main.py  # 注册健康度计算定时任务
```

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#Section 23.3] — DeviceHealthScoreCalculator 架构
- [Source: _bmad-output/planning-artifacts/epics.md#Story 36.2] — 详细技术规格
- [Source: app/models/report.py:63-77] — DeviceHealthScore 表结构
- [Source: app/services/diagnosis/battery_soh_service.py:584-653] — 技术债务

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Completion Notes List

- Story 36.2 依赖 Story 36.1（DegradationResult + DegradationAnalyzer）
- 不涉及 MaintenanceAdvice 表（36.3 负责）
- 不涉及前端（36.4 负责）
- UPS/PDU 插件由 36.5 负责，本 Story 中这些设备的劣化评分在无插件时为 minimal

### File List

**新建：**
- `backend/app/services/predictive_maintenance/health_calculator.py`
- `backend/alembic/versions/20260322_story_36_2_health_score_fields.py`
- `backend/tests/services/test_health_calculator.py`

**修改：**
- `backend/app/models/report.py` — DeviceHealthScore 添加 score_factors, data_sufficiency, degradation_score
- `backend/app/services/diagnosis/battery_soh_service.py` — 修复技术债务
- `backend/app/main.py` — 注册健康度计算定时任务
