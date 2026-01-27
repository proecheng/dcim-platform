<template>
  <div class="status-panel">
    <div class="status-panel__header">
      <span class="status-panel__title">{{ title }}</span>
      <el-button
        v-if="showRefresh"
        :icon="Refresh"
        circle
        size="small"
        :loading="loading"
        @click="$emit('refresh')"
      />
    </div>

    <div class="status-panel__content">
      <div
        v-for="item in items"
        :key="item.key"
        class="status-panel__item"
        :class="{ 'status-panel__item--clickable': item.clickable }"
        @click="handleItemClick(item)"
      >
        <div class="status-panel__item-icon" :style="{ backgroundColor: item.color }">
          <el-icon v-if="item.icon">
            <component :is="item.icon" />
          </el-icon>
          <span v-else>{{ item.label.charAt(0) }}</span>
        </div>
        <div class="status-panel__item-info">
          <div class="status-panel__item-label">{{ item.label }}</div>
          <div class="status-panel__item-value">
            <ValueDisplay
              :value="item.value"
              :unit="item.unit"
              :status="item.status"
              size="default"
              :animate="animate"
            />
          </div>
        </div>
        <div v-if="item.trend" class="status-panel__item-trend">
          <el-icon :class="getTrendClass(item.trend)">
            <CaretTop v-if="item.trend === 'up'" />
            <CaretBottom v-if="item.trend === 'down'" />
          </el-icon>
          <span v-if="item.trendValue" class="status-panel__item-trend-value">
            {{ item.trendValue }}%
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Component } from 'vue'
import { Refresh, CaretTop, CaretBottom } from '@element-plus/icons-vue'
import ValueDisplay from './ValueDisplay.vue'

interface StatusItem {
  key: string
  label: string
  value: number | string
  unit?: string
  icon?: Component
  color?: string
  status?: 'normal' | 'alarm' | 'offline'
  trend?: 'up' | 'down' | 'stable'
  trendValue?: number
  clickable?: boolean
}

interface Props {
  title?: string
  items: StatusItem[]
  showRefresh?: boolean
  loading?: boolean
  animate?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  title: '状态面板',
  showRefresh: true,
  loading: false,
  animate: true
})

const emit = defineEmits<{
  (e: 'refresh'): void
  (e: 'item-click', item: StatusItem): void
}>()

const getTrendClass = (trend: string) => ({
  'status-panel__item-trend-icon': true,
  'status-panel__item-trend-icon--up': trend === 'up',
  'status-panel__item-trend-icon--down': trend === 'down'
})

const handleItemClick = (item: StatusItem) => {
  if (item.clickable) {
    emit('item-click', item)
  }
}
</script>

<style lang="scss" scoped>
.status-panel {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  overflow: hidden;

  &__header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    border-bottom: 1px solid var(--el-border-color);
  }

  &__title {
    font-weight: 500;
    font-size: 14px;
    color: var(--el-text-color-primary);
  }

  &__content {
    padding: 8px;
  }

  &__item {
    display: flex;
    align-items: center;
    padding: 12px;
    border-radius: 6px;
    transition: background-color 0.3s;

    &--clickable {
      cursor: pointer;

      &:hover {
        background: var(--el-fill-color-light);
      }
    }

    & + & {
      margin-top: 4px;
    }
  }

  &__item-icon {
    width: 40px;
    height: 40px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-weight: 500;
    flex-shrink: 0;
  }

  &__item-info {
    flex: 1;
    margin-left: 12px;
    min-width: 0;
  }

  &__item-label {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    margin-bottom: 4px;
  }

  &__item-value {
    font-size: 18px;
    font-weight: 600;
    color: var(--el-text-color-primary);
  }

  &__item-trend {
    display: flex;
    align-items: center;
    margin-left: 12px;
  }

  &__item-trend-icon {
    font-size: 16px;

    &--up {
      color: var(--el-color-danger);
    }

    &--down {
      color: var(--el-color-success);
    }
  }

  &__item-trend-value {
    font-size: 12px;
    margin-left: 2px;
  }
}
</style>
