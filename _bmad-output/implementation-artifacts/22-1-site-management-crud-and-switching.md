# Story 22-1: 站点管理CRUD与切换

## 状态: 就绪

## Story

As a 系统管理员,
I want 在站点管理页面管理多个数据中心站点并在站点间切换,
So that 我可以从单一界面集中管理多站点基础设施。

## 验收标准 (AC)

1. 页面路由: `/system/sites`，替换当前 PlaceholderView
2. 站点概览卡片区: 每个站点显示关键指标（设备数、网关数、告警数、状态）
3. 站点列表表格: 站点名称、站点编码、地址、联系人、设备数、网关数、状态(正常/告警/离线)、创建时间
4. 支持站点 CRUD 操作（创建/编辑/删除）
5. 创建/编辑站点对话框: 站点编码、站点名称、地址、联系人、联系电话、描述
6. 删除站点需要二次确认（el-popconfirm）
7. 后端 API 已存在于 `spatial.py`，直接使用 `@/api/modules/spatial` 中的 getSites/createSite/updateSite/deleteSite
8. 站点切换功能: 复用已有 `useSiteStore` 的 `switchSite` 方法
9. 包含 2.5D 视觉增强（使用 `@/styles/_mixins-25d` 的 page-dashboard + page-list 混合模式）

## 棕地分析

### 已有代码
- **后端 API**: `api/v1/spatial.py` — 完整站点 CRUD（GET列表、POST创建、PUT更新、DELETE删除、GET汇总）
- **前端 API**: `api/modules/spatial.ts` — getSites, createSite, updateSite, deleteSite, getSiteSummary + 完整类型定义（Site, SiteForm, SiteSummaryItem, SiteSummaryResponse）
- **Store**: `stores/site.ts` — useSiteStore（fetchSites, fetchSummary, switchSite, currentSiteId）
- **路由**: `/system/sites` 已存在，当前指向 PlaceholderView
- **参考页面**: `views/system/user.vue`（CRUD 模式）、`views/system/audit-log.vue`（列表模式）

### 需要修改
- `views/system/sites.vue` — 替换 PlaceholderView 为完整实现

### 不需要修改
- 后端代码（API 已完整）
- 路由配置（已存在）
- Store（已存在）
- API 模块（已存在）

## 技术方案

### 页面结构
1. **概览卡片区** — el-row + el-col 展示站点汇总（总站点数、总设备数、总网关数、总告警数）
2. **工具栏** — 搜索框 + 新建站点按钮
3. **站点表格** — el-table 展示站点列表，含操作列（编辑/删除/切换）
4. **创建/编辑对话框** — el-dialog + el-form

### 数据流
- 使用 `getSites()` 获取站点列表
- 使用 `getSiteSummary()` 获取汇总数据
- CRUD 操作直接调用 `spatial.ts` 中的 API
- 站点切换调用 `useSiteStore().switchSite()`

### 样式
- 使用 `@use '@/styles/_mixins-25d' as *`
- 概览卡片区使用 `stat-cards-arc` mixin
- 表格区使用 `page-list` mixin
- 遵循 user.vue / audit-log.vue 的样式模式

## 对抗性审查

### 潜在问题
1. **SiteForm 类型不完整**: spatial.ts 中 SiteForm 只有 site_code/site_name/address/description，缺少 contact_person/contact_phone。需要在页面内扩展提交数据。
2. **API 响应格式**: request.ts 拦截器已 unwrap response.data，getSites 返回的可能是数组或 {data: []}，site store 已处理 `(res as any).data ?? res`。
3. **删除保护**: 后端可能有关联数据保护（楼层/房间），前端需要处理删除失败的错误提示。

### 风险缓解
- SiteForm 扩展字段通过 Partial 传递，后端 SiteUpdate schema 接受可选字段
- 错误处理统一使用 try/catch + ElMessage.error
- 删除使用 el-popconfirm 二次确认

## 依赖
- 无新增依赖，所有 API/Store/类型已存在
