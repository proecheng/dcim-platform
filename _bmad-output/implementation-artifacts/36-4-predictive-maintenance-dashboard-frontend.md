# Story 36.4: 预测性维护仪表盘前端

Status: ready-for-dev

## Story

As a 运维主管,
I want 在统一仪表盘上查看所有关键设备的健康度评分、劣化趋势和维护建议状态,
So that 我能全局掌握设备健康状况并及时安排维护。

## Acceptance Criteria

1. **Given** 运维主管进入预测性维护页面 **When** 页面加载 **Then** 展示所有关键设备的健康度评分卡片（按评分排序，低分优先）
2. **Given** 设备列表展示 **When** data_sufficiency="partial" **Then** 评分旁显示"评估精度：中等"提示
3. **Given** 设备列表展示 **When** data_sufficiency="minimal" **Then** 评分旁显示"评估精度：有限，建议补充采集配置"提示
4. **Given** 运维主管点击设备卡片 **When** 展开详情 **Then** 显示各因子评分明细、维护建议列表
5. **Given** 存在 pending 维护建议 **When** 运维人员操作 **Then** 可直接确认转工单或标记误报
6. **Given** 运维主管筛选 **When** 按设备类型/健康等级筛选 **Then** 列表实时过滤

## Tasks / Subtasks

- [ ] Task 1: 后端 API 扩展 (AC: #1, #2, #3, #4)
  - [ ] 1.1 在 `predictive_maintenance.py` 新增 `GET /dashboard` 端点（聚合统计+设备列表）
  - [ ] 1.2 在 `predictive_maintenance.py` 新增 `GET /devices/{id}/detail` 端点（因子明细+建议）
  - [ ] 1.3 扩展 Pydantic Schema（DashboardResponse, DeviceDetailResponse）
- [ ] Task 2: 前端 API 模块 (AC: #1-#6)
  - [ ] 2.1 新建 `frontend/src/api/modules/predictiveMaintenance.ts` — 类型定义 + API 函数
- [ ] Task 3: 预测性维护主页面 (AC: #1, #2, #3, #6)
  - [ ] 3.1 新建 `frontend/src/views/operation/predictive.vue` — 统计卡片 + 筛选栏 + 设备卡片列表
- [ ] Task 4: 设备详情对话框 (AC: #4, #5)
  - [ ] 4.1 设备健康度详情弹窗（因子评分明细 + 建议列表 + 确认/拒绝操作）
- [ ] Task 5: 路由注册 (AC: #1)
  - [ ] 5.1 在 `router/index.ts` operation 分组下新增 predictive 路由
- [ ] Task 6: 后端测试 (AC: #1-#5)
  - [ ] 6.1 dashboard 端点测试（统计+列表）
  - [ ] 6.2 device detail 端点测试（因子+建议）
  - [ ] 6.3 data_sufficiency 字段正确传递测试

## Dev Notes

### 关键设计决策

**1. 后端 API 扩展（新增 2 个端点到现有 predictive_maintenance.py）：**

```python
# GET /api/v1/predictive-maintenance/dashboard
# 返回：统计概览 + 设备健康度列表（带 score_factors、data_sufficiency）
@router.get("/dashboard")
async def get_dashboard(
    device_type: str | None = Query(None),
    health_level: str | None = Query(None),
    site_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    # 1. 查询 DeviceHealthScore（JOIN Device 支持 site_id 过滤）
    # 2. 统计 summary: total, by_level(健康/关注/预警/危险), by_type
    # 3. 筛选 + 排序（score ASC，低分优先）
    # 4. 空数据 → 返回 summary 全零 + devices=[]
    # 返回: { summary: {...}, devices: [...] }
```

```python
# GET /api/v1/predictive-maintenance/devices/{device_id}/detail
# 返回：设备健康度详情 + score_factors 解析 + 关联建议列表
@router.get("/devices/{device_id}/detail")
async def get_device_detail(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    # 1. 查询 DeviceHealthScore（含 score_factors JSON Text）
    # 2. 防御性解析 score_factors: json.loads(str) if str else None（score_factors 可能为 None）
    # 3. 查询该设备的 MaintenanceAdvice 列表（最近 10 条）
    # 返回: { health: {...}, factors: {...}, advices: [...] }
```

**2. Pydantic Schema 扩展：**
```python
# backend/app/schemas/predictive_maintenance.py 新增

class DashboardSummary(BaseModel):
    total: int
    healthy: int    # 健康
    attention: int  # 关注
    warning: int    # 预警
    danger: int     # 危险

class DeviceHealthItem(BaseModel):
    device_id: int
    device_name: str | None
    device_type: str | None
    score: float
    health_level: Literal["健康", "关注", "预警", "危险"]
    data_sufficiency: str | None
    degradation_score: float | None
    alarm_count: int
    calculated_at: datetime | None
    model_config = ConfigDict(from_attributes=True)

class DashboardResponse(BaseModel):
    summary: DashboardSummary
    devices: list[DeviceHealthItem]

class ScoreFactorDetail(BaseModel):
    degradation: dict | None = None
    alarm: dict | None = None
    maintenance: dict | None = None
    data_sufficiency: str | None = None
    plugin_key: str | None = None

class DeviceDetailResponse(BaseModel):
    health: DeviceHealthItem
    factors: ScoreFactorDetail | None
    advices: list[MaintenanceAdviceInfo]
```

**3. 前端 API 模块 `predictiveMaintenance.ts`：**
```typescript
// frontend/src/api/modules/predictiveMaintenance.ts

export interface DashboardSummary {
  total: number
  healthy: number
  attention: number
  warning: number
  danger: number
}

export interface DeviceHealthItem {
  device_id: number
  device_name: string | null
  device_type: string | null
  score: number
  health_level: '健康' | '关注' | '预警' | '危险'
  data_sufficiency: 'full' | 'partial' | 'minimal' | null
  degradation_score: number | null
  alarm_count: number
  calculated_at: string | null
}

export interface DashboardResponse {
  summary: DashboardSummary
  devices: DeviceHealthItem[]
}

export interface MaintenanceAdviceInfo {
  id: number
  device_id: number
  device_name: string | null
  device_type: string | null
  health_score: number | null
  urgency: 'high' | 'medium' | null
  reason: string | null
  suggested_action: string | null
  status: 'pending' | 'converted' | 'rejected' | 'auto_closed'
  feedback: string | null
  work_order_id: number | null
  created_at: string | null
  updated_at: string | null
  confirmed_at: string | null
  confirmed_by: number | null
}

export interface DeviceDetailResponse {
  health: DeviceHealthItem
  factors: {
    degradation?: { score: number; weight: number }
    alarm?: { score: number; weight: number; count: number }
    maintenance?: { score: number; weight: number; days_since: number | null }
    data_sufficiency?: string
    plugin_key?: string
  } | null
  advices: MaintenanceAdviceInfo[]
}

// API 函数
export function getDashboard(params?: {
  device_type?: string
  health_level?: string
}): Promise<DashboardResponse> {
  return request.get('/v1/predictive-maintenance/dashboard', { params })
}

export function getDeviceDetail(deviceId: number): Promise<DeviceDetailResponse> {
  return request.get(`/v1/predictive-maintenance/devices/${deviceId}/detail`)
}

export function getAdviceList(params?: {
  status?: string
  device_type?: string
}): Promise<MaintenanceAdviceInfo[]> {
  return request.get('/v1/predictive-maintenance/advices', { params })
}

export function confirmAdvice(adviceId: number): Promise<{ advice_id: number; work_order_id: number; work_order_no: string; status: string }> {
  return request.post(`/v1/predictive-maintenance/advices/${adviceId}/confirm`)
}

export function rejectAdvice(adviceId: number, feedback: string): Promise<MaintenanceAdviceInfo> {
  return request.post(`/v1/predictive-maintenance/advices/${adviceId}/reject`, { feedback })
}
```

**4. 前端页面 `predictive.vue` 结构：**

页面布局（参考 `device-status/index.vue` 模式）：
```
┌──────────────────────────────────────────┐
│ 统计卡片区（4个）                          │
│ [总设备 N] [健康 N] [关注 N] [预警+危险 N] │
├──────────────────────────────────────────┤
│ 筛选栏: [设备类型 ▼] [健康等级 ▼] [刷新]   │
├──────────────────────────────────────────┤
│ 设备健康度卡片网格（el-row + el-col）       │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│ │ AC-001   │ │ UPS-002  │ │ PDU-003  │  │
│ │ 35.2分   │ │ 58.0分   │ │ 72.5分   │  │
│ │ ●危险    │ │ ●预警    │ │ ●关注    │  │
│ │ [精度:有限]│ │          │ │ [精度:中等]│  │
│ └──────────┘ └──────────┘ └──────────┘  │
└──────────────────────────────────────────┘
```

设备卡片颜色映射：
- 健康(≥80): `#67C23A` (绿色)
- 关注(60-79): `#E6A23C` (橙色)
- 预警(40-59): `#F56C6C` (红色)
- 危险(<40): `#909399` → `#F56C6C` 加深红 + 闪烁动画

点击卡片 → `el-dialog` 弹出详情：
```
┌─── 设备健康度详情 ───────────────────────┐
│ AC-001 | 35.2分 | 危险                    │
│                                          │
│ 评分因子明细:                             │
│ ├─ 劣化趋势: 25.0分 (权重40%)            │
│ ├─ 告警频次: 30.0分 (权重30%, 近30天12次)  │
│ └─ 维保记录: 50.0分 (权重30%, 距上次180天)  │
│                                          │
│ 数据充分度: 有限(可用1/5点位)              │
│                                          │
│ ─── 维护建议 ──────────────────          │
│ [pending] COP持续下降，建议检查制冷剂       │
│           [确认转工单] [标记误报]            │
│ [converted] 回风温度上升 → 工单 MA-001     │
└──────────────────────────────────────────┘
```

**5. 路由注册：**
```typescript
// frontend/src/router/index.ts — operation children 中追加
{ path: 'predictive', name: 'Predictive', component: () => import('@/views/operation/predictive.vue'), meta: { title: '预测性维护', icon: 'TrendCharts' } },
```

**6. data_sufficiency 前端提示映射：**
```typescript
function sufficiencyText(ds: string | null): string {
  if (ds === 'partial') return '评估精度：中等'
  if (ds === 'minimal' || ds === null) return '评估精度：有限，建议补充采集配置'
  return ''  // full 无提示
}

function sufficiencyType(ds: string | null): '' | 'warning' | 'danger' {
  if (ds === 'partial') return 'warning'
  if (ds === 'minimal' || ds === null) return 'danger'
  return ''
}
```

### 现有代码关键引用

| 文件 | 说明 | 关键字段/方法 |
|------|------|-------------|
| `backend/app/api/v1/predictive_maintenance.py` | Story 36.3 的 4 个端点 | list/detail/confirm/reject advices |
| `backend/app/schemas/predictive_maintenance.py` | MaintenanceAdviceInfo 等 | Literal 校验 status/urgency |
| `backend/app/models/report.py:63-81` | DeviceHealthScore 表 | score, health_level, score_factors, data_sufficiency |
| `backend/app/models/report.py:84+` | MaintenanceAdvice 表 | device_id, status, work_order_id |
| `backend/app/api/v1/report.py:1192-1257` | 旧的 device-health API（仅供参考，不修改） | /reports/device-health |
| `frontend/src/api/modules/report.ts:325-368` | 旧的 DeviceHealthScore 类型（不复用，新建独立模块） | 接口定义参考 |
| `frontend/src/views/operation/workorder.vue` | 运维管理页面模式参考 | el-table + 筛选栏模式 |
| `frontend/src/views/device-status/index.vue` | 设备卡片网格模式参考 | el-row/el-col + 卡片布局 |
| `frontend/src/components/charts/LineChart.vue` | 折线图组件 | 如需趋势图可复用 |
| `frontend/src/router/index.ts:171-178` | operation 路由组 | children 数组 |

### Project Structure Notes

**新建文件清单：**
```
frontend/src/api/modules/predictiveMaintenance.ts   # API 模块
frontend/src/views/operation/predictive.vue          # 预测性维护仪表盘页面
```

**修改文件清单：**
```
backend/app/api/v1/predictive_maintenance.py         # 新增 dashboard + device detail 端点
backend/app/schemas/predictive_maintenance.py        # 新增 Dashboard/Detail Schema
frontend/src/router/index.ts                         # 注册 predictive 路由
backend/tests/services/test_maintenance_advisor.py   # 追加 dashboard/detail API 测试
```

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#Section 23.5] — 数据充分度与精度提示
- [Source: _bmad-output/planning-artifacts/architecture.md#Section 23.6] — API 设计
- [Source: _bmad-output/planning-artifacts/epics.md#Story 36.4] — 详细技术规格
- [Source: _bmad-output/planning-artifacts/prd.md#FR-PM06] — 预测性维护仪表盘

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Completion Notes List

- Story 36.4 依赖 Story 36.2（DeviceHealthScore 增强）+ Story 36.3（维护建议引擎）
- 旧的 `/reports/device-health` API 保持不变，新增 `/predictive-maintenance/dashboard` 提供增强版本（含 score_factors、data_sufficiency）
- 前端 API 模块独立于 report.ts，新建 `predictiveMaintenance.ts`
- 路由挂载在 `/operation/predictive`，与 workorder/inspection/knowledge 同级
- 页面不使用 Pinia Store（数据量不大，页面内 ref 即可）
- 不新建子组件文件，详情弹窗内联在 predictive.vue 中（el-dialog 嵌入主页面，代码量可控）
- data_sufficiency 前端提示文案：full=无提示、partial=中等、minimal=有限+建议补充、null(旧数据)=视同minimal
- 确认/拒绝操作后本地更新 advice 状态，不全量 reload dashboard
- 确认/拒绝并发冲突时后端返回 409，前端捕获后 ElMessage.warning 提示并刷新

### File List

**新建：**
- `frontend/src/api/modules/predictiveMaintenance.ts`
- `frontend/src/views/operation/predictive.vue`

**修改：**
- `backend/app/api/v1/predictive_maintenance.py` — 新增 dashboard + device detail
- `backend/app/schemas/predictive_maintenance.py` — 新增 Schema
- `frontend/src/router/index.ts` — 注册路由
- `backend/tests/services/test_maintenance_advisor.py` — 追加测试
