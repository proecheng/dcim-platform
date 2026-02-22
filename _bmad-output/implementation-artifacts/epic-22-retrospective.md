# Epic 22 回顾：站点管理前端

## 完成情况

全部 1 个 Story 完成。本 Epic 为站点管理模块实现了完整的 CRUD 和站点切换功能，替换 PlaceholderView 占位组件。

| Story | 标题 | 核心特性 | 前端构建 |
|-------|------|---------|---------|
| 22-1 | 站点管理 CRUD 与切换 | 概览卡片 + CRUD 表格 + 站点切换 | ✅ |

**优先级：** P0（最高）

## 关键经验教训

### 最高复用度

- Phase 2 补充 Epic 中复用度最高的 Story：后端 API（`spatial.py`）、前端 API 模块（`spatial.ts`）、Store（`useSiteStore`）、路由全部已存在。
- 只需修改一个文件：`views/system/sites.vue`，替换 PlaceholderView。
- 证明了 Epic 1-17 的基础设施建设质量——后续页面开发可以直接"组装"。

### 棕地分析价值

- Story 文件包含完整的棕地分析：已有代码、需要修改、不需要修改三个清单。
- 开发者无需探索即可直接开工，显著减少了上下文切换成本。
- 建议后续所有替换 PlaceholderView 的 Story 都包含棕地分析。

### 类型定义完整性

- 对抗性审查发现 `SiteForm` 类型缺少 `contact_person` / `contact_phone` 字段。
- 前端类型定义与后端 schema 不完全同步是常见问题，即使 API 模块已存在也需要对照检查。

### 混合 2.5D Preset

- 页面同时使用 `stat-cards-arc`（概览卡片区）和 `page-list`（表格区）两种 mixin。
- 这是 dashboard + list 混合模式的首次应用，适用于"概览+管理"类页面。

## 待改进项

- **SiteForm 类型应补全**：在 `spatial.ts` 中补充 `contact_person` / `contact_phone` 字段，保持类型定义与后端 schema 同步。

## 行动项

| 行动 | 负责人 | 优先级 |
|------|--------|--------|
| 补全 SiteForm 类型定义 | Dev Team | 低（可选） |
