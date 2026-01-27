# 数字孪生大屏视觉升级实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 全面升级数字孪生大屏的视觉效果、数据可视化、交互体验和多风格支持

**Architecture:** 基于现有Vue3+Three.js架构，增加GSAP动画库、ECharts图表库、DataV科技感组件库，实现入场动画、数据图表、3D特效和多主题切换

**Tech Stack:** Vue 3, Three.js, GSAP, ECharts 5, @kjgl77/datav-vue3, v-scale-screen, countup.js

**Design Document:** docs/plans/2026-01-20-bigscreen-visual-upgrade-design.md

---

## Phase 0: 基础设施准备

### Task 0.1: 安装新依赖包

**Files:**
- Modify: `frontend/package.json`

**Step 1: 安装核心依赖**

```bash
cd frontend
npm install @kjgl77/datav-vue3 echarts vue-echarts gsap v-scale-screen countup.js
npm install -D @types/countup.js
```

**Step 2: 验证安装**

Run: `npm list @kjgl77/datav-vue3 echarts gsap`
Expected: 显示已安装的版本号

**Step 3: Commit**

```bash
git add package.json package-lock.json
git commit -m "feat(bigscreen): add visualization dependencies (DataV, ECharts, GSAP)"
```

---

### Task 0.2: 配置DataV全局组件

**Files:**
- Modify: `frontend/src/main.ts`

**Step 1: 注册DataV组件库**

在 main.ts 中添加:

```typescript
import DataVVue3 from '@kjgl77/datav-vue3'

// 在 app.use(router) 之后添加
app.use(DataVVue3)
```

**Step 2: 验证配置**

Run: `npm run build`
Expected: 构建成功无错误

**Step 3: Commit**

```bash
git add frontend/src/main.ts
git commit -m "feat(bigscreen): register DataV Vue3 components globally"
```

---

### Task 0.3: 添加屏幕自适应容器

**Files:**
- Modify: `frontend/src/views/bigscreen/index.vue`

**Step 1: 导入v-scale-screen**

```typescript
import VScaleScreen from 'v-scale-screen'
```

**Step 2: 包裹大屏内容**

将整个 bigscreen-container 包裹在 VScaleScreen 中:

```vue
<template>
  <VScaleScreen :width="1920" :height="1080" :fullScreen="true">
    <div class="bigscreen-container">
      <!-- 现有内容 -->
    </div>
  </VScaleScreen>
</template>
```

**Step 3: 验证适配**

Run: `npm run dev`
Expected: 访问大屏页面，调整浏览器窗口大小，内容应等比缩放

**Step 4: Commit**

```bash
git add frontend/src/views/bigscreen/index.vue
git commit -m "feat(bigscreen): add responsive scale screen adapter"
```

---

## Phase 1: 入场动画系统

### Task 1.1: 创建入场动画composable

**Files:**
- Create: `frontend/src/composables/bigscreen/useEntranceAnimation.ts`

**Step 1: 编写入场动画逻辑**

```typescript
// frontend/src/composables/bigscreen/useEntranceAnimation.ts
import { ref } from 'vue'
import gsap from 'gsap'

export interface EntranceAnimationOptions {
  duration?: number
  staggerDelay?: number
  onComplete?: () => void
}

export function useEntranceAnimation(options: EntranceAnimationOptions = {}) {
  const { duration = 1.5, staggerDelay = 0.1, onComplete } = options

  const isAnimating = ref(false)
  const isComplete = ref(false)
  let timeline: gsap.core.Timeline | null = null

  function playEntrance() {
    if (isAnimating.value) return

    isAnimating.value = true
    timeline = gsap.timeline({
      onComplete: () => {
        isAnimating.value = false
        isComplete.value = true
        onComplete?.()
      }
    })

    // 背景淡入
    timeline.from('.bigscreen-container', {
      opacity: 0,
      duration: 0.5,
      ease: 'power2.out'
    })

    // 3D场景
    timeline.from('.three-scene-container', {
      opacity: 0,
      scale: 0.9,
      duration: 0.8,
      ease: 'power2.out'
    }, 0.2)

    // 顶部栏从上滑入
    timeline.from('.top-bar', {
      y: -80,
      opacity: 0,
      duration: 0.5,
      ease: 'power3.out'
    }, 0.4)

    // 左侧面板从左滑入
    timeline.from('.left-panel', {
      x: -300,
      opacity: 0,
      duration: 0.5,
      ease: 'power3.out'
    }, 0.6)

    // 右侧面板从右滑入
    timeline.from('.right-panel', {
      x: 300,
      opacity: 0,
      duration: 0.5,
      ease: 'power3.out'
    }, 0.6)

    // 底部栏从下滑入
    timeline.from('.bottom-bar', {
      y: 80,
      opacity: 0,
      duration: 0.4,
      ease: 'power3.out'
    }, 0.8)

    // KPI数字
    timeline.from('.kpi .value', {
      textContent: 0,
      duration: 1,
      ease: 'power1.out',
      snap: { textContent: 1 },
      stagger: staggerDelay
    }, 0.8)
  }

  function skipEntrance() {
    timeline?.progress(1)
  }

  function resetAnimation() {
    timeline?.kill()
    isAnimating.value = false
    isComplete.value = false
  }

  return {
    isAnimating,
    isComplete,
    playEntrance,
    skipEntrance,
    resetAnimation
  }
}
```

**Step 2: 验证文件创建**

Run: `cat frontend/src/composables/bigscreen/useEntranceAnimation.ts | head -20`
Expected: 显示文件开头内容

**Step 3: Commit**

```bash
git add frontend/src/composables/bigscreen/useEntranceAnimation.ts
git commit -m "feat(bigscreen): add entrance animation composable with GSAP"
```

---

### Task 1.2: 集成入场动画到大屏

**Files:**
- Modify: `frontend/src/views/bigscreen/index.vue`

**Step 1: 导入并使用入场动画**

在 script setup 中添加:

```typescript
import { useEntranceAnimation } from '@/composables/bigscreen/useEntranceAnimation'

const entranceAnimation = useEntranceAnimation({
  onComplete: () => {
    console.log('Entrance animation complete')
  }
})
```

**Step 2: 在场景就绪后播放动画**

修改 onSceneReady 函数，在末尾添加:

```typescript
async function onSceneReady() {
  // ... 现有代码 ...

  // 播放入场动画
  setTimeout(() => {
    entranceAnimation.playEntrance()
  }, 100)
}
```

**Step 3: 添加跳过动画按钮(可选)**

在加载指示器区域添加:

```vue
<div v-if="entranceAnimation.isAnimating.value" class="skip-animation" @click="entranceAnimation.skipEntrance">
  跳过动画
</div>
```

**Step 4: 验证动画**

Run: `npm run dev`
Expected: 打开大屏页面，应看到元素依次入场动画

**Step 5: Commit**

```bash
git add frontend/src/views/bigscreen/index.vue
git commit -m "feat(bigscreen): integrate entrance animation on scene ready"
```

---

### Task 1.3: 创建数字滚动组件

**Files:**
- Create: `frontend/src/components/bigscreen/ui/DigitalCounter.vue`

**Step 1: 编写数字滚动组件**

```vue
<!-- frontend/src/components/bigscreen/ui/DigitalCounter.vue -->
<template>
  <span class="digital-counter" :class="{ 'is-animating': isAnimating }">
    <span class="value">{{ displayValue }}</span>
    <span class="unit" v-if="unit">{{ unit }}</span>
  </span>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { CountUp } from 'countup.js'

const props = withDefaults(defineProps<{
  value: number
  decimals?: number
  duration?: number
  unit?: string
  prefix?: string
  suffix?: string
  autoPlay?: boolean
}>(), {
  decimals: 0,
  duration: 2,
  autoPlay: true
})

const displayValue = ref(props.autoPlay ? 0 : props.value)
const isAnimating = ref(false)
let countUpInstance: CountUp | null = null

function animateTo(endValue: number) {
  isAnimating.value = true

  if (countUpInstance) {
    countUpInstance.update(endValue)
  } else {
    // 简单实现，不依赖DOM
    const startValue = displayValue.value
    const startTime = performance.now()
    const duration = props.duration * 1000

    function animate(currentTime: number) {
      const elapsed = currentTime - startTime
      const progress = Math.min(elapsed / duration, 1)

      // easeOutQuart
      const easeProgress = 1 - Math.pow(1 - progress, 4)
      const currentValue = startValue + (endValue - startValue) * easeProgress

      displayValue.value = Number(currentValue.toFixed(props.decimals))

      if (progress < 1) {
        requestAnimationFrame(animate)
      } else {
        isAnimating.value = false
      }
    }

    requestAnimationFrame(animate)
  }
}

watch(() => props.value, (newVal) => {
  animateTo(newVal)
})

onMounted(() => {
  if (props.autoPlay && props.value !== 0) {
    setTimeout(() => animateTo(props.value), 100)
  }
})

defineExpose({ animateTo })
</script>

<style scoped lang="scss">
.digital-counter {
  display: inline-flex;
  align-items: baseline;
  font-family: 'Courier New', monospace;

  .value {
    font-weight: bold;
  }

  .unit {
    font-size: 0.7em;
    margin-left: 2px;
    opacity: 0.8;
  }
}
</style>
```

**Step 2: 验证组件**

Run: `npm run build`
Expected: 构建成功

**Step 3: Commit**

```bash
git add frontend/src/components/bigscreen/ui/DigitalCounter.vue
git commit -m "feat(bigscreen): add digital counter component with animation"
```

---

## Phase 2: 数据可视化图表

### Task 2.1: 创建ECharts基础封装组件

**Files:**
- Create: `frontend/src/components/bigscreen/charts/BaseChart.vue`

**Step 1: 编写BaseChart组件**

```vue
<!-- frontend/src/components/bigscreen/charts/BaseChart.vue -->
<template>
  <div ref="chartRef" class="base-chart" :style="{ width, height }"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import type { EChartsOption, ECharts } from 'echarts'

const props = withDefaults(defineProps<{
  option: EChartsOption
  width?: string
  height?: string
  autoResize?: boolean
  theme?: string | object
}>(), {
  width: '100%',
  height: '100%',
  autoResize: true,
  theme: 'dark'
})

const emit = defineEmits<{
  (e: 'chartReady', chart: ECharts): void
  (e: 'click', params: any): void
}>()

const chartRef = ref<HTMLElement | null>(null)
let chartInstance: ECharts | null = null
let resizeObserver: ResizeObserver | null = null

function initChart() {
  if (!chartRef.value) return

  chartInstance = echarts.init(chartRef.value, props.theme)
  chartInstance.setOption(props.option)

  // 点击事件
  chartInstance.on('click', (params) => {
    emit('click', params)
  })

  emit('chartReady', chartInstance)
}

function updateChart() {
  if (chartInstance) {
    chartInstance.setOption(props.option, { notMerge: false })
  }
}

function resizeChart() {
  chartInstance?.resize()
}

// 监听option变化
watch(() => props.option, () => {
  nextTick(updateChart)
}, { deep: true })

onMounted(() => {
  initChart()

  if (props.autoResize && chartRef.value) {
    resizeObserver = new ResizeObserver(() => {
      resizeChart()
    })
    resizeObserver.observe(chartRef.value)
  }
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  chartInstance?.dispose()
  chartInstance = null
})

defineExpose({
  getChart: () => chartInstance,
  resize: resizeChart,
  setOption: (opt: EChartsOption) => chartInstance?.setOption(opt)
})
</script>

<style scoped>
.base-chart {
  min-height: 100px;
}
</style>
```

**Step 2: 验证构建**

Run: `npm run build`
Expected: 构建成功

**Step 3: Commit**

```bash
git add frontend/src/components/bigscreen/charts/BaseChart.vue
git commit -m "feat(bigscreen): add ECharts base chart wrapper component"
```

---

### Task 2.2: 创建温度趋势图表组件

**Files:**
- Create: `frontend/src/components/bigscreen/charts/TemperatureTrend.vue`

**Step 1: 编写温度趋势图表**

```vue
<!-- frontend/src/components/bigscreen/charts/TemperatureTrend.vue -->
<template>
  <BaseChart :option="chartOption" :height="height" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import BaseChart from './BaseChart.vue'
import type { EChartsOption } from 'echarts'

const props = withDefaults(defineProps<{
  data: { time: string; value: number }[]
  height?: string
  title?: string
  unit?: string
  thresholds?: { warning: number; danger: number }
}>(), {
  height: '160px',
  title: '温度趋势',
  unit: '°C',
  thresholds: () => ({ warning: 28, danger: 32 })
})

const chartOption = computed<EChartsOption>(() => ({
  title: {
    text: props.title,
    textStyle: {
      color: '#8899aa',
      fontSize: 12,
      fontWeight: 'normal'
    },
    left: 0,
    top: 0
  },
  tooltip: {
    trigger: 'axis',
    backgroundColor: 'rgba(10, 20, 40, 0.9)',
    borderColor: 'rgba(0, 136, 255, 0.5)',
    textStyle: { color: '#fff' },
    formatter: (params: any) => {
      const p = params[0]
      return `${p.axisValue}<br/>温度: ${p.value}${props.unit}`
    }
  },
  grid: {
    left: 40,
    right: 10,
    top: 35,
    bottom: 20
  },
  xAxis: {
    type: 'category',
    data: props.data.map(d => d.time),
    axisLine: { lineStyle: { color: '#334455' } },
    axisLabel: {
      color: '#667788',
      fontSize: 10,
      interval: 'auto'
    },
    splitLine: { show: false }
  },
  yAxis: {
    type: 'value',
    axisLine: { show: false },
    axisLabel: {
      color: '#667788',
      fontSize: 10,
      formatter: `{value}${props.unit}`
    },
    splitLine: {
      lineStyle: { color: 'rgba(255,255,255,0.05)' }
    }
  },
  series: [{
    type: 'line',
    data: props.data.map(d => d.value),
    smooth: true,
    symbol: 'none',
    lineStyle: {
      width: 2,
      color: {
        type: 'linear',
        x: 0, y: 0, x2: 1, y2: 0,
        colorStops: [
          { offset: 0, color: '#00ccff' },
          { offset: 1, color: '#0088ff' }
        ]
      }
    },
    areaStyle: {
      color: {
        type: 'linear',
        x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: 'rgba(0, 136, 255, 0.3)' },
          { offset: 1, color: 'rgba(0, 136, 255, 0)' }
        ]
      }
    },
    markLine: {
      silent: true,
      symbol: 'none',
      data: [
        {
          yAxis: props.thresholds.warning,
          lineStyle: { color: '#ffcc00', type: 'dashed', width: 1 },
          label: { show: false }
        },
        {
          yAxis: props.thresholds.danger,
          lineStyle: { color: '#ff3300', type: 'dashed', width: 1 },
          label: { show: false }
        }
      ]
    }
  }]
}))
</script>
```

**Step 2: 验证构建**

Run: `npm run build`
Expected: 构建成功

**Step 3: Commit**

```bash
git add frontend/src/components/bigscreen/charts/TemperatureTrend.vue
git commit -m "feat(bigscreen): add temperature trend chart component"
```

---

### Task 2.3: 创建功率分布饼图组件

**Files:**
- Create: `frontend/src/components/bigscreen/charts/PowerDistribution.vue`

**Step 1: 编写功率分布图表**

```vue
<!-- frontend/src/components/bigscreen/charts/PowerDistribution.vue -->
<template>
  <BaseChart :option="chartOption" :height="height" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import BaseChart from './BaseChart.vue'
import type { EChartsOption } from 'echarts'

const props = withDefaults(defineProps<{
  data: { name: string; value: number; color?: string }[]
  height?: string
  title?: string
}>(), {
  height: '180px',
  title: '功率分布'
})

const defaultColors = ['#0096ff', '#00ff88', '#ffcc00', '#ff6600', '#cc66ff']

const chartOption = computed<EChartsOption>(() => ({
  title: {
    text: props.title,
    textStyle: {
      color: '#8899aa',
      fontSize: 12,
      fontWeight: 'normal'
    },
    left: 0,
    top: 0
  },
  tooltip: {
    trigger: 'item',
    backgroundColor: 'rgba(10, 20, 40, 0.9)',
    borderColor: 'rgba(0, 136, 255, 0.5)',
    textStyle: { color: '#fff' },
    formatter: '{b}: {c} kW ({d}%)'
  },
  legend: {
    orient: 'vertical',
    right: 10,
    top: 'center',
    textStyle: { color: '#8899aa', fontSize: 11 },
    itemWidth: 10,
    itemHeight: 10
  },
  series: [{
    type: 'pie',
    radius: ['45%', '70%'],
    center: ['35%', '55%'],
    avoidLabelOverlap: false,
    itemStyle: {
      borderRadius: 4,
      borderColor: '#0a0a1a',
      borderWidth: 2
    },
    label: {
      show: false
    },
    emphasis: {
      label: {
        show: true,
        fontSize: 14,
        fontWeight: 'bold',
        color: '#fff'
      },
      itemStyle: {
        shadowBlur: 20,
        shadowColor: 'rgba(0, 136, 255, 0.5)'
      }
    },
    data: props.data.map((item, index) => ({
      name: item.name,
      value: item.value,
      itemStyle: {
        color: item.color || defaultColors[index % defaultColors.length]
      }
    }))
  }]
}))
</script>
```

**Step 2: Commit**

```bash
git add frontend/src/components/bigscreen/charts/PowerDistribution.vue
git commit -m "feat(bigscreen): add power distribution pie chart component"
```

---

### Task 2.4: 创建PUE趋势面积图组件

**Files:**
- Create: `frontend/src/components/bigscreen/charts/PueTrend.vue`

**Step 1: 编写PUE趋势图表**

```vue
<!-- frontend/src/components/bigscreen/charts/PueTrend.vue -->
<template>
  <BaseChart :option="chartOption" :height="height" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import BaseChart from './BaseChart.vue'
import type { EChartsOption } from 'echarts'

const props = withDefaults(defineProps<{
  data: { date: string; value: number }[]
  height?: string
  title?: string
}>(), {
  height: '140px',
  title: 'PUE趋势'
})

const chartOption = computed<EChartsOption>(() => ({
  title: {
    text: props.title,
    textStyle: {
      color: '#8899aa',
      fontSize: 12,
      fontWeight: 'normal'
    },
    left: 0,
    top: 0
  },
  tooltip: {
    trigger: 'axis',
    backgroundColor: 'rgba(10, 20, 40, 0.9)',
    borderColor: 'rgba(0, 136, 255, 0.5)',
    textStyle: { color: '#fff' }
  },
  grid: {
    left: 45,
    right: 10,
    top: 35,
    bottom: 25
  },
  xAxis: {
    type: 'category',
    data: props.data.map(d => d.date),
    axisLine: { lineStyle: { color: '#334455' } },
    axisLabel: { color: '#667788', fontSize: 10 },
    splitLine: { show: false }
  },
  yAxis: {
    type: 'value',
    min: 1.0,
    max: 2.0,
    axisLine: { show: false },
    axisLabel: { color: '#667788', fontSize: 10 },
    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }
  },
  series: [{
    type: 'line',
    data: props.data.map(d => d.value),
    smooth: true,
    symbol: 'circle',
    symbolSize: 6,
    lineStyle: { width: 2, color: '#00ff88' },
    itemStyle: { color: '#00ff88' },
    areaStyle: {
      color: {
        type: 'linear',
        x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: 'rgba(0, 255, 136, 0.25)' },
          { offset: 1, color: 'rgba(0, 255, 136, 0)' }
        ]
      }
    },
    markLine: {
      silent: true,
      symbol: 'none',
      data: [{
        yAxis: 1.4,
        lineStyle: { color: '#00ff88', type: 'dashed', width: 1 },
        label: { show: true, formatter: '优秀', color: '#00ff88', fontSize: 10 }
      }]
    }
  }]
}))
</script>
```

**Step 2: Commit**

```bash
git add frontend/src/components/bigscreen/charts/PueTrend.vue
git commit -m "feat(bigscreen): add PUE trend area chart component"
```

---

### Task 2.5: 创建图表组件索引文件

**Files:**
- Create: `frontend/src/components/bigscreen/charts/index.ts`

**Step 1: 创建索引文件**

```typescript
// frontend/src/components/bigscreen/charts/index.ts
export { default as BaseChart } from './BaseChart.vue'
export { default as TemperatureTrend } from './TemperatureTrend.vue'
export { default as PowerDistribution } from './PowerDistribution.vue'
export { default as PueTrend } from './PueTrend.vue'
```

**Step 2: Commit**

```bash
git add frontend/src/components/bigscreen/charts/index.ts
git commit -m "feat(bigscreen): add charts component index"
```

---

### Task 2.6: 重构左侧面板集成图表

**Files:**
- Modify: `frontend/src/components/bigscreen/panels/LeftPanel.vue`

**Step 1: 导入图表组件和DataV边框**

```typescript
import { TemperatureTrend } from '@/components/bigscreen/charts'
import { DvBorderBox8, DvDecoration3 } from '@kjgl77/datav-vue3'
```

**Step 2: 添加模拟温度数据**

```typescript
// 模拟24小时温度数据
const temperatureHistory = computed(() => {
  const data = []
  const now = new Date()
  for (let i = 23; i >= 0; i--) {
    const time = new Date(now.getTime() - i * 3600000)
    data.push({
      time: `${time.getHours().toString().padStart(2, '0')}:00`,
      value: 22 + Math.random() * 6 + (i > 12 ? 2 : 0)
    })
  }
  return data
})
```

**Step 3: 更新模板使用DataV边框和图表**

替换 panel 结构:

```vue
<template>
  <dv-border-box-8 class="left-panel" :class="{ collapsed: isCollapsed }" :dur="3">
    <div class="panel-header" @click="toggleCollapse">
      <dv-decoration-3 style="width:100px;height:15px;" />
      <span class="panel-title">环境监测</span>
      <el-icon class="collapse-icon">
        <ArrowLeft v-if="!isCollapsed" />
        <ArrowRight v-else />
      </el-icon>
    </div>

    <div class="panel-content" v-show="!isCollapsed">
      <!-- 温度趋势图表 -->
      <div class="data-section">
        <TemperatureTrend
          :data="temperatureHistory"
          title="24小时温度"
          height="140px"
        />
      </div>

      <!-- 温度概览 -->
      <div class="data-section">
        <h4>温度概览</h4>
        <!-- 现有内容保持不变 -->
      </div>

      <!-- 其余内容保持不变 -->
    </div>
  </dv-border-box-8>
</template>
```

**Step 4: 验证渲染**

Run: `npm run dev`
Expected: 左侧面板显示DataV边框和温度趋势图表

**Step 5: Commit**

```bash
git add frontend/src/components/bigscreen/panels/LeftPanel.vue
git commit -m "feat(bigscreen): integrate charts and DataV border in LeftPanel"
```

---

### Task 2.7: 重构右侧面板集成图表

**Files:**
- Modify: `frontend/src/components/bigscreen/panels/RightPanel.vue`

**Step 1: 导入图表组件**

```typescript
import { PowerDistribution, PueTrend } from '@/components/bigscreen/charts'
import { DvBorderBox8, DvDecoration3, DvWaterLevelPond } from '@kjgl77/datav-vue3'
```

**Step 2: 准备图表数据**

```typescript
// 功率分布数据
const powerDistributionData = computed(() => [
  { name: 'IT负载', value: store.energy.itPower, color: '#0096ff' },
  { name: '制冷系统', value: store.energy.coolingPower, color: '#00ff88' },
  { name: '照明/其他', value: Math.max(store.energy.totalPower - store.energy.itPower - store.energy.coolingPower, 0), color: '#ffcc00' }
])

// PUE趋势数据
const pueHistoryData = computed(() => {
  const data = []
  const now = new Date()
  for (let i = 6; i >= 0; i--) {
    const date = new Date(now.getTime() - i * 86400000)
    data.push({
      date: `${date.getMonth() + 1}/${date.getDate()}`,
      value: 1.4 + Math.random() * 0.15
    })
  }
  return data
})

// 用电量水球图配置
const waterLevelConfig = computed(() => ({
  data: [store.energy.todayEnergy / 2000], // 假设每日限额2000kWh
  shape: 'roundRect',
  waveNum: 2,
  waveHeight: 15,
  formatter: '{value}%'
}))
```

**Step 3: 更新模板**

```vue
<template>
  <dv-border-box-8 class="right-panel" :class="{ collapsed: isCollapsed }" :dur="3">
    <div class="panel-header" @click="toggleCollapse">
      <el-icon class="collapse-icon">
        <ArrowLeft v-if="isCollapsed" />
        <ArrowRight v-else />
      </el-icon>
      <span class="panel-title">能耗统计</span>
      <dv-decoration-3 style="width:100px;height:15px;" />
    </div>

    <div class="panel-content" v-show="!isCollapsed">
      <!-- 功率分布图表 -->
      <div class="data-section">
        <PowerDistribution
          :data="powerDistributionData"
          title="功率分布"
          height="160px"
        />
      </div>

      <!-- PUE 趋势 -->
      <div class="data-section">
        <PueTrend
          :data="pueHistoryData"
          title="PUE趋势(7天)"
          height="130px"
        />
      </div>

      <!-- 今日用电 - 使用水球图 -->
      <div class="data-section">
        <h4>今日用电</h4>
        <div class="water-level-container">
          <dv-water-level-pond :config="waterLevelConfig" style="width:100%;height:100px" />
        </div>
        <div class="energy-cost">
          <span class="cost-label">电费约</span>
          <span class="cost-value">¥{{ store.energy.todayCost.toFixed(0) }}</span>
        </div>
      </div>

      <!-- 需量状态保持不变 -->
    </div>
  </dv-border-box-8>
</template>
```

**Step 4: 验证渲染**

Run: `npm run dev`
Expected: 右侧面板显示功率饼图、PUE趋势图和水球图

**Step 5: Commit**

```bash
git add frontend/src/components/bigscreen/panels/RightPanel.vue
git commit -m "feat(bigscreen): integrate charts and DataV components in RightPanel"
```

---

## Phase 3: 3D特效增强

### Task 3.1: 添加OutlinePass选中高亮效果

**Files:**
- Create: `frontend/src/utils/three/outlineEffect.ts`
- Modify: `frontend/src/composables/bigscreen/useThreeScene.ts`

**Step 1: 创建OutlinePass工具函数**

```typescript
// frontend/src/utils/three/outlineEffect.ts
import * as THREE from 'three'
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js'
import { OutlinePass } from 'three/examples/jsm/postprocessing/OutlinePass.js'

export interface OutlineConfig {
  edgeStrength?: number
  edgeGlow?: number
  edgeThickness?: number
  pulsePeriod?: number
  visibleEdgeColor?: string
  hiddenEdgeColor?: string
}

const defaultConfig: OutlineConfig = {
  edgeStrength: 3.0,
  edgeGlow: 1.0,
  edgeThickness: 2.0,
  pulsePeriod: 2,
  visibleEdgeColor: '#00ccff',
  hiddenEdgeColor: '#004466'
}

export function createOutlinePass(
  scene: THREE.Scene,
  camera: THREE.Camera,
  resolution: THREE.Vector2,
  config: OutlineConfig = {}
): OutlinePass {
  const mergedConfig = { ...defaultConfig, ...config }

  const outlinePass = new OutlinePass(resolution, scene, camera)
  outlinePass.edgeStrength = mergedConfig.edgeStrength!
  outlinePass.edgeGlow = mergedConfig.edgeGlow!
  outlinePass.edgeThickness = mergedConfig.edgeThickness!
  outlinePass.pulsePeriod = mergedConfig.pulsePeriod!
  outlinePass.visibleEdgeColor.set(mergedConfig.visibleEdgeColor!)
  outlinePass.hiddenEdgeColor.set(mergedConfig.hiddenEdgeColor!)

  return outlinePass
}

export function setOutlineObjects(outlinePass: OutlinePass, objects: THREE.Object3D[]) {
  outlinePass.selectedObjects = objects
}

export function clearOutlineObjects(outlinePass: OutlinePass) {
  outlinePass.selectedObjects = []
}
```

**Step 2: 在useThreeScene中集成OutlinePass**

在 `useThreeScene.ts` 的 setupPostProcessing 函数中添加:

```typescript
import { createOutlinePass } from '@/utils/three/outlineEffect'

// 在函数内添加
const outlinePass = createOutlinePass(targetScene, targetCamera, new THREE.Vector2(width, height))
newComposer.addPass(outlinePass)

// 导出 outlinePass 引用
```

**Step 3: Commit**

```bash
git add frontend/src/utils/three/outlineEffect.ts frontend/src/composables/bigscreen/useThreeScene.ts
git commit -m "feat(bigscreen): add OutlinePass for cabinet selection highlight"
```

---

### Task 3.2: 创建电力流向动画效果

**Files:**
- Create: `frontend/src/utils/three/powerFlowEffect.ts`
- Create: `frontend/src/components/bigscreen/effects/PowerFlowLines.vue`

**Step 1: 创建电力流向工具函数**

```typescript
// frontend/src/utils/three/powerFlowEffect.ts
import * as THREE from 'three'

export interface PowerFlowConfig {
  color?: number
  opacity?: number
  tubeRadius?: number
  flowSpeed?: number
  segments?: number
}

const defaultConfig: PowerFlowConfig = {
  color: 0x00ccff,
  opacity: 0.8,
  tubeRadius: 0.02,
  flowSpeed: 0.02,
  segments: 64
}

export class PowerFlowLine {
  private tube: THREE.Mesh
  private texture: THREE.Texture
  private config: PowerFlowConfig

  constructor(
    path: THREE.Vector3[],
    scene: THREE.Scene,
    config: PowerFlowConfig = {}
  ) {
    this.config = { ...defaultConfig, ...config }

    // 创建曲线
    const curve = new THREE.CatmullRomCurve3(path)

    // 创建管道几何体
    const tubeGeometry = new THREE.TubeGeometry(
      curve,
      this.config.segments!,
      this.config.tubeRadius!,
      8,
      false
    )

    // 创建流动纹理
    this.texture = this.createFlowTexture()
    this.texture.wrapS = THREE.RepeatWrapping
    this.texture.repeat.x = path.length * 2

    // 创建材质
    const material = new THREE.MeshBasicMaterial({
      map: this.texture,
      transparent: true,
      opacity: this.config.opacity!,
      side: THREE.DoubleSide
    })

    this.tube = new THREE.Mesh(tubeGeometry, material)
    scene.add(this.tube)
  }

  private createFlowTexture(): THREE.Texture {
    const canvas = document.createElement('canvas')
    canvas.width = 256
    canvas.height = 1
    const ctx = canvas.getContext('2d')!

    // 创建渐变
    const gradient = ctx.createLinearGradient(0, 0, 256, 0)
    gradient.addColorStop(0, 'rgba(0, 204, 255, 0)')
    gradient.addColorStop(0.3, 'rgba(0, 204, 255, 1)')
    gradient.addColorStop(0.7, 'rgba(0, 204, 255, 1)')
    gradient.addColorStop(1, 'rgba(0, 204, 255, 0)')

    ctx.fillStyle = gradient
    ctx.fillRect(0, 0, 256, 1)

    const texture = new THREE.CanvasTexture(canvas)
    return texture
  }

  update() {
    this.texture.offset.x -= this.config.flowSpeed!
  }

  setVisible(visible: boolean) {
    this.tube.visible = visible
  }

  dispose() {
    this.tube.geometry.dispose()
    ;(this.tube.material as THREE.Material).dispose()
    this.texture.dispose()
    this.tube.parent?.remove(this.tube)
  }
}
```

**Step 2: 创建PowerFlowLines组件**

```vue
<!-- frontend/src/components/bigscreen/effects/PowerFlowLines.vue -->
<template>
  <!-- 逻辑组件，不渲染DOM -->
  <div class="power-flow-lines" style="display: none;"></div>
</template>

<script setup lang="ts">
import { inject, watch, onMounted, onUnmounted, type ShallowRef } from 'vue'
import * as THREE from 'three'
import { PowerFlowLine } from '@/utils/three/powerFlowEffect'
import { useBigscreenStore } from '@/stores/bigscreen'

const store = useBigscreenStore()
const scene = inject<ShallowRef<THREE.Scene | null>>('three-scene')

const flowLines: PowerFlowLine[] = []
let animationId: number | null = null

// 创建电力流向线条
function createFlowLines() {
  if (!scene?.value || !store.layout) return

  // 示例：从UPS到各机柜的电力线
  // 实际应根据布局数据生成
  const upsPosition = new THREE.Vector3(-15, 1, 0)

  store.layout.modules.forEach(module => {
    module.cabinets.forEach(cabinet => {
      const cabinetPos = new THREE.Vector3(
        module.position.x + cabinet.position.x,
        1.5,
        module.position.z + cabinet.position.z
      )

      // 创建中间控制点
      const midPoint = new THREE.Vector3(
        (upsPosition.x + cabinetPos.x) / 2,
        2.5,
        (upsPosition.z + cabinetPos.z) / 2
      )

      const path = [upsPosition.clone(), midPoint, cabinetPos]
      const flowLine = new PowerFlowLine(path, scene.value!, {
        flowSpeed: 0.015 + Math.random() * 0.01
      })

      flowLines.push(flowLine)
    })
  })

  // 启动动画
  animate()
}

function animate() {
  flowLines.forEach(line => line.update())
  animationId = requestAnimationFrame(animate)
}

function clearFlowLines() {
  if (animationId) {
    cancelAnimationFrame(animationId)
    animationId = null
  }
  flowLines.forEach(line => line.dispose())
  flowLines.length = 0
}

// 监听图层开关
watch(() => store.layers.power, (visible) => {
  flowLines.forEach(line => line.setVisible(visible))
})

onMounted(() => {
  setTimeout(createFlowLines, 500)
})

onUnmounted(() => {
  clearFlowLines()
})
</script>
```

**Step 3: Commit**

```bash
git add frontend/src/utils/three/powerFlowEffect.ts frontend/src/components/bigscreen/effects/PowerFlowLines.vue
git commit -m "feat(bigscreen): add power flow animation effect"
```

---

### Task 3.3: 创建告警脉冲动画效果

**Files:**
- Create: `frontend/src/components/bigscreen/effects/AlarmPulse.vue`

**Step 1: 创建告警脉冲组件**

```vue
<!-- frontend/src/components/bigscreen/effects/AlarmPulse.vue -->
<template>
  <div class="alarm-pulse" style="display: none;"></div>
</template>

<script setup lang="ts">
import { inject, watch, onMounted, onUnmounted, type ShallowRef } from 'vue'
import * as THREE from 'three'
import { useBigscreenStore } from '@/stores/bigscreen'

const store = useBigscreenStore()
const scene = inject<ShallowRef<THREE.Scene | null>>('three-scene')

interface AlarmPulseEffect {
  sphere: THREE.Mesh
  rings: THREE.Mesh[]
  cleanup: () => void
}

const alarmEffects = new Map<string, AlarmPulseEffect>()
let animationId: number | null = null

function createAlarmEffect(deviceId: string, position: THREE.Vector3): AlarmPulseEffect {
  const group = new THREE.Group()

  // 发光球体
  const sphereGeometry = new THREE.SphereGeometry(0.15, 16, 16)
  const sphereMaterial = new THREE.MeshBasicMaterial({
    color: 0xff3300,
    transparent: true,
    opacity: 0.9
  })
  const sphere = new THREE.Mesh(sphereGeometry, sphereMaterial)
  sphere.position.copy(position)
  sphere.position.y += 2.5
  group.add(sphere)

  // 扩散波纹
  const rings: THREE.Mesh[] = []
  for (let i = 0; i < 3; i++) {
    const ringGeometry = new THREE.RingGeometry(0.1, 0.15, 32)
    const ringMaterial = new THREE.MeshBasicMaterial({
      color: 0xff3300,
      transparent: true,
      opacity: 0.5,
      side: THREE.DoubleSide
    })
    const ring = new THREE.Mesh(ringGeometry, ringMaterial)
    ring.position.copy(position)
    ring.position.y += 2.5
    ring.rotation.x = -Math.PI / 2
    ring.userData.phase = i * (Math.PI * 2 / 3)
    group.add(ring)
    rings.push(ring)
  }

  scene.value!.add(group)

  return {
    sphere,
    rings,
    cleanup: () => {
      group.traverse((obj) => {
        if (obj instanceof THREE.Mesh) {
          obj.geometry.dispose()
          ;(obj.material as THREE.Material).dispose()
        }
      })
      scene.value?.remove(group)
    }
  }
}

function animate() {
  const time = Date.now() * 0.003

  alarmEffects.forEach((effect) => {
    // 球体脉冲
    const pulseScale = 1 + 0.2 * Math.sin(time * 2)
    effect.sphere.scale.setScalar(pulseScale)
    ;(effect.sphere.material as THREE.MeshBasicMaterial).opacity = 0.6 + 0.3 * Math.sin(time * 2)

    // 波纹扩散
    effect.rings.forEach((ring, i) => {
      const phase = ring.userData.phase
      const progress = ((time + phase) % (Math.PI * 2)) / (Math.PI * 2)
      const scale = 1 + progress * 3
      ring.scale.setScalar(scale)
      ;(ring.material as THREE.MeshBasicMaterial).opacity = 0.5 * (1 - progress)
    })
  })

  animationId = requestAnimationFrame(animate)
}

function updateAlarmEffects() {
  if (!scene?.value) return

  // 清除已解除告警的效果
  alarmEffects.forEach((effect, deviceId) => {
    if (!store.activeAlarms.find(a => a.deviceId === deviceId)) {
      effect.cleanup()
      alarmEffects.delete(deviceId)
    }
  })

  // 为新告警创建效果
  store.activeAlarms.forEach(alarm => {
    if (!alarmEffects.has(alarm.deviceId)) {
      // 查找设备位置
      const cabinet = store.layout?.modules
        .flatMap(m => m.cabinets.map(c => ({ ...c, modulePos: m.position })))
        .find(c => c.id === alarm.deviceId)

      if (cabinet) {
        const position = new THREE.Vector3(
          cabinet.modulePos.x + cabinet.position.x,
          0,
          cabinet.modulePos.z + cabinet.position.z
        )
        const effect = createAlarmEffect(alarm.deviceId, position)
        alarmEffects.set(alarm.deviceId, effect)
      }
    }
  })
}

watch(() => store.activeAlarms, updateAlarmEffects, { deep: true })

onMounted(() => {
  setTimeout(() => {
    updateAlarmEffects()
    animate()
  }, 500)
})

onUnmounted(() => {
  if (animationId) {
    cancelAnimationFrame(animationId)
  }
  alarmEffects.forEach(effect => effect.cleanup())
  alarmEffects.clear()
})
</script>
```

**Step 2: Commit**

```bash
git add frontend/src/components/bigscreen/effects/AlarmPulse.vue
git commit -m "feat(bigscreen): add alarm pulse animation effect"
```

---

### Task 3.4: 创建特效组件索引并集成到主视图

**Files:**
- Create: `frontend/src/components/bigscreen/effects/index.ts`
- Modify: `frontend/src/views/bigscreen/index.vue`

**Step 1: 创建特效组件索引**

```typescript
// frontend/src/components/bigscreen/effects/index.ts
export { default as PowerFlowLines } from './PowerFlowLines.vue'
export { default as AlarmPulse } from './AlarmPulse.vue'
```

**Step 2: 在主视图中导入并使用特效**

在 index.vue 的 template 中添加:

```vue
<ThreeScene ref="threeSceneRef" @vue:mounted="onSceneReady">
  <template v-if="isSceneReady">
    <DataCenterModel />
    <HeatmapOverlay />
    <CabinetLabels />
    <AlarmBubbles />
    <!-- 新增特效 -->
    <PowerFlowLines v-if="store.layers.power" />
    <AlarmPulse />
  </template>
</ThreeScene>
```

**Step 3: 导入组件**

```typescript
import { PowerFlowLines, AlarmPulse } from '@/components/bigscreen/effects'
```

**Step 4: Commit**

```bash
git add frontend/src/components/bigscreen/effects/index.ts frontend/src/views/bigscreen/index.vue
git commit -m "feat(bigscreen): integrate 3D effects into main view"
```

---

## Phase 4: 交互体验升级

### Task 4.1: 创建键盘快捷键composable

**Files:**
- Create: `frontend/src/composables/bigscreen/useKeyboardShortcuts.ts`

**Step 1: 编写键盘快捷键逻辑**

```typescript
// frontend/src/composables/bigscreen/useKeyboardShortcuts.ts
import { onMounted, onUnmounted } from 'vue'
import { useBigscreenStore } from '@/stores/bigscreen'

export interface KeyboardShortcutsOptions {
  onCameraPreset?: (preset: string) => void
  onToggleTour?: () => void
  onToggleFullscreen?: () => void
  onDrillBack?: () => void
  onCycleLayer?: () => void
}

export function useKeyboardShortcuts(options: KeyboardShortcutsOptions) {
  const store = useBigscreenStore()

  const shortcuts: Record<string, () => void> = {
    'Digit1': () => options.onCameraPreset?.('overview'),
    'Digit2': () => options.onCameraPreset?.('topDown'),
    'Digit3': () => options.onCameraPreset?.('front'),
    'Digit4': () => options.onCameraPreset?.('side'),
    'Digit5': () => options.onCameraPreset?.('corner'),
    'Space': () => options.onToggleTour?.(),
    'Escape': () => {
      // 关闭设备详情面板或返回上级
      if (store.selectedDeviceId) {
        store.selectDevice(null)
      } else {
        options.onDrillBack?.()
      }
    },
    'KeyF': () => options.onToggleFullscreen?.(),
    'Tab': () => options.onCycleLayer?.(),
    'KeyH': () => store.toggleLayer('heatmap'),
    'KeyP': () => store.toggleLayer('power'),
    'KeyS': () => store.toggleLayer('status'),
    'KeyA': () => store.toggleLayer('airflow'),
  }

  function handleKeydown(event: KeyboardEvent) {
    // 忽略输入框中的按键
    if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) {
      return
    }

    const handler = shortcuts[event.code]
    if (handler) {
      event.preventDefault()
      handler()
    }
  }

  onMounted(() => {
    document.addEventListener('keydown', handleKeydown)
  })

  onUnmounted(() => {
    document.removeEventListener('keydown', handleKeydown)
  })

  return {
    shortcuts
  }
}
```

**Step 2: Commit**

```bash
git add frontend/src/composables/bigscreen/useKeyboardShortcuts.ts
git commit -m "feat(bigscreen): add keyboard shortcuts composable"
```

---

### Task 4.2: 创建右键上下文菜单组件

**Files:**
- Create: `frontend/src/components/bigscreen/ui/ContextMenu.vue`

**Step 1: 编写右键菜单组件**

```vue
<!-- frontend/src/components/bigscreen/ui/ContextMenu.vue -->
<template>
  <Teleport to="body">
    <Transition name="context-menu">
      <div
        v-if="visible"
        class="context-menu"
        :style="{ left: position.x + 'px', top: position.y + 'px' }"
        @contextmenu.prevent
      >
        <div
          v-for="(item, index) in items"
          :key="index"
          :class="['menu-item', { divider: item.divider, disabled: item.disabled }]"
          @click="handleClick(item)"
        >
          <template v-if="!item.divider">
            <span class="menu-icon" v-if="item.icon">
              <component :is="item.icon" />
            </span>
            <span class="menu-label">{{ item.label }}</span>
            <span class="menu-shortcut" v-if="item.shortcut">{{ item.shortcut }}</span>
          </template>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'

export interface ContextMenuItem {
  label?: string
  icon?: any
  action?: string
  shortcut?: string
  disabled?: boolean
  divider?: boolean
}

const props = defineProps<{
  visible: boolean
  position: { x: number; y: number }
  items: ContextMenuItem[]
}>()

const emit = defineEmits<{
  (e: 'select', action: string): void
  (e: 'close'): void
}>()

function handleClick(item: ContextMenuItem) {
  if (item.divider || item.disabled) return
  if (item.action) {
    emit('select', item.action)
  }
  emit('close')
}

function handleClickOutside(event: MouseEvent) {
  emit('close')
}

watch(() => props.visible, (visible) => {
  if (visible) {
    setTimeout(() => {
      document.addEventListener('click', handleClickOutside)
    }, 0)
  } else {
    document.removeEventListener('click', handleClickOutside)
  }
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped lang="scss">
.context-menu {
  position: fixed;
  z-index: 9999;
  min-width: 160px;
  background: rgba(10, 20, 40, 0.95);
  border: 1px solid rgba(0, 136, 255, 0.4);
  border-radius: 6px;
  padding: 6px 0;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(10px);
}

.menu-item {
  display: flex;
  align-items: center;
  padding: 8px 16px;
  cursor: pointer;
  color: #ccc;
  font-size: 13px;
  transition: background 0.2s;

  &:hover:not(.divider):not(.disabled) {
    background: rgba(0, 136, 255, 0.2);
    color: #fff;
  }

  &.divider {
    height: 1px;
    margin: 6px 0;
    padding: 0;
    background: rgba(255, 255, 255, 0.1);
    cursor: default;
  }

  &.disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .menu-icon {
    width: 20px;
    margin-right: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #00ccff;
  }

  .menu-label {
    flex: 1;
  }

  .menu-shortcut {
    margin-left: 20px;
    font-size: 11px;
    color: #667788;
  }
}

.context-menu-enter-active,
.context-menu-leave-active {
  transition: opacity 0.15s, transform 0.15s;
}

.context-menu-enter-from,
.context-menu-leave-to {
  opacity: 0;
  transform: scale(0.95);
}
</style>
```

**Step 2: Commit**

```bash
git add frontend/src/components/bigscreen/ui/ContextMenu.vue
git commit -m "feat(bigscreen): add context menu component"
```

---

### Task 4.3: 集成快捷键和右键菜单到主视图

**Files:**
- Modify: `frontend/src/views/bigscreen/index.vue`

**Step 1: 导入并使用快捷键**

```typescript
import { useKeyboardShortcuts } from '@/composables/bigscreen/useKeyboardShortcuts'
import ContextMenu from '@/components/bigscreen/ui/ContextMenu.vue'
import type { ContextMenuItem } from '@/components/bigscreen/ui/ContextMenu.vue'

// 在 setup 中
useKeyboardShortcuts({
  onCameraPreset: setCamera,
  onToggleTour: handleToggleTour,
  onToggleFullscreen: toggleFullscreen,
  onDrillBack: () => store.selectDevice(null)
})
```

**Step 2: 添加右键菜单状态和处理**

```typescript
// 右键菜单
const contextMenu = reactive({
  visible: false,
  position: { x: 0, y: 0 },
  targetDevice: null as string | null
})

const contextMenuItems: ContextMenuItem[] = [
  { label: '查看详情', icon: 'InfoFilled', action: 'viewDetail' },
  { label: '历史数据', icon: 'DataLine', action: 'viewHistory' },
  { label: '告警记录', icon: 'Bell', action: 'viewAlarms' },
  { divider: true },
  { label: '电力链路', icon: 'Connection', action: 'showPowerChain' },
  { label: '网络拓扑', icon: 'Share', action: 'showNetwork' },
  { divider: true },
  { label: '返回全景', icon: 'Back', action: 'drillBack', shortcut: 'Esc' },
]

function handleContextMenu(event: MouseEvent, deviceId: string) {
  event.preventDefault()
  contextMenu.visible = true
  contextMenu.position = { x: event.clientX, y: event.clientY }
  contextMenu.targetDevice = deviceId
}

function handleContextMenuSelect(action: string) {
  if (!contextMenu.targetDevice) return

  switch (action) {
    case 'viewDetail':
      store.selectDevice(contextMenu.targetDevice)
      break
    case 'viewHistory':
      handleViewHistory(contextMenu.targetDevice)
      break
    case 'drillBack':
      store.selectDevice(null)
      break
    // ... 其他动作
  }
}
```

**Step 3: 在模板中添加右键菜单**

```vue
<ContextMenu
  :visible="contextMenu.visible"
  :position="contextMenu.position"
  :items="contextMenuItems"
  @select="handleContextMenuSelect"
  @close="contextMenu.visible = false"
/>
```

**Step 4: Commit**

```bash
git add frontend/src/views/bigscreen/index.vue
git commit -m "feat(bigscreen): integrate keyboard shortcuts and context menu"
```

---

## Phase 5: 多主题支持

### Task 5.1: 创建主题配置类型和默认主题

**Files:**
- Create: `frontend/src/config/themes/types.ts`
- Create: `frontend/src/config/themes/tech-blue.ts`

**Step 1: 定义主题类型**

```typescript
// frontend/src/config/themes/types.ts
export interface BigscreenTheme {
  name: string
  displayName: string

  scene: {
    backgroundColor: number
    fogColor: number
    fogDensity: number
  }

  materials: {
    cabinetBody: {
      color: number
      metalness: number
      roughness: number
      envMapIntensity: number
    }
    cabinetFrame: {
      color: number
      metalness: number
      roughness: number
    }
    floor: {
      color: number
      metalness: number
      roughness: number
    }
  }

  lighting: {
    ambient: { color: number; intensity: number }
    directional: { color: number; intensity: number }
    hemisphere: { skyColor: number; groundColor: number; intensity: number }
  }

  ui: {
    primaryColor: string
    secondaryColor: string
    dangerColor: string
    warningColor: string
    successColor: string
    backgroundColor: string
    borderColor: string
    textColor: string
    textSecondaryColor: string
  }

  effects: {
    bloom: boolean
    bloomStrength: number
    outline: boolean
    particles: boolean
    flowLines: boolean
  }
}
```

**Step 2: 创建科技蓝主题**

```typescript
// frontend/src/config/themes/tech-blue.ts
import type { BigscreenTheme } from './types'

export const techBlueTheme: BigscreenTheme = {
  name: 'tech-blue',
  displayName: '科技蓝',

  scene: {
    backgroundColor: 0x0a0a1a,
    fogColor: 0x0a0a1a,
    fogDensity: 0.015
  },

  materials: {
    cabinetBody: {
      color: 0x2a2a3a,
      metalness: 0.8,
      roughness: 0.25,
      envMapIntensity: 1.0
    },
    cabinetFrame: {
      color: 0x1a1a2a,
      metalness: 0.9,
      roughness: 0.2
    },
    floor: {
      color: 0x1a1a2e,
      metalness: 0.4,
      roughness: 0.6
    }
  },

  lighting: {
    ambient: { color: 0xffffff, intensity: 0.4 },
    directional: { color: 0xffffff, intensity: 1.2 },
    hemisphere: { skyColor: 0x88ccff, groundColor: 0x444466, intensity: 0.5 }
  },

  ui: {
    primaryColor: '#00ccff',
    secondaryColor: '#0088ff',
    dangerColor: '#ff3300',
    warningColor: '#ffcc00',
    successColor: '#00ff88',
    backgroundColor: 'rgba(10, 15, 30, 0.9)',
    borderColor: 'rgba(0, 136, 255, 0.3)',
    textColor: '#ffffff',
    textSecondaryColor: '#8899aa'
  },

  effects: {
    bloom: true,
    bloomStrength: 0.2,
    outline: true,
    particles: true,
    flowLines: true
  }
}
```

**Step 3: Commit**

```bash
git add frontend/src/config/themes/types.ts frontend/src/config/themes/tech-blue.ts
git commit -m "feat(bigscreen): add theme type definitions and tech-blue theme"
```

---

### Task 5.2: 创建其他预设主题

**Files:**
- Create: `frontend/src/config/themes/wireframe.ts`
- Create: `frontend/src/config/themes/realistic.ts`
- Create: `frontend/src/config/themes/night.ts`
- Create: `frontend/src/config/themes/index.ts`

**Step 1: 科技线框主题**

```typescript
// frontend/src/config/themes/wireframe.ts
import type { BigscreenTheme } from './types'

export const wireframeTheme: BigscreenTheme = {
  name: 'wireframe',
  displayName: '科技线框',

  scene: {
    backgroundColor: 0x000000,
    fogColor: 0x000000,
    fogDensity: 0.01
  },

  materials: {
    cabinetBody: {
      color: 0x003366,
      metalness: 0.1,
      roughness: 0.9,
      envMapIntensity: 0.2
    },
    cabinetFrame: {
      color: 0x00ccff,
      metalness: 0.1,
      roughness: 0.9
    },
    floor: {
      color: 0x001122,
      metalness: 0.1,
      roughness: 0.9
    }
  },

  lighting: {
    ambient: { color: 0x0066ff, intensity: 0.3 },
    directional: { color: 0x00ccff, intensity: 0.5 },
    hemisphere: { skyColor: 0x0066ff, groundColor: 0x000033, intensity: 0.3 }
  },

  ui: {
    primaryColor: '#00ccff',
    secondaryColor: '#0066ff',
    dangerColor: '#ff0066',
    warningColor: '#ffcc00',
    successColor: '#00ff66',
    backgroundColor: 'rgba(0, 10, 30, 0.8)',
    borderColor: 'rgba(0, 204, 255, 0.5)',
    textColor: '#00ccff',
    textSecondaryColor: '#006699'
  },

  effects: {
    bloom: true,
    bloomStrength: 0.5,
    outline: true,
    particles: true,
    flowLines: true
  }
}
```

**Step 2: 写实风格主题**

```typescript
// frontend/src/config/themes/realistic.ts
import type { BigscreenTheme } from './types'

export const realisticTheme: BigscreenTheme = {
  name: 'realistic',
  displayName: '写实风格',

  scene: {
    backgroundColor: 0x1a1a1a,
    fogColor: 0x1a1a1a,
    fogDensity: 0.008
  },

  materials: {
    cabinetBody: {
      color: 0x2a2a2a,
      metalness: 0.6,
      roughness: 0.4,
      envMapIntensity: 1.5
    },
    cabinetFrame: {
      color: 0x1a1a1a,
      metalness: 0.8,
      roughness: 0.3
    },
    floor: {
      color: 0x333333,
      metalness: 0.2,
      roughness: 0.8
    }
  },

  lighting: {
    ambient: { color: 0xffffff, intensity: 0.5 },
    directional: { color: 0xfff5e6, intensity: 1.5 },
    hemisphere: { skyColor: 0xffffff, groundColor: 0x444444, intensity: 0.6 }
  },

  ui: {
    primaryColor: '#4a90d9',
    secondaryColor: '#357abd',
    dangerColor: '#d93025',
    warningColor: '#f9ab00',
    successColor: '#1e8e3e',
    backgroundColor: 'rgba(30, 30, 30, 0.95)',
    borderColor: 'rgba(100, 100, 100, 0.3)',
    textColor: '#ffffff',
    textSecondaryColor: '#999999'
  },

  effects: {
    bloom: false,
    bloomStrength: 0,
    outline: true,
    particles: false,
    flowLines: false
  }
}
```

**Step 3: 暗夜模式主题**

```typescript
// frontend/src/config/themes/night.ts
import type { BigscreenTheme } from './types'

export const nightTheme: BigscreenTheme = {
  name: 'night',
  displayName: '暗夜模式',

  scene: {
    backgroundColor: 0x000000,
    fogColor: 0x000000,
    fogDensity: 0.02
  },

  materials: {
    cabinetBody: {
      color: 0x151515,
      metalness: 0.5,
      roughness: 0.5,
      envMapIntensity: 0.3
    },
    cabinetFrame: {
      color: 0x0a0a0a,
      metalness: 0.6,
      roughness: 0.4
    },
    floor: {
      color: 0x0a0a0a,
      metalness: 0.1,
      roughness: 0.9
    }
  },

  lighting: {
    ambient: { color: 0x222222, intensity: 0.2 },
    directional: { color: 0x444444, intensity: 0.3 },
    hemisphere: { skyColor: 0x111111, groundColor: 0x000000, intensity: 0.1 }
  },

  ui: {
    primaryColor: '#336699',
    secondaryColor: '#224466',
    dangerColor: '#cc3300',
    warningColor: '#cc9900',
    successColor: '#339966',
    backgroundColor: 'rgba(0, 0, 0, 0.9)',
    borderColor: 'rgba(50, 50, 50, 0.5)',
    textColor: '#888888',
    textSecondaryColor: '#555555'
  },

  effects: {
    bloom: false,
    bloomStrength: 0,
    outline: true,
    particles: false,
    flowLines: false
  }
}
```

**Step 4: 主题索引文件**

```typescript
// frontend/src/config/themes/index.ts
export * from './types'
export { techBlueTheme } from './tech-blue'
export { wireframeTheme } from './wireframe'
export { realisticTheme } from './realistic'
export { nightTheme } from './night'

import type { BigscreenTheme } from './types'
import { techBlueTheme } from './tech-blue'
import { wireframeTheme } from './wireframe'
import { realisticTheme } from './realistic'
import { nightTheme } from './night'

export const themes: Record<string, BigscreenTheme> = {
  'tech-blue': techBlueTheme,
  'wireframe': wireframeTheme,
  'realistic': realisticTheme,
  'night': nightTheme
}

export const defaultTheme = 'tech-blue'
```

**Step 5: Commit**

```bash
git add frontend/src/config/themes/
git commit -m "feat(bigscreen): add wireframe, realistic, and night themes"
```

---

### Task 5.3: 创建主题管理composable

**Files:**
- Create: `frontend/src/composables/bigscreen/useTheme.ts`

**Step 1: 编写主题管理逻辑**

```typescript
// frontend/src/composables/bigscreen/useTheme.ts
import { ref, computed, watch } from 'vue'
import * as THREE from 'three'
import { themes, defaultTheme, type BigscreenTheme } from '@/config/themes'

export function useTheme() {
  const currentThemeName = ref(defaultTheme)

  const currentTheme = computed(() => themes[currentThemeName.value] || themes[defaultTheme])

  const availableThemes = computed(() =>
    Object.entries(themes).map(([name, theme]) => ({
      name,
      displayName: theme.displayName
    }))
  )

  function setTheme(themeName: string) {
    if (themes[themeName]) {
      currentThemeName.value = themeName
      applyUITheme(themes[themeName])
      // 3D场景的主题应用由外部处理
    }
  }

  function applyUITheme(theme: BigscreenTheme) {
    const root = document.documentElement
    root.style.setProperty('--bs-primary-color', theme.ui.primaryColor)
    root.style.setProperty('--bs-secondary-color', theme.ui.secondaryColor)
    root.style.setProperty('--bs-danger-color', theme.ui.dangerColor)
    root.style.setProperty('--bs-warning-color', theme.ui.warningColor)
    root.style.setProperty('--bs-success-color', theme.ui.successColor)
    root.style.setProperty('--bs-bg-color', theme.ui.backgroundColor)
    root.style.setProperty('--bs-border-color', theme.ui.borderColor)
    root.style.setProperty('--bs-text-color', theme.ui.textColor)
    root.style.setProperty('--bs-text-secondary-color', theme.ui.textSecondaryColor)
  }

  function applySceneTheme(
    scene: THREE.Scene,
    theme: BigscreenTheme
  ) {
    // 更新背景色
    scene.background = new THREE.Color(theme.scene.backgroundColor)

    // 更新雾效
    if (scene.fog instanceof THREE.FogExp2) {
      scene.fog.color.setHex(theme.scene.fogColor)
      scene.fog.density = theme.scene.fogDensity
    }
  }

  function applyMaterialTheme(
    materials: Map<string, THREE.Material>,
    theme: BigscreenTheme
  ) {
    const bodyMat = materials.get('cabinet_body') as THREE.MeshStandardMaterial
    if (bodyMat) {
      bodyMat.color.setHex(theme.materials.cabinetBody.color)
      bodyMat.metalness = theme.materials.cabinetBody.metalness
      bodyMat.roughness = theme.materials.cabinetBody.roughness
      bodyMat.envMapIntensity = theme.materials.cabinetBody.envMapIntensity
      bodyMat.needsUpdate = true
    }

    const frameMat = materials.get('cabinet_frame') as THREE.MeshStandardMaterial
    if (frameMat) {
      frameMat.color.setHex(theme.materials.cabinetFrame.color)
      frameMat.metalness = theme.materials.cabinetFrame.metalness
      frameMat.roughness = theme.materials.cabinetFrame.roughness
      frameMat.needsUpdate = true
    }
  }

  // 初始化时应用默认主题
  applyUITheme(currentTheme.value)

  return {
    currentThemeName,
    currentTheme,
    availableThemes,
    setTheme,
    applySceneTheme,
    applyMaterialTheme
  }
}
```

**Step 2: Commit**

```bash
git add frontend/src/composables/bigscreen/useTheme.ts
git commit -m "feat(bigscreen): add theme management composable"
```

---

### Task 5.4: 添加主题选择器UI

**Files:**
- Modify: `frontend/src/views/bigscreen/index.vue`

**Step 1: 导入主题composable**

```typescript
import { useTheme } from '@/composables/bigscreen/useTheme'

const themeManager = useTheme()
```

**Step 2: 在顶部栏添加主题选择器**

在 mode-selector 后面添加:

```vue
<div class="theme-selector">
  <el-dropdown @command="handleThemeChange">
    <span class="theme-label">
      <el-icon><Brush /></el-icon>
      {{ themeManager.currentTheme.value.displayName }}
    </span>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item
          v-for="theme in themeManager.availableThemes.value"
          :key="theme.name"
          :command="theme.name"
        >
          {{ theme.displayName }}
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</div>
```

**Step 3: 添加主题切换处理函数**

```typescript
function handleThemeChange(themeName: string) {
  themeManager.setTheme(themeName)

  // 应用到3D场景
  if (threeSceneRef.value?.scene) {
    themeManager.applySceneTheme(threeSceneRef.value.scene, themeManager.currentTheme.value)
  }
}
```

**Step 4: 添加样式**

```scss
.theme-selector {
  .theme-label {
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 6px 12px;
    background: rgba(0, 136, 255, 0.1);
    border: 1px solid rgba(0, 136, 255, 0.3);
    border-radius: 4px;
    font-size: 13px;

    &:hover {
      background: rgba(0, 136, 255, 0.2);
    }
  }
}
```

**Step 5: Commit**

```bash
git add frontend/src/views/bigscreen/index.vue
git commit -m "feat(bigscreen): add theme selector UI"
```

---

## Phase 6: 最终集成与测试

### Task 6.1: 更新组件索引文件

**Files:**
- Modify: `frontend/src/components/bigscreen/index.ts`

**Step 1: 添加新组件导出**

```typescript
// 现有导出保持不变，添加新的导出
export * from './charts'
export * from './effects'
export { default as ContextMenu } from './ui/ContextMenu.vue'
export { default as DigitalCounter } from './ui/DigitalCounter.vue'
```

**Step 2: Commit**

```bash
git add frontend/src/components/bigscreen/index.ts
git commit -m "feat(bigscreen): update component index with new exports"
```

---

### Task 6.2: 构建验证

**Step 1: 运行完整构建**

Run: `cd frontend && npm run build`
Expected: 构建成功，无错误

**Step 2: 运行类型检查**

Run: `cd frontend && npm run type-check`
Expected: 类型检查通过

**Step 3: 如有错误，修复后重新构建**

---

### Task 6.3: 功能测试清单

**Step 1: 启动开发服务器**

Run: `cd frontend && npm run dev`

**Step 2: 测试检查清单**

- [ ] 入场动画正常播放
- [ ] 数字滚动效果正常
- [ ] 左侧面板显示温度趋势图
- [ ] 右侧面板显示功率分布图和PUE趋势图
- [ ] DataV边框和装饰组件正常显示
- [ ] 机柜选中高亮效果正常
- [ ] 电力流向动画正常(开启功率图层时)
- [ ] 告警脉冲效果正常(有告警时)
- [ ] 键盘快捷键响应正常 (1-5视角, Space巡航, H热力图等)
- [ ] 右键菜单正常弹出和响应
- [ ] 主题切换正常
- [ ] 屏幕自适应正常(调整窗口大小)

**Step 3: 截图记录测试结果**

---

### Task 6.4: 最终提交

**Step 1: 提交所有更改**

```bash
git add .
git commit -m "feat(bigscreen): complete visual upgrade implementation

- Add entrance animation with GSAP
- Add ECharts charts (temperature trend, power distribution, PUE trend)
- Add DataV UI components (borders, decorations, water level)
- Add 3D effects (OutlinePass, power flow, alarm pulse)
- Add keyboard shortcuts and context menu
- Add multi-theme support (4 themes)
- Add responsive scale screen adapter
- Update all panels with new design"
```

---

## 验证标准

| 功能模块 | 验证项 | 预期结果 |
|---------|--------|---------|
| 入场动画 | 页面加载后动画播放 | 元素依次入场，数字滚动 |
| 数据图表 | 图表渲染和数据更新 | 实时显示温度/功率/PUE数据 |
| DataV组件 | 边框和装饰显示 | 科技感边框正常显示 |
| 选中高亮 | 点击机柜 | 边缘发光效果 |
| 电力流向 | 开启功率图层 | 蓝色能量线流动 |
| 告警脉冲 | 有告警设备时 | 红色脉冲波纹 |
| 快捷键 | 按1-5/H/P/Space等 | 对应功能响应 |
| 右键菜单 | 在机柜上右键 | 菜单弹出 |
| 主题切换 | 选择不同主题 | UI和场景颜色变化 |
| 屏幕适配 | 调整窗口大小 | 等比缩放 |

---

## 备注

- 本计划预计需要多个开发周期完成
- 建议按Phase顺序实施，每个Phase完成后进行测试
- 如遇到依赖冲突或兼容性问题，优先解决后再继续
- 3D特效部分可能需要根据实际性能进行调优

---

*本实施计划基于设计文档 docs/plans/2026-01-20-bigscreen-visual-upgrade-design.md 创建*
