<template>
  <div class="demand-comparison-card" :class="{ compact }">
    <div class="card-header" v-if="!compact">
      <span class="title">需量配置对比</span>
      <el-link type="primary" @click="goToFullAnalysis">
        查看完整分析 →
      </el-link>
    </div>

    <div class="comparison-content" v-loading="loading">
      <div class="main-comparison">
        <div class="comparison-item">
          <div class="label">申报需量</div>
          <div class="value declared">{{ data?.current_declared || currentDeclared || 0 }} <span class="unit">kW</span></div>
        </div>
        <div class="comparison-arrow">
          <el-icon><ArrowRight /></el-icon>
        </div>
        <div class="comparison-item">
          <div class="label">实际最大</div>
          <div class="value actual">{{ data?.max_demand_12m || maxDemand12m || 0 }} <span class="unit">kW</span></div>
        </div>
      </div>

      <div class="utilization-bar">
        <div class="bar-label">
          <span>利用率</span>
          <span class="percentage" :class="utilizationClass">
            {{ ((data?.utilization_rate || 0) * 100).toFixed(1) }}%
          </span>
        </div>
        <el-progress
          :percentage="(data?.utilization_rate || 0) * 100"
          :stroke-width="10"
          :color="utilizationColor"
          :show-text="false"
        />
      </div>

      <div class="recommendation" v-if="data?.recommendation">
        <el-alert
          :type="data.recommendation.risk_level === 'low' ? 'success' : 'warning'"
          :closable="false"
        >
          <template #title>
            <div class="rec-content">
              <span>建议调整至 <strong>{{ data.recommendation.suggested_demand }} kW</strong></span>
              <span class="saving">
                月节省 <strong>¥{{ data.recommendation.monthly_saving }}</strong>
              </span>
            </div>
          </template>
        </el-alert>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight } from '@element-plus/icons-vue'
import { getDemandComparison, type DemandComparisonData } from '@/api/modules/demand'

const props = defineProps<{
  meterPointId?: number
  currentDeclared?: number
  maxDemand12m?: number
  avgDemand12m?: number
  compact?: boolean
  // 如果提供了 analysisData，直接使用不调用 API
  analysisData?: Record<string, any>
}>()

const router = useRouter()
const loading = ref(false)
const data = ref<DemandComparisonData | null>(null)

// 统一阈值配置（与后端 DemandThresholds 保持一致）
const DEMAND_THRESHOLDS = {
  low_utilization: 0.80,   // 低利用率阈值 (80%)
  high_utilization: 1.05   // 高利用率阈值 (105%)
}

const utilizationClass = computed(() => {
  const rate = data.value?.utilization_rate || 0
  if (rate < DEMAND_THRESHOLDS.low_utilization) return 'low'      // < 80%: 申报过高
  if (rate <= DEMAND_THRESHOLDS.high_utilization) return 'good'   // 80%-105%: 合理
  return 'high'                                                    // > 105%: 风险
})

const utilizationColor = computed(() => {
  const rate = data.value?.utilization_rate || 0
  if (rate < DEMAND_THRESHOLDS.low_utilization) return '#faad14'  // 利用率过低，可优化
  if (rate <= DEMAND_THRESHOLDS.high_utilization) return '#52c41a'  // 配置合理
  return '#f5222d'  // 超申报风险
})

onMounted(() => {
  if (props.analysisData) {
    // 使用传入的分析数据
    data.value = {
      meter_point_id: props.meterPointId,
      meter_point_name: '全站',
      current_declared: props.analysisData.current_declared || props.currentDeclared || 800,
      max_demand_12m: props.analysisData.max_demand_12m || props.maxDemand12m || 685,
      avg_demand_12m: props.analysisData.avg_demand_12m || props.avgDemand12m || 520,
      utilization_rate: (props.analysisData.max_demand_12m || 685) / (props.analysisData.current_declared || 800),
      over_declared: (props.analysisData.current_declared || 800) - (props.analysisData.max_demand_12m || 685),
      recommendation: {
        suggested_demand: props.analysisData.recommended_declared || 750,
        reduce_amount: (props.analysisData.current_declared || 800) - (props.analysisData.recommended_declared || 750),
        monthly_saving: props.analysisData.monthly_saving || 1400,
        risk_level: props.analysisData.risk_level || 'low'
      }
    }
  } else {
    loadData()
  }
})

watch(() => props.meterPointId, () => {
  if (!props.analysisData) {
    loadData()
  }
})

async function loadData() {
  loading.value = true
  try {
    const res = await getDemandComparison(props.meterPointId)
    if (res.code === 0 && res.data) {
      data.value = res.data
    }
  } catch (e) {
    console.error('加载需量对比数据失败', e)
  } finally {
    loading.value = false
  }
}

function goToFullAnalysis() {
  router.push('/energy/demand/config')
}
</script>

<style scoped lang="scss">
.demand-comparison-card {
  background: var(--bg-card-solid, #1a2a4a);
  border-radius: 8px;
  padding: 16px;

  &.compact {
    padding: 12px;

    .main-comparison {
      gap: 16px;

      .comparison-item .value {
        font-size: 20px;
      }
    }
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;

    .title {
      font-size: 14px;
      font-weight: 600;
      color: var(--text-primary, rgba(255, 255, 255, 0.95));
    }
  }

  .main-comparison {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 24px;
    margin-bottom: 16px;

    .comparison-item {
      text-align: center;

      .label {
        font-size: 12px;
        color: var(--text-secondary, rgba(255, 255, 255, 0.65));
        margin-bottom: 4px;
      }

      .value {
        font-size: 24px;
        font-weight: bold;

        &.declared {
          color: var(--text-primary, rgba(255, 255, 255, 0.95));
        }

        &.actual {
          color: var(--primary-color, #1890ff);
        }

        .unit {
          font-size: 12px;
          font-weight: normal;
          color: var(--text-secondary, rgba(255, 255, 255, 0.65));
        }
      }
    }

    .comparison-arrow {
      color: var(--text-secondary, rgba(255, 255, 255, 0.45));
      font-size: 20px;
    }
  }

  .utilization-bar {
    margin-bottom: 12px;

    .bar-label {
      display: flex;
      justify-content: space-between;
      font-size: 12px;
      color: var(--text-secondary, rgba(255, 255, 255, 0.65));
      margin-bottom: 6px;

      .percentage {
        font-weight: 600;

        &.low { color: #faad14; }
        &.good { color: #52c41a; }
        &.high { color: #f5222d; }
      }
    }
  }

  .recommendation {
    .rec-content {
      display: flex;
      justify-content: space-between;
      align-items: center;
      width: 100%;

      .saving {
        color: var(--success-color, #52c41a);
      }

      strong {
        font-weight: 600;
      }
    }
  }
}
</style>
