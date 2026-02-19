# Story 9.4: 联动恢复流程

Status: ready-for-dev

## Story

As a 运维工程师,
I want 在事件解除后执行联动恢复,
So that 设备可以安全有序地恢复到正常状态。

## FR 追溯

- FR38: 运维工程师可以执行联动恢复流程（逐项恢复设备到正常状态）
- Architecture 7.1: 联动引擎架构

## Acceptance Criteria

1. Given 消防联动已执行，现场确认安全
   When 运维工程师执行"联动恢复"
   Then 支持一键恢复（按预设顺序：门禁→照明→电源→空调→排烟→录像）
   And 支持逐项手动恢复（可跳过某些项或调整顺序）
   And 恢复过程中每步操作记录到事件日志

2. Given 联动执行记录存在
   When 运维工程师查看可恢复的执行记录
   Then 仅显示 status=completed 或 partial_failure 的执行记录
   And 已恢复的记录不再出现在待恢复列表中

3. Given 恢复流程正在执行
   When 某个恢复步骤失败
   Then 记录失败原因，继续执行后续步骤（不中断）
   And 最终状态标记为 partial_recovery

4. Given 恢复流程完成
   When 查看恢复记录
   Then 显示每个恢复步骤的执行时间、状态、操作人
   And 原始执行记录关联恢复记录

## 现有代码分析

### 已有实现（直接复用）

| 组件 | 文件 | 说明 |
|------|------|------|
| 联动执行记录 | `models/linkage.py` | LinkageExecution(status, event_id, policy_id), LinkageLog |
| 联动策略 | `models/linkage.py` | LinkagePolicy(actions), LinkageAction(action_type, action_config) |
| 联动引擎 | `engines/linkage_engine.py` | _execute_action(), _update_execution_status(), _update_log() |
| 动作处理器 | `engines/action_handlers.py` | ActionHandler, ActionResult, ActionHandlerRegistry |
| 联动 API | `api/v1/linkage.py` | 执行记录查询, 策略管理 |
| 联动 Schema | `schemas/linkage.py` | LinkageExecutionResponse, LinkageLogResponse |
| WebSocket | `services/websocket.py` | ws_manager.broadcast_linkage() |
| 前端联动 API | `api/modules/linkage.ts` | getLinkageExecutions(), getLinkageExecution() |
| 前端执行页面 | `views/linkage/execution.vue` | 执行记录列表+详情抽屉 |
| 依赖注入 | `api/deps.py` | require_operator, require_viewer |

### 需要新增

| 组件 | 文件 | 说明 |
|------|------|------|
| 恢复记录模型 | `models/linkage.py` | LinkageRecovery, LinkageRecoveryLog |
| 恢复 Schema | `schemas/linkage.py` | 新增恢复相关 Schema |
| 恢复 API | `api/v1/linkage.py` | 新增恢复相关端点 |
| 恢复引擎逻辑 | `engines/recovery_engine.py` | 新建 RecoveryEngine 类（审查修复 H2） |
| 前端恢复 API | `api/modules/linkage.ts` | 新增恢复相关 API 函数 |
| 前端恢复页面 | `views/linkage/recovery.vue` | 恢复管理页面 |
| 路由注册 | `router/index.ts` | 新增恢复页面路由 |

## Technical Design

### 恢复流程设计

联动恢复是联动执行的逆操作。消防联动执行了一系列动作（关空调、切电源、解锁门禁等），恢复流程按相反顺序逐项恢复设备到正常状态。

**预设恢复顺序**（与联动执行顺序相反）：
1. 门禁 — 恢复正常门禁控制（lock ACCESS_CONTROL）
2. 照明 — 关闭应急照明，恢复正常照明（deactivate EMERGENCY_LIGHTING）
3. 电源 — 恢复非关键电源（restore NON_CRITICAL_POWER）
4. 空调 — 恢复空调系统（start HVAC）
5. 排烟 — 关闭排烟风机（stop EXHAUST_FAN）
6. 录像 — 停止全区域录像（stop VIDEO_RECORD）

**恢复命令映射**（基于 fire_protection_policies.yaml 中的联动动作）：

| 联动动作 | 联动命令 | 恢复命令 | 恢复目标 |
|---------|---------|---------|---------|
| 关闭空调 | shutdown HVAC | start HVAC | 恢复空调 |
| 启动排烟 | start EXHAUST_FAN | stop EXHAUST_FAN | 关闭排烟 |
| 切断电源 | cutoff NON_CRITICAL_POWER | restore NON_CRITICAL_POWER | 恢复电源 |
| 解锁门禁 | unlock ACCESS_CONTROL | lock ACCESS_CONTROL | 恢复门禁 |
| 应急照明 | activate EMERGENCY_LIGHTING | deactivate EMERGENCY_LIGHTING | 关闭应急照明 |
| 全区域录像 | VIDEO_RECORD start | VIDEO_RECORD stop | 停止录像 |

### 数据模型

```python
# 新增到 models/linkage.py

class LinkageRecovery(Base):
    """联动恢复记录表"""
    __tablename__ = "linkage_recoveries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_id = Column(Integer, ForeignKey("linkage_executions.id"), nullable=False)
    operator = Column(String(50), nullable=False, comment="操作人")
    mode = Column(String(20), default="auto", comment="恢复模式: auto(一键)/manual(逐项)")
    status = Column(String(20), default="executing", comment="状态: executing/completed/partial_recovery/failed")
    started_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime, nullable=True)
    total_duration_ms = Column(Integer, nullable=True)

    logs = relationship("LinkageRecoveryLog", backref="recovery", lazy="selectin", cascade="all, delete-orphan")


class LinkageRecoveryLog(Base):
    """联动恢复步骤日志表"""
    __tablename__ = "linkage_recovery_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    recovery_id = Column(Integer, ForeignKey("linkage_recoveries.id"), nullable=False)
    step_order = Column(Integer, default=0, comment="恢复步骤顺序")
    action_type = Column(String(50), comment="动作类型")
    target_type = Column(String(50), comment="目标设备类型")
    recovery_command = Column(String(50), comment="恢复命令")
    action_config = Column(JSON, comment="恢复动作配置")
    status = Column(String(20), default="pending", comment="状态: pending/executing/success/failed/skipped")
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
```

### API 设计

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | /linkage/recoveries | 恢复记录列表 | viewer |
| GET | /linkage/recoveries/{id} | 恢复记录详情 | viewer |
| GET | /linkage/executions/recoverable | 可恢复的执行记录列表 | operator |
| POST | /linkage/executions/{id}/recover | 发起一键恢复 | operator |
| POST | /linkage/recoveries/{id}/step/{step_order}/execute | 手动执行单个恢复步骤 | operator |
| POST | /linkage/recoveries/{id}/step/{step_order}/skip | 跳过单个恢复步骤 | operator |

### 恢复步骤生成逻辑

从 LinkageExecution 的 trigger_event.payload 和关联的 LinkageLog 中提取已执行的动作，生成反向恢复步骤：

```python
# 恢复命令映射
RECOVERY_COMMAND_MAP = {
    ("MQTT_COMMAND", "shutdown"): "start",       # 关闭 → 启动
    ("MQTT_COMMAND", "start"): "stop",            # 启动 → 停止
    ("MQTT_COMMAND", "cutoff"): "restore",        # 切断 → 恢复
    ("MQTT_COMMAND", "unlock"): "lock",           # 解锁 → 上锁
    ("MQTT_COMMAND", "activate"): "deactivate",   # 激活 → 停用
    ("VIDEO_RECORD", None): "stop",               # 录像 → 停止
}

# 预设恢复顺序（越小越先执行）
RECOVERY_ORDER = {
    "ACCESS_CONTROL": 1,
    "EMERGENCY_LIGHTING": 2,
    "NON_CRITICAL_POWER": 3,
    "HVAC": 4,
    "EXHAUST_FAN": 5,
}
```

### 前端页面设计

**恢复管理页面** (`views/linkage/recovery.vue`)：
- 顶部：可恢复执行记录列表（筛选：状态、时间范围）
- 点击执行记录 → 展开恢复面板
  - 显示恢复步骤列表（步骤顺序、目标设备、恢复命令、状态）
  - "一键恢复"按钮 — 按预设顺序自动执行所有步骤
  - 每个步骤有"执行"和"跳过"按钮 — 支持逐项手动恢复
  - 恢复进度实时更新
- 底部：历史恢复记录列表

## Tasks

### Task 1: 数据模型 — LinkageRecovery + LinkageRecoveryLog

**文件**: `backend/app/models/linkage.py`

新增 LinkageRecovery 和 LinkageRecoveryLog 模型到现有 linkage.py 文件末尾。

**验收标准**:
- LinkageRecovery 包含: id, execution_id(FK), operator, mode, status, started_at, completed_at, total_duration_ms
- LinkageRecoveryLog 包含: id, recovery_id(FK), step_order, action_type, target_type, recovery_command, action_config(JSON), status, error_message, started_at, completed_at, duration_ms
- LinkageRecovery.logs relationship 配置正确
- 在 `models/__init__.py` 中注册导出

### Task 2: Schema — 恢复相关 Pydantic 模型

**文件**: `backend/app/schemas/linkage.py`

新增恢复相关 Schema 到现有文件末尾。

**验收标准**:
- RecoveryCreate: mode(auto/manual)
- RecoveryLogResponse: 包含所有字段, ConfigDict(from_attributes=True)
- RecoveryResponse: 包含所有字段 + logs 列表
- RecoveryStepExecuteRequest: 可选 action_config 覆盖

### Task 3: 恢复引擎逻辑

**文件**: `backend/app/engines/recovery_engine.py`（新建，审查修复 H2）

独立的恢复引擎，避免 linkage_engine.py 过于臃肿。

**验收标准**:
- `generate_recovery_steps(execution_id)` — 从 LinkageLog(status=success) 生成恢复步骤列表（审查修复 M1）
- `start_recovery(recovery_id)` — 用 asyncio.create_task 后台串行执行所有恢复步骤（审查修复 H3）
- `execute_single_step(recovery_id, step_order)` — 执行单个恢复步骤
- `skip_step(recovery_id, step_order)` — 跳过单个恢复步骤
- 恢复命令映射 RECOVERY_COMMAND_MAP：从 LinkageLog.action_config 提取 command/target_type（审查修复 C1）
- 恢复顺序 RECOVERY_ORDER 定义正确
- 跳过 ALARM_NOTIFY 和 VIDEO_POPUP 类型（审查修复 H1）
- 每个步骤执行通过 ActionHandler 处理（复用现有动作处理器）
- 步骤失败不中断后续步骤
- 恢复完成后更新 LinkageRecovery 状态和耗时
- WebSocket 广播恢复进度

### Task 4: API 端点

**文件**: `backend/app/api/v1/linkage.py`

在现有 linkage.py 中新增恢复相关端点。

**验收标准**:
- GET /linkage/executions/recoverable — 返回可恢复的执行记录（status in completed/partial_failure，且无关联恢复记录或恢复记录 status=failed）
- POST /linkage/executions/{id}/recover — 创建恢复记录 + 生成恢复步骤，mode=auto 时自动执行
- GET /linkage/recoveries — 恢复记录列表（分页+筛选）
- GET /linkage/recoveries/{id} — 恢复记录详情（含步骤日志）
- POST /linkage/recoveries/{id}/step/{step_order}/execute — 手动执行单步
- POST /linkage/recoveries/{id}/step/{step_order}/skip — 跳过单步
- 静态路由在参数化路由之前
- 权限: 查询 require_viewer, 操作 require_operator

### Task 5: 集成注册

**文件**: `backend/app/models/__init__.py`, `backend/app/api/v1/__init__.py`

**验收标准**:
- models/__init__.py 导出 LinkageRecovery, LinkageRecoveryLog
- 无需新增路由注册（恢复端点在现有 linkage router 中）

### Task 6: 前端 API 模块

**文件**: `frontend/src/api/modules/linkage.ts`

在现有 linkage.ts 中新增恢复相关类型和 API 函数。

**验收标准**:
- LinkageRecoveryLog 接口
- LinkageRecovery 接口
- getRecoverableExecutions() API
- createRecovery(executionId, mode) API
- getRecoveries(params) API
- getRecovery(id) API
- executeRecoveryStep(recoveryId, stepOrder) API
- skipRecoveryStep(recoveryId, stepOrder) API

### Task 7: 前端恢复页面

**文件**: `frontend/src/views/linkage/recovery.vue`

**验收标准**:
- 可恢复执行记录列表（el-table，含策略名称、事件ID、执行时间、状态）
- 点击记录展开恢复面板（el-drawer 或 el-dialog）
- 恢复步骤列表（步骤顺序、目标设备、恢复命令、状态标签）
- "一键恢复"按钮（确认弹窗后调用 createRecovery(id, 'auto')）
- 每个步骤"执行"/"跳过"按钮
- 历史恢复记录列表（底部 el-table）
- 恢复状态标签颜色映射

### Task 8: 路由注册

**文件**: `frontend/src/router/index.ts`

**验收标准**:
- 在联动管理路由组下新增恢复页面路由
- path: 'recovery', name: 'LinkageRecovery', meta: { title: '联动恢复', icon: 'RefreshRight' }

### Task 9: 后端测试

**文件**: `backend/tests/test_recovery.py`

**验收标准**:
- 测试恢复步骤生成（从执行记录生成正确的反向步骤）
- 测试恢复命令映射正确性
- 测试一键恢复 API（创建恢复记录 + 步骤）
- 测试逐项恢复（执行单步、跳过单步）
- 测试可恢复列表筛选（排除已恢复的记录）
- 测试恢复状态流转（executing → completed/partial_recovery）
- 测试步骤失败不中断后续步骤
- 测试恢复记录详情查询

## 审查修复

| # | 严重度 | 问题 | 修复 |
|---|--------|------|------|
| C1 | Critical | RECOVERY_COMMAND_MAP 的 key 需要从 LinkageLog.action_config 中提取 command 和 target_type，VIDEO_RECORD 用 action_type 匹配 | 恢复步骤生成从 LinkageLog.action_config 提取 command/target_type，VIDEO_RECORD 按 action_type 匹配 |
| C2 | Critical | 可恢复列表筛选条件有歧义（多次恢复尝试场景） | 排除存在 status in (completed, partial_recovery, executing) 的恢复记录的执行记录 |
| H1 | High | ALARM_NOTIFY 类型不需要恢复（通知不可逆），应排除 | 恢复步骤生成时跳过 ALARM_NOTIFY 和 VIDEO_POPUP 类型 |
| H2 | High | 恢复逻辑放 linkage_engine.py 会导致类过于臃肿 | 新建 engines/recovery_engine.py，包含 RecoveryEngine 类 |
| H3 | High | 一键恢复串行执行可能导致 HTTP 超时 | POST /recover 用 create_task 后台执行，API 立即返回 recovery_id |
| M1 | Medium | 恢复步骤应仅从 LinkageLog(status=success) 生成，不依赖 trigger_event | 明确：只有成功执行的动作才需要恢复 |

## Dev Notes

- 恢复端点全部放在现有 `linkage.py` router 中，前缀 `/api/v1/linkage/`，无需新增 router
- 恢复步骤通过 ActionHandler 执行，复用 MQTT_COMMAND / VIDEO_RECORD 等现有处理器
- 恢复命令是联动命令的逆操作，通过 RECOVERY_COMMAND_MAP 映射
- 一键恢复按 RECOVERY_ORDER 顺序串行执行（非并行），确保设备安全有序恢复
- 逐项恢复允许运维工程师跳过某些步骤或调整执行顺序
- ALARM_NOTIFY 和 VIDEO_POPUP 类型不生成恢复步骤（通知不可逆）（审查修复 H1）
- 恢复步骤仅从 LinkageLog(status=success) 生成（审查修复 M1）
- 恢复引擎独立为 engines/recovery_engine.py（审查修复 H2）
- 一键恢复用 asyncio.create_task 后台执行，API 立即返回（审查修复 H3）
- 可恢复列表排除存在 status in (completed, partial_recovery, executing) 的恢复记录（审查修复 C2）
