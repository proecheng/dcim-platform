# 数字孪生大屏面板修复实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复数字孪生大屏的三个交互问题：导航不影响主界面、面板折叠显示半透明标题、面板始终可拖拽

**Architecture:** 修改 DraggablePanel 组件的折叠行为和样式，确保大屏界面与主界面完全隔离

**Tech Stack:** Vue 3, TypeScript, SCSS

---

## 问题分析

### 问题1：导航影响主界面
**现象**: 当大屏在同一窗口打开时，点击返回按钮会用 Vue Router 导航，改变主界面状态
**根因**: `goBack()` 函数在没有 `window.opener` 时使用 `router.push('/dashboard')`
**解决方案**: 大屏应始终在新标签页打开，返回时直接关闭标签页

### 问题2：面板折叠时显示不正确
**现象**: 折叠时面板宽度缩小到50px，只显示2个字符的缩写
**要求**: 折叠时应保留半透明的面板标题栏，隐藏下面的内容
**解决方案**: 重新设计 DraggablePanel 的折叠样式

### 问题3：折叠状态下无法拖拽
**现象**: `startDrag` 函数在 `isCollapsed` 为 true 时直接返回
**要求**: 即使折叠状态也应可拖拽
**解决方案**: 移除折叠状态下的拖拽限制

---

## Task 1: 修复大屏打开方式

**Files:**
- Modify: `frontend/src/views/dashboard/index.vue` (找到大屏入口按钮)
- Modify: `frontend/src/views/bigscreen/index.vue:388-396`

**Step 1: 查找仪表盘中的大屏入口**

在仪表盘中，大屏入口应使用 `window.open` 而非路由导航，确保大屏始终在新标签页打开。

**Step 2: 修改 bigscreen/index.vue 的 goBack 函数**

```typescript
// 修改前
function goBack() {
  if (window.opener) {
    window.close()
  } else {
    router.push('/dashboard')
  }
}

// 修改后
function goBack() {
  // 始终尝试关闭当前窗口/标签页
  // 如果是新标签页打开的，会成功关闭
  // 如果不能关闭（浏览器安全限制），则导航到首页
  try {
    window.close()
    // 如果关闭失败（脚本无法关闭非脚本打开的窗口），则执行导航
    setTimeout(() => {
      // 仍在页面上，说明关闭失败
      window.location.href = '/'
    }, 100)
  } catch (e) {
    window.location.href = '/'
  }
}
```

**Step 3: 验证仪表盘大屏入口**

检查 dashboard/index.vue 中打开大屏的代码，确保使用 `window.open`。

---

## Task 2: 重新设计 DraggablePanel 折叠样式

**Files:**
- Modify: `frontend/src/components/bigscreen/ui/DraggablePanel.vue`

**Step 1: 修改模板结构**

将折叠时的显示方式从"缩小宽度+显示缩写"改为"保持宽度+隐藏内容+半透明标题栏"。

```vue
<template>
  <div
    ref="panelRef"
    class="draggable-panel"
    :class="{ collapsed: isCollapsed, dragging: isDragging }"
    :style="panelStyle"
  >
    <!-- 拖拽手柄/标题栏 - 始终显示 -->
    <div
      class="panel-header"
      :class="{ 'collapsed-header': isCollapsed }"
      @mousedown="startDrag"
      @touchstart="startDrag"
    >
      <div class="header-left">
        <span class="panel-title">{{ title }}</span>
      </div>
      <div class="header-controls">
        <button class="control-btn" @click.stop="toggleCollapse" :title="isCollapsed ? '展开' : '收起'">
          <span class="icon">{{ isCollapsed ? '▼' : '▲' }}</span>
        </button>
        <button v-if="closable" class="control-btn close" @click.stop="$emit('close')" title="关闭">
          <span class="icon">×</span>
        </button>
      </div>
    </div>

    <!-- 内容区域 - 仅在展开时显示 -->
    <Transition name="collapse">
      <div v-show="!isCollapsed" class="panel-content">
        <slot></slot>
      </div>
    </Transition>
  </div>
</template>
```

**Step 2: 移除折叠时拖拽限制**

```typescript
function startDrag(e: MouseEvent | TouchEvent) {
  // 移除这行: if (isCollapsed.value) return

  isDragging.value = true
  // ... 其余代码保持不变
}
```

**Step 3: 修改折叠样式**

```scss
.draggable-panel {
  position: absolute;
  z-index: 100;
  background: rgba(0, 20, 40, 0.9);
  border: 1px solid rgba(0, 200, 255, 0.3);
  border-radius: 8px;
  backdrop-filter: blur(10px);
  transition: box-shadow 0.2s ease;
  // 移除: width 0.3s ease

  &.dragging {
    box-shadow: 0 8px 32px rgba(0, 200, 255, 0.3);
    z-index: 200;
    cursor: grabbing;
  }

  &.collapsed {
    // 移除宽度限制
    // 不再设置 width: 50px

    .panel-header {
      // 折叠时标题栏变为半透明
      background: rgba(0, 50, 80, 0.6);
      border-bottom: none;
      border-radius: 8px;
    }
  }
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: linear-gradient(180deg, rgba(0, 100, 150, 0.4) 0%, rgba(0, 50, 100, 0.2) 100%);
  border-bottom: 1px solid rgba(0, 200, 255, 0.2);
  border-radius: 8px 8px 0 0;
  cursor: grab;
  user-select: none;

  &:active {
    cursor: grabbing;
  }

  &.collapsed-header {
    border-radius: 8px;
  }
}

// 移除 .collapsed-title 相关样式（不再需要）
```

**Step 4: 运行构建验证**

```bash
cd frontend && npm run build
```
Expected: 构建成功，无错误

---

## Task 3: 修改 LeftPanel 确保折叠时宽度正确

**Files:**
- Modify: `frontend/src/components/bigscreen/panels/LeftPanel.vue`

**Step 1: 检查当前实现**

LeftPanel 已经使用 DraggablePanel，无需修改模板结构。确认样式在折叠时正确显示。

**Step 2: 添加必要的样式覆盖（如需要）**

如果 LeftPanel 的内容区域在折叠时仍然影响宽度，添加样式确保内容被正确隐藏。

---

## Task 4: 修改 RightPanel 确保折叠时宽度正确

**Files:**
- Modify: `frontend/src/components/bigscreen/panels/RightPanel.vue`

**Step 1: 检查当前实现**

RightPanel 已经使用 DraggablePanel。确认样式在折叠时正确显示。

---

## Task 5: 修改 FloorSelector 确保折叠时宽度正确

**Files:**
- Modify: `frontend/src/components/bigscreen/FloorSelector.vue`

**Step 1: 检查当前实现**

FloorSelector 已经使用 DraggablePanel。确认样式在折叠时正确显示。

---

## Task 6: 功能测试与验证

**Step 1: 启动开发服务器**

```bash
cd frontend && npm run dev
```

**Step 2: 测试导航隔离**

1. 在仪表盘点击"打开数字孪生大屏"按钮
2. 确认大屏在新标签页打开
3. 在大屏中点击返回按钮
4. 确认标签页关闭，主界面不受影响

**Step 3: 测试面板折叠**

1. 点击左侧面板的折叠按钮
2. 确认面板标题栏变为半透明，保持原有宽度
3. 确认内容被隐藏
4. 点击展开按钮，确认内容重新显示

**Step 4: 测试折叠状态拖拽**

1. 折叠任意面板
2. 拖拽折叠后的面板标题栏
3. 确认面板可以移动位置

**Step 5: 测试右侧面板**

重复上述折叠和拖拽测试

**Step 6: 测试楼层选择器**

重复上述折叠和拖拽测试

---

## Task 7: 构建验证

**Step 1: 运行生产构建**

```bash
cd frontend && npm run build
```
Expected: 构建成功

**Step 2: 检查构建输出**

确认无警告和错误

---

## Task 8: 更新文档

**Files:**
- Modify: `docs/plans/2026-01-19-bigscreen-digital-twin-design.md`
- Modify: `progress.md`
- Modify: `findings.md`
- Modify: `task_plan.md`

**Step 1: 更新设计文档**

在 7.5 可拖拽面板系统 部分添加折叠行为说明：

```markdown
#### 折叠行为

| 状态 | 显示效果 |
|------|----------|
| 展开 | 完整面板：标题栏 + 内容区域 |
| 折叠 | 仅显示半透明标题栏，内容隐藏，保持原有宽度 |

**设计原则：**
- 折叠时标题栏保持可见，用户可识别面板类型
- 折叠状态下面板仍可拖拽
- 使用 CSS transition 实现平滑动画
```

**Step 2: 更新 progress.md**

添加新的会话记录

**Step 3: 更新 findings.md**

添加 V4.2 面板交互修复的记录

**Step 4: 更新 task_plan.md**

添加 Phase 22 的完成记录

---

## 验证清单

- [ ] 大屏始终在新标签页打开
- [ ] 点击返回按钮关闭大屏标签页，不影响主界面
- [ ] 面板折叠时显示半透明标题栏
- [ ] 面板折叠时内容被隐藏
- [ ] 面板折叠时保持原有宽度（不缩小到50px）
- [ ] 面板在折叠状态下可拖拽
- [ ] 所有面板（左侧、右侧、楼层选择器）折叠行为一致
- [ ] 构建成功无错误
- [ ] 文档已更新
