<template>
  <div class="security-overview">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: rgba(64, 158, 255, 0.15);">
              <el-icon :size="22"><Lock /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value primary">{{ totalCount }}</div>
              <div class="stat-label">门禁设备数</div>
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
              <div class="stat-label">正常设备数</div>
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
              <div class="stat-label">告警设备数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: rgba(144, 147, 153, 0.15);">
              <el-icon :size="22"><Remove /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value offline">{{ offlineCount }}</div>
              <div class="stat-label">离线设备数</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 安防传感器数据表 -->
    <el-card shadow="hover" class="table-card">
      <template #header>
        <div class="card-header">
          <el-icon :size="18"><Lock /></el-icon>
          <span>安防传感器数据</span>
          <el-button type="primary" link @click="fetchData" style="margin-left: auto;">刷新</el-button>
        </div>
      </template>
      <el-table :data="sensorData" stripe height="480" v-loading="loading">
        <el-table-column prop="point_name" label="设备名称" min-width="180" />
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
        <el-table-column prop="area_code" label="区域" width="80" />
        <el-table-column prop="updated_at" label="更新时间" min-width="170" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { Lock, CircleCheck, Warning, Remove } from '@element-plus/icons-vue'
import { useRealtimeStore } from '@/stores/realtime'

const SEC_DEVICE_TYPES = ['DOOR', 'SMOKE', 'IR']

const deviceTypeLabels: Record<string, string> = {
  DOOR: '门禁',
  SMOKE: '烟雾',
  IR: '红外',
}

const realtimeStore = useRealtimeStore()
const loading = computed(() => realtimeStore.loading)

const sensorData = computed(() =>
  realtimeStore.realtimeData.filter((d) => SEC_DEVICE_TYPES.includes(d.device_type))
)

const totalCount = computed(() => sensorData.value.length)
const normalCount = computed(() => sensorData.value.filter((d) => d.status === 'normal').length)
const alarmCount = computed(() => sensorData.value.filter((d) => d.status === 'alarm').length)
const offlineCount = computed(() => sensorData.value.filter((d) => d.status === 'offline').length)

type TagType = 'info' | 'warning' | 'success' | 'danger' | 'primary'
function statusTagType(status: string): TagType {
  const map: Record<string, TagType> = { normal: 'success', alarm: 'danger', offline: 'info' }
  return map[status] || 'info'
}

function statusText(status: string) {
  const map: Record<string, string> = { normal: '正常', alarm: '告警', offline: '离线' }
  return map[status] || status
}

async function fetchData() {
  try {
    await realtimeStore.fetchAllData()
  } catch (e) {
    console.error('安防监控数据加载失败', e)
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

.security-overview {
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
      &.offline { color: var(--text-secondary, #909399); }
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
}
</style>
