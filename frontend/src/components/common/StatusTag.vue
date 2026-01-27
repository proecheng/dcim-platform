<template>
  <el-tag
    :type="tagType"
    :effect="effect"
    :size="size"
    :round="round"
    :class="['status-tag', { 'is-flash': flash }]"
  >
    <span v-if="showDot" class="status-tag__dot" :style="{ backgroundColor: dotColor }"></span>
    <span class="status-tag__text">{{ displayText }}</span>
  </el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'

type StatusType = 'success' | 'warning' | 'danger' | 'info' | 'primary' | ''

interface StatusConfig {
  type: StatusType
  text: string
  color?: string
  flash?: boolean
}

interface Props {
  status?: string | number | boolean
  statusMap?: Record<string, StatusConfig>
  type?: StatusType
  text?: string
  effect?: 'light' | 'dark' | 'plain'
  size?: 'large' | 'default' | 'small'
  round?: boolean
  showDot?: boolean
  flash?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  effect: 'light',
  size: 'default',
  round: false,
  showDot: false,
  flash: false
})

// 预定义状态映射
const defaultStatusMap: Record<string, StatusConfig> = {
  // 通用状态
  'true': { type: 'success', text: '是' },
  'false': { type: 'info', text: '否' },
  '1': { type: 'success', text: '是' },
  '0': { type: 'info', text: '否' },

  // 启用/禁用
  'enabled': { type: 'success', text: '启用' },
  'disabled': { type: 'info', text: '禁用' },

  // 在线/离线
  'online': { type: 'success', text: '在线' },
  'offline': { type: 'danger', text: '离线' },
  'maintenance': { type: 'warning', text: '维护中' },

  // 告警级别
  'critical': { type: 'danger', text: '紧急', flash: true },
  'major': { type: 'warning', text: '重要' },
  'minor': { type: 'primary', text: '次要' },
  'info': { type: 'info', text: '提示' },

  // 告警状态
  'active': { type: 'danger', text: '活动', flash: true },
  'acknowledged': { type: 'warning', text: '已确认' },
  'resolved': { type: 'success', text: '已解决' },
  'ignored': { type: 'info', text: '已忽略' },

  // 数据质量
  'normal': { type: 'success', text: '正常' },
  'alarm': { type: 'danger', text: '告警', flash: true },

  // 任务状态
  'pending': { type: 'info', text: '待处理' },
  'processing': { type: 'primary', text: '处理中' },
  'completed': { type: 'success', text: '已完成' },
  'failed': { type: 'danger', text: '失败' },

  // 报表状态
  'generating': { type: 'primary', text: '生成中' },

  // 通讯状态
  'success': { type: 'success', text: '成功' },
  'timeout': { type: 'warning', text: '超时' }
}

const statusConfig = computed(() => {
  const statusKey = String(props.status)
  const mergedMap = { ...defaultStatusMap, ...props.statusMap }
  return mergedMap[statusKey] || { type: 'info' as StatusType, text: statusKey, color: undefined, flash: false }
})

const tagType = computed(() => {
  const type = props.type || statusConfig.value.type
  // Ensure we return a valid tag type, default to 'info' if empty
  return type || 'info'
})

const displayText = computed(() => {
  return props.text || statusConfig.value.text
})

const dotColor = computed(() => {
  if (statusConfig.value.color) {
    return statusConfig.value.color
  }
  // Use theme-aware colors matching CSS variables
  const colorMap: Record<StatusType, string> = {
    success: '#52c41a',  // var(--success-color)
    warning: '#faad14',  // var(--warning-color)
    danger: '#f5222d',   // var(--error-color)
    info: 'rgba(255, 255, 255, 0.65)',  // var(--text-secondary)
    primary: '#1890ff',  // var(--primary-color)
    '': 'rgba(255, 255, 255, 0.65)'
  }
  return colorMap[tagType.value]
})

const flash = computed(() => {
  return props.flash || statusConfig.value.flash
})
</script>

<style lang="scss" scoped>
.status-tag {
  &__dot {
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    margin-right: 4px;
    vertical-align: middle;
  }

  &__text {
    vertical-align: middle;
  }

  &.is-flash {
    animation: flash 1s infinite;
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
