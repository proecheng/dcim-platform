<template>
  <div ref="chartRef" class="pie-chart" :style="{ height: height }"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, shallowRef } from 'vue'
import * as echarts from 'echarts'

interface DataItem {
  name: string
  value: number
  color?: string
}

interface Props {
  data: DataItem[]
  height?: string
  title?: string
  showLegend?: boolean
  showTooltip?: boolean
  showLabel?: boolean
  labelPosition?: 'outside' | 'inside' | 'center'
  radius?: string | string[]
  center?: string[]
  roseType?: false | 'radius' | 'area'
}

const props = withDefaults(defineProps<Props>(), {
  height: '300px',
  showLegend: true,
  showTooltip: true,
  showLabel: true,
  labelPosition: 'outside',
  radius: '60%',
  center: () => ['50%', '50%'],
  roseType: false
})

const chartRef = ref<HTMLElement>()
const chartInstance = shallowRef<echarts.ECharts>()

const getOption = (): echarts.EChartsOption => {
  const colors = props.data
    .filter(d => d.color)
    .map(d => d.color)

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
      trigger: 'item',
      formatter: '{a} <br/>{b}: {c} ({d}%)'
    } : undefined,
    legend: props.showLegend ? {
      orient: 'vertical',
      left: 'left',
      data: props.data.map(d => d.name)
    } : undefined,
    color: colors.length > 0 ? colors : undefined,
    series: [
      {
        name: props.title || '数据',
        type: 'pie',
        radius: props.radius,
        center: props.center,
        roseType: props.roseType === false ? undefined : props.roseType,
        data: props.data.map(d => ({
          name: d.name,
          value: d.value,
          itemStyle: d.color ? { color: d.color } : undefined
        })),
        label: {
          show: props.showLabel,
          position: props.labelPosition,
          formatter: props.labelPosition === 'inside'
            ? '{d}%'
            : '{b}: {d}%'
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }
    ]
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

watch(() => props.data, updateChart, { deep: true })

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
.pie-chart {
  width: 100%;
}
</style>
