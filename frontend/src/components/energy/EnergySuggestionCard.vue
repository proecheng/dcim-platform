<template>
  <el-card class="suggestion-card" :class="`priority-${priority}`" shadow="hover">
    <div class="card-header">
      <div class="priority-badge">
        <el-tag :type="priorityType" size="small">{{ priorityText }}</el-tag>
      </div>
      <div class="status-badge">
        <el-tag :type="statusType" size="small" effect="plain">{{ statusText }}</el-tag>
      </div>
    </div>

    <div class="card-body">
      <div class="rule-name">{{ ruleName }}</div>
      <div class="suggestion-text">{{ suggestion }}</div>

      <div class="saving-info" v-if="potentialSaving || potentialCostSaving">
        <div class="saving-item" v-if="potentialSaving">
          <el-icon><Lightning /></el-icon>
          <span>预计节省 {{ potentialSaving.toFixed(1) }} kWh/月</span>
        </div>
        <div class="saving-item" v-if="potentialCostSaving">
          <el-icon><Money /></el-icon>
          <span>预计节省 {{ potentialCostSaving.toFixed(2) }} 元/月</span>
        </div>
      </div>

      <div class="trigger-info" v-if="triggerValue !== undefined">
        <span class="label">触发值:</span>
        <span class="value">{{ triggerValue }}</span>
        <span class="threshold" v-if="thresholdValue !== undefined">
          (阈值: {{ thresholdValue }})
        </span>
      </div>
    </div>

    <div class="card-footer" v-if="status === 'pending'">
      <el-button type="primary" size="small" @click="handleAccept">
        <el-icon><Check /></el-icon>
        接受
      </el-button>
      <el-button type="danger" size="small" plain @click="handleReject">
        <el-icon><Close /></el-icon>
        拒绝
      </el-button>
    </div>

    <div class="card-footer" v-else-if="status === 'accepted'">
      <el-button type="success" size="small" @click="handleComplete">
        <el-icon><Select /></el-icon>
        标记完成
      </el-button>
    </div>

    <div class="completed-info" v-else-if="status === 'completed'">
      <el-icon class="success-icon"><CircleCheck /></el-icon>
      <span>已完成</span>
      <span v-if="actualSaving" class="actual-saving">
        实际节省: {{ actualSaving.toFixed(1) }} kWh
      </span>
    </div>

    <div class="rejected-info" v-else-if="status === 'rejected'">
      <el-icon class="reject-icon"><CircleClose /></el-icon>
      <span>已拒绝</span>
      <span v-if="remark" class="remark">{{ remark }}</span>
    </div>

    <div class="time-info">
      <span>{{ formatTime(createdAt) }}</span>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  Lightning, Money, Check, Close, Select,
  CircleCheck, CircleClose
} from '@element-plus/icons-vue'
import dayjs from 'dayjs'

const props = defineProps<{
  id: number
  ruleName?: string
  suggestion: string
  priority: 'high' | 'medium' | 'low'
  status: 'pending' | 'accepted' | 'rejected' | 'completed'
  potentialSaving?: number
  potentialCostSaving?: number
  triggerValue?: number
  thresholdValue?: number
  actualSaving?: number
  remark?: string
  createdAt: string
}>()

const emit = defineEmits<{
  accept: [id: number]
  reject: [id: number]
  complete: [id: number]
}>()

// 优先级类型
const priorityType = computed(() => {
  switch (props.priority) {
    case 'high': return 'danger'
    case 'medium': return 'warning'
    case 'low': return 'info'
    default: return 'info'
  }
})

// 优先级文本
const priorityText = computed(() => {
  switch (props.priority) {
    case 'high': return '高'
    case 'medium': return '中'
    case 'low': return '低'
    default: return '未知'
  }
})

// 状态类型
const statusType = computed(() => {
  switch (props.status) {
    case 'pending': return 'warning'
    case 'accepted': return 'primary'
    case 'rejected': return 'info'
    case 'completed': return 'success'
    default: return 'info'
  }
})

// 状态文本
const statusText = computed(() => {
  switch (props.status) {
    case 'pending': return '待处理'
    case 'accepted': return '已接受'
    case 'rejected': return '已拒绝'
    case 'completed': return '已完成'
    default: return '未知'
  }
})

// 格式化时间
function formatTime(time: string): string {
  return dayjs(time).format('YYYY-MM-DD HH:mm')
}

// 处理接受
function handleAccept() {
  emit('accept', props.id)
}

// 处理拒绝
function handleReject() {
  emit('reject', props.id)
}

// 处理完成
function handleComplete() {
  emit('complete', props.id)
}
</script>

<style scoped lang="scss">
.suggestion-card {
  margin-bottom: 12px;
  transition: all 0.3s;
  background-color: var(--bg-card-solid, #1a2a4a);
  border-color: var(--border-color, rgba(255, 255, 255, 0.1));

  &.priority-high {
    border-left: 4px solid var(--error-color, #f5222d);
  }

  &.priority-medium {
    border-left: 4px solid var(--warning-color, #faad14);
  }

  &.priority-low {
    border-left: 4px solid var(--text-secondary, rgba(255, 255, 255, 0.65));
  }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.card-body {
  margin-bottom: 12px;
}

.rule-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, rgba(255, 255, 255, 0.95));
  margin-bottom: 8px;
}

.suggestion-text {
  font-size: 13px;
  color: var(--text-regular, rgba(255, 255, 255, 0.85));
  line-height: 1.6;
  margin-bottom: 12px;
}

.saving-info {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  padding: 8px 12px;
  background: rgba(82, 196, 26, 0.1);
  border-radius: 4px;
  margin-bottom: 8px;
}

.saving-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--success-color, #52c41a);
}

.trigger-info {
  font-size: 12px;
  color: var(--text-secondary, rgba(255, 255, 255, 0.65));

  .value {
    color: var(--error-color, #f5222d);
    font-weight: 600;
    margin-left: 4px;
  }

  .threshold {
    margin-left: 8px;
  }
}

.card-footer {
  display: flex;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
}

.completed-info,
.rejected-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
  font-size: 13px;
  color: var(--text-regular, rgba(255, 255, 255, 0.85));
}

.success-icon {
  color: var(--success-color, #52c41a);
  font-size: 16px;
}

.reject-icon {
  color: var(--text-secondary, rgba(255, 255, 255, 0.65));
  font-size: 16px;
}

.actual-saving {
  margin-left: auto;
  color: var(--success-color, #52c41a);
  font-weight: 500;
}

.remark {
  margin-left: auto;
  color: var(--text-secondary, rgba(255, 255, 255, 0.65));
  font-style: italic;
}

.time-info {
  margin-top: 8px;
  font-size: 11px;
  color: var(--text-placeholder, rgba(255, 255, 255, 0.45));
  text-align: right;
}
</style>
