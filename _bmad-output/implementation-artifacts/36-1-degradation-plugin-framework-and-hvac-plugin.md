# Story 36.1: 劣化分析插件框架与 HVAC 插件

Status: ready-for-dev

## Story

As a 系统架构师,
I want 建立可扩展的劣化分析插件框架，并实现空调（HVAC）劣化分析插件作为首个实现,
So that 后续设备类型的劣化分析可以通过新增插件快速接入。

## Acceptance Criteria

1. **Given** 系统启动 **When** 加载劣化分析模块 **Then** DegradationPlugin 基类和插件注册表可用
2. **Given** HVAC 设备有≥30天回风温度和运行状态历史数据 **When** 执行劣化分析 **Then** 输出 DegradationResult（含 score、confidence、trend_factors、data_sufficiency="full"）
3. **Given** HVAC 设备仅有回风温度数据（无 COP/压缩机时长） **When** 执行劣化分析 **Then** data_sufficiency="partial"，基于可用数据降级评估，confidence 降低
4. **Given** HVAC 设备无任何历史数据 **When** 执行劣化分析 **Then** data_sufficiency="minimal"，返回默认评分100（健康），confidence=0
5. **Given** 分析窗口可配置 **When** 管理员设置 window_days=60 **Then** 使用60天滚动窗口
6. **Given** PointHistory 表有最近 1 小时数据 **When** hourly 归档任务执行 **Then** 聚合写入 PointHistoryArchive（archive_type='hourly'）
7. **Given** DegradationAnalyzer 批量分析 **When** 调用 analyze_all_devices() **Then** 仅分析有对应插件的设备类型（UPS/AC/PRECISION_AC_INDOOR/PRECISION_AC_OUTDOOR/PDU），跳过传感器类型（TH/DOOR/SMOKE/WATER 等）

## Tasks / Subtasks

- [ ] Task 1: 劣化分析插件框架 (AC: #1)
  - [ ] 1.1 新建 `backend/app/services/predictive_maintenance/__init__.py` — try/except 包裹插件导入，导入失败仅 warning 不阻塞包加载
  - [ ] 1.2 新建 `backend/app/services/predictive_maintenance/base.py` — DegradationPlugin ABC + DegradationResult dataclass
  - [ ] 1.3 新建 `backend/app/services/predictive_maintenance/registry.py` — 插件注册表（装饰器模式，参考 `gateway/adapters/registry.py`）
  - [ ] 1.4 新建 `backend/app/services/predictive_maintenance/config.py` — 分析配置（窗口天数、设备类型映射、阈值）
- [ ] Task 2: HVAC 劣化分析插件 (AC: #2, #3, #4, #5)
  - [ ] 2.1 新建 `backend/app/services/predictive_maintenance/hvac_plugin.py` — 实现 HVACDegradationPlugin
  - [ ] 2.2 回风温度偏差趋势分析 — 30天线性回归斜率
  - [ ] 2.3 COP 趋势分析（可选数据点，有则使用）— 斜率 < -0.05/月 → 劣化信号
  - [ ] 2.4 压缩机运行时长评估（可选）— 累计小时数 vs 维保周期
  - [ ] 2.5 滤网压差上升趋势检测（可选）— 压差上升 → 滤网堵塞预警
  - [ ] 2.6 数据充分度判断逻辑 — full/partial/minimal 三级
  - [ ] 2.7 综合评分：各指标加权合并，权重可配置
- [ ] Task 3: DegradationAnalyzer 调度器 (AC: #7)
  - [ ] 3.1 新建 `backend/app/services/predictive_maintenance/analyzer.py` — DegradationAnalyzer 类
  - [ ] 3.2 DEVICE_TYPE_MAP 映射（UPS→ups, AC/PRECISION_AC_INDOOR/PRECISION_AC_OUTDOOR→hvac, PDU→pdu）
  - [ ] 3.3 `_fetch_point_history()` — 优先 PointHistoryArchive(hourly)，降级到 PointHistory（限最近7天，内存采样为小时级避免拉取过多行）
  - [ ] 3.4 `analyze_device()` — 单设备分析
  - [ ] 3.5 `analyze_all_devices()` — 批量分析（仅 supported_types），每个设备用 try/except 隔离异常，单设备失败不影响其余
- [ ] Task 4: Hourly 归档定时任务 (AC: #6)
  - [ ] 4.0 为 PointHistoryArchive 添加 UNIQUE 复合索引 `(point_id, archive_type, recorded_at)` — 通过修改模型 `__table_args__` 实现，保证数据库级幂等
  - [ ] 4.1 在 `backend/app/services/predictive_maintenance/archiver.py` 中实现 `archive_hourly()` — 单条 SQL `GROUP BY point_id` 聚合所有点位的上一小时数据，INSERT 前检查唯一约束避免重复，过滤 quality<2 的坏数据
  - [ ] 4.2 SQLite 兼容：用 `strftime('%Y-%m-%d %H:00:00', recorded_at)` 替代 `date_trunc`
  - [ ] 4.3 在 `main.py` 中注册 hourly 归档任务（优先 APScheduler `scheduler.add_job('interval', hours=1, max_instances=1, coalesce=True)`，fallback 到 asyncio.create_task）
- [ ] Task 5: 测试 (AC: #1-#7)
  - [ ] 5.1 插件注册表测试 — 注册/获取/列举插件
  - [ ] 5.2 HVAC 插件 full data 测试 — 30天完整数据 → score + confidence + trend_factors
  - [ ] 5.3 HVAC 插件 partial data 测试 — 仅回风温度 → data_sufficiency="partial", confidence 降低
  - [ ] 5.4 HVAC 插件 minimal data 测试 — 无数据 → score=100, confidence=0, data_sufficiency="minimal"
  - [ ] 5.5 HVAC 插件可配置窗口测试 — window_days=60 使用60天窗口
  - [ ] 5.6 Analyzer analyze_all_devices 测试 — 分析 UPS/AC/PRECISION_AC_INDOOR/PRECISION_AC_OUTDOOR/PDU，跳过 TH/DOOR/SMOKE/WATER 等
  - [ ] 5.7 Analyzer _fetch_point_history 降级测试 — PointHistoryArchive 无数据时降级到 PointHistory
  - [ ] 5.8 archive_hourly 聚合测试 — 正确聚合 min/max/avg/sum/count 写入 PointHistoryArchive
  - [ ] 5.9 archive_hourly 幂等测试 — 重复执行不产生重复记录
  - [ ] 5.10 线性回归斜率计算测试 — 验证趋势检测准确性

## Dev Notes

### 关键设计决策

**1. 不复用 AnalysisPlugin 体系：**
AnalysisPlugin（`backend/app/services/analysis_plugins/`）是能源分析插件（输入=能耗数据，输出=节能建议），输入输出与劣化分析完全不同。新建独立的 DegradationPlugin 体系。

**2. 插件注册模式（参考 gateway/adapters/registry.py）：**
```python
# backend/app/services/predictive_maintenance/registry.py
DEGRADATION_PLUGIN_REGISTRY: dict[str, type[DegradationPlugin]] = {}

def register_degradation_plugin(device_type: str):
    """装饰器 — 注册劣化分析插件"""
    def decorator(cls):
        DEGRADATION_PLUGIN_REGISTRY[device_type] = cls
        return cls
    return decorator

def get_degradation_plugin(device_type: str) -> type[DegradationPlugin] | None:
    return DEGRADATION_PLUGIN_REGISTRY.get(device_type)
```

**3. DegradationPlugin 基类（Architecture Section 23.2）：**
```python
# backend/app/services/predictive_maintenance/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

@dataclass
class DegradationResult:
    device_id: int
    score: float                    # 0~100 劣化评分（100=健康）
    confidence: float               # 0~1 评估置信度
    available_points: int           # 实际可用数据点数
    total_points: int               # 理想数据点数
    trend_factors: dict[str, float] = field(default_factory=dict)
    primary_concern: str | None = None
    data_sufficiency: str = "minimal"  # full | partial | minimal
    detail: dict | None = None          # 各指标详细分析结果（供 36.3 维护建议引擎使用）

class DegradationPlugin(ABC):
    @abstractmethod
    def get_device_type(self) -> str: ...
    @abstractmethod
    def get_required_points(self) -> list[str]: ...
    @abstractmethod
    def get_optional_points(self) -> list[str]: ...
    @abstractmethod
    async def analyze(self, device_id: int,
                      point_history: dict[str, list],
                      window_days: int = 30) -> DegradationResult: ...
```

**4. HVAC 插件数据查询链路：**
- Device(device_id) → Point(device_id=X, point_code 匹配) → PointHistoryArchive(point_id=Y, archive_type='hourly')
- **point_code 匹配策略**：使用 `point_code LIKE '%{suffix}%'` 模式，支持两套命名体系：
  - cooling_seed 新体系：`AC-A01_return_temp`、`AC-A01_cop`、`AC-A01_compressor1_status`
  - building_points 旧体系：通过 `point_name LIKE '%回风温度%'` 备选匹配
- **关键：使用 PointHistoryArchive 表（hourly 聚合数据），不查询原始 PointHistory 表**
- 30天 hourly 数据 = 720行/点位，性能可控
- 如果 PointHistoryArchive 中 hourly 数据不足（新接入设备），降级为查询 PointHistory 限最近7天（内存采样为小时级）

**5. HVAC 劣化分析逻辑（5项指标）：**
| 指标 | 必需/可选 | point_code 后缀模式 | 劣化信号 |
|------|----------|-------------------|---------|
| 回风温度偏差 | 必需 | `return_temp` | 偏差趋势上升（线性回归斜率>0） |
| 压缩机运行状态 | 必需 | `compressor1_status` / `compressor2_status` | 频繁启停（启停次数异常） |
| COP/EER | 可选 | `cop` | 斜率 < -0.05/月 |
| 压缩机运行时长 | 可选 | `compressor_hours`（暂无种子数据） | 超过维保周期（默认 20000h） |
| 滤网告警 | 可选 | `filter_alarm`（DI 类型） | 频繁触发 → 滤网堵塞预警 |

**6. 数据充分度判定规则：**
- `full`：必需点位 + ≥2个可选点位有≥30天数据
- `partial`：仅必需点位有数据，或数据天数 < 30
- `minimal`：必需点位无数据

**7. 线性回归斜率计算：**
使用简单线性回归（numpy 不作为依赖，手动计算）。**timestamps 使用天数偏移量**（day 0, 1, 2, ..., 29），斜率单位为"值/天"，乘以 30 即为"值/月"：
```python
def _linear_regression_slope(timestamps: list[float], values: list[float]) -> float:
    """计算线性回归斜率（最小二乘法）"""
    n = len(values)
    if n < 2:
        return 0.0
    sum_x = sum(timestamps)
    sum_y = sum(values)
    sum_xy = sum(x * y for x, y in zip(timestamps, values))
    sum_x2 = sum(x * x for x in timestamps)
    denominator = n * sum_x2 - sum_x * sum_x
    if denominator == 0:
        return 0.0
    return (n * sum_xy - sum_x * sum_y) / denominator
```

**8. Hourly 归档任务 — SQLite 兼容 + 幂等 + 性能：**
```python
# 聚合上一小时 PointHistory 写入 PointHistoryArchive
# SQLite: strftime('%Y-%m-%d %H:00:00', recorded_at)
# PostgreSQL: date_trunc('hour', recorded_at)
# 使用 strftime 保证 SQLite 兼容
hour_start = datetime.now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
hour_end = hour_start + timedelta(hours=1)
# 幂等策略：PointHistoryArchive UNIQUE(point_id, archive_type, recorded_at) 约束保证数据库级幂等
# 聚合策略：单条 SQL GROUP BY point_id 一次聚合所有点位，避免逐点循环查询
# 数据质量：聚合 SQL 过滤 quality < 2 的坏数据（quality=2 为坏数据标记）
# 注意：datetime.now() 使用服务器本地时间（无 DST 时区），当前仅支持 UTC+8 部署
```

**9. DegradationAnalyzer 设备类型映射：**
```python
DEVICE_TYPE_MAP = {
    "UPS": "ups",
    "AC": "hvac",                    # 旧体系 AC → hvac 插件
    "PRECISION_AC_INDOOR": "hvac",   # cooling_seed 室内机
    "PRECISION_AC_OUTDOOR": "hvac",  # cooling_seed 室外机
    "PDU": "pdu",
    # TH/DOOR/SMOKE/WATER/IR/FAN/LIGHT 等不参与劣化分析
}
```

**10. 定时任务注册模式（参考 main.py 现有模式）：**
- hourly 归档：优先使用 APScheduler（`scheduler.add_job(func, 'interval', hours=1)`），APScheduler 不可用时 fallback 到 asyncio.create_task + while True + sleep(3600)
- 在 `app/main.py` lifespan() 中注册，与现有任务风格一致
- shutdown 时 APScheduler 自动管理，或 fallback 时手动 cancel

**11. PointHistoryArchive 索引与 UNIQUE 约束（性能+幂等）：**
- 为 PointHistoryArchive 添加 UNIQUE 复合索引 `(point_id, archive_type, recorded_at)`
- 通过 `__table_args__ = (Index("idx_archive_point_type_time", "point_id", "archive_type", "recorded_at", unique=True),)` 实现
- 同时解决查询性能和并发幂等问题（INSERT OR IGNORE / try/except IntegrityError）
- APScheduler 注册时加 `max_instances=1, coalesce=True` 防止并发触发

**12. 插件导入防护模式：**
- `__init__.py` 中 try/except 包裹插件导入，导入失败仅 warning 日志，不阻塞包加载
- 参考 main.py 中 ML 模块条件加载模式 + calibrator ImportError 处理

**13. analyze_all_devices 异常隔离：**
- 对每个设备的 analyze_device() 调用用 try/except 包裹
- 单设备分析失败记录 error 日志后继续处理下一台，不中断批量分析

### 现有代码关键引用

| 文件 | 说明 | 关键字段/方法 |
|------|------|-------------|
| `app/models/report.py:63-78` | DeviceHealthScore 表 | score, health_level, alarm_count, maintenance_count |
| `app/models/history.py:32-47` | PointHistoryArchive 表 | point_id, archive_type, value_min/max/avg, sample_count |
| `app/models/device.py:11-39` | Device 表 | device_type (UPS/AC/PRECISION_AC_INDOOR/PRECISION_AC_OUTDOOR/PDU/TH/DOOR/SMOKE/WATER), site_id |
| `app/models/point.py` | Point 表 | point_code, device_id, point_type (AI/DI/AO/DO), is_virtual |
| `gateway/adapters/registry.py:1-28` | 适配器注册表 | register_adapter 装饰器模式 |
| `app/services/diagnosis/battery_soh_service.py:584-653` | update_device_health_score | 技术债务：引用 total_score/score_factors（不存在字段），36.2 修复 |
| `app/main.py:430-621` | 定时任务注册 | asyncio.create_task + while True + sleep 模式 |

### Project Structure Notes

**新建文件清单：**
```
backend/app/services/predictive_maintenance/
├── __init__.py               # 包初始化 + 插件自动导入
├── base.py                   # DegradationPlugin ABC + DegradationResult dataclass
├── registry.py               # 插件注册表（装饰器模式）
├── config.py                 # 分析配置（窗口天数、阈值、设备类型映射）
├── hvac_plugin.py            # HVAC 劣化分析插件（首个实现）
├── analyzer.py               # DegradationAnalyzer（调度器）
└── archiver.py               # hourly 归档任务
```

**修改文件清单：**
```
backend/app/main.py           # 注册 hourly 归档定时任务
```

**测试文件：**
```
backend/tests/services/test_degradation_plugin.py    # 10 个测试
```

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#Section 23.1-23.2] — 劣化分析架构总览 + 插件基类
- [Source: _bmad-output/planning-artifacts/epics.md#Story 36.1] — Epic 36 Story 36.1 详细技术规格
- [Source: gateway/adapters/registry.py] — 插件注册表装饰器模式参考
- [Source: app/models/history.py:32-47] — PointHistoryArchive 表结构
- [Source: app/main.py:430-621] — 定时任务注册模式参考

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Completion Notes List

- Story 36.1 仅负责插件框架 + HVAC 插件 + 归档任务，不涉及 DeviceHealthScore 表修改（36.2 负责）
- 不涉及 MaintenanceAdvice 表（36.3 负责）
- 不涉及前端（36.4 负责）
- UPS/PDU/Battery 插件由 36.5 负责
- battery_soh_service.py 技术债务修复由 36.2 负责

### File List

**新建：**
- `backend/app/services/predictive_maintenance/__init__.py`
- `backend/app/services/predictive_maintenance/base.py`
- `backend/app/services/predictive_maintenance/registry.py`
- `backend/app/services/predictive_maintenance/config.py`
- `backend/app/services/predictive_maintenance/hvac_plugin.py`
- `backend/app/services/predictive_maintenance/analyzer.py`
- `backend/app/services/predictive_maintenance/archiver.py`
- `backend/tests/services/test_degradation_plugin.py`

**修改：**
- `backend/app/main.py` — 注册 hourly 归档定时任务
