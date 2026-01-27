<template>
  <el-card shadow="hover" class="load-comparison-chart">
    <template #header>
      <div class="card-header">
        <span>负荷转移前后对比</span>
        <div class="header-controls">
          <el-radio-group v-model="dataRange" size="small" @change="handleRangeChange">
            <el-radio-button label="1day">1天</el-radio-button>
            <el-radio-button label="7day">7天平均</el-radio-button>
          </el-radio-group>
          <el-radio-group v-model="timeGranularity" size="small" style="margin-left: 12px;">
            <el-radio-button label="1h">1小时</el-radio-button>
            <el-radio-button label="15min">15分钟</el-radio-button>
          </el-radio-group>
        </div>
      </div>
    </template>

    <!-- 图表容器 - 始终保持在DOM中，使用loading遮罩 -->
    <div ref="chartRef" class="chart-container" v-show="hasValidData" v-loading="loading" element-loading-text="加载中..." element-loading-background="rgba(0, 0, 0, 0.6)"></div>

    <!-- 空状态 - 只在没有数据且不在加载时显示 -->
    <div v-if="!hasValidData && !loading" class="empty-state">
      <el-empty :image-size="80">
        <template #description>
          <div v-if="!hasShiftRules">请先选择设备并配置转移规则</div>
          <div v-else>正在加载负荷数据...</div>
        </template>
      </el-empty>
    </div>

    <!-- 时段图例 -->
    <div class="period-legend" v-if="hasValidData">
      <div class="legend-section">
        <span class="legend-title">曲线:</span>
        <span class="legend-item"><span class="line-dot current"></span>转移前负荷</span>
        <span class="legend-item"><span class="line-dot shifted"></span>转移后负荷</span>
      </div>
      <div class="legend-section">
        <span class="legend-title">时段:</span>
        <span class="legend-item"><span class="period-dot sharp"></span>尖峰</span>
        <span class="legend-item"><span class="period-dot peak"></span>峰时</span>
        <span class="legend-item"><span class="period-dot flat"></span>平时</span>
        <span class="legend-item"><span class="period-dot valley"></span>谷时</span>
        <span class="legend-item"><span class="period-dot deep-valley"></span>深谷</span>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick, computed } from 'vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'

// 转移规则类型
interface ShiftRule {
  sourcePeriod: string
  targetPeriod: string
  power: number
  hours: number
}

// 设备规则类型
interface DeviceRules {
  deviceId: number
  deviceName: string
  rules: ShiftRule[]
}

const props = defineProps<{
  deviceRules: DeviceRules[]  // 所有设备的转移规则
  pricingPeriods?: {          // 电价时段配置
    sharp?: number[]
    peak?: number[]
    flat?: number[]
    valley?: number[]
    deep_valley?: number[]
  }
}>()

const emit = defineEmits<{
  (e: 'range-change', range: string): void
}>()

const chartRef = ref<HTMLElement>()
let chartInstance: echarts.ECharts | null = null
let resizeObserver: ResizeObserver | null = null

const dataRange = ref<'1day' | '7day'>('1day')
const timeGranularity = ref<'1h' | '15min'>('1h')
const loading = ref(false)
const loadData = ref<number[]>([])

// 默认时段配置（小时数）
const defaultPeriods = {
  sharp: [11, 18],           // 尖峰: 11:00-12:00, 18:00-19:00
  peak: [9, 10, 17, 19, 20], // 峰时
  flat: [8, 13, 14, 15, 16, 21], // 平时
  valley: [22, 23, 6, 7],    // 谷时
  deep_valley: [0, 1, 2, 3, 4, 5] // 深谷
}

// 时段颜色配置
const periodColors: Record<string, string> = {
  sharp: 'rgba(114, 46, 209, 0.25)',      // 紫色 - 尖峰
  peak: 'rgba(245, 108, 108, 0.25)',       // 红色 - 峰时
  flat: 'rgba(250, 173, 20, 0.20)',        // 黄色 - 平时
  valley: 'rgba(103, 194, 58, 0.25)',      // 绿色 - 谷时
  deep_valley: 'rgba(64, 158, 255, 0.25)'  // 蓝色 - 深谷
}

const periodNames: Record<string, string> = {
  sharp: '尖峰',
  peak: '峰时',
  flat: '平时',
  valley: '谷时',
  deep_valley: '深谷'
}

// 电价配置（元/kWh）
const periodPrices: Record<string, number> = {
  sharp: 1.40,
  peak: 1.00,
  flat: 0.65,
  valley: 0.35,
  deep_valley: 0.20
}

// 判断某小时属于哪个时段
function getHourPeriod(hour: number): string {
  const periods = props.pricingPeriods || defaultPeriods
  if (periods.sharp?.includes(hour)) return 'sharp'
  if (periods.peak?.includes(hour)) return 'peak'
  if (periods.flat?.includes(hour)) return 'flat'
  if (periods.valley?.includes(hour)) return 'valley'
  if (periods.deep_valley?.includes(hour)) return 'deep_valley'
  return 'flat'
}

// 是否有有效的转移规则
const hasShiftRules = computed(() => {
  const result = props.deviceRules && props.deviceRules.length > 0 &&
    props.deviceRules.some(d => d.rules && d.rules.length > 0 && d.rules.some(r => r.power > 0))
  console.log('[LoadComparisonChart] hasShiftRules:', result, 'deviceRules:', props.deviceRules)
  return result
})

// 是否有有效数据可展示 - 只要有负荷数据就可以显示
const hasValidData = computed(() => {
  return loadData.value.length > 0
})

// 生成时间点数量
const timePointCount = computed(() => {
  return timeGranularity.value === '15min' ? 96 : 24
})

// 生成X轴时间标签
function generateTimeLabels(): string[] {
  const labels: string[] = []
  const count = timePointCount.value

  if (count === 96) {
    // 15分钟间隔
    for (let i = 0; i < 96; i++) {
      const hour = Math.floor(i / 4)
      const minute = (i % 4) * 15
      labels.push(`${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`)
    }
  } else {
    // 1小时间隔
    for (let i = 0; i < 24; i++) {
      labels.push(`${i.toString().padStart(2, '0')}:00`)
    }
  }

  return labels
}

// 生成模拟负荷数据（基于时段特征）
function generateMockLoadData(): number[] {
  const count = timePointCount.value
  const data: number[] = []

  // 基础负荷 (kW)
  const baseLoad = 450

  for (let i = 0; i < count; i++) {
    const hour = count === 96 ? Math.floor(i / 4) : i
    const period = getHourPeriod(hour)

    // 根据时段设置负荷因子
    let loadFactor = 1.0
    switch (period) {
      case 'sharp':
        loadFactor = 1.35 + Math.random() * 0.1  // 尖峰负荷最高
        break
      case 'peak':
        loadFactor = 1.20 + Math.random() * 0.08
        break
      case 'flat':
        loadFactor = 0.90 + Math.random() * 0.06
        break
      case 'valley':
        loadFactor = 0.65 + Math.random() * 0.05
        break
      case 'deep_valley':
        loadFactor = 0.45 + Math.random() * 0.05
        break
    }

    // 添加一些平滑的波动
    const timeWave = Math.sin(i / count * Math.PI * 2) * 0.03

    data.push(baseLoad * (loadFactor + timeWave))
  }

  // 如果是7天平均，稍微平滑一下数据
  if (dataRange.value === '7day') {
    for (let i = 1; i < data.length - 1; i++) {
      data[i] = (data[i - 1] + data[i] + data[i + 1]) / 3
    }
  }

  return data
}

// 计算转移后的负荷数据
function calculateShiftedLoadData(originalData: number[]): number[] {
  const shiftedData = [...originalData]
  const count = timePointCount.value
  const pointsPerHour = count === 96 ? 4 : 1

  if (!props.deviceRules || props.deviceRules.length === 0) {
    return shiftedData
  }

  // 遍历所有设备的所有规则
  for (const deviceRule of props.deviceRules) {
    if (!deviceRule.rules) continue

    for (const rule of deviceRule.rules) {
      if (!rule.power || rule.power <= 0) continue

      // 找出源时段和目标时段的时间点
      const sourceIndices: number[] = []
      const targetIndices: number[] = []

      for (let i = 0; i < count; i++) {
        const hour = count === 96 ? Math.floor(i / 4) : i
        const period = getHourPeriod(hour)

        if (period === rule.sourcePeriod) {
          sourceIndices.push(i)
        }
        if (period === rule.targetPeriod) {
          targetIndices.push(i)
        }
      }

      // 计算需要转移的时间点数量
      const hoursToShift = rule.hours || 1
      const pointsToShift = hoursToShift * pointsPerHour

      // 从源时段减少功率
      const sourcePowerPerPoint = rule.power
      for (let i = 0; i < Math.min(pointsToShift, sourceIndices.length); i++) {
        const idx = sourceIndices[i]
        shiftedData[idx] = Math.max(0, shiftedData[idx] - sourcePowerPerPoint)
      }

      // 向目标时段增加功率
      for (let i = 0; i < Math.min(pointsToShift, targetIndices.length); i++) {
        const idx = targetIndices[i]
        shiftedData[idx] += sourcePowerPerPoint
      }
    }
  }

  return shiftedData
}

// 生成时段背景区域标记
function generatePeriodMarkAreas(): any[] {
  const areas: any[] = []
  const periods = props.pricingPeriods || defaultPeriods
  const count = timePointCount.value

  // 收集每个时段的连续区间
  const periodRanges: Record<string, [number, number][]> = {
    sharp: [],
    peak: [],
    flat: [],
    valley: [],
    deep_valley: []
  }

  // 按时段分组时间点
  for (const [period, hours] of Object.entries(periods) as [string, number[]][]) {
    if (!hours || hours.length === 0) continue

    const sortedHours = [...hours].sort((a, b) => a - b)

    // 处理跨日情况（如 22, 23, 0, 1, 2...）
    let rangeStart = sortedHours[0]
    let rangeEnd = sortedHours[0]

    for (let i = 1; i < sortedHours.length; i++) {
      if (sortedHours[i] === rangeEnd + 1) {
        rangeEnd = sortedHours[i]
      } else {
        periodRanges[period].push([rangeStart, rangeEnd])
        rangeStart = sortedHours[i]
        rangeEnd = sortedHours[i]
      }
    }
    periodRanges[period].push([rangeStart, rangeEnd])
  }

  // 转换为X轴坐标
  for (const [period, ranges] of Object.entries(periodRanges)) {
    for (const [startHour, endHour] of ranges) {
      let xStart: number | string
      let xEnd: number | string

      if (count === 96) {
        // 15分钟粒度
        xStart = startHour * 4
        xEnd = (endHour + 1) * 4 - 1
      } else {
        // 1小时粒度
        xStart = startHour
        xEnd = endHour
      }

      areas.push([
        {
          xAxis: xStart,
          itemStyle: {
            color: periodColors[period]
          }
        },
        {
          xAxis: xEnd
        }
      ])
    }
  }

  return areas
}

// 计算节省金额
function calculateSavingAtPoint(originalPower: number, shiftedPower: number, hour: number): number {
  const period = getHourPeriod(hour)
  const price = periodPrices[period] || 0
  const powerDiff = originalPower - shiftedPower
  return powerDiff * price / 1000 // 转换为kWh节省
}

// 渲染图表
function renderChart() {
  console.log('[LoadComparisonChart] renderChart called, chartRef:', !!chartRef.value, 'loadData.length:', loadData.value.length)

  if (!chartRef.value) {
    console.log('[LoadComparisonChart] chartRef not ready, will retry')
    setTimeout(() => {
      if (chartRef.value && loadData.value.length > 0) {
        renderChart()
      }
    }, 100)
    return
  }

  if (loadData.value.length === 0) {
    console.log('[LoadComparisonChart] No data to render')
    return
  }

  // 确保图表实例存在且有效
  if (!chartInstance || chartInstance.isDisposed()) {
    chartInstance = echarts.init(chartRef.value)
  }

  const timeLabels = generateTimeLabels()
  const originalData = loadData.value
  const shiftedData = calculateShiftedLoadData(originalData)
  const count = timePointCount.value

  // 计算差异数据
  const diffData = originalData.map((orig, i) => orig - shiftedData[i])

  const option: EChartsOption = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(0, 0, 0, 0.85)',
      borderColor: 'rgba(255, 255, 255, 0.1)',
      textStyle: { color: '#fff', fontSize: 12 },
      formatter: (params: any) => {
        if (!params || params.length === 0) return ''

        const dataIndex = params[0]?.dataIndex
        const time = params[0]?.axisValue || ''
        const hour = count === 96 ? Math.floor(dataIndex / 4) : dataIndex
        const period = getHourPeriod(hour)
        const periodName = periodNames[period] || period
        const periodPrice = periodPrices[period] || 0

        let html = `<div style="font-weight: 600; margin-bottom: 8px; font-size: 13px;">${time} <span style="color: ${periodColors[period].replace('0.25', '0.9')}; background: ${periodColors[period]}; padding: 2px 6px; border-radius: 3px; font-size: 11px;">${periodName} ¥${periodPrice.toFixed(2)}/kWh</span></div>`

        // 转移前负荷
        const origValue = originalData[dataIndex]
        const shiftValue = shiftedData[dataIndex]
        const diff = origValue - shiftValue

        html += `<div style="display: flex; justify-content: space-between; margin-bottom: 4px;"><span><span style="display: inline-block; width: 10px; height: 10px; background: #409eff; border-radius: 50%; margin-right: 6px;"></span>转移前负荷:</span><span style="font-weight: 600;">${origValue.toFixed(1)} kW</span></div>`
        html += `<div style="display: flex; justify-content: space-between; margin-bottom: 4px;"><span><span style="display: inline-block; width: 10px; height: 10px; background: #67c23a; border-radius: 50%; margin-right: 6px;"></span>转移后负荷:</span><span style="font-weight: 600;">${shiftValue.toFixed(1)} kW</span></div>`

        // 差异
        if (Math.abs(diff) > 0.1) {
          const diffColor = diff > 0 ? '#67c23a' : '#f56c6c'
          const diffLabel = diff > 0 ? '减少' : '增加'
          html += `<div style="border-top: 1px solid rgba(255,255,255,0.1); margin-top: 6px; padding-top: 6px; display: flex; justify-content: space-between;"><span>功率变化:</span><span style="color: ${diffColor}; font-weight: 600;">${diffLabel} ${Math.abs(diff).toFixed(1)} kW</span></div>`
        }

        return html
      }
    },
    grid: {
      top: 30,
      right: 40,
      bottom: 50,
      left: 60
    },
    xAxis: {
      type: 'category',
      data: timeLabels,
      axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.2)' } },
      axisLabel: {
        color: 'rgba(255, 255, 255, 0.65)',
        fontSize: 10,
        interval: count === 96 ? 7 : 1,
        rotate: count === 96 ? 45 : 0
      },
      splitLine: { show: false }
    },
    yAxis: {
      type: 'value',
      name: '功率 (kW)',
      nameTextStyle: { color: 'rgba(255, 255, 255, 0.65)', fontSize: 12 },
      axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.2)' } },
      axisLabel: { color: 'rgba(255, 255, 255, 0.65)', fontSize: 11 },
      splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.08)', type: 'dashed' } }
    },
    series: [
      {
        name: '转移前负荷',
        type: 'line',
        data: originalData,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#409eff', width: 2.5 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(64, 158, 255, 0.25)' },
            { offset: 1, color: 'rgba(64, 158, 255, 0.02)' }
          ])
        },
        markArea: {
          silent: true,
          data: generatePeriodMarkAreas()
        },
        z: 2
      },
      {
        name: '转移后负荷',
        type: 'line',
        data: shiftedData,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#67c23a', width: 2.5, type: 'dashed' },
        z: 3
      },
      {
        name: '功率差异',
        type: 'bar',
        data: diffData.map(d => ({
          value: d,
          itemStyle: {
            color: d > 0.1
              ? 'rgba(103, 194, 58, 0.4)'   // 减少 = 绿色
              : d < -0.1
                ? 'rgba(245, 108, 108, 0.4)' // 增加 = 红色
                : 'transparent'
          }
        })),
        barWidth: count === 96 ? '60%' : '40%',
        z: 1
      }
    ]
  }

  chartInstance.setOption(option, true)
}

// 加载数据
async function loadLoadData() {
  console.log('[LoadComparisonChart] loadLoadData called')
  loading.value = true

  // 模拟API调用延迟
  await new Promise(resolve => setTimeout(resolve, 200))

  // 生成模拟数据
  loadData.value = generateMockLoadData()
  console.log('[LoadComparisonChart] loadData generated, length:', loadData.value.length)

  loading.value = false

  // 等待DOM更新后再渲染图表
  await nextTick()
  renderChart()
}

// 数据范围变化
function handleRangeChange() {
  emit('range-change', dataRange.value)
  loadLoadData()
}

// 监听props变化 - 使用getter函数确保正确监听
watch(
  () => props.deviceRules,
  async (newRules) => {
    console.log('[LoadComparisonChart] deviceRules changed:', newRules?.length, 'devices')
    if (newRules && newRules.length > 0) {
      await loadLoadData()
    }
  },
  { deep: true }
)

// 监听时间粒度变化
watch(
  () => timeGranularity.value,
  async () => {
    if (hasShiftRules.value) {
      await loadLoadData()
    }
  }
)

onMounted(async () => {
  console.log('[LoadComparisonChart] onMounted, deviceRules:', props.deviceRules?.length)
  await nextTick()

  // 设置ResizeObserver - chartRef使用v-show所以应该始终存在
  if (chartRef.value) {
    resizeObserver = new ResizeObserver(() => {
      if (chartInstance && !chartInstance.isDisposed()) {
        chartInstance.resize()
      }
    })
    resizeObserver.observe(chartRef.value)
  }

  // 初始加载数据
  await loadLoadData()
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  chartInstance?.dispose()
})
</script>

<style scoped lang="scss">
.load-comparison-chart {
  margin-top: 20px;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
  }

  .header-controls {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .chart-container {
    height: 350px;
    width: 100%;
    min-height: 350px;
  }

  .empty-state {
    height: 350px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .period-legend {
    margin-top: 16px;
    padding-top: 12px;
    border-top: 1px solid var(--border-color);
    display: flex;
    flex-wrap: wrap;
    gap: 20px;

    .legend-section {
      display: flex;
      align-items: center;
      gap: 12px;

      .legend-title {
        font-size: 12px;
        color: var(--text-secondary);
      }

      .legend-item {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 11px;
        color: var(--text-secondary);

        .line-dot {
          width: 12px;
          height: 3px;
          border-radius: 1px;

          &.current {
            background: #409eff;
          }

          &.shifted {
            background: #67c23a;
            background: repeating-linear-gradient(
              90deg,
              #67c23a 0px,
              #67c23a 4px,
              transparent 4px,
              transparent 6px
            );
          }
        }

        .period-dot {
          width: 12px;
          height: 12px;
          border-radius: 2px;

          &.sharp {
            background: rgba(114, 46, 209, 0.6);
          }

          &.peak {
            background: rgba(245, 108, 108, 0.6);
          }

          &.flat {
            background: rgba(250, 173, 20, 0.5);
          }

          &.valley {
            background: rgba(103, 194, 58, 0.6);
          }

          &.deep-valley {
            background: rgba(64, 158, 255, 0.6);
          }
        }
      }
    }
  }
}
</style>
