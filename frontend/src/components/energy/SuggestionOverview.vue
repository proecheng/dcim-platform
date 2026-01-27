<template>
  <div class="suggestion-overview">
    <!-- 问题描述 -->
    <el-card shadow="never" class="overview-card">
      <template #header>
        <div class="card-header">
          <el-icon><WarningFilled /></el-icon>
          <span>问题描述</span>
        </div>
      </template>
      <div class="problem-content">
        <p>{{ suggestion.problem_description || '暂无问题描述' }}</p>
      </div>
    </el-card>

    <!-- 分析详情 -->
    <el-card shadow="never" class="overview-card">
      <template #header>
        <div class="card-header">
          <el-icon><DataAnalysis /></el-icon>
          <span>分析详情</span>
        </div>
      </template>
      <div class="analysis-content">
        <p>{{ suggestion.analysis_detail || '暂无分析详情' }}</p>

        <!-- 电价配置信息 -->
        <div v-if="hasPricingData" class="pricing-info">
          <el-divider content-position="left">当前电价配置</el-divider>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="尖峰电价" v-if="parameters?.sharp_price">
              {{ parameters.sharp_price }} 元/kWh
            </el-descriptions-item>
            <el-descriptions-item label="高峰电价" v-if="parameters?.peak_price">
              {{ parameters.peak_price }} 元/kWh
            </el-descriptions-item>
            <el-descriptions-item label="平段电价" v-if="parameters?.normal_price">
              {{ parameters.normal_price }} 元/kWh
            </el-descriptions-item>
            <el-descriptions-item label="低谷电价" v-if="parameters?.valley_price">
              {{ parameters.valley_price }} 元/kWh
            </el-descriptions-item>
            <el-descriptions-item label="峰谷价差" v-if="parameters?.price_diff">
              <span class="highlight">{{ parameters.price_diff?.toFixed(3) }} 元/kWh</span>
            </el-descriptions-item>
            <el-descriptions-item label="可转移功率" v-if="parameters?.total_shiftable_power">
              <span class="highlight">{{ parameters.total_shiftable_power }} kW</span>
            </el-descriptions-item>
          </el-descriptions>

          <el-alert
            v-if="dataSource"
            type="info"
            :closable="false"
            class="data-source-alert"
          >
            <template #title>
              <span>{{ dataSource.message || '数据来源：系统设置 → 电价配置' }}</span>
            </template>
          </el-alert>
        </div>
      </div>
    </el-card>

    <!-- 预期效果 -->
    <el-card shadow="never" class="overview-card">
      <template #header>
        <div class="card-header">
          <el-icon><TrendCharts /></el-icon>
          <span>预期效果</span>
        </div>
      </template>
      <div class="effect-content">
        <p v-if="suggestion.expected_effect?.description">
          {{ suggestion.expected_effect.description }}
        </p>

        <el-row :gutter="20" class="effect-stats">
          <el-col :span="8">
            <el-statistic title="预计月节能" :value="suggestion.potential_saving || 0">
              <template #suffix>kWh</template>
            </el-statistic>
          </el-col>
          <el-col :span="8">
            <el-statistic
              title="预计月节省"
              :value="(suggestion.potential_cost_saving || 0) / 12"
              :precision="0"
            >
              <template #suffix>元</template>
            </el-statistic>
          </el-col>
          <el-col :span="8">
            <el-statistic
              title="预计年节省"
              :value="(suggestion.potential_cost_saving || 0) / 10000"
              :precision="2"
            >
              <template #suffix>万元</template>
            </el-statistic>
          </el-col>
        </el-row>
      </div>
    </el-card>

    <!-- 实施步骤 -->
    <el-card shadow="never" class="overview-card" v-if="suggestion.implementation_steps?.length">
      <template #header>
        <div class="card-header">
          <el-icon><List /></el-icon>
          <span>实施步骤</span>
        </div>
      </template>
      <el-timeline>
        <el-timeline-item
          v-for="step in suggestion.implementation_steps"
          :key="step.step"
          :timestamp="step.duration"
          placement="top"
        >
          <span class="step-number">步骤 {{ step.step }}</span>
          <p class="step-desc">{{ step.description }}</p>
        </el-timeline-item>
      </el-timeline>
    </el-card>

    <!-- 基本信息 -->
    <el-card shadow="never" class="overview-card">
      <template #header>
        <div class="card-header">
          <el-icon><InfoFilled /></el-icon>
          <span>基本信息</span>
        </div>
      </template>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="建议类型">
          <el-tag size="small">{{ categoryText[suggestion.category] || suggestion.category }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="优先级">
          <el-tag
            size="small"
            :type="priorityType[suggestion.priority]"
          >
            {{ priorityText[suggestion.priority] || suggestion.priority }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="实施难度">
          {{ difficultyText[suggestion.difficulty] || suggestion.difficulty }}
        </el-descriptions-item>
        <el-descriptions-item label="当前状态">
          <el-tag size="small" :type="statusType[suggestion.status]">
            {{ statusText[suggestion.status] || suggestion.status }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">
          {{ formatTime(suggestion.created_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="模板ID">
          {{ suggestion.template_id || '-' }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  WarningFilled, DataAnalysis, TrendCharts, List, InfoFilled
} from '@element-plus/icons-vue'
import type { SuggestionDetail } from '@/api/modules/energy'

const props = defineProps<{
  suggestion: SuggestionDetail
}>()

const parameters = computed(() => props.suggestion.parameters)
const dataSource = computed(() => props.suggestion.data_sources?.pricing)

const hasPricingData = computed(() => {
  const p = parameters.value
  return p && (p.sharp_price || p.peak_price || p.valley_price || p.price_diff)
})

const categoryText: Record<string, string> = {
  pue: 'PUE优化',
  cost: '成本优化',
  demand: '需量管理',
  efficiency: '效率提升',
  peak_valley: '峰谷优化'
}

const priorityText: Record<string, string> = {
  urgent: '紧急',
  high: '高',
  medium: '中',
  low: '低'
}

const priorityType: Record<string, 'danger' | 'warning' | 'info' | 'success' | 'primary'> = {
  urgent: 'danger',
  high: 'danger',
  medium: 'warning',
  low: 'info'
}

const difficultyText: Record<string, string> = {
  easy: '简单',
  medium: '中等',
  hard: '困难'
}

const statusText: Record<string, string> = {
  pending: '待处理',
  accepted: '已接受',
  rejected: '已拒绝',
  completed: '已完成'
}

const statusType: Record<string, 'danger' | 'warning' | 'info' | 'success' | 'primary'> = {
  pending: 'primary',
  accepted: 'warning',
  rejected: 'danger',
  completed: 'success'
}

function formatTime(time?: string) {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}
</script>

<style scoped lang="scss">
.suggestion-overview {
  .overview-card {
    margin-bottom: 16px;
    background: var(--bg-card-solid, #1a2a4a);

    .card-header {
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 500;
    }
  }

  .problem-content,
  .analysis-content,
  .effect-content {
    line-height: 1.8;
    color: var(--text-regular, rgba(255, 255, 255, 0.85));
  }

  .pricing-info {
    margin-top: 16px;

    .data-source-alert {
      margin-top: 12px;
    }
  }

  .highlight {
    color: var(--success-color, #52c41a);
    font-weight: bold;
  }

  .effect-stats {
    margin-top: 20px;
    text-align: center;
  }

  .step-number {
    font-weight: bold;
    color: var(--primary-color, #1890ff);
  }

  .step-desc {
    margin-top: 4px;
    color: var(--text-regular, rgba(255, 255, 255, 0.85));
  }
}
</style>
