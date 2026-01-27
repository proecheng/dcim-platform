<template>
  <el-card class="demand-status-card" shadow="hover" @click="$router.push('/energy/analysis?tab=demand')">
    <div class="card-header">
      <div class="header-left">
        <el-icon :size="20" color="#E6A23C"><DataLine /></el-icon>
        <span class="title">需量状态</span>
      </div>
    </div>

    <div class="card-body">
      <div class="main-display">
        <span class="value" :class="valueClass">{{ utilizationRate }}</span>
        <span class="unit">%</span>
      </div>

      <div class="demand-progress">
        <el-progress
          :percentage="Math.min(utilizationRate, 100)"
          :color="progressColors"
          :stroke-width="12"
          :show-text="false"
        />
      </div>

      <div class="demand-info">
        <div class="info-item">
          <span class="label">当前需量</span>
          <span class="value">{{ currentDemand?.toFixed(0) || 0 }} kW</span>
        </div>
        <div class="info-item">
          <span class="label">申报需量</span>
          <span class="value">{{ declaredDemand || 0 }} kW</span>
        </div>
      </div>

      <div class="sparkline-container" v-if="trendData && trendData.length > 0">
        <Sparkline :data="trendData" :color="trendColor" height="28px" />
      </div>

      <div class="footer" v-if="overDeclaredRisk">
        <el-tag type="danger" size="small" effect="light">
          <el-icon><Warning /></el-icon>
          超申报风险
        </el-tag>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { DataLine, Warning } from '@element-plus/icons-vue'
import Sparkline from '@/components/charts/Sparkline.vue'

const props = defineProps<{
  currentDemand?: number
  declaredDemand?: number
  trendData?: number[]
  overDeclaredRisk?: boolean
}>()

const utilizationRate = computed(() => {
  if (!props.declaredDemand || props.declaredDemand === 0) return 0
  return Math.round(((props.currentDemand || 0) / props.declaredDemand) * 100)
})

const valueClass = computed(() => {
  const rate = utilizationRate.value
  if (rate >= 90) return 'danger'
  if (rate >= 75) return 'warning'
  return 'normal'
})

const progressColors = [
  { color: '#67C23A', percentage: 60 },
  { color: '#E6A23C', percentage: 80 },
  { color: '#F56C6C', percentage: 100 }
]

const trendColor = computed(() => {
  const rate = utilizationRate.value
  if (rate >= 90) return '#F56C6C'
  if (rate >= 75) return '#E6A23C'
  return '#67C23A'
})
</script>

<style scoped lang="scss">
.demand-status-card {
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
  }

  .card-body {
    .main-display {
      display: flex;
      align-items: baseline;
      gap: 4px;
      margin-bottom: 8px;

      .value {
        font-size: 28px;
        font-weight: bold;

        &.normal { color: #67C23A; }
        &.warning { color: #E6A23C; }
        &.danger { color: #F56C6C; }
      }

      .unit { font-size: 14px; color: #909399; }
    }

    .demand-progress {
      margin: 8px 0;
    }

    .demand-info {
      display: flex;
      justify-content: space-between;
      margin: 8px 0;

      .info-item {
        display: flex;
        flex-direction: column;
        gap: 2px;

        .label { font-size: 12px; color: #909399; }
        .value { font-size: 14px; color: #606266; font-weight: 500; }
      }
    }

    .sparkline-container {
      margin: 8px 0;
    }

    .footer {
      margin-top: 8px;

      .el-tag {
        display: flex;
        align-items: center;
        gap: 4px;
      }
    }
  }
}
</style>
