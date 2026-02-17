# Story 5.5: 告警升级规则与前端管理

Status: ready-for-dev

## Story

As a 系统管理员,
I want 配置告警升级规则并通过前端管理告警规则,
So that 超时未处理的告警可以自动升级通知上级。

## Acceptance Criteria (验收标准)

1. **AC-1: 告警升级规则模型** — 新增 `AlarmEscalation` 数据库模型，支持配置：源告警级别、超时时间（分钟）、升级后告警级别、通知对象（用户ID列表）、是否启用。支持 Alembic 迁移
2. **AC-2: 告警升级规则 CRUD API** — 新增 REST API 端点：创建/查询列表/查询详情/更新/删除/启用禁用切换 告警升级规则。需要 operator 权限
3. **AC-3: 告警升级引擎** — 后台定时任务（每 60 秒）扫描所有 active 状态且超时未处理的告警，匹配升级规则后自动升级告警级别。升级后更新 Alarm 记录的 alarm_level，并通过 WebSocket alarms 通道广播升级事件（action: "escalate"）
4. **AC-4: 升级通知** — 告警升级时，在 Alarm 记录中追加升级备注（如"[自动升级] 从 minor 升级为 major，超时 30 分钟未处理"）。通过 WebSocket 推送升级通知到前端
5. **AC-5: 前端升级规则管理** — 在告警管理页面新增"升级规则"Tab，支持升级规则的列表展示、创建、编辑、删除、启用/禁用操作。表格列：规则名称、源告警级别、超时时间、升级后级别、通知对象、启用状态、操作
6. **AC-6: 前端升级通知展示** — 告警列表中，被升级的告警显示升级标记（如"已升级"Tag）。useAlarm composable 处理 WebSocket 的 escalate action，更新告警列表
7. **AC-7: 阈值规则前端管理增强** — 告警管理页面的"告警规则"Tab 已有复合规则管理。新增"阈值规则"Tab（或在现有 Tab 中增加子 Tab），展示 AlarmThreshold 列表，支持创建/编辑/删除/启用禁用操作（复用现有 threshold API）
8. **AC-8: 后端测试** — 测试升级规则 CRUD API、测试升级引擎定时扫描逻辑、测试升级后告警级别变更
9. **AC-9: 前端构建验证** — `npm run build` 构建成功

## Tasks / Subtasks (任务分解)

- [ ] Task 1: 后端 — 告警升级规则模型 (AC: #1)
  - [ ] 1.1 在 `backend/app/models/alarm.py` 新增 `AlarmEscalation` 模型：
    - `id`: 主键
    - `rule_name`: 规则名称（String(100), not null）
    - `source_level`: 源告警级别（String(20), not null, 如 "minor"/"major"）
    - `timeout_minutes`: 超时时间（Integer, not null, 单位分钟）
    - `target_level`: 升级后告警级别（String(20), not null）
    - `notify_user_ids`: 通知对象（String(500), 逗号分隔的用户ID，如 "1,2,3"。避免 JSON Text 与 Pydantic List[int] 的序列化问题）
    - `is_enabled`: 是否启用（Boolean, default True）
    - `description`: 规则描述（Text, optional）
    - `created_at`: 创建时间
    - `updated_at`: 更新时间
  - [ ] 1.2 创建 Alembic 迁移：`alembic revision --autogenerate -m "add_alarm_escalation_table"`
  - [ ] 1.3 执行迁移：`alembic upgrade head`

- [ ] Task 2: 后端 — 告警升级 Schema (AC: #2)
  - [ ] 2.1 在 `backend/app/schemas/alarm.py` 新增：
    - `AlarmEscalationBase`: rule_name, source_level, timeout_minutes, target_level, notify_user_ids(List[int]), is_enabled, description
    - `AlarmEscalationCreate(AlarmEscalationBase)`: 创建
    - `AlarmEscalationUpdate`: 所有字段 Optional
    - `AlarmEscalationInfo(AlarmEscalationBase)`: 含 id, created_at, updated_at, from_attributes=True
  - [ ] 2.2 `AlarmEscalationInfo` 需要 `@field_validator('notify_user_ids', mode='before')` 将逗号分隔字符串 "1,2,3" 解析为 `List[int]`：
    ```python
    @field_validator('notify_user_ids', mode='before')
    @classmethod
    def parse_notify_ids(cls, v):
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(',') if x.strip()] if v else []
        return v or []
    ```
  - [ ] 2.3 `AlarmEscalationCreate` / `AlarmEscalationUpdate` 需要在 API 层将 `List[int]` 转为逗号分隔字符串再写入 DB：在 API 端点中 `data.notify_user_ids = ','.join(str(x) for x in data.notify_user_ids)` 后再赋值给模型
  - [ ] 2.4 在 `AlarmInfo` schema 中新增 `escalation_count: Optional[int] = None` 和 `escalated_from: Optional[str] = None` 和 `escalation_remark: Optional[str] = None`（CRITICAL — 不加这些字段，前端永远收不到升级信息）

- [ ] Task 3: 后端 — 告警升级规则 CRUD API (AC: #2)
  - [ ] 3.1 新建 `backend/app/api/v1/escalation.py` 路由文件
  - [ ] 3.2 实现 `GET /api/v1/escalations` — 列表查询，支持 source_level/is_enabled 筛选，分页
  - [ ] 3.3 实现 `POST /api/v1/escalations` — 创建升级规则
  - [ ] 3.4 实现 `GET /api/v1/escalations/{id}` — 查询详情
  - [ ] 3.5 实现 `PUT /api/v1/escalations/{id}` — 更新升级规则
  - [ ] 3.6 实现 `DELETE /api/v1/escalations/{id}` — 删除升级规则
  - [ ] 3.7 实现 `PUT /api/v1/escalations/{id}/toggle` — 启用/禁用切换
  - [ ] 3.8 在 `backend/app/api/v1/__init__.py` 注册路由：prefix="/escalations", tags=["告警升级"]
  - [ ] 3.9 权限要求：查询需 viewer，创建/编辑/删除需 operator

- [ ] Task 4: 后端 — 告警升级引擎 (AC: #3, #4)
  - [ ] 4.1 确认 `backend/app/engines/__init__.py` 存在（Story 5-2 已创建，但需验证）。新建 `backend/app/engines/escalation_engine.py`
  - [ ] 4.2 实现 `check_escalations(session: AsyncSession)` 异步函数：
    - 查询所有启用的升级规则
    - 对每条规则，查询匹配的 active 告警（`alarm_level == source_level` 且 `created_at` 距今超过 `timeout_minutes`）。注意：查询条件 `alarm_level == source_level` 本身就是防重复升级的机制 — 升级后 alarm_level 变了，不再匹配同一规则
    - 对匹配的告警，更新 `alarm_level` 为 `target_level`，更新 `escalated_from` 为当前 `alarm_level`（即 source_level），`escalation_count += 1`
    - 写入 `escalation_remark`（专用字段，不要写 ack_remark — 那是操作员确认备注）：`"[自动升级] 从 {source_level} 升级为 {target_level}，超时 {timeout_minutes} 分钟未处理"`
    - 收集广播消息到列表，`await session.commit()` 成功后再逐条广播（5-4 经验：broadcast 必须在 commit 后）
    - 广播格式：`ws_manager.broadcast_alarm({"action": "escalate", "id": alarm_id, "alarm_level": target_level, "previous_level": source_level})`
    - 构建广播消息时使用本地变量（alarm_id, target_level 等），不要在 commit 后读取 ORM 属性
  - [ ] 4.3 在 Alarm 模型中新增 3 个字段：
    - `escalation_count`（Integer, default 0）— 升级次数
    - `escalated_from`（String(20), nullable）— 升级前的级别（每次升级更新为当前级别，支持多步升级链：minor→major→critical）
    - `escalation_remark`（Text, nullable）— 升级备注（专用字段，不复用 ack_remark）
  - [ ] 4.4 创建 Alembic 迁移添加 escalation_count、escalated_from、escalation_remark 字段
  - [ ] 4.5 多步升级支持：不要用 `escalated_from is not None` 作为跳过条件。查询条件 `alarm_level == source_level` 已经天然防止同规则重复升级。例如：Rule A (minor→major, 30min) + Rule B (major→critical, 60min)，告警先被 A 升级为 major，然后 B 可以继续匹配升级为 critical

- [ ] Task 5: 后端 — 升级引擎定时调度 (AC: #3)
  - [ ] 5.1 在 `backend/app/main.py` 的 `lifespan()` 中新增升级引擎定时任务（每 60 秒）：
    ```python
    async def _escalation_engine_loop():
        while True:
            await asyncio.sleep(60)
            try:
                async with async_session() as session:
                    await check_escalations(session)
            except Exception as e:
                logger.warning("告警升级检查失败: %s", e)
    escalation_task = asyncio.create_task(_escalation_engine_loop())
    ```
  - [ ] 5.2 导入：`from .engines.escalation_engine import check_escalations`
  - [ ] 5.3 在 lifespan yield 后取消：`escalation_task.cancel()`
  - [ ] 5.4 添加启动日志：`print("告警升级引擎已启动，每60秒检查一次")`

- [ ] Task 6: 前端 — 升级规则 API 模块 (AC: #5)
  - [ ] 6.1 在 `frontend/src/api/modules/alarm.ts` 的 `AlarmInfo` 接口中新增字段：`escalation_count?: number`、`escalated_from?: string | null`、`escalation_remark?: string | null`（CRITICAL — 不加这些字段前端无法显示升级信息）
  - [ ] 6.2 在 `frontend/src/api/modules/alarm.ts` 中新增升级规则相关接口和类型：
    - `AlarmEscalationInfo` 接口
    - `AlarmEscalationCreateParams` / `AlarmEscalationUpdateParams` 接口
    - `getEscalations(params)` / `createEscalation(data)` / `updateEscalation(id, data)` / `deleteEscalation(id)` / `toggleEscalation(id)` 函数
  - [ ] 6.3 在 `frontend/src/api/modules/index.ts` 中导出新增的升级规则 API

- [ ] Task 7: 前端 — 升级规则管理 Tab (AC: #5, #6)
  - [ ] 7.1 在 `frontend/src/views/alarm/index.vue` 新增"升级规则"Tab（在现有"告警规则"Tab 后面）
  - [ ] 7.2 实现升级规则列表表格：规则名称、源告警级别（Tag）、超时时间（分钟）、升级后级别（Tag）、通知对象、启用状态（Switch）、操作（编辑/删除）
  - [ ] 7.3 实现创建/编辑升级规则对话框：表单包含 rule_name、source_level（下拉）、timeout_minutes（数字输入）、target_level（下拉）、notify_user_ids（多选用户）、is_enabled（开关）、description（文本域）
  - [ ] 7.4 source_level 和 target_level 下拉选项：critical/major/minor/info，且 target_level 必须高于 source_level（critical > major > minor > info）
  - [ ] 7.5 通知对象选择：调用用户列表 API 获取可选用户

- [ ] Task 8: 前端 — 告警升级展示 (AC: #6)
  - [ ] 8.1 在 `frontend/src/views/alarm/index.vue` 的告警列表中，对 `escalated_from` 不为空的告警显示"已升级"Tag（橙色），tooltip 显示 `escalation_remark`
  - [ ] 8.2 在 `frontend/src/composables/useAlarm.ts` 中新增 `case 'escalate':` 处理（在现有 switch/case 块中，约第 214 行前插入）。处理逻辑必须遵循双更新模式：(1) 更新 `activeAlarms` 数组中对应告警的 `alarm_level` 和 `escalated_from`；(2) 调用 `alarmStore.updateAlarm(data.id, { alarm_level: data.alarm_level, escalated_from: data.previous_level })`；(3) 触发 `window.dispatchEvent(new Event('alarm-status-changed'))` 刷新列表
  - [ ] 8.3 在 `frontend/src/stores/alarm.ts` 的 Alarm 接口中新增 `escalation_count?: number`、`escalated_from?: string | null`、`escalation_remark?: string | null`

- [ ] Task 9: 前端 — 阈值规则管理 Tab (AC: #7)
  - [ ] 9.1 在 `frontend/src/views/alarm/index.vue` 新增"阈值规则"Tab（name="thresholds"）
  - [ ] 9.2 实现阈值规则列表表格：复用现有 threshold API（`getThresholdList`、`createThreshold`、`updateThreshold`、`deleteThreshold` — 注意函数名是 `getThresholdList` 不是 `getThresholds`），展示 point_name、threshold_type、threshold_value、alarm_level、delay_seconds、is_enabled、操作
  - [ ] 9.3 实现创建/编辑阈值规则对话框：复用现有 threshold API。启用/禁用使用 `updateThreshold(id, { is_enabled: !current })` — 阈值 API 没有专用 toggle 端点
  - [ ] 9.4 支持按设备类型、阈值类型、启用状态筛选

- [ ] Task 10: 后端测试 (AC: #8)
  - [ ] 10.1 新建 `backend/tests/test_escalation.py`
  - [ ] 10.2 测试升级规则 CRUD：创建/查询/更新/删除/切换启用
  - [ ] 10.3 测试升级引擎：超时告警被正确升级
  - [ ] 10.4 测试升级引擎：未超时告警不被升级
  - [ ] 10.5 测试升级引擎：已升级告警不重复升级
  - [ ] 10.6 测试升级引擎：禁用规则不生效

- [ ] Task 11: 前端构建验证 (AC: #9)
  - [ ] 11.1 `npm run build` 构建成功

## Dev Notes (开发指南)

### 1. 文件位置

```
backend/app/models/alarm.py                        # 修改 — 新增 AlarmEscalation 模型、Alarm 新增 escalation_count/escalated_from/escalation_remark 字段
backend/app/schemas/alarm.py                       # 修改 — 新增升级规则 Schema
backend/app/api/v1/escalation.py                   # 新建 — 升级规则 CRUD API
backend/app/api/v1/__init__.py                     # 修改 — 注册 escalation 路由
backend/app/engines/escalation_engine.py           # 新建 — 升级引擎
backend/app/main.py                                # 修改 — 新增升级引擎定时任务
backend/alembic/versions/xxx_add_alarm_escalation.py  # 新建 — 数据库迁移
backend/tests/test_escalation.py                   # 新建 — 升级测试
frontend/src/api/modules/alarm.ts                  # 修改 — 新增升级规则 API
frontend/src/views/alarm/index.vue                 # 修改 — 新增升级规则 Tab、阈值规则 Tab、升级标记展示
frontend/src/composables/useAlarm.ts               # 修改 — 处理 escalate action
frontend/src/stores/alarm.ts                       # 修改 — Alarm 接口新增字段
```

### 2. 现有基础设施

**告警管理页面已有 Tab 结构**（alarm/index.vue）：
- Tab "告警记录"（name="records"）— 告警记录列表
- Tab "告警规则"（name="rules"）— AlarmRule 复合规则管理（已实现 CRUD）
- Tab "告警屏蔽"（name="shields"）— AlarmShield 屏蔽管理（已实现 CRUD）
- 新增 Tab "升级规则"（name="escalations"）和 "阈值规则"（name="thresholds"）

**告警 API 模块**（api/modules/alarm.ts）已有：
- `getAlarmRules` / `createAlarmRule` / `updateAlarmRule` / `deleteAlarmRule` / `toggleAlarmRule`
- `getAlarmShields` / `createAlarmShield` / `deleteAlarmShield`
- 升级规则 API 按相同模式新增

**阈值 API 模块**（api/modules/threshold.ts）已有完整 CRUD：
- `getThresholds` / `createThreshold` / `updateThreshold` / `deleteThreshold`
- 阈值规则 Tab 直接复用这些 API

**WebSocket broadcast_alarm 消息格式**（websocket.py 第56-66行）：
```python
message = {"type": "alarm", "action": action, "data": {...}}
```
升级事件使用 `action: "escalate"`

**useAlarm.ts 已有 switch/case 处理**（第185-188行）：
- `case 'ack'` / `case 'resolve'` / `case 'update'` / `case 'batch_ack'`
- 新增 `case 'escalate'` 处理

### 3. 告警级别优先级

```
critical (紧急) > major (重要) > minor (次要) > info (提示)
```

升级规则验证：target_level 必须高于 source_level。后端 API 创建/更新时校验。

### 4. 升级引擎防重复升级 & 多步升级

```python
# 查询条件 alarm_level == source_level 天然防止同规则重复升级
# 升级后 alarm_level 变了，不再匹配同一规则
# 多步升级示例：
#   Rule A: minor → major (30min)
#   Rule B: major → critical (60min)
#   告警创建 30min 后被 A 升级为 major（escalated_from="minor"）
#   再过 60min 被 B 升级为 critical（escalated_from="major"）
# 不要用 escalated_from is not None 作为跳过条件！
```

### 5. notify_user_ids 存储

使用 String(500) 字段存储逗号分隔字符串（如 `"1,2,3"`），Schema 中用 `List[int]` 类型。`AlarmEscalationInfo` 通过 `@field_validator` 将字符串解析为列表，API 创建/更新时将列表转为字符串再写入 DB。避免 JSON Text 与 Pydantic 的序列化冲突。

### 6. escalation_remark 专用字段

不要复用 `ack_remark`（那是操作员确认备注，写入会覆盖用户数据）。使用专用的 `escalation_remark` 字段存储升级备注。

### 7. 关键约束

- **Alembic 迁移**: 一个迁移包含：建 alarm_escalations 表 + 给 alarms 表加 escalation_count/escalated_from/escalation_remark 字段
- **engines/__init__.py**: 确认 `backend/app/engines/__init__.py` 存在（Story 5-2 已创建）
- **权限控制**: 升级规则管理需要 operator 权限，查看需要 viewer 权限
- **WebSocket action**: 使用 "escalate"，前端 useAlarm.ts 的 switch/case 需要新增处理，遵循双更新模式（activeAlarms + alarmStore + event dispatch）
- **broadcast 时序**: 升级引擎必须在 session.commit() 成功后再广播（5-4 经验）
- **ORM session expire**: 升级引擎 commit 后不要读取 ORM 属性，使用已知值构建广播消息
- **AlarmInfo schema**: 必须新增 escalation_count/escalated_from/escalation_remark 字段，否则 API 不返回升级信息
- **前端 AlarmInfo 接口**: api/modules/alarm.ts 和 stores/alarm.ts 都需要新增升级字段
- **自动导入**: 前端 Vue API 无需手动 import（unplugin-auto-import），但自定义组件需要手动 import
- **告警级别下拉**: 复用现有的级别选项（critical/major/minor/info），与告警规则 Tab 保持一致
- **阈值 API 函数名**: `getThresholdList`（不是 getThresholds）、`createThreshold`、`updateThreshold`、`deleteThreshold`
- **阈值无 toggle 端点**: 启用/禁用使用 `updateThreshold(id, { is_enabled: !current })`

### 8. Story 5.2/5.3/5.4 经验教训

- broadcast_alarm() 从 data dict 提取 action 到消息顶层：`{type: "alarm", action: "xxx", data: {...}}`
- 前端 useAlarm.ts 的 alarmStore 需要在函数顶层获取，不能在 case 内部获取
- ORM commit 后属性可能过期，广播消息用已知值
- 通信监控广播应在 commit 后发送（5-4 经验）
- 前端自定义组件需要手动 import（unplugin-auto-import 不覆盖）

### References

- [Source: models/alarm.py] Alarm 模型（第28行）、AlarmRule 模型（第58行）、AlarmShield 模型（第72行）
- [Source: schemas/alarm.py] AlarmRuleBase/Create/Update/Info（第131-162行）— 升级规则 Schema 按此模式
- [Source: api/v1/alarm.py] 告警规则 CRUD 路由模式
- [Source: views/alarm/index.vue] Tab 结构（第153行 告警规则 Tab）、规则 CRUD 对话框模式
- [Source: composables/useAlarm.ts] WebSocket action switch/case（第185行）
- [Source: api/modules/alarm.ts] 规则 API 函数模式（第213-251行）
- [Source: api/modules/threshold.ts] 阈值 CRUD API（第55-170行）
- [Source: main.py] 定时任务模式（第174-182行 告警引擎刷新、第186-195行 通信监控）
- [Source: services/websocket.py] broadcast_alarm 消息格式（第56-66行）
- [Source: prd.md] FR33（第762行）：告警升级规则；FR87（第855行）：告警规则前端管理

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
