# 算力中心智能监控系统 - 科技风格配色方案全面实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标:** 系统性地将整个软件的配色统一为科技风格深色主题，确保所有界面视觉一致、文字清晰可读、图表美观协调。

**参考图片:** 图片20.png（深蓝底青色强调）、图片23.png（PUE多图表面板）、图片39.png（紫蓝青综合管理平台）

**技术栈:** Vue 3, SCSS, Element Plus, ECharts, CSS Custom Properties

---

## 一、配色方案总览

### 1.1 核心色彩体系（已在 dark-tech.scss 中定义）

```scss
// ========== 背景色系 ==========
$bg-primary: #0a1628;           // 页面主背景（最深蓝黑）
$bg-secondary: #0d1b2a;         // 侧边栏/次级区域
$bg-tertiary: #112240;          // 卡片头部/输入框背景
$bg-card: rgba(26, 42, 74, 0.85); // 卡片背景（半透明玻璃感）
$bg-card-solid: #1a2a4a;        // 卡片背景（实色）

// ========== 强调色（科技青） ==========
$accent-color: #00d4ff;         // 核心强调色
$accent-light: #00f7ff;         // 高亮态
$accent-glow: rgba(0, 212, 255, 0.3); // 发光效果

// ========== 主色系 ==========
$primary-color: #1890ff;        // Element Plus 蓝
$primary-light: #40a9ff;
$primary-dark: #096dd9;

// ========== 状态色 ==========
$success-color: #52c41a;        // 正常/成功（绿）
$warning-color: #faad14;        // 警告（橙黄）
$error-color: #f5222d;          // 错误/危险（红）
$info-color: #1890ff;           // 信息（蓝）

// ========== 告警等级色 ==========
$alarm-critical: #ff4d4f;       // 紧急 (1级) - 红
$alarm-major: #fa8c16;          // 重要 (2级) - 橙
$alarm-minor: #faad14;          // 一般 (3级) - 黄
$alarm-info: #1890ff;           // 提示 (4级) - 蓝

// ========== 文字色 ==========
$text-primary: rgba(255, 255, 255, 0.95);   // 标题/重要文字
$text-regular: rgba(255, 255, 255, 0.85);   // 正文
$text-secondary: rgba(255, 255, 255, 0.65); // 次要说明
$text-placeholder: rgba(255, 255, 255, 0.45); // 占位符
$text-disabled: rgba(255, 255, 255, 0.25);  // 禁用

// ========== 边框色 ==========
$border-color: rgba(255, 255, 255, 0.1);
$border-light: rgba(255, 255, 255, 0.06);
$border-active: rgba(0, 212, 255, 0.5);
$border-glow: rgba(0, 212, 255, 0.3);
```

### 1.2 图表配色规范（参考图片20、23、39）

```typescript
// ECharts 图表色板
const chartPalette = {
  // 主色板（按使用频率排序）
  primary: ['#00d4ff', '#1890ff', '#5470c6', '#73c0de'],

  // 对比色板（用于多系列）
  contrast: ['#00d4ff', '#f5a623', '#52c41a', '#ff6b6b'],

  // 渐变色（用于面积图）
  gradients: {
    cyan: ['rgba(0, 212, 255, 0.4)', 'rgba(0, 212, 255, 0.05)'],
    blue: ['rgba(24, 144, 255, 0.4)', 'rgba(24, 144, 255, 0.05)'],
    orange: ['rgba(245, 166, 35, 0.4)', 'rgba(245, 166, 35, 0.05)'],
  },

  // 坐标轴
  axis: {
    line: 'rgba(255, 255, 255, 0.1)',
    label: 'rgba(255, 255, 255, 0.65)',
    splitLine: 'rgba(255, 255, 255, 0.05)',
  },

  // 仪表盘色段
  gauge: [
    [0.3, '#52c41a'],   // 优秀 (绿)
    [0.7, '#faad14'],   // 一般 (黄)
    [1.0, '#f5222d'],   // 危险 (红)
  ]
}
```

---

## 二、需要修改的文件清单

### 2.1 公共组件（优先级最高）

| 文件 | 问题描述 | 修改方案 |
|------|----------|----------|
| `components/common/SearchForm.vue` | 使用 `var(--el-bg-color)` 默认白色 | 改用 `var(--bg-card)` |
| `components/common/DataTable.vue` | 无问题（已使用 el-table 样式） | 验证即可 |
| `components/common/StatusTag.vue` | 硬编码颜色值 | 使用 CSS 变量 |

### 2.2 能源管理模块

| 文件 | 问题描述 | 修改方案 |
|------|----------|----------|
| `views/energy/monitor.vue` | ECharts 使用旧配色 | 统一图表主题 |
| `views/energy/statistics.vue` | 硬编码文字颜色 | 使用 CSS 变量 |
| `views/energy/topology.vue` | 节点图标硬编码颜色 | 使用状态色变量 |
| `views/energy/regulation.vue` | 表单/卡片硬编码样式 | 统一深色主题 |
| `views/energy/suggestions.vue` | 浅色背景优先级标签 | 改为深色透明 |
| `components/energy/PUEGauge.vue` | 仪表盘硬编码颜色 | 统一仪表盘主题 |
| `components/energy/PowerCard.vue` | 负载率硬编码颜色 | 使用计算属性 |
| `components/energy/CostCard.vue` | 饼图/图标硬编码颜色 | 使用图表主题 |
| `components/energy/EnergySuggestionCard.vue` | 优先级边框/背景 | 使用状态色变量 |
| `components/energy/SuggestionsCard.vue` | 优先级颜色函数 | 统一颜色逻辑 |

### 2.3 告警模块

| 文件 | 问题描述 | 修改方案 |
|------|----------|----------|
| `views/alarm/index.vue` | 使用 Element Plus 默认样式 | 已适配，验证即可 |

### 2.4 报告模块

| 文件 | 问题描述 | 修改方案 |
|------|----------|----------|
| `views/report/index.vue` | 统计卡片已有渐变 | 验证/微调 |

### 2.5 资产模块

| 文件 | 问题描述 | 修改方案 |
|------|----------|----------|
| `views/asset/index.vue` | 发光效果硬编码 | 使用 CSS 变量 |
| `views/asset/cabinet.vue` | 机柜可视化样式 | 使用统一配色 |

### 2.6 运维模块

| 文件 | 问题描述 | 修改方案 |
|------|----------|----------|
| `views/operation/workorder.vue` | 状态/类型颜色硬编码 | 使用状态色映射 |
| `views/operation/knowledge.vue` | 分类颜色硬编码 | 使用统一配色 |

### 2.7 楼层布局组件

| 文件 | 问题描述 | 修改方案 |
|------|----------|----------|
| `components/floor-layouts/FloorLayoutBase.vue` | SVG 颜色硬编码 | 使用 CSS 变量 |

### 2.8 登录页

| 文件 | 问题描述 | 修改方案 |
|------|----------|----------|
| `views/login/index.vue` | 自定义设计 | 保持设计，优化可维护性 |

---

## 三、实施任务分解

### Task 1: 公共搜索表单组件深色化

**文件:** `frontend/src/components/common/SearchForm.vue`

**Step 1:** 读取当前文件内容

**Step 2:** 修改 SCSS 样式
```scss
.search-form {
  padding: 16px;
  background: var(--bg-card);  // 改为卡片背景
  border-radius: var(--radius-base);
  border: 1px solid var(--border-color);
  margin-bottom: 16px;

  &__expand {
    border-top-color: var(--border-color);
  }
}
```

**Step 3:** 运行构建验证
```bash
cd frontend && npm run build
```

**Step 4:** 提交
```bash
git add frontend/src/components/common/SearchForm.vue
git commit -m "fix(components): update SearchForm to dark theme

- Change background from --el-bg-color to --bg-card
- Add border styling for dark theme consistency

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

### Task 2: 能源监控页面图表主题统一

**文件:** `frontend/src/views/energy/monitor.vue`

**Step 1:** 读取当前文件内容，理解 ECharts 配置结构

**Step 2:** 更新 ECharts 选项，添加统一的深色主题配置

在图表选项中添加：
```typescript
const commonChartOptions = {
  backgroundColor: 'transparent',
  textStyle: {
    color: 'rgba(255, 255, 255, 0.65)'
  },
  grid: {
    borderColor: 'rgba(255, 255, 255, 0.1)'
  },
  xAxis: {
    axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.1)' } },
    axisLabel: { color: 'rgba(255, 255, 255, 0.65)' },
    splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } }
  },
  yAxis: {
    axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.1)' } },
    axisLabel: { color: 'rgba(255, 255, 255, 0.65)' },
    splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } }
  }
}
```

**Step 3:** 更新图表系列颜色为科技青主色调
```typescript
series: [{
  type: 'line',
  smooth: true,
  itemStyle: { color: '#00d4ff' },
  areaStyle: {
    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
      { offset: 0, color: 'rgba(0, 212, 255, 0.4)' },
      { offset: 1, color: 'rgba(0, 212, 255, 0.05)' }
    ])
  }
}]
```

**Step 4:** 运行构建验证

**Step 5:** 提交

---

### Task 3: 能源统计页面配色修复

**文件:** `frontend/src/views/energy/statistics.vue`

**Step 1:** 读取当前文件

**Step 2:** 替换所有硬编码颜色
- `#303133` → `var(--text-primary)`
- `#909399` → `var(--text-secondary)`
- `#eee` → `var(--border-color)`
- `#f5f7fa` → `var(--bg-tertiary)`

**Step 3:** 更新 ECharts 配置使用深色主题

**Step 4:** 运行构建验证

**Step 5:** 提交

---

### Task 4: 能源拓扑页面配色修复

**文件:** `frontend/src/views/energy/topology.vue`

**Step 1:** 读取当前文件

**Step 2:** 更新设备图标颜色映射
```typescript
const deviceColors = {
  transformer: 'var(--error-color)',    // #f5222d
  meter: 'var(--warning-color)',        // #faad14
  panel: 'var(--primary-color)',        // #1890ff
  circuit: 'var(--success-color)',      // #52c41a
  device: '#722ed1'                     // 紫色保留
}
```

**Step 3:** 添加深色主题卡片样式

**Step 4:** 运行构建验证

**Step 5:** 提交

---

### Task 5: 能源调控页面配色修复

**文件:** `frontend/src/views/energy/regulation.vue`

**Step 1:** 读取当前文件

**Step 2:** 替换所有硬编码颜色（参考颜色映射表）

**Step 3:** 确保表格、表单使用深色样式

**Step 4:** 运行构建验证

**Step 5:** 提交

---

### Task 6: 能源建议页面配色修复

**文件:** `frontend/src/views/energy/suggestions.vue`

**Step 1:** 读取当前文件

**Step 2:** 更新优先级标签背景色
```scss
// 原浅色背景替换为深色透明
.priority-high { background: rgba(245, 34, 45, 0.15); }
.priority-medium { background: rgba(250, 173, 20, 0.15); }
.priority-low { background: rgba(82, 196, 26, 0.15); }
```

**Step 3:** 运行构建验证

**Step 4:** 提交

---

### Task 7: PUE 仪表盘组件配色修复

**文件:** `frontend/src/components/energy/PUEGauge.vue`

**Step 1:** 读取当前文件

**Step 2:** 更新仪表盘颜色配置
```typescript
axisLine: {
  lineStyle: {
    color: [
      [0.3, '#52c41a'],   // 优秀 - 绿
      [0.7, '#faad14'],   // 一般 - 黄
      [1.0, '#f5222d']    // 危险 - 红
    ]
  }
}
```

**Step 3:** 更新文字和背景色为深色主题

**Step 4:** 运行构建验证

**Step 5:** 提交

---

### Task 8: 电力卡片组件配色修复

**文件:** `frontend/src/components/energy/PowerCard.vue`

**Step 1:** 读取当前文件

**Step 2:** 更新负载率颜色计算函数

**Step 3:** 替换硬编码样式为 CSS 变量

**Step 4:** 运行构建验证

**Step 5:** 提交

---

### Task 9: 成本卡片组件配色修复

**文件:** `frontend/src/components/energy/CostCard.vue`

**Step 1:** 读取当前文件

**Step 2:** 更新饼图颜色配置

**Step 3:** 更新图标和文字颜色

**Step 4:** 运行构建验证

**Step 5:** 提交

---

### Task 10: 能源建议卡片组件配色修复

**文件:** `frontend/src/components/energy/EnergySuggestionCard.vue`

**Step 1:** 读取当前文件

**Step 2:** 更新优先级边框和背景色
```scss
&--high { border-left-color: var(--error-color); }
&--medium { border-left-color: var(--warning-color); }
&--low { border-left-color: var(--success-color); }
```

**Step 3:** 运行构建验证

**Step 4:** 提交

---

### Task 11: 建议卡片组件配色修复

**文件:** `frontend/src/components/energy/SuggestionsCard.vue`

**Step 1:** 读取当前文件

**Step 2:** 更新优先级颜色映射函数

**Step 3:** 运行构建验证

**Step 4:** 提交

---

### Task 12: 状态标签组件配色修复

**文件:** `frontend/src/components/common/StatusTag.vue`

**Step 1:** 读取当前文件

**Step 2:** 更新颜色映射使用 CSS 变量值

**Step 3:** 运行构建验证

**Step 4:** 提交

---

### Task 13: 资产管理页面配色修复

**文件:** `frontend/src/views/asset/index.vue`, `frontend/src/views/asset/cabinet.vue`

**Step 1:** 读取两个文件

**Step 2:** 统一发光效果和阴影使用 CSS 变量

**Step 3:** 运行构建验证

**Step 4:** 提交

---

### Task 14: 运维模块配色修复

**文件:** `frontend/src/views/operation/workorder.vue`, `frontend/src/views/operation/knowledge.vue`

**Step 1:** 读取两个文件

**Step 2:** 更新状态/分类颜色映射

**Step 3:** 运行构建验证

**Step 4:** 提交

---

### Task 15: 楼层布局组件配色修复

**文件:** `frontend/src/components/floor-layouts/FloorLayoutBase.vue`

**Step 1:** 读取当前文件

**Step 2:** 更新 SVG 颜色和图例样式

**Step 3:** 运行构建验证

**Step 4:** 提交

---

### Task 16: 全面测试与文档更新

**Step 1:** 运行完整构建
```bash
cd frontend && npm run build
```

**Step 2:** 启动开发服务器进行视觉检查
```bash
cd frontend && npm run dev
```

**Step 3:** 逐页检查清单
- [ ] 首页/仪表盘
- [ ] 大屏展示
- [ ] 能源监控
- [ ] 能源统计
- [ ] 能源拓扑
- [ ] 能源调控
- [ ] 能源建议
- [ ] 告警管理
- [ ] 报告中心
- [ ] 资产管理
- [ ] 机柜管理
- [ ] 工单管理
- [ ] 知识库
- [ ] 登录页

**Step 4:** 更新 progress.md 文档

**Step 5:** 最终提交
```bash
git add .
git commit -m "docs: complete tech color scheme implementation V4.4.0

- Unified dark theme across all pages
- Standardized ECharts color palette
- Fixed white background issues
- Improved text contrast and readability

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## 四、颜色替换快速参考表

| 原始颜色 | 替换为 | 用途 |
|----------|--------|------|
| `#303133` | `var(--text-primary)` | 主要文字 |
| `#606266` | `var(--text-regular)` | 常规文字 |
| `#909399` | `var(--text-secondary)` | 次要文字 |
| `#C0C4CC` | `var(--text-placeholder)` | 占位符 |
| `#eee`, `#EBEEF5` | `var(--border-color)` | 边框 |
| `#f5f7fa`, `#fafafa` | `var(--bg-tertiary)` | 浅色背景 |
| `white`, `#fff` | `var(--bg-card)` 或保留 | 卡片背景 |
| `#409eff`, `#1890ff` | `var(--primary-color)` | 主色蓝 |
| `#67c23a`, `#52c41a` | `var(--success-color)` | 成功绿 |
| `#e6a23c`, `#faad14` | `var(--warning-color)` | 警告橙 |
| `#f56c6c`, `#f5222d` | `var(--error-color)` | 错误红 |
| `#00d4ff` | `var(--accent-color)` | 科技青强调 |

---

## 五、ECharts 图表主题模板

```typescript
// 统一图表主题配置
export const darkChartTheme = {
  backgroundColor: 'transparent',
  textStyle: {
    color: 'rgba(255, 255, 255, 0.65)'
  },
  title: {
    textStyle: {
      color: 'rgba(255, 255, 255, 0.95)'
    },
    subtextStyle: {
      color: 'rgba(255, 255, 255, 0.65)'
    }
  },
  legend: {
    textStyle: {
      color: 'rgba(255, 255, 255, 0.65)'
    }
  },
  tooltip: {
    backgroundColor: 'rgba(26, 42, 74, 0.95)',
    borderColor: 'rgba(0, 212, 255, 0.3)',
    textStyle: {
      color: 'rgba(255, 255, 255, 0.85)'
    }
  },
  xAxis: {
    axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.1)' } },
    axisLabel: { color: 'rgba(255, 255, 255, 0.65)' },
    splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } }
  },
  yAxis: {
    axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.1)' } },
    axisLabel: { color: 'rgba(255, 255, 255, 0.65)' },
    splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } }
  },
  grid: {
    borderColor: 'rgba(255, 255, 255, 0.1)'
  },
  color: ['#00d4ff', '#1890ff', '#52c41a', '#faad14', '#f5222d', '#722ed1']
}
```

---

## 六、验证清单

完成所有任务后检查：

- [ ] 所有页面使用深色背景（无白色区域）
- [ ] 所有文字清晰可读（对比度足够）
- [ ] 所有 ECharts 图表使用统一深色主题
- [ ] 所有表格表头和行使用深色样式
- [ ] 所有卡片使用半透明深色背景
- [ ] 所有表单输入框使用深色样式
- [ ] 所有状态标签颜色统一
- [ ] 告警颜色符合等级规范
- [ ] 构建无错误
- [ ] 文档已更新

---

## 七、回滚方案

如遇问题，可通过 git 回滚：
```bash
git revert HEAD~N  # N 为需要回滚的提交数
```

或恢复单个文件：
```bash
git checkout HEAD~1 -- path/to/file
```
