<template>
  <div class="metric-display" v-if="metric">
    <div class="metric-value">
      <span class="value">{{ formatValue(metric.value) }}</span>
      <span v-if="metric.unit" class="unit">{{ metric.unit }}</span>
      <el-tooltip placement="top" :show-after="300">
        <template #content>
          <div class="metric-tooltip">
            <div class="tooltip-section">
              <strong>计算公式:</strong>
              <div class="formula">{{ metric.formula }}</div>
            </div>
            <div v-if="metric.data_source" class="tooltip-section">
              <strong>数据来源:</strong>
              <pre class="data-source">{{ formatDataSource(metric.data_source) }}</pre>
            </div>
            <div v-if="metric.typical_range" class="tooltip-section">
              <strong>典型范围:</strong>
              <span class="typical-range">{{ metric.typical_range }}</span>
            </div>
            <div v-if="metric.description" class="tooltip-section">
              <strong>说明:</strong>
              <span>{{ metric.description }}</span>
            </div>
            <div v-if="metric.parameters" class="tooltip-section">
              <strong>参数:</strong>
              <pre class="data-source">{{ formatDataSource(metric.parameters) }}</pre>
            </div>
          </div>
        </template>
        <el-icon class="info-icon">
          <InfoFilled />
        </el-icon>
      </el-tooltip>
    </div>
  </div>
  <span v-else class="no-data">--</span>
</template>

<script setup lang="ts">
import { InfoFilled } from '@element-plus/icons-vue'

interface MetricValue {
  value: number
  unit?: string
  formula?: string
  data_source?: any
  typical_range?: string
  description?: string
  parameters?: any
}

const props = defineProps<{
  metric: MetricValue | null | undefined
}>()

const formatValue = (value: number): string => {
  if (value === null || value === undefined || isNaN(value)) {
    return '--'
  }

  // 格式化数字，添加千分位分隔符
  if (Math.abs(value) >= 1000) {
    return value.toLocaleString('zh-CN', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 2
    })
  }

  return value.toFixed(2)
}

const formatDataSource = (data: any): string => {
  if (typeof data === 'string') {
    return data
  }
  return JSON.stringify(data, null, 2)
}
</script>

<style lang="scss" scoped>
.metric-display {
  display: inline-flex;
  align-items: center;

  .metric-value {
    display: flex;
    align-items: center;
    gap: 8px;

    .value {
      font-size: 16px;
      font-weight: 600;
      color: var(--el-text-color-primary);
      font-family: 'Roboto Mono', monospace;
    }

    .unit {
      font-size: 14px;
      color: var(--el-text-color-secondary);
      margin-left: 4px;
    }

    .info-icon {
      color: var(--el-color-info);
      cursor: help;
      font-size: 16px;

      &:hover {
        color: var(--el-color-primary);
      }
    }
  }
}

.no-data {
  color: var(--el-text-color-placeholder);
  font-style: italic;
}

.metric-tooltip {
  max-width: 400px;

  .tooltip-section {
    margin-bottom: 12px;

    &:last-child {
      margin-bottom: 0;
    }

    strong {
      display: block;
      margin-bottom: 4px;
      color: var(--el-color-primary);
    }

    .formula {
      padding: 8px;
      background-color: rgba(0, 0, 0, 0.1);
      border-radius: 4px;
      font-family: 'Courier New', monospace;
      font-size: 13px;
      word-break: break-word;
    }

    .data-source {
      padding: 8px;
      background-color: rgba(0, 0, 0, 0.1);
      border-radius: 4px;
      font-family: 'Courier New', monospace;
      font-size: 12px;
      margin: 0;
      overflow-x: auto;
      max-height: 200px;
    }

    .typical-range {
      color: var(--el-color-success);
      font-weight: 500;
    }
  }
}
</style>
