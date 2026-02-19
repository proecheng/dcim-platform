# Story 12-2: 智能摘要面板

## Story

As a 运维主管,
I want 登录后看到需要我决策的事项摘要,
So that 我可以快速了解当前最重要的待办事项。

## Status: Draft

## Brownfield Analysis

Existing data sources for pending items:
- **告警**: `Alarm` model — active/acknowledged alarms (`api/v1/alarm.py` GET `/active`, `/count`)
- **工单审批**: `WorkOrderApproval` — pending approvals (`api/v1/operation.py` GET `/approvals`)
- **工单**: `WorkOrder` — pending/processing orders (`api/v1/operation.py` GET `/workorders`)
- **巡检**: `InspectionTask` — overdue tasks (`api/v1/operation.py` GET `/tasks`)
- **资产维保**: `Asset` — warranty expiring (`api/v1/asset.py` GET `/warranty-expiring`)
- **容量**: capacity alerts (`api/v1/capacity.py` GET `/alerts`)

No existing summary/dashboard endpoint aggregating these.

## Acceptance Criteria

1. Given 运维主管调用摘要 API, When 系统聚合各模块待处理事项, Then 返回按优先级排序的摘要列表
2. And 每项包含类型、标题、优先级、推荐操作、跳转链接
3. And 包含告警升级、工单审批、逾期巡检、维保到期等类别

## Technical Design

### New API endpoint in `api/v1/report.py`:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/summary-panel` | 获取智能摘要面板数据 |

Returns a list of `SummaryItem` sorted by priority:
```json
{
  "items": [
    {
      "type": "alarm",
      "title": "3条紧急告警待处理",
      "priority": 1,
      "count": 3,
      "action": "查看告警",
      "link": "/alarm"
    }
  ],
  "total_items": 5,
  "generated_at": "..."
}
```

### Data collection:
1. Active critical/major alarms → priority 1
2. Pending work order approvals → priority 2
3. Overdue inspection tasks → priority 2
4. Pending work orders → priority 3
5. Active minor/info alarms → priority 4

### Frontend types in `api/modules/report.ts`

### Tests: 5 tests in existing `test_report_auto.py`
