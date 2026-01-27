<template>
  <div
    class="point-card"
    :class="[
      `point-card--${status}`,
      { 'point-card--clickable': clickable }
    ]"
    @click="handleClick"
  >
    <!-- 头部 -->
    <div class="point-card__header">
      <div class="point-card__title">
        <span class="point-card__name">{{ name }}</span>
        <el-tag :type="pointTypeTag" size="small">{{ pointType }}</el-tag>
      </div>
      <div class="point-card__status">
        <span class="point-card__dot" :class="`point-card__dot--${status}`"></span>
        <span class="point-card__status-text">{{ statusText }}</span>
      </div>
    </div>

    <!-- 数值显示 -->
    <div class="point-card__value">
      <ValueDisplay
        :value="value"
        :unit="unit"
        :precision="precision"
        :status="status"
        :trend="trend"
        :animate="animate"
        size="large"
      />
    </div>

    <!-- 底部信息 -->
    <div class="point-card__footer">
      <div class="point-card__info">
        <span class="point-card__code">{{ code }}</span>
        <span class="point-card__time">{{ updateTimeText }}</span>
      </div>
      <div v-if="showActions" class="point-card__actions">
        <el-button
          v-if="showHistory"
          :icon="DataLine"
          circle
          size="small"
          @click.stop="$emit('history', pointId)"
        />
        <el-button
          v-if="showControl && (pointType === 'AO' || pointType === 'DO')"
          :icon="Setting"
          circle
          size="small"
          @click.stop="$emit('control', pointId)"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { DataLine, Setting } from '@element-plus/icons-vue'
import ValueDisplay from './ValueDisplay.vue'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/zh-cn'

dayjs.extend(relativeTime)
dayjs.locale('zh-cn')

interface Props {
  pointId: number
  code: string
  name: string
  pointType: 'AI' | 'DI' | 'AO' | 'DO'
  value: number
  unit?: string
  precision?: number
  status?: 'normal' | 'alarm' | 'offline'
  trend?: 'up' | 'down' | 'stable'
  updatedAt?: string
  clickable?: boolean
  animate?: boolean
  showActions?: boolean
  showHistory?: boolean
  showControl?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  precision: 2,
  status: 'normal',
  clickable: true,
  animate: true,
  showActions: true,
  showHistory: true,
  showControl: true
})

const emit = defineEmits<{
  (e: 'click', pointId: number): void
  (e: 'history', pointId: number): void
  (e: 'control', pointId: number): void
}>()

const pointTypeTag = computed(() => {
  const map: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    'AI': 'success',
    'DI': 'info',
    'AO': 'warning',
    'DO': 'danger'
  }
  return map[props.pointType] || 'info'
})

const statusText = computed(() => {
  const map: Record<string, string> = {
    'normal': '正常',
    'alarm': '告警',
    'offline': '离线'
  }
  return map[props.status] || '未知'
})

const updateTimeText = computed(() => {
  if (!props.updatedAt) return ''
  return dayjs(props.updatedAt).fromNow()
})

const handleClick = () => {
  if (props.clickable) {
    emit('click', props.pointId)
  }
}
</script>

<style lang="scss" scoped>
.point-card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 16px;
  transition: all 0.3s;

  &--clickable {
    cursor: pointer;

    &:hover {
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
      transform: translateY(-2px);
    }
  }

  &--alarm {
    border-color: var(--el-color-danger);
    background: rgba(245, 108, 108, 0.05);
  }

  &--offline {
    border-color: var(--el-color-info);
    opacity: 0.7;
  }

  &__header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }

  &__title {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  &__name {
    font-weight: 500;
    font-size: 14px;
    color: var(--el-text-color-primary);
  }

  &__status {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  &__dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;

    &--normal {
      background: var(--el-color-success);
    }

    &--alarm {
      background: var(--el-color-danger);
      animation: flash 1s infinite;
    }

    &--offline {
      background: var(--el-color-info);
    }
  }

  &__status-text {
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }

  &__value {
    padding: 16px 0;
    text-align: center;
  }

  &__footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 12px;
    border-top: 1px dashed var(--el-border-color);
  }

  &__info {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  &__code {
    font-size: 11px;
    color: var(--el-text-color-secondary);
    font-family: monospace;
  }

  &__time {
    font-size: 11px;
    color: var(--el-text-color-placeholder);
  }

  &__actions {
    display: flex;
    gap: 4px;
  }
}

@keyframes flash {
  0%, 50%, 100% {
    opacity: 1;
  }
  25%, 75% {
    opacity: 0.3;
  }
}
</style>
