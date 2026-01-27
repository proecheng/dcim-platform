<template>
  <el-card class="cost-card" shadow="hover" @click="$router.push('/energy/statistics')">
    <div class="card-header">
      <div class="header-left">
        <el-icon :size="20" color="#F56C6C"><Coin /></el-icon>
        <span class="title">今日电费</span>
      </div>
    </div>

    <div class="card-body">
      <div class="main-display">
        <span class="currency">¥</span>
        <span class="value">{{ todayCost?.toFixed(0) || 0 }}</span>
      </div>

      <div class="pie-container" ref="pieRef"></div>

      <div class="cost-info">
        <div class="info-item">
          <span class="dot peak"></span>
          <span class="label">峰时</span>
          <span class="value">{{ peakRatioValue }}%</span>
        </div>
        <div class="info-item">
          <span class="dot flat"></span>
          <span class="label">平时</span>
          <span class="value">{{ flatRatioValue }}%</span>
        </div>
        <div class="info-item">
          <span class="dot valley"></span>
          <span class="label">谷时</span>
          <span class="value">{{ valleyRatioValue }}%</span>
        </div>
      </div>

      <div class="footer">
        <span class="footer-item">本月: ¥{{ monthCost?.toFixed(0) || 0 }}</span>
        <span class="footer-item">均价: ¥{{ avgPrice?.toFixed(2) || 0 }}/度</span>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, shallowRef, computed } from 'vue'
import { Coin } from '@element-plus/icons-vue'
import * as echarts from 'echarts'

// Theme colors for ECharts (can't use CSS variables directly)
const themeColors = {
  error: '#f5222d',
  warning: '#faad14',
  success: '#52c41a'
}

const props = defineProps<{
  todayCost?: number
  monthCost?: number
  avgPrice?: number
  peakRatio?: number
  flatRatio?: number
  valleyRatio?: number
}>()

const pieRef = ref<HTMLElement>()
const chartInstance = shallowRef<echarts.ECharts>()

const peakRatioValue = computed(() => props.peakRatio || 45)
const flatRatioValue = computed(() => props.flatRatio || 30)
const valleyRatioValue = computed(() => props.valleyRatio || 25)

const initChart = () => {
  if (!pieRef.value) return
  chartInstance.value = echarts.init(pieRef.value)
  updateChart()
}

const updateChart = () => {
  if (!chartInstance.value) return

  chartInstance.value.setOption({
    series: [{
      type: 'pie',
      radius: ['50%', '70%'],
      center: ['50%', '50%'],
      avoidLabelOverlap: false,
      label: { show: false },
      data: [
        { value: peakRatioValue.value, name: '峰时', itemStyle: { color: themeColors.error } },
        { value: flatRatioValue.value, name: '平时', itemStyle: { color: themeColors.warning } },
        { value: valleyRatioValue.value, name: '谷时', itemStyle: { color: themeColors.success } }
      ]
    }]
  })
}

watch([peakRatioValue, flatRatioValue, valleyRatioValue], updateChart)

onMounted(() => {
  initChart()
  window.addEventListener('resize', () => chartInstance.value?.resize())
})

onUnmounted(() => {
  chartInstance.value?.dispose()
})
</script>

<style scoped lang="scss">
.cost-card {
  cursor: pointer;
  transition: all 0.3s;
  background-color: var(--bg-card-solid, #1a2a4a);
  border-color: var(--border-color, rgba(255, 255, 255, 0.1));

  &:hover {
    transform: translateY(-2px);
  }

  :deep(.el-card__body) {
    padding: 16px;
  }

  .card-header {
    display: flex;
    align-items: center;
    margin-bottom: 8px;

    .header-left {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .title { font-size: 14px; color: var(--text-regular, rgba(255, 255, 255, 0.85)); }
  }

  .card-body {
    .main-display {
      display: flex;
      align-items: baseline;
      margin-bottom: 8px;

      .currency { font-size: 16px; color: var(--error-color, #f5222d); font-weight: 500; }
      .value { font-size: 28px; font-weight: bold; color: var(--text-primary, rgba(255, 255, 255, 0.95)); }
    }

    .pie-container {
      height: 60px;
      margin: 8px 0;
    }

    .cost-info {
      display: flex;
      justify-content: space-around;
      margin: 8px 0;

      .info-item {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 12px;

        .dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;

          &.peak { background: var(--error-color, #f5222d); }
          &.flat { background: var(--warning-color, #faad14); }
          &.valley { background: var(--success-color, #52c41a); }
        }

        .label { color: var(--text-secondary, rgba(255, 255, 255, 0.65)); }
        .value { color: var(--text-regular, rgba(255, 255, 255, 0.85)); font-weight: 500; }
      }
    }

    .footer {
      display: flex;
      justify-content: space-between;
      font-size: 12px;
      color: var(--text-secondary, rgba(255, 255, 255, 0.65));
    }
  }
}
</style>
