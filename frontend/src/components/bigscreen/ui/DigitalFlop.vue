<!-- frontend/src/components/bigscreen/ui/DigitalFlop.vue -->
<template>
  <div class="digital-flop" :class="[sizeClass, { 'has-trend': showTrend }]">
    <span ref="countRef" class="value">{{ displayValue }}</span>
    <span v-if="suffix" class="suffix">{{ suffix }}</span>
    <span v-if="showTrend && trend !== 0" class="trend" :class="trendClass">
      <el-icon v-if="trend > 0"><ArrowUp /></el-icon>
      <el-icon v-else><ArrowDown /></el-icon>
      <span class="trend-value">{{ Math.abs(trend).toFixed(1) }}%</span>
    </span>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, computed } from 'vue'
import { CountUp } from 'countup.js'
import { ArrowUp, ArrowDown } from '@element-plus/icons-vue'

const props = withDefaults(defineProps<{
  value: number
  decimals?: number
  suffix?: string
  duration?: number
  size?: 'small' | 'medium' | 'large' | 'xlarge'
  showTrend?: boolean
  trend?: number
  separator?: string
  prefix?: string
}>(), {
  decimals: 0,
  suffix: '',
  duration: 1.5,
  size: 'medium',
  showTrend: false,
  trend: 0,
  separator: ',',
  prefix: ''
})

const countRef = ref<HTMLElement | null>(null)
const displayValue = ref('0')
let countUp: CountUp | null = null

const sizeClass = computed(() => `size-${props.size}`)

const trendClass = computed(() => {
  if (props.trend > 0) return 'trend-up'
  if (props.trend < 0) return 'trend-down'
  return ''
})

function initCountUp() {
  if (!countRef.value) return

  countUp = new CountUp(countRef.value, props.value, {
    decimalPlaces: props.decimals,
    duration: props.duration,
    separator: props.separator,
    prefix: props.prefix,
    useEasing: true,
    useGrouping: true,
    enableScrollSpy: false
  })

  if (!countUp.error) {
    countUp.start()
  } else {
    displayValue.value = props.value.toFixed(props.decimals)
  }
}

function updateValue(newValue: number) {
  if (countUp) {
    countUp.update(newValue)
  } else {
    displayValue.value = newValue.toFixed(props.decimals)
  }
}

watch(() => props.value, (newValue) => {
  updateValue(newValue)
})

onMounted(() => {
  initCountUp()
})
</script>

<style scoped lang="scss">
.digital-flop {
  display: inline-flex;
  align-items: baseline;
  font-family: 'DIN Alternate', 'Helvetica Neue', Arial, sans-serif;
  color: #00ccff;

  .value {
    font-weight: bold;
    letter-spacing: 0.02em;
    text-shadow: 0 0 10px rgba(0, 204, 255, 0.5);
  }

  .suffix {
    font-size: 0.6em;
    color: #8899aa;
    margin-left: 4px;
    font-weight: normal;
  }

  .trend {
    display: inline-flex;
    align-items: center;
    margin-left: 8px;
    font-size: 0.5em;
    padding: 2px 6px;
    border-radius: 4px;

    .el-icon {
      margin-right: 2px;
    }

    &.trend-up {
      color: #ff4d4f;
      background: rgba(255, 77, 79, 0.15);
    }

    &.trend-down {
      color: #52c41a;
      background: rgba(82, 196, 26, 0.15);
    }
  }

  // Size variants
  &.size-small {
    .value {
      font-size: 18px;
    }
  }

  &.size-medium {
    .value {
      font-size: 24px;
    }
  }

  &.size-large {
    .value {
      font-size: 32px;
    }
  }

  &.size-xlarge {
    .value {
      font-size: 48px;
    }
  }
}
</style>
