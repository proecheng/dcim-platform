# Story 26.7: 灾难恢复演练

**Epic**: Epic 26 - 智能诊断高级功能 (Phase 3)
**Story ID**: 26.7
**Story Key**: 26-7-disaster-recovery-drill
**优先级**: P3 (愿景阶段)
**估算**: 3 天
**状态**: done
**创建日期**: 2026-03-09
**FR 追溯**: FR34-42

---

## 1. Story 概述

### 1.1 用户故事

```
As a 管理员,
I want 系统定期演练诊断引擎灾难恢复流程,
So that 降级机制经过验证确实有效。
```

### 1.2 业务价值

- 验证 Story 24.7 实现的熔断降级机制在真实故障场景下确实有效
- 定期演练发现潜在问题，避免真实故障时降级失效
- 生成可审计的演练报告，满足运维合规要求
- 降低诊断系统不可用的风险

### 1.3 前置条件

- [x] Story 24.7: 熔断降级机制（CircuitBreaker + FallbackStore）已实现
- [x] Story 24.2: 诊断调度器（DiagnosisScheduler + APScheduler）已实现
- [x] Story 26.6: 报告生成框架（ReportRecord 模型 + Markdown 报告）已实现

### 1.4 验收标准

- [x] AC-1: 管理员可通过 API 配置演练计划（演练窗口、场景选择）
- [x] AC-2: 支持两种演练场景：L2/L3 熔断降级、DB 查询超时降级
- [x] AC-3: 演练执行时熔断器状态正确切换，降级在 30 秒内生效
- [x] AC-4: 演练期间真实告警自动走 L1 规则引擎
- [x] AC-5: 演练不产生诊断结果记录（仅验证机制，不调用 `save_complete()`）
- [x] AC-6: 管理员可通过 API 立即终止演练
- [x] AC-7: 演练结束后生成演练报告，存储到 `report_records` 表
- [x] AC-8: 演练后自动恢复所有注入的故障（熔断器→CLOSED）
- [x] AC-9: 提供 15+ 个单元测试，覆盖核心逻辑（实际 22 个）

---

## 2. 技术设计

### 2.1 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                   Chaos Drill Service                        │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ DrillSchedule│  │ DrillExecutor│  │ DrillReportGen   │   │
│  │ (计划管理)    │  │ (场景执行)    │  │ (报告生成)        │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────────┘   │
│         │                 │                  │               │
│         ▼                 ▼                  ▼               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              ChaosDrillService (主服务)               │    │
│  └──────────────────────┬──────────────────────────────┘    │
│                         │                                    │
└─────────────────────────┼────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
   CircuitBreaker    FallbackStore   ReportRecord
   (熔断器控制)       (降级验证)      (报告存储)
```

**模块位置**:
- 服务: `app/services/diagnosis/chaos_drill_service.py`
- API: `app/api/v1/chaos_drill.py`
- Schema: `app/schemas/chaos_drill.py`
- 测试: `tests/services/diagnosis/test_chaos_drill_service.py`

### 2.2 数据模型

不新增数据库表，复用现有模型：

- **ReportRecord**: 存储演练报告（`report_type='diagnosis_drill'`）
- **SystemConfig**: 存储演练计划配置（`config_group='chaos_drill'`）

**演练计划配置 JSON 结构**（存储在 SystemConfig.config_value）:
```json
{
  "enabled": false,
  "cron_expression": "0 2 * * 0",
  "window_minutes": 120,
  "scenarios": ["circuit_breaker_degradation", "db_timeout_fallback"],
  "confirmed": false,
  "confirmed_by": null,
  "confirmed_at": null
}
```

**演练报告数据 JSON 结构**（存储在 ReportRecord.report_data）:
```json
{
  "drill_id": "drill-20260309-020000",
  "start_time": "2026-03-09T02:00:00Z",
  "end_time": "2026-03-09T02:05:30Z",
  "duration_seconds": 330,
  "scenarios": [
    {
      "name": "circuit_breaker_degradation",
      "description": "L2/L3 熔断降级验证",
      "status": "passed",
      "start_time": "2026-03-09T02:00:00Z",
      "end_time": "2026-03-09T02:02:00Z",
      "recovery_seconds": 1.2,
      "details": {
        "breaker_state_before": "CLOSED",
        "breaker_forced_to": "OPEN",
        "degradation_detected": true,
        "degradation_latency_ms": 50,
        "l1_fallback_working": true,
        "breaker_restored_to": "CLOSED"
      }
    },
    {
      "name": "db_timeout_fallback",
      "description": "数据库超时 Redis 暂存验证",
      "status": "passed",
      "start_time": "2026-03-09T02:02:00Z",
      "end_time": "2026-03-09T02:05:30Z",
      "recovery_seconds": 2.5,
      "details": {
        "fault_injected": true,
        "redis_fallback_working": true,
        "data_integrity_check": true,
        "fault_cleared": true
      }
    }
  ],
  "overall_status": "passed",
  "summary": "2 个场景全部通过，降级机制验证有效"
}
```

### 2.3 API 设计

#### 2.3.1 获取演练计划

```
GET /api/v1/diagnosis/chaos/schedule
权限: admin
```

**响应 200**:
```json
{
  "enabled": false,
  "cron_expression": "0 2 * * 0",
  "window_minutes": 120,
  "scenarios": ["circuit_breaker_degradation", "db_timeout_fallback"],
  "confirmed": false,
  "next_run_time": null
}
```

#### 2.3.2 更新演练计划

```
PUT /api/v1/diagnosis/chaos/schedule
权限: admin
```

**请求体**:
```json
{
  "enabled": true,
  "cron_expression": "0 2 * * 0",
  "window_minutes": 120,
  "scenarios": ["circuit_breaker_degradation"]
}
```

#### 2.3.3 确认演练计划

```
POST /api/v1/diagnosis/chaos/schedule/confirm
权限: admin
```

**响应 200**:
```json
{
  "message": "演练计划已确认",
  "next_run_time": "2026-03-16T02:00:00Z"
}
```

#### 2.3.4 手动触发演练

```
POST /api/v1/diagnosis/chaos/trigger
权限: admin
```

**请求体**:
```json
{
  "scenarios": ["circuit_breaker_degradation", "db_timeout_fallback"]
}
```

**响应 202**:
```json
{
  "message": "演练已启动",
  "drill_id": "drill-20260309-143000"
}
```

#### 2.3.5 终止演练

```
POST /api/v1/diagnosis/chaos/stop
权限: admin
```

**响应 200**:
```json
{
  "message": "演练已终止，所有故障已恢复",
  "drill_id": "drill-20260309-143000"
}
```

#### 2.3.6 查询演练历史

```
GET /api/v1/diagnosis/chaos/history?page=1&page_size=10
权限: admin
```

**响应 200**:
```json
{
  "total": 5,
  "items": [
    {
      "id": 1,
      "report_name": "灾难恢复演练报告 2026-03-09",
      "status": "completed",
      "report_data": { ... },
      "created_at": "2026-03-09T02:06:00Z"
    }
  ]
}
```

### 2.4 演练场景设计

#### 场景 1: circuit_breaker_degradation（L2/L3 熔断降级）

**步骤**:
1. 记录当前熔断器状态（`breaker.state`）
2. 调用 `breaker.force_open()` 安全地强制切换为 OPEN（需先在 CircuitBreaker 中添加此方法，内部获取 `_lock`）
3. 验证: `allow_request("L2")` 返回 `(True, degraded=True)`
4. 验证: L1 请求不受影响（`allow_request("L1")` 返回 `(True, degraded=False)`）
5. 恢复: 调用 `breaker.reset()` 重置为 CLOSED
6. 验证: `allow_request("L2")` 返回 `(True, degraded=False)`
7. 使用 `time.perf_counter()` 记录恢复耗时

**需要在 CircuitBreaker 中添加的方法**:
```python
async def force_open(self):
    """演练专用：安全地强制熔断器为 OPEN 状态"""
    self._ensure_lock()  # 同步方法，确保 _lock 已初始化
    async with self._lock:
        self._last_trip_time = self._time_func()
        await self._set_state(BreakerState.OPEN, reason="chaos_drill")  # 复用内部方法，正确触发回调
```

**注意**: `_ensure_lock()` 是同步方法（不可 await），`_set_state()` 是 async 方法，回调参数格式为 dict。

#### 场景 2: db_timeout_fallback（数据库超时 Redis 暂存）

**步骤**:
1. 构造一个模拟诊断结果 dict（`template_id=None` 可接受）
2. 直接调用 `await DiagnosisFallbackStore.save_to_redis(data, reason="chaos_drill")` 验证 Redis 写入（async staticmethod，返回 Redis key）
3. 验证: Redis 中存在对应的 `diagnosis:pending:*` key
4. **直接删除该 key**（使用 `redis.delete(key)`），不调用 `recover_pending()` 以避免将模拟数据写入 DB（违反 AC-5）
5. 使用 `time.perf_counter()` 记录操作耗时

**设计说明**: 不注入真实 DB 故障，而是直接验证 FallbackStore 的 `save_to_redis()` → `recover_pending()` 完整链路。这更安全、更可靠。

### 2.5 安全保护机制

- **演练标志**: `ChaosDrillService.is_drill_active` 全局标志
- **真实告警保护**: 调度器在 `_handle_alarm()` 中检查 `is_drill_active`，若为 True 则强制 `inference_level="L1"`（无需在 `_execute_inference` 中重复检查，因为 L1 本身跳过熔断器逻辑）
- **一键终止**: `stop_drill()` 立即清除所有故障注入、恢复熔断器、清除标志
- **超时保护**: 使用 `asyncio.wait_for()` 包裹每个场景，默认 120 秒超时自动终止
- **并发保护**: 使用延迟初始化的 `_drill_lock`（`_ensure_lock()` 模式）保证同一时间只能有一个演练在执行

---

## 3. 实现任务

### Task 1: ChaosDrillService 核心服务 (1 天)

**文件**: `app/services/diagnosis/chaos_drill_service.py`

实现以下方法:
- `get_drill_schedule()` — 获取演练计划配置
- `update_drill_schedule()` — 更新演练计划
- `confirm_drill_schedule()` — 确认演练计划
- `trigger_drill()` — 手动触发演练
- `stop_drill()` — 终止演练
- `execute_drill()` — 执行演练（内部方法）
- `_run_circuit_breaker_scenario()` — 场景 1 执行
- `_run_db_timeout_scenario()` — 场景 2 执行
- `_generate_drill_report()` — 生成演练报告
- `get_drill_history()` — 查询演练历史

### Task 2: Pydantic Schema (0.5 天)

**文件**: `app/schemas/chaos_drill.py`

定义请求/响应模型:
- `DrillScheduleResponse`
- `DrillScheduleUpdateRequest`
- `DrillTriggerRequest`
- `DrillTriggerResponse`
- `DrillStopResponse`
- `DrillHistoryResponse`
- `DrillHistoryItem`

### Task 3: API 路由 (0.5 天)

**文件**: `app/api/v1/chaos_drill.py`

6 个 REST 端点，权限均为 admin。

### Task 4: 调度器集成 (0.5 天)

在 `scheduler.py` 中添加:
- 在 `_handle_alarm()` 中添加演练模式检查（`inference_level` 确定之后、加入队列之前，强制 L1）
- 注意: 不需要在 `_execute_inference()` 中添加检查，因为 L1 本身就跳过熔断器逻辑

### Task 5: 单元测试 (0.5 天)

**文件**: `tests/services/diagnosis/test_chaos_drill_service.py`

测试用例（15+ 个）:
1. 获取默认演练计划
2. 更新演练计划
3. 确认演练计划
4. 触发演练 - 熔断降级场景
5. 触发演练 - DB 超时场景
6. 触发演练 - 全部场景
7. 终止演练
8. 演练报告生成
9. 查询演练历史
10. 并发演练保护
11. 场景超时保护
12. 演练标志正确设置/清除
13. 熔断器状态恢复验证
14. 无效场景名称处理
15. 未确认计划不执行

---

## 4. Dev Notes

### 4.1 关键实现模式

```python
# 熔断器状态控制（复用现有 CircuitBreaker）
from app.services.diagnosis.circuit_breaker import CircuitBreaker, BreakerState

# 安全地强制熔断（使用新增的 force_open 方法，内部获取 asyncio.Lock）
await breaker.force_open()

# 恢复（已有方法）
breaker.reset()  # 同步方法，重置为 CLOSED
```

```python
# 演练模式全局标志（类变量，进程级共享）
class ChaosDrillService:
    _instance = None
    is_drill_active: bool = False
    _current_drill_id: str | None = None
    _drill_lock: asyncio.Lock | None = None  # 延迟初始化

    @classmethod
    def _ensure_lock(cls):
        if cls._drill_lock is None:
            cls._drill_lock = asyncio.Lock()
```

```python
# 场景超时保护
import asyncio
try:
    result = await asyncio.wait_for(
        self._run_circuit_breaker_scenario(breaker),
        timeout=120.0
    )
except asyncio.TimeoutError:
    scenario_result["status"] = "timeout"
```

```python
# 高精度计时
import time
start = time.perf_counter()
# ... 场景执行 ...
elapsed = time.perf_counter() - start
```

### 4.2 与调度器的集成

调度器 `_handle_alarm()` 方法（scheduler.py 约 line 263-267）中添加检查:
```python
# 演练模式保护：真实告警强制 L1
from app.services.diagnosis.chaos_drill_service import ChaosDrillService
if ChaosDrillService.is_drill_active:
    inference_level = "L1"
    logger.info(f"演练模式: 告警 {alarm_id} 强制降级为 L1")
```

**插入位置**: 在 `_handle_alarm` 中确定 `inference_level` 之后、加入队列之前。

### 4.3 避免的设计陷阱

- **不要直接修改 `_state` 私有属性**: 使用 `force_open()` 方法（需新增），内部获取 `_lock` 避免竞态
- **不要模拟网络分区**: FR34-42 提到的"网络分区"场景标注为"愿景阶段"，本 Story 不实现
- **不要真正停止进程**: 使用熔断器状态切换模拟，不要 kill/restart 任何进程
- **不要注入真实 DB 故障**: 场景 2 直接调用 FallbackStore 方法验证，而非破坏 DB 连接
- **演练 DB 操作使用独立 session**: 避免影响正常业务的数据库事务
- **不要为 DiagnosisResult 添加 `is_drill` 列**: 演练不产生诊断结果记录，无需数据库迁移

### 4.4 关键导入路径

```python
# 正确的导入路径（棕地项目，路径可能不直观）
from app.models.config import SystemConfig          # 不是 system_config
from app.models.report import ReportRecord
from app.services.diagnosis.circuit_breaker import CircuitBreaker, BreakerState
from app.services.diagnosis.fallback_store import DiagnosisFallbackStore
from app.api.deps import require_role               # 不是 app.core.security
```

### 4.5 ReportRecord.report_data 序列化

`report_data` 列类型为 `Text`（字符串），需要手动 JSON 序列化:
```python
import json
report = ReportRecord(
    report_type="diagnosis_drill",
    report_name=f"灾难恢复演练报告 {date_str}",
    report_data=json.dumps(report_data_dict, ensure_ascii=False),  # 必须 json.dumps
    status="completed",
    # ...
)
```

### 4.6 边界情况处理

- **熔断器已为 OPEN**: 场景 1 开始前检查 `breaker.state`，如果已经是 `BreakerState.OPEN`，则跳过该场景，报告状态标记为 `"skipped"`，原因 `"breaker_already_open"`
- **服务器重启时演练中断**: `is_drill_active` 是内存变量，重启后自动清除。熔断器也会重新创建（默认 CLOSED），无"僵尸演练"风险
- **API 路由注册模式**: 遵循 `misdiagnosis_reports.py` 模式，`chaos_drill.py` 中自带完整 prefix `"/diagnosis/chaos"`，在 `__init__.py` 中独立注册（不嵌套到 diagnosis_router）
