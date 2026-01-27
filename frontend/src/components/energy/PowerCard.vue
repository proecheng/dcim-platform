<template>
  <el-card class="power-card" :class="{ 'is-alarm': status === 'alarm' }" shadow="hover">
    <div class="card-header">
      <span class="device-name">{{ deviceName }}</span>
      <el-tag :type="statusType" size="small">{{ statusText }}</el-tag>
    </div>
    <div class="card-body">
      <div class="power-value">
        <span class="value">{{ formatPower(activePower) }}</span>
        <span class="unit">kW</span>
      </div>
      <div class="power-details">
        <div class="detail-row">
          <span class="label">电压</span>
          <span class="value">{{ formatValue(voltage, 'V') }}</span>
        </div>
        <div class="detail-row">
          <span class="label">电流</span>
          <span class="value">{{ formatValue(current, 'A') }}</span>
        </div>
        <div class="detail-row">
          <span class="label">功率因数</span>
          <span class="value">{{ powerFactor?.toFixed(2) ?? '-' }}</span>
        </div>
        <div class="detail-row">
          <span class="label">负载率</span>
          <span class="value" :style="{ color: loadRateColor }">
            {{ loadRate?.toFixed(1) ?? '-' }}%
          </span>
        </div>
      </div>
      <div class="load-bar">
        <el-progress
          :percentage="loadRate ?? 0"
          :color="loadRateColor"
          :stroke-width="8"
          :show-text="false"
        />
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  deviceName: string
  deviceType: string
  activePower?: number
  voltage?: number
  current?: number
  powerFactor?: number
  loadRate?: number
  status: 'normal' | 'warning' | 'alarm' | 'offline'
}>()

// 状态类型
const statusType = computed(() => {
  switch (props.status) {
    case 'normal': return 'success'
    case 'warning': return 'warning'
    case 'alarm': return 'danger'
    case 'offline': return 'info'
    default: return 'info'
  }
})

// 状态文本
const statusText = computed(() => {
  switch (props.status) {
    case 'normal': return '正常'
    case 'warning': return '预警'
    case 'alarm': return '告警'
    case 'offline': return '离线'
    default: return '未知'
  }
})

// 负载率颜色 - 使用语义化颜色
const loadRateColor = computed(() => {
  const rate = props.loadRate ?? 0
  if (rate < 30) return 'var(--text-secondary)'
  if (rate < 60) return 'var(--success-color)'
  if (rate < 80) return 'var(--warning-color)'
  return 'var(--error-color)'
})

// 格式化功率
function formatPower(power?: number): string {
  if (power === undefined || power === null) return '-'
  return power.toFixed(1)
}

// 格式化数值
function formatValue(value?: number, unit?: string): string {
  if (value === undefined || value === null) return '-'
  return `${value.toFixed(1)} ${unit ?? ''}`
}
</script>

<style scoped lang="scss">
.power-card {
  background-color: var(--bg-card-solid);
  border: 1px solid var(--border-color);
  transition: all 0.3s;

  &.is-alarm {
    border-color: var(--error-color);
    animation: alarm-flash 1s infinite;
  }
}

@keyframes alarm-flash {
  0%, 100% { box-shadow: 0 0 8px rgba(245, 108, 108, 0.3); }
  50% { box-shadow: 0 0 16px rgba(245, 108, 108, 0.6); }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.device-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.power-value {
  display: flex;
  align-items: baseline;
  gap: 4px;

  .value {
    font-size: 32px;
    font-weight: bold;
    color: var(--primary-color);
  }

  .unit {
    font-size: 14px;
    color: var(--text-secondary);
  }
}

.power-details {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;

  .label {
    color: var(--text-secondary);
  }

  .value {
    color: var(--text-primary);
    font-weight: 500;
  }
}

.load-bar {
  margin-top: 4px;
}
</style>
