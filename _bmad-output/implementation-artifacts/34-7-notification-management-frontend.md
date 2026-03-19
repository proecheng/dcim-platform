# Story 34.7: 通知管理前端

Status: done

## Story

As a 运维管理员,
I want 在前端统一管理通知策略、查看通知记录、配置渠道参数和用户联系方式,
So that 我能掌握通知系统的运行状态并灵活调整配置。

## Acceptance Criteria

1. **Given** 管理员进入用户编辑页 **When** 切换到"通知联系方式"Tab **Then** 可管理该用户的通知联系方式（CRUD + 从账户导入）
2. **Given** 管理员进入通知策略页 **When** 创建/编辑策略 **Then** 可视化配置时段（含跨午夜）、选择渠道、选择通知对象（按站点过滤）
3. **Given** 用户进入通知记录页 **When** 查看记录 **Then** 按时间/渠道/状态/级别筛选，查看投递链路
4. **Given** 管理员进入渠道配置页 **When** 查看渠道状态 **Then** 可查看各渠道启用/健康状态并测试发送
5. **Given** viewer 角色访问通知管理 **When** 查看页面 **Then** 仅显示通知记录 Tab（只读），策略管理和渠道配置 Tab 不可见

## Tasks / Subtasks

- [x] Task 1: 后端通知记录查询 API (AC: #3, #5)
  - [x] 1.1 在 `backend/app/api/v1/notification.py` 新增 `GET /v1/notification/records` 分页查询端点
  - [x] 1.2 支持筛选参数：channel_type, status, alarm_level, start_time(datetime), end_time(datetime)
  - [x] 1.3 使用 outerjoin(Alarm) 获取 alarm_level；创建 `NotificationRecordInfo` response schema
  - [x] 1.4 权限：`require_viewer`（所有登录用户可查看记录）
  - [x] 1.5 创建 `backend/tests/api/test_notification_records.py` — 分页、筛选、alarm_level JOIN、权限测试
- [x] Task 2: 前端 API 模块 (AC: #1~#4)
  - [x] 2.1 创建 `frontend/src/api/modules/notification.ts` — 统一通知 API 模块
  - [x] 2.2 定义 TypeScript 接口：NotificationPolicyForm, NotificationRecordQuery, NotificationRecordItem, ChannelStatusItem, ContactForm
  - [x] 2.3 包含：策略 CRUD、记录查询、渠道状态/测试、用户联系方式 CRUD
- [x] Task 3: 通知管理页面 — 主入口 + 三个 Tab (AC: #2~#5)
  - [x] 3.1 创建 `frontend/src/views/system/notification.vue` — 通知管理主页面
  - [x] 3.2 Tab 1: 通知策略管理（admin only）— 表格 + 新增/编辑对话框，含表单验证规则
  - [x] 3.3 Tab 2: 通知记录（所有用户可见）— 只读表格 + 筛选 + 分页
  - [x] 3.4 Tab 3: 渠道状态（admin only）— 渠道卡片 + 测试发送对话框
- [x] Task 4: 用户编辑扩展 — 通知联系方式 Tab (AC: #1)
  - [x] 4.1 在 `UserManagement.vue` 用户编辑对话框中新增"通知联系方式"Tab（仅编辑模式，新增用户不显示）
  - [x] 4.2 对话框宽度调整为 680px；联系方式表格 + 新增/编辑/删除
  - [x] 4.3 "从账户导入"按钮，一键复制 User.email/phone
- [x] Task 5: 路由 + 权限 + 排除路径 (AC: #5)
  - [x] 5.1 在 router/index.ts 的 system children 中添加通知管理路由
  - [x] 5.2 策略管理/渠道配置仅 admin 可见（v-if），通知记录所有用户可见
  - [x] 5.3 在 `request.ts` 的 `excludedPaths` 中确认 `/v1/notification/` 已包含，如缺失则添加

## Dev Notes

### 路由规划

```
/system/notification — 通知管理主页面（三个 Tab）
  Tab 1: 通知策略 (admin only)
  Tab 2: 通知记录 (所有登录用户)
  Tab 3: 渠道状态 (admin only)
```

非 admin 用户进入页面时，activeTab 默认为 "records"。

### 后端新增 API

```python
# backend/app/api/v1/notification.py — 新增端点

from datetime import datetime
from app.models.alarm import Alarm

@router.get("/records", summary="查询通知记录")
async def list_notification_records(
    channel_type: Optional[str] = None,
    status: Optional[str] = None,
    alarm_level: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user = Depends(require_viewer),
    session = Depends(get_db),
):
    """分页查询通知记录，支持多维度筛选"""
    # 基础查询 — outerjoin Alarm 获取 alarm_level
    query = (
        select(
            NotificationRecord,
            Alarm.alarm_level.label("alarm_level"),
        )
        .outerjoin(Alarm, NotificationRecord.alarm_id == Alarm.id)
        .order_by(NotificationRecord.id.desc())
    )

    if channel_type:
        query = query.where(NotificationRecord.channel_type == channel_type)
    if status:
        query = query.where(NotificationRecord.status == status)
    if alarm_level:
        query = query.where(Alarm.alarm_level == alarm_level)
    if start_time:
        query = query.where(NotificationRecord.created_at >= start_time)
    if end_time:
        query = query.where(NotificationRecord.created_at <= end_time)

    # 总数
    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar() or 0

    # 分页
    result = await session.execute(query.offset((page - 1) * page_size).limit(page_size))
    rows = result.all()

    items = []
    for record, al_level in rows:
        items.append(NotificationRecordInfo(
            id=record.id,
            alarm_id=record.alarm_id,
            alarm_level=al_level,
            user_id=record.user_id,
            policy_id=record.policy_id,
            channel_type=record.channel_type,
            platform=record.platform,
            contact_value=record.contact_value,
            content_summary=record.content_summary,
            status=record.status,
            retry_count=record.retry_count,
            error_message=record.error_message,
            sent_at=record.sent_at,
            created_at=record.created_at,
        ))

    return {"items": items, "total": total, "page": page, "page_size": page_size}
```

### NotificationRecordInfo Schema

```python
# backend/app/schemas/notification_record.py — 新建

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class NotificationRecordInfo(BaseModel):
    id: int
    alarm_id: Optional[int] = None
    alarm_level: Optional[str] = None  # 来自 JOIN Alarm 表
    user_id: Optional[int] = None
    policy_id: Optional[int] = None
    channel_type: str
    platform: Optional[str] = None
    contact_value: str
    content_summary: Optional[str] = None
    status: str
    retry_count: int = 0
    error_message: Optional[str] = None
    sent_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
```

### 前端 TypeScript 接口

```typescript
// frontend/src/api/modules/notification.ts

import request from '@/utils/request'

// ===== 类型定义 =====

export interface NotificationPolicyItem {
  id: number
  name: string
  site_id: number | null
  alarm_level: string
  time_range_start: string | null
  time_range_end: string | null
  channels: string[]
  notify_user_ids: number[]
  is_enabled: boolean
  channel_escalation_enabled: boolean
  escalation_timeout_minutes: number | null
  escalation_channel_order: string[] | null
  is_default: boolean
  created_at: string
}

export interface NotificationPolicyForm {
  name: string
  site_id: number | null
  alarm_level: string
  time_range_start: string | null
  time_range_end: string | null
  channels: string[]
  notify_user_ids: number[]
  is_enabled: boolean
  channel_escalation_enabled: boolean
  escalation_timeout_minutes: number | null
  escalation_channel_order: string[] | null
}

export interface NotificationRecordItem {
  id: number
  alarm_id: number | null
  alarm_level: string | null
  user_id: number | null
  policy_id: number | null
  channel_type: string
  platform: string | null
  contact_value: string
  content_summary: string | null
  status: string
  retry_count: number
  error_message: string | null
  sent_at: string | null
  created_at: string | null
}

export interface NotificationRecordQuery {
  channel_type?: string
  status?: string
  alarm_level?: string
  start_time?: string
  end_time?: string
  page?: number
  page_size?: number
}

export interface ChannelStatusItem {
  channel_type: string
  enabled: boolean
  healthy: boolean
}

export interface ContactItem {
  id: number
  user_id: number
  channel_type: string
  platform: string | null
  contact_value: string
  is_enabled: boolean
}

export interface ContactForm {
  channel_type: string
  platform: string | null
  contact_value: string
  is_enabled: boolean
}

// ===== 通知策略 =====
export function getPolicies(params?: { site_id?: number; alarm_level?: string }) {
  return request.get('/v1/notification/policies', { params })
}
export function createPolicy(data: NotificationPolicyForm) {
  return request.post('/v1/notification/policies', data)
}
export function updatePolicy(id: number, data: Partial<NotificationPolicyForm>) {
  return request.put(`/v1/notification/policies/${id}`, data)
}
export function deletePolicy(id: number) {
  return request.delete(`/v1/notification/policies/${id}`)
}

// ===== 通知记录 =====
export function getRecords(params?: NotificationRecordQuery) {
  return request.get('/v1/notification/records', { params })
}

// ===== 渠道状态 =====
export function getChannelStatus(): Promise<ChannelStatusItem[]> {
  return request.get('/v1/notification/channels')
}
export function testChannel(data: { channel_type: string; contact_value: string }) {
  return request.post('/v1/notification/channels/test', data)
}

// ===== 用户联系方式 =====
export function getUserContacts(userId: number): Promise<ContactItem[]> {
  return request.get(`/v1/users/${userId}/notification-contacts`)
}
export function createContact(userId: number, data: ContactForm) {
  return request.post(`/v1/users/${userId}/notification-contacts`, data)
}
export function updateContact(userId: number, contactId: number, data: Partial<ContactForm>) {
  return request.put(`/v1/users/${userId}/notification-contacts/${contactId}`, data)
}
export function deleteContact(userId: number, contactId: number) {
  return request.delete(`/v1/users/${userId}/notification-contacts/${contactId}`)
}
export function importFromProfile(userId: number) {
  return request.post(`/v1/users/${userId}/notification-contacts/import-from-profile`)
}
```

### 策略编辑对话框

**关键字段：**

| 字段 | 组件 | 说明 |
|------|------|------|
| name | el-input | 策略名称 |
| site_id | el-select | 站点选择（可选，null=全局） |
| alarm_level | el-select | 告警级别（critical/major/minor/info） |
| time_range_start/end | el-time-picker | 生效时段（HH:mm 格式） |
| channels | el-checkbox-group | 通知渠道多选（sms/email/im/voice） |
| notify_user_ids | el-select multiple | 通知对象（按站点权限过滤用户列表） |
| is_enabled | el-switch | 启用状态 |
| channel_escalation_enabled | el-switch | 渠道升级开关 |
| escalation_timeout_minutes | el-input-number | 升级超时（分钟） |
| escalation_channel_order | el-select multiple | 升级渠道顺序 |

**表单验证规则：**
- `name`: required, 1-100 字符
- `alarm_level`: required
- `channels`: required, 至少选一个
- `notify_user_ids`: required, 至少选一个
- `time_range_start` 和 `time_range_end`: 要么都填要么都不填（自定义 validator）
- `escalation_timeout_minutes`: 当 `channel_escalation_enabled=true` 时 required, min=1

### 用户联系方式 Tab

在 UserManagement.vue 的编辑对话框中新增第二个 Tab：

- **仅编辑模式显示**：新增用户时（isEdit=false）不显示联系方式 Tab，因为用户尚未创建，无 userId
- **对话框宽度**：从 520px 调整为 680px 以容纳联系方式表格
- 切换到联系方式 Tab 时自动加载当前用户的联系方式数据

### 权限控制

| 功能 | 权限 | 前端实现 | 后端保护 |
|------|------|----------|----------|
| 通知策略管理 | admin | `v-if="isAdmin"` Tab 隐藏 | 现有 API 已有 `require_admin` |
| 渠道状态/测试 | admin | `v-if="isAdmin"` Tab 隐藏 | 现有 API 已有 `require_admin` |
| 通知记录查看 | 所有登录用户 | 默认可见 Tab | records API 使用 `require_viewer` |
| 用户联系方式 | admin 或本人 | 编辑对话框内 Tab | 现有 API 已有权限检查 |

非 admin 用户进入页面时，activeTab 默认设为 "records"（因为 policies/channels Tab 不可见）。

### UI 状态处理

- **空数据**: 使用 `el-empty` 组件展示提示
- **加载中**: 表格使用 `v-loading` 指令
- **渠道测试**: 成功 `ElMessage.success("发送成功")`，失败 `ElMessage.error(res.error_message)`
- **API 错误**: 统一走 request.ts 拦截器（已有）
- **策略列表暂不分页**: 通知策略数量有限（通常几十条），不加分页

### request.ts 排除路径

检查 `request.ts` 的 `excludedPaths`，确保 `/v1/notification/` 已包含。如缺失则添加，防止 site_id 自动注入。`/v1/users/` 已在排除列表中，联系方式 API 不受影响。

### 文件清单

| 操作 | 文件 |
|------|------|
| 新建 | `backend/app/schemas/notification_record.py` — NotificationRecordInfo schema |
| 修改 | `backend/app/api/v1/notification.py` — 新增 GET /records 端点 |
| 新建 | `backend/tests/api/test_notification_records.py` — records API 测试 |
| 新建 | `frontend/src/api/modules/notification.ts` — 通知 API 模块（含 TS 接口） |
| 新建 | `frontend/src/views/system/notification.vue` — 通知管理主页面 |
| 修改 | `frontend/src/views/settings/UserManagement.vue` — 编辑对话框增加联系方式 Tab |
| 修改 | `frontend/src/router/index.ts` — 添加通知管理路由 |
| 修改 | `frontend/src/utils/request.ts` — 确认排除路径（如需） |

### 测试场景

1. 通知策略 CRUD — 创建/编辑/删除策略，表格刷新正确
2. 策略编辑 — 时段选择、渠道多选、通知对象选择、表单验证
3. 通知记录 — 筛选条件（时间/渠道/状态/级别）正确过滤
4. 通知记录 — 分页正确（page/page_size）
5. 通知记录 — alarm_level 通过 JOIN 正确显示
6. 渠道状态 — 显示各渠道启用/健康状态
7. 渠道测试 — 输入联系方式后测试发送，显示成功/失败结果
8. 用户联系方式 — 新增/编辑/删除联系方式
9. 用户联系方式 — 从账户导入功能
10. 权限 — viewer/operator 仅看到通知记录 Tab
11. 权限 — admin 可见全部三个 Tab
12. 编辑对话框 — 新增用户时不显示联系方式 Tab，编辑时显示
13. 后端 records API — 分页 + 各筛选参数 + 权限 require_viewer
14. 空状态 — 各表格空数据时显示 el-empty 提示
