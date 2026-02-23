<!-- frontend/src/components/bigscreen/BigscreenHistoryDialog.vue -->
<!-- 大屏设备历史数据趋势弹窗 -->
<template>
  <Teleport to="body">
    <Transition name="history-dialog">
      <div
        v-if="visible"
        class="history-dialog-overlay"
        @click.self="handleClose"
        @keydown.esc="handleClose"
      >
        <div class="history-dialog" role="dialog" aria-modal="true" aria-label="设备历史数据">
          <!-- 头部 -->
          <div class="dialog-header">
            <div class="device-info">
              <h2 class="device-name">{{ deviceName }}</h2>
              <span class="device-type">{{ deviceType }}</span>
              <span class="device-status" :class="deviceStatus">
                <i class="status-dot"></i>
                {{ statusLabel }}
              </span>
            </div>
            <button class="close-btn" @click="handleClose" aria-label="关闭">
              <el-icon :size="20"><Close /></el-icon>
            </button>
          </div>

          <!-- 工具栏 -->
          <div class="dialog-toolbar">
            <!-- 时间范围选择 -->
            <div class="time-range-group">
              <button
                v-for="range in timeRanges"
                :key="range.value"
                class="range-btn"
                :class="{ active: currentRange === range.value }"
                @click="switchTimeRange(range.value)"
              >
                {{ range.label }}
              </button>
            </div>

            <!-- 点位筛选 -->
            <div class="point-filter" v-if="pointOptions.length > 0">
              <span class="filter-label">点位:</span>
              <label
                v-for="pt in pointOptions"
                :key="pt.id"
                class="point-checkbox"
              >
                <input
                  type="checkbox"
                  :checked="selectedPointIds.has(pt.id)"
                  @change="togglePoint(pt.id)"
                />
                <span
                  class="point-color"
                  :style="{ background: getPointColor(pt.id) }"
                ></span>
                <span class="point-label">{{ pt.point_name }}</span>
              </label>
            </div>
          </div>

          <!-- 图表区域 -->
          <div class="dialog-body">
            <div v-if="loading" class="loading-state">
              <el-icon class="spin-icon" :size="32"><Loading /></el-icon>
              <span>加载历史数据...</span>
            </div>
            <div v-else-if="noData" class="empty-state">
              <el-icon :size="48"><DataLine /></el-icon>
              <span>{{ noDataHint }}</span>
            </div>
            <div v-else ref="chartRef" class="trend-chart"></div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted, nextTick, shallowRef } from 'vue'
import { Close, Loading, DataLine } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import type { ECharts, EChartsOption } from 'echarts'
import { getDeviceDetail } from '@/api/modules/device'
import type { PointRealtimeItem } from '@/api/modules/device'
import { getPointTrend } from '@/api/modules/history'
import type { TrendData } from '@/api/modules/history'
import { getPointThresholds } from '@/api/modules/threshold'
import type { ThresholdInfo } from '@/api/modules/threshold'

const props = defineProps<{
  visible: boolean
  deviceId: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

// ==================== 常量 ====================

const CHART_COLORS = [
  '#00ccff', '#00ff88', '#ffaa00', '#ff4d4f',
  '#9254de', '#36cfc9', '#597ef7', '#73d13d'
]

interface TimeRange {
  label: string
  value: number // 分钟
}

const timeRanges: TimeRange[] = [
  { label: '1小时', value: 60 },
  { label: '6小时', value: 360 },
  { label: '24小时', value: 1440 },
  { label: '7天', value: 10080 }
]

// ==================== 状态 ====================

const loading = ref(false)
const currentRange = ref(1440) // 默认24小时
const chartRef = ref<HTMLElement | null>(null)
const chartInstance = shallowRef<ECharts | null>(null)

// 设备信息
const deviceName = ref('--')
const deviceType = ref('--')
const deviceStatus = ref('normal')

// 点位数据
const aiPoints = ref<PointRealtimeItem[]>([])
const selectedPointIds = ref<Set<number>>(new Set())
const trendDataMap = ref<Map<number, TrendData[]>>(new Map())
const thresholdMap = ref<Map<number, ThresholdInfo[]>>(new Map())
const noDataHint = ref('暂无历史数据')

// ==================== 计算属性 ====================

const statusLabel = computed(() => {
  const labels: Record<string, string> = {
    normal: '正常', online: '在线', alarm: '告警', offline: '离线', maintenance: '维护'
  }
  return labels[deviceStatus.value] || deviceStatus.value
})

const pointOptions = computed(() => aiPoints.value)

const noData = computed(() => {
  if (aiPoints.value.length === 0) return true
  for (const [, data] of trendDataMap.value) {
    if (data.length > 0) return false
  }
  return true
})

// ==================== 方法 ====================

function getPointColor(pointId: number): string {
  const idx = aiPoints.value.findIndex(p => p.id === pointId)
  return CHART_COLORS[idx % CHART_COLORS.length]
}

function handleClose() {
  emit('update:visible', false)
}

function togglePoint(pointId: number) {
  const newSet = new Set(selectedPointIds.value)
  if (newSet.has(pointId)) {
    newSet.delete(pointId)
  } else {
    newSet.add(pointId)
  }
  selectedPointIds.value = newSet
  renderChart()
}

async function switchTimeRange(minutes: number) {
  currentRange.value = minutes
  await fetchTrendData()
}

/** 加载设备信息和点位列表 */
async function loadDeviceInfo() {
  try {
    // 尝试将 deviceId 解析为数字 id
    const numericId = parseInt(props.deviceId, 10)
    if (isNaN(numericId)) {
      // deviceId 是字符串编码（如 "A-01"），无法查询历史数据
      deviceName.value = props.deviceId
      deviceType.value = '机柜'
      deviceStatus.value = 'normal'
      aiPoints.value = []
      noDataHint.value = '该设备暂不支持历史数据查看（非数字 ID）'
      return
    }

    const detail = await getDeviceDetail(numericId)
    deviceName.value = detail.device.device_name
    deviceType.value = detail.device.device_type
    deviceStatus.value = detail.device.status
    noDataHint.value = '暂无历史数据'

    // 筛选 AI 类型点位
    aiPoints.value = detail.points.filter(p => p.point_type === 'AI')

    // 默认全选
    selectedPointIds.value = new Set(aiPoints.value.map(p => p.id))
  } catch {
    deviceName.value = props.deviceId
    deviceType.value = '--'
    aiPoints.value = []
  }
}

/** 获取趋势数据 */
async function fetchTrendData() {
  if (aiPoints.value.length === 0) {
    trendDataMap.value = new Map()
    renderChart()
    return
  }

  loading.value = true
  try {
    const results = await Promise.allSettled(
      aiPoints.value.map(async (pt) => {
        const trend = await getPointTrend(pt.id, { duration: currentRange.value })
        return { pointId: pt.id, data: trend }
      })
    )

    const newMap = new Map<number, TrendData[]>()
    for (const result of results) {
      if (result.status === 'fulfilled') {
        newMap.set(result.value.pointId, result.value.data)
      }
    }
    trendDataMap.value = newMap

    // 获取阈值（仅首次）
    if (thresholdMap.value.size === 0) {
      await fetchThresholds()
    }

    await nextTick()
    renderChart()
  } finally {
    loading.value = false
  }
}

/** 获取阈值配置 */
async function fetchThresholds() {
  const results = await Promise.allSettled(
    aiPoints.value.map(async (pt) => {
      const thresholds = await getPointThresholds(pt.id)
      return { pointId: pt.id, thresholds }
    })
  )

  const newMap = new Map<number, ThresholdInfo[]>()
  for (const result of results) {
    if (result.status === 'fulfilled') {
      newMap.set(result.value.pointId, result.value.thresholds)
    }
  }
  thresholdMap.value = newMap
}

/** 渲染 ECharts 趋势图 */
function renderChart() {
  if (!chartRef.value) return

  if (!chartInstance.value) {
    chartInstance.value = echarts.init(chartRef.value, undefined, { renderer: 'canvas' })
  }

  const series: EChartsOption['series'] = []
  const legendData: string[] = []

  // 数据系列
  for (const pt of aiPoints.value) {
    if (!selectedPointIds.value.has(pt.id)) continue

    const data = trendDataMap.value.get(pt.id) || []
    const color = getPointColor(pt.id)
    const name = pt.point_name

    legendData.push(name)
    series.push({
      name,
      type: 'line',
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 2, color },
      itemStyle: { color },
      areaStyle: { color: `${color}15` },
      data: data.map(d => [d.time, d.value])
    })

    // 阈值线和标记区域
    const thresholds = thresholdMap.value.get(pt.id) || []
    for (const th of thresholds) {
      if (!th.is_enabled) continue

      // 阈值虚线
      series.push({
        name: `${name}-${th.threshold_type}`,
        type: 'line',
        symbol: 'none',
        lineStyle: {
          type: 'dashed',
          width: 1,
          color: th.threshold_type.includes('high') ? '#ff4d4f' : '#faad14'
        },
        markLine: {
          silent: true,
          symbol: 'none',
          label: {
            formatter: `${th.threshold_type === 'high_high' ? 'HH' : th.threshold_type === 'high' ? 'H' : th.threshold_type === 'low' ? 'L' : 'LL'} ${th.threshold_value}`,
            color: '#ff4d4f88',
            fontSize: 10
          },
          data: [{ yAxis: th.threshold_value }],
          lineStyle: {
            type: 'dashed',
            color: th.threshold_type.includes('high') ? '#ff4d4f88' : '#faad1488'
          }
        },
        data: []
      })

      // 超阈值区域标记（仅 high 类型）
      if (th.threshold_type.includes('high') && data.length > 0) {
        series.push({
          name: `${name}-area-${th.threshold_type}`,
          type: 'line',
          symbol: 'none',
          lineStyle: { width: 0 },
          areaStyle: { color: 'transparent' },
          markArea: {
            silent: true,
            itemStyle: {
              color: 'rgba(255, 77, 79, 0.08)'
            },
            data: [[
              { yAxis: th.threshold_value },
              { yAxis: Infinity }
            ]]
          },
          data: []
        })
      }
    }
  }

  const option: EChartsOption = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(10, 20, 40, 0.95)',
      borderColor: 'rgba(0, 136, 255, 0.4)',
      textStyle: { color: '#fff', fontSize: 12 },
      axisPointer: {
        type: 'cross',
        lineStyle: { color: 'rgba(0, 136, 255, 0.3)' }
      }
    },
    legend: {
      show: false // 使用自定义点位筛选
    },
    grid: {
      top: 20,
      right: 40,
      bottom: 40,
      left: 60,
      containLabel: false
    },
    xAxis: {
      type: 'time',
      axisLine: { lineStyle: { color: 'rgba(136, 153, 170, 0.3)' } },
      axisTick: { lineStyle: { color: 'rgba(136, 153, 170, 0.3)' } },
      axisLabel: { color: '#8899aa', fontSize: 11 },
      splitLine: { show: false }
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#8899aa', fontSize: 11 },
      splitLine: { lineStyle: { color: 'rgba(136, 153, 170, 0.1)' } }
    },
    series,
    animation: true,
    animationDuration: 600
  }

  chartInstance.value.setOption(option, { notMerge: true })
}

// ==================== 生命周期 ====================

// 监听弹窗打开
watch(() => props.visible, async (val) => {
  if (val) {
    // 注册 ESC 关闭
    document.addEventListener('keydown', handleEsc)

    loading.value = true
    trendDataMap.value = new Map()
    thresholdMap.value = new Map()
    currentRange.value = 1440

    await loadDeviceInfo()
    await nextTick()
    await fetchTrendData()
  } else {
    document.removeEventListener('keydown', handleEsc)
    disposeChart()
  }
})

function handleEsc(e: KeyboardEvent) {
  if (e.key === 'Escape') handleClose()
}

function disposeChart() {
  if (chartInstance.value) {
    chartInstance.value.dispose()
    chartInstance.value = null
  }
}

// resize 处理
function handleResize() {
  chartInstance.value?.resize()
}

watch(() => props.visible, (val) => {
  if (val) {
    window.addEventListener('resize', handleResize)
  } else {
    window.removeEventListener('resize', handleResize)
  }
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleEsc)
  window.removeEventListener('resize', handleResize)
  disposeChart()
})
</script>

<style scoped lang="scss">
.history-dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(4px);
}

.history-dialog {
  width: 90vw;
  height: 85vh;
  max-width: 1400px;
  background: rgba(10, 15, 30, 0.98);
  border: 1px solid rgba(0, 136, 255, 0.3);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow:
    0 0 40px rgba(0, 136, 255, 0.15),
    0 8px 32px rgba(0, 0, 0, 0.6);
}

// 头部
.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: linear-gradient(90deg, rgba(0, 136, 255, 0.12) 0%, transparent 100%);
  border-bottom: 1px solid rgba(0, 136, 255, 0.2);
  flex-shrink: 0;

  .device-info {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .device-name {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    color: #fff;
  }

  .device-type {
    font-size: 12px;
    color: #8899aa;
    padding: 2px 10px;
    background: rgba(136, 153, 170, 0.15);
    border-radius: 10px;
  }

  .device-status {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;

    .status-dot {
      display: inline-block;
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #00ff88;
    }

    &.normal, &.online {
      color: #00ff88;
      .status-dot { background: #00ff88; }
    }
    &.alarm {
      color: #ff4d4f;
      .status-dot { background: #ff4d4f; animation: blink 1s infinite; }
    }
    &.offline {
      color: #666;
      .status-dot { background: #666; }
    }
    &.maintenance {
      color: #faad14;
      .status-dot { background: #faad14; }
    }
  }

  .close-btn {
    background: none;
    border: none;
    color: #8899aa;
    cursor: pointer;
    padding: 8px;
    border-radius: 6px;
    transition: all 0.2s;
    display: flex;
    align-items: center;

    &:hover {
      background: rgba(255, 255, 255, 0.1);
      color: #fff;
    }
  }
}

// 工具栏
.dialog-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
  flex-wrap: wrap;
  gap: 12px;

  .time-range-group {
    display: flex;
    gap: 4px;
    background: rgba(255, 255, 255, 0.04);
    border-radius: 6px;
    padding: 2px;

    .range-btn {
      padding: 6px 16px;
      border: none;
      border-radius: 4px;
      background: transparent;
      color: #8899aa;
      font-size: 13px;
      cursor: pointer;
      transition: all 0.2s;

      &:hover {
        color: #fff;
        background: rgba(0, 136, 255, 0.15);
      }

      &.active {
        color: #fff;
        background: rgba(0, 136, 255, 0.35);
        box-shadow: 0 0 8px rgba(0, 136, 255, 0.2);
      }
    }
  }

  .point-filter {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;

    .filter-label {
      font-size: 13px;
      color: #8899aa;
    }

    .point-checkbox {
      display: flex;
      align-items: center;
      gap: 6px;
      cursor: pointer;
      font-size: 12px;
      color: #aab;

      input[type="checkbox"] {
        display: none;
      }

      .point-color {
        width: 10px;
        height: 10px;
        border-radius: 2px;
        opacity: 0.4;
        transition: opacity 0.2s;
      }

      input:checked ~ .point-color {
        opacity: 1;
      }

      input:checked ~ .point-label {
        color: #ddd;
      }

      .point-label {
        transition: color 0.2s;
      }

      &:hover .point-label {
        color: #fff;
      }
    }
  }
}

// 图表区域
.dialog-body {
  flex: 1;
  padding: 16px 24px 24px;
  min-height: 0;
  position: relative;

  .trend-chart {
    width: 100%;
    height: 100%;
  }

  .loading-state,
  .empty-state {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    color: #8899aa;
    font-size: 14px;
  }

  .spin-icon {
    animation: spin 1s linear infinite;
  }
}

// 动画
.history-dialog-enter-active,
.history-dialog-leave-active {
  transition: opacity 0.3s ease;

  .history-dialog {
    transition: transform 0.3s ease, opacity 0.3s ease;
  }
}

.history-dialog-enter-from,
.history-dialog-leave-to {
  opacity: 0;

  .history-dialog {
    transform: scale(0.95);
    opacity: 0;
  }
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
