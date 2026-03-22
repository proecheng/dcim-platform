# 全系统数据链路一致性审计报告

**日期**: 2026-03-22
**审计范围**: Epic 1-36 全功能跨层数据链路一致性
**审计方法**: 三并行 Agent（后端/前端/跨层）+ 深度验证

---

## 发现与修复

### 已修复的 6 个问题

| # | 问题 | 严重性 | 修复文件 |
|---|------|--------|----------|
| 1 | 2个定时任务(channel_escalation_task、rollback_task)未在 shutdown 中 cancel | HIGH | `backend/app/main.py` |
| 2 | 前端缺少 `resolve_batch` WebSocket action 处理 | MEDIUM | `frontend/src/composables/useAlarm.ts` |
| 3 | 诊断消息共用 alarms 通道但被前端 `type !== 'alarm'` 静默丢弃 | MEDIUM | `frontend/src/composables/useAlarm.ts` |
| 4 | 前端 AlarmInfo 缺少 `source` 字段（后端 Story 35.3 新增） | LOW | `frontend/src/api/modules/alarm.ts` |
| 5 | 前端 Alarm store 接口有 3 个后端不存在的字段、缺少多个字段 | LOW | `frontend/src/stores/alarm.ts` |
| 6 | DataSource status 枚举值(5种)散落在 3 个文件无集中定义 | LOW | `backend/app/models/gateway.py` + 3个引用文件 |

### 修复详情

**#1 定时任务 cancel（HIGH）**
- `channel_escalation_task`（Story 34.5）和 `rollback_task`（Story 30.2）创建了 asyncio.create_task 但未在 shutdown 事件中 cancel
- 在 `soh_calculation_task.cancel()` 之后添加两行 cancel

**#2 resolve_batch 处理（MEDIUM）**
- 后端 gateway_monitor.py 在网关恢复时发送 `resolve_batch` action
- 前端 switch 中无此 case，批量恢复告警时前端不会刷新
- 添加 case 处理：重新拉取活跃告警列表 + 派发事件

**#3 诊断消息静默丢弃（MEDIUM）**
- Story 24.6 诊断系统通过 alarms 通道发送 diagnosis_alert/diagnosis_suggestion
- 前端 `if (message.type !== 'alarm') return` 直接丢弃
- 添加诊断消息判断，记录日志后 return（不干扰告警逻辑）

**#4 AlarmInfo source 字段（LOW）**
- 后端 Story 35.3 新增 `source` 字段标识告警来源
- 前端 AlarmInfo 接口缺少该字段

**#5 Alarm store 接口同步（LOW）**
- 移除: `process_remark`, `processed_by`, `processed_at`（后端无此字段）
- 添加: `alarm_no`, `alarm_type`, `ack_remark`, `resolve_remark`, `resolve_type`, `source`

**#6 DataSourceStatus 常量（LOW）**
- 5 种状态值散落在 communication_monitor.py、gateway_monitor.py、datasources.py
- 在 gateway.py 添加 `DataSourceStatus` 常量类，替换所有硬编码引用

---

## 验证为误报的项目（不修改）

| 项目 | 误报原因 |
|------|---------|
| AlarmStatistics 重复定义 | index.ts 已正确去重 |
| WebSocket 告警格式不一致 | 实际都通过 `broadcast_alarm()` 推送 |
| 通知系统与数据源告警不匹配 | 设计上数据源告警不进入通知流程 |
| NotificationPolicyItem 缺少 is_default | 实际已有 |
| Precool API 响应包装 | request.ts 拦截器已正确解包 |
| 负荷转移字段不对齐 | 实际完全一致 |

---

## 测试验证

- 后端 alarm 测试: **104 passed**
- 后端 gateway health 测试: **6 passed**
- 后端 communication monitor 测试: **4 passed**
- 前端类型检查: 无新增错误（已有错误与本次修改无关）
