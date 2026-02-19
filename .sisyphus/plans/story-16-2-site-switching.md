# Story 16-2: 站点切换与统一视图 — 设计方案

## 目标

在前端顶部导航栏添加站点选择器，切换站点后所有页面数据自动过滤到目标站点。支持"全部站点"汇总视图。后端新增跨站点汇总 API。

## 验收标准

1. 顶部导航栏有站点选择器（下拉框），显示用户有权限的站点列表
2. 选择站点后，所有页面数据切换到目标站点
3. 支持"全部站点"选项，汇总显示所有站点的关键指标
4. 支持跨站点对比（仪表盘汇总卡片）
5. 站点选择持久化到 localStorage，刷新后保持

## 实现步骤

### Step 1: 后端 — 跨站点汇总 API

**文件**: `backend/app/api/v1/spatial.py`

新增端点:
```
GET /api/v1/spatial/sites/summary
```

返回所有用户可见站点的汇总数据:
```json
{
  "total_sites": 3,
  "total_gateways": 15,
  "total_devices": 120,
  "total_alarms": 5,
  "sites": [
    {
      "id": 1,
      "site_code": "BJ-01",
      "site_name": "北京站点",
      "status": "active",
      "gateway_count": 5,
      "device_count": 40,
      "active_alarm_count": 2,
      "pue": 1.45
    }
  ]
}
```

依赖 `get_user_site_ids` 过滤，admin 看全部，其他角色看授权站点。

### Step 2: 前端 — Pinia Site Store

**新建文件**: `frontend/src/stores/site.ts`

```typescript
export const useSiteStore = defineStore('site', () => {
  // 当前选中站点 ID (null = 全部站点)
  const currentSiteId = ref<number | null>(null)
  // 站点列表
  const sites = ref<SiteInfo[]>([])
  // 加载状态
  const loading = ref(false)

  // 计算属性
  const currentSite = computed(...)
  const currentSiteName = computed(...)

  // 方法
  async function fetchSites() { ... }
  function switchSite(siteId: number | null) { ... }
  function initFromStorage() { ... }
})
```

在 `stores/index.ts` 中导出 `useSiteStore`。

### Step 3: 前端 — 站点 API 模块

**新建文件**: `frontend/src/api/modules/site.ts`

```typescript
export function getSiteList(params?: { keyword?: string; status?: string })
export function getSiteSummary()
```

在 `api/modules/index.ts` 中导出。

### Step 4: 前端 — 站点选择器组件

**新建文件**: `frontend/src/components/common/SiteSwitcher.vue`

- Element Plus `el-select` 下拉框
- 第一项: "全部站点" (value = null)
- 后续项: 各站点名称 (value = site.id)
- 选中后调用 `siteStore.switchSite(siteId)`
- 站点状态用小圆点标识 (active=绿, maintenance=黄, inactive=灰)

### Step 5: 前端 — 集成到 MainLayout

**修改文件**: `frontend/src/layouts/MainLayout.vue`

在 `header-right` 区域，告警声音开关之前插入 `<SiteSwitcher />`。

布局: `[折叠按钮] [面包屑] ... [站点选择器] [告警声音] [告警徽章] [用户下拉]`

### Step 6: 前端 — API 请求自动注入 site_id

**方案**: 在 composable 或 axios 拦截器中自动注入 `site_id` 参数。

**新建文件**: `frontend/src/composables/useSiteFilter.ts`

```typescript
export function useSiteFilter() {
  const siteStore = useSiteStore()

  // 返回当前站点过滤参数
  function getSiteParams(): Record<string, any> {
    if (siteStore.currentSiteId !== null) {
      return { site_id: siteStore.currentSiteId }
    }
    return {}
  }

  // 监听站点切换，触发回调
  function onSiteChange(callback: () => void) {
    watch(() => siteStore.currentSiteId, callback)
  }

  return { getSiteParams, onSiteChange }
}
```

各页面在 API 调用时使用 `getSiteParams()` 合并参数，并用 `onSiteChange` 监听切换后刷新数据。

### Step 7: 前端 — 仪表盘跨站点汇总卡片

**修改文件**: `frontend/src/views/dashboard/index.vue` (或对应仪表盘页面)

当 `currentSiteId === null` (全部站点) 时:
- 显示跨站点汇总卡片: 总站点数、总网关数、总设备数、总告警数
- 每个站点一行摘要: 站点名、状态、PUE、告警数
- 使用 `getSiteSummary()` API

当 `currentSiteId !== null` (单站点) 时:
- 显示原有仪表盘内容，数据按 site_id 过滤

### Step 8: 后端测试

**新建/修改**: `backend/tests/test_site_management.py`

新增测试:
- `test_site_summary_admin_sees_all` — admin 看到所有站点汇总
- `test_site_summary_viewer_sees_authorized` — viewer 只看到授权站点
- `test_site_summary_includes_alarm_count` — 汇总包含告警数

## 不做的事

- 不修改现有 API 的签名（site_id 已在 16-1 中作为可选参数加入）
- 不做跨站点报表导出（后续 Story 或独立需求）
- 不做站点管理 CRUD 页面（16-1 已有后端 API，前端管理页面可后续补充）

## 依赖

- Story 16-1 已完成: Site CRUD API、site_id 过滤、get_user_site_ids 依赖

## 风险

- 部分页面 API 可能尚未支持 site_id 过滤（如告警、历史数据）— 需逐步适配
- 全部站点视图下数据量可能较大 — 汇总 API 只返回统计数据，不返回明细
