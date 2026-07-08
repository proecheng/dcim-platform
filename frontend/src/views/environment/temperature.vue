<template>
  <div class="temperature-monitor">
    <!-- 顶部统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="4" v-for="card in statCards" :key="card.label">
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
          :class="{
            'zone-alarm': zone.hasAlarm,
            'zone-drift': zone.hasDrift && !zone.hasAlarm,
          }"
          @click="handleZoneClick(zone)"
        >
          <template #header>
            <div class="zone-header">
              <span class="zone-name">{{ zone.areaCode }}</span>
              <div class="zone-badges">
                <el-tag v-if="zone.hasAlarm" type="danger" size="small" effect="dark">告警</el-tag>
                <el-tooltip v-if="zone.hasDrift" content="数据可靠性: 低" placement="top">
                  <el-tag type="warning" size="small" effect="dark">
                    <el-icon :size="12" style="margin-right: 2px;"><WarnTriangleFilled /></el-icon>
                    漂移
                  </el-tag>
                </el-tooltip>
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
                <span class="metric-label">告警</span>
                <span class="metric-value alarm-val">{{ zone.alarmCount }}</span>
              </div>
            </div>
            <div class="zone-metric-row">
              <div class="zone-metric">
                <span class="metric-label">平均温度</span>
                <span class="metric-value temp-val">{{ zone.avgTemp != null ? zone.avgTemp.toFixed(1) + '°C' : '--' }}</span>
              </div>
              <div class="zone-metric">
                <span class="metric-label">平均湿度</span>
                <span class="metric-value humi-val">{{ zone.avgHumidity != null ? zone.avgHumidity.toFixed(1) + '%' : '--' }}</span>
              </div>
            </div>
            <div class="zone-metric-row">
              <div class="zone-metric">
                <span class="metric-label">最低温度</span>
                <span class="metric-value">{{ zone.minTemp != null ? zone.minTemp.toFixed(1) + '°C' : '--' }}</span>
              </div>
              <div class="zone-metric">
                <span class="metric-label">最高温度</span>
                <span class="metric-value">{{ zone.maxTemp != null ? zone.maxTemp.toFixed(1) + '°C' : '--' }}</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 传感器详情抽屉 -->
    <el-drawer
      v-model="drawerVisible"
      :title="selectedZone ? `${selectedZone.areaCode} — 传感器列表` : '传感器列表'"
      size="520px"
      direction="rtl"
    >
      <div v-if="selectedZone" class="sensor-list">
        <div
          v-for="sensor in selectedZone.sensors"
          :key="sensor.point_id"
          class="sensor-item"
          :class="{ 'sensor-active': selectedSensor?.point_id === sensor.point_id }"
          @click="handleSensorClick(sensor)"
        >
          <div class="sensor-header">
            <span class="sensor-name">{{ sensor.point_name }}</span>
            <div class="sensor-tags">
              <el-tag :type="statusTagType(sensor.status)" size="small">{{ statusText(sensor.status) }}</el-tag>
              <el-tooltip v-if="isDrift(sensor.point_id)" content="数据可靠性: 低" placement="top">
                <el-icon :size="16" color="#faad14" style="margin-left: 4px;"><WarnTriangleFilled /></el-icon>
              </el-tooltip>
            </div>
          </div>
          <div class="sensor-value">
            <span>{{ sensor.value != null ? sensor.value : '--' }} {{ sensor.unit || '' }}</span>
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
              <span class="detail-label">当前值</span>
              <span class="detail-val">{{ selectedSensor.value != null ? selectedSensor.value : '--' }} {{ selectedSensor.unit || '' }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">状态</span>
              <el-tag :type="statusTagType(selectedSensor.status)" size="small">{{ statusText(selectedSensor.status) }}</el-tag>
            </div>
            <div class="detail-row">
              <span class="detail-label">更新时间</span>
              <span class="detail-val">{{ formatTime(selectedSensor.updated_at) }}</span>
            </div>
          </div>

          <!-- 24h 趋势图 -->
          <div class="trend-chart-title">最近 24 小时趋势</div>
          <div ref="trendChartRef" class="trend-chart" />

          <!-- 关联告警 -->
          <div class="alarm-section">
            <div class="alarm-title">关联告警</div>
            <el-table v-if="sensorAlarms.length" :data="sensorAlarms" size="small" max-height="200">
              <el-table-column prop="alarm_message" label="告警信息" min-width="160" show-overflow-tooltip />
              <el-table-column label="级别" width="70">
                <template #default="{ row }">
                  <el-tag :type="alarmLevelType(row.alarm_level)" size="small">{{ alarmLevelText(row.alarm_level) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="时间" width="140">
                <template #default="{ row }">
                  {{ formatTime(row.created_at) }}
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-else description="暂无活动告警" :image-size="40" />
          </div>
        </div>
      </template>
    </el-drawer>

    <!-- 底部数据表格 -->
    <el-card shadow="hover" class="table-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-icon :size="18"><Sunny /></el-icon>
            <span>温湿度传感器数据</span>
          </div>
          <div class="header-filters">
            <el-select v-model="filterArea" placeholder="全部区域" clearable size="default" style="width: 140px;">
              <el-option v-for="area in areaOptions" :key="area" :label="area" :value="area" />
            </el-select>
            <el-select v-model="filterStatus" placeholder="全部状态" clearable size="default" style="width: 140px;">
              <el-option label="正常" value="normal" />
              <el-option label="告警" value="alarm" />
              <el-option label="离线" value="offline" />
              <el-option label="疑似漂移" value="drift" />
            </el-select>
            <el-input v-model="searchKeyword" placeholder="搜索传感器名称" clearable size="default" style="width: 200px;" :prefix-icon="Search" />
            <el-button type="primary" link @click="fetchData">刷新</el-button>
          </div>
        </div>
      </template>
      <el-table :data="filteredTableData" stripe height="420" v-loading="loading" :row-class-name="tableRowClass">
        <el-table-column prop="point_name" label="传感器名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="area_code" label="区域" width="100" />
        <el-table-column label="当前值" width="120">
          <template #default="{ row }">
            <span>{{ row.value != null ? row.value : '--' }} {{ row.unit || '' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="数据质量" width="100">
          <template #default="{ row }">
            <DataQualityTag :quality="row.quality ?? 0" />
          </template>
        </el-table-column>
        <el-table-column label="漂移" width="80">
          <template #default="{ row }">
            <el-tooltip v-if="isDrift(row.point_id)" content="数据可靠性: 低" placement="top">
              <el-icon :size="18" color="#faad14"><WarnTriangleFilled /></el-icon>
            </el-tooltip>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" min-width="170">
          <template #default="{ row }">
            {{ formatTime(row.updated_at) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import * as echarts from 'echarts'
import { Sunny, Search, WarnTriangleFilled, Odometer, Monitor, CircleCheck, WarningFilled, TrendCharts } from '@element-plus/icons-vue'
import { getPointTrend, type TrendData } from '@/api/modules/history'
import { useTemperatureData, type ZoneGroup } from '@/composables/useTemperatureData'
import DataQualityTag from '@/components/common/DataQualityTag.vue'
import type { RealtimeData } from '@/api/modules/realtime'
import { useAlarmStore, type Alarm } from '@/stores/alarm'

const {
  thSensors,
  loading,
  totalCount,
  onlineCount,
  alarmCount,
  driftCount,
  avgTemp,
  avgHumidity,
  zoneGroups,
  isDrift,
  fetchData,
} = useTemperatureData()

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
    label: '告警数',
    value: alarmCount.value,
    icon: WarningFilled,
    iconBg: 'rgba(245, 34, 45, 0.15)',
    valueClass: 'danger',
  },
  {
    label: '平均温度',
    value: avgTemp.value != null ? avgTemp.value.toFixed(1) + '°C' : '--',
    icon: Sunny,
    iconBg: 'rgba(230, 162, 60, 0.15)',
    valueClass: 'warning',
  },
  {
    label: '平均湿度',
    value: avgHumidity.value != null ? avgHumidity.value.toFixed(1) + '%' : '--',
    icon: Odometer,
    iconBg: 'rgba(64, 158, 255, 0.15)',
    valueClass: 'primary',
  },
  {
    label: '疑似漂移',
    value: driftCount.value,
    icon: TrendCharts,
    iconBg: 'rgba(250, 173, 20, 0.15)',
    valueClass: 'drift',
  },
])

// ── 区域卡片点击 → 抽屉 ──
const drawerVisible = ref(false)
const selectedZone = ref<ZoneGroup | null>(null)
const selectedSensor = ref<RealtimeData | null>(null)
const sensorAlarms = ref<Alarm[]>([])
const trendChartRef = ref<HTMLElement | null>(null)
let trendChart: echarts.ECharts | null = null

function handleZoneClick(zone: ZoneGroup) {
  selectedZone.value = zone
  selectedSensor.value = null
  sensorAlarms.value = []
  drawerVisible.value = true
}

async function handleSensorClick(sensor: RealtimeData) {
  selectedSensor.value = sensor
  // 从 AlarmStore 加载关联告警（Story 27.7 AC1）
  const alarmStore = useAlarmStore()
  sensorAlarms.value = alarmStore.activeAlarms.filter(a => a.point_id === sensor.point_id)
  // 加载趋势图
  await nextTick()
  loadTrendChart(sensor.point_id, sensor.point_name, sensor.unit)
}

function loadTrendChart(pointId: number, name: string, unit: string) {
  if (!trendChartRef.value) return
  if (trendChart) trendChart.dispose()
  trendChart = echarts.init(trendChartRef.value, 'dark-tech')
  trendChart.showLoading()

  getPointTrend(pointId, { duration: 1440, limit: 500 })
    .then((data: TrendData[]) => {
      const option: echarts.EChartsOption = {
        tooltip: { trigger: 'axis' },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: {
          type: 'category',
          data: data.map(d => d.time),
          axisLabel: {
            rotate: 30,
            formatter: (value: string) => value.substring(11, 16),
          },
        },
        yAxis: {
          type: 'value',
          name: unit || '',
        },
        series: [{
          name: name || '数值',
          type: 'line',
          data: data.map(d => d.value),
          smooth: true,
          areaStyle: { opacity: 0.3 },
          itemStyle: { color: '#409eff' },
        }],
      }
      trendChart!.hideLoading()
      trendChart!.setOption(option, true)
    })
    .catch(() => {
      trendChart?.hideLoading()
    })
}

// ── 底部表格筛选 ──
const filterArea = ref('')
const filterStatus = ref('')
const searchKeyword = ref('')

const areaOptions = computed(() => {
  const areas = new Set(thSensors.value.map(d => d.area_code))
  return Array.from(areas).sort()
})

const filteredTableData = computed(() => {
  let data = thSensors.value

  if (filterArea.value) {
    data = data.filter(d => d.area_code === filterArea.value)
  }

  if (filterStatus.value) {
    if (filterStatus.value === 'drift') {
      data = data.filter(d => isDrift(d.point_id))
    } else {
      data = data.filter(d => d.status === filterStatus.value)
    }
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
  const map: Record<string, string> = { normal: '正常', alarm: '告警', offline: '离线' }
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

function formatTime(t: string | null | undefined): string {
  if (!t) return '--'
  return t.replace('T', ' ').substring(0, 19)
}

function tableRowClass({ row }: { row: RealtimeData }): string {
  if (isDrift(row.point_id)) return 'drift-row'
  if (row.quality === 2) return 'unreliable-row'
  return ''
}

// 清理 ECharts
onUnmounted(() => {
  if (trendChart) {
    trendChart.dispose()
    trendChart = null
  }
})
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.temperature-monitor {
  @include page-dashboard(6);

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
      &.drift { color: #faad14; }
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

    &.zone-alarm {
      border-color: #f5222d;
      box-shadow: 0 0 8px rgba(245, 34, 45, 0.25);
    }

    &.zone-drift {
      border-color: #faad14;
      box-shadow: 0 0 8px rgba(250, 173, 20, 0.2);
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

          &.temp-val { color: #faad14; }
          &.humi-val { color: #1890ff; }
          &.alarm-val { color: #f5222d; }
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

  :deep(.drift-row) {
    background-color: rgba(250, 173, 20, 0.08) !important;
  }

  :deep(.unreliable-row) {
    background-color: rgba(245, 34, 45, 0.06) !important;
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

    .sensor-header {
      display: flex;
      align-items: center;
      justify-content: space-between;

      .sensor-name {
        font-size: 14px;
        font-weight: 500;
      }

      .sensor-tags {
        display: flex;
        align-items: center;
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

  .trend-chart-title,
  .alarm-title {
    font-size: 14px;
    font-weight: 600;
    margin: 16px 0 8px;
  }

  .trend-chart {
    width: 100%;
    height: 220px;
  }

  .alarm-section {
    margin-top: 8px;
  }
}
</style>
