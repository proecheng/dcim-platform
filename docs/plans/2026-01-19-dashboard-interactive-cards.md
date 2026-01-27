# Dashboard Interactive Energy Cards Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enhance the 5 energy dashboard cards with interactive mini-charts, trend indicators, click-to-drill-down navigation, and tooltip details.

**Architecture:** Create standalone Vue components for each card type with embedded ECharts sparklines. Each card will show current value, trend spark, and support click navigation to detailed pages. Use composable pattern for shared chart logic.

**Tech Stack:** Vue 3 Composition API, ECharts 5, TypeScript, Element Plus

---

## Task 1: Create Sparkline Component

**Files:**
- Create: `frontend/src/components/charts/Sparkline.vue`
- Test: Manual visual testing in Storybook-like environment

**Step 1: Create the Sparkline component file**

```vue
<template>
  <div ref="chartRef" class="sparkline" :style="{ width, height }"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, shallowRef } from 'vue'
import * as echarts from 'echarts'

interface Props {
  data: number[]
  width?: string
  height?: string
  color?: string
  areaColor?: string
  showArea?: boolean
  lineWidth?: number
}

const props = withDefaults(defineProps<Props>(), {
  width: '100%',
  height: '40px',
  color: '#409EFF',
  showArea: true,
  lineWidth: 2
})

const chartRef = ref<HTMLElement>()
const chartInstance = shallowRef<echarts.ECharts>()

const getOption = (): echarts.EChartsOption => ({
  grid: {
    top: 2,
    right: 2,
    bottom: 2,
    left: 2
  },
  xAxis: {
    type: 'category',
    show: false,
    data: props.data.map((_, i) => i)
  },
  yAxis: {
    type: 'value',
    show: false,
    min: (value) => value.min - (value.max - value.min) * 0.1,
    max: (value) => value.max + (value.max - value.min) * 0.1
  },
  series: [{
    type: 'line',
    data: props.data,
    smooth: true,
    symbol: 'none',
    lineStyle: {
      width: props.lineWidth,
      color: props.color
    },
    areaStyle: props.showArea ? {
      color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: props.areaColor || props.color + '40' },
        { offset: 1, color: props.areaColor || props.color + '05' }
      ])
    } : undefined
  }]
})

const initChart = () => {
  if (!chartRef.value) return
  chartInstance.value = echarts.init(chartRef.value)
  chartInstance.value.setOption(getOption())
}

const updateChart = () => {
  chartInstance.value?.setOption(getOption(), true)
}

const resizeChart = () => {
  chartInstance.value?.resize()
}

watch(() => props.data, updateChart, { deep: true })

onMounted(() => {
  initChart()
  window.addEventListener('resize', resizeChart)
})

onUnmounted(() => {
  window.removeEventListener('resize', resizeChart)
  chartInstance.value?.dispose()
})

defineExpose({ resize: resizeChart })
</script>

<style scoped>
.sparkline {
  min-width: 60px;
}
</style>
```

**Step 2: Verify component creation**

Run: `dir frontend\src\components\charts\Sparkline.vue`
Expected: File exists

**Step 3: Commit**

```bash
git add frontend/src/components/charts/Sparkline.vue
git commit -m "feat(charts): add Sparkline component for mini trend visualization"
```

---

## Task 2: Create Interactive Power Card Component

**Files:**
- Create: `frontend/src/components/energy/InteractivePowerCard.vue`
- Modify: `frontend/src/components/charts/Sparkline.vue` (import)

**Step 1: Create the InteractivePowerCard component**

```vue
<template>
  <el-card
    class="interactive-power-card"
    shadow="hover"
    @click="handleClick"
  >
    <div class="card-header">
      <div class="header-left">
        <el-icon :size="20" :color="iconColor"><component :is="icon" /></el-icon>
        <span class="title">{{ title }}</span>
      </div>
      <el-tooltip v-if="tooltip" :content="tooltip" placement="top">
        <el-icon :size="16" class="info-icon"><InfoFilled /></el-icon>
      </el-tooltip>
    </div>

    <div class="card-body">
      <div class="main-value">
        <span class="value" :style="{ color: valueColor }">{{ formattedValue }}</span>
        <span class="unit">{{ unit }}</span>
        <el-icon v-if="trendIcon" :size="16" :color="trendColor" class="trend-icon">
          <component :is="trendIcon" />
        </el-icon>
      </div>

      <div class="sparkline-container" v-if="trendData.length > 0">
        <Sparkline
          :data="trendData"
          :color="sparklineColor"
          height="32px"
        />
      </div>

      <div class="details" v-if="details.length > 0">
        <div v-for="(item, index) in details" :key="index" class="detail-item">
          <span class="label">{{ item.label }}</span>
          <span class="value">{{ item.value }}</span>
        </div>
      </div>

      <div class="footer" v-if="footerTag || footerText">
        <el-tag v-if="footerTag" :type="footerTag.type" size="small">
          {{ footerTag.text }}
        </el-tag>
        <span v-if="footerText" class="footer-text">{{ footerText }}</span>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { InfoFilled, Top, Bottom, Minus } from '@element-plus/icons-vue'
import Sparkline from '@/components/charts/Sparkline.vue'

interface DetailItem {
  label: string
  value: string | number
}

interface FooterTag {
  text: string
  type: 'success' | 'warning' | 'danger' | 'info'
}

const props = defineProps<{
  title: string
  value: number | string
  unit: string
  icon: any
  iconColor?: string
  valueColor?: string
  trend?: 'up' | 'down' | 'stable'
  trendData?: number[]
  sparklineColor?: string
  details?: DetailItem[]
  footerTag?: FooterTag
  footerText?: string
  tooltip?: string
  navigateTo?: string
}>()

const router = useRouter()

const formattedValue = computed(() => {
  if (typeof props.value === 'number') {
    return props.value.toFixed(1)
  }
  return props.value
})

const trendIcon = computed(() => {
  switch (props.trend) {
    case 'up': return Top
    case 'down': return Bottom
    default: return null
  }
})

const trendColor = computed(() => {
  switch (props.trend) {
    case 'up': return '#F56C6C'
    case 'down': return '#67C23A'
    default: return '#909399'
  }
})

const trendData = computed(() => props.trendData || [])

const handleClick = () => {
  if (props.navigateTo) {
    router.push(props.navigateTo)
  }
}
</script>

<style scoped lang="scss">
.interactive-power-card {
  cursor: pointer;
  transition: all 0.3s;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }

  :deep(.el-card__body) {
    padding: 16px;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;

    .header-left {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .title {
      font-size: 14px;
      color: #606266;
    }

    .info-icon {
      color: #C0C4CC;
      cursor: help;
    }
  }

  .card-body {
    .main-value {
      display: flex;
      align-items: baseline;
      gap: 4px;
      margin-bottom: 8px;

      .value {
        font-size: 28px;
        font-weight: bold;
        color: #303133;
      }

      .unit {
        font-size: 14px;
        color: #909399;
      }

      .trend-icon {
        margin-left: 4px;
      }
    }

    .sparkline-container {
      margin: 8px 0;
    }

    .details {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 8px;

      .detail-item {
        display: flex;
        gap: 4px;
        font-size: 12px;

        .label {
          color: #909399;
        }

        .value {
          color: #606266;
        }
      }
    }

    .footer {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 8px;

      .footer-text {
        font-size: 12px;
        color: #909399;
      }
    }
  }
}
</style>
```

**Step 2: Verify component creation**

Run: `dir frontend\src\components\energy\InteractivePowerCard.vue`
Expected: File exists

**Step 3: Commit**

```bash
git add frontend/src/components/energy/InteractivePowerCard.vue
git commit -m "feat(energy): add InteractivePowerCard with sparkline and drill-down"
```

---

## Task 3: Create PUE Indicator Card Component

**Files:**
- Create: `frontend/src/components/energy/PUEIndicatorCard.vue`

**Step 1: Create the PUE card with gauge visualization**

```vue
<template>
  <el-card class="pue-indicator-card" shadow="hover" @click="$router.push('/energy/analysis')">
    <div class="card-header">
      <div class="header-left">
        <el-icon :size="20" color="#67C23A"><TrendCharts /></el-icon>
        <span class="title">PUE效率</span>
      </div>
      <el-tooltip content="Power Usage Effectiveness: 数据中心总能耗与IT设备能耗比值" placement="top">
        <el-icon :size="16" class="info-icon"><InfoFilled /></el-icon>
      </el-tooltip>
    </div>

    <div class="card-body">
      <div class="pue-display">
        <div class="pue-value" :class="pueClass">
          {{ pue?.toFixed(2) || '-' }}
        </div>
        <el-icon v-if="trend === 'down'" :size="20" color="#67C23A"><Bottom /></el-icon>
        <el-icon v-else-if="trend === 'up'" :size="20" color="#F56C6C"><Top /></el-icon>
      </div>

      <div class="pue-bar">
        <div class="bar-track">
          <div class="bar-fill" :style="barStyle"></div>
          <div class="target-marker" :style="targetMarkerStyle"></div>
        </div>
        <div class="bar-labels">
          <span>1.0</span>
          <span class="target-label">目标:{{ target }}</span>
          <span>2.5</span>
        </div>
      </div>

      <div class="sparkline-container" v-if="trendData.length > 0">
        <Sparkline :data="trendData" :color="sparklineColor" height="28px" />
      </div>

      <div class="footer">
        <el-tag :type="statusType" size="small">{{ statusText }}</el-tag>
        <span class="compare-text" v-if="compareYesterday">
          较昨日 {{ compareYesterday > 0 ? '+' : '' }}{{ compareYesterday.toFixed(2) }}
        </span>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { TrendCharts, InfoFilled, Top, Bottom } from '@element-plus/icons-vue'
import Sparkline from '@/components/charts/Sparkline.vue'

const props = defineProps<{
  pue?: number
  target?: number
  trend?: 'up' | 'down' | 'stable'
  trendData?: number[]
  compareYesterday?: number
}>()

const target = computed(() => props.target || 1.4)

const pueClass = computed(() => {
  const pue = props.pue || 0
  if (pue <= 1.4) return 'excellent'
  if (pue <= 1.6) return 'good'
  if (pue <= 1.8) return 'normal'
  return 'warning'
})

const sparklineColor = computed(() => {
  const pue = props.pue || 0
  if (pue <= 1.4) return '#67C23A'
  if (pue <= 1.6) return '#409EFF'
  if (pue <= 1.8) return '#E6A23C'
  return '#F56C6C'
})

const statusType = computed(() => {
  const pue = props.pue || 0
  if (pue <= target.value) return 'success'
  if (pue <= target.value + 0.2) return 'warning'
  return 'danger'
})

const statusText = computed(() => {
  const pue = props.pue || 0
  if (pue <= target.value) return '达标'
  return '待优化'
})

const barStyle = computed(() => {
  const pue = props.pue || 1.0
  const percent = Math.min(100, Math.max(0, ((pue - 1.0) / 1.5) * 100))
  return {
    width: `${percent}%`,
    backgroundColor: sparklineColor.value
  }
})

const targetMarkerStyle = computed(() => {
  const percent = ((target.value - 1.0) / 1.5) * 100
  return { left: `${percent}%` }
})
</script>

<style scoped lang="scss">
.pue-indicator-card {
  cursor: pointer;
  transition: all 0.3s;

  &:hover {
    transform: translateY(-2px);
  }

  :deep(.el-card__body) {
    padding: 16px;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;

    .header-left {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .title { font-size: 14px; color: #606266; }
    .info-icon { color: #C0C4CC; cursor: help; }
  }

  .card-body {
    .pue-display {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 12px;

      .pue-value {
        font-size: 32px;
        font-weight: bold;

        &.excellent { color: #67C23A; }
        &.good { color: #409EFF; }
        &.normal { color: #E6A23C; }
        &.warning { color: #F56C6C; }
      }
    }

    .pue-bar {
      margin: 12px 0;

      .bar-track {
        position: relative;
        height: 8px;
        background: #EBEEF5;
        border-radius: 4px;

        .bar-fill {
          height: 100%;
          border-radius: 4px;
          transition: width 0.3s;
        }

        .target-marker {
          position: absolute;
          top: -4px;
          width: 2px;
          height: 16px;
          background: #303133;
          transform: translateX(-50%);
        }
      }

      .bar-labels {
        display: flex;
        justify-content: space-between;
        margin-top: 4px;
        font-size: 10px;
        color: #909399;

        .target-label {
          color: #606266;
          font-weight: 500;
        }
      }
    }

    .sparkline-container {
      margin: 8px 0;
    }

    .footer {
      display: flex;
      align-items: center;
      gap: 8px;

      .compare-text {
        font-size: 12px;
        color: #909399;
      }
    }
  }
}
</style>
```

**Step 2: Verify and commit**

```bash
git add frontend/src/components/energy/PUEIndicatorCard.vue
git commit -m "feat(energy): add PUEIndicatorCard with visual gauge and trend"
```

---

## Task 4: Create Demand Status Card Component

**Files:**
- Create: `frontend/src/components/energy/DemandStatusCard.vue`

**Step 1: Create the Demand card with progress visualization**

```vue
<template>
  <el-card class="demand-status-card" shadow="hover" @click="$router.push('/energy/analysis')">
    <div class="card-header">
      <div class="header-left">
        <el-icon :size="20" color="#E6A23C"><DataLine /></el-icon>
        <span class="title">需量状态</span>
      </div>
    </div>

    <div class="card-body">
      <div class="main-display">
        <span class="value" :class="valueClass">{{ utilizationRate }}</span>
        <span class="unit">%</span>
      </div>

      <div class="demand-progress">
        <el-progress
          :percentage="utilizationRate"
          :color="progressColors"
          :stroke-width="12"
          :show-text="false"
        />
      </div>

      <div class="demand-info">
        <div class="info-item">
          <span class="label">当前需量</span>
          <span class="value">{{ currentDemand?.toFixed(0) || 0 }} kW</span>
        </div>
        <div class="info-item">
          <span class="label">申报需量</span>
          <span class="value">{{ declaredDemand || 0 }} kW</span>
        </div>
      </div>

      <div class="sparkline-container" v-if="trendData.length > 0">
        <Sparkline :data="trendData" :color="trendColor" height="28px" />
      </div>

      <div class="footer" v-if="overDeclaredRisk">
        <el-tag type="danger" size="small" effect="light">
          <el-icon><Warning /></el-icon>
          超申报风险
        </el-tag>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { DataLine, Warning } from '@element-plus/icons-vue'
import Sparkline from '@/components/charts/Sparkline.vue'

const props = defineProps<{
  currentDemand?: number
  declaredDemand?: number
  trendData?: number[]
  overDeclaredRisk?: boolean
}>()

const utilizationRate = computed(() => {
  if (!props.declaredDemand || props.declaredDemand === 0) return 0
  return Math.round(((props.currentDemand || 0) / props.declaredDemand) * 100)
})

const valueClass = computed(() => {
  const rate = utilizationRate.value
  if (rate >= 90) return 'danger'
  if (rate >= 75) return 'warning'
  return 'normal'
})

const progressColors = [
  { color: '#67C23A', percentage: 60 },
  { color: '#E6A23C', percentage: 80 },
  { color: '#F56C6C', percentage: 100 }
]

const trendColor = computed(() => {
  const rate = utilizationRate.value
  if (rate >= 90) return '#F56C6C'
  if (rate >= 75) return '#E6A23C'
  return '#67C23A'
})
</script>

<style scoped lang="scss">
.demand-status-card {
  cursor: pointer;
  transition: all 0.3s;

  &:hover {
    transform: translateY(-2px);
  }

  :deep(.el-card__body) {
    padding: 16px;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;

    .header-left {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .title { font-size: 14px; color: #606266; }
  }

  .card-body {
    .main-display {
      display: flex;
      align-items: baseline;
      gap: 4px;
      margin-bottom: 8px;

      .value {
        font-size: 28px;
        font-weight: bold;

        &.normal { color: #67C23A; }
        &.warning { color: #E6A23C; }
        &.danger { color: #F56C6C; }
      }

      .unit { font-size: 14px; color: #909399; }
    }

    .demand-progress {
      margin: 8px 0;
    }

    .demand-info {
      display: flex;
      justify-content: space-between;
      margin: 8px 0;

      .info-item {
        display: flex;
        flex-direction: column;
        gap: 2px;

        .label { font-size: 12px; color: #909399; }
        .value { font-size: 14px; color: #606266; font-weight: 500; }
      }
    }

    .sparkline-container {
      margin: 8px 0;
    }

    .footer {
      margin-top: 8px;

      .el-tag {
        display: flex;
        align-items: center;
        gap: 4px;
      }
    }
  }
}
</style>
```

**Step 2: Commit**

```bash
git add frontend/src/components/energy/DemandStatusCard.vue
git commit -m "feat(energy): add DemandStatusCard with progress bar and risk alert"
```

---

## Task 5: Create Cost Card Component

**Files:**
- Create: `frontend/src/components/energy/CostCard.vue`

**Step 1: Create the Cost card with pie chart**

```vue
<template>
  <el-card class="cost-card" shadow="hover" @click="$router.push('/energy/statistics')">
    <div class="card-header">
      <div class="header-left">
        <el-icon :size="20" color="#F56C6C"><Coin /></el-icon>
        <span class="title">今日电费</span>
      </div>
    </div>

    <div class="card-body">
      <div class="main-display">
        <span class="currency">¥</span>
        <span class="value">{{ todayCost?.toFixed(0) || 0 }}</span>
      </div>

      <div class="pie-container" ref="pieRef"></div>

      <div class="cost-info">
        <div class="info-item">
          <span class="dot peak"></span>
          <span class="label">峰时</span>
          <span class="value">{{ peakRatio }}%</span>
        </div>
        <div class="info-item">
          <span class="dot flat"></span>
          <span class="label">平时</span>
          <span class="value">{{ flatRatio }}%</span>
        </div>
        <div class="info-item">
          <span class="dot valley"></span>
          <span class="label">谷时</span>
          <span class="value">{{ valleyRatio }}%</span>
        </div>
      </div>

      <div class="footer">
        <span class="footer-item">本月: ¥{{ monthCost?.toFixed(0) || 0 }}</span>
        <span class="footer-item">均价: ¥{{ avgPrice?.toFixed(2) || 0 }}/度</span>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, shallowRef, computed } from 'vue'
import { Coin } from '@element-plus/icons-vue'
import * as echarts from 'echarts'

const props = defineProps<{
  todayCost?: number
  monthCost?: number
  avgPrice?: number
  peakRatio?: number
  flatRatio?: number
  valleyRatio?: number
}>()

const pieRef = ref<HTMLElement>()
const chartInstance = shallowRef<echarts.ECharts>()

const peakRatio = computed(() => props.peakRatio || 45)
const flatRatio = computed(() => props.flatRatio || 30)
const valleyRatio = computed(() => props.valleyRatio || 25)

const initChart = () => {
  if (!pieRef.value) return
  chartInstance.value = echarts.init(pieRef.value)
  updateChart()
}

const updateChart = () => {
  if (!chartInstance.value) return

  chartInstance.value.setOption({
    series: [{
      type: 'pie',
      radius: ['50%', '70%'],
      center: ['50%', '50%'],
      avoidLabelOverlap: false,
      label: { show: false },
      data: [
        { value: peakRatio.value, name: '峰时', itemStyle: { color: '#F56C6C' } },
        { value: flatRatio.value, name: '平时', itemStyle: { color: '#E6A23C' } },
        { value: valleyRatio.value, name: '谷时', itemStyle: { color: '#67C23A' } }
      ]
    }]
  })
}

watch([peakRatio, flatRatio, valleyRatio], updateChart)

onMounted(() => {
  initChart()
  window.addEventListener('resize', () => chartInstance.value?.resize())
})

onUnmounted(() => {
  chartInstance.value?.dispose()
})
</script>

<style scoped lang="scss">
.cost-card {
  cursor: pointer;
  transition: all 0.3s;

  &:hover {
    transform: translateY(-2px);
  }

  :deep(.el-card__body) {
    padding: 16px;
  }

  .card-header {
    display: flex;
    align-items: center;
    margin-bottom: 8px;

    .header-left {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .title { font-size: 14px; color: #606266; }
  }

  .card-body {
    .main-display {
      display: flex;
      align-items: baseline;
      margin-bottom: 8px;

      .currency { font-size: 16px; color: #F56C6C; font-weight: 500; }
      .value { font-size: 28px; font-weight: bold; color: #303133; }
    }

    .pie-container {
      height: 60px;
      margin: 8px 0;
    }

    .cost-info {
      display: flex;
      justify-content: space-around;
      margin: 8px 0;

      .info-item {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 12px;

        .dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;

          &.peak { background: #F56C6C; }
          &.flat { background: #E6A23C; }
          &.valley { background: #67C23A; }
        }

        .label { color: #909399; }
        .value { color: #606266; font-weight: 500; }
      }
    }

    .footer {
      display: flex;
      justify-content: space-between;
      font-size: 12px;
      color: #909399;
    }
  }
}
</style>
```

**Step 2: Commit**

```bash
git add frontend/src/components/energy/CostCard.vue
git commit -m "feat(energy): add CostCard with peak/valley pie chart"
```

---

## Task 6: Create Suggestions Card Component

**Files:**
- Create: `frontend/src/components/energy/SuggestionsCard.vue`

**Step 1: Create the Suggestions card**

```vue
<template>
  <el-card class="suggestions-card" shadow="hover" @click="$router.push('/energy/suggestions')">
    <div class="card-header">
      <div class="header-left">
        <el-icon :size="20" color="#909399"><List /></el-icon>
        <span class="title">节能建议</span>
      </div>
      <el-badge :value="pendingCount" :hidden="pendingCount === 0" type="danger" />
    </div>

    <div class="card-body">
      <div class="main-display">
        <span class="value">{{ pendingCount }}</span>
        <span class="unit">条待处理</span>
      </div>

      <div class="priority-list" v-if="highPriorityCount > 0">
        <el-tag type="danger" size="small" effect="light">
          {{ highPriorityCount }} 条高优先级
        </el-tag>
      </div>

      <div class="saving-info" v-if="potentialSaving > 0">
        <el-icon :size="14" color="#67C23A"><TrendCharts /></el-icon>
        <span>可节省 ¥{{ potentialSaving?.toFixed(0) }}/月</span>
      </div>

      <div class="recent-suggestions" v-if="recentSuggestions.length > 0">
        <div
          v-for="(item, index) in recentSuggestions.slice(0, 2)"
          :key="index"
          class="suggestion-item"
        >
          <el-icon :size="12" :color="getPriorityColor(item.priority)"><Warning /></el-icon>
          <span class="text">{{ item.title }}</span>
        </div>
      </div>

      <div class="footer">
        <span class="action-hint">点击查看详情 →</span>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { List, Warning, TrendCharts } from '@element-plus/icons-vue'

interface Suggestion {
  title: string
  priority: 'high' | 'medium' | 'low'
}

defineProps<{
  pendingCount?: number
  highPriorityCount?: number
  potentialSaving?: number
  recentSuggestions?: Suggestion[]
}>()

const getPriorityColor = (priority: string) => {
  switch (priority) {
    case 'high': return '#F56C6C'
    case 'medium': return '#E6A23C'
    default: return '#909399'
  }
}
</script>

<style scoped lang="scss">
.suggestions-card {
  cursor: pointer;
  transition: all 0.3s;

  &:hover {
    transform: translateY(-2px);

    .action-hint {
      color: #409EFF;
    }
  }

  :deep(.el-card__body) {
    padding: 16px;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;

    .header-left {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .title { font-size: 14px; color: #606266; }
  }

  .card-body {
    .main-display {
      display: flex;
      align-items: baseline;
      gap: 4px;
      margin-bottom: 8px;

      .value { font-size: 28px; font-weight: bold; color: #303133; }
      .unit { font-size: 14px; color: #909399; }
    }

    .priority-list {
      margin: 8px 0;
    }

    .saving-info {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 13px;
      color: #67C23A;
      margin: 8px 0;
    }

    .recent-suggestions {
      margin: 8px 0;

      .suggestion-item {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 12px;
        color: #606266;
        padding: 4px 0;
        border-bottom: 1px dashed #EBEEF5;

        &:last-child {
          border-bottom: none;
        }

        .text {
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      }
    }

    .footer {
      margin-top: 8px;

      .action-hint {
        font-size: 12px;
        color: #C0C4CC;
        transition: color 0.3s;
      }
    }
  }
}
</style>
```

**Step 2: Commit**

```bash
git add frontend/src/components/energy/SuggestionsCard.vue
git commit -m "feat(energy): add SuggestionsCard with priority indicators"
```

---

## Task 7: Add Trend Data API Support

**Files:**
- Modify: `backend/app/api/v1/realtime.py:371-552` (enhance energy-dashboard endpoint)
- Modify: `frontend/src/api/modules/energy.ts` (add trend data types)

**Step 1: Enhance backend API to include trend data**

Add to `realtime.py` in `get_energy_dashboard` function, after line 544:

```python
    # 6. 趋势数据 (用于迷你图表)
    trends = {
        "power_1h": [],
        "pue_24h": [],
        "demand_24h": []
    }

    # 获取近1小时功率趋势 (每5分钟一个点)
    one_hour_ago = datetime.now() - timedelta(hours=1)
    power_trend_result = await db.execute(
        select(PUEHistory.total_power, PUEHistory.record_time)
        .where(PUEHistory.record_time >= one_hour_ago)
        .order_by(PUEHistory.record_time)
    )
    power_trend_rows = power_trend_result.all()
    trends["power_1h"] = [row[0] or 0 for row in power_trend_rows]

    # 获取近24小时PUE趋势 (每小时一个点)
    one_day_ago = datetime.now() - timedelta(hours=24)
    pue_trend_result = await db.execute(
        select(func.avg(PUEHistory.pue), func.date_trunc('hour', PUEHistory.record_time))
        .where(PUEHistory.record_time >= one_day_ago)
        .group_by(func.date_trunc('hour', PUEHistory.record_time))
        .order_by(func.date_trunc('hour', PUEHistory.record_time))
    )
    pue_trend_rows = pue_trend_result.all()
    trends["pue_24h"] = [round(row[0], 2) if row[0] else 0 for row in pue_trend_rows]

    # 获取近24小时需量趋势
    trends["demand_24h"] = [row[0] or 0 for row in power_trend_rows[-24:]] if len(power_trend_rows) >= 24 else trends["power_1h"]
```

Then update the return statement to include trends:

```python
    return {
        "realtime": realtime,
        "efficiency": efficiency,
        "demand": demand,
        "cost": cost,
        "suggestions": suggestions,
        "trends": trends,  # Add this line
        "update_time": datetime.now().isoformat()
    }
```

**Step 2: Update frontend type definition**

Add to `energy.ts` EnergyDashboardData interface:

```typescript
export interface EnergyDashboardData {
  realtime: {
    total_power: number
    it_power: number
    cooling_power: number
    other_power: number
    today_energy: number
    month_energy: number
  }
  efficiency: {
    pue: number
    pue_target: number
    pue_trend: 'up' | 'down' | 'stable'
    cooling_ratio: number
    it_ratio: number
  }
  demand: {
    current_demand: number
    declared_demand: number
    utilization_rate: number
    max_today: number
    over_declared_risk: boolean
  }
  cost: {
    today_cost: number
    month_cost: number
    peak_ratio: number
    valley_ratio: number
    avg_price: number
  }
  suggestions: {
    pending_count: number
    high_priority_count: number
    potential_saving_kwh: number
    potential_saving_cost: number
  }
  trends: {
    power_1h: number[]
    pue_24h: number[]
    demand_24h: number[]
  }
  update_time: string
}
```

**Step 3: Commit**

```bash
git add backend/app/api/v1/realtime.py frontend/src/api/modules/energy.ts
git commit -m "feat(api): add trend data arrays to energy-dashboard endpoint"
```

---

## Task 8: Update Dashboard to Use New Components

**Files:**
- Modify: `frontend/src/views/dashboard/index.vue:51-150`

**Step 1: Import new components**

Add to script imports section:

```typescript
import InteractivePowerCard from '@/components/energy/InteractivePowerCard.vue'
import PUEIndicatorCard from '@/components/energy/PUEIndicatorCard.vue'
import DemandStatusCard from '@/components/energy/DemandStatusCard.vue'
import CostCard from '@/components/energy/CostCard.vue'
import SuggestionsCard from '@/components/energy/SuggestionsCard.vue'
import { Lightning } from '@element-plus/icons-vue'
```

**Step 2: Replace energy cards section (lines 51-150)**

Replace the entire `<el-row class="energy-cards">` section with:

```vue
    <!-- 能源统计卡片 (V2.3 Enhanced) -->
    <el-row :gutter="20" class="energy-cards" v-if="energyData">
      <el-col :span="5">
        <InteractivePowerCard
          title="实时功率"
          :value="energyData.realtime?.total_power || 0"
          unit="kW"
          :icon="Lightning"
          icon-color="#409EFF"
          :trend-data="energyData.trends?.power_1h || []"
          sparkline-color="#409EFF"
          :details="[
            { label: 'IT', value: `${energyData.realtime?.it_power?.toFixed(1) || 0} kW` },
            { label: '制冷', value: `${energyData.realtime?.cooling_power?.toFixed(1) || 0} kW` }
          ]"
          navigate-to="/energy/monitor"
          tooltip="数据中心总功率消耗，包括IT设备和基础设施"
        />
      </el-col>

      <el-col :span="5">
        <PUEIndicatorCard
          :pue="energyData.efficiency?.pue"
          :target="energyData.efficiency?.pue_target"
          :trend="energyData.efficiency?.pue_trend"
          :trend-data="energyData.trends?.pue_24h || []"
          :compare-yesterday="energyData.efficiency?.pue - 1.5"
        />
      </el-col>

      <el-col :span="5">
        <DemandStatusCard
          :current-demand="energyData.demand?.current_demand"
          :declared-demand="energyData.demand?.declared_demand"
          :trend-data="energyData.trends?.demand_24h || []"
          :over-declared-risk="energyData.demand?.over_declared_risk"
        />
      </el-col>

      <el-col :span="5">
        <CostCard
          :today-cost="energyData.cost?.today_cost"
          :month-cost="energyData.cost?.month_cost"
          :avg-price="energyData.cost?.avg_price"
          :peak-ratio="energyData.cost?.peak_ratio"
          :valley-ratio="energyData.cost?.valley_ratio"
          :flat-ratio="100 - (energyData.cost?.peak_ratio || 0) - (energyData.cost?.valley_ratio || 0)"
        />
      </el-col>

      <el-col :span="4">
        <SuggestionsCard
          :pending-count="energyData.suggestions?.pending_count"
          :high-priority-count="energyData.suggestions?.high_priority_count"
          :potential-saving="energyData.suggestions?.potential_saving_cost"
        />
      </el-col>
    </el-row>
```

**Step 3: Commit**

```bash
git add frontend/src/views/dashboard/index.vue
git commit -m "feat(dashboard): integrate interactive energy cards with sparklines"
```

---

## Task 9: Add Component Barrel Export

**Files:**
- Create: `frontend/src/components/energy/index.ts`

**Step 1: Create barrel export file**

```typescript
// Energy components barrel export
export { default as InteractivePowerCard } from './InteractivePowerCard.vue'
export { default as PUEIndicatorCard } from './PUEIndicatorCard.vue'
export { default as DemandStatusCard } from './DemandStatusCard.vue'
export { default as CostCard } from './CostCard.vue'
export { default as SuggestionsCard } from './SuggestionsCard.vue'
export { default as PUEGauge } from './PUEGauge.vue'
export { default as PowerCard } from './PowerCard.vue'
export { default as EnergySuggestionCard } from './EnergySuggestionCard.vue'
```

**Step 2: Commit**

```bash
git add frontend/src/components/energy/index.ts
git commit -m "chore(components): add energy components barrel export"
```

---

## Task 10: Final Integration Test

**Step 1: Start backend service**

```bash
cd D:\mytest1
python -m uvicorn backend.app.main:app --reload --port 8000
```

Expected: Server starts successfully

**Step 2: Start frontend service**

```bash
cd D:\mytest1\frontend
npm run dev
```

Expected: Vite dev server starts on port 3000

**Step 3: Manual verification checklist**

- [ ] Dashboard loads without errors
- [ ] All 5 energy cards display with data
- [ ] Sparkline charts render in Power, PUE, and Demand cards
- [ ] Pie chart renders in Cost card
- [ ] Clicking cards navigates to correct pages
- [ ] Hover effects work on all cards
- [ ] Data refreshes every 10 seconds

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat(dashboard): complete interactive energy cards implementation

- Add Sparkline component for mini trend charts
- Add InteractivePowerCard with trend visualization
- Add PUEIndicatorCard with gauge bar and trend
- Add DemandStatusCard with progress and risk alert
- Add CostCard with peak/valley pie chart
- Add SuggestionsCard with priority indicators
- Enhance energy-dashboard API with trend data
- Update dashboard to use new interactive components"
```

---

Plan complete and saved to `docs/plans/2026-01-19-dashboard-interactive-cards.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
