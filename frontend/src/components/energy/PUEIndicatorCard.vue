<template>
  <el-card class="pue-indicator-card" shadow="hover" @click="$router.push('/energy/analysis')">
    <div class="card-header">
      <div class="header-left">
        <el-icon :size="20" color="#67C23A"><TrendCharts /></el-icon>
        <span class="title">PUE效率</span>
      </div>
      <el-tooltip content="Power Usage Effectiveness: 数据中心总能耗与IT设备能耗比值" placement="top">
        <el-icon :size="16" class="info-icon"><InfoFilled /></el-icon>
      </el-tooltip>
    </div>

    <div class="card-body">
      <div class="pue-display">
        <div class="pue-value" :class="pueClass">
          {{ pue?.toFixed(2) || '-' }}
        </div>
        <el-icon v-if="trend === 'down'" :size="20" color="#67C23A"><Bottom /></el-icon>
        <el-icon v-else-if="trend === 'up'" :size="20" color="#F56C6C"><Top /></el-icon>
      </div>

      <div class="pue-bar">
        <div class="bar-track">
          <div class="bar-fill" :style="barStyle"></div>
          <div class="target-marker" :style="targetMarkerStyle"></div>
        </div>
        <div class="bar-labels">
          <span>1.0</span>
          <span class="target-label">目标:{{ target }}</span>
          <span>2.5</span>
        </div>
      </div>

      <div class="sparkline-container" v-if="trendData && trendData.length > 0">
        <Sparkline :data="trendData" :color="sparklineColor" height="28px" />
      </div>

      <div class="footer">
        <el-tag :type="statusType" size="small">{{ statusText }}</el-tag>
        <span class="compare-text" v-if="compareYesterday !== undefined">
          较昨日 {{ compareYesterday > 0 ? '+' : '' }}{{ compareYesterday.toFixed(2) }}
        </span>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { TrendCharts, InfoFilled, Top, Bottom } from '@element-plus/icons-vue'
import Sparkline from '@/components/charts/Sparkline.vue'

const props = defineProps<{
  pue?: number
  target?: number
  trend?: 'up' | 'down' | 'stable'
  trendData?: number[]
  compareYesterday?: number
}>()

const target = computed(() => props.target || 1.4)

const pueClass = computed(() => {
  const pue = props.pue || 0
  if (pue <= 1.4) return 'excellent'
  if (pue <= 1.6) return 'good'
  if (pue <= 1.8) return 'normal'
  return 'warning'
})

const sparklineColor = computed(() => {
  const pue = props.pue || 0
  if (pue <= 1.4) return '#67C23A'
  if (pue <= 1.6) return '#409EFF'
  if (pue <= 1.8) return '#E6A23C'
  return '#F56C6C'
})

const statusType = computed(() => {
  const pue = props.pue || 0
  if (pue <= target.value) return 'success'
  if (pue <= target.value + 0.2) return 'warning'
  return 'danger'
})

const statusText = computed(() => {
  const pue = props.pue || 0
  if (pue <= target.value) return '达标'
  return '待优化'
})

const barStyle = computed(() => {
  const pue = props.pue || 1.0
  const percent = Math.min(100, Math.max(0, ((pue - 1.0) / 1.5) * 100))
  return {
    width: `${percent}%`,
    backgroundColor: sparklineColor.value
  }
})

const targetMarkerStyle = computed(() => {
  const percent = ((target.value - 1.0) / 1.5) * 100
  return { left: `${percent}%` }
})
</script>

<style scoped lang="scss">
.pue-indicator-card {
  cursor: pointer;
  transition: all 0.3s;

  &:hover {
    transform: translateY(-2px);
  }

  :deep(.el-card__body) {
    padding: 16px;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;

    .header-left {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .title { font-size: 14px; color: #606266; }
    .info-icon { color: #C0C4CC; cursor: help; }
  }

  .card-body {
    .pue-display {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 12px;

      .pue-value {
        font-size: 32px;
        font-weight: bold;

        &.excellent { color: #67C23A; }
        &.good { color: #409EFF; }
        &.normal { color: #E6A23C; }
        &.warning { color: #F56C6C; }
      }
    }

    .pue-bar {
      margin: 12px 0;

      .bar-track {
        position: relative;
        height: 8px;
        background: #EBEEF5;
        border-radius: 4px;

        .bar-fill {
          height: 100%;
          border-radius: 4px;
          transition: width 0.3s;
        }

        .target-marker {
          position: absolute;
          top: -4px;
          width: 2px;
          height: 16px;
          background: #303133;
          transform: translateX(-50%);
        }
      }

      .bar-labels {
        display: flex;
        justify-content: space-between;
        margin-top: 4px;
        font-size: 10px;
        color: #909399;

        .target-label {
          color: #606266;
          font-weight: 500;
        }
      }
    }

    .sparkline-container {
      margin: 8px 0;
    }

    .footer {
      display: flex;
      align-items: center;
      gap: 8px;

      .compare-text {
        font-size: 12px;
        color: #909399;
      }
    }
  }
}
</style>
