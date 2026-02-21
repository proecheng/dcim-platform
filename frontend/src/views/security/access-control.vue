<template>
  <div class="access-control-page">
    <!-- 顶部统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6" v-for="card in statCards" :key="card.label">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" :style="{ background: card.iconBg }">
              <el-icon :size="22"><component :is="card.icon" /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value" :class="card.valueClass">
                {{ card.value }}
              </div>
              <div class="stat-label">{{ card.label }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 左右分栏主体 -->
    <div class="main-split">
      <!-- 左侧: 门禁设备列表 -->
      <div class="device-panel">
        <div class="panel-header">
          <el-icon :size="16"><Lock /></el-icon>
          <span>门禁设备</span>
          <el-tag size="small" type="info" effect="plain">{{ totalCount }}</el-tag>
        </div>
        <div class="device-list">
          <div
            v-for="device in doorDevices"
            :key="device.point_id"
            class="device-item"
            :class="{
              'device-active': selectedDevice?.point_id === device.point_id,
              'device-alarm': device.doorStatus === 'alarm',
            }"
            @click="handleDeviceClick(device)"
          >
            <div class="device-top">
              <span class="device-name">{{ device.point_name }}</span>
              <el-tag
                :type="doorStatusTagType(device.doorStatus)"
                size="small"
                :effect="device.doorStatus === 'alarm' ? 'dark' : 'light'"
              >
                {{ device.doorStatusText }}
              </el-tag>
            </div>
            <div class="device-bottom">
              <span class="device-area">
                <el-icon :size="12"><Location /></el-icon>
                {{ device.area_code || '未分区' }}
              </span>
              <span class="device-time">{{ formatTime(device.last_change_at) }}</span>
            </div>
          </div>
          <el-empty v-if="!loading && doorDevices.length === 0" description="暂无门禁设备" :image-size="60" />
        </div>
      </div>

      <!-- 右侧: 时间线视图 -->
      <div class="timeline-panel">
        <div class="panel-header">
          <el-icon :size="16"><Clock /></el-icon>
          <span>出入记录</span>
          <span v-if="selectedDevice" class="selected-device-name">— {{ selectedDevice.point_name }}</span>
          <div class="timeline-filters">
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              size="small"
              style="width: 240px;"
              value-format="YYYY-MM-DDTHH:mm:ss"
              @change="handleFilterChange"
            />
            <el-select
              v-model="filterEventType"
              placeholder="全部类型"
              clearable
              size="small"
              style="width: 130px;"
              @change="handleFilterChange"
            >
              <el-option label="刷卡开门" value="card_open" />
              <el-option label="远程开门" value="remote_open" />
              <el-option label="异常开门" value="anomaly_open" />
              <el-option label="消防联动" value="fire_linkage_open" />
            </el-select>
          </div>
        </div>

        <div v-if="!selectedDevice" class="timeline-empty">
          <el-empty description="请选择左侧门禁设备查看出入记录" :image-size="80" />
        </div>

        <div v-else-if="eventsLoading" class="timeline-loading">
          <el-skeleton :rows="6" animated />
        </div>

        <div v-else-if="filteredEvents.length === 0" class="timeline-empty">
          <el-empty description="该设备暂无出入记录" :image-size="60" />
        </div>

        <div v-else class="timeline-content">
          <el-timeline>
            <el-timeline-item
              v-for="event in filteredEvents"
              :key="event.id"
              :timestamp="formatTime(event.time)"
              placement="top"
              :color="eventColor(event)"
              :icon="eventIcon(event)"
              :hollow="!event.isAnomaly && !event.isFireLinkage"
              size="large"
            >
              <div
                class="event-card"
                :class="{
                  'event-anomaly': event.isAnomaly,
                  'event-fire': event.isFireLinkage,
                }"
              >
                <div class="event-header">
                  <el-tag
                    :type="eventTagType(event)"
                    size="small"
                    :effect="event.isAnomaly ? 'dark' : 'light'"
                  >
                    <el-icon v-if="event.isAnomaly" :size="12" style="margin-right: 2px;"><Warning /></el-icon>
                    {{ event.eventLabel }}
                  </el-tag>
                  <el-tag
                    :type="event.result === 'success' ? 'success' : 'danger'"
                    size="small"
                    effect="plain"
                  >
                    {{ event.result === 'success' ? '成功' : '失败' }}
                  </el-tag>
                </div>
                <div class="event-body">
                  <span v-if="event.person" class="event-person">
                    <el-icon :size="12"><User /></el-icon>
                    {{ event.person }}
                  </span>
                  <span v-if="event.isFireLinkage && event.policyName" class="event-policy">
                    <el-icon :size="12"><Connection /></el-icon>
                    {{ event.policyName }}
                  </span>
                  <span class="event-message">{{ event.rawAlarm.alarm_message }}</span>
                </div>
              </div>
            </el-timeline-item>
          </el-timeline>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Lock, CircleCheck, Warning, Bell, Clock, Location, User, Connection } from '@element-plus/icons-vue'
import { useAccessControlData, type DoorDevice, type AccessEvent, type DoorStatus, type AccessEventType } from '@/composables/useAccessControlData'

const {
  doorDevices,
  loading,
  eventsLoading,
  totalCount,
  onlineCount,
  alarmCount,
  todayEventCount,
  accessEvents,
  fetchDeviceEvents,
} = useAccessControlData()

// ── 统计卡片配置 ──
const statCards = computed(() => [
  {
    label: '设备总数',
    value: totalCount.value,
    icon: Lock,
    iconBg: 'rgba(64, 158, 255, 0.15)',
    valueClass: 'primary',
  },
  {
    label: '在线数',
    value: onlineCount.value,
    icon: CircleCheck,
    iconBg: 'rgba(82, 196, 26, 0.15)',
    valueClass: 'success',
  },
  {
    label: '告警数',
    value: alarmCount.value,
    icon: Warning,
    iconBg: 'rgba(245, 34, 45, 0.15)',
    valueClass: 'danger',
  },
  {
    label: '今日事件',
    value: todayEventCount.value,
    icon: Bell,
    iconBg: 'rgba(250, 173, 20, 0.15)',
    valueClass: 'warning',
  },
])

// ── 设备选择 ──
const selectedDevice = ref<DoorDevice | null>(null)

// 默认选中第一个设备
watch(doorDevices, (devices) => {
  if (devices.length > 0 && !selectedDevice.value) {
    handleDeviceClick(devices[0])
  }
}, { immediate: true })

function handleDeviceClick(device: DoorDevice) {
  selectedDevice.value = device
  loadEvents()
}

// ── 时间线筛选 ──
const dateRange = ref<[string, string] | null>(null)
const filterEventType = ref<AccessEventType | ''>('')

const filteredEvents = computed(() => {
  if (!filterEventType.value) return accessEvents.value
  return accessEvents.value.filter(e => e.eventType === filterEventType.value)
})

function handleFilterChange() {
  loadEvents()
}

function loadEvents() {
  if (!selectedDevice.value) return
  const startTime = dateRange.value?.[0] || undefined
  const endTime = dateRange.value?.[1] || undefined
  fetchDeviceEvents(selectedDevice.value.point_id, startTime, endTime)
}

// ── 辅助函数 ──
type TagType = 'info' | 'warning' | 'success' | 'danger' | 'primary'

function doorStatusTagType(status: DoorStatus): TagType {
  const map: Record<DoorStatus, TagType> = {
    closed: 'success',
    open: 'primary',
    alarm: 'danger',
    offline: 'info',
  }
  return map[status]
}

function eventColor(event: AccessEvent): string {
  if (event.isAnomaly) return '#f5222d'
  if (event.isFireLinkage) return '#fa8c16'
  if (event.eventType === 'remote_open') return '#1890ff'
  return event.result === 'success' ? '#52c41a' : '#8c8c8c'
}

function eventIcon(event: AccessEvent): typeof Warning | undefined {
  if (event.isAnomaly) return Warning
  return undefined
}

function eventTagType(event: AccessEvent): TagType {
  if (event.isAnomaly) return 'danger'
  if (event.isFireLinkage) return 'warning'
  if (event.eventType === 'remote_open') return 'primary'
  return 'success'
}

function formatTime(t: string | null | undefined): string {
  if (!t) return '--'
  return t.replace('T', ' ').substring(0, 19)
}
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.access-control-page {
  @include page-dashboard(4);

  .stat-row {
    margin-bottom: 16px;
  }

  .stat-card {
    background: var(--bg-card);
    border-color: var(--border-color);
    transition: transform 0.2s, box-shadow 0.2s;

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
    }

    .stat-content {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 4px 0;
    }

    .stat-icon {
      width: 44px;
      height: 44px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }

    .stat-info {
      flex: 1;
      min-width: 0;
    }

    .stat-value {
      font-size: 26px;
      font-weight: 700;
      line-height: 1.2;

      &.primary { color: var(--primary-color, #1890ff); }
      &.success { color: var(--success-color, #52c41a); }
      &.danger { color: var(--error-color, #f5222d); }
      &.warning { color: var(--warning-color, #faad14); }
    }

    .stat-label {
      font-size: 13px;
      color: var(--text-secondary);
      margin-top: 2px;
    }
  }

  // ── 左右分栏主体 ──
  .main-split {
    display: flex;
    gap: 16px;
    min-height: 0;
    flex: 1;
    animation: slideInDepth 0.6s ease-out 0.2s both;
  }

  // ── 左侧设备面板 ──
  .device-panel {
    width: 320px;
    flex-shrink: 0;
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    transform: perspective(800px) rotateY(0.5deg);
    transition: all 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);

    &:hover {
      transform: perspective(800px) rotateY(0deg) translateY(-2px);
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
    }

    .panel-header {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 14px 16px;
      border-bottom: 1px solid var(--border-color);
      font-size: 15px;
      font-weight: 600;
      color: var(--text-primary);
    }

    .device-list {
      flex: 1;
      overflow-y: auto;
      padding: 8px;

      &::-webkit-scrollbar {
        width: 4px;
      }

      &::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.15);
        border-radius: 2px;
      }
    }

    .device-item {
      padding: 10px 12px;
      border-radius: 8px;
      cursor: pointer;
      transition: background 0.2s, border-color 0.2s;
      margin-bottom: 4px;
      border-left: 3px solid transparent;

      &:hover {
        background: rgba(24, 144, 255, 0.08);
      }

      &.device-active {
        background: rgba(24, 144, 255, 0.15);
        border-left-color: #1890ff;
      }

      &.device-alarm {
        border-left-color: #f5222d;
        animation: pulseAlarmBg 2s ease-in-out infinite;

        &:not(.device-active) {
          background: rgba(245, 34, 45, 0.06);
        }
      }

      .device-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 4px;

        .device-name {
          font-size: 14px;
          font-weight: 500;
          color: var(--text-primary);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          max-width: 180px;
        }
      }

      .device-bottom {
        display: flex;
        align-items: center;
        justify-content: space-between;
        font-size: 12px;
        color: var(--text-secondary);

        .device-area {
          display: flex;
          align-items: center;
          gap: 2px;
        }

        .device-time {
          font-size: 11px;
          opacity: 0.7;
        }
      }
    }
  }

  // ── 右侧时间线面板 ──
  .timeline-panel {
    flex: 1;
    min-width: 0;
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    transform: perspective(800px) rotateY(-0.5deg) translateZ(-3px);
    transition: all 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);

    &:hover {
      transform: perspective(800px) rotateY(0deg) translateZ(0) translateY(-2px);
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
    }

    .panel-header {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 14px 16px;
      border-bottom: 1px solid var(--border-color);
      font-size: 15px;
      font-weight: 600;
      color: var(--text-primary);
      flex-wrap: wrap;

      .selected-device-name {
        font-weight: 400;
        font-size: 13px;
        color: var(--text-secondary);
      }

      .timeline-filters {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-left: auto;
      }
    }

    .timeline-empty,
    .timeline-loading {
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 40px;
    }

    .timeline-content {
      flex: 1;
      overflow-y: auto;
      padding: 20px 24px;

      &::-webkit-scrollbar {
        width: 4px;
      }

      &::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.15);
        border-radius: 2px;
      }
    }
  }
}

// ── 事件卡片 ──
.event-card {
  padding: 10px 14px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.06));
  transition: background 0.2s, box-shadow 0.2s;

  &:hover {
    background: rgba(255, 255, 255, 0.06);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  }

  &.event-anomaly {
    background: rgba(245, 34, 45, 0.08);
    border-color: rgba(245, 34, 45, 0.25);

    &:hover {
      background: rgba(245, 34, 45, 0.12);
    }
  }

  &.event-fire {
    background: rgba(250, 140, 22, 0.06);
    border-color: rgba(250, 140, 22, 0.2);

    &:hover {
      background: rgba(250, 140, 22, 0.1);
    }
  }

  .event-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
  }

  .event-body {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    font-size: 13px;
    color: var(--text-secondary);

    .event-person {
      display: flex;
      align-items: center;
      gap: 4px;
      color: var(--text-primary);
      font-weight: 500;
    }

    .event-policy {
      display: flex;
      align-items: center;
      gap: 4px;
      color: #fa8c16;
    }

    .event-message {
      flex: 1;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }
}

// ── 告警脉冲动画 ──
@keyframes pulseAlarmBg {
  0%, 100% {
    box-shadow: inset 0 0 0 rgba(245, 34, 45, 0);
  }
  50% {
    box-shadow: inset 0 0 12px rgba(245, 34, 45, 0.1);
  }
}
</style>
