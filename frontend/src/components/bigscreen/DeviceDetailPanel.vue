<!-- frontend/src/components/bigscreen/DeviceDetailPanel.vue -->
<template>
  <Transition name="slide">
    <div v-if="store.selectedDeviceId && deviceData" class="device-detail-panel">
      <div class="panel-header">
        <h3>{{ deviceConfig?.name || '设备详情' }}</h3>
        <el-icon class="close-btn" @click="handleClose"><Close /></el-icon>
      </div>

      <div class="panel-content">
        <!-- 状态指示 -->
        <div class="status-row">
          <span class="status-indicator" :class="deviceData.status"></span>
          <span class="status-text">{{ statusLabels[deviceData.status] }}</span>
        </div>

        <!-- 基本信息 -->
        <div class="info-section">
          <div class="info-item">
            <span class="label">设备ID</span>
            <span class="value">{{ store.selectedDeviceId }}</span>
          </div>
          <div class="info-item" v-if="deviceConfig?.position">
            <span class="label">位置</span>
            <span class="value">
              X: {{ deviceConfig.position.x.toFixed(1) }},
              Z: {{ deviceConfig.position.z.toFixed(1) }}
            </span>
          </div>
        </div>

        <!-- 实时数据 -->
        <div class="data-section">
          <h4>实时数据</h4>
          <div class="data-grid">
            <div class="data-item" v-if="deviceData.temperature !== undefined">
              <div class="data-icon temp">
                <el-icon><Odometer /></el-icon>
              </div>
              <div class="data-info">
                <span class="data-label">温度</span>
                <span class="data-value" :class="getTempClass(deviceData.temperature)">
                  {{ deviceData.temperature.toFixed(1) }}°C
                </span>
              </div>
            </div>

            <div class="data-item" v-if="deviceData.humidity !== undefined">
              <div class="data-icon humidity">
                <el-icon><Cloudy /></el-icon>
              </div>
              <div class="data-info">
                <span class="data-label">湿度</span>
                <span class="data-value">{{ deviceData.humidity.toFixed(1) }}%</span>
              </div>
            </div>

            <div class="data-item" v-if="deviceData.power !== undefined">
              <div class="data-icon power">
                <el-icon><Lightning /></el-icon>
              </div>
              <div class="data-info">
                <span class="data-label">功率</span>
                <span class="data-value">{{ deviceData.power.toFixed(1) }} kW</span>
              </div>
            </div>

            <div class="data-item" v-if="deviceData.load !== undefined">
              <div class="data-icon load">
                <el-icon><Cpu /></el-icon>
              </div>
              <div class="data-info">
                <span class="data-label">负载</span>
                <span class="data-value">{{ deviceData.load.toFixed(0) }}%</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="action-section">
          <el-button type="primary" size="small" @click="handleLocate">
            <el-icon><Aim /></el-icon>
            定位
          </el-button>
          <el-button size="small" @click="handleViewHistory">
            <el-icon><DataLine /></el-icon>
            历史
          </el-button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Close, Odometer, Cloudy, Lightning, Cpu, Aim, DataLine } from '@element-plus/icons-vue'
import { useBigscreenStore } from '@/stores/bigscreen'

const emit = defineEmits<{
  (e: 'locate', deviceId: string): void
  (e: 'viewHistory', deviceId: string): void
}>()

const store = useBigscreenStore()

// 状态标签
const statusLabels: Record<string, string> = {
  normal: '正常运行',
  alarm: '告警中',
  offline: '离线'
}

// 获取设备数据
const deviceData = computed(() => {
  if (!store.selectedDeviceId) return null
  return store.deviceData[store.selectedDeviceId] || {
    id: store.selectedDeviceId,
    status: 'normal' as const,
    temperature: 24,
    humidity: 50,
    power: 5,
    load: 60
  }
})

// 获取设备配置
const deviceConfig = computed(() => {
  if (!store.selectedDeviceId || !store.layout) return null
  for (const module of store.layout.modules) {
    const cabinet = module.cabinets.find(c => c.id === store.selectedDeviceId)
    if (cabinet) return cabinet
  }
  return null
})

// 获取温度样式类
function getTempClass(temp: number): string {
  if (temp > 30) return 'danger'
  if (temp > 26) return 'warning'
  if (temp < 18) return 'cold'
  return 'normal'
}

// 关闭面板
function handleClose() {
  store.selectDevice(null)
}

// 定位设备
function handleLocate() {
  if (store.selectedDeviceId) {
    emit('locate', store.selectedDeviceId)
  }
}

// 查看历史
function handleViewHistory() {
  if (store.selectedDeviceId) {
    emit('viewHistory', store.selectedDeviceId)
  }
}
</script>

<style scoped lang="scss">
.device-detail-panel {
  position: absolute;
  top: 60px;
  right: 20px;
  width: 280px;
  background: rgba(10, 15, 30, 0.95);
  border: 1px solid rgba(0, 136, 255, 0.3);
  border-radius: 8px;
  color: #fff;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: rgba(0, 136, 255, 0.1);
  border-bottom: 1px solid rgba(0, 136, 255, 0.2);

  h3 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
  }

  .close-btn {
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;

    &:hover {
      background: rgba(255, 255, 255, 0.1);
    }
  }
}

.panel-content {
  padding: 16px;
}

.status-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;

  .status-indicator {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #00ff88;

    &.alarm {
      background: #ff3300;
      animation: blink 1s infinite;
    }

    &.offline {
      background: #666;
    }
  }

  .status-text {
    font-size: 13px;
    color: #aaa;
  }
}

.info-section {
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);

  .info-item {
    display: flex;
    justify-content: space-between;
    margin-bottom: 8px;
    font-size: 12px;

    .label {
      color: #888;
    }

    .value {
      color: #ccc;
    }
  }
}

.data-section {
  margin-bottom: 16px;

  h4 {
    margin: 0 0 12px;
    font-size: 12px;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 1px;
  }

  .data-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  .data-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 6px;
  }

  .data-icon {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 6px;
    font-size: 16px;

    &.temp { background: rgba(255, 100, 0, 0.2); color: #ff6400; }
    &.humidity { background: rgba(0, 150, 255, 0.2); color: #0096ff; }
    &.power { background: rgba(255, 200, 0, 0.2); color: #ffc800; }
    &.load { background: rgba(0, 255, 136, 0.2); color: #00ff88; }
  }

  .data-info {
    display: flex;
    flex-direction: column;
  }

  .data-label {
    font-size: 10px;
    color: #888;
  }

  .data-value {
    font-size: 14px;
    font-weight: 600;
    color: #fff;

    &.danger { color: #ff3300; }
    &.warning { color: #ffcc00; }
    &.cold { color: #0066ff; }
    &.normal { color: #00ff88; }
  }
}

.action-section {
  display: flex;
  gap: 8px;

  :deep(.el-button) {
    flex: 1;
    background: rgba(0, 136, 255, 0.2);
    border-color: rgba(0, 136, 255, 0.4);
    color: #ccc;

    &:hover {
      background: rgba(0, 136, 255, 0.3);
      color: #fff;
    }

    &.el-button--primary {
      background: rgba(0, 136, 255, 0.4);
    }
  }
}

// 滑入动画
.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
