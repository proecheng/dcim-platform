<template>
  <div class="calculation-details">
    <!-- 计算公式 -->
    <el-card shadow="never" class="formula-card">
      <template #header>
        <div class="card-header">
          <el-icon><Memo /></el-icon>
          <span>计算公式</span>
        </div>
      </template>
      <div class="formula-content">
        <div class="main-formula">
          {{ calculationFormula?.formula || '日收益 = 转移功率 × 转移时长 × (转出电价 - 转入电价)' }}
        </div>
      </div>
    </el-card>

    <!-- 数据来源 -->
    <el-card shadow="never" class="source-card">
      <template #header>
        <div class="card-header">
          <el-icon><Connection /></el-icon>
          <span>数据来源</span>
        </div>
      </template>
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item
          v-for="(value, key) in calculationFormula?.variables_from_db"
          :key="key"
          :label="key"
        >
          {{ value }}
        </el-descriptions-item>
      </el-descriptions>
      <el-alert
        type="info"
        :closable="false"
        class="source-tip"
      >
        <template #title>
          以上数据来自数据库，可在「系统设置 → 电价配置」中修改
        </template>
      </el-alert>
    </el-card>

    <!-- 计算步骤 -->
    <el-card shadow="never" class="steps-card">
      <template #header>
        <div class="card-header">
          <el-icon><List /></el-icon>
          <span>计算步骤</span>
        </div>
      </template>
      <el-timeline>
        <el-timeline-item
          v-for="step in calculationFormula?.steps"
          :key="step.step"
          :type="step.step === calculationFormula?.steps?.length ? 'success' : 'primary'"
          :hollow="step.step !== calculationFormula?.steps?.length"
        >
          <div class="step-content">
            <span class="step-label">步骤 {{ step.step }}</span>
            <p class="step-desc">{{ step.desc }}</p>
          </div>
        </el-timeline-item>
      </el-timeline>
    </el-card>

    <!-- 参数汇总 -->
    <el-card shadow="never" class="params-card">
      <template #header>
        <div class="card-header">
          <el-icon><Setting /></el-icon>
          <span>参数汇总</span>
        </div>
      </template>
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="总可调节容量">
          {{ parameters?.total_shiftable_power?.toFixed(1) || 0 }} kW
        </el-descriptions-item>
        <el-descriptions-item label="默认转移时长">
          {{ parameters?.default_shift_hours || 2 }} 小时
        </el-descriptions-item>
        <el-descriptions-item label="日转移电量">
          {{ ((parameters?.total_shiftable_power || 0) * (parameters?.default_shift_hours || 2)).toFixed(1) }} kWh
        </el-descriptions-item>
        <el-descriptions-item label="峰谷价差">
          <span class="highlight">{{ parameters?.price_diff?.toFixed(3) || 0 }} 元/kWh</span>
        </el-descriptions-item>
        <el-descriptions-item label="日节省">
          {{ parameters?.daily_saving?.toFixed(2) || 0 }} 元
        </el-descriptions-item>
        <el-descriptions-item label="年节省">
          <span class="highlight large">{{ ((parameters?.annual_saving || 0) / 10000).toFixed(2) }} 万元</span>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 数据溯源信息 -->
    <el-card shadow="never" class="trace-card" v-if="dataSources">
      <template #header>
        <div class="card-header">
          <el-icon><Document /></el-icon>
          <span>数据溯源</span>
        </div>
      </template>
      <div class="trace-content">
        <div class="trace-item">
          <span class="trace-label">电价数据来源:</span>
          <span class="trace-value">{{ parameters?.pricing_source || 'electricity_pricing表' }}</span>
        </div>
        <div class="trace-item">
          <span class="trace-label">设备数据来源:</span>
          <span class="trace-value">{{ parameters?.device_source || 'device_shift_configs表' }}</span>
        </div>
        <div class="trace-item" v-if="dataSources?.pricing?.config_count">
          <span class="trace-label">有效电价配置:</span>
          <span class="trace-value">{{ dataSources.pricing.config_count }} 条</span>
        </div>
        <div class="trace-item" v-if="dataSources?.devices?.shiftable_config_count">
          <span class="trace-label">可转移设备配置:</span>
          <span class="trace-value">{{ dataSources.devices.shiftable_config_count }} 条</span>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Memo, Connection, List, Setting, Document } from '@element-plus/icons-vue'
import type { SuggestionDetail, CalculationFormula } from '@/api/modules/energy'

const props = defineProps<{
  suggestion: SuggestionDetail
}>()

const parameters = computed(() => props.suggestion.parameters)
const calculationFormula = computed(() => props.suggestion.parameters?.calculation_formula as CalculationFormula | undefined)
const dataSources = computed(() => props.suggestion.data_sources)
</script>

<style scoped lang="scss">
.calculation-details {
  .formula-card,
  .source-card,
  .steps-card,
  .params-card,
  .trace-card {
    margin-bottom: 16px;
    background: var(--bg-card-solid, #1a2a4a);

    .card-header {
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 500;
    }
  }

  .formula-content {
    .main-formula {
      font-size: 16px;
      font-weight: 500;
      color: var(--primary-color, #1890ff);
      padding: 12px;
      background: rgba(24, 144, 255, 0.1);
      border-radius: 4px;
      text-align: center;
    }
  }

  .source-tip {
    margin-top: 12px;
  }

  .step-content {
    .step-label {
      font-weight: bold;
      color: var(--primary-color, #1890ff);
    }

    .step-desc {
      margin-top: 4px;
      color: var(--text-regular, rgba(255, 255, 255, 0.85));
      font-family: monospace;
    }
  }

  .highlight {
    color: var(--success-color, #52c41a);
    font-weight: bold;

    &.large {
      font-size: 16px;
    }
  }

  .trace-content {
    .trace-item {
      display: flex;
      padding: 8px 0;
      border-bottom: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));

      &:last-child {
        border-bottom: none;
      }

      .trace-label {
        width: 120px;
        color: var(--text-secondary, rgba(255, 255, 255, 0.65));
      }

      .trace-value {
        flex: 1;
        color: var(--text-regular, rgba(255, 255, 255, 0.85));
        font-family: monospace;
      }
    }
  }
}
</style>
