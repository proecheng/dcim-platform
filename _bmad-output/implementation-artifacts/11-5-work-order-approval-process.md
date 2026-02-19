# Story 11-5: 工单审批流程

## Story

As a 运维主管,
I want 关键操作工单需要审批才能执行,
So that 高风险操作有管理层把关，降低误操作风险。

**FR 追溯:** FR68（审批部分）

---

## 状态: 已审查

## 设计

### 概述

为工单系统增加审批流程。当工单类型为"变更请求"时，工单从"已接单"状态进入"处理中"前需要审批。审批人可批准或驳回，驳回需填写原因。审批超时自动升级。审批记录完整保存。

### 新增模型: WorkOrderApproval

在 `models/operation.py` 中新增:

```python
class ApprovalStatus(str, PyEnum):
    """审批状态枚举"""
    pending = "待审批"
    approved = "已批准"
    rejected = "已驳回"
    timeout = "已超时"
    escalated = "已升级"

class WorkOrderApproval(Base):
    __tablename__ = "work_order_approvals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=False, comment="工单ID")
    approver = Column(String(100), nullable=False, comment="审批人")
    status = Column(Enum(ApprovalStatus), default=ApprovalStatus.pending, comment="审批状态")
    reason = Column(Text, comment="审批意见/驳回原因")
    timeout_hours = Column(Integer, default=24, comment="超时时间(小时)")
    escalate_to = Column(String(100), comment="超时升级审批人")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    resolved_at = Column(DateTime, comment="审批完成时间")
```

### 新增 Schema

在 `schemas/operation.py` 中新增:
- WorkOrderApprovalCreate: `{order_id, approver, timeout_hours?, escalate_to?}`
- WorkOrderApprovalResponse: 完整审批记录
- ApproveRequest: `{reason?}` — 批准请求
- RejectRequest: `{reason}` — 驳回请求（reason 必填）

### 新增 API 端点

在 `api/v1/operation.py` 中新增:

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | /workorders/{id}/submit-approval | 提交审批（创建审批记录） | require_operator |
| GET | /approvals | 获取审批列表（支持 status 过滤） | require_viewer |
| GET | /approvals/{id} | 获取审批详情 | require_viewer |
| POST | /approvals/{id}/approve | 批准审批 | require_operator |
| POST | /approvals/{id}/reject | 驳回审批 | require_operator |

### 业务逻辑

#### 提交审批 (POST /workorders/{id}/submit-approval)
1. 校验工单存在且状态为"已接单"
2. 校验工单类型为"变更请求"（只有变更请求需要审批）
3. 校验该工单没有进行中的审批（status=待审批）
4. 创建 WorkOrderApproval 记录
5. 添加工单日志："提交审批，审批人: xxx"
6. 返回审批记录

#### 批准审批 (POST /approvals/{id}/approve)
1. 校验审批存在且状态为"待审批"
2. 检查是否超时（超时则标记为"已超时"并拒绝操作）
3. 更新审批状态为"已批准"，记录 resolved_at
4. 自动将关联工单从"已接单"转为"处理中"，记录 started_at
5. 添加工单日志："审批通过: xxx"
6. 返回审批记录

#### 驳回审批 (POST /approvals/{id}/reject)
1. 校验审批存在且状态为"待审批"
2. reason 必填
3. 更新审批状态为"已驳回"，记录 reason 和 resolved_at
4. 工单状态保持"已接单"不变（可重新提交审批）
5. 添加工单日志："审批驳回: xxx，原因: yyy"
6. 返回审批记录

#### 审批列表 (GET /approvals)
- 支持 status 过滤
- 支持 order_id 过滤
- 按 created_at 降序
- 惰性检查超时：查询时检查 pending 审批是否超时

#### 超时处理
- 在列表查询和详情查询时惰性检查
- 如果 `now() > created_at + timeout_hours` 且 status 为"待审批":
  - 如果有 escalate_to：状态改为"已升级"，自动创建新审批记录给 escalate_to
  - 如果没有 escalate_to：状态改为"已超时"
- 添加工单日志记录超时/升级事件

### 前端 API

在 `api/modules/operation.ts` 中新增:
- WorkOrderApproval 接口
- submitApproval(orderId, data) 函数
- getApprovals(params) 函数
- getApprovalDetail(id) 函数
- approveApproval(id, data) 函数
- rejectApproval(id, data) 函数

### 不需要独立前端页面

审批功能集成到现有工单详情页面中，不需要独立的审批管理页面。审批列表可通过 API 查询。

### 测试用例

1. test_submit_approval — 提交审批成功
2. test_submit_approval_wrong_status — 非"已接单"状态提交审批失败
3. test_submit_approval_wrong_type — 非"变更请求"类型提交审批失败
4. test_submit_approval_duplicate — 重复提交审批失败
5. test_list_approvals — 获取审批列表
6. test_list_approvals_filter_status — 按状态过滤审批列表
7. test_approve_approval — 批准审批成功，工单自动转为处理中
8. test_reject_approval — 驳回审批成功，reason 必填
9. test_reject_approval_no_reason — 驳回审批无 reason 失败
10. test_approve_already_resolved — 批准已处理的审批失败
11. test_approval_timeout — 超时审批自动标记
12. test_approval_escalation — 超时升级到上级审批人
