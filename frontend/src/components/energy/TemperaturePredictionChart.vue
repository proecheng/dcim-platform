<template>
  <div v-loading="loading" class="temperature-prediction-chart">
    <div v-if="errorMsg" class="chart-error">
      <el-empty :description="errorMsg" />
    </div>
    <template v-else>
      <div class="chart-toolbar">
        <el-button-group size="small">
          <el-button :type="selectedHours === 0.5 ? 'primary' : ''" @click="changeHours(0.5)">0.5h</el-button>
          <el-button :type="selectedHours === 1 ? 'primary' : ''" @click="changeHours(1)">1h</el-button>
          <el-button :type="selectedHours === 2 ? 'primary' : ''" @click="changeHours(2)">2h</el-button>
        </el-button-group>
        <el-tag v-if="modelVersion" size="small" :type="modelVersion === 'TCL' ? 'success' : 'warning'" style="margin-left: 12px">
          {{ modelVersion === 'TCL' ? 'TCL-v1' : 'THM-fallback' }}
        </el-tag>
      </div>
      <div ref="chartRef" style="width: 100%; height: 350px"></div>
    </template>
  </div>
</template>

<script setup lang="ts">
import echarts, { type EChartsOption } from '@/utils/echarts'
import { useDebounceFn } from '@vueuse/core'
import { predictTemperature, getValidationReport } from '@/api/modules/precool'
import type { PredictResponse, ValidationReport } from '@/api/modules/precool'

const props = withDefaults(defineProps<{
  zoneId: number
  zoneName?: string
}>(), {
  zoneName: ''
})

const chartRef = ref<HTMLElement>()
const chartInstance = shallowRef<echarts.ECharts>()
const loading = ref(false)
const errorMsg = ref('')
const selectedHours = ref(1)
const modelVersion = ref('')
const refreshTimer = ref<number>()

// 误差带数据
const errorBand = ref(2.0)
const errorBandColor = ref('rgba(230, 162, 60, 0.2)') // 默认黄色(精度未知)

const fetchValidation = async () => {
  try {
    const res = await getValidationReport(props.zoneId)
    const report = res.data as unknown as ValidationReport
    const mae = report?.mae_1h

    if (mae == null) {
      errorBand.value = 2.0
      errorBandColor.value = 'rgba(230, 162, 60, 0.2)' // 黄色(精度未知)
    } else if (mae < 1.0) {
      errorBand.value = Math.max(mae, 1.0)
      errorBandColor.value = 'rgba(103, 194, 58, 0.2)' // 绿色
    } else if (mae <= 2.0) {
      errorBand.value = mae
      errorBandColor.value = 'rgba(230, 162, 60, 0.2)' // 黄色
    } else {
      errorBand.value = mae
      errorBandColor.value = 'rgba(245, 108, 108, 0.2)' // 红色
    }
  } catch {
    errorBand.value = 2.0
    errorBandColor.value = 'rgba(230, 162, 60, 0.2)'
  }
}

const fetchPrediction = async () => {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await predictTemperature(props.zoneId, { hours: selectedHours.value })
    const data = res.data as unknown as PredictResponse
    if (!data || !data.temperature_trajectory) {
      errorMsg.value = '暂无预测数据'
      return
    }
    modelVersion.value = data.model_version || ''
    renderChart(data)
  } catch {
    errorMsg.value = '预测数据加载失败'
  } finally {
    loading.value = false
  }
}

const renderChart = (data: PredictResponse) => {
  if (!chartInstance.value) return

  const timeSteps = data.time_steps
  const trajectory = data.temperature_trajectory
  const band = errorBand.value

  // 误差带下界数据
  const lowerBound = trajectory.map(v => Math.round((v - band) * 100) / 100)
  // 误差带宽度(上界 - 下界 = 2 * band)
  const bandWidth = trajectory.map(() => Math.round(2 * band * 100) / 100)

  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      renderMode: 'richText',
      formatter: (params: any) => {
        if (!Array.isArray(params) || params.length === 0) return ''
        let text = `${params[0].axisValue}\n`
        for (const p of params) {
          if (p.seriesName === '误差下界' || p.seriesName === '误差带') continue
          text += `${p.seriesName}: ${p.value}°C\n`
        }
        return text
      }
    },
    legend: {
      data: ['预测温度'],
      top: 5,
      right: 10
    },
    grid: {
      top: 40,
      right: 30,
      bottom: 30,
      left: 50
    },
    xAxis: {
      type: 'category',
      data: timeSteps,
      boundaryGap: false
    },
    yAxis: {
      type: 'value',
      name: '温度 (°C)',
      min: (value: any) => Math.floor(value.min - 2),
      max: (value: any) => Math.ceil(value.max + 2)
    },
    series: [
      // 误差带下界(不可见)
      {
        name: '误差下界',
        type: 'line',
        data: lowerBound,
        lineStyle: { opacity: 0 },
        areaStyle: { opacity: 0 },
        symbol: 'none',
        stack: 'errorBand',
        silent: true
      },
      // 误差带(下界到上界的差值)
      {
        name: '误差带',
        type: 'line',
        data: bandWidth,
        lineStyle: { opacity: 0 },
        areaStyle: { color: errorBandColor.value },
        symbol: 'none',
        stack: 'errorBand',
        silent: true
      },
      // 预测温度轨迹
      {
        name: '预测温度',
        type: 'line',
        data: trajectory,
        lineStyle: { type: 'dashed', color: '#409EFF', width: 2 },
        itemStyle: { color: '#409EFF' },
        symbol: 'circle',
        symbolSize: 4,
        markPoint: {
          data: [
            {
              name: '当前温度',
              coord: [timeSteps[0], trajectory[0]],
              symbol: 'circle',
              symbolSize: 10,
              itemStyle: { color: '#E6A23C' },
              label: {
                show: true,
                formatter: `当前: ${trajectory[0]}°C`,
                position: 'top',
                fontSize: 11
              }
            }
          ]
        },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [
            {
              yAxis: 27,
              name: 'ASHRAE 上限',
              lineStyle: { type: 'dashed', color: '#f56c6c' },
              label: { formatter: 'ASHRAE 上限 27°C', position: 'insideEndTop' }
            },
            {
              yAxis: 18,
              name: 'ASHRAE 下限',
              lineStyle: { type: 'dashed', color: '#409EFF' },
              label: { formatter: 'ASHRAE 下限 18°C', position: 'insideEndBottom' }
            }
          ]
        }
      }
    ]
  }

  chartInstance.value.setOption(option, true)
}

const changeHours = (hours: number) => {
  selectedHours.value = hours
  fetchPrediction()
}

const handleResize = useDebounceFn(() => {
  chartInstance.value?.resize()
}, 200)

const startAutoRefresh = () => {
  refreshTimer.value = window.setInterval(() => {
    fetchPrediction()
  }, 60000)
}

const stopAutoRefresh = () => {
  if (refreshTimer.value) {
    clearInterval(refreshTimer.value)
    refreshTimer.value = undefined
  }
}

watch(() => props.zoneId, () => {
  fetchValidation()
  fetchPrediction()
})

onMounted(async () => {
  if (chartRef.value) {
    chartInstance.value = echarts.init(chartRef.value)
  }
  window.addEventListener('resize', handleResize)
  await fetchValidation()
  await fetchPrediction()
  startAutoRefresh()
})

onUnmounted(() => {
  stopAutoRefresh()
  window.removeEventListener('resize', handleResize)
  chartInstance.value?.dispose()
})
</script>

<style scoped lang="scss">
.temperature-prediction-chart {
  .chart-toolbar {
    display: flex;
    align-items: center;
    margin-bottom: 10px;
  }

  .chart-error {
    min-height: 200px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
}
</style>
