<template>
  <div ref="chartRef" class="bar-chart" :style="{ height: height }"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, shallowRef } from 'vue'
import * as echarts from 'echarts'

interface SeriesData {
  name: string
  data: number[]
  color?: string
  stack?: string
  barWidth?: number | string
}

interface Props {
  xData: string[]
  series: SeriesData[]
  height?: string
  title?: string
  showLegend?: boolean
  showTooltip?: boolean
  horizontal?: boolean
  yAxisName?: string
  barWidth?: number | string
  stack?: boolean
  gridTop?: number
  gridBottom?: number
  gridLeft?: number
  gridRight?: number
}

const props = withDefaults(defineProps<Props>(), {
  height: '300px',
  showLegend: true,
  showTooltip: true,
  horizontal: false,
  barWidth: 'auto',
  stack: false,
  gridTop: 60,
  gridBottom: 30,
  gridLeft: 50,
  gridRight: 20
})

const chartRef = ref<HTMLElement>()
const chartInstance = shallowRef<echarts.ECharts>()

const getOption = (): echarts.EChartsOption => {
  const categoryAxis = {
    type: 'category' as const,
    data: props.xData,
    axisLine: {
      lineStyle: {
        color: '#ddd'
      }
    },
    axisLabel: {
      color: '#666'
    }
  }

  const valueAxis = {
    type: 'value' as const,
    name: props.yAxisName,
    splitLine: {
      lineStyle: {
        type: 'dashed' as const
      }
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
    tooltip: props.showTooltip ? {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      }
    } : undefined,
    legend: props.showLegend ? {
      top: 25,
      data: props.series.map(s => s.name)
    } : undefined,
    grid: {
      top: props.gridTop,
      bottom: props.gridBottom,
      left: props.gridLeft,
      right: props.gridRight,
      containLabel: true
    },
    xAxis: props.horizontal ? valueAxis : categoryAxis,
    yAxis: props.horizontal ? categoryAxis : valueAxis,
    series: props.series.map(s => ({
      name: s.name,
      type: 'bar' as const,
      data: s.data,
      barWidth: s.barWidth || props.barWidth,
      stack: props.stack ? 'total' : s.stack,
      itemStyle: s.color ? { color: s.color } : undefined,
      emphasis: {
        focus: 'series'
      }
    }))
  }
}

const initChart = () => {
  if (!chartRef.value) return

  chartInstance.value = echarts.init(chartRef.value)
  chartInstance.value.setOption(getOption())
}

const updateChart = () => {
  if (chartInstance.value) {
    chartInstance.value.setOption(getOption(), true)
  }
}

const resizeChart = () => {
  chartInstance.value?.resize()
}

watch([() => props.xData, () => props.series], updateChart, { deep: true })

onMounted(() => {
  initChart()
  window.addEventListener('resize', resizeChart)
})

onUnmounted(() => {
  window.removeEventListener('resize', resizeChart)
  chartInstance.value?.dispose()
})

defineExpose({
  resize: resizeChart,
  getChart: () => chartInstance.value
})
</script>

<style lang="scss" scoped>
.bar-chart {
  width: 100%;
}
</style>
