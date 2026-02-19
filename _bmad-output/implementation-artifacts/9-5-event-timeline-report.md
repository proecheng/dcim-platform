# Story 9.5: 事件时间线报告

Status: ready-for-dev

## Story

As a 运维主管,
I want 查看完整的事件时间线报告,
So that 我可以进行事后复盘和合规存档。

## FR 追溯

- FR39: 系统自动生成事件时间线报告（从检测到恢复的完整链路，含每个动作的执行时间和结果）
- Architecture 7.7: 事件时间线报告

## Acceptance Criteria

1. Given 一次联动事件已完成（含恢复）
   When 查看事件报告
   Then 显示完整时间线：event_id、trigger_time（毫秒精度）、trigger_source、level、每个动作的开始/结束时间和结果、total_duration、recovery_time、operator
   And 联动记录永久保存

2. Given 事件时间线报告已生成
   When 运维主管点击"导出"
   Then 报告可导出为 Excel 格式用于合规存档
   And 导出文件包含完整时间线数据

3. Given 联动执行记录列表
   When 运维主管按条件筛选
   Then 支持按时间范围、策略名称、状态筛选
   And 支持分页浏览

## 现有代码分析

### 已有实现（直接复用）

| 组件 | 文件 | 说明 |
|------|------|------|
| 联动执行记录 | `models/linkage.py` | LinkageExecution(status, event_id, policy_id, trigger_source, trigger_event, started_at, completed_at, total_duration_ms) |
| 联动执行日志 | `models/linkage.py` | LinkageLog(action_type, action_config, status, started_at, completed_at, duration_ms) |
| 联动恢复记录 | `models/linkage.py` | LinkageRecovery(operator, mode, status, started_at, completed_at, total_duration_ms) |
| 联动恢复日志 | `models/linkage.py` | LinkageRecoveryLog(step_order, action_type, recovery_command, status, duration_ms) |
| 联动策略 | `models/linkage.py` | LinkagePolicy(name, priority, trigger_type) |
| 联动 API | `api/v1/linkage.py` | 执行记录查询(list_executions, get_execution), 恢复记录查询(list_recoveries, get_recovery) |
| 联动 Schema | `schemas/linkage.py` | LinkageExecutionResponse, LinkageLogResponse, RecoveryResponse, RecoveryLogResponse |
| 前端联动 API | `api/modules/linkage.ts` | getLinkageExecutions(), getLinkageExecution(), getRecoveries(), getRecovery() |
| 前端执行页面 | `views/linkage/execution.vue` | 执行记录列表+详情抽屉 |
| 导出模式参考 | `api/v1/energy.py` | export_energy_report() — Excel/PDF 导出模式 |
| 依赖注入 | `api/deps.py` | require_operator, require_viewer |

### 需要新增

| 组件 | 文件 | 说明 |
|------|------|------|
| 时间线报告 API | `api/v1/linkage.py` | 新增 GET /timeline/{execution_id} 和 GET /timeline/{execution_id}/export |
| 时间线 Schema | `schemas/linkage.py` | TimelineEvent, TimelineReportResponse |
| 时间线报告服务 | `services/timeline_report.py` | 聚合执行+恢复数据，生成时间线；Excel 导出 |
| 前端时间线 API | `api/modules/linkage.ts` | getEventTimeline(), exportEventTimeline() |
| 前端时间线页面 | `views/linkage/timeline.vue` | 时间线报告页面（列表+详情+导出） |
| 路由配置 | `router/index.ts` | 添加 timeline 路由 |
| 后端测试 | `tests/test_timeline.py` | 时间线 API 测试 |

## Technical Implementation Notes

### 1. 时间线数据模型（不需要新表）

时间线报告是一个**聚合视图**，从已有的 4 张表聚合数据：
- `linkage_executions` — 事件基本信息
- `linkage_logs` — 联动动作执行详情
- `linkage_recoveries` — 恢复记录
- `linkage_recovery_logs` — 恢复步骤详情

不需要新建数据库表，只需要新的 Schema 和聚合查询。

### 2. 时间线 Schema 设计

```python
class TimelineEvent(BaseModel):
    """时间线中的单个事件"""
    timestamp: datetime          # 事件发生时间
    phase: str                   # 阶段: trigger/action/recovery
    event_type: str              # 事件类型描述
    detail: str                  # 详细描述
    status: str                  # 状态: success/failed/timeout/skipped/pending
    duration_ms: Optional[int]   # 耗时(毫秒)

class TimelineReportResponse(BaseModel):
    """完整时间线报告"""
    execution_id: int
    event_id: str
    policy_name: str
    trigger_source: Optional[str]
    trigger_time: datetime       # 毫秒精度
    level: str                   # 策略优先级(fire_signal/critical/normal)
    total_duration_ms: Optional[int]
    recovery_time_ms: Optional[int]
    operator: Optional[str]      # 恢复操作人
    status: str                  # 整体状态
    events: List[TimelineEvent]  # 时间线事件列表（按时间排序）
```

### 3. API 端点设计

```
GET  /linkage/timeline/{execution_id}         — 获取单个事件的完整时间线报告
GET  /linkage/timeline/{execution_id}/export   — 导出时间线报告为 Excel
```

注意：时间线列表复用已有的 `GET /linkage/executions` 端点，不需要新的列表端点。

### 4. 时间线聚合逻辑

`services/timeline_report.py` 中的 `generate_timeline()`:

1. 查询 LinkageExecution + LinkagePolicy（获取 event_id, trigger_source, priority, started_at）
2. 查询 LinkageLog（获取每个动作的执行详情）
3. 查询 LinkageRecovery（获取恢复记录，如果有）
4. 查询 LinkageRecoveryLog（获取恢复步骤详情，如果有）
5. 按时间排序合并为统一的 TimelineEvent 列表

### 5. Excel 导出

使用 openpyxl（项目已有依赖），生成包含以下 sheet 的 Excel：
- Sheet 1 "事件概要": event_id, 策略名称, 触发来源, 级别, 触发时间, 总耗时, 恢复耗时, 操作人, 状态
- Sheet 2 "时间线详情": 序号, 时间, 阶段, 事件类型, 详情, 状态, 耗时(ms)

### 6. 前端页面设计

`views/linkage/timeline.vue`:
- 顶部：执行记录列表（复用 getLinkageExecutions），点击某条记录查看时间线
- 详情区域：
  - 事件概要卡片（event_id, 策略, 触发来源, 级别, 时间, 耗时）
  - 时间线组件（使用 Element Plus 的 el-timeline）
  - 导出按钮

## Adversarial Review Findings

| ID | 级别 | 问题 | 解决方案 |
|----|------|------|----------|
| C1 | Critical | timeline 路由需在参数化路由之前注册 | 在 linkage.py 中将 timeline 端点放在 executions/{id} 之前 |
| M1 | Medium | TimelineEvent.timestamp 可能为 None（started_at nullable） | timestamp 改为 Optional[datetime]，聚合时用 execution.started_at 作 fallback |
| M2 | Medium | 导出文件名应包含 event_id 便于识别 | 文件名格式: timeline_{event_id}.xlsx |

## Dev Notes

- 不需要新建数据库表，纯聚合查询
- Excel 导出使用 openpyxl（已在 requirements.txt），参考 energy_report_excel.py 的模式
- 前端时间线使用 el-timeline 组件，每个节点显示时间+阶段+状态+耗时
- 路由添加到 linkage children 中，path: 'timeline'
- **C1**: timeline 静态路由必须在 executions/{execution_id} 参数化路由之前注册
- **M1**: TimelineEvent.timestamp 使用 Optional[datetime]，None 时用 execution.started_at 兜底
- **M2**: 导出文件名包含 event_id

## Tasks

- [ ] Task 1: 创建时间线 Schema (schemas/linkage.py 新增 TimelineEvent, TimelineReportResponse)
- [ ] Task 2: 创建时间线报告服务 (services/timeline_report.py — 聚合查询 + Excel 导出)
- [ ] Task 3: 添加时间线 API 端点 (api/v1/linkage.py — GET timeline/{id}, GET timeline/{id}/export)
- [ ] Task 4: 前端 API 函数 (api/modules/linkage.ts — getEventTimeline, exportEventTimeline)
- [ ] Task 5: 前端时间线页面 (views/linkage/timeline.vue)
- [ ] Task 6: 路由配置 (router/index.ts — 添加 timeline 子路由)
- [ ] Task 7: 后端测试 (tests/test_timeline.py)
