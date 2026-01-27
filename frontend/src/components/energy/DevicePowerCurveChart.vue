<template>
  <div class="device-power-curve-chart" ref="containerRef">
    <div class="chart-header">
      <span class="chart-title">{{ deviceName }} 功率曲线</span>
      <el-switch
        v-model="showComparison"
        active-text="显示调整后"
        inactive-text="仅显示当前"
        size="small"
      />
    </div>
    <div ref="chartRef" class="chart-container"></div>
    <div class="chart-legend">
      <div class="legend-item">
        <span class="legend-dot sharp"></span>
        <span>尖峰</span>
      </div>
      <div class="legend-item">
        <span class="legend-dot peak"></span>
        <span>峰时</span>
      </div>
      <div class="legend-item">
        <span class="legend-dot flat"></span>
        <span>平时</span>
      </div>
      <div class="legend-item">
        <span class="legend-dot valley"></span>
        <span>谷时</span>
      </div>
      <div class="legend-item">
        <span class="legend-dot deep-valley"></span>
        <span>深谷</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'

interface ShiftRule {
  sourcePeriod: string
  targetPeriod: string
  power: number
  hours: number
}

const props = defineProps<{
  deviceName: string
  devicePower: number  // 设备额定功率
  shiftRules: ShiftRule[]  // 转移规则列表
  pricingPeriods?: {  // 电价时段配置
    sharp?: number[]
    peak?: number[]
    flat?: number[]
    valley?: number[]
    deep_valley?: number[]
  }
}>()

const chartRef = ref<HTMLElement>()
const containerRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null
const showComparison = ref(true)
let resizeObserver: ResizeObserver | null = null
let initRetryCount = 0
const MAX_RETRY = 10

// 默认时段配置
const defaultPeriods = {
  sharp: [11, 18],
  peak: [9, 10, 17, 19, 20],
  flat: [8, 13, 14, 15, 16, 21],
  valley: [22, 23, 6, 7],
  deep_valley: [0, 1, 2, 3, 4, 5]
}

// 获取每小时所属时段
function getHourPeriod(hour: number): string {
  const periods = props.pricingPeriods || defaultPeriods
  if (periods.sharp?.includes(hour)) return 'sharp'
  if (periods.peak?.includes(hour)) return 'peak'
  if (periods.flat?.includes(hour)) return 'flat'
  if (periods.valley?.includes(hour)) return 'valley'
  if (periods.deep_valley?.includes(hour)) return 'deep_valley'
  return 'flat'
}

// 时段颜色映射
const periodColors: Record<string, string> = {
  sharp: '#722ed1',
  peak: '#f5222d',
  flat: '#faad14',
  valley: '#52c41a',
  deep_valley: '#1890ff'
}

// 生成24小时功率数据
function generateMockPowerData(): number[] {
  const data: number[] = []
  const basePower = Math.max(props.devicePower || 100, 10) * 0.6

  for (let hour = 0; hour < 24; hour++) {
    const period = getHourPeriod(hour)
    let powerFactor = 1.0

    switch (period) {
      case 'sharp':
        powerFactor = 1.2
        break
      case 'peak':
        powerFactor = 1.1
        break
      case 'valley':
        powerFactor = 0.7
        break
      case 'deep_valley':
        powerFactor = 0.5
        break
      default:
        powerFactor = 0.9
    }

    // 固定的波动因子（基于小时，保证一致性）
    const randomFactor = 0.9 + (Math.sin(hour * 0.5) * 0.1 + 0.1)
    data.push(basePower * powerFactor * randomFactor)
  }

  return data
}

// 计算调整后的功率数据
function calculateAdjustedPowerData(originalData: number[]): number[] {
  const adjustedData = [...originalData]

  for (const rule of props.shiftRules) {
    const { sourcePeriod, targetPeriod, power, hours } = rule

    const sourceHours: number[] = []
    const targetHours: number[] = []

    for (let hour = 0; hour < 24; hour++) {
      const period = getHourPeriod(hour)
      if (period === sourcePeriod) sourceHours.push(hour)
      if (period === targetPeriod) targetHours.push(hour)
    }

    const hoursToShift = Math.min(hours, sourceHours.length)
    for (let i = 0; i < hoursToShift && i < sourceHours.length; i++) {
      adjustedData[sourceHours[i]] = Math.max(0, adjustedData[sourceHours[i]] - power)
    }

    const hoursToAdd = Math.min(hours, targetHours.length)
    for (let i = 0; i < hoursToAdd && i < targetHours.length; i++) {
      adjustedData[targetHours[i]] += power
    }
  }

  return adjustedData
}

// 生成时段背景区域
function generatePeriodMarkAreas() {
  const areas: any[] = []
  const periods = props.pricingPeriods || defaultPeriods

  const periodRanges: Record<string, number[][]> = {
    sharp: [],
    peak: [],
    flat: [],
    valley: [],
    deep_valley: []
  }

  for (const [period, hours] of Object.entries(periods) as [string, number[]][]) {
    if (!hours || hours.length === 0) continue

    const sortedHours = [...hours].sort((a, b) => a - b)
    let rangeStart = sortedHours[0]
    let rangeEnd = sortedHours[0]

    for (let i = 1; i < sortedHours.length; i++) {
      if (sortedHours[i] === rangeEnd + 1) {
        rangeEnd = sortedHours[i]
      } else {
        periodRanges[period].push([rangeStart, rangeEnd + 1])
        rangeStart = sortedHours[i]
        rangeEnd = sortedHours[i]
      }
    }
    periodRanges[period].push([rangeStart, rangeEnd + 1])
  }

  for (const [period, ranges] of Object.entries(periodRanges)) {
    for (const [start, end] of ranges) {
      areas.push([
        { xAxis: start, itemStyle: { color: periodColors[period], opacity: 0.15 } },
        { xAxis: end }
      ])
    }
  }

  return areas
}

// 尝试初始化图表
function tryInitChart() {
  if (!chartRef.value) {
    if (initRetryCount < MAX_RETRY) {
      initRetryCount++
      setTimeout(tryInitChart, 100)
    }
    return
  }

  const rect = chartRef.value.getBoundingClientRect()
  if (rect.width < 50 || rect.height < 50) {
    if (initRetryCount < MAX_RETRY) {
      initRetryCount++
      setTimeout(tryInitChart, 100)
    }
    return
  }

  initChart()
}

// 初始化图表
function initChart() {
  if (!chartRef.value) return

  if (chart) {
    chart.dispose()
    chart = null
  }

  chart = echarts.init(chartRef.value)
  updateChart()
  window.addEventListener('resize', handleResize)
}

// 更新图表
function updateChart() {
  if (!chart) return

  const originalData = generateMockPowerData()
  const adjustedData = calculateAdjustedPowerData(originalData)
  const hours = Array.from({ length: 24 }, (_, i) => `${i}:00`)

  const series: any[] = [
    {
      name: '当前功率',
      type: 'line',
      data: originalData,
      smooth: true,
      lineStyle: { color: '#1890ff', width: 2 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(24, 144, 255, 0.3)' },
          { offset: 1, color: 'rgba(24, 144, 255, 0.05)' }
        ])
      },
      itemStyle: { color: '#1890ff' },
      markArea: {
        silent: true,
        data: generatePeriodMarkAreas()
      }
    }
  ]

  if (showComparison.value && props.shiftRules.length > 0) {
    series.push({
      name: '调整后功率',
      type: 'line',
      data: adjustedData,
      smooth: true,
      lineStyle: { color: '#52c41a', width: 2, type: 'dashed' },
      itemStyle: { color: '#52c41a' },
      z: 10
    })
  }

  const option: echarts.EChartsOption = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(0, 0, 0, 0.8)',
      borderColor: 'rgba(255, 255, 255, 0.2)',
      textStyle: { color: '#fff' },
      formatter: (params: any) => {
        let result = `<div style="font-weight: bold; margin-bottom: 4px;">${params[0].axisValue}</div>`
        const hour = parseInt(params[0].axisValue)
        const period = getHourPeriod(hour)
        const periodNames: Record<string, string> = {
          sharp: '尖峰', peak: '峰时', flat: '平时', valley: '谷时', deep_valley: '深谷'
        }
        result += `<div style="color: ${periodColors[period]}; margin-bottom: 8px;">时段: ${periodNames[period]}</div>`

        for (const param of params) {
          result += `<div>${param.marker} ${param.seriesName}: ${param.value.toFixed(2)} kW</div>`
        }

        if (params.length === 2) {
          const diff = params[1].value - params[0].value
          const diffColor = diff > 0 ? '#52c41a' : '#f5222d'
          result += `<div style="color: ${diffColor}; margin-top: 4px;">差异: ${diff > 0 ? '+' : ''}${diff.toFixed(2)} kW</div>`
        }

        return result
      }
    },
    legend: {
      data: showComparison.value && props.shiftRules.length > 0
        ? ['当前功率', '调整后功率']
        : ['当前功率'],
      top: 0,
      textStyle: { color: 'rgba(255, 255, 255, 0.85)' }
    },
    grid: { left: '50px', right: '20px', top: '40px', bottom: '30px' },
    xAxis: {
      type: 'category',
      data: hours,
      axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.2)' } },
      axisLabel: { color: 'rgba(255, 255, 255, 0.65)', fontSize: 11, interval: 2 },
      splitLine: { show: true, lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } }
    },
    yAxis: {
      type: 'value',
      name: '功率 (kW)',
      nameTextStyle: { color: 'rgba(255, 255, 255, 0.65)', fontSize: 12 },
      axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.2)' } },
      axisLabel: { color: 'rgba(255, 255, 255, 0.65)', fontSize: 11 },
      splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.1)', type: 'dashed' } }
    },
    series
  }

  chart.setOption(option, true)
}

function handleResize() {
  chart?.resize()
}

function setupResizeObserver() {
  if (!containerRef.value) return

  resizeObserver = new ResizeObserver((entries) => {
    for (const entry of entries) {
      const { width, height } = entry.contentRect
      if (width > 50 && height > 50) {
        nextTick(() => {
          if (!chart && chartRef.value) {
            initChart()
          } else if (chart) {
            chart.resize()
          }
        })
      }
    }
  })

  resizeObserver.observe(containerRef.value)
}

// 监听规则变化
watch(() => props.shiftRules, () => {
  nextTick(() => {
    if (chart) {
      updateChart()
    } else {
      tryInitChart()
    }
  })
}, { deep: true })

watch(() => props.devicePower, () => {
  if (chart) updateChart()
})

watch(() => props.deviceName, () => {
  if (chart) updateChart()
})

watch(() => showComparison.value, () => {
  if (chart) updateChart()
})

onMounted(() => {
  nextTick(() => {
    setupResizeObserver()
    // 延迟初始化，等待 collapse transition 完成
    setTimeout(() => {
      tryInitChart()
    }, 50)
  })
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  if (chart) {
    chart.dispose()
    chart = null
  }
})
</script>

<style scoped lang="scss">
.device-power-curve-chart {
  margin-top: 16px;
  padding: 16px;
  background: rgba(0, 0, 0, 0.4);
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.15);

  .chart-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;

    .chart-title {
      font-size: 14px;
      font-weight: 500;
      color: rgba(255, 255, 255, 0.9);
    }
  }

  .chart-container {
    width: 100%;
    height: 220px;
    min-height: 220px;
  }

  .chart-legend {
    display: flex;
    justify-content: center;
    gap: 16px;
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid rgba(255, 255, 255, 0.1);

    .legend-item {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      color: rgba(255, 255, 255, 0.7);

      .legend-dot {
        width: 12px;
        height: 12px;
        border-radius: 2px;

        &.sharp { background: #722ed1; }
        &.peak { background: #f5222d; }
        &.flat { background: #faad14; }
        &.valley { background: #52c41a; }
        &.deep-valley { background: #1890ff; }
      }
    }
  }
}

:deep(.el-switch) {
  .el-switch__label {
    color: rgba(255, 255, 255, 0.65);
    font-size: 11px;
  }

  &.is-checked .el-switch__label--left {
    color: rgba(255, 255, 255, 0.45);
  }

  &:not(.is-checked) .el-switch__label--right {
    color: rgba(255, 255, 255, 0.45);
  }
}
</style>
