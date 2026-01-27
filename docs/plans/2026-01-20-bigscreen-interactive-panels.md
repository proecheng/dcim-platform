# 数字孪生大屏交互面板增强实现计划

> **状态**: ✅ 已完成 (2026-01-21)
>
> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现大屏所有可点击组件在新标签页打开对应主界面，并使所有面板支持拖拽定位和展开/隐藏功能

**Architecture:** 统一导航行为 → 创建可拖拽面板组件 → 改造现有面板 → 持久化面板状态 → 更新文档

**Tech Stack:** Vue 3, TypeScript, Pinia, CSS3 Transform/Transition

## 实施结果

| 任务 | 状态 |
|------|------|
| Task 1: 统一导航行为 - 新标签页打开 | ✅ 完成 |
| Task 2: 创建可拖拽面板包装组件 | ✅ 完成 |
| Task 3: 创建面板状态管理 | ✅ 完成 |
| Task 4: 改造 LeftPanel 为可拖拽 | ✅ 完成 |
| Task 5: 改造 RightPanel 为可拖拽 | ✅ 完成 |
| Task 6: 改造 FloorSelector 为可拖拽 | ✅ 完成 |
| Task 7: 添加面板管理器到底部栏 | ✅ 完成 |
| Task 8: 更新大屏主视图集成 | ✅ 完成 |
| Task 9: 更新文档 | ✅ 完成 |

---

## 问题现状分析

| 问题 | 现状 | 目标 |
|------|------|------|
| 导航行为不一致 | 部分在父窗口导航，部分不导航 | 所有点击统一在新标签页打开 |
| 面板位置固定 | 面板使用absolute固定位置 | 支持拖拽到任意位置 |
| 折叠功能不完整 | LeftPanel/RightPanel有折叠，其他没有 | 所有面板支持展开/隐藏 |
| 状态不持久 | 刷新后状态丢失 | 面板位置和状态持久化 |

## 涉及面板组件

| 面板 | 当前位置 | 导航目标 | 现有折叠 |
|------|----------|----------|----------|
| LeftPanel | 左上 top:60px left:20px | /monitor, /alarm | ✅ 有 |
| RightPanel | 右上 top:60px right:20px | /energy/* | ✅ 有 |
| DeviceDetailPanel | 右侧滑入 top:60px right:20px | 无 | ❌ 无 |
| FloorSelector | 左上 top:80px left:20px | 无 | ❌ 无 |
| BottomBar | 底部居中 | 无 | ❌ 无 |

---

## Task 1: 统一导航行为 - 新标签页打开

**Files:**
- Modify: `frontend/src/views/bigscreen/index.vue`
- Modify: `frontend/src/components/bigscreen/panels/LeftPanel.vue`
- Modify: `frontend/src/components/bigscreen/panels/RightPanel.vue`

**Step 1: 修改 handleNavigate 函数**

在 `frontend/src/views/bigscreen/index.vue` 中修改（约L409-417）：

```typescript
// 导航到主界面指定页面 - 始终在新标签页打开
function handleNavigate(path: string) {
  // 构建完整URL
  const baseUrl = window.location.origin
  const fullUrl = `${baseUrl}${path}`

  // 始终在新标签页打开
  window.open(fullUrl, '_blank')
}
```

**Step 2: 验证**

Run: `cd D:/mytest1/frontend && npm run build`
Expected: 构建成功

---

## Task 2: 创建可拖拽面板包装组件

**Files:**
- Create: `frontend/src/components/bigscreen/ui/DraggablePanel.vue`
- Modify: `frontend/src/components/bigscreen/ui/index.ts`

**Step 1: 创建 DraggablePanel 组件**

```vue
<template>
  <div
    ref="panelRef"
    class="draggable-panel"
    :class="{ collapsed: isCollapsed, dragging: isDragging }"
    :style="panelStyle"
  >
    <!-- 拖拽手柄 -->
    <div
      class="panel-header"
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

    <!-- 内容区域 -->
    <Transition name="collapse">
      <div v-show="!isCollapsed" class="panel-content">
        <slot></slot>
      </div>
    </Transition>

    <!-- 折叠时的迷你标题 -->
    <div v-if="isCollapsed" class="collapsed-title">
      {{ title.substring(0, 2) }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = withDefaults(defineProps<{
  title: string
  initialX?: number
  initialY?: number
  initialCollapsed?: boolean
  closable?: boolean
  panelId: string
  minWidth?: number
  minHeight?: number
}>(), {
  initialX: 20,
  initialY: 60,
  initialCollapsed: false,
  closable: false,
  minWidth: 50,
  minHeight: 40
})

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'positionChange', data: { id: string; x: number; y: number }): void
  (e: 'collapseChange', data: { id: string; collapsed: boolean }): void
}>()

const panelRef = ref<HTMLDivElement>()
const isDragging = ref(false)
const isCollapsed = ref(props.initialCollapsed)

// 位置状态
const position = ref({ x: props.initialX, y: props.initialY })

// 拖拽起始位置
const dragStart = ref({ x: 0, y: 0 })
const positionStart = ref({ x: 0, y: 0 })

const panelStyle = computed(() => ({
  left: `${position.value.x}px`,
  top: `${position.value.y}px`
}))

function startDrag(e: MouseEvent | TouchEvent) {
  if (isCollapsed.value) return

  isDragging.value = true

  const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX
  const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY

  dragStart.value = { x: clientX, y: clientY }
  positionStart.value = { ...position.value }

  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
  document.addEventListener('touchmove', onDrag)
  document.addEventListener('touchend', stopDrag)
}

function onDrag(e: MouseEvent | TouchEvent) {
  if (!isDragging.value) return

  const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX
  const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY

  const deltaX = clientX - dragStart.value.x
  const deltaY = clientY - dragStart.value.y

  // 计算新位置，限制在视口内
  const newX = Math.max(0, Math.min(window.innerWidth - 100, positionStart.value.x + deltaX))
  const newY = Math.max(0, Math.min(window.innerHeight - 50, positionStart.value.y + deltaY))

  position.value = { x: newX, y: newY }
}

function stopDrag() {
  if (isDragging.value) {
    isDragging.value = false
    emit('positionChange', { id: props.panelId, x: position.value.x, y: position.value.y })
  }

  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
  document.removeEventListener('touchmove', onDrag)
  document.removeEventListener('touchend', stopDrag)
}

function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value
  emit('collapseChange', { id: props.panelId, collapsed: isCollapsed.value })
}

// 暴露方法供外部控制
function setPosition(x: number, y: number) {
  position.value = { x, y }
}

function setCollapsed(collapsed: boolean) {
  isCollapsed.value = collapsed
}

defineExpose({ setPosition, setCollapsed, position, isCollapsed })

onUnmounted(() => {
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
  document.removeEventListener('touchmove', onDrag)
  document.removeEventListener('touchend', stopDrag)
})
</script>

<style scoped lang="scss">
.draggable-panel {
  position: absolute;
  z-index: 100;
  background: rgba(0, 20, 40, 0.9);
  border: 1px solid rgba(0, 200, 255, 0.3);
  border-radius: 8px;
  backdrop-filter: blur(10px);
  transition: box-shadow 0.2s ease, width 0.3s ease;

  &.dragging {
    box-shadow: 0 8px 32px rgba(0, 200, 255, 0.3);
    z-index: 200;
    cursor: grabbing;
  }

  &.collapsed {
    width: 50px !important;
    min-width: 50px;

    .panel-header {
      padding: 8px;
      justify-content: center;

      .header-left, .header-controls {
        display: none;
      }
    }

    .collapsed-title {
      display: flex;
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
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.panel-title {
  color: #00ccff;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 1px;
}

.header-controls {
  display: flex;
  align-items: center;
  gap: 4px;
}

.control-btn {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 100, 150, 0.3);
  border: 1px solid rgba(0, 200, 255, 0.2);
  border-radius: 4px;
  color: #88ccff;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    background: rgba(0, 150, 200, 0.4);
    color: #ffffff;
  }

  &.close:hover {
    background: rgba(255, 50, 50, 0.4);
    border-color: rgba(255, 100, 100, 0.5);
  }

  .icon {
    font-size: 12px;
    line-height: 1;
  }
}

.panel-content {
  overflow: hidden;
}

.collapsed-title {
  display: none;
  align-items: center;
  justify-content: center;
  padding: 8px;
  color: #00ccff;
  font-size: 14px;
  font-weight: bold;
  writing-mode: vertical-rl;
  text-orientation: mixed;
}

// 折叠动画
.collapse-enter-active,
.collapse-leave-active {
  transition: all 0.3s ease;
  max-height: 800px;
  opacity: 1;
}

.collapse-enter-from,
.collapse-leave-to {
  max-height: 0;
  opacity: 0;
}
</style>
```

**Step 2: 更新 ui/index.ts 导出**

在 `frontend/src/components/bigscreen/ui/index.ts` 添加：
```typescript
export { default as DraggablePanel } from './DraggablePanel.vue'
```

**Step 3: 验证**

Run: `cd D:/mytest1/frontend && npm run build`
Expected: 构建成功

---

## Task 3: 创建面板状态管理

**Files:**
- Modify: `frontend/src/stores/bigscreen.ts`

**Step 1: 添加面板状态定义**

在 bigscreen store 中添加 panelStates 状态和相关 actions：

```typescript
// 在 state 中添加
panelStates: {
  leftPanel: { x: 20, y: 60, collapsed: false, visible: true },
  rightPanel: { x: -300, y: 60, collapsed: false, visible: true }, // 负数表示从右边计算
  deviceDetail: { x: -320, y: 60, collapsed: false, visible: true },
  floorSelector: { x: 20, y: 80, collapsed: false, visible: true },
  bottomBar: { collapsed: false, visible: true }
} as Record<string, { x?: number; y?: number; collapsed: boolean; visible: boolean }>

// 在 actions 中添加
updatePanelPosition(panelId: string, x: number, y: number) {
  if (this.panelStates[panelId]) {
    this.panelStates[panelId].x = x
    this.panelStates[panelId].y = y
    this.savePanelStates()
  }
},

updatePanelCollapsed(panelId: string, collapsed: boolean) {
  if (this.panelStates[panelId]) {
    this.panelStates[panelId].collapsed = collapsed
    this.savePanelStates()
  }
},

togglePanelVisible(panelId: string) {
  if (this.panelStates[panelId]) {
    this.panelStates[panelId].visible = !this.panelStates[panelId].visible
    this.savePanelStates()
  }
},

savePanelStates() {
  try {
    localStorage.setItem('bigscreen-panel-states', JSON.stringify(this.panelStates))
  } catch (e) {
    console.warn('Failed to save panel states:', e)
  }
},

loadPanelStates() {
  try {
    const saved = localStorage.getItem('bigscreen-panel-states')
    if (saved) {
      const parsed = JSON.parse(saved)
      Object.keys(parsed).forEach(key => {
        if (this.panelStates[key]) {
          this.panelStates[key] = { ...this.panelStates[key], ...parsed[key] }
        }
      })
    }
  } catch (e) {
    console.warn('Failed to load panel states:', e)
  }
},

resetPanelStates() {
  this.panelStates = {
    leftPanel: { x: 20, y: 60, collapsed: false, visible: true },
    rightPanel: { x: -300, y: 60, collapsed: false, visible: true },
    deviceDetail: { x: -320, y: 60, collapsed: false, visible: true },
    floorSelector: { x: 20, y: 80, collapsed: false, visible: true },
    bottomBar: { collapsed: false, visible: true }
  }
  this.savePanelStates()
}
```

**Step 2: 验证**

Run: `cd D:/mytest1/frontend && npm run build`
Expected: 构建成功

---

## Task 4: 改造 LeftPanel 为可拖拽

**Files:**
- Modify: `frontend/src/components/bigscreen/panels/LeftPanel.vue`

**Step 1: 重构 LeftPanel 使用 DraggablePanel**

重写 LeftPanel.vue，将内容包装在 DraggablePanel 中，移除原有的折叠逻辑：

```vue
<template>
  <DraggablePanel
    ref="panelRef"
    title="环境监测"
    panelId="leftPanel"
    :initialX="panelState.x"
    :initialY="panelState.y"
    :initialCollapsed="panelState.collapsed"
    @positionChange="handlePositionChange"
    @collapseChange="handleCollapseChange"
  >
    <div class="left-panel-content">
      <!-- 温湿度仪表 -->
      <div class="section gauges" @click="navigateTo('/monitor')">
        <div class="section-title">
          <span>温湿度监测</span>
          <span class="nav-hint">点击查看详情 →</span>
        </div>
        <div class="gauge-row">
          <GaugeChart
            title="平均温度"
            :value="store.environment.avgTemperature"
            unit="°C"
            :min="0"
            :max="50"
            color="#ff6b6b"
          />
          <GaugeChart
            title="平均湿度"
            :value="store.environment.avgHumidity"
            unit="%"
            :min="0"
            :max="100"
            color="#4ecdc4"
          />
        </div>
      </div>

      <!-- 温度趋势 -->
      <div class="section trend" @click="navigateTo('/monitor')">
        <div class="section-title">
          <span>温度趋势</span>
          <span class="nav-hint">→</span>
        </div>
        <TemperatureTrend :data="temperatureTrendData" />
      </div>

      <!-- 温湿度概览 -->
      <div class="section overview" @click="navigateTo('/monitor')">
        <div class="section-title">
          <span>环境概览</span>
          <span class="nav-hint">→</span>
        </div>
        <div class="overview-grid">
          <div class="overview-item">
            <span class="label">最高温度</span>
            <span class="value temp-high">{{ store.environment.maxTemperature.toFixed(1) }}°C</span>
          </div>
          <div class="overview-item">
            <span class="label">最低温度</span>
            <span class="value temp-low">{{ store.environment.minTemperature.toFixed(1) }}°C</span>
          </div>
          <div class="overview-item">
            <span class="label">最高湿度</span>
            <span class="value">{{ store.environment.maxHumidity.toFixed(1) }}%</span>
          </div>
          <div class="overview-item">
            <span class="label">最低湿度</span>
            <span class="value">{{ store.environment.minHumidity.toFixed(1) }}%</span>
          </div>
        </div>
      </div>

      <!-- 告警滚动列表 -->
      <div class="section alarms">
        <div class="section-title">
          <span>实时告警</span>
          <span class="view-all" @click.stop="viewAllAlarms">查看全部 →</span>
        </div>
        <div class="alarm-list">
          <div
            v-for="alarm in store.recentAlarms.slice(0, 5)"
            :key="alarm.id"
            class="alarm-item"
            :class="alarm.level"
            @click="locateAlarm(alarm)"
          >
            <span class="alarm-time">{{ formatTime(alarm.time) }}</span>
            <span class="alarm-device">{{ alarm.deviceName }}</span>
            <span class="alarm-message">{{ alarm.message }}</span>
          </div>
          <div v-if="store.recentAlarms.length === 0" class="no-alarm">
            暂无告警
          </div>
        </div>
      </div>
    </div>
  </DraggablePanel>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useBigscreenStore } from '@/stores/bigscreen'
import { DraggablePanel } from '@/components/bigscreen/ui'
import { GaugeChart, TemperatureTrend } from '@/components/bigscreen/charts'
import type { BigscreenAlarm } from '@/types/bigscreen'

const store = useBigscreenStore()
const panelRef = ref()

const emit = defineEmits<{
  (e: 'locateAlarm', alarm: BigscreenAlarm): void
  (e: 'viewAllAlarms'): void
  (e: 'navigate', path: string): void
}>()

// 从store获取面板状态
const panelState = computed(() => store.panelStates.leftPanel || { x: 20, y: 60, collapsed: false })

// 温度趋势数据
const temperatureTrendData = computed(() => {
  const now = Date.now()
  return Array.from({ length: 24 }, (_, i) => ({
    time: new Date(now - (23 - i) * 3600000).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    value: 22 + Math.random() * 6
  }))
})

function handlePositionChange(data: { id: string; x: number; y: number }) {
  store.updatePanelPosition(data.id, data.x, data.y)
}

function handleCollapseChange(data: { id: string; collapsed: boolean }) {
  store.updatePanelCollapsed(data.id, data.collapsed)
}

function navigateTo(path: string) {
  emit('navigate', path)
}

function locateAlarm(alarm: BigscreenAlarm) {
  emit('locateAlarm', alarm)
}

function viewAllAlarms() {
  emit('viewAllAlarms')
}

function formatTime(time: string | Date) {
  const date = typeof time === 'string' ? new Date(time) : time
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

onMounted(() => {
  store.loadPanelStates()
})
</script>

<style scoped lang="scss">
.left-panel-content {
  width: 280px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section {
  background: rgba(0, 50, 100, 0.3);
  border-radius: 6px;
  padding: 10px;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    background: rgba(0, 80, 130, 0.4);

    .nav-hint {
      opacity: 1;
      transform: translateX(3px);
    }
  }
}

.section-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #88ccff;
  font-size: 12px;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(0, 200, 255, 0.2);
}

.nav-hint {
  color: #00ccff;
  font-size: 10px;
  opacity: 0.5;
  transition: all 0.2s ease;
}

.view-all {
  color: #00ccff;
  font-size: 10px;
  cursor: pointer;

  &:hover {
    text-decoration: underline;
  }
}

.gauge-row {
  display: flex;
  gap: 10px;
}

.overview-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.overview-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px;
  background: rgba(0, 50, 100, 0.3);
  border-radius: 4px;

  .label {
    font-size: 10px;
    color: #668899;
  }

  .value {
    font-size: 16px;
    font-weight: bold;
    color: #00ff88;

    &.temp-high { color: #ff6b6b; }
    &.temp-low { color: #4ecdc4; }
  }
}

.alarm-list {
  max-height: 150px;
  overflow-y: auto;
}

.alarm-item {
  display: flex;
  gap: 8px;
  padding: 6px 8px;
  margin-bottom: 4px;
  background: rgba(0, 50, 100, 0.3);
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    background: rgba(0, 80, 130, 0.5);
  }

  &.critical {
    border-left: 3px solid #ff3333;
  }
  &.warning {
    border-left: 3px solid #ffcc00;
  }
  &.info {
    border-left: 3px solid #00ccff;
  }

  .alarm-time {
    color: #668899;
    flex-shrink: 0;
  }
  .alarm-device {
    color: #88ccff;
    flex-shrink: 0;
  }
  .alarm-message {
    color: #aabbcc;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.no-alarm {
  text-align: center;
  color: #668899;
  padding: 20px;
  font-size: 12px;
}
</style>
```

**Step 2: 验证**

Run: `cd D:/mytest1/frontend && npm run build`
Expected: 构建成功

---

## Task 5: 改造 RightPanel 为可拖拽

**Files:**
- Modify: `frontend/src/components/bigscreen/panels/RightPanel.vue`

**Step 1: 重构 RightPanel 使用 DraggablePanel**

类似 LeftPanel，重写 RightPanel.vue：

```vue
<template>
  <DraggablePanel
    ref="panelRef"
    title="能耗统计"
    panelId="rightPanel"
    :initialX="initialX"
    :initialY="panelState.y"
    :initialCollapsed="panelState.collapsed"
    @positionChange="handlePositionChange"
    @collapseChange="handleCollapseChange"
  >
    <div class="right-panel-content">
      <!-- 实时功率 -->
      <div class="section power" @click="navigateTo('/energy/analysis')">
        <div class="section-title">
          <span>实时功率</span>
          <span class="nav-hint">点击查看详情 →</span>
        </div>
        <div class="power-display">
          <DigitalFlop :value="store.energy.totalPower" suffix="kW" />
        </div>
        <PowerDistribution :data="powerDistributionData" />
      </div>

      <!-- PUE趋势 -->
      <div class="section pue" @click="navigateTo('/energy/analysis')">
        <div class="section-title">
          <span>PUE趋势</span>
          <span class="nav-hint">→</span>
        </div>
        <PueTrend :data="pueTrendData" />
      </div>

      <!-- 今日用电 -->
      <div class="section daily" @click="navigateTo('/energy/statistics')">
        <div class="section-title">
          <span>今日用电</span>
          <span class="nav-hint">→</span>
        </div>
        <div class="daily-stats">
          <div class="stat-item">
            <span class="label">总用电量</span>
            <span class="value">{{ store.energy.dailyConsumption.toFixed(0) }} kWh</span>
          </div>
          <div class="stat-item">
            <span class="label">较昨日</span>
            <span class="value" :class="store.energy.dailyChange > 0 ? 'up' : 'down'">
              {{ store.energy.dailyChange > 0 ? '+' : '' }}{{ store.energy.dailyChange.toFixed(1) }}%
            </span>
          </div>
        </div>
      </div>

      <!-- 需量状态 -->
      <div class="section demand" @click="navigateTo('/energy/topology')">
        <div class="section-title">
          <span>需量状态</span>
          <span class="nav-hint">→</span>
        </div>
        <div class="demand-display">
          <div class="demand-current">
            <span class="label">当前需量</span>
            <span class="value">{{ store.energy.currentDemand.toFixed(0) }} kW</span>
          </div>
          <div class="demand-limit">
            <span class="label">申报容量</span>
            <span class="value">{{ store.energy.demandLimit.toFixed(0) }} kW</span>
          </div>
          <div class="demand-bar">
            <div
              class="demand-fill"
              :style="{ width: `${(store.energy.currentDemand / store.energy.demandLimit * 100).toFixed(0)}%` }"
              :class="{ warning: store.energy.currentDemand / store.energy.demandLimit > 0.8 }"
            ></div>
          </div>
        </div>
      </div>
    </div>
  </DraggablePanel>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useBigscreenStore } from '@/stores/bigscreen'
import { DraggablePanel } from '@/components/bigscreen/ui'
import { DigitalFlop } from '@/components/bigscreen/ui'
import { PowerDistribution, PueTrend } from '@/components/bigscreen/charts'

const store = useBigscreenStore()
const panelRef = ref()

const emit = defineEmits<{
  (e: 'navigate', path: string): void
}>()

// 从store获取面板状态，右侧面板需要从右边计算位置
const panelState = computed(() => store.panelStates.rightPanel || { x: -300, y: 60, collapsed: false })

// 计算实际X位置（从右边）
const initialX = computed(() => {
  if (panelState.value.x < 0) {
    return window.innerWidth + panelState.value.x
  }
  return panelState.value.x
})

// 功率分布数据
const powerDistributionData = computed(() => [
  { name: 'IT设备', value: store.energy.totalPower * 0.65 },
  { name: '制冷系统', value: store.energy.totalPower * 0.25 },
  { name: '照明配套', value: store.energy.totalPower * 0.1 }
])

// PUE趋势数据
const pueTrendData = computed(() => {
  const now = Date.now()
  return Array.from({ length: 24 }, (_, i) => ({
    time: new Date(now - (23 - i) * 3600000).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    value: 1.4 + Math.random() * 0.2
  }))
})

function handlePositionChange(data: { id: string; x: number; y: number }) {
  store.updatePanelPosition(data.id, data.x, data.y)
}

function handleCollapseChange(data: { id: string; collapsed: boolean }) {
  store.updatePanelCollapsed(data.id, data.collapsed)
}

function navigateTo(path: string) {
  emit('navigate', path)
}

onMounted(() => {
  store.loadPanelStates()
})
</script>

<style scoped lang="scss">
.right-panel-content {
  width: 280px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section {
  background: rgba(0, 50, 100, 0.3);
  border-radius: 6px;
  padding: 10px;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    background: rgba(0, 80, 130, 0.4);

    .nav-hint {
      opacity: 1;
      transform: translateX(3px);
    }
  }
}

.section-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #88ccff;
  font-size: 12px;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(0, 200, 255, 0.2);
}

.nav-hint {
  color: #00ccff;
  font-size: 10px;
  opacity: 0.5;
  transition: all 0.2s ease;
}

.power-display {
  text-align: center;
  margin-bottom: 10px;
}

.daily-stats {
  display: flex;
  justify-content: space-around;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;

  .label {
    font-size: 10px;
    color: #668899;
  }

  .value {
    font-size: 18px;
    font-weight: bold;
    color: #00ff88;

    &.up { color: #ff6b6b; }
    &.down { color: #4ecdc4; }
  }
}

.demand-display {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.demand-current, .demand-limit {
  display: flex;
  justify-content: space-between;
  font-size: 12px;

  .label { color: #668899; }
  .value { color: #00ccff; font-weight: bold; }
}

.demand-bar {
  height: 8px;
  background: rgba(0, 50, 100, 0.5);
  border-radius: 4px;
  overflow: hidden;
}

.demand-fill {
  height: 100%;
  background: linear-gradient(90deg, #00ff88, #00ccff);
  border-radius: 4px;
  transition: width 0.3s ease;

  &.warning {
    background: linear-gradient(90deg, #ffcc00, #ff6b6b);
  }
}
</style>
```

**Step 2: 验证**

Run: `cd D:/mytest1/frontend && npm run build`
Expected: 构建成功

---

## Task 6: 改造 FloorSelector 为可拖拽

**Files:**
- Modify: `frontend/src/components/bigscreen/FloorSelector.vue`

**Step 1: 重构 FloorSelector 使用 DraggablePanel**

```vue
<template>
  <DraggablePanel
    ref="panelRef"
    title="楼层选择"
    panelId="floorSelector"
    :initialX="panelState.x"
    :initialY="panelState.y"
    :initialCollapsed="panelState.collapsed"
    @positionChange="handlePositionChange"
    @collapseChange="handleCollapseChange"
  >
    <div class="floor-selector-content">
      <div class="floor-buttons">
        <button
          v-for="floor in floors"
          :key="floor.floor_code"
          :class="['floor-btn', { active: currentFloor === floor.floor_code }]"
          @click="selectFloor(floor.floor_code)"
        >
          {{ floor.floor_code }}
          <span class="floor-name">{{ floor.floor_name }}</span>
        </button>
      </div>

      <div class="view-toggle">
        <button
          :class="['view-btn', { active: viewMode === '2d' }]"
          @click="setViewMode('2d')"
        >
          2D 平面
        </button>
        <button
          :class="['view-btn', { active: viewMode === '3d' }]"
          @click="setViewMode('3d')"
        >
          3D 场景
        </button>
      </div>

      <div v-if="loading" class="loading-indicator">
        加载中...
      </div>
    </div>
  </DraggablePanel>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useBigscreenStore } from '@/stores/bigscreen'
import { DraggablePanel } from '@/components/bigscreen/ui'
import { getFloors, getFloorMap, type FloorInfo } from '@/api/modules/floorMap'

const store = useBigscreenStore()
const panelRef = ref()

const props = defineProps<{
  modelValue?: string
  mode?: '2d' | '3d'
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', floor: string): void
  (e: 'update:mode', mode: '2d' | '3d'): void
  (e: 'floorChange', data: { floor: string; mode: '2d' | '3d'; mapData: any }): void
}>()

const floors = ref<FloorInfo[]>([])
const currentFloor = ref(props.modelValue || 'F1')
const viewMode = ref<'2d' | '3d'>(props.mode || '3d')
const loading = ref(false)

// 从store获取面板状态
const panelState = computed(() => store.panelStates.floorSelector || { x: 20, y: 80, collapsed: false })

function handlePositionChange(data: { id: string; x: number; y: number }) {
  store.updatePanelPosition(data.id, data.x, data.y)
}

function handleCollapseChange(data: { id: string; collapsed: boolean }) {
  store.updatePanelCollapsed(data.id, data.collapsed)
}

onMounted(async () => {
  store.loadPanelStates()

  try {
    const res = await getFloors()
    const data = res.data || res
    floors.value = data.floors || []

    if (floors.value.length === 0) {
      floors.value = [
        { floor_code: 'B1', floor_name: '地下制冷机房', map_types: ['2d', '3d'] },
        { floor_code: 'F1', floor_name: '1楼机房区A', map_types: ['2d', '3d'] },
        { floor_code: 'F2', floor_name: '2楼机房区B', map_types: ['2d', '3d'] },
        { floor_code: 'F3', floor_name: '3楼办公监控', map_types: ['2d', '3d'] }
      ]
    }

    await loadFloorMap()
  } catch (err) {
    console.error('Failed to load floors:', err)
    floors.value = [
      { floor_code: 'B1', floor_name: '地下制冷机房', map_types: ['2d', '3d'] },
      { floor_code: 'F1', floor_name: '1楼机房区A', map_types: ['2d', '3d'] },
      { floor_code: 'F2', floor_name: '2楼机房区B', map_types: ['2d', '3d'] },
      { floor_code: 'F3', floor_name: '3楼办公监控', map_types: ['2d', '3d'] }
    ]
  }
})

async function selectFloor(floorCode: string) {
  currentFloor.value = floorCode
  emit('update:modelValue', floorCode)
  await loadFloorMap()
}

async function setViewMode(mode: '2d' | '3d') {
  viewMode.value = mode
  emit('update:mode', mode)
  await loadFloorMap()
}

async function loadFloorMap() {
  if (loading.value) return
  loading.value = true

  try {
    const res = await getFloorMap(currentFloor.value, viewMode.value)
    const data = res.data || res
    const mapData = data.map_data

    emit('floorChange', {
      floor: currentFloor.value,
      mode: viewMode.value,
      mapData
    })
  } catch (err) {
    console.error('Failed to load floor map:', err)
    emit('floorChange', {
      floor: currentFloor.value,
      mode: viewMode.value,
      mapData: null
    })
  } finally {
    loading.value = false
  }
}

watch(() => props.modelValue, (val) => {
  if (val && val !== currentFloor.value) {
    currentFloor.value = val
    loadFloorMap()
  }
})

watch(() => props.mode, (val) => {
  if (val && val !== viewMode.value) {
    viewMode.value = val
    loadFloorMap()
  }
})
</script>

<style scoped lang="scss">
.floor-selector-content {
  min-width: 130px;
  padding: 8px;
}

.floor-buttons {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}

.floor-btn {
  background: rgba(0, 100, 150, 0.3);
  border: 1px solid rgba(0, 200, 255, 0.2);
  border-radius: 4px;
  color: #88ccff;
  padding: 8px 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: left;
  font-size: 14px;
  font-weight: 500;

  .floor-name {
    display: block;
    font-size: 10px;
    font-weight: normal;
    color: #668899;
    margin-top: 2px;
  }

  &:hover {
    background: rgba(0, 150, 200, 0.4);
    border-color: rgba(0, 200, 255, 0.5);
    transform: translateX(2px);
  }

  &.active {
    background: rgba(0, 200, 255, 0.3);
    border-color: #00ccff;
    color: #ffffff;
    box-shadow: 0 0 10px rgba(0, 200, 255, 0.3);

    .floor-name {
      color: #aaddff;
    }
  }
}

.view-toggle {
  display: flex;
  gap: 4px;
  border-top: 1px solid rgba(0, 200, 255, 0.2);
  padding-top: 10px;
}

.view-btn {
  flex: 1;
  background: rgba(0, 100, 150, 0.3);
  border: 1px solid rgba(0, 200, 255, 0.2);
  border-radius: 4px;
  color: #88ccff;
  padding: 6px 8px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    background: rgba(0, 150, 200, 0.4);
  }

  &.active {
    background: rgba(0, 200, 255, 0.3);
    border-color: #00ccff;
    color: #ffffff;
    box-shadow: 0 0 8px rgba(0, 200, 255, 0.3);
  }
}

.loading-indicator {
  text-align: center;
  color: #668899;
  font-size: 11px;
  margin-top: 8px;
  padding: 4px;
  background: rgba(0, 100, 150, 0.2);
  border-radius: 4px;
}
</style>
```

**Step 2: 验证**

Run: `cd D:/mytest1/frontend && npm run build`
Expected: 构建成功

---

## Task 7: 添加面板管理器到底部栏

**Files:**
- Modify: `frontend/src/views/bigscreen/index.vue`

**Step 1: 添加面板可见性切换控件**

在底部栏添加面板管理按钮，允许用户显示/隐藏各面板：

在 template 的 bottom-bar 中添加：
```vue
<div class="panel-toggles">
  <span class="label">面板:</span>
  <el-checkbox
    :model-value="store.panelStates.leftPanel?.visible"
    @change="store.togglePanelVisible('leftPanel')"
  >
    环境
  </el-checkbox>
  <el-checkbox
    :model-value="store.panelStates.rightPanel?.visible"
    @change="store.togglePanelVisible('rightPanel')"
  >
    能耗
  </el-checkbox>
  <el-checkbox
    :model-value="store.panelStates.floorSelector?.visible"
    @change="store.togglePanelVisible('floorSelector')"
  >
    楼层
  </el-checkbox>
  <el-button size="small" @click="store.resetPanelStates()">
    重置布局
  </el-button>
</div>
```

**Step 2: 为各面板添加 v-if 控制可见性**

```vue
<LeftPanel
  v-if="store.modeConfig.showAllPanels && store.panelStates.leftPanel?.visible"
  ...
/>

<RightPanel
  v-if="store.modeConfig.showAllPanels && store.panelStates.rightPanel?.visible"
  ...
/>

<FloorSelector
  v-if="store.panelStates.floorSelector?.visible"
  ...
/>
```

**Step 3: 添加样式**

```scss
.panel-toggles {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: 20px;
  padding-left: 20px;
  border-left: 1px solid rgba(255, 255, 255, 0.2);

  :deep(.el-checkbox) {
    color: #ccc;

    .el-checkbox__label {
      color: #ccc;
      font-size: 13px;
    }
  }
}
```

**Step 4: 验证**

Run: `cd D:/mytest1/frontend && npm run build`
Expected: 构建成功

---

## Task 8: 更新大屏主视图集成

**Files:**
- Modify: `frontend/src/views/bigscreen/index.vue`

**Step 1: 更新 imports**

确保导入更新后的组件和store方法。

**Step 2: 在 onMounted 中加载面板状态**

```typescript
onMounted(() => {
  // 加载面板状态
  store.loadPanelStates()

  // ... 其他初始化代码
})
```

**Step 3: 验证完整功能**

Run: `cd D:/mytest1/frontend && npm run build`
Expected: 构建成功

---

## Task 9: 更新文档

**Files:**
- Update: `findings.md`
- Update: `progress.md`

**Step 1: 更新 findings.md**

添加本次修改的详细记录，包括：
- 导航行为统一（新标签页打开）
- DraggablePanel 组件设计
- 面板状态持久化方案
- 各面板改造记录

**Step 2: 更新 progress.md**

添加会话进度记录，包括：
- 任务完成清单
- 新增/修改文件列表
- 版本更新说明

**Step 3: 最终验证**

Run: `cd D:/mytest1/frontend && npm run build`
Expected: 构建成功，无错误

---

## 验证清单

- [x] 所有可点击组件在新标签页打开对应页面
- [x] LeftPanel 可拖拽到任意位置
- [x] RightPanel 可拖拽到任意位置
- [x] FloorSelector 可拖拽到任意位置
- [x] 所有面板可折叠/展开
- [x] 面板状态持久化到 localStorage
- [x] 底部栏可控制面板显示/隐藏
- [x] 重置布局功能正常
- [x] 前端构建通过
- [x] 文档已更新

---

## 回滚方案

如果出现问题：
1. 恢复 LeftPanel.vue、RightPanel.vue、FloorSelector.vue 原始版本
2. 删除 DraggablePanel.vue 组件
3. 恢复 bigscreen store 原始状态定义
4. 清除 localStorage 中的 bigscreen-panel-states
