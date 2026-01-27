# 深色科技风主题实施计划 ✅ COMPLETE

> **Implementation Status:** All 7 tasks completed successfully on 2026-01-20.
> **Build Status:** ✅ Passed (31.42s)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将算力中心智能监控系统升级为深色科技风主题，对齐行业DCIM系统UI标准

**Architecture:** 基于CSS变量实现主题系统，覆盖Element Plus默认样式，统一全站深色背景+青色强调的视觉风格

**Tech Stack:** Vue 3 + SCSS + Element Plus + CSS Variables

---

## Task 1: 创建深色主题变量文件

**Files:**
- Create: `frontend/src/styles/themes/dark-tech.scss`

**Step 1: 创建目录和主题变量文件**

```scss
// frontend/src/styles/themes/dark-tech.scss

// ============================================
// 深色科技风主题变量 - 基于行业DCIM系统UI研究
// ============================================

// ============= 背景色系 =============
$bg-primary: #0a1628;           // 主背景色 (最深)
$bg-secondary: #0d1b2a;         // 次级背景
$bg-tertiary: #112240;          // 三级背景
$bg-card: rgba(26, 42, 74, 0.85); // 卡片背景 (半透明)
$bg-card-solid: #1a2a4a;        // 卡片背景 (实色)
$bg-hover: rgba(24, 144, 255, 0.1); // 悬停背景
$bg-active: rgba(24, 144, 255, 0.2); // 激活背景

// ============= 主色系 =============
$primary-color: #1890ff;        // 主色 (Element Plus蓝)
$primary-light: #40a9ff;        // 主色浅
$primary-lighter: #69c0ff;      // 主色更浅
$primary-dark: #096dd9;         // 主色深

// ============= 强调色 (科技青) =============
$accent-color: #00d4ff;         // 强调色
$accent-light: #00f7ff;         // 强调色浅
$accent-glow: rgba(0, 212, 255, 0.3); // 发光效果

// ============= 状态色 =============
$success-color: #52c41a;        // 成功/正常
$success-light: #73d13d;
$warning-color: #faad14;        // 警告
$warning-light: #ffc53d;
$error-color: #f5222d;          // 错误/危险
$error-light: #ff4d4f;
$info-color: #1890ff;           // 信息

// ============= 告警等级色 =============
$alarm-critical: #ff4d4f;       // 紧急 (1级)
$alarm-major: #fa8c16;          // 重要 (2级)
$alarm-minor: #faad14;          // 一般 (3级)
$alarm-info: #1890ff;           // 提示 (4级)

// ============= 文字色 =============
$text-primary: rgba(255, 255, 255, 0.95);   // 主要文字
$text-regular: rgba(255, 255, 255, 0.85);   // 常规文字
$text-secondary: rgba(255, 255, 255, 0.65); // 次要文字
$text-placeholder: rgba(255, 255, 255, 0.45); // 占位符
$text-disabled: rgba(255, 255, 255, 0.25);  // 禁用文字

// ============= 边框色 =============
$border-color: rgba(255, 255, 255, 0.1);      // 默认边框
$border-light: rgba(255, 255, 255, 0.06);     // 浅色边框
$border-lighter: rgba(255, 255, 255, 0.03);   // 更浅边框
$border-active: rgba(0, 212, 255, 0.5);       // 激活边框
$border-glow: rgba(0, 212, 255, 0.3);         // 发光边框

// ============= 阴影 =============
$shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.3);
$shadow-base: 0 4px 12px rgba(0, 0, 0, 0.4);
$shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.5);
$shadow-glow: 0 0 20px rgba(0, 212, 255, 0.2);

// ============= 尺寸 =============
$header-height: 60px;
$sidebar-width: 220px;
$sidebar-collapsed-width: 64px;

// ============= 圆角 =============
$radius-sm: 2px;
$radius-base: 4px;
$radius-lg: 8px;
$radius-xl: 12px;

// ============= 过渡 =============
$transition-fast: 0.15s ease;
$transition-base: 0.25s ease;
$transition-slow: 0.35s ease;

// ============= 图表配色 =============
$chart-colors: (
  #5470c6,  // 蓝
  #91cc75,  // 绿
  #fac858,  // 黄
  #ee6666,  // 红
  #73c0de,  // 青
  #3ba272,  // 深绿
  #fc8452,  // 橙
  #9a60b4,  // 紫
  #ea7ccc,  // 粉
  #48b8d0   // 湖蓝
);

// ============= CSS Variables 导出 =============
:root {
  // 背景
  --bg-primary: #{$bg-primary};
  --bg-secondary: #{$bg-secondary};
  --bg-tertiary: #{$bg-tertiary};
  --bg-card: #{$bg-card};
  --bg-card-solid: #{$bg-card-solid};
  --bg-hover: #{$bg-hover};
  --bg-active: #{$bg-active};

  // 主色
  --primary-color: #{$primary-color};
  --primary-light: #{$primary-light};
  --primary-lighter: #{$primary-lighter};
  --primary-dark: #{$primary-dark};

  // 强调色
  --accent-color: #{$accent-color};
  --accent-light: #{$accent-light};
  --accent-glow: #{$accent-glow};

  // 状态色
  --success-color: #{$success-color};
  --warning-color: #{$warning-color};
  --error-color: #{$error-color};
  --info-color: #{$info-color};

  // 告警色
  --alarm-critical: #{$alarm-critical};
  --alarm-major: #{$alarm-major};
  --alarm-minor: #{$alarm-minor};
  --alarm-info: #{$alarm-info};

  // 文字
  --text-primary: #{$text-primary};
  --text-regular: #{$text-regular};
  --text-secondary: #{$text-secondary};
  --text-placeholder: #{$text-placeholder};
  --text-disabled: #{$text-disabled};

  // 边框
  --border-color: #{$border-color};
  --border-light: #{$border-light};
  --border-active: #{$border-active};
  --border-glow: #{$border-glow};

  // 阴影
  --shadow-sm: #{$shadow-sm};
  --shadow-base: #{$shadow-base};
  --shadow-lg: #{$shadow-lg};
  --shadow-glow: #{$shadow-glow};

  // 尺寸
  --header-height: #{$header-height};
  --sidebar-width: #{$sidebar-width};
  --sidebar-collapsed-width: #{$sidebar-collapsed-width};

  // 圆角
  --radius-sm: #{$radius-sm};
  --radius-base: #{$radius-base};
  --radius-lg: #{$radius-lg};
}
```

**Step 2: 验证文件创建成功**

Run: `dir frontend\src\styles\themes\`
Expected: 显示 dark-tech.scss 文件

**Step 3: Commit**

```bash
git add frontend/src/styles/themes/dark-tech.scss
git commit -m "feat: add dark tech theme variables

- Define complete color system (background, primary, accent, status)
- Define alarm level colors
- Define text colors with opacity levels
- Define border and shadow variables
- Export as CSS variables for runtime use"
```

---

## Task 2: 创建 Element Plus 深色主题覆盖

**Files:**
- Create: `frontend/src/styles/element-dark.scss`

**Step 1: 创建 Element Plus 覆盖样式文件**

```scss
// frontend/src/styles/element-dark.scss
// Element Plus 深色主题覆盖样式

@use './themes/dark-tech.scss' as theme;

// ============= 全局覆盖 =============

// 按钮
.el-button {
  --el-button-bg-color: transparent;
  --el-button-border-color: var(--border-color);
  --el-button-text-color: var(--text-regular);
  --el-button-hover-bg-color: var(--bg-hover);
  --el-button-hover-border-color: var(--primary-color);
  --el-button-hover-text-color: var(--primary-color);

  &--primary {
    --el-button-bg-color: var(--primary-color);
    --el-button-border-color: var(--primary-color);
    --el-button-text-color: #fff;
    --el-button-hover-bg-color: var(--primary-light);
    --el-button-hover-border-color: var(--primary-light);

    &.is-plain {
      --el-button-bg-color: transparent;
      --el-button-text-color: var(--primary-color);
      --el-button-hover-bg-color: var(--primary-color);
      --el-button-hover-text-color: #fff;
    }
  }

  &--success {
    --el-button-bg-color: var(--success-color);
    --el-button-border-color: var(--success-color);
  }

  &--warning {
    --el-button-bg-color: var(--warning-color);
    --el-button-border-color: var(--warning-color);
  }

  &--danger {
    --el-button-bg-color: var(--error-color);
    --el-button-border-color: var(--error-color);
  }
}

// 输入框
.el-input {
  --el-input-bg-color: var(--bg-tertiary);
  --el-input-border-color: var(--border-color);
  --el-input-text-color: var(--text-regular);
  --el-input-placeholder-color: var(--text-placeholder);
  --el-input-hover-border-color: var(--primary-color);
  --el-input-focus-border-color: var(--accent-color);

  .el-input__wrapper {
    background-color: var(--bg-tertiary);
    box-shadow: 0 0 0 1px var(--border-color) inset;

    &:hover {
      box-shadow: 0 0 0 1px var(--primary-color) inset;
    }

    &.is-focus {
      box-shadow: 0 0 0 1px var(--accent-color) inset, var(--shadow-glow);
    }
  }
}

// 选择器
.el-select {
  --el-select-border-color-hover: var(--primary-color);

  .el-input__wrapper {
    background-color: var(--bg-tertiary);
  }
}

.el-select-dropdown {
  background-color: var(--bg-card-solid);
  border-color: var(--border-color);

  .el-select-dropdown__item {
    color: var(--text-regular);

    &:hover {
      background-color: var(--bg-hover);
    }

    &.selected {
      color: var(--primary-color);
      background-color: var(--bg-active);
    }
  }
}

// 表格
.el-table {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: var(--bg-tertiary);
  --el-table-header-text-color: var(--text-primary);
  --el-table-text-color: var(--text-regular);
  --el-table-border-color: var(--border-color);
  --el-table-row-hover-bg-color: var(--bg-hover);
  --el-table-current-row-bg-color: var(--bg-active);

  background-color: transparent;

  th.el-table__cell {
    background-color: var(--bg-tertiary);
    color: var(--text-primary);
    font-weight: 600;
  }

  tr {
    background-color: transparent;

    &:hover > td.el-table__cell {
      background-color: var(--bg-hover);
    }
  }

  // 斑马纹
  &--striped .el-table__body tr.el-table__row--striped td.el-table__cell {
    background-color: rgba(255, 255, 255, 0.02);
  }
}

// 卡片
.el-card {
  --el-card-bg-color: var(--bg-card);
  --el-card-border-color: var(--border-color);

  background: var(--bg-card);
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-sm);

  .el-card__header {
    border-bottom-color: var(--border-color);
    color: var(--text-primary);
    padding: 16px 20px;
  }

  .el-card__body {
    color: var(--text-regular);
  }
}

// 标签
.el-tag {
  --el-tag-bg-color: var(--bg-hover);
  --el-tag-border-color: transparent;
  --el-tag-text-color: var(--text-regular);

  &--primary {
    --el-tag-bg-color: rgba(24, 144, 255, 0.2);
    --el-tag-text-color: var(--primary-color);
  }

  &--success {
    --el-tag-bg-color: rgba(82, 196, 26, 0.2);
    --el-tag-text-color: var(--success-color);
  }

  &--warning {
    --el-tag-bg-color: rgba(250, 173, 20, 0.2);
    --el-tag-text-color: var(--warning-color);
  }

  &--danger {
    --el-tag-bg-color: rgba(245, 34, 45, 0.2);
    --el-tag-text-color: var(--error-color);
  }

  &--info {
    --el-tag-bg-color: rgba(144, 147, 153, 0.2);
    --el-tag-text-color: var(--text-secondary);
  }
}

// 菜单
.el-menu {
  --el-menu-bg-color: var(--bg-secondary);
  --el-menu-text-color: var(--text-secondary);
  --el-menu-active-color: var(--accent-color);
  --el-menu-hover-bg-color: var(--bg-hover);
  --el-menu-item-height: 48px;

  background-color: var(--bg-secondary);
  border-right: none;

  .el-menu-item,
  .el-sub-menu__title {
    color: var(--text-secondary);

    &:hover {
      background-color: var(--bg-hover);
      color: var(--text-primary);
    }

    &.is-active {
      color: var(--accent-color);
      background-color: var(--bg-active);

      &::before {
        content: '';
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        width: 3px;
        background: var(--accent-color);
      }
    }
  }

  .el-sub-menu.is-active > .el-sub-menu__title {
    color: var(--accent-color);
  }
}

// 弹窗
.el-dialog {
  --el-dialog-bg-color: var(--bg-card-solid);
  --el-dialog-title-font-size: 18px;

  background: var(--bg-card-solid);
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-lg);

  .el-dialog__header {
    border-bottom: 1px solid var(--border-color);
    padding: 16px 20px;
  }

  .el-dialog__title {
    color: var(--text-primary);
  }

  .el-dialog__body {
    color: var(--text-regular);
  }

  .el-dialog__footer {
    border-top: 1px solid var(--border-color);
    padding: 12px 20px;
  }
}

// 抽屉
.el-drawer {
  --el-drawer-bg-color: var(--bg-card-solid);

  .el-drawer__header {
    border-bottom: 1px solid var(--border-color);
    color: var(--text-primary);
    margin-bottom: 0;
    padding: 16px 20px;
  }

  .el-drawer__body {
    color: var(--text-regular);
  }
}

// 分页
.el-pagination {
  --el-pagination-bg-color: transparent;
  --el-pagination-text-color: var(--text-secondary);
  --el-pagination-button-bg-color: var(--bg-tertiary);
  --el-pagination-button-color: var(--text-secondary);
  --el-pagination-hover-color: var(--primary-color);

  .el-pager li {
    background-color: var(--bg-tertiary);
    color: var(--text-secondary);

    &:hover {
      color: var(--primary-color);
    }

    &.is-active {
      background-color: var(--primary-color);
      color: #fff;
    }
  }
}

// 表单
.el-form-item__label {
  color: var(--text-regular);
}

// 日期选择器
.el-date-editor {
  --el-date-editor-bg: var(--bg-tertiary);
}

.el-picker-panel {
  background: var(--bg-card-solid);
  border-color: var(--border-color);
  color: var(--text-regular);

  .el-date-table th {
    color: var(--text-secondary);
  }

  .el-date-table td.available:hover {
    background-color: var(--bg-hover);
  }

  .el-date-table td.current:not(.disabled) span {
    background-color: var(--primary-color);
  }
}

// 消息提示
.el-message {
  --el-message-bg-color: var(--bg-card-solid);
  --el-message-border-color: var(--border-color);

  background-color: var(--bg-card-solid);
  border-color: var(--border-color);
}

// 通知
.el-notification {
  --el-notification-bg-color: var(--bg-card-solid);
  --el-notification-title-color: var(--text-primary);
  --el-notification-content-color: var(--text-regular);

  background-color: var(--bg-card-solid);
  border-color: var(--border-color);
}

// 面包屑
.el-breadcrumb {
  .el-breadcrumb__item {
    .el-breadcrumb__inner {
      color: var(--text-secondary);

      &.is-link:hover {
        color: var(--primary-color);
      }
    }

    &:last-child .el-breadcrumb__inner {
      color: var(--text-primary);
    }
  }

  .el-breadcrumb__separator {
    color: var(--text-placeholder);
  }
}

// 空状态
.el-empty {
  --el-empty-description-margin-top: 20px;

  .el-empty__description {
    color: var(--text-secondary);
  }
}

// Tooltip
.el-tooltip__popper {
  &.is-dark {
    background: var(--bg-card-solid);
    border-color: var(--border-color);
    color: var(--text-regular);
  }
}

// 进度条
.el-progress {
  .el-progress__text {
    color: var(--text-regular);
  }
}

// 徽章
.el-badge__content {
  border: none;
}

// 下拉菜单
.el-dropdown-menu {
  background-color: var(--bg-card-solid);
  border-color: var(--border-color);

  .el-dropdown-menu__item {
    color: var(--text-regular);

    &:hover {
      background-color: var(--bg-hover);
      color: var(--primary-color);
    }

    &.is-disabled {
      color: var(--text-disabled);
    }
  }

  .el-dropdown-menu__item--divided::before {
    background-color: var(--border-color);
  }
}
```

**Step 2: 验证文件创建成功**

Run: `dir frontend\src\styles\`
Expected: 显示 element-dark.scss 文件

**Step 3: Commit**

```bash
git add frontend/src/styles/element-dark.scss
git commit -m "feat: add Element Plus dark theme overrides

- Override button styles for dark theme
- Override input, select components
- Override table with transparent background
- Override card with glass effect
- Override menu with active indicator
- Override dialog, drawer, pagination
- Override tag colors for status display"
```

---

## Task 3: 更新全局样式入口文件

**Files:**
- Modify: `frontend/src/styles/index.scss`

**Step 1: 备份现有文件内容**

Run: `type frontend\src\styles\index.scss`
Expected: 查看当前内容

**Step 2: 更新全局样式文件**

```scss
// frontend/src/styles/index.scss

// 导入主题变量
@use './themes/dark-tech.scss';

// 导入 Element Plus 覆盖
@import './element-dark.scss';

// ============= 全局基础样式 =============

* {
  box-sizing: border-box;
}

html, body {
  margin: 0;
  padding: 0;
  height: 100%;
  background: var(--bg-primary);
  color: var(--text-regular);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

#app {
  height: 100%;
}

// ============= 滚动条样式 =============

::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;

  &:hover {
    background: rgba(255, 255, 255, 0.3);
  }
}

::-webkit-scrollbar-track {
  background: transparent;
}

// ============= 告警级别颜色 =============

.alarm-critical {
  color: var(--alarm-critical);
}

.alarm-major {
  color: var(--alarm-major);
}

.alarm-minor {
  color: var(--alarm-minor);
}

.alarm-info {
  color: var(--alarm-info);
}

// ============= 状态颜色 =============

.status-normal {
  color: var(--success-color);
}

.status-alarm {
  color: var(--error-color);
}

.status-offline {
  color: var(--text-disabled);
}

// ============= 点位类型颜色 =============

.point-type-ai {
  color: var(--primary-color);
}

.point-type-di {
  color: var(--success-color);
}

.point-type-ao {
  color: var(--warning-color);
}

.point-type-do {
  color: var(--error-color);
}

// ============= 通用工具类 =============

.text-primary {
  color: var(--text-primary);
}

.text-secondary {
  color: var(--text-secondary);
}

.text-success {
  color: var(--success-color);
}

.text-warning {
  color: var(--warning-color);
}

.text-danger {
  color: var(--error-color);
}

.bg-card {
  background: var(--bg-card);
}

.border-glow {
  border: 1px solid var(--border-glow);
  box-shadow: var(--shadow-glow);
}

// ============= 发光效果 =============

.glow-text {
  text-shadow: 0 0 10px var(--accent-glow);
}

.glow-box {
  box-shadow: var(--shadow-glow);
}

// ============= 卡片悬浮效果 =============

.hover-lift {
  transition: transform var(--transition-base), box-shadow var(--transition-base);

  &:hover {
    transform: translateY(-4px);
    box-shadow: var(--shadow-lg);
  }
}

// ============= 渐变边框 =============

.gradient-border {
  position: relative;

  &::before {
    content: '';
    position: absolute;
    inset: 0;
    padding: 1px;
    border-radius: inherit;
    background: linear-gradient(135deg, var(--accent-color), var(--primary-color));
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    -webkit-mask-composite: xor;
    mask-composite: exclude;
  }
}
```

**Step 3: 验证语法正确**

Run: `cd frontend && npm run build -- --mode development 2>&1 | findstr -i "error"`
Expected: 无 SCSS 语法错误

**Step 4: Commit**

```bash
git add frontend/src/styles/index.scss
git commit -m "feat: update global styles with dark theme

- Import dark theme variables
- Import Element Plus overrides
- Update base styles for dark background
- Update scrollbar styles
- Add utility classes for colors and effects
- Add glow and gradient border effects"
```

---

## Task 4: 更新主布局组件

**Files:**
- Modify: `frontend/src/layouts/MainLayout.vue`

**Step 1: 更新 MainLayout 模板和样式**

将 MainLayout.vue 的 `<style>` 部分更新为：

```vue
<style scoped lang="scss">
.main-layout {
  height: 100vh;
  background: var(--bg-primary);
}

.aside {
  background: var(--bg-secondary);
  border-right: 1px solid var(--border-color);
  transition: width 0.3s;
  overflow: hidden;

  .logo {
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    color: var(--accent-color);
    font-size: 16px;
    font-weight: bold;
    border-bottom: 1px solid var(--border-color);
    background: var(--bg-primary);

    .el-icon {
      color: var(--accent-color);
    }
  }

  .el-menu {
    border-right: none;
    background: transparent;
  }
}

.header {
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  height: var(--header-height);

  .header-left {
    display: flex;
    align-items: center;
    gap: 16px;

    .collapse-btn {
      cursor: pointer;
      color: var(--text-secondary);
      transition: color var(--transition-fast);

      &:hover {
        color: var(--accent-color);
      }
    }
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 20px;

    .alarm-badge {
      margin-right: 10px;

      .el-button {
        color: var(--text-secondary);
        border-color: var(--border-color);
        background: transparent;

        &:hover {
          color: var(--accent-color);
          border-color: var(--accent-color);
        }
      }
    }

    .user-info {
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      padding: 4px 8px;
      border-radius: var(--radius-base);
      transition: background var(--transition-fast);

      &:hover {
        background: var(--bg-hover);
      }

      .username {
        color: var(--text-regular);
      }

      .el-icon {
        color: var(--text-secondary);
      }
    }
  }
}

.main {
  background: var(--bg-primary);
  padding: 20px;
  overflow-y: auto;
}
</style>
```

**Step 2: 更新 MainLayout 的菜单组件属性**

更新 `<el-menu>` 组件，移除硬编码颜色：

```vue
<el-menu
  :default-active="$route.path"
  :collapse="isCollapse"
  :router="true"
  class="dark-menu"
>
```

**Step 3: 验证布局正常**

Run: `cd frontend && npm run dev`
Expected: 开发服务器启动，布局正常显示深色主题

**Step 4: Commit**

```bash
git add frontend/src/layouts/MainLayout.vue
git commit -m "feat: update MainLayout with dark theme styles

- Apply dark background to sidebar and header
- Update logo with accent color glow
- Update menu styles for dark theme
- Update user info hover effect
- Remove hardcoded colors, use CSS variables"
```

---

## Task 5: 更新仪表盘页面

**Files:**
- Modify: `frontend/src/views/dashboard/index.vue`

**Step 1: 更新仪表盘样式**

将 dashboard/index.vue 的 `<style>` 部分更新为：

```vue
<style scoped lang="scss">
.dashboard {
  .stat-cards {
    margin-bottom: 20px;
  }

  .quick-actions {
    margin-bottom: 20px;

    :deep(.el-card) {
      background: var(--bg-card);
      border-color: var(--border-color);
    }

    .actions-content {
      display: flex;
      align-items: center;
      gap: 16px;

      .actions-title {
        font-weight: 600;
        color: var(--text-primary);
        margin-right: 8px;
      }
    }
  }

  .stat-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    transition: all var(--transition-base);

    &:hover {
      border-color: var(--border-glow);
      box-shadow: var(--shadow-glow);
      transform: translateY(-2px);
    }

    :deep(.el-card__body) {
      display: flex;
      align-items: center;
      gap: 20px;
    }

    .stat-icon {
      width: 64px;
      height: 64px;
      border-radius: var(--radius-lg);
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }

    .stat-info {
      .stat-value {
        font-size: 32px;
        font-weight: bold;
        color: var(--text-primary);
        font-family: 'DIN', monospace;
      }

      .stat-label {
        font-size: 14px;
        color: var(--text-secondary);
        margin-top: 4px;
      }
    }
  }

  .chart-row {
    margin-top: 20px;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    color: var(--text-primary);
  }

  .alarm-card {
    .alarm-list {
      max-height: 400px;
      overflow-y: auto;
    }

    .alarm-item {
      padding: 12px;
      border-left: 3px solid;
      margin-bottom: 10px;
      background: var(--bg-tertiary);
      border-radius: var(--radius-base);
      transition: all var(--transition-fast);

      &:hover {
        background: var(--bg-hover);
      }

      &.level-critical {
        border-color: var(--alarm-critical);
      }

      &.level-major {
        border-color: var(--alarm-major);
      }

      &.level-minor {
        border-color: var(--alarm-minor);
      }

      &.level-info {
        border-color: var(--alarm-info);
      }

      .alarm-title {
        display: flex;
        align-items: center;
        gap: 8px;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 4px;
      }

      .alarm-message {
        font-size: 13px;
        color: var(--text-secondary);
        margin-bottom: 4px;
      }

      .alarm-time {
        font-size: 12px;
        color: var(--text-placeholder);
      }
    }
  }

  // V2.3: 能源统计卡片
  .energy-cards {
    margin-bottom: 20px;

    :deep(.el-col) {
      & > div {
        height: 100%;
      }
    }
  }
}
</style>
```

**Step 2: 验证仪表盘显示正常**

Run: `cd frontend && npm run dev`
Expected: 访问 /dashboard，看到深色主题的仪表盘

**Step 3: Commit**

```bash
git add frontend/src/views/dashboard/index.vue
git commit -m "feat: update dashboard with dark theme styles

- Apply dark card backgrounds with glow effect on hover
- Update stat cards with modern styling
- Update alarm list with dark theme colors
- Use CSS variables throughout"
```

---

## Task 6: 创建 ECharts 深色主题配置

**Files:**
- Create: `frontend/src/utils/echarts-dark-theme.ts`

**Step 1: 创建 ECharts 主题配置文件**

```typescript
// frontend/src/utils/echarts-dark-theme.ts

import * as echarts from 'echarts'

/**
 * DCIM深色科技风 ECharts 主题
 */
export const darkTechTheme: echarts.ThemeOption = {
  color: [
    '#5470c6',
    '#91cc75',
    '#fac858',
    '#ee6666',
    '#73c0de',
    '#3ba272',
    '#fc8452',
    '#9a60b4',
    '#ea7ccc',
    '#48b8d0'
  ],

  backgroundColor: 'transparent',

  textStyle: {
    color: 'rgba(255, 255, 255, 0.65)'
  },

  title: {
    textStyle: {
      color: 'rgba(255, 255, 255, 0.95)',
      fontSize: 16,
      fontWeight: 600
    },
    subtextStyle: {
      color: 'rgba(255, 255, 255, 0.45)'
    }
  },

  legend: {
    textStyle: {
      color: 'rgba(255, 255, 255, 0.65)'
    },
    pageTextStyle: {
      color: 'rgba(255, 255, 255, 0.65)'
    }
  },

  tooltip: {
    backgroundColor: 'rgba(13, 27, 42, 0.95)',
    borderColor: 'rgba(0, 212, 255, 0.3)',
    borderWidth: 1,
    textStyle: {
      color: 'rgba(255, 255, 255, 0.85)'
    },
    extraCssText: 'box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);'
  },

  xAxis: {
    axisLine: {
      show: true,
      lineStyle: {
        color: 'rgba(255, 255, 255, 0.1)'
      }
    },
    axisTick: {
      show: true,
      lineStyle: {
        color: 'rgba(255, 255, 255, 0.1)'
      }
    },
    axisLabel: {
      color: 'rgba(255, 255, 255, 0.65)'
    },
    splitLine: {
      show: true,
      lineStyle: {
        color: 'rgba(255, 255, 255, 0.05)'
      }
    }
  },

  yAxis: {
    axisLine: {
      show: false
    },
    axisTick: {
      show: false
    },
    axisLabel: {
      color: 'rgba(255, 255, 255, 0.65)'
    },
    splitLine: {
      show: true,
      lineStyle: {
        color: 'rgba(255, 255, 255, 0.05)'
      }
    }
  },

  grid: {
    borderColor: 'rgba(255, 255, 255, 0.1)'
  },

  categoryAxis: {
    axisLine: {
      lineStyle: {
        color: 'rgba(255, 255, 255, 0.1)'
      }
    },
    axisTick: {
      lineStyle: {
        color: 'rgba(255, 255, 255, 0.1)'
      }
    },
    axisLabel: {
      color: 'rgba(255, 255, 255, 0.65)'
    },
    splitLine: {
      lineStyle: {
        color: 'rgba(255, 255, 255, 0.05)'
      }
    }
  },

  valueAxis: {
    axisLine: {
      show: false
    },
    axisTick: {
      show: false
    },
    axisLabel: {
      color: 'rgba(255, 255, 255, 0.65)'
    },
    splitLine: {
      lineStyle: {
        color: 'rgba(255, 255, 255, 0.05)'
      }
    }
  },

  line: {
    symbol: 'circle',
    symbolSize: 6,
    smooth: true
  },

  bar: {
    itemStyle: {
      borderRadius: [4, 4, 0, 0]
    }
  },

  pie: {
    itemStyle: {
      borderWidth: 2,
      borderColor: '#0a1628'
    }
  },

  gauge: {
    axisLine: {
      lineStyle: {
        color: [
          [0.3, '#52c41a'],
          [0.7, '#1890ff'],
          [1, '#ff4d4f']
        ],
        width: 12
      }
    },
    axisTick: {
      show: false
    },
    splitLine: {
      length: 12,
      lineStyle: {
        color: 'rgba(255, 255, 255, 0.3)'
      }
    },
    axisLabel: {
      color: 'rgba(255, 255, 255, 0.65)'
    },
    pointer: {
      width: 5
    },
    title: {
      color: 'rgba(255, 255, 255, 0.65)'
    },
    detail: {
      color: 'rgba(255, 255, 255, 0.95)',
      fontSize: 24,
      fontWeight: 'bold'
    }
  },

  dataZoom: {
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    dataBackgroundColor: 'rgba(255, 255, 255, 0.1)',
    fillerColor: 'rgba(24, 144, 255, 0.2)',
    handleColor: '#1890ff',
    textStyle: {
      color: 'rgba(255, 255, 255, 0.65)'
    }
  }
}

/**
 * 注册 ECharts 深色主题
 */
export function registerDarkTheme(): void {
  echarts.registerTheme('dark-tech', darkTechTheme)
}

/**
 * 获取主题名称
 */
export const DARK_THEME_NAME = 'dark-tech'
```

**Step 2: 在 main.ts 中注册主题**

在 `frontend/src/main.ts` 中添加：

```typescript
// 在其他 import 之后添加
import { registerDarkTheme } from './utils/echarts-dark-theme'

// 在 createApp 之前调用
registerDarkTheme()
```

**Step 3: 验证主题注册成功**

Run: `cd frontend && npm run build`
Expected: 构建成功，无错误

**Step 4: Commit**

```bash
git add frontend/src/utils/echarts-dark-theme.ts frontend/src/main.ts
git commit -m "feat: add ECharts dark theme configuration

- Create comprehensive dark theme for ECharts
- Configure colors, tooltips, axes, legends
- Add special styles for gauge, pie, bar charts
- Register theme globally in main.ts"
```

---

## Task 7: 构建验证和测试

**Files:**
- None (验证任务)

**Step 1: 执行完整构建**

Run: `cd frontend && npm run build`
Expected: 构建成功，无错误

**Step 2: 启动开发服务器**

Run: `cd frontend && npm run dev`
Expected: 开发服务器正常启动

**Step 3: 手动验证页面**

检查清单:
- [ ] 登录页面显示正常
- [ ] 主布局深色背景
- [ ] 左侧菜单深色主题
- [ ] 顶部导航深色主题
- [ ] 仪表盘卡片深色主题
- [ ] 数据表格深色主题
- [ ] 弹窗/对话框深色主题

**Step 4: 最终提交**

```bash
git add -A
git commit -m "feat: complete dark tech theme implementation (Phase 12)

- Added dark theme variable system
- Added Element Plus dark overrides
- Updated global styles
- Updated MainLayout component
- Updated Dashboard page
- Added ECharts dark theme

Closes Phase 12: 深色主题系统升级"
```

---

## Summary

完成以上7个任务后，系统将具备完整的深色科技风主题：

| 任务 | 内容 | 文件 |
|------|------|------|
| Task 1 | 主题变量定义 | `styles/themes/dark-tech.scss` |
| Task 2 | Element Plus覆盖 | `styles/element-dark.scss` |
| Task 3 | 全局样式更新 | `styles/index.scss` |
| Task 4 | 主布局更新 | `layouts/MainLayout.vue` |
| Task 5 | 仪表盘更新 | `views/dashboard/index.vue` |
| Task 6 | ECharts主题 | `utils/echarts-dark-theme.ts` |
| Task 7 | 构建验证 | - |

**关键配色**:
- 主背景: `#0a1628`
- 卡片背景: `rgba(26, 42, 74, 0.85)`
- 主色: `#1890ff`
- 强调色: `#00d4ff`
