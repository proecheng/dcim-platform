# Story 5.3: 告警处理闭环

Status: ready-for-dev

## Story

As a 运维工程师,
I want 对告警进行确认、处理和解除操作,
So that 告警有完整的处理记录和闭环流程。

## Acceptance Criteria (验收标准)

1. **AC-1: 告警确认（单条）** — 运维工程师在告警列表选择一条 active 状态的告警，点击"确认"按钮，弹出确认对话框（含备注输入），提交后告警状态变为 acknowledged，记录确认人（当前登录用户 ID）、确认时间、确认备注。前端列表实时刷新状态和统计数字
2. **AC-2: 批量确认** — 运维工程师勾选多条 active 状态的告警，点击"批量确认"按钮，弹出确认对话框（含备注输入），提交后所有选中告警状态变为 acknowledged。后端 `PUT /api/v1/alarms/batch-acknowledge` 接口需修复：当前接收裸参数，需改为 Pydantic schema；前端发送字段名 `ids` 需改为 `alarm_ids`
3. **AC-3: 告警处理（记录处理过程）** — 运维工程师对 active 或 acknowledged 状态的告警，点击"处理"按钮，弹出处理对话框，可输入处理过程描述（process_remark）。提交后告警记录处理过程，但不改变状态（处理过程是中间记录，不等于解决）。需要在 Alarm 模型新增 `process_remark` 和 `processed_by`、`processed_at` 字段
4. **AC-4: 告警解除（手动）** — 运维工程师对非 resolved 状态的告警，点击"解除"按钮，弹出解除对话框（含备注和解决类型选择），提交后告警状态变为 resolved，记录解决人、解决时间、解决备注、解决类型（manual）、持续时间（duration_seconds = now - created_at）
5. **AC-5: 告警统计筛选** — 告警统计 API `GET /api/v1/alarms/statistics` 支持按级别（alarm_level）、设备类型（device_type，通过 JOIN Point 表）、时间段（start_time/end_time）筛选。返回新增 `by_device_type` 字段
6. **AC-6: 告警记录永久保留** — 告警记录不设自动删除策略，resolved 状态的告警保留在数据库中。导出 API 支持导出全部历史告警
7. **AC-7: 前端告警列表增强** — 告警列表表格增加列：触发值、阈值、确认时间、解决时间、持续时间。支持按设备类型筛选。操作列增加"处理"按钮
8. **AC-8: WebSocket 状态同步** — 告警确认/处理/解除操作后，通过 WebSocket alarms 通道广播状态变更消息，前端 `useAlarm.ts` 收到后更新本地状态。同时 `views/alarm/index.vue` 监听自定义事件 `alarm-status-changed` 触发 `loadAlarms()` 重新加载列表数据，实现"无需手动刷新"
9. **AC-9: 后端测试** — 测试告警确认、批量确认、处理、解除 API，测试统计筛选

## Tasks / Subtasks (任务分解)

- [ ] Task 1: 后端 — Alarm 模型扩展 (AC: #3)
  - [ ] 1.1 在 `backend/app/models/alarm.py` 的 Alarm 类新增字段：`process_remark`（Text）、`processed_by`（Integer, ForeignKey users.id）、`processed_at`（DateTime）
  - [ ] 1.2 创建 Alembic 迁移：`alembic revision --autogenerate -m "add alarm process fields"`
  - [ ] 1.3 执行迁移：`alembic upgrade head`

- [ ] Task 2: 后端 — Schema 扩展 (AC: #3, #5, #7)
  - [ ] 2.1 在 `backend/app/schemas/alarm.py` 的 AlarmInfo 中新增 Optional 字段：`process_remark: Optional[str]`、`processed_by: Optional[int]`、`processed_at: Optional[datetime]`
  - [ ] 2.2 新增 `AlarmProcess` schema：`process_remark: str`（必填）
  - [ ] 2.3 新增 `BatchAcknowledgeRequest` schema：`alarm_ids: List[int]`、`remark: Optional[str] = None`（放在 schemas/alarm.py 中，不要内联在 API 文件里）
  - [ ] 2.4 修改 `AlarmStatistics` schema，新增 `by_device_type: Dict[str, int] = {}` 字段
  - [ ] 2.5 更新 `alarm.py` API 文件的 import 列表，添加 `AlarmProcess`、`BatchAcknowledgeRequest`
  - [ ] 2.6 在 `alarm.py` API 文件顶部添加 `import logging` 和 `logger = logging.getLogger(__name__)`

- [ ] Task 3: 后端 — 告警处理 API (AC: #3, #8)
  - [ ] 3.1 在 `backend/app/api/v1/alarm.py` 新增 `PUT /{alarm_id}/process` 端点（放在 `resolve_alarm` 之后、`batch_acknowledge` 之前）
  - [ ] 3.2 校验告警状态为 active 或 acknowledged（resolved 不允许处理）
  - [ ] 3.3 更新 `process_remark`、`processed_by`（current_user.id）、`processed_at`（datetime.now()）
  - [ ] 3.4 广播 `action: "update"` 消息，使用已知值构建 dict（不从 commit 后的 ORM 对象读取属性，避免 session expire 风险）

- [ ] Task 4: 后端 — 修复批量确认 API (AC: #2, #8)
  - [ ] 4.1 修改 `PUT /batch-acknowledge` 端点，使用 `BatchAcknowledgeRequest` schema 接收请求体
  - [ ] 4.2 使用 `result.rowcount` 获取实际更新行数，返回准确的确认数量
  - [ ] 4.3 广播 `action: "batch_ack"` 消息，包含更新的告警 ID 列表

- [ ] Task 5: 后端 — 确认/解除 API 增加 WebSocket 广播 (AC: #1, #4, #8)
  - [ ] 5.1 在 `acknowledge_alarm()` 的 `await db.commit()` 之后，广播 `action: "ack"` 消息（与前端现有 `case 'ack'` 匹配）
  - [ ] 5.2 在 `resolve_alarm()` 的 `await db.commit()` 之后，广播 `action: "resolve"` 消息（与前端现有 `case 'resolve'` 匹配）
  - [ ] 5.3 广播消息使用已知值构建（alarm_id 参数、current_user.id、datetime.now().isoformat()），不从 commit 后的 ORM 对象读取
  - [ ] 5.4 导入 ws_manager：`from ...services.websocket import ws_manager`

- [ ] Task 6: 后端 — 告警统计增强 (AC: #5)
  - [ ] 6.1 修改 `GET /statistics` 端点，新增 `device_type` 和 `alarm_level` 查询参数
  - [ ] 6.2 通过 JOIN Point 表获取 device_type，支持按 device_type 分组统计
  - [ ] 6.3 返回结果新增 `by_device_type` 字段

- [ ] Task 7: 前端 — alarm store 扩展 (AC: #8)
  - [ ] 7.1 在 `frontend/src/stores/alarm.ts` 的 `Alarm` 接口新增字段：`acknowledged_by?: number`、`acknowledged_at?: string`、`process_remark?: string`、`processed_by?: number`、`processed_at?: string`、`resolved_by?: number`、`resolved_at?: string`、`duration_seconds?: number`、`trigger_value?: number`、`threshold_value?: number`
  - [ ] 7.2 新增 `updateAlarm(id: number, fields: Partial<Alarm>)` 方法：查找 activeAlarms 中对应 id 的告警，用 Object.assign 更新字段；如果 status 变为 resolved 则从列表移除；最后调用 updateCount()
  - [ ] 7.3 在 return 中暴露 `updateAlarm`

- [ ] Task 8: 前端 — useAlarm.ts WebSocket 消息处理增强 (AC: #8)
  - [ ] 8.1 将 `alarmStore` 从 `handleNewAlarm` 内部局部获取提升到 `useAlarm()` 函数顶层：`const alarmStore = useAlarmStore()`
  - [ ] 8.2 在 `handleAlarmMessage` 的 switch 中新增 `case 'update'` 分支：更新 activeAlarms 中对应告警字段，调用 `alarmStore.updateAlarm(data.id, data)`
  - [ ] 8.3 新增 `case 'batch_ack'` 分支：遍历 `data.alarm_ids`，对每个 id 调用 `handleAlarmAck(id)`
  - [ ] 8.4 在 ack/update/resolve/batch_ack 的 case 末尾触发 `window.dispatchEvent(new Event('alarm-status-changed'))`，通知 index.vue 刷新

- [ ] Task 9: 前端 — views/alarm/index.vue 监听 WebSocket 刷新 (AC: #8)
  - [ ] 9.1 在 `index.vue` 中引入 `useAlarm` composable（`autoFetch: false, autoSubscribe: true, playSound: false, showNotification: false`）
  - [ ] 9.2 在 onMounted 中添加 `window.addEventListener('alarm-status-changed', handleAlarmStatusChanged)`
  - [ ] 9.3 `handleAlarmStatusChanged` 调用 `loadAlarms()` 和 `loadAlarmCount()`
  - [ ] 9.4 在 onUnmounted 中清理事件监听

- [ ] Task 10: 前端 — 告警列表 UI 增强 (AC: #7, #1, #3, #4)
  - [ ] 10.1 告警表格增加列：trigger_value、threshold_value、acknowledged_at、resolved_at、duration_seconds（格式化显示）
  - [ ] 10.2 操作列增加"处理"按钮（active/acknowledged 状态显示）
  - [ ] 10.3 新增处理对话框（ElDialog），包含 process_remark 文本域
  - [ ] 10.4 修改确认操作：从直接调用 API 改为弹出 ElDialog，增加备注输入
  - [ ] 10.5 修改解除操作：弹出 ElDialog，增加备注和解决类型选择（manual/timeout）
  - [ ] 10.6 筛选条件增加设备类型下拉（从 point 列表提取 device_type 去重）
  - [ ] 10.7 duration_seconds 列格式化显示（如 "2小时30分"）

- [ ] Task 11: 前端 — API 模块补充 (AC: #3)
  - [ ] 11.1 在 `frontend/src/api/modules/alarm.ts` 新增 `processAlarm(id, data)` 函数
  - [ ] 11.2 新增 `AlarmProcessParams` 接口：`process_remark: string`
  - [ ] 11.3 修复 `batchAcknowledgeAlarms` 函数的请求体格式，使用 `{ alarm_ids: ids, remark }` 匹配后端

- [ ] Task 12: 后端测试 (AC: #9)
  - [ ] 12.1 创建 `backend/tests/test_alarm_api.py`
  - [ ] 12.2 测试 `PUT /{id}/acknowledge` — 确认 active 告警成功，确认非 active 告警返回 400
  - [ ] 12.3 测试 `PUT /{id}/process` — 处理 active/acknowledged 告警成功，处理 resolved 告警返回 400
  - [ ] 12.4 测试 `PUT /{id}/resolve` — 解除告警成功，解除已解决告警返回 400，验证 duration_seconds 计算
  - [ ] 12.5 测试 `PUT /batch-acknowledge` — 批量确认成功，验证只更新 active 状态的告警，验证返回实际更新行数
  - [ ] 12.6 测试 `GET /statistics` — 验证按 device_type 和 alarm_level 筛选

- [ ] Task 13: 前端构建验证
  - [ ] 13.1 `npm run build` 构建成功

## Dev Notes (开发指南)

### 1. 文件位置

```
backend/app/models/alarm.py                        # 修改 — Alarm 模型新增 process 字段
backend/app/schemas/alarm.py                       # 修改 — 新增 AlarmProcess/BatchAcknowledgeRequest schema，扩展 AlarmInfo/AlarmStatistics
backend/app/api/v1/alarm.py                        # 修改 — 新增 process 端点，修复 batch-acknowledge，增加 WS 广播，添加 logger
backend/app/services/websocket.py                  # 复用 — broadcast_alarm() 方法（Story 5.2 已修复 dict copy）
backend/tests/test_alarm_api.py                    # 新建 — 告警 API 测试
frontend/src/stores/alarm.ts                       # 修改 — Alarm 接口扩展，新增 updateAlarm 方法
frontend/src/composables/useAlarm.ts               # 修改 — 新增 update/batch_ack 消息处理，alarmStore 提升到函数顶层
frontend/src/views/alarm/index.vue                 # 修改 — 列表增强、处理对话框、筛选增强、WebSocket 刷新
frontend/src/api/modules/alarm.ts                  # 修改 — 新增 processAlarm API，修复 batchAcknowledge 请求体
```

### 2. WebSocket action 命名规范（CRITICAL — 必须与前端匹配）

`useAlarm.ts` 第 181-191 行的 `handleAlarmMessage` 已有 switch/case：

| 操作 | 后端广播 action | 前端 case | 说明 |
|------|----------------|-----------|------|
| 确认告警 | `"ack"` | `case 'ack'`（第185行，已存在） | 不要用 "update"！ |
| 处理告警 | `"update"` | `case 'update'`（新增） | 新增处理分支 |
| 解除告警 | `"resolve"` | `case 'resolve'`（第188行，已存在） | 已存在 |
| 批量确认 | `"batch_ack"` | `case 'batch_ack'`（新增） | 新增批量分支 |

### 3. 避免 ORM session expire 风险（CRITICAL）

`broadcast_alarm()` 的消息 dict 必须使用已知值构建，不要从 `await db.commit()` 之后的 ORM 对象读取属性：

```python
# 正确：使用函数参数和局部变量
await ws_manager.broadcast_alarm({
    "id": alarm_id,                          # 函数参数
    "status": "acknowledged",                # 已知常量
    "acknowledged_by": current_user.id,      # 依赖注入对象
    "acknowledged_at": datetime.now().isoformat(),
    "action": "ack",
})

# 错误：从 commit 后的 ORM 对象读取（可能触发 lazy load 报错）
await ws_manager.broadcast_alarm({
    "id": alarm.id,              # alarm 可能已 expired
    "alarm_no": alarm.alarm_no,  # 可能触发 lazy load 报错
})
```

### 4. Schema 分离原则

所有 Pydantic schema 定义在 `schemas/alarm.py` 中，不要在 API 文件中内联定义：

```python
# schemas/alarm.py 中新增：
class AlarmProcess(BaseModel):
    """处理告警"""
    process_remark: str

class BatchAcknowledgeRequest(BaseModel):
    """批量确认告警"""
    alarm_ids: List[int]
    remark: Optional[str] = None
```

### 5. 前端双重状态管理桥接方案（解决 index.vue 与 useAlarm.ts 数据源分离问题）

`index.vue` 的数据来自 `getAlarmList()` API 调用，`useAlarm.ts` 维护 WebSocket 实时状态。两者是独立的数据源。

桥接方案：`useAlarm.ts` 在处理 ack/update/resolve/batch_ack 消息后，触发自定义事件：

```typescript
// useAlarm.ts 中每个 case 末尾：
window.dispatchEvent(new Event('alarm-status-changed'))
```

```typescript
// index.vue 中监听：
import { useAlarm } from '@/composables/useAlarm'
const { } = useAlarm({ autoFetch: false, autoSubscribe: true, playSound: false, showNotification: false })

const handleAlarmStatusChanged = () => {
  loadAlarms()
  loadAlarmCount()
}
onMounted(() => {
  window.addEventListener('alarm-status-changed', handleAlarmStatusChanged)
})
onUnmounted(() => {
  window.removeEventListener('alarm-status-changed', handleAlarmStatusChanged)
})
```

### 6. 前端 useAlarm.ts alarmStore 提升

当前 `alarmStore` 只在 `handleNewAlarm` 内部（第109行）局部获取。需提升到 `useAlarm()` 函数顶层：

```typescript
export function useAlarm(options: UseAlarmOptions = {}) {
  const alarmStore = useAlarmStore()  // 提升到这里
  // ... 其余代码 ...
  // handleNewAlarm 中删除局部的 const alarmStore = useAlarmStore()
```

### 7. 批量确认返回实际更新行数

```python
result = await db.execute(update(Alarm).where(...).values(...))
await db.commit()
actual_count = result.rowcount
return {"message": f"已确认 {actual_count} 条告警", "count": actual_count}
```

### 8. 前端 duration_seconds 格式化

```typescript
function formatDuration(seconds: number | null): string {
  if (!seconds) return '-'
  if (seconds < 60) return `${seconds}秒`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}分${seconds % 60}秒`
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  return `${hours}小时${mins}分`
}
```

### 9. 关键约束

- **不新增数据库表**: 仅在现有 Alarm 表新增 3 个字段
- **不破坏现有 API**: 所有现有端点保持向后兼容，新增字段为 Optional
- **Schema 分离**: 所有 Pydantic schema 定义在 `schemas/alarm.py` 中
- **WebSocket action 命名**: 必须与前端 `useAlarm.ts` 的 switch/case 匹配（ack/update/resolve/batch_ack）
- **ORM session expire**: broadcast_alarm 的消息 dict 使用已知值构建
- **自动导入**: 前端 Vue API 无需手动 import（unplugin-auto-import）
- **Alembic 迁移**: 新增字段必须通过 Alembic 迁移，兼容 SQLite
- **权限控制**: 确认/处理/解除需要 operator 权限，查看需要 viewer 权限
- **告警记录永久保留**: 不添加任何自动清理逻辑

### 10. Story 5.2 经验教训

- `broadcast_alarm()` 从 data dict 提取 action 到消息顶层（第58-64行），构建 `{type: "alarm", action: "xxx", data: {...}}`
- `broadcast_alarm()` 内部用 dict comprehension 排除 action 字段（不再 pop），无 mutation 风险
- alarm store 的 `addAlarm` 有去重逻辑（相同 id 不重复添加），列表上限 200 条
- `useAlarm.ts` 的计数使用 `Math.max(0, count - 1)` 防止负数
- async/await 处理 play() 声音播放

### References

- [Source: models/alarm.py] Alarm 模型（status: active/acknowledged/resolved/ignored, acknowledged_by, resolved_by, duration_seconds）
- [Source: schemas/alarm.py] AlarmInfo, AlarmAcknowledge, AlarmResolve, AlarmStatistics schema
- [Source: api/v1/alarm.py] 现有告警 API（acknowledge 第346行, resolve 第378行, batch-acknowledge 第414行, statistics 第139行）
- [Source: services/websocket.py] broadcast_alarm()（第56-66行）：提取 action 到消息顶层
- [Source: composables/useAlarm.ts] handleAlarmMessage（第176-192行）：switch on action — 'new'(182), 'ack'(185), 'resolve'(188)
- [Source: stores/alarm.ts] Alarm 接口（第4-12行，需扩展），addAlarm/removeAlarm（需新增 updateAlarm）
- [Source: views/alarm/index.vue] 告警页面（数据来自 API 调用非 store，需桥接 WebSocket 事件）
- [Source: api/modules/alarm.ts] batchAcknowledgeAlarms（第116-118行发送 {ids, ...data}，需改为 {alarm_ids}）

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
