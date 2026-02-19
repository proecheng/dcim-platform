# Story 9.6: 控制命令分级确认

Status: ready-for-dev

## Story

As a 运维工程师,
I want 系统对不同风险等级的控制命令执行不同的确认流程,
So that 高风险操作有足够的安全把关，低风险操作不影响效率。

## FR 追溯

- Architecture 4.5: 控制命令分级确认
- NFR-S4: 远程控制双重确认弹窗，关键操作需审批

## Acceptance Criteria

1. Given 运维工程师在前端发起控制命令（如调整空调温度、切断电源、开关门禁）
   When 命令风险等级为"普通"（如调整空调设定温度、开关照明）
   Then 前端弹出二次确认弹窗，用户确认后直接通过后端下发

2. Given 运维工程师在前端发起控制命令
   When 命令风险等级为"关键"（如切断回路电源、设备下架断电、UPS 切换）
   Then 前端提交审批请求，后端创建审批工单，审批人确认后才下发命令

3. Given 关键命令审批工单已创建
   When 审批超时（默认 30 分钟）
   Then 自动取消并通知发起人

4. Given 任何控制命令（无论级别）已执行
   Then 记录到操作审计日志（操作人、命令内容、目标设备、执行结果）

5. Given 管理员进入命令风险配置页面
   When 调整命令风险等级
   Then 配置立即生效，后续命令按新等级执行确认流程

## 现有代码分析

### 已有实现（直接复用）

| 组件 | 文件 | 说明 |
|------|------|------|
| 控制指令表 | models/system.py | ControlCommand(point_id, target_value, executed_by, status, result_message) |
| 操作日志表 | models/log.py | OperationLog(user_id, username, module, action, target_type, target_id, ...) |
| 系统配置表 | models/config.py | SystemConfig(config_group, config_key, config_value, value_type) |
| 系统配置 API | api/v1/config.py | get_configs, update_configs — 按 group 管理配置 |
| 依赖注入 | api/deps.py | require_operator, require_admin, require_viewer |
| 联动模型 | models/linkage.py | LinkagePolicy, LinkageAction — 动作类型参考 |
| 联动 API | api/v1/linkage.py | 联动管理端点 — API 模式参考 |

### 需要新增

| 组件 | 文件 | 说明 |
|------|------|------|
| 命令审批模型 | models/command.py | CommandApproval 表（审批工单） |
| 命令审计日志模型 | models/command.py | CommandAuditLog 表（命令级审计日志） |
| 命令 Schema | schemas/command.py | 命令提交、审批、审计日志的请求/响应 Schema |
| 命令服务 | services/command_service.py | 分级确认逻辑、审批流程、超时取消 |
| 命令 API | api/v1/command.py | 命令提交、审批管理、审计日志查询、风险配置 |
| 前端命令 API | api/modules/command.ts | 命令提交、审批、审计日志 API 函数 |
| 前端审批页面 | views/linkage/command.vue | 命令审批管理页面 |
| 路由配置 | router/index.ts | 添加 command 子路由 |
| 后端测试 | tests/test_command.py | 命令分级确认 API 测试 |

## Technical Implementation Notes

### 1. 数据模型设计

CommandApproval（命令审批工单表）字段：
- id: int — 主键
- command_type: str — 命令类型标识（如 power_off, ac_temp_set）
- risk_level: str — 风险等级: normal / critical
- target_device_id: int — 目标设备ID
- target_device_name: str — 目标设备名称
- command_content: JSON — 命令内容（参数）
- requester_id: int — 发起人ID
- requester_name: str — 发起人用户名
- approver_id: int (nullable) — 审批人ID
- approver_name: str (nullable) — 审批人用户名
- status: str — pending / approved / rejected / cancelled / timeout
- reject_reason: str (nullable) — 驳回原因
- timeout_minutes: int — 超时时间（分钟），默认 30
- created_at: datetime — 创建时间
- approved_at: datetime (nullable) — 审批时间
- executed_at: datetime (nullable) — 执行时间
- expired_at: datetime — 过期时间（created_at + timeout_minutes）

CommandAuditLog（命令审计日志表）字段：
- id: int — 主键
- command_type: str — 命令类型
- risk_level: str — 风险等级
- target_device_id: int — 目标设备ID
- target_device_name: str — 目标设备名称
- command_content: JSON — 命令内容
- operator_id: int — 操作人ID
- operator_name: str — 操作人用户名
- approval_id: int (nullable) — 关联审批ID（关键命令才有）
- result: str — success / failed / cancelled / timeout
- result_message: str (nullable) — 结果描述
- created_at: datetime — 记录时间

### 2. 风险等级配置

使用 SystemConfig 表存储风险等级配置：
- config_group: "command_risk"
- config_key: 命令类型标识（如 power_off, ac_temp_set）
- config_value: 风险等级（normal 或 critical）

默认风险等级映射：

| 命令类型 | 默认等级 | 说明 |
|---------|---------|------|
| ac_temp_set | normal | 调整空调温度 |
| light_switch | normal | 开关照明 |
| door_access | normal | 门禁开关 |
| power_off | critical | 切断回路电源 |
| ups_switch | critical | UPS 切换 |
| device_decommission | critical | 设备下架断电 |

### 3. API 端点设计

命令提交：
- POST /command/submit — 提交控制命令（自动判断风险等级）

审批管理：
- GET /command/approvals — 审批工单列表（分页+筛选）
- GET /command/approvals/{id} — 审批工单详情
- POST /command/approvals/{id}/approve — 批准审批
- POST /command/approvals/{id}/reject — 驳回审批

审计日志：
- GET /command/audit-logs — 审计日志列表（分页+筛选）

风险配置：
- GET /command/risk-configs — 获取风险等级配置列表
- PUT /command/risk-configs — 批量更新风险等级配置（管理员）

### 4. 命令提交流程

前端提交命令 -> POST /command/submit
  -> 查询 SystemConfig 获取该命令类型的风险等级
  -> 如果 risk_level == normal:
       -> 直接执行命令（模拟 MQTT 下发）
       -> 写入 CommandAuditLog
       -> 返回 { status: executed, message: 命令已下发 }
  -> 如果 risk_level == critical:
       -> 创建 CommandApproval（status=pending, expired_at=now+30min）
       -> 写入 CommandAuditLog（result=pending）
       -> 返回 { status: pending_approval, approval_id: N, message: 已提交审批 }

### 5. 审批超时处理

在 command_service.py 中提供 check_expired_approvals() 函数：
- 查询所有 status=pending 且 expired_at < now 的审批工单
- 将 status 更新为 timeout
- 更新对应的 CommandAuditLog result 为 timeout
- 返回超时数量

API 端点 GET /command/approvals 在查询前先调用此函数（惰性检查）。

### 6. 前端页面设计

views/linkage/command.vue:
- Tab 1: 命令审批 — 审批工单列表（待审批/已审批/已超时），审批操作按钮
- Tab 2: 审计日志 — 所有命令的审计日志列表，支持按时间/设备/操作人筛选
- Tab 3: 风险配置 — 命令类型风险等级配置表格，管理员可编辑

命令提交不在此页面，而是在设备详情页或其他操作入口通过弹窗触发。
本页面仅管理审批和查看日志。

## Adversarial Review Findings

| ID | 级别 | 问题 | 解决方案 |
|----|------|------|----------|
| M1 | Medium | models/system.py 已有 ControlCommand 和 OperationLog，但字段不匹配需求（缺少 risk_level, command_type 等），且 OperationLog 表名与 log.py 冲突 | 新模型放在独立的 models/command.py，不复用 system.py。新表名 command_approvals 和 command_audit_logs 无冲突 |
| M2 | Medium | 惰性超时检查在 GET /command/approvals 中执行，长时间无人查看则超时工单不会被标记 | 可接受 — 超时工单不会被执行（approve 端点也会检查过期），惰性检查足够 |
| L1 | Low | 风险配置 config_value 是 Text 类型，无枚举约束 | 在 service 层校验，只接受 normal 和 critical 两个值 |

## Dev Notes

- 消防联动（fire_signal）不走此流程，由联动引擎自动执行（Story 9-2 已实现）
- 本 Story 不实现真实 MQTT 下发，命令执行为模拟（记录日志+返回成功）
- 审批超时使用惰性检查（查询时检查），不需要后台定时任务
- 风险配置使用已有的 SystemConfig 表，config_group=command_risk
- 审计日志独立于 OperationLog，因为需要记录命令特有字段（command_content, target_device, result）
- 前端自动导入：ref, computed, onMounted 等无需 import
- Element Plus 组件自动导入

## Tasks

- [ ] Task 1: 创建命令模型 (models/command.py — CommandApproval, CommandAuditLog)
- [ ] Task 2: 创建命令 Schema (schemas/command.py — 请求/响应 Schema)
- [ ] Task 3: 创建命令服务 (services/command_service.py — 分级确认、审批、超时检查)
- [ ] Task 4: 创建命令 API (api/v1/command.py — 命令提交、审批管理、审计日志、风险配置)
- [ ] Task 5: 注册路由 (api/v1/__init__.py — 注册 command router)
- [ ] Task 6: 前端命令 API (api/modules/command.ts — 类型定义 + API 函数)
- [ ] Task 7: 前端审批管理页面 (views/linkage/command.vue — 审批+审计+风险配置)
- [ ] Task 8: 前端路由配置 (router/index.ts — 添加 command 子路由)
- [ ] Task 9: 后端测试 (tests/test_command.py)
