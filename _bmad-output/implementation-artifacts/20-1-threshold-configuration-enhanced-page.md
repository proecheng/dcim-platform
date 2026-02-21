# Story 20.1: 阈值配置增强页

## Story

**As a** 系统管理员,
**I want to** 在独立的阈值配置页面上批量管理告警阈值，并通过可视化阈值线直观看到阈值与实时数据的关系,
**So that** 我可以高效地为大量点位配置合理的告警阈值。

## 状态: 就绪

## 验收标准 (AC)

### AC1: 页面路由与基础布局
- **Given** 用户已登录系统
- **When** 导航到 `/strategy/alarm-rules/thresholds`
- **Then** 显示独立的阈值配置增强页面，包含统计卡片和阈值规则列表表格
- **And** 页面包含 2.5D 视觉增强效果

### AC2: 阈值规则列表表格
- **Given** 页面已加载
- **When** 查看阈值规则列表
- **Then** 表格显示：点位名称、点位编码、设备类型、4级阈值（提示/次要/重要/紧急）、启用状态、最后更新时间
- **And** 支持分页浏览

### AC3: 按设备类型批量筛选
- **Given** 页面已加载
- **When** 在筛选栏选择设备类型（如"温湿度传感器"、"UPS"）
- **Then** 表格仅显示该设备类型下的阈值规则
- **And** 支持按阈值类型、启用状态筛选

### AC4: 批量操作
- **Given** 用户选中多条阈值规则
- **When** 点击"批量启用"或"批量禁用"
- **Then** 所选规则的启用状态被批量更新
- **And** 支持按设备类型批量修改阈值

### AC5: 可视化阈值线预览对话框
- **Given** 用户点击"添加"或"编辑"阈值规则
- **When** 配置对话框打开
- **Then** 对话框包含 ECharts 趋势图，显示点位最近24小时数据
- **And** 4级阈值叠加为彩色水平线（提示-蓝、次要-黄、重要-橙、紧急-红）
- **And** 可通过输入框调整阈值，图表实时更新阈值线位置

### AC6: 单条规则 CRUD
- **Given** 页面已加载
- **When** 用户执行创建/编辑/删除/启用/禁用操作
- **Then** 操作成功后刷新列表
- **And** 删除操作需要二次确认

## 技术说明

### 前端文件
- `frontend/src/views/alarm/thresholds.vue` — 替换现有 PlaceholderView

### API 依赖
- `getThresholdList` — 获取阈值列表（分页）
- `createThreshold` — 创建阈值
- `updateThreshold` — 更新阈值
- `deleteThreshold` — 删除阈值
- `setFourLevelThresholds` — 4级阈值一体化配置
- `batchSetByDeviceType` — 按设备类型批量配置
- `getPointList` — 获取点位列表（筛选用）
- `getPointTrend` — 获取点位趋势数据（ECharts 图表用）

### ECharts 阈值线实现方案
- 使用 `markLine` 绘制4级阈值水平线
- 阈值线颜色：info=#409EFF, minor=#E6A23C, major=#F56C0C, critical=#F56C6C
- 通过输入框修改阈值时，响应式更新 markLine 数据
- **注意**: ECharts 原生不支持 markLine 拖拽，采用输入框+实时预览方案替代

### 2.5D 视觉增强
- 使用 `@use '@/styles/_mixins-25d' as d25` 引入 mixin
- 应用 `page-list` preset（表格+筛选类页面）

### 设计决策
1. **输入框替代拖拽**: ECharts markLine 不支持原生拖拽交互，实现自定义拖拽需要大量 hack 代码且维护成本高。采用输入框+实时预览方案，用户体验更稳定可靠。
2. **复用现有 API**: 完全复用 `threshold.ts` 和 `history.ts` 中已有的 API，不新增后端接口。
3. **独立页面**: 与 `alarm/index.vue` 中的阈值 tab 独立，提供增强的批量管理和可视化能力。

## 任务分解

### Task 1: 页面基础结构与统计卡片
- 替换 PlaceholderView
- 实现统计卡片（总规则数、已启用、已禁用、设备类型数）
- 应用 2.5D mixin

### Task 2: 阈值规则列表表格
- 实现带分页的表格
- 显示点位名称、设备类型、4级阈值、启用状态
- 筛选栏（设备类型、阈值类型、启用状态）

### Task 3: 批量操作
- 表格多选
- 批量启用/禁用
- 按设备类型批量修改阈值对话框

### Task 4: 可视化阈值配置对话框
- ECharts 趋势图（24小时数据）
- 4级阈值 markLine 水平线
- 输入框实时调整阈值线
- 创建/编辑表单

### Task 5: 单条规则 CRUD 与删除确认
- 创建/编辑/删除/启用/禁用
- 删除二次确认
