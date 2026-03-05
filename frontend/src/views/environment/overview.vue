<template>
  <div class="environment-overview">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: rgba(230, 162, 60, 0.15);">
              <el-icon :size="22"><Sunny /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value warning">{{ avgTemp }}</div>
              <div class="stat-label">平均温度 (°C)</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: rgba(64, 158, 255, 0.15);">
              <el-icon :size="22"><Monitor /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value primary">{{ avgHumidity }}</div>
              <div class="stat-label">平均湿度 (%)</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: rgba(82, 196, 26, 0.15);">
              <el-icon :size="22"><CircleCheck /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value success">{{ normalCount }}</div>
              <div class="stat-label">正常传感器数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: rgba(245, 34, 45, 0.15);">
              <el-icon :size="22"><Warning /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value danger">{{ alarmCount }}</div>
              <div class="stat-label">告警传感器数</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 传感器数据表 -->
    <el-card shadow="hover" class="table-card">
      <template #header>
        <div class="card-header">
          <el-icon :size="18"><Sunny /></el-icon>
          <span>环境传感器数据</span>
          <el-button type="primary" link @click="fetchData" style="margin-left: auto;">刷新</el-button>
        </div>
      </template>
      <el-table :data="sensorData" stripe height="480" v-loading="loading" :row-class-name="qualityRowClass">
        <el-table-column prop="point_name" label="传感器名称" min-width="180" />
        <el-table-column label="设备类型" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ deviceTypeLabels[row.device_type] || row.device_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="当前值" width="140">
          <template #default="{ row }">
            <span>{{ row.value != null ? row.value : '--' }} {{ row.unit || '' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="quality" label="数据质量" width="100">
          <template #default="{ row }">
            <DataQualityTag :quality="row.quality ?? 0" />
          </template>
        </el-table-column>
        <el-table-column prop="area_code" label="区域" width="80" />
        <el-table-column prop="updated_at" label="更新时间" min-width="170" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { Sunny, Monitor, CircleCheck, Warning } from '@element-plus/icons-vue'
import { type RealtimeData } from '@/api/modules/realtime'
import { useRealtimeStore } from '@/stores/realtime'
import DataQualityTag from '@/components/common/DataQualityTag.vue'

const ENV_DEVICE_TYPES = ['TH', 'WATER', 'SMOKE']

const deviceTypeLabels: Record<string, string> = {
  TH: '温湿度',
  WATER: '水浸',
  SMOKE: '烟雾',
}

const realtimeStore = useRealtimeStore()
const loading = computed(() => realtimeStore.loading)

const sensorData = computed(() =>
  realtimeStore.realtimeData.filter((d) => ENV_DEVICE_TYPES.includes(d.device_type))
)

const avgTemp = computed(() => {
  const temps = sensorData.value.filter(
    (d) => d.device_type === 'TH' && (d.unit === '°C' || d.unit === '℃') && d.value != null
  )
  if (!temps.length) return '--'
  const avg = temps.reduce((s, d) => s + (d.value ?? 0), 0) / temps.length
  return avg.toFixed(1)
})

const avgHumidity = computed(() => {
  const hums = sensorData.value.filter(
    (d) => d.device_type === 'TH' && (d.unit === '%' || d.unit === '%RH') && d.value != null
  )
  if (!hums.length) return '--'
  const avg = hums.reduce((s, d) => s + (d.value ?? 0), 0) / hums.length
  return avg.toFixed(1)
})

const normalCount = computed(() => sensorData.value.filter((d) => d.status === 'normal').length)
const alarmCount = computed(() => sensorData.value.filter((d) => d.status === 'alarm').length)

type TagType = 'info' | 'warning' | 'success' | 'danger' | 'primary'
function statusTagType(status: string): TagType {
  const map: Record<string, TagType> = { normal: 'success', alarm: 'danger', offline: 'info' }
  return map[status] || 'info'
}

function statusText(status: string) {
  const map: Record<string, string> = { normal: '正常', alarm: '告警', offline: '离线' }
  return map[status] || status
}

function qualityRowClass({ row }: { row: RealtimeData }) {
  return row.quality === 2 ? 'unreliable-row' : ''
}

async function fetchData() {
  try {
    await realtimeStore.fetchAllData()
  } catch (e) {
    console.error('环境监控数据加载失败', e)
  }
}

onMounted(() => {
  if (realtimeStore.totalPoints === 0) {
    fetchData()
  }
})
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.environment-overview {
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

  .table-card {
    background: var(--bg-card);
    border-color: var(--border-color);

    .card-header {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 15px;
      font-weight: 600;
      color: var(--text-primary);
    }
  }

  :deep(.unreliable-row) {
    background-color: #FEF0F0 !important;
  }
}
</style>
