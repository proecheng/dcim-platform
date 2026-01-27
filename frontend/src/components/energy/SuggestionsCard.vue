<template>
  <el-card class="suggestions-card" shadow="hover" @click="$router.push('/energy/analysis?tab=overview')">
    <div class="card-header">
      <div class="header-left">
        <el-icon :size="20" color="#909399"><List /></el-icon>
        <span class="title">节能建议</span>
      </div>
      <el-badge :value="pendingCount" :hidden="!pendingCount || pendingCount === 0" type="danger" />
    </div>

    <div class="card-body">
      <div class="main-display">
        <span class="value">{{ pendingCount || 0 }}</span>
        <span class="unit">条待处理</span>
      </div>

      <div class="priority-list" v-if="highPriorityCount && highPriorityCount > 0">
        <el-tag type="danger" size="small" effect="light">
          {{ highPriorityCount }} 条高优先级
        </el-tag>
      </div>

      <div class="saving-info" v-if="potentialSaving && potentialSaving > 0">
        <el-icon :size="14" color="#67C23A"><TrendCharts /></el-icon>
        <span>可节省 ¥{{ potentialSaving?.toFixed(0) }}/月</span>
      </div>

      <div class="recent-suggestions" v-if="recentSuggestions && recentSuggestions.length > 0">
        <div
          v-for="(item, index) in recentSuggestions.slice(0, 2)"
          :key="index"
          class="suggestion-item"
        >
          <el-icon :size="12" :color="getPriorityColor(item.priority)"><Warning /></el-icon>
          <span class="text">{{ item.title }}</span>
        </div>
      </div>

      <div class="footer">
        <span class="action-hint">点击查看详情 →</span>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { List, Warning, TrendCharts } from '@element-plus/icons-vue'

interface Suggestion {
  title: string
  priority: 'high' | 'medium' | 'low'
}

defineProps<{
  pendingCount?: number
  highPriorityCount?: number
  potentialSaving?: number
  recentSuggestions?: Suggestion[]
}>()

// Theme colors for dynamic icon colors
const themeColors = {
  error: '#f5222d',
  warning: '#faad14',
  secondary: 'rgba(255, 255, 255, 0.65)'
}

const getPriorityColor = (priority: string) => {
  switch (priority) {
    case 'high': return themeColors.error
    case 'medium': return themeColors.warning
    default: return themeColors.secondary
  }
}
</script>

<style scoped lang="scss">
.suggestions-card {
  cursor: pointer;
  transition: all 0.3s;
  background-color: var(--bg-card-solid, #1a2a4a);
  border-color: var(--border-color, rgba(255, 255, 255, 0.1));

  &:hover {
    transform: translateY(-2px);

    .action-hint {
      color: var(--primary-color, #1890ff);
    }
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

    .title { font-size: 14px; color: var(--text-regular, rgba(255, 255, 255, 0.85)); }
  }

  .card-body {
    .main-display {
      display: flex;
      align-items: baseline;
      gap: 4px;
      margin-bottom: 8px;

      .value { font-size: 28px; font-weight: bold; color: var(--text-primary, rgba(255, 255, 255, 0.95)); }
      .unit { font-size: 14px; color: var(--text-secondary, rgba(255, 255, 255, 0.65)); }
    }

    .priority-list {
      margin: 8px 0;
    }

    .saving-info {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 13px;
      color: var(--success-color, #52c41a);
      margin: 8px 0;
    }

    .recent-suggestions {
      margin: 8px 0;

      .suggestion-item {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 12px;
        color: var(--text-regular, rgba(255, 255, 255, 0.85));
        padding: 4px 0;
        border-bottom: 1px dashed var(--border-color, rgba(255, 255, 255, 0.1));

        &:last-child {
          border-bottom: none;
        }

        .text {
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      }
    }

    .footer {
      margin-top: 8px;

      .action-hint {
        font-size: 12px;
        color: var(--text-placeholder, rgba(255, 255, 255, 0.45));
        transition: color 0.3s;
      }
    }
  }
}
</style>
