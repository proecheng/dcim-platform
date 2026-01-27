<template>
  <div
    class="value-display"
    :class="[
      `value-display--${size}`,
      `value-display--${status}`,
      { 'value-display--animate': animate }
    ]"
  >
    <span class="value-display__value" ref="valueRef">
      {{ displayValue }}
    </span>
    <span v-if="unit" class="value-display__unit">{{ unit }}</span>
    <span v-if="trend && trend !== 'stable'" class="value-display__trend">
      <el-icon :class="trendClass">
        <CaretTop v-if="trend === 'up'" />
        <CaretBottom v-if="trend === 'down'" />
      </el-icon>
    </span>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { CaretTop, CaretBottom } from '@element-plus/icons-vue'

interface Props {
  value: number | string
  unit?: string
  precision?: number
  size?: 'small' | 'default' | 'large' | 'xlarge'
  status?: 'normal' | 'alarm' | 'offline'
  trend?: 'up' | 'down' | 'stable'
  animate?: boolean
  animationDuration?: number
}

const props = withDefaults(defineProps<Props>(), {
  precision: 2,
  size: 'default',
  status: 'normal',
  animate: true,
  animationDuration: 500
})

const valueRef = ref<HTMLElement>()
const animatedValue = ref<number>(0)
const previousValue = ref<number>(0)

const displayValue = computed(() => {
  if (typeof props.value === 'string') {
    return props.value
  }

  const val = props.animate ? animatedValue.value : props.value

  if (typeof val === 'number' && !isNaN(val)) {
    return val.toFixed(props.precision)
  }

  return '--'
})

const trendClass = computed(() => ({
  'value-display__trend-icon': true,
  'value-display__trend-icon--up': props.trend === 'up',
  'value-display__trend-icon--down': props.trend === 'down'
}))

// 数值动画
const animateValue = (from: number, to: number) => {
  if (!props.animate || typeof to !== 'number' || isNaN(to)) {
    animatedValue.value = to
    return
  }

  const startTime = performance.now()
  const duration = props.animationDuration

  const step = (currentTime: number) => {
    const elapsed = currentTime - startTime
    const progress = Math.min(elapsed / duration, 1)

    // 使用缓动函数
    const easeProgress = 1 - Math.pow(1 - progress, 3)
    animatedValue.value = from + (to - from) * easeProgress

    if (progress < 1) {
      requestAnimationFrame(step)
    }
  }

  requestAnimationFrame(step)
}

watch(() => props.value, (newVal, oldVal) => {
  if (typeof newVal === 'number') {
    previousValue.value = typeof oldVal === 'number' ? oldVal : 0
    animateValue(previousValue.value, newVal)
  }
})

onMounted(() => {
  if (typeof props.value === 'number') {
    animatedValue.value = props.value
  }
})
</script>

<style lang="scss" scoped>
.value-display {
  display: inline-flex;
  align-items: baseline;
  font-family: 'Roboto Mono', monospace;

  &--small {
    .value-display__value {
      font-size: 18px;
    }
    .value-display__unit {
      font-size: 12px;
    }
  }

  &--default {
    .value-display__value {
      font-size: 24px;
    }
    .value-display__unit {
      font-size: 14px;
    }
  }

  &--large {
    .value-display__value {
      font-size: 32px;
    }
    .value-display__unit {
      font-size: 16px;
    }
  }

  &--xlarge {
    .value-display__value {
      font-size: 48px;
    }
    .value-display__unit {
      font-size: 20px;
    }
  }

  &--normal {
    .value-display__value {
      color: var(--el-text-color-primary);
    }
  }

  &--alarm {
    .value-display__value {
      color: var(--el-color-danger);
    }
  }

  &--offline {
    .value-display__value {
      color: var(--el-text-color-placeholder);
    }
  }

  &__value {
    font-weight: 600;
    line-height: 1;
    transition: color 0.3s;
  }

  &__unit {
    margin-left: 4px;
    color: var(--el-text-color-secondary);
  }

  &__trend {
    margin-left: 8px;
  }

  &__trend-icon {
    font-size: 16px;

    &--up {
      color: var(--el-color-danger);
    }

    &--down {
      color: var(--el-color-success);
    }
  }
}
</style>
