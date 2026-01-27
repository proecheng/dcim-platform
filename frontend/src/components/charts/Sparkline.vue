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
