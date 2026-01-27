<!-- frontend/src/components/bigscreen/charts/BaseChart.vue -->
<template>
  <div ref="chartRef" class="chart-container"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, shallowRef } from 'vue'
import * as echarts from 'echarts'
import type { EChartsOption, ECharts } from 'echarts'

const props = withDefaults(defineProps<{
  option: EChartsOption
  autoResize?: boolean
  theme?: string | object
  loading?: boolean
}>(), {
  autoResize: true,
  theme: 'dark',
  loading: false
})

const emit = defineEmits<{
  (e: 'click', params: unknown): void
  (e: 'init', instance: ECharts): void
}>()

const chartRef = ref<HTMLElement | null>(null)
const chartInstance = shallowRef<ECharts | null>(null)

// 大屏暗色主题配置
const darkTheme = {
  color: [
    '#00ccff', '#00ff88', '#ffaa00', '#ff4d4f',
    '#9254de', '#36cfc9', '#597ef7', '#73d13d'
  ],
  backgroundColor: 'transparent',
  textStyle: {
    color: '#8899aa'
  },
  title: {
    textStyle: {
      color: '#ffffff'
    },
    subtextStyle: {
      color: '#8899aa'
    }
  },
  legend: {
    textStyle: {
      color: '#8899aa'
    }
  },
  tooltip: {
    backgroundColor: 'rgba(10, 20, 40, 0.9)',
    borderColor: 'rgba(0, 136, 255, 0.4)',
    textStyle: {
      color: '#ffffff'
    }
  },
  axisLine: {
    lineStyle: {
      color: 'rgba(136, 153, 170, 0.3)'
    }
  },
  splitLine: {
    lineStyle: {
      color: 'rgba(136, 153, 170, 0.1)'
    }
  }
}

function initChart() {
  if (!chartRef.value) return

  // 注册自定义主题
  echarts.registerTheme('bigscreen-dark', darkTheme)

  chartInstance.value = echarts.init(
    chartRef.value,
    props.theme === 'dark' ? 'bigscreen-dark' : props.theme
  )

  chartInstance.value.setOption(props.option)

  // 绑定点击事件
  chartInstance.value.on('click', (params) => {
    emit('click', params)
  })

  emit('init', chartInstance.value)
}

function updateOption() {
  if (chartInstance.value) {
    chartInstance.value.setOption(props.option, { notMerge: false })
  }
}

function handleResize() {
  chartInstance.value?.resize()
}

function showLoading() {
  chartInstance.value?.showLoading({
    text: '',
    color: '#00ccff',
    maskColor: 'rgba(0, 0, 0, 0.3)',
    zlevel: 0
  })
}

function hideLoading() {
  chartInstance.value?.hideLoading()
}

// 监听 option 变化
watch(() => props.option, () => {
  updateOption()
}, { deep: true })

// 监听 loading 状态
watch(() => props.loading, (loading) => {
  if (loading) {
    showLoading()
  } else {
    hideLoading()
  }
})

// 暴露方法
defineExpose({
  getInstance: () => chartInstance.value,
  resize: handleResize,
  setOption: (option: EChartsOption) => {
    chartInstance.value?.setOption(option)
  }
})

onMounted(() => {
  initChart()

  if (props.autoResize) {
    window.addEventListener('resize', handleResize)
  }

  if (props.loading) {
    showLoading()
  }
})

onUnmounted(() => {
  if (props.autoResize) {
    window.removeEventListener('resize', handleResize)
  }

  chartInstance.value?.dispose()
  chartInstance.value = null
})
</script>

<style scoped lang="scss">
.chart-container {
  width: 100%;
  height: 100%;
  min-height: 150px;
}
</style>
