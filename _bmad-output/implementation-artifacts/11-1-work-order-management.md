# Story 11-1: 工单管理

## Story

**As a** 运维工程师,
**I want** 通过系统创建和处理工单,
**So that** 运维工作有完整的流程记录和跟踪。

## Status: Done

## Implementation Notes

- **棕地增强**: 后端模型/Schema/API/服务层已存在（models/operation.py, schemas/operation.py, api/v1/operation.py, services/operation.py），路由已注册
- 本次增强内容:
  1. 新增 `accepted` 状态（已接单，在 assigned 和 processing 之间）
  2. 新增 `alarm_id`、`area_code` 字段到 WorkOrder 模型
  3. 新增 `accepted_at` 时间戳字段
  4. 新增状态转换校验（VALID_TRANSITIONS 映射表）
  5. 新增 accept（接单）和 close（关闭）API 端点
  6. 从 WorkOrderUpdate 中移除 status 字段（状态只能通过专用端点变更）
  7. 前端 API 模块已存在，新增 acceptWorkOrder、closeWorkOrder 函数
  8. 前端路由已存在，需创建 workorder.vue 页面
  9. 新增后端测试覆盖完整生命周期
- order_no 格式: WO-20260217-0001，当日序号通过查询当日最大序号 +1 实现
- 状态转换严格校验: pending→assigned→accepted→processing→completed→closed
- 每次状态变更自动写入 WorkOrderLog
- 告警自动创建工单在 Story 11-4 实现，本 Story 只提供 alarm_id 字段预留
- 工单审批流程在 Story 11-5 实现，本 Story 不涉及审批
