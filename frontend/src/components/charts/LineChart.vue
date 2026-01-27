<template>
  <div ref="chartRef" class="line-chart" :style="{ height: height }"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, shallowRef } from 'vue'
import * as echarts from 'echarts'

interface SeriesData {
  name: string
  data: (number | null)[]
  color?: string
  type?: 'line' | 'bar'
  smooth?: boolean
  areaStyle?: boolean
  yAxisIndex?: number
}

interface Props {
  xData: string[]
  series: SeriesData[]
  height?: string
  title?: string
  showLegend?: boolean
  showTooltip?: boolean
  showDataZoom?: boolean
  xAxisType?: 'category' | 'time'
  yAxisName?: string
  yAxisName2?: string
  gridTop?: number
  gridBottom?: number
  gridLeft?: number
  gridRight?: number
  smooth?: boolean
  areaStyle?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  height: '300px',
  showLegend: true,
  showTooltip: true,
  showDataZoom: false,
  xAxisType: 'category',
  gridTop: 60,
  gridBottom: 30,
  gridLeft: 50,
  gridRight: 50,
  smooth: true,
  areaStyle: false
})

const chartRef = ref<HTMLElement>()
const chartInstance = shallowRef<echarts.ECharts>()

const getOption = (): echarts.EChartsOption => {
  const hasDualAxis = props.series.some(s => s.yAxisIndex === 1)

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
        type: 'cross'
      }
    } : undefined,
    legend: props.showLegend ? {
      top: 25,
      data: props.series.map(s => s.name)
    } : undefined,
    grid: {
      top: props.gridTop,
      bottom: props.showDataZoom ? props.gridBottom + 40 : props.gridBottom,
      left: props.gridLeft,
      right: hasDualAxis ? props.gridRight : 20,
      containLabel: true
    },
    dataZoom: props.showDataZoom ? [
      {
        type: 'inside',
        start: 0,
        end: 100
      },
      {
        type: 'slider',
        start: 0,
        end: 100
      }
    ] : undefined,
    xAxis: {
      type: props.xAxisType,
      data: props.xData,
      boundaryGap: false,
      axisLine: {
        lineStyle: {
          color: '#ddd'
        }
      },
      axisLabel: {
        color: '#666'
      }
    },
    yAxis: hasDualAxis ? [
      {
        type: 'value',
        name: props.yAxisName,
        splitLine: {
          lineStyle: {
            type: 'dashed'
          }
        }
      },
      {
        type: 'value',
        name: props.yAxisName2,
        splitLine: {
          show: false
        }
      }
    ] : {
      type: 'value',
      name: props.yAxisName,
      splitLine: {
        lineStyle: {
          type: 'dashed'
        }
      }
    },
    series: props.series.map(s => ({
      name: s.name,
      type: s.type || 'line',
      data: s.data,
      smooth: s.smooth ?? props.smooth,
      yAxisIndex: s.yAxisIndex || 0,
      itemStyle: s.color ? { color: s.color } : undefined,
      areaStyle: (s.areaStyle ?? props.areaStyle) ? {
        opacity: 0.3
      } : undefined,
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
.line-chart {
  width: 100%;
}
</style>
