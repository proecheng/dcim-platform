<template>
  <div class="pue-gauge">
    <div class="gauge-container" ref="chartRef"></div>
    <div class="pue-details">
      <div class="detail-item">
        <span class="label">总功率</span>
        <span class="value">{{ formatPower(totalPower) }}</span>
      </div>
      <div class="detail-item">
        <span class="label">IT负载</span>
        <span class="value">{{ formatPower(itPower) }}</span>
      </div>
      <div class="detail-item">
        <span class="label">制冷功率</span>
        <span class="value">{{ formatPower(coolingPower) }}</span>
      </div>
      <div class="detail-item">
        <span class="label">PUE等级</span>
        <span class="value" :style="{ color: pueLevel.color }">{{ pueLevel.level }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{
  pue: number
  totalPower?: number
  itPower?: number
  coolingPower?: number
}>()

const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

// Theme colors for ECharts (CSS variables can't be used directly in ECharts)
const themeColors = {
  textPrimary: 'rgba(255, 255, 255, 0.95)',
  textSecondary: 'rgba(255, 255, 255, 0.65)',
  success: '#52c41a',
  primary: '#1890ff',
  warning: '#faad14',
  error: '#f5222d',
  border: 'rgba(255, 255, 255, 0.1)'
}

// PUE等级
const pueLevel = computed(() => {
  const pue = props.pue
  if (pue <= 1.4) return { level: '优秀', color: themeColors.success }
  if (pue <= 1.6) return { level: '良好', color: themeColors.primary }
  if (pue <= 1.8) return { level: '一般', color: themeColors.warning }
  return { level: '较差', color: themeColors.error }
})

// 格式化功率
function formatPower(power?: number): string {
  if (power === undefined || power === null) return '-'
  return `${power.toFixed(1)} kW`
}

// 获取图表配置
function getOption() {
  return {
    series: [
      {
        type: 'gauge',
        startAngle: 200,
        endAngle: -20,
        min: 1,
        max: 3,
        splitNumber: 4,
        itemStyle: {
          color: pueLevel.value.color
        },
        progress: {
          show: true,
          width: 20
        },
        pointer: {
          show: true,
          length: '60%',
          width: 6
        },
        axisLine: {
          lineStyle: {
            width: 20,
            color: [
              [0.2, themeColors.success],
              [0.4, themeColors.primary],
              [0.6, themeColors.warning],
              [1, themeColors.error]
            ]
          }
        },
        axisTick: {
          distance: -30,
          splitNumber: 5,
          lineStyle: {
            width: 1,
            color: themeColors.textSecondary
          }
        },
        splitLine: {
          distance: -35,
          length: 10,
          lineStyle: {
            width: 2,
            color: themeColors.textSecondary
          }
        },
        axisLabel: {
          distance: -20,
          color: themeColors.textSecondary,
          fontSize: 12,
          formatter: (value: number) => value.toFixed(1)
        },
        anchor: {
          show: false
        },
        title: {
          show: true,
          offsetCenter: [0, '70%'],
          fontSize: 14,
          color: themeColors.textSecondary
        },
        detail: {
          valueAnimation: true,
          width: '60%',
          lineHeight: 40,
          borderRadius: 8,
          offsetCenter: [0, '40%'],
          fontSize: 32,
          fontWeight: 'bold',
          formatter: '{value}',
          color: pueLevel.value.color
        },
        data: [
          {
            value: props.pue,
            name: 'PUE'
          }
        ]
      }
    ]
  }
}

// 初始化图表
function initChart() {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  chart.setOption(getOption())
}

// 更新图表
function updateChart() {
  if (!chart) return
  chart.setOption(getOption())
}

// 监听数据变化
watch(() => props.pue, updateChart)

onMounted(() => {
  initChart()
  window.addEventListener('resize', () => chart?.resize())
})

onUnmounted(() => {
  chart?.dispose()
  window.removeEventListener('resize', () => chart?.resize())
})
</script>

<style scoped lang="scss">
.pue-gauge {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.gauge-container {
  width: 280px;
  height: 220px;
}

.pue-details {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-top: 8px;
  width: 100%;
  max-width: 280px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px;
  background: var(--bg-tertiary);
  border-radius: 6px;
  border: 1px solid var(--border-color);

  .label {
    font-size: 12px;
    color: var(--text-secondary);
    margin-bottom: 4px;
  }

  .value {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
  }
}
</style>
