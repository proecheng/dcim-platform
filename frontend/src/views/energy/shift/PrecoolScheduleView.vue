<template>
  <div class="precool-schedule-view">
    <el-page-header @back="$router.back()">
      <template #content>
        <span>预冷计划管理</span>
      </template>
    </el-page-header>

    <!-- 顶部工具栏 -->
    <el-card class="toolbar-card" shadow="never" style="margin-top: 16px">
      <div class="toolbar-row">
        <div class="toolbar-left">
          <el-select v-model="selectedZoneId" placeholder="选择制冷区域" style="width: 200px" @change="onZoneChange">
            <el-option v-for="z in zoneList" :key="z.zone_id" :label="z.zone_name" :value="z.zone_id" />
          </el-select>
          <el-button-group style="margin-left: 12px">
            <el-button :type="dateMode === 'today' ? 'primary' : ''" @click="switchDate('today')">今日</el-button>
            <el-button :type="dateMode === 'tomorrow' ? 'primary' : ''" @click="switchDate('tomorrow')">明日</el-button>
          </el-button-group>
          <el-tag v-if="precoolConfig" :type="precoolConfig.precool_enabled ? 'success' : 'info'" style="margin-left: 12px">
            预冷: {{ precoolConfig.precool_enabled ? '已启用' : '未启用' }}
          </el-tag>
          <el-tag v-if="precoolConfig" type="warning" style="margin-left: 8px">
            目标: {{ precoolConfig.precool_target_temp }}°C
          </el-tag>
        </div>
        <div class="toolbar-right">
          <el-button type="primary" :icon="Plus" :loading="creating" @click="handleCreate">生成计划</el-button>
          <el-button
            type="danger"
            :icon="VideoPause"
            :disabled="!hasExecutingPlan"
            :loading="aborting"
            @click="handleAbort"
          >中止计划</el-button>
          <el-button :icon="Refresh" @click="fetchSchedules">刷新</el-button>
        </div>
      </div>
    </el-card>

    <!-- 时间线 -->
    <el-card shadow="never" style="margin-top: 12px">
      <template #header>
        <span>预冷时间线 — {{ dateLabel }}</span>
      </template>
      <PrecoolTimeline :schedules="scheduleList" :loading="listLoading" @select="showDetail" />
    </el-card>

    <!-- 计划列表表格 -->
    <el-card shadow="never" style="margin-top: 12px">
      <template #header>
        <span>计划列表</span>
      </template>
      <el-table :data="scheduleList" v-loading="listLoading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="预冷时段" width="180">
          <template #default="{ row }">
            {{ formatTime(row.precool_start_time) }} - {{ formatTime(row.precool_end_time) }}
          </template>
        </el-table-column>
        <el-table-column label="峰时段" width="180">
          <template #default="{ row }">
            {{ formatTime(row.peak_start_time) }} - {{ formatTime(row.peak_end_time) }}
          </template>
        </el-table-column>
        <el-table-column prop="target_temp" label="目标温度" width="100">
          <template #default="{ row }">{{ row.target_temp }}°C</template>
        </el-table-column>
        <el-table-column label="计划节省" width="120">
          <template #default="{ row }">
            {{ row.planned_savings_kwh != null ? row.planned_savings_kwh.toFixed(1) + ' kWh' : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="实际节省" width="120">
          <template #default="{ row }">
            {{ row.actual_savings_kwh != null ? row.actual_savings_kwh.toFixed(1) + ' kWh' : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="showDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 详情对话框 -->
    <el-dialog v-model="detailVisible" title="预冷计划详情" width="800px" destroy-on-close>
      <div v-loading="detailLoading">
        <el-descriptions :column="2" border size="small" v-if="detailData">
          <el-descriptions-item label="计划ID">{{ detailData.id }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTagType(detailData.status)" size="small">{{ statusLabel(detailData.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="预冷时段">
            {{ formatTime(detailData.precool_start_time) }} - {{ formatTime(detailData.precool_end_time) }}
          </el-descriptions-item>
          <el-descriptions-item label="峰时段">
            {{ formatTime(detailData.peak_start_time) }} - {{ formatTime(detailData.peak_end_time) }}
          </el-descriptions-item>
          <el-descriptions-item label="目标温度">{{ detailData.target_temp }}°C</el-descriptions-item>
          <el-descriptions-item label="计划节省">
            {{ detailData.planned_savings_kwh != null ? detailData.planned_savings_kwh.toFixed(1) + ' kWh' : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="实际节省">
            {{ detailData.actual_savings_kwh != null ? detailData.actual_savings_kwh.toFixed(1) + ' kWh' : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="中止原因" v-if="detailData.abort_reason">
            {{ detailData.abort_reason }}
          </el-descriptions-item>
        </el-descriptions>

        <!-- 温度轨迹图 -->
        <div v-if="hasTrajectory" style="margin-top: 16px">
          <h4 style="margin-bottom: 8px">温度轨迹</h4>
          <div ref="tempChartRef" style="width: 100%; height: 280px"></div>
        </div>

        <!-- 功率轨迹图 -->
        <div v-if="hasPowerTrajectory" style="margin-top: 16px">
          <h4 style="margin-bottom: 8px">制冷功率轨迹</h4>
          <div ref="powerChartRef" style="width: 100%; height: 250px"></div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Plus, Refresh, VideoPause } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import echarts from '@/utils/echarts'
import PrecoolTimeline from '@/components/energy/PrecoolTimeline.vue'
import {
  getDashboard,
  listSchedules,
  getSchedule,
  createSchedule,
  abortSchedule,
  getPrecoolConfig,
} from '@/api/modules/precool'
import type { ScheduleListItem, ScheduleDetail, PrecoolConfig, DashboardZone } from '@/api/modules/precool'

// ========== 状态 ==========
const zoneList = ref<DashboardZone[]>([])
const selectedZoneId = ref<number>(0)
const dateMode = ref<'today' | 'tomorrow'>('tomorrow')
const precoolConfig = ref<PrecoolConfig | null>(null)
const scheduleList = ref<ScheduleListItem[]>([])
const listLoading = ref(false)
const creating = ref(false)
const aborting = ref(false)

// 详情
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailData = ref<ScheduleDetail | null>(null)
const tempChartRef = ref<HTMLElement>()
const powerChartRef = ref<HTMLElement>()
let tempChart: echarts.ECharts | null = null
let powerChart: echarts.ECharts | null = null

// ========== 计算属性 ==========
const dateLabel = computed(() => dateMode.value === 'today' ? '今日' : '明日')

const scheduleDateStr = computed(() => {
  const d = new Date()
  if (dateMode.value === 'tomorrow') d.setDate(d.getDate() + 1)
  return d.toISOString().split('T')[0]
})

const hasExecutingPlan = computed(() =>
  scheduleList.value.some(s => s.status === 'executing')
)

const hasTrajectory = computed(() => {
  const t = detailData.value?.temperature_trajectory
  return t && (t.predicted?.length || t.actual?.length)
})

const hasPowerTrajectory = computed(() => {
  const t = detailData.value?.temperature_trajectory
  return t && (t.q_cool?.length || t.q_cool_actual?.length)
})

// ========== 工具函数 ==========
type TagType = 'primary' | 'success' | 'info' | 'warning' | 'danger'

function statusTagType(status: string): TagType {
  const map: Record<string, TagType> = {
    pending: 'info',
    executing: 'success',
    completed: 'info',
    aborted: 'danger',
  }
  return map[status] ?? 'info'
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: '待执行',
    executing: '执行中',
    completed: '已完成',
    aborted: '已中止',
  }
  return map[status] ?? status
}

function formatTime(isoStr: string): string {
  if (!isoStr) return '-'
  const d = new Date(isoStr)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

// ========== 数据加载 ==========
async function fetchZones() {
  try {
    const res = await getDashboard()
    const data = (res as any).data?.data ?? (res as any).data
    zoneList.value = data?.zones || []
    if (zoneList.value.length && !selectedZoneId.value) {
      selectedZoneId.value = zoneList.value[0].zone_id
    }
  } catch {
    zoneList.value = []
  }
}

async function fetchConfig() {
  if (!selectedZoneId.value) return
  try {
    const res = await getPrecoolConfig(selectedZoneId.value)
    const data = (res as any).data?.data ?? (res as any).data
    precoolConfig.value = data
  } catch {
    precoolConfig.value = null
  }
}

async function fetchSchedules() {
  if (!selectedZoneId.value) return
  listLoading.value = true
  try {
    const res = await listSchedules(selectedZoneId.value, {
      schedule_date: scheduleDateStr.value,
      limit: 50,
    })
    const data = (res as any).data?.data ?? (res as any).data
    scheduleList.value = data?.items || []
  } catch {
    scheduleList.value = []
  } finally {
    listLoading.value = false
  }
}

function onZoneChange() {
  fetchConfig()
  fetchSchedules()
}

function switchDate(mode: 'today' | 'tomorrow') {
  dateMode.value = mode
  fetchSchedules()
}

// ========== 操作 ==========
async function handleCreate() {
  if (!selectedZoneId.value) return
  creating.value = true
  try {
    await createSchedule(selectedZoneId.value, { schedule_date: scheduleDateStr.value })
    ElMessage.success('预冷计划生成成功')
    fetchSchedules()
  } catch (err: any) {
    const msg = err?.response?.data?.message || err?.message || '生成失败'
    ElMessage.error(msg)
  } finally {
    creating.value = false
  }
}

async function handleAbort() {
  const executingPlan = scheduleList.value.find(s => s.status === 'executing')
  if (!executingPlan) return

  try {
    await ElMessageBox.confirm('确定要中止当前执行中的预冷计划吗？', '确认中止', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }

  aborting.value = true
  try {
    await abortSchedule(executingPlan.id, { reason: 'manual_abort' })
    ElMessage.success('预冷计划已中止')
    fetchSchedules()
  } catch (err: any) {
    const msg = err?.response?.data?.message || err?.message || '中止失败'
    ElMessage.error(msg)
  } finally {
    aborting.value = false
  }
}

// ========== 详情对话框 ==========
async function showDetail(schedule: ScheduleListItem) {
  detailVisible.value = true
  detailLoading.value = true
  detailData.value = null
  try {
    const res = await getSchedule(schedule.id)
    const data = (res as any).data?.data ?? (res as any).data
    detailData.value = data
    await nextTick()
    renderDetailCharts()
  } catch {
    ElMessage.error('加载计划详情失败')
  } finally {
    detailLoading.value = false
  }
}

function renderDetailCharts() {
  const trajectory = detailData.value?.temperature_trajectory
  if (!trajectory) return

  const timestamps = trajectory.timestamps || []
  const labels = timestamps.map((t: string) => {
    const d = new Date(t)
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  })

  // 温度轨迹
  if (tempChartRef.value && (trajectory.predicted?.length || trajectory.actual?.length)) {
    tempChart?.dispose()
    tempChart = echarts.init(tempChartRef.value)
    const series: any[] = []
    if (trajectory.predicted?.length) {
      series.push({
        name: '预测温度',
        type: 'line',
        data: trajectory.predicted,
        lineStyle: { type: 'dashed', color: '#409EFF' },
        itemStyle: { color: '#409EFF' },
        symbol: 'none',
      })
    }
    if (trajectory.actual?.length) {
      series.push({
        name: '实际温度',
        type: 'line',
        data: trajectory.actual,
        lineStyle: { color: '#67C23A' },
        itemStyle: { color: '#67C23A' },
        symbol: 'none',
      })
    }
    // ASHRAE markLine
    if (series.length) {
      series[0].markLine = {
        silent: true,
        symbol: 'none',
        data: [
          { yAxis: 27, lineStyle: { type: 'dashed', color: '#f56c6c' }, label: { formatter: 'ASHRAE 27°C', position: 'insideEndTop' } },
          { yAxis: 18, lineStyle: { type: 'dashed', color: '#409EFF' }, label: { formatter: 'ASHRAE 18°C', position: 'insideEndBottom' } },
        ],
      }
    }
    tempChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: series.map(s => s.name), top: 0 },
      grid: { top: 30, right: 20, bottom: 30, left: 50 },
      xAxis: { type: 'category', data: labels, boundaryGap: false },
      yAxis: { type: 'value', name: '°C' },
      series,
    })
  }

  // 功率轨迹
  if (powerChartRef.value && (trajectory.q_cool?.length || trajectory.q_cool_actual?.length)) {
    powerChart?.dispose()
    powerChart = echarts.init(powerChartRef.value)
    const pSeries: any[] = []
    if (trajectory.q_cool?.length) {
      pSeries.push({
        name: '计划功率',
        type: 'line',
        data: trajectory.q_cool,
        lineStyle: { type: 'dashed', color: '#E6A23C' },
        itemStyle: { color: '#E6A23C' },
        symbol: 'none',
      })
    }
    if (trajectory.q_cool_actual?.length) {
      pSeries.push({
        name: '实际功率',
        type: 'line',
        data: trajectory.q_cool_actual,
        lineStyle: { color: '#409EFF' },
        itemStyle: { color: '#409EFF' },
        symbol: 'none',
      })
    }
    powerChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: pSeries.map(s => s.name), top: 0 },
      grid: { top: 30, right: 20, bottom: 30, left: 50 },
      xAxis: { type: 'category', data: labels, boundaryGap: false },
      yAxis: { type: 'value', name: 'kW' },
      series: pSeries,
    })
  }
}

watch(detailVisible, (val) => {
  if (!val) {
    tempChart?.dispose()
    tempChart = null
    powerChart?.dispose()
    powerChart = null
    detailData.value = null
  }
})

// ========== 生命周期 ==========
onMounted(async () => {
  await fetchZones()
  fetchConfig()
  fetchSchedules()
})
</script>

<style scoped lang="scss">
.precool-schedule-view {
  padding: 16px;

  .toolbar-card {
    :deep(.el-card__body) {
      padding: 12px 16px;
    }
  }

  .toolbar-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
  }

  .toolbar-left,
  .toolbar-right {
    display: flex;
    align-items: center;
    gap: 8px;
  }
}
</style>
