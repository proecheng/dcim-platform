<template>
  <div class="vpp-monitor-view">
    <el-page-header @back="$router.back()" title="返回">
      <template #content>
        <span>VPP 集成状态监控</span>
      </template>
    </el-page-header>

    <!-- 连接状态 -->
    <el-card shadow="never" style="margin-top: 16px">
      <div style="display: flex; align-items: center; gap: 16px">
        <span style="font-weight: 600">VPP 连接状态：</span>
        <el-tag :type="connectionTagType" size="large" effect="dark">
          {{ connectionStatusText }}
        </el-tag>
        <span style="color: #909399; font-size: 13px">
          最后更新: {{ lastUpdateTime }}
        </span>
        <el-button size="small" :icon="Refresh" @click="refreshAll" :loading="loading">
          刷新
        </el-button>
      </div>
    </el-card>

    <!-- 统计卡片 -->
    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="6" v-for="stat in statCards" :key="stat.label">
        <el-card shadow="hover">
          <el-statistic :title="stat.label" :value="stat.value" :suffix="stat.suffix" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 可调容量仪表盘 -->
    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>向下可调容量（削峰）</span>
          </template>
          <GaugeChart
            :value="downCapacity"
            title="向下可调"
            unit="kW"
            :min="0"
            :max="maxGauge"
            height="280px"
          />
          <div style="text-align: center; color: #909399; font-size: 13px">
            热功率: {{ downThermalKw }} kW_th
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>向上可调容量（填谷）</span>
          </template>
          <GaugeChart
            :value="upCapacity"
            title="向上可调"
            unit="kW"
            :min="0"
            :max="maxGauge"
            height="280px"
          />
          <div style="text-align: center; color: #909399; font-size: 13px">
            热功率: {{ upThermalKw }} kW_th
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 指令执行列表 -->
    <el-card shadow="hover" style="margin-top: 16px">
      <template #header>
        <span>指令执行记录</span>
      </template>
      <el-table :data="dispatches" v-loading="tableLoading" stripe>
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="command_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag
              :type="row.command_type === 'down_adjust' ? 'warning' : 'success'"
              size="small"
            >
              {{ row.command_type === 'down_adjust' ? '削峰' : '填谷' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="target_power_kw" label="目标功率(kW)" width="130" />
        <el-table-column prop="accepted_power_kw" label="实际调控(kW)" width="130">
          <template #default="{ row }">
            {{ row.accepted_power_kw ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="duration_minutes" label="持续(分)" width="100" />
        <el-table-column prop="reject_reason" label="备注" show-overflow-tooltip />
      </el-table>
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="totalDispatches"
        layout="total, prev, pager, next"
        @current-change="fetchDispatches"
        style="margin-top: 16px; justify-content: flex-end; display: flex"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import GaugeChart from '@/components/charts/GaugeChart.vue'
import { getVppCapacity, getVppDispatches, getVppStatistics } from '@/api/modules/precool'

// ==================== 响应式状态 ====================

const loading = ref(false)
const tableLoading = ref(false)

// 连接状态
const connectionStatus = ref<'online' | 'offline' | 'error'>('offline')
const lastUpdateTime = ref('-')

// 容量数据
const downCapacity = ref(0)
const upCapacity = ref(0)
const downThermalKw = ref(0)
const upThermalKw = ref(0)
const maxGauge = ref(100)

// 统计数据
const statistics = ref({
  daily: { count: 0, total_power_kw: 0, total_energy_kwh: 0, estimated_savings_yuan: 0 },
  monthly: { count: 0, total_power_kw: 0, total_energy_kwh: 0, estimated_savings_yuan: 0 },
})

// 指令列表
const dispatches = ref<any[]>([])
const currentPage = ref(1)
const pageSize = 20
const totalDispatches = ref(0)

// ==================== 计算属性 ====================

type TagType = 'success' | 'info' | 'warning' | 'danger' | 'primary'

const connectionTagType = computed((): TagType => {
  const map: Record<string, TagType> = {
    online: 'success',
    offline: 'info',
    error: 'danger',
  }
  return map[connectionStatus.value] || 'info'
})

const connectionStatusText = computed(() => {
  const map: Record<string, string> = {
    online: '在线',
    offline: '离线',
    error: '异常',
  }
  return map[connectionStatus.value] || '未知'
})

const statCards = computed(() => [
  {
    label: '今日参与次数',
    value: statistics.value.daily.count,
    suffix: '次',
  },
  {
    label: '今日调控电量',
    value: statistics.value.daily.total_energy_kwh,
    suffix: 'kWh',
  },
  {
    label: '本月参与次数',
    value: statistics.value.monthly.count,
    suffix: '次',
  },
  {
    label: '本月节省电费',
    value: statistics.value.monthly.estimated_savings_yuan,
    suffix: '元',
  },
])

// ==================== 方法 ====================

function statusTagType(status: string): TagType {
  const map: Record<string, TagType> = {
    accepted: 'success',
    rejected: 'danger',
    received: 'warning',
    executing: 'primary',
    completed: 'success',
    failed: 'danger',
  }
  return map[status] || 'info'
}

function statusText(status: string) {
  const map: Record<string, string> = {
    accepted: '已接受',
    rejected: '已拒绝',
    received: '已接收',
    executing: '执行中',
    completed: '已完成',
    failed: '失败',
  }
  return map[status] || status
}

function formatTime(iso: string) {
  if (!iso) return '-'
  return iso.replace('T', ' ').slice(0, 19)
}

async function fetchCapacity() {
  try {
    const res = await getVppCapacity()
    if (res.code === 200 && res.data) {
      const data = res.data
      downCapacity.value = Math.round(data.down_adjustable_kw * 10) / 10
      upCapacity.value = Math.round(data.up_adjustable_kw * 10) / 10
      downThermalKw.value = Math.round((data.down_adjustable_thermal_kw || 0) * 10) / 10
      upThermalKw.value = Math.round((data.up_adjustable_thermal_kw || 0) * 10) / 10

      // 动态调整仪表盘最大值
      const maxVal = Math.max(downCapacity.value, upCapacity.value, 10)
      maxGauge.value = Math.ceil(maxVal / 10) * 10 + 20

      connectionStatus.value = 'online'
      lastUpdateTime.value = new Date().toLocaleTimeString()
    } else {
      connectionStatus.value = 'error'
    }
  } catch {
    connectionStatus.value = 'offline'
  }
}

async function fetchStatistics() {
  try {
    const res = await getVppStatistics()
    if (res.code === 200 && res.data) {
      statistics.value = res.data
    }
  } catch {
    // 静默处理
  }
}

async function fetchDispatches(page?: number) {
  if (page) currentPage.value = page
  tableLoading.value = true
  try {
    const res = await getVppDispatches({
      page: currentPage.value,
      page_size: pageSize,
    })
    if (res.code === 200 && res.data) {
      dispatches.value = res.data.items || []
      totalDispatches.value = res.data.total || 0
    }
  } catch {
    // 静默处理
  } finally {
    tableLoading.value = false
  }
}

async function refreshAll() {
  loading.value = true
  await Promise.all([fetchCapacity(), fetchStatistics(), fetchDispatches()])
  loading.value = false
}

// ==================== 生命周期 ====================

let refreshTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  refreshAll()
  // 每 30 秒自动刷新容量和统计
  refreshTimer = setInterval(() => {
    fetchCapacity()
    fetchStatistics()
  }, 30000)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>

<style scoped>
.vpp-monitor-view {
  padding: 20px;
}
</style>
