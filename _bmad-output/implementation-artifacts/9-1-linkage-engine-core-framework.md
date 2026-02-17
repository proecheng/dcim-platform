# Story 9.1: 联动引擎核心框架

Status: done

## Story

As a 开发者,
I want 一个事件驱动的联动引擎,
So that 系统可以在特定事件触发时自动执行预设动作序列。

## FR 追溯

- FR36: 系统支持配置联动策略（条件→动作链），在特定事件触发时自动执行预设动作序列
- Architecture 7.1-7.7: 消防分级联动引擎

## Acceptance Criteria

1. Given 联动引擎订阅进程内事件总线
   When 告警引擎或外部系统产生事件
   Then 联动引擎评估条件并执行匹配的策略

2. Given 联动策略匹配成功
   When 动作执行器执行动作
   Then 通过 asyncio.gather 并行执行所有动作，每个动作独立超时（3s）
   And 单个动作失败不阻塞其他动作

3. Given 联动引擎运行中
   When 收到 FIRE_SIGNAL 优先级事件
   Then 跳过排队立即评估执行

4. Given 联动策略已配置
   When 通过 API 管理策略
   Then 支持策略 CRUD、启用/禁用、手动触发测试

5. Given 联动执行完成
   When 查看执行日志
   Then 所有动作执行结果（成功/失败/超时）强制记录到联动日志

6. Given 动作类型注册表
   When 配置联动动作
   Then 支持动作类型：MQTT_COMMAND、ALARM_NOTIFY、VIDEO_RECORD、VIDEO_POPUP、WEBHOOK

## 架构决策（Epic 8 回顾确认）

> **进程内事件总线替代 Redis Pub/Sub**：系统未来将迁移到其他服务器，当前阶段不引入 Redis。使用 asyncio 事件总线（进程内），设计时预留抽象接口，迁移后可无缝切换到 Redis Pub/Sub。

## 现有代码分析

### 已有实现（直接复用）

| 层级 | 文件 | 内容 |
|------|------|------|
| 告警模型 | `backend/app/models/alarm.py` | Alarm(alarm_no, point_id, alarm_level, alarm_type, status, trigger_value) |
| 告警规则 | `backend/app/models/alarm.py` | AlarmRule(rule_name, rule_type, condition_expr, alarm_level) |
| 告警升级 | `backend/app/models/alarm.py` | AlarmEscalation(source_level, timeout_minutes, target_level) |
| WebSocket | `backend/app/services/websocket.py` | ConnectionManager(channels: realtime/alarms/control/system), broadcast_alarm() |
| 设备模型 | `backend/app/models/device.py` | Device(device_type, device_code, device_name) |
| 点位模型 | `backend/app/models/point.py` | Point(device_id, point_type, point_code) |
| 数据库基类 | `backend/app/core/database.py` | Base, async_session, get_db |
| 依赖注入 | `backend/app/api/deps.py` | get_current_user, require_admin, require_operator |
| 路由注册 | `backend/app/api/v1/__init__.py` | api_router.include_router() |

### 缺失实现（需新增）

| 缺失项 | 说明 |
|--------|------|
| 联动策略模型 | LinkagePolicy, LinkageAction, LinkageExecution, LinkageLog |
| 事件总线 | 进程内 asyncio 事件总线（抽象接口 + 内存实现） |
| 联动引擎服务 | 条件评估器 + 动作执行器 + 优先级队列 |
| 联动 API | 策略 CRUD、启用/禁用、手动触发、执行日志查询 |
| 联动 Schema | 请求/响应 Pydantic 模型 |
| 前端联动管理页面 | 策略管理 + 执行日志 |
| 前端 API 模块 | linkage.ts |

## 详细设计

### 1. 事件总线抽象层

```python
# backend/app/engines/event_bus.py

class EventPriority(str, Enum):
    FIRE_SIGNAL = "fire_signal"   # 最高优先级，跳过排队
    CRITICAL = "critical"
    NORMAL = "normal"

class Event:
    event_type: str          # 如 "alarm.triggered", "alarm.resolved", "fire.detected"
    source: str              # 来源标识
    priority: EventPriority
    payload: dict            # 事件数据
    timestamp: datetime

class EventBus(ABC):
    """事件总线抽象接口 — 未来可替换为 Redis Pub/Sub"""
    async def publish(self, channel: str, event: Event): ...
    async def subscribe(self, channel: str, handler: Callable): ...
    async def unsubscribe(self, channel: str, handler: Callable): ...

class InMemoryEventBus(EventBus):
    """进程内实现 — asyncio.Queue + handlers dict"""
```

### 2. 数据模型

```
LinkagePolicy (联动策略)
├── id, name, description
├── trigger_type: str          # "alarm_level", "alarm_type", "event_type", "fire_signal"
├── trigger_condition: JSON    # {"alarm_level": "critical", "device_type": "SMOKE"}
├── priority: str              # "fire_signal" / "critical" / "normal"
├── is_enabled: bool
├── is_system: bool            # True=YAML预定义不可删, False=用户自定义
├── actions → LinkageAction[]
├── created_at, updated_at

LinkageAction (联动动作)
├── id, policy_id (FK→LinkagePolicy)
├── action_type: str           # MQTT_COMMAND / ALARM_NOTIFY / VIDEO_RECORD / VIDEO_POPUP / WEBHOOK
├── action_config: JSON        # 动作参数（目标设备、命令内容等）
├── sort_order: int            # 执行顺序（并行执行，但日志按此排序）
├── timeout_seconds: int       # 独立超时，默认3
├── retry_count: int           # 失败重试次数，默认0
├── created_at

LinkageExecution (联动执行记录)
├── id, policy_id (FK→LinkagePolicy)
├── event_id: str              # UUID，关联触发事件
├── trigger_source: str        # 触发来源描述
├── trigger_event: JSON        # 触发事件快照
├── status: str                # "executing" / "completed" / "partial_failure" / "failed"
├── started_at, completed_at
├── total_duration_ms: int
├── logs → LinkageLog[]

LinkageLog (联动动作日志)
├── id, execution_id (FK→LinkageExecution)
├── action_id (FK→LinkageAction)
├── action_type: str
├── action_config: JSON
├── status: str                # "success" / "failed" / "timeout"
├── error_message: str
├── started_at, completed_at
├── duration_ms: int
```

### 3. 联动引擎服务

```
LinkageEngine (单例，lifespan 启动)
├── event_bus: EventBus
├── _policy_cache: Dict[int, LinkagePolicy]  # 内存缓存已启用策略
├── _action_handlers: Dict[str, ActionHandler]  # 动作类型→处理器
│
├── start() — 订阅事件总线，加载策略缓存
├── stop() — 取消订阅，清理
├── _on_event(event) — 事件处理入口
│   ├── FIRE_SIGNAL → 立即评估（跳过队列）
│   └── 其他 → 正常评估
├── _evaluate(event) → List[LinkagePolicy] — 条件匹配
├── _execute(policy, event) — 执行策略
│   ├── 创建 LinkageExecution 记录
│   ├── asyncio.gather(*actions, return_exceptions=True)
│   ├── 每个动作独立 asyncio.wait_for(timeout=3s)
│   ├── 记录 LinkageLog
│   └── 更新 execution status
└── reload_policies() — 策略变更时刷新缓存
```

### 4. 动作处理器

```python
class ActionHandler(ABC):
    action_type: str
    async def execute(self, config: dict, event: Event) -> ActionResult: ...

# 本 Story 实现的处理器：
class AlarmNotifyHandler(ActionHandler):     # 通过 WebSocket 推送告警通知
class WebhookHandler(ActionHandler):         # HTTP POST 调用外部系统

# 占位处理器（后续 Story 实现）：
class MqttCommandHandler(ActionHandler):     # MQTT 命令下发（需 MQTT 客户端）
class VideoRecordHandler(ActionHandler):     # NVR 录像触发（需视频集成 Epic 10）
class VideoPopupHandler(ActionHandler):      # 前端视频弹窗推送（需视频集成 Epic 10）
```

### 5. API 设计

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/v1/linkage/policies` | 策略列表（分页+筛选） | viewer |
| GET | `/api/v1/linkage/policies/{id}` | 策略详情（含动作列表） | viewer |
| POST | `/api/v1/linkage/policies` | 创建策略 | admin |
| PUT | `/api/v1/linkage/policies/{id}` | 更新策略 | admin |
| DELETE | `/api/v1/linkage/policies/{id}` | 删除策略（is_system=True 禁止删除） | admin |
| PUT | `/api/v1/linkage/policies/{id}/toggle` | 启用/禁用策略 | operator |
| POST | `/api/v1/linkage/policies/{id}/test` | 手动触发测试（生成模拟事件） | operator |
| GET | `/api/v1/linkage/executions` | 执行记录列表（分页+筛选） | viewer |
| GET | `/api/v1/linkage/executions/{id}` | 执行详情（含动作日志） | viewer |
| GET | `/api/v1/linkage/action-types` | 获取支持的动作类型列表 | viewer |

## Tasks / Subtasks

### 后端

- [ ] Task 1: 事件总线抽象层 (AC: #1, #3)
  - [ ] 1.1 新建 `engines/event_bus.py`: EventPriority 枚举、Event 数据类（含 is_test: bool = False）、EventBus 抽象基类 [审查修复: H3]
  - [ ] 1.2 实现 InMemoryEventBus: Dict[str, List[Callable]] 存储订阅者，publish 时直接 asyncio.gather 调用所有 handler（不使用 Queue）[审查修复: C4]
  - [ ] 1.3 全局单例 `get_event_bus()` 工厂函数

- [ ] Task 2: 联动数据模型 (AC: #4, #5)
  - [ ] 2.1 新建 `models/linkage.py`: LinkagePolicy, LinkageAction, LinkageExecution, LinkageLog
  - [ ] 2.2 LinkagePolicy: trigger_type, trigger_condition(JSON), priority, is_enabled, is_system
  - [ ] 2.3 LinkageAction: policy_id FK, action_type, action_config(JSON), sort_order, timeout_seconds(default=3), retry_count(default=0)
  - [ ] 2.4 LinkageExecution: policy_id FK, event_id(String(36) UUID), trigger_source, trigger_event(JSON), status, started_at, completed_at, total_duration_ms [审查修复: M3]
  - [ ] 2.5 LinkageLog: execution_id FK, action_id FK, action_type, status("success"/"failed"/"timeout"/"skipped"), error_message, started_at, completed_at, duration_ms [审查修复: M4]
  - [ ] 2.6 在 `models/__init__.py` 注册新模型

- [ ] Task 3: 联动 Schema (AC: #4, #5)
  - [ ] 3.1 新建 `schemas/linkage.py`
  - [ ] 3.2 LinkagePolicyCreate/Update/Response（含 actions 嵌套）
  - [ ] 3.3 LinkageActionCreate/Response
  - [ ] 3.4 LinkageExecutionResponse（含 logs 嵌套）
  - [ ] 3.5 LinkageLogResponse
  - [ ] 3.6 LinkagePolicyTestRequest（手动触发测试的模拟事件参数）
  - [ ] 3.7 ActionTypeInfo（动作类型描述）

- [ ] Task 4: 动作处理器 (AC: #2, #6)
  - [ ] 4.1 新建 `engines/action_handlers.py`: ActionHandler 抽象基类、ActionResult 数据类
  - [ ] 4.2 AlarmNotifyHandler: 通过 ws_manager.broadcast_alarm() 推送，is_test 时消息标注"[测试]" [审查修复: H3]
  - [ ] 4.3 WebhookHandler: httpx.AsyncClient POST 调用，is_test 时跳过实际 HTTP 调用只记录日志 [审查修复: H3, M5]
  - [ ] 4.4 MqttCommandHandler/VideoRecordHandler/VideoPopupHandler: 占位实现，返回 status="skipped", error_message="动作类型未实现" [审查修复: M4]
  - [ ] 4.5 ActionHandlerRegistry: 注册表，按 action_type 查找处理器

- [ ] Task 5: 联动引擎核心 (AC: #1, #2, #3)
  - [ ] 5.1 新建 `engines/linkage_engine.py`: LinkageEngine 类
  - [ ] 5.2 start(): 订阅事件总线 "linkage" 频道，从数据库加载已启用策略到内存缓存
  - [ ] 5.3 _on_event(): FIRE_SIGNAL 跳过条件缓冲直接评估，其他正常评估
  - [ ] 5.4 _evaluate(): 遍历缓存策略，匹配 trigger_type + trigger_condition。数值比较必须用 `is not None` [审查修复: H4]
  - [ ] 5.5 _execute(): asyncio.gather 并行执行动作，每个动作 asyncio.wait_for(timeout)，timeout 用 `timeout_seconds if timeout_seconds is not None else 3` [审查修复: H4]
  - [ ] 5.6 单个动作失败不阻塞其他，记录 LinkageExecution + LinkageLog
  - [ ] 5.7 reload_policies(): copy-on-write 模式刷新缓存（构建新 dict 后原子替换引用）[审查修复: C5]
  - [ ] 5.8 全局单例 `get_linkage_engine()`

- [ ] Task 6: 联动 API (AC: #4, #5)
  - [ ] 6.1 新建 `api/v1/linkage.py`
  - [ ] 6.2 GET /policies — 分页列表，支持 is_enabled/trigger_type 筛选
  - [ ] 6.3 GET /policies/{id} — 详情含 actions
  - [ ] 6.4 POST /policies — 创建策略+动作（事务），调用 engine.reload_policies()
  - [ ] 6.5 PUT /policies/{id} — 更新策略+动作，is_system=True 时禁止修改 trigger 相关字段
  - [ ] 6.6 DELETE /policies/{id} — is_system=True 返回 403
  - [ ] 6.7 PUT /policies/{id}/toggle — 启用/禁用
  - [ ] 6.8 POST /policies/{id}/test — 构造模拟事件发布到事件总线
  - [ ] 6.9 GET /executions — 分页列表，支持 policy_id/status/时间范围筛选
  - [ ] 6.10 GET /executions/{id} — 详情含 logs
  - [ ] 6.11 GET /action-types — 返回已注册的动作类型列表
  - [ ] 6.12 在 `api/v1/__init__.py` 注册路由: `api_router.include_router(linkage_router, prefix="/linkage", tags=["联动策略"])`

- [ ] Task 7: 引擎生命周期集成 (AC: #1)
  - [ ] 7.1 在 `main.py` lifespan 中：用 asyncio.create_task() 启动联动引擎事件循环，yield 后 task.cancel() [审查修复: C3]
  - [ ] 7.2 新增 WebSocket 频道 "linkage" 到 ConnectionManager，新增 broadcast_linkage() 方法，消息格式: {type: "linkage", action: "execution_started"|"execution_completed"|"action_result", data: {...}} [审查修复: H2]
  - [ ] 7.3 在 alarm_engine 告警创建流程中添加 event_bus.publish("linkage", event) 调用 [审查修复: H1]
  - [ ] 7.4 检查 requirements.txt 是否包含 httpx，如无则添加 httpx>=0.25.0 [审查修复: M5]

- [ ] Task 8: 后端测试 (AC: all)
  - [ ] 8.1 test_event_bus — InMemoryEventBus publish/subscribe/fire_signal 优先级
  - [ ] 8.2 test_linkage_policy_crud — 策略 CRUD API
  - [ ] 8.3 test_linkage_policy_system_protect — is_system=True 禁止删除/修改触发条件
  - [ ] 8.4 test_linkage_engine_evaluate — 条件匹配逻辑
  - [ ] 8.5 test_linkage_engine_execute — 并行执行+独立超时+部分失败
  - [ ] 8.6 test_linkage_execution_log — 执行记录和日志查询
  - [ ] 8.7 test_linkage_policy_test_trigger — 手动触发测试

### 前端

- [ ] Task 9: 前端 API 模块 (AC: #4, #5)
  - [ ] 9.1 新建 `api/modules/linkage.ts`
  - [ ] 9.2 TypeScript 接口: LinkagePolicy, LinkageAction, LinkageExecution, LinkageLog, ActionTypeInfo
  - [ ] 9.3 API 函数: getLinkagePolicies, getLinkagePolicy, createLinkagePolicy, updateLinkagePolicy, deleteLinkagePolicy, toggleLinkagePolicy, testLinkagePolicy, getLinkageExecutions, getLinkageExecution, getActionTypes

- [ ] Task 10: 联动策略管理页面 (AC: #4)
  - [ ] 10.1 新建 `views/linkage/policy.vue`
  - [ ] 10.2 策略列表表格: name, trigger_type, priority, is_enabled, is_system, actions 数量, updated_at
  - [ ] 10.3 新建/编辑策略对话框: 基本信息 + 动作列表（可增删排序）
  - [ ] 10.4 动作配置: action_type 下拉 + 动态 action_config 表单
  - [ ] 10.5 启用/禁用开关、删除确认（is_system 禁止删除）
  - [ ] 10.6 手动测试按钮 + 测试结果展示

- [ ] Task 11: 联动执行日志页面 (AC: #5)
  - [ ] 11.1 新建 `views/linkage/execution.vue`
  - [ ] 11.2 执行记录列表: event_id, policy_name, trigger_source, status, started_at, total_duration_ms
  - [ ] 11.3 执行详情抽屉: 动作日志时间线（每个动作的开始/结束/状态/耗时）
  - [ ] 11.4 筛选: 策略名称、状态、时间范围

- [ ] Task 12: 路由注册 (AC: all)
  - [ ] 12.1 在 `router/index.ts` 新增联动管理路由组:
    - `/linkage/policy` — 联动策略管理
    - `/linkage/execution` — 联动执行日志
  - [ ] 12.2 侧边栏菜单: "联动管理" 分组下两个子菜单

## 对抗性审查修复

### C3: lifespan 后台任务模式
**问题**: main.py 中所有后台任务用 `asyncio.create_task()` + yield 后 `task.cancel()`。联动引擎必须遵循同样模式。
**修复**: Task 7.1 中联动引擎的事件处理循环用 `asyncio.create_task(engine_loop())`，shutdown 时 `task.cancel()`。不要在 engine 内部管理 task 生命周期。

### C4: FIRE_SIGNAL 跳过队列的竞态风险
**问题**: FIRE_SIGNAL 直接调用 handler 时，队列中的普通事件可能并发执行，导致同一策略重复触发。
**修复**: 简化设计 — 不使用 asyncio.Queue，所有事件都直接 dispatch 到 handler。InMemoryEventBus 内部用 `Dict[str, List[Callable]]` 存储订阅者，publish 时直接 `asyncio.gather(*[handler(event) for handler in handlers])`。FIRE_SIGNAL 的区别仅在于联动引擎内部的评估优先级（跳过条件缓冲/去抖）。

### C5: 策略缓存刷新并发安全
**问题**: reload_policies() 刷新过程中事件到达可能读到不一致缓存。
**修复**: 使用 copy-on-write — 构建新 dict 后原子替换 `self._policy_cache = new_cache`。Python dict 赋值是原子操作，无需加锁。

### H1: alarm_engine 集成点
**问题**: alarm_engine 检测越限后创建 Alarm 记录，但没有事件发布机制。联动引擎无法收到告警事件。
**修复**: 在 alarm_engine 的告警创建流程中添加 `await event_bus.publish("linkage", event)` 调用。这是联动引擎能工作的前提。在 Task 7 中新增子任务。

### H2: WebSocket "linkage" 频道消息格式
**问题**: 未定义联动事件的 WebSocket 消息格式。
**修复**: 定义格式 `{type: "linkage", action: "execution_started"|"execution_completed"|"action_result", data: {execution_id, policy_name, status, ...}}`。在 websocket.py 中新增 `broadcast_linkage()` 方法。

### H3: 手动测试触发的安全性
**问题**: POST /policies/{id}/test 会真正执行动作（WebhookHandler 发 HTTP 请求）。
**修复**: Event 数据类新增 `is_test: bool = False`。测试触发时设为 True。WebhookHandler 检查 is_test 时跳过实际 HTTP 调用，只记录日志。AlarmNotifyHandler 正常推送但消息标注"[测试]"。

### H4: value or fallback 陷阱检查点
**问题**: Dev Notes 提到但 Tasks 中无具体检查点。
**修复**: Task 5.4 条件评估中，trigger_condition 的数值比较必须用 `if value is not None`。所有 `timeout_seconds or 3` 改为 `timeout_seconds if timeout_seconds is not None else 3`。

### M3: event_id UUID 存储
**修复**: LinkageExecution.event_id 用 `Column(String(36))`，Python 层 `str(uuid.uuid4())` 生成。

### M4: 占位处理器状态
**修复**: LinkageLog.status 枚举为 "success" / "failed" / "timeout" / "skipped"。占位处理器返回 "skipped" + error_message="动作类型未实现"。

### M5: httpx 依赖
**修复**: WebhookHandler 需要 httpx。检查 requirements.txt，如无则添加 `httpx>=0.25.0`。

## Dev Notes

### 后端模式参考

- 异步数据库：`Depends(get_db)` + AsyncSession，所有写操作必须 `await db.commit()`
- 权限：admin 管理策略，operator 启用/禁用和测试，viewer 查看
- JSON 字段：SQLite 用 `Column(Text)` 存 JSON 字符串，读取时 `json.loads()`，写入时 `json.dumps()`
- 新文件放在 `engines/` 目录（架构规定：引擎层独立于 services）
- `value or fallback` 陷阱：用 `if value is not None` 判断，不要用 `value or default`
- 前后端枚举一致性：action_type、status 等枚举值前后端必须完全一致（英文）

### 事件总线设计要点

- 抽象接口 `EventBus` 定义 publish/subscribe/unsubscribe
- `InMemoryEventBus` 用 `asyncio.Queue` + `Dict[str, List[Callable]]`
- FIRE_SIGNAL 事件不入队列，直接调用所有 handler
- 预留 `RedisEventBus` 实现接口（本 Story 不实现，仅定义接口）

### 联动引擎生命周期

- 在 `main.py` 的 `lifespan` async context manager 中启动/停止
- 参考现有 simulator 的启动模式
- 引擎启动时从数据库加载所有 is_enabled=True 的策略到内存
- 策略 CRUD 操作后调用 `engine.reload_policies()` 刷新缓存

### 前端模式参考

- 2.5D 样式: `@use '@/styles/mixins-25d' as *` + `@include page-dashboard(N)`
- 自动导入: Vue/Pinia API 无需手动 import
- API 模块: 参考 `api/modules/alarm.ts` 的结构
- 表格: 使用 Element Plus `el-table` + `el-pagination`
- 对话框: `el-dialog` + `el-form`
- 路由: 参考现有 alarm 路由结构

### 架构对齐

- Architecture 7.1: 联动引擎架构 — 事件总线 + 条件评估器 + 动作执行器
- Architecture 7.3: 动作类型注册表 — 5 种动作类型
- Architecture 7.4: 消防信号最高优先级 — FIRE_SIGNAL 跳过排队
- Architecture 7.5: 联动策略配置方式 — YAML 预定义(is_system) + 数据库自定义
- Architecture 4.3: API 模块 — `/api/v1/linkage`
- Architecture 2.3: 后端分层 — engines/ 目录

### 与后续 Story 的关系

- Story 9-2（消防分级联动策略）：使用本 Story 的引擎框架，添加消防专用策略和 YAML 预定义
- Story 9-3（智能故障诊断）：可通过事件总线接收告警事件
- Story 9-4（联动恢复流程）：扩展 LinkageExecution 添加恢复状态
- Story 9-5（事件时间线报告）：基于 LinkageExecution + LinkageLog 生成报告
- Story 9-6（控制命令分级确认）：MqttCommandHandler 的完整实现

### Project Structure Notes

- 后端新增: `engines/event_bus.py`, `engines/action_handlers.py`, `engines/linkage_engine.py`, `engines/__init__.py`
- 后端新增: `models/linkage.py`, `schemas/linkage.py`, `api/v1/linkage.py`
- 后端修改: `models/__init__.py`（注册模型）, `api/v1/__init__.py`（注册路由）, `main.py`（lifespan 集成）, `services/websocket.py`（新增 linkage 频道）
- 后端新增: `tests/test_linkage.py`
- 前端新增: `api/modules/linkage.ts`, `views/linkage/policy.vue`, `views/linkage/execution.vue`
- 前端修改: `router/index.ts`（新增路由）

### References

- [Source: architecture.md#7.1] 联动引擎架构
- [Source: architecture.md#7.2] 消防分级联动策略
- [Source: architecture.md#7.3] 动作类型注册表
- [Source: architecture.md#7.4] 消防信号最高优先级
- [Source: architecture.md#7.5] 联动策略配置方式
- [Source: architecture.md#4.3] API 模块列表 — `/api/v1/linkage`
- [Source: architecture.md#2.3] 后端分层 — engines/ 目录
- [Source: prd.md#FR36] 联动策略配置
- [Source: epic-8-retrospective.md] A1: 进程内 Pub/Sub + Redis 抽象层
- [Source: epic-8-retrospective.md] A2: 前后端枚举常量共享
- [Source: epic-8-retrospective.md] A3: value or fallback 必查

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (Sisyphus orchestrator + Momus code review)

### Debug Log References

- 代码审查发现 2 Critical + 3 High + 2 Medium 问题，全部修复
- CR#1 (Critical): 前端 priority 枚举与后端不一致 → 对齐为 fire_signal/critical/normal
- CR#2 (Critical): 前端 trigger_type 枚举与后端不一致 → 对齐为 alarm.triggered/alarm.resolved/device.offline
- CR#3 (High): ORM 对象缓存导致 detached instance 错误 → 改为 dict 缓存
- CR#4 (High): N+1 查询问题 → 添加 selectinload
- CR#5 (High): model 注释 partial_fail → partial_failure
- CR#6 (Medium): test_policy event_type 默认值 → Optional[str] = None

### Completion Notes List

- 7/7 后端测试通过 (pytest)
- 前端构建成功 (vite build)
- 事件总线使用 InMemoryEventBus（直接 dispatch，无 Queue），预留 Redis 抽象接口
- 5 种动作处理器已注册（AlarmNotify/Webhook 完整实现，Mqtt/VideoRecord/VideoPopup 占位）
- 10 个 REST API 端点，权限分级 (admin/operator/viewer)
- 前端策略管理页 + 执行日志页，2.5D 风格

### File List

**后端新增:**
- `backend/app/engines/event_bus.py` — 事件总线抽象层 + InMemoryEventBus
- `backend/app/engines/action_handlers.py` — 动作处理器抽象 + 5 种处理器 + 注册表
- `backend/app/engines/linkage_engine.py` — 联动引擎核心（条件评估 + 并行执行 + dict 缓存）
- `backend/app/models/linkage.py` — 4 个数据模型 (LinkagePolicy/Action/Execution/Log)
- `backend/app/schemas/linkage.py` — Pydantic v2 请求/响应 Schema
- `backend/app/api/v1/linkage.py` — 10 个 REST API 端点
- `backend/tests/test_linkage.py` — 7 个测试用例

**后端修改:**
- `backend/app/models/__init__.py` — 注册 4 个联动模型
- `backend/app/api/v1/__init__.py` — 注册联动路由
- `backend/app/main.py` — lifespan 集成（load_policies + subscribe）
- `backend/app/services/websocket.py` — 新增 "linkage" 频道 + broadcast_linkage()
- `backend/app/services/simulator.py` — 告警事件发布到事件总线
- `backend/requirements.txt` — 添加 httpx>=0.25.0

**前端新增:**
- `frontend/src/api/modules/linkage.ts` — TypeScript 接口 + 10 个 API 函数
- `frontend/src/views/linkage/policy.vue` — 联动策略管理页面
- `frontend/src/views/linkage/execution.vue` — 联动执行日志页面

**前端修改:**
- `frontend/src/router/index.ts` — 联动管理路由组
