<template>
  <div
    class="alarm-badge"
    :class="[
      `alarm-badge--${level}`,
      { 'alarm-badge--flash': flash }
    ]"
    @click="handleClick"
  >
    <el-icon v-if="showIcon" class="alarm-badge__icon">
      <WarningFilled />
    </el-icon>
    <span class="alarm-badge__count">{{ displayCount }}</span>
    <span v-if="showLabel" class="alarm-badge__label">{{ levelLabel }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { WarningFilled } from '@element-plus/icons-vue'

interface Props {
  count: number
  level?: 'critical' | 'major' | 'minor' | 'info'
  showIcon?: boolean
  showLabel?: boolean
  flash?: boolean
  max?: number
}

const props = withDefaults(defineProps<Props>(), {
  level: 'major',
  showIcon: true,
  showLabel: false,
  flash: false,
  max: 99
})

const emit = defineEmits<{
  (e: 'click'): void
}>()

const displayCount = computed(() => {
  if (props.count > props.max) {
    return `${props.max}+`
  }
  return props.count
})

const levelLabel = computed(() => {
  const map: Record<string, string> = {
    critical: '紧急',
    major: '重要',
    minor: '次要',
    info: '提示'
  }
  return map[props.level] || ''
})

const handleClick = () => {
  emit('click')
}
</script>

<style lang="scss" scoped>
.alarm-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.3s;

  &:hover {
    opacity: 0.8;
  }

  &--critical {
    background: var(--el-color-danger);
    color: white;
  }

  &--major {
    background: var(--el-color-warning);
    color: white;
  }

  &--minor {
    background: var(--el-color-primary);
    color: white;
  }

  &--info {
    background: var(--el-color-info);
    color: white;
  }

  &--flash {
    animation: flash 1s infinite;
  }

  &__icon {
    margin-right: 4px;
  }

  &__count {
    font-weight: 600;
  }

  &__label {
    margin-left: 4px;
    font-size: 12px;
    opacity: 0.9;
  }
}

@keyframes flash {
  0%, 50%, 100% {
    opacity: 1;
  }
  25%, 75% {
    opacity: 0.5;
  }
}
</style>
