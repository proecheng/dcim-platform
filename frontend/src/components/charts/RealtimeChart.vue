<template>
  <div ref="chartRef" class="realtime-chart" :style="{ height: height }"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, shallowRef } from 'vue'
import * as echarts from 'echarts'
import dayjs from 'dayjs'

interface DataPoint {
  time: string | Date
  value: number
}

interface Props {
  height?: string
  title?: string
  unit?: string
  maxPoints?: number
  color?: string
  areaStyle?: boolean
  yAxisMin?: number | 'dataMin'
  yAxisMax?: number | 'dataMax'
  showMarkLine?: boolean
  warningValue?: number
  criticalValue?: number
  smooth?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  height: '200px',
  maxPoints: 60,
  color: '#409eff',
  areaStyle: true,
  yAxisMin: 'dataMin',
  yAxisMax: 'dataMax',
  showMarkLine: false,
  smooth: true
})

const chartRef = ref<HTMLElement>()
const chartInstance = shallowRef<echarts.ECharts>()

const dataQueue = ref<DataPoint[]>([])

const getOption = (): echarts.EChartsOption => {
  const markLineData: any[] = []

  if (props.showMarkLine) {
    if (props.warningValue !== undefined) {
      markLineData.push({
        yAxis: props.warningValue,
        name: '警告',
        lineStyle: { color: '#e6a23c' },
        label: { formatter: '警告: {c}' }
      })
    }
    if (props.criticalValue !== undefined) {
      markLineData.push({
        yAxis: props.criticalValue,
        name: '严重',
        lineStyle: { color: '#f56c6c' },
        label: { formatter: '严重: {c}' }
      })
    }
  }

  return {
    title: props.title ? {
      text: props.title,
      left: 'center',
      textStyle: {
        fontSize: 14,
        fontWeight: 'normal'
      }
    } : undefined,
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const point = params[0]
        if (point) {
          const time = dayjs(point.axisValue).format('HH:mm:ss')
          const value = point.value[1]
          return `${time}<br/>${point.seriesName}: ${value}${props.unit || ''}`
        }
        return ''
      }
    },
    grid: {
      top: props.title ? 50 : 20,
      bottom: 30,
      left: 50,
      right: 20
    },
    xAxis: {
      type: 'time',
      splitLine: {
        show: false
      },
      axisLabel: {
        formatter: (value: number) => dayjs(value).format('HH:mm:ss'),
        color: '#666'
      }
    },
    yAxis: {
      type: 'value',
      name: props.unit,
      min: props.yAxisMin,
      max: props.yAxisMax,
      splitLine: {
        lineStyle: {
          type: 'dashed'
        }
      }
    },
    series: [
      {
        name: props.title || '数值',
        type: 'line',
        smooth: props.smooth,
        showSymbol: false,
        data: dataQueue.value.map(d => [
          typeof d.time === 'string' ? new Date(d.time).getTime() : d.time.getTime(),
          d.value
        ]),
        itemStyle: {
          color: props.color
        },
        areaStyle: props.areaStyle ? {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: props.color + '80' },
            { offset: 1, color: props.color + '10' }
          ])
        } : undefined,
        markLine: markLineData.length > 0 ? {
          symbol: 'none',
          data: markLineData
        } : undefined
      }
    ]
  }
}

const initChart = () => {
  if (!chartRef.value) return

  chartInstance.value = echarts.init(chartRef.value)
  chartInstance.value.setOption(getOption())
}

const addPoint = (point: DataPoint) => {
  dataQueue.value.push(point)

  // 保持最大点数
  if (dataQueue.value.length > props.maxPoints) {
    dataQueue.value.shift()
  }

  // 更新图表
  if (chartInstance.value) {
    chartInstance.value.setOption({
      series: [{
        data: dataQueue.value.map(d => [
          typeof d.time === 'string' ? new Date(d.time).getTime() : d.time.getTime(),
          d.value
        ])
      }]
    })
  }
}

const setData = (data: DataPoint[]) => {
  dataQueue.value = data.slice(-props.maxPoints)

  if (chartInstance.value) {
    chartInstance.value.setOption(getOption())
  }
}

const clear = () => {
  dataQueue.value = []
  if (chartInstance.value) {
    chartInstance.value.setOption({
      series: [{
        data: []
      }]
    })
  }
}

const resizeChart = () => {
  chartInstance.value?.resize()
}

onMounted(() => {
  initChart()
  window.addEventListener('resize', resizeChart)
})

onUnmounted(() => {
  window.removeEventListener('resize', resizeChart)
  chartInstance.value?.dispose()
})

defineExpose({
  addPoint,
  setData,
  clear,
  resize: resizeChart,
  getChart: () => chartInstance.value
})
</script>

<style lang="scss" scoped>
.realtime-chart {
  width: 100%;
}
</style>
