<template>
  <div class="water-leak-monitor">
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

    <!-- 区域分组卡片 -->
    <el-row :gutter="16" class="zone-row">
      <el-col :span="6" v-for="zone in zoneGroups" :key="zone.areaCode">
        <el-card
          shadow="hover"
          class="zone-card"
          :class="{ 'zone-alarm-pulse': zone.hasAlarm }"
          @click="handleZoneClick(zone)"
        >
          <template #header>
            <div class="zone-header">
              <span class="zone-name">{{ zone.areaCode }}</span>
              <div class="zone-badges">
                <el-tag v-if="zone.hasAlarm" type="danger" size="small" effect="dark">
                  <el-icon :size="12" style="margin-right: 2px;"><Warning /></el-icon>
                  漏水
                </el-tag>
                <el-tag v-else type="success" size="small" effect="dark">正常</el-tag>
              </div>
            </div>
          </template>
          <div class="zone-body">
            <div class="zone-metric-row">
              <div class="zone-metric">
                <span class="metric-label">传感器</span>
                <span class="metric-value">{{ zone.sensors.length }}</span>
              </div>
              <div class="zone-metric">
                <span class="metric-label">在线</span>
                <span class="metric-value success-val">{{ zone.normalCount + zone.alarmCount }}</span>
              </div>
            </div>
            <div class="zone-metric-row">
              <div class="zone-metric">
                <span class="metric-label">正常</span>
                <span class="metric-value normal-val">{{ zone.normalCount }}</span>
              </div>
              <div class="zone-metric">
                <span class="metric-label">告警</span>
                <span class="metric-value alarm-val">{{ zone.alarmCount }}</span>
              </div>
            </div>
            <div class="zone-status-bar">
              <div
                class="status-segment normal-seg"
                :style="{ width: zone.sensors.length ? (zone.normalCount / zone.sensors.length * 100) + '%' : '0%' }"
              />
              <div
                class="status-segment alarm-seg"
                :style="{ width: zone.sensors.length ? (zone.alarmCount / zone.sensors.length * 100) + '%' : '0%' }"
              />
              <div
                class="status-segment offline-seg"
                :style="{ width: zone.sensors.length ? (zone.offlineCount / zone.sensors.length * 100) + '%' : '0%' }"
              />
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 传感器详情抽屉 -->
    <el-drawer
      v-model="drawerVisible"
      :title="selectedZone ? `${selectedZone.areaCode} — 水浸传感器` : '水浸传感器'"
      size="520px"
      direction="rtl"
    >
      <div v-if="selectedZone" class="sensor-list">
        <div
          v-for="sensor in selectedZone.sensors"
          :key="sensor.point_id"
          class="sensor-item"
          :class="{
            'sensor-active': selectedSensor?.point_id === sensor.point_id,
            'sensor-alarm': sensor.status === 'alarm',
          }"
          @click="handleSensorClick(sensor)"
        >
          <div class="sensor-header">
            <span class="sensor-name">{{ sensor.point_name }}</span>
            <el-tag :type="statusTagType(sensor.status)" size="small">{{ statusText(sensor.status) }}</el-tag>
          </div>
          <div class="sensor-value">
            <span>{{ sensor.value_text || (sensor.status === 'alarm' ? '漏水' : '正常') }}</span>
          </div>
        </div>
      </div>

      <!-- 传感器详情面板 -->
      <template v-if="selectedSensor">
        <el-divider>传感器详情</el-divider>
        <div class="sensor-detail">
          <div class="detail-info">
            <div class="detail-row">
              <span class="detail-label">设备名称</span>
              <span class="detail-val">{{ selectedSensor.point_name }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">当前状态</span>
              <el-tag :type="statusTagType(selectedSensor.status)" size="small">{{ statusText(selectedSensor.status) }}</el-tag>
            </div>
            <div class="detail-row">
              <span class="detail-label">状态文本</span>
              <span class="detail-val">{{ selectedSensor.value_text || '--' }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">所属区域</span>
              <span class="detail-val">{{ selectedSensor.area_code || '--' }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">点位编码</span>
              <span class="detail-val">{{ selectedSensor.point_code || '--' }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">最后变化</span>
              <span class="detail-val">{{ formatTime(selectedSensor.last_change_at) }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">更新时间</span>
              <span class="detail-val">{{ formatTime(selectedSensor.updated_at) }}</span>
            </div>
          </div>

          <!-- 最近告警记录 -->
          <div class="alarm-section">
            <div class="alarm-title">最近告警记录</div>
            <el-table
              v-if="sensorAlarms.length"
              :data="sensorAlarms"
              size="small"
              max-height="260"
              v-loading="alarmLoading"
            >
              <el-table-column prop="alarm_message" label="告警信息" min-width="160" show-overflow-tooltip />
              <el-table-column label="级别" width="70">
                <template #default="{ row }">
                  <el-tag :type="alarmLevelType(row.alarm_level)" size="small">{{ alarmLevelText(row.alarm_level) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="70">
                <template #default="{ row }">
                  <el-tag :type="alarmStatusType(row.status)" size="small">{{ alarmStatusText(row.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="时间" width="140">
                <template #default="{ row }">
                  {{ formatTime(row.created_at) }}
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-else-if="!alarmLoading" description="暂无告警记录" :image-size="40" />
          </div>
        </div>
      </template>
    </el-drawer>

    <!-- 底部数据表格 -->
    <el-card shadow="hover" class="table-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-icon :size="18"><Warning /></el-icon>
            <span>水浸传感器数据</span>
          </div>
          <div class="header-filters">
            <el-select v-model="filterArea" placeholder="全部区域" clearable size="default" style="width: 140px;">
              <el-option v-for="area in areaOptions" :key="area" :label="area" :value="area" />
            </el-select>
            <el-select v-model="filterStatus" placeholder="全部状态" clearable size="default" style="width: 140px;">
              <el-option label="正常" value="normal" />
              <el-option label="告警" value="alarm" />
              <el-option label="离线" value="offline" />
            </el-select>
            <el-input v-model="searchKeyword" placeholder="搜索传感器名称" clearable size="default" style="width: 200px;" :prefix-icon="Search" />
            <el-button type="primary" link @click="fetchData">刷新</el-button>
          </div>
        </div>
      </template>
      <el-table :data="filteredTableData" stripe height="420" v-loading="loading" :row-class-name="tableRowClass">
        <el-table-column prop="point_name" label="传感器名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="area_code" label="区域" width="100" />
        <el-table-column label="当前状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态文本" width="100">
          <template #default="{ row }">
            <span>{{ row.value_text || '--' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="数据质量" width="100">
          <template #default="{ row }">
            <DataQualityTag :quality="row.quality ?? 0" />
          </template>
        </el-table-column>
        <el-table-column label="变化次数" width="90">
          <template #default="{ row }">
            {{ row.change_count ?? 0 }}
          </template>
        </el-table-column>
        <el-table-column label="最后变化" min-width="160">
          <template #default="{ row }">
            {{ formatTime(row.last_change_at) }}
          </template>
        </el-table-column>
        <el-table-column label="更新时间" min-width="160">
          <template #default="{ row }">
            {{ formatTime(row.updated_at) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { Warning, Search, Monitor, CircleCheck, WarningFilled, Bell } from '@element-plus/icons-vue'
import { getAlarmList, type AlarmInfo } from '@/api/modules/alarm'
import { useWaterLeakData, type WaterLeakZoneGroup } from '@/composables/useWaterLeakData'
import DataQualityTag from '@/components/common/DataQualityTag.vue'
import type { RealtimeData } from '@/api/modules/realtime'

const {
  wlSensors,
  loading,
  totalCount,
  onlineCount,
  alarmCount,
  recentAlarmCount,
  zoneGroups,
  fetchData,
} = useWaterLeakData()

// ── 统计卡片配置 ──
const statCards = computed(() => [
  {
    label: '传感器总数',
    value: totalCount.value,
    icon: Monitor,
    iconBg: 'rgba(24, 144, 255, 0.15)',
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
    label: '当前漏水告警',
    value: alarmCount.value,
    icon: WarningFilled,
    iconBg: 'rgba(245, 34, 45, 0.15)',
    valueClass: 'danger',
  },
  {
    label: '24h 告警数',
    value: recentAlarmCount.value,
    icon: Bell,
    iconBg: 'rgba(250, 173, 20, 0.15)',
    valueClass: 'warning',
  },
])

// ── 区域卡片点击 → 抽屉 ──
const drawerVisible = ref(false)
const selectedZone = ref<WaterLeakZoneGroup | null>(null)
const selectedSensor = ref<RealtimeData | null>(null)
const sensorAlarms = ref<AlarmInfo[]>([])
const alarmLoading = ref(false)

function handleZoneClick(zone: WaterLeakZoneGroup) {
  selectedZone.value = zone
  selectedSensor.value = null
  sensorAlarms.value = []
  drawerVisible.value = true
}

async function handleSensorClick(sensor: RealtimeData) {
  selectedSensor.value = sensor
  alarmLoading.value = true
  try {
    const res = await getAlarmList({
      point_id: sensor.point_id,
      page: 1,
      page_size: 20,
    })
    sensorAlarms.value = res.items ?? []
  } catch {
    sensorAlarms.value = []
  } finally {
    alarmLoading.value = false
  }
}

// ── 底部表格筛选 ──
const filterArea = ref('')
const filterStatus = ref('')
const searchKeyword = ref('')

const areaOptions = computed(() => {
  const areas = new Set(wlSensors.value.map(d => d.area_code))
  return Array.from(areas).sort()
})

const filteredTableData = computed(() => {
  let data = wlSensors.value

  if (filterArea.value) {
    data = data.filter(d => d.area_code === filterArea.value)
  }

  if (filterStatus.value) {
    data = data.filter(d => d.status === filterStatus.value)
  }

  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase()
    data = data.filter(d => d.point_name.toLowerCase().includes(kw))
  }

  return data
})

// ── 辅助函数 ──
type TagType = 'info' | 'warning' | 'success' | 'danger' | 'primary'

function statusTagType(status: string): TagType {
  const map: Record<string, TagType> = { normal: 'success', alarm: 'danger', offline: 'info' }
  return map[status] || 'info'
}

function statusText(status: string): string {
  const map: Record<string, string> = { normal: '正常', alarm: '漏水', offline: '离线' }
  return map[status] || status
}

function alarmLevelType(level: string): TagType {
  const map: Record<string, TagType> = { critical: 'danger', major: 'warning', minor: 'primary', info: 'info' }
  return map[level] || 'info'
}

function alarmLevelText(level: string): string {
  const map: Record<string, string> = { critical: '紧急', major: '重要', minor: '次要', info: '提示' }
  return map[level] || level
}

function alarmStatusType(status: string): TagType {
  const map: Record<string, TagType> = { active: 'danger', acknowledged: 'warning', resolved: 'success', ignored: 'info' }
  return map[status] || 'info'
}

function alarmStatusText(status: string): string {
  const map: Record<string, string> = { active: '活动', acknowledged: '已确认', resolved: '已解决', ignored: '已忽略' }
  return map[status] || status
}

function formatTime(t: string | null | undefined): string {
  if (!t) return '--'
  return t.replace('T', ' ').substring(0, 19)
}

function tableRowClass({ row }: { row: RealtimeData }): string {
  if (row.status === 'alarm') return 'alarm-row'
  return ''
}
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.water-leak-monitor {
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

  // ── 区域卡片 ──
  .zone-row {
    margin-bottom: 16px;
  }

  .zone-card {
    cursor: pointer;
    background: var(--bg-card);
    border-color: var(--border-color);
    transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
    margin-bottom: 16px;

    &:hover {
      transform: translateY(-3px);
      box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
    }

    // 漏水告警红色脉冲动画
    &.zone-alarm-pulse {
      border-color: #f5222d;
      animation: pulseAlarm 2s ease-in-out infinite;
    }

    .zone-header {
      display: flex;
      align-items: center;
      justify-content: space-between;

      .zone-name {
        font-size: 15px;
        font-weight: 600;
        color: var(--text-primary);
      }

      .zone-badges {
        display: flex;
        gap: 4px;
      }
    }

    .zone-body {
      .zone-metric-row {
        display: flex;
        justify-content: space-between;
        margin-bottom: 8px;

        &:last-child {
          margin-bottom: 0;
        }
      }

      .zone-metric {
        flex: 1;

        .metric-label {
          display: block;
          font-size: 12px;
          color: var(--text-secondary);
          margin-bottom: 2px;
        }

        .metric-value {
          font-size: 16px;
          font-weight: 600;
          color: var(--text-primary);

          &.success-val { color: #52c41a; }
          &.normal-val { color: #1890ff; }
          &.alarm-val { color: #f5222d; }
        }
      }

      .zone-status-bar {
        display: flex;
        height: 4px;
        border-radius: 2px;
        overflow: hidden;
        background: rgba(255, 255, 255, 0.06);
        margin-top: 10px;

        .status-segment {
          height: 100%;
          transition: width 0.4s ease;

          &.normal-seg { background: #52c41a; }
          &.alarm-seg { background: #f5222d; }
          &.offline-seg { background: #8c8c8c; }
        }
      }
    }
  }

  // ── 底部表格 ──
  .table-card {
    background: var(--bg-card);
    border-color: var(--border-color);

    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 8px;

      .header-left {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 15px;
        font-weight: 600;
        color: var(--text-primary);
      }

      .header-filters {
        display: flex;
        align-items: center;
        gap: 8px;
      }
    }
  }

  :deep(.alarm-row) {
    background-color: rgba(245, 34, 45, 0.08) !important;
  }
}

// ── 红色脉冲动画 ──
@keyframes pulseAlarm {
  0%, 100% {
    box-shadow: 0 0 8px rgba(245, 34, 45, 0.25);
  }
  50% {
    box-shadow: 0 0 20px rgba(245, 34, 45, 0.5), 0 0 40px rgba(245, 34, 45, 0.2);
  }
}

// ── 抽屉内传感器列表 ──
.sensor-list {
  .sensor-item {
    padding: 10px 12px;
    border-radius: 8px;
    cursor: pointer;
    transition: background 0.2s;
    margin-bottom: 4px;

    &:hover {
      background: rgba(24, 144, 255, 0.08);
    }

    &.sensor-active {
      background: rgba(24, 144, 255, 0.15);
      border-left: 3px solid #1890ff;
    }

    &.sensor-alarm {
      border-left: 3px solid #f5222d;

      &:not(.sensor-active) {
        background: rgba(245, 34, 45, 0.06);
      }
    }

    .sensor-header {
      display: flex;
      align-items: center;
      justify-content: space-between;

      .sensor-name {
        font-size: 14px;
        font-weight: 500;
      }
    }

    .sensor-value {
      font-size: 13px;
      color: var(--text-secondary);
      margin-top: 4px;
    }
  }
}

// ── 传感器详情 ──
.sensor-detail {
  .detail-info {
    .detail-row {
      display: flex;
      justify-content: space-between;
      padding: 6px 0;
      border-bottom: 1px solid var(--border-color, rgba(255, 255, 255, 0.06));

      .detail-label {
        font-size: 13px;
        color: var(--text-secondary);
      }

      .detail-val {
        font-size: 13px;
        font-weight: 500;
      }
    }
  }

  .alarm-title {
    font-size: 14px;
    font-weight: 600;
    margin: 16px 0 8px;
  }

  .alarm-section {
    margin-top: 8px;
  }
}
</style>
