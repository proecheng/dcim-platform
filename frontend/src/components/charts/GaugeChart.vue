<template>
  <div ref="chartRef" class="gauge-chart" :style="{ height: height }"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, shallowRef, computed } from 'vue'
import * as echarts from 'echarts'

interface Props {
  value: number
  height?: string
  title?: string
  unit?: string
  min?: number
  max?: number
  splitNumber?: number
  showPointer?: boolean
  showProgress?: boolean
  axisLabelShow?: boolean
  startAngle?: number
  endAngle?: number
  radius?: string
  colors?: { value: number; color: string }[]
}

const props = withDefaults(defineProps<Props>(), {
  height: '200px',
  min: 0,
  max: 100,
  splitNumber: 10,
  showPointer: true,
  showProgress: true,
  axisLabelShow: true,
  startAngle: 225,
  endAngle: -45,
  radius: '75%'
})

const chartRef = ref<HTMLElement>()
const chartInstance = shallowRef<echarts.ECharts>()

const defaultColors = [
  { value: 0.3, color: '#67e0e3' },
  { value: 0.7, color: '#37a2da' },
  { value: 1, color: '#fd666d' }
]

const axisLineColors = computed(() => {
  if (props.colors && props.colors.length > 0) {
    return props.colors.map(c => [c.value / props.max, c.color])
  }
  return defaultColors.map(c => [c.value, c.color])
})

const getOption = (): echarts.EChartsOption => {
  return {
    series: [
      {
        type: 'gauge',
        startAngle: props.startAngle,
        endAngle: props.endAngle,
        radius: props.radius,
        min: props.min,
        max: props.max,
        splitNumber: props.splitNumber,
        progress: {
          show: props.showProgress,
          width: 18
        },
        pointer: {
          show: props.showPointer,
          length: '60%',
          width: 6
        },
        axisLine: {
          lineStyle: {
            width: 18,
            color: axisLineColors.value as any
          }
        },
        axisTick: {
          show: true,
          splitNumber: 2,
          lineStyle: {
            width: 2,
            color: '#999'
          }
        },
        splitLine: {
          show: true,
          length: 12,
          lineStyle: {
            width: 3,
            color: '#999'
          }
        },
        axisLabel: {
          show: props.axisLabelShow,
          distance: 25,
          color: '#999',
          fontSize: 12
        },
        anchor: {
          show: true,
          showAbove: true,
          size: 18,
          itemStyle: {
            borderWidth: 8,
            borderColor: '#5470c6'
          }
        },
        title: {
          show: !!props.title,
          offsetCenter: [0, '70%'],
          fontSize: 14,
          color: '#666'
        },
        detail: {
          valueAnimation: true,
          fontSize: 24,
          fontWeight: 'bold',
          offsetCenter: [0, '40%'],
          formatter: (value: number) => {
            return props.unit ? `${value.toFixed(1)}${props.unit}` : value.toFixed(1)
          },
          color: 'inherit'
        },
        data: [
          {
            value: props.value,
            name: props.title || ''
          }
        ]
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
    chartInstance.value.setOption({
      series: [{
        data: [{
          value: props.value,
          name: props.title || ''
        }]
      }]
    })
  }
}

const resizeChart = () => {
  chartInstance.value?.resize()
}

watch(() => props.value, updateChart)

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
.gauge-chart {
  width: 100%;
}
</style>
