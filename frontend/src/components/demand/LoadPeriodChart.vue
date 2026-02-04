<template>
  <div class="load-period-chart">
    <div class="chart-header">
      <div class="title-group">
        <span class="title">24小时负荷分布</span>
        <span class="subtitle" v-if="meterPointName">{{ meterPointName }}</span>
        <el-tag v-if="isMockData" type="warning" size="small" class="mock-badge">
          演示数据
        </el-tag>
      </div>
      <div class="header-info">
        <span class="date">{{ date || '昨日' }}</span>
        <el-link type="primary" @click="goToFullAnalysis">
          查看详细分析 →
        </el-link>
      </div>
    </div>

    <div class="chart-container" v-loading="loading">
      <div ref="chartRef" style="height: 240px; width: 100%"></div>
    </div>

    <div class="period-summary" v-if="data">
      <div class="summary-item peak">
        <span class="label">峰时</span>
        <span class="value">{{ getSummary('peak')?.avg_power || 0 }} kW</span>
        <span class="hours">{{ getSummary('peak')?.hours || 0 }}h</span>
      </div>
      <div class="summary-item valley">
        <span class="label">谷时</span>
        <span class="value">{{ getSummary('valley')?.avg_power || 0 }} kW</span>
        <span class="hours">{{ getSummary('valley')?.hours || 0 }}h</span>
      </div>
      <div class="summary-item shiftable" v-if="data.shiftable_power > 0">
        <span class="label">可转移</span>
        <span class="value highlight">{{ data.shiftable_power }} kW</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick, computed } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'
import { getLoadPeriodDistribution, type LoadPeriodData, type PeriodSummary } from '@/api/modules/demand'

const props = withDefaults(
  defineProps<{
    meterPointId?: number
    meterPointName?: string
    date?: string
    showPricing?: boolean
    highlightPeriods?: string[]
  }>(),
  {
    showPricing: true,
    highlightPeriods: () => []
  }
)

const router = useRouter()
const loading = ref(false)
const data = ref<LoadPeriodData | null>(null)
const chartRef = ref<HTMLElement>()
const isMockData = ref(false)

let chartInstance: echarts.ECharts | null = null
let resizeObserver: ResizeObserver | null = null

const meterPointName = computed(() => {
  if (props.meterPointName) return props.meterPointName
  if (!props.meterPointId) return '全站总负荷'
  return `计量点 #${props.meterPointId}`
})

const periodColors: Record<string, string> = {
  sharp: '#722ed1',
  peak: '#f5222d',
  flat: '#faad14',
  valley: '#52c41a',
  deep_valley: '#1890ff'
}

// 模拟数据基础功率配置 (kW)
const MOCK_BASE_POWER_KW = {
  deep_valley: 380,
  valley: 450,
  flat: 550,
  peak: 680,
  sharp: 750
} as const

const POWER_RANDOM_VARIANCE_KW = 60
const SHIFTABLE_LOAD_RATIO = 0.5

onMounted(() => {
  loadData()
})

onUnmounted(() => {
  cleanup()
})

watch(() => [props.meterPointId, props.date], () => {
  loadData()
})

function cleanup() {
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
}

async function applyMockDataFallback() {
  isMockData.value = true
  generateMockData()
  await nextTick()
  renderChart()
}

async function loadData() {
  loading.value = true
  isMockData.value = false
  try {
    const res = await getLoadPeriodDistribution({
      meterPointId: props.meterPointId,
      date: props.date
    })
    if (res.code === 0 && res.data && res.data.hourly_data && res.data.hourly_data.length > 0) {
      data.value = res.data
      await nextTick()
      renderChart()
    } else {
      await applyMockDataFallback()
    }
  } catch {
    await applyMockDataFallback()
  } finally {
    loading.value = false
  }
}

function generateMockData() {
  const periodMap: Record<number, 'sharp' | 'peak' | 'flat' | 'valley' | 'deep_valley'> = {
    0: 'deep_valley', 1: 'deep_valley', 2: 'deep_valley', 3: 'deep_valley',
    4: 'valley', 5: 'valley', 6: 'valley', 7: 'valley',
    8: 'flat', 9: 'peak', 10: 'peak', 11: 'sharp',
    12: 'peak', 13: 'flat', 14: 'flat', 15: 'flat',
    16: 'flat', 17: 'peak', 18: 'sharp', 19: 'peak',
    20: 'peak', 21: 'flat', 22: 'valley', 23: 'valley'
  }

  // 使用确定性波动代替 Math.random()
  const hourlyData = Array.from({ length: 24 }, (_, hour) => {
    const period = periodMap[hour]
    const basePower = MOCK_BASE_POWER_KW[period]
    // 使用正弦波生成确定性波动
    const deterministicVariation = Math.sin(hour * 0.5) * (POWER_RANDOM_VARIANCE_KW / 2)
    return {
      hour,
      power: Math.round(basePower + deterministicVariation),
      period
    }
  })

  const periodSummary: Record<string, PeriodSummary> = {}
  for (const period of ['sharp', 'peak', 'flat', 'valley', 'deep_valley'] as const) {
    const periodData = hourlyData.filter(d => d.period === period)
    if (periodData.length > 0) {
      const totalPower = periodData.reduce((sum, d) => sum + d.power, 0)
      periodSummary[period] = {
        total_kwh: Math.round(totalPower),
        avg_power: Math.round(totalPower / periodData.length),
        hours: periodData.length
      }
    }
  }

  const peakAvg = MOCK_BASE_POWER_KW.peak
  const valleyAvg = MOCK_BASE_POWER_KW.valley

  data.value = {
    date: props.date || new Date().toISOString().split('T')[0],
    hourly_data: hourlyData,
    period_summary: periodSummary,
    shiftable_power: Math.round((peakAvg - valleyAvg) * SHIFTABLE_LOAD_RATIO)
  }
}

function renderChart() {
  if (!chartRef.value || !data.value) return

  try {
    cleanup()

    chartInstance = echarts.init(chartRef.value)

    const hours = data.value.hourly_data.map(d => d.hour)
    const powers = data.value.hourly_data.map(d => d.power)
    const periods = data.value.hourly_data.map(d => d.period)

    const option: EChartsOption = {
      grid: {
        top: 30,
        right: 20,
        bottom: 40,
        left: 50
      },
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const point = params[0]
          const period = periods[point.dataIndex]
          const periodName: Record<string, string> = {
            sharp: '尖峰',
            peak: '峰时',
            flat: '平时',
            valley: '谷时',
            deep_valley: '深谷'
          }
          return `${point.axisValue}时<br/>负荷: ${point.value} kW<br/>时段: ${periodName[period] || period}`
        }
      },
      xAxis: {
        type: 'category',
        data: hours,
        name: '时刻',
        nameTextStyle: {
          color: 'rgba(255, 255, 255, 0.65)'
        },
        axisLabel: {
          color: 'rgba(255, 255, 255, 0.65)',
          fontSize: 11,
          formatter: '{value}:00'
        },
        axisLine: {
          lineStyle: {
            color: 'rgba(255, 255, 255, 0.15)'
          }
        }
      },
      yAxis: {
        type: 'value',
        name: 'kW',
        nameTextStyle: {
          color: 'rgba(255, 255, 255, 0.65)'
        },
        axisLabel: {
          color: 'rgba(255, 255, 255, 0.65)',
          fontSize: 11
        },
        splitLine: {
          lineStyle: {
            color: 'rgba(255, 255, 255, 0.1)'
          }
        }
      },
      series: [
        {
          name: '负荷',
          type: 'bar',
          data: powers.map((power, idx) => {
            const period = periods[idx]
            const baseColor = periodColors[period] || '#1890ff'
            const shouldHighlight = props.highlightPeriods.length === 0 || props.highlightPeriods.includes(period)
            return {
              value: power,
              itemStyle: {
                color: baseColor,
                opacity: shouldHighlight ? 1 : 0.4
              }
            }
          }),
          barWidth: '60%'
        }
      ]
    }

    chartInstance.setOption(option)

    resizeObserver = new ResizeObserver(() => {
      chartInstance?.resize()
    })
    resizeObserver.observe(chartRef.value)
  } catch {
    // Chart rendering failed silently
  }
}

function getSummary(period: string) {
  return data.value?.period_summary[period]
}

function goToFullAnalysis() {
  router.push('/energy/analysis?tab=shift')
}
</script>

<style scoped lang="scss">
.load-period-chart {
  background: var(--bg-card-solid, #1a2a4a);
  border-radius: 8px;
  padding: 12px;

  .chart-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;

    .title-group {
      display: flex;
      flex-direction: column;
      gap: 4px;

      .title {
        font-size: 14px;
        font-weight: 600;
        color: var(--text-primary, rgba(255, 255, 255, 0.95));
      }

      .subtitle {
        font-size: 11px;
        color: var(--text-secondary, rgba(255, 255, 255, 0.65));
      }

      .mock-badge {
        align-self: flex-start;
        margin-top: 4px;
      }
    }

    .title {
      font-size: 13px;
      font-weight: 600;
      color: var(--text-primary, rgba(255, 255, 255, 0.95));
    }

    .header-info {
      display: flex;
      align-items: center;
      gap: 12px;

      .date {
        font-size: 12px;
        color: var(--text-secondary, rgba(255, 255, 255, 0.65));
      }
    }
  }

  .period-summary {
    display: flex;
    gap: 20px;
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid rgba(255, 255, 255, 0.1);

    .summary-item {
      display: flex;
      flex-direction: column;
      gap: 4px;
      flex: 1;

      .label {
        font-size: 12px;
        color: var(--text-secondary, rgba(255, 255, 255, 0.65));
      }

      .value {
        font-size: 16px;
        font-weight: 600;
        color: var(--text-primary, rgba(255, 255, 255, 0.95));

        &.highlight {
          color: var(--primary-color, #1890ff);
        }
      }

      .hours {
        font-size: 11px;
        color: var(--text-secondary, rgba(255, 255, 255, 0.45));
      }

      &.peak .value {
        color: #f5222d;
      }

      &.valley .value {
        color: #52c41a;
      }
    }
  }
}
</style>
