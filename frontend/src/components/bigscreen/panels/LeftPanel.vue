<!-- frontend/src/components/bigscreen/panels/LeftPanel.vue -->
<template>
  <DraggablePanel
    ref="panelRef"
    title="环境监测"
    panelId="leftPanel"
    :initialX="panelState.x"
    :initialY="panelState.y"
    :initialCollapsed="panelState.collapsed"
    @positionChange="handlePositionChange"
    @collapseChange="handleCollapseChange"
  >
    <div class="left-panel-content">
      <!-- 温湿度仪表盘 -->
      <div class="data-section gauge-section clickable" @click="navigateTo('/dashboard')">
        <div class="gauge-row">
          <div class="gauge-item">
            <GaugeChart
              :value="store.environment.temperature.avg"
              title="温度"
              unit="°C"
              :min="15"
              :max="40"
              :thresholds="{ warning: 28, danger: 32 }"
            />
          </div>
          <div class="gauge-item">
            <GaugeChart
              :value="store.environment.humidity.avg"
              title="湿度"
              unit="%"
              :min="0"
              :max="100"
              :thresholds="{ warning: 60, danger: 80 }"
            />
          </div>
        </div>
        <div class="nav-hint">点击查看监控详情 →</div>
      </div>

      <!-- 温度趋势图 -->
      <div class="data-section clickable" @click="navigateTo('/dashboard')">
        <h4>温度趋势 (24h)</h4>
        <div class="chart-container">
          <TemperatureTrend
            :data="temperatureTrendData"
            :thresholds="{ warning: 28, danger: 32 }"
          />
        </div>
      </div>

      <!-- 温湿度概览 -->
      <div class="data-section clickable" @click="navigateTo('/dashboard')">
        <h4>温湿度范围</h4>
        <div class="stat-grid">
          <div class="stat-row">
            <span class="stat-label">温度</span>
            <div class="stat-values">
              <DigitalFlop
                :value="store.environment.temperature.min"
                :decimals="1"
                suffix="°C"
                size="small"
              />
              <span class="stat-separator">~</span>
              <DigitalFlop
                :value="store.environment.temperature.max"
                :decimals="1"
                suffix="°C"
                size="small"
              />
            </div>
          </div>
          <div class="stat-row">
            <span class="stat-label">湿度</span>
            <div class="stat-values">
              <DigitalFlop
                :value="store.environment.humidity.min"
                :decimals="0"
                suffix="%"
                size="small"
              />
              <span class="stat-separator">~</span>
              <DigitalFlop
                :value="store.environment.humidity.max"
                :decimals="0"
                suffix="%"
                size="small"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- 实时告警 -->
      <div class="data-section alarm-section clickable" @click="navigateTo('/alarms')">
        <h4>
          实时告警
          <span class="alarm-count" v-if="store.alarmCount > 0">
            ({{ store.alarmCount }})
          </span>
        </h4>
        <div class="alarm-list" v-if="store.activeAlarms.length > 0">
          <div
            v-for="alarm in store.activeAlarms.slice(0, 5)"
            :key="alarm.id"
            class="alarm-item"
            :class="alarm.level"
            @click.stop="handleAlarmClick(alarm)"
          >
            <span class="alarm-level">●</span>
            <span class="alarm-device">{{ alarm.deviceId }}</span>
            <span class="alarm-message">{{ alarm.message }}</span>
          </div>
        </div>
        <div class="no-alarm" v-else>
          <span>✓ 系统运行正常</span>
        </div>
        <div class="view-all" v-if="store.activeAlarms.length > 3" @click.stop="handleViewAllAlarms">
          查看全部 →
        </div>
      </div>
    </div>
  </DraggablePanel>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useBigscreenStore } from '@/stores/bigscreen'
import { DraggablePanel, DigitalFlop } from '@/components/bigscreen/ui'
import { TemperatureTrend, GaugeChart } from '@/components/bigscreen/charts'
import type { BigscreenAlarm } from '@/types/bigscreen'

const emit = defineEmits<{
  (e: 'locateAlarm', alarm: BigscreenAlarm): void
  (e: 'viewAllAlarms'): void
  (e: 'navigate', path: string): void
}>()

const store = useBigscreenStore()
const panelRef = ref()

// 从store获取面板状态
const panelState = computed(() => store.panelStates.leftPanel || { x: 20, y: 60, collapsed: false })

// 模拟24小时温度趋势数据
const temperatureTrendData = computed(() => {
  const now = new Date()
  const data = []
  for (let i = 23; i >= 0; i--) {
    const time = new Date(now.getTime() - i * 3600000)
    const baseTemp = store.environment.temperature.avg
    const variation = Math.sin(i / 4) * 2 + Math.random() * 1 - 0.5
    data.push({
      time: `${time.getHours().toString().padStart(2, '0')}:00`,
      value: Math.round((baseTemp + variation) * 10) / 10
    })
  }
  return data
})

function handlePositionChange(data: { id: string; x: number; y: number }) {
  store.updatePanelPosition(data.id, data.x, data.y)
}

function handleCollapseChange(data: { id: string; collapsed: boolean }) {
  store.updatePanelCollapsed(data.id, data.collapsed)
}

function navigateTo(path: string) {
  emit('navigate', path)
}

function handleAlarmClick(alarm: BigscreenAlarm) {
  emit('locateAlarm', alarm)
}

function handleViewAllAlarms() {
  emit('viewAllAlarms')
}

onMounted(() => {
  store.loadPanelStates()
})
</script>

<style scoped lang="scss">
.left-panel-content {
  width: 260px;
  padding: 12px;
  max-height: calc(100vh - 200px);
  overflow-y: auto;

  &::-webkit-scrollbar {
    width: 4px;
  }

  &::-webkit-scrollbar-track {
    background: rgba(255, 255, 255, 0.05);
  }

  &::-webkit-scrollbar-thumb {
    background: rgba(0, 136, 255, 0.3);
    border-radius: 2px;
  }
}

.data-section {
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);

  &:last-child {
    margin-bottom: 0;
    padding-bottom: 0;
    border-bottom: none;
  }

  &.clickable {
    cursor: pointer;
    transition: background 0.2s, transform 0.2s;
    border-radius: 6px;
    padding: 10px;
    margin: 0 -10px 12px;

    &:hover {
      background: rgba(0, 136, 255, 0.1);
      transform: translateX(3px);

      .nav-hint {
        opacity: 1;
        color: #00ccff;
      }
    }
  }

  h4 {
    display: flex;
    align-items: center;
    margin: 0 0 10px;
    font-size: 12px;
    color: #88ccff;
    font-weight: 500;
  }
}

.nav-hint {
  margin-top: 8px;
  text-align: center;
  font-size: 10px;
  color: #556677;
  opacity: 0;
  transition: opacity 0.2s, color 0.2s;
}

.gauge-section {
  .gauge-row {
    display: flex;
    gap: 8px;
  }

  .gauge-item {
    flex: 1;
    height: 100px;
  }
}

.chart-container {
  height: 120px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 6px;
  overflow: hidden;
}

.stat-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 4px;
  border-left: 2px solid rgba(0, 204, 255, 0.5);

  .stat-label {
    font-size: 11px;
    color: #8899aa;
  }

  .stat-values {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .stat-separator {
    color: #556677;
    margin: 0 4px;
  }
}

.alarm-section {
  .alarm-count {
    margin-left: 6px;
    color: #ff4d4f;
    font-size: 11px;
  }
}

.alarm-list {
  max-height: 150px;
  overflow-y: auto;
}

.alarm-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  margin-bottom: 4px;
  background: rgba(0, 50, 100, 0.3);
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    background: rgba(0, 80, 130, 0.5);
  }

  &.critical .alarm-level {
    color: #ff4d4f;
  }
  &.warning .alarm-level {
    color: #ffaa00;
  }
  &.info .alarm-level {
    color: #00ccff;
  }

  .alarm-device {
    color: #88ccff;
    flex-shrink: 0;
    max-width: 60px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .alarm-message {
    color: #aabbcc;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
  }
}

.no-alarm {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  color: #00ff88;
  font-size: 12px;
}

.view-all {
  margin-top: 8px;
  text-align: center;
  font-size: 11px;
  color: #00ccff;
  cursor: pointer;
  transition: color 0.2s;

  &:hover {
    color: #00ff88;
  }
}
</style>
