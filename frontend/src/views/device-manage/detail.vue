<template>
  <div class="device-detail-page">
    <el-page-header @back="router.back()" style="margin-bottom: 16px;">
      <template #content>
        <span>{{ deviceData?.device_name || '设备详情' }}</span>
      </template>
    </el-page-header>

    <!-- 设备信息卡片 -->
    <el-card shadow="hover" v-loading="loading">
      <template #header>设备信息</template>
      <el-descriptions :column="3" border v-if="deviceData">
        <el-descriptions-item label="设备编码">{{ deviceData.device_code }}</el-descriptions-item>
        <el-descriptions-item label="设备名称">{{ deviceData.device_name }}</el-descriptions-item>
        <el-descriptions-item label="设备类型">
          <el-tag size="small">{{ deviceData.device_type }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="区域">{{ deviceData.area_code }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusTagType" size="small">{{ statusText }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="厂商">{{ deviceData.manufacturer || '--' }}</el-descriptions-item>
        <el-descriptions-item label="型号">{{ deviceData.model || '--' }}</el-descriptions-item>
        <el-descriptions-item label="安装日期">{{ deviceData.install_date || '--' }}</el-descriptions-item>
        <el-descriptions-item label="启用状态">
          <el-tag :type="deviceData.is_enabled ? 'success' : 'info'" size="small">
            {{ deviceData.is_enabled ? '已启用' : '已禁用' }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 关联点位实时数据 -->
    <el-card shadow="hover" style="margin-top: 16px;">
      <template #header>
        <div class="card-header">
          <span>关联点位实时数据</span>
          <el-tag v-if="points.length > 0" size="small">{{ points.length }} 个点位</el-tag>
        </div>
      </template>
      <el-table
        :data="points"
        stripe
        border
        row-key="id"
        :expand-row-keys="expandedRowKeys"
        :row-class-name="qualityRowClass"
        @expand-change="handleExpandChange"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div v-if="row.point_type === 'AI'" class="expand-chart-wrapper">
              <div class="chart-toolbar">
                <el-radio-group v-model="chartDurations[row.id]" size="small" @change="loadTrendData(row.id)">
                  <el-radio-button :value="60">1小时</el-radio-button>
                  <el-radio-button :value="360">6小时</el-radio-button>
                  <el-radio-button :value="1440">24小时</el-radio-button>
                  <el-radio-button :value="10080">7天</el-radio-button>
                  <el-radio-button :value="43200">30天</el-radio-button>
                </el-radio-group>
              </div>
              <div :ref="(el: any) => setChartRef(row.id, el)" class="trend-chart"></div>
            </div>
            <el-empty v-else description="仅 AI 类型点位支持历史曲线" :image-size="40" />
          </template>
        </el-table-column>
        <el-table-column prop="point_code" label="点位编码" width="160" />
        <el-table-column prop="point_name" label="点位名称" min-width="160" />
        <el-table-column prop="point_type" label="类型" width="80">
          <template #default="{ row }">
            <el-tag size="small" :type="row.point_type === 'AI' ? 'primary' : 'info'">
              {{ row.point_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="当前值" width="140">
          <template #default="{ row }">
            {{ row.value != null ? Number(row.value).toFixed(2) : '--' }}
            {{ row.unit || '' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="pointStatusType(row.status)" size="small">
              {{ pointStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="quality" label="数据质量" width="100">
          <template #default="{ row }">
            <DataQualityTag :quality="row.quality ?? 0" />
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="170">
          <template #default="{ row }">
            {{ row.updated_at ? row.updated_at.replace('T', ' ').substring(0, 19) : '--' }}
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && points.length === 0" description="暂无关联点位" :image-size="60" />
    </el-card>

    <!-- 当前告警 -->
    <el-card shadow="hover" style="margin-top: 16px;">
      <template #header>
        <div class="card-header">
          <span>当前告警</span>
          <el-tag v-if="alarms.length > 0" type="danger" size="small">{{ alarms.length }} 条</el-tag>
        </div>
      </template>
      <el-table :data="alarms" stripe border v-if="alarms.length > 0">
        <el-table-column prop="alarm_no" label="告警编号" width="140" />
        <el-table-column prop="alarm_level" label="级别" width="90">
          <template #default="{ row }">
            <el-tag :type="alarmLevelType(row.alarm_level)" size="small">
              {{ alarmLevelText(row.alarm_level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="alarm_message" label="告警消息" min-width="200" />
        <el-table-column label="触发值" width="100">
          <template #default="{ row }">
            {{ row.trigger_value != null ? Number(row.trigger_value).toFixed(2) : '--' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'danger' : 'warning'" size="small">
              {{ row.status === 'active' ? '活动' : '已确认' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="触发时间" width="170">
          <template #default="{ row }">
            {{ row.created_at ? row.created_at.replace('T', ' ').substring(0, 19) : '--' }}
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="暂无活动告警" :image-size="60" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import {
  getDeviceDetail,
  type DeviceInfo,
  type PointRealtimeItem,
  type AlarmItem
} from '@/api/modules/device'
import { getPointTrend, type TrendData } from '@/api/modules/history'
import DataQualityTag from '@/components/common/DataQualityTag.vue'

const router = useRouter()
const route = useRoute()

const loading = ref(false)
const deviceData = ref<DeviceInfo | null>(null)
const points = ref<PointRealtimeItem[]>([])
const alarms = ref<AlarmItem[]>([])

// ===== ECharts 管理 =====
const chartRefs: Record<number, HTMLElement | null> = {}
const chartInstances: Record<number, echarts.ECharts> = {}
const chartDurations: Record<number, number> = reactive({})
const expandedRowKeys = ref<number[]>([])

function setChartRef(pointId: number, el: HTMLElement | null) {
  chartRefs[pointId] = el
}

// ===== 状态映射 =====
type TagType = 'success' | 'warning' | 'danger' | 'info' | 'primary'

const statusTagType = computed<TagType>(() => {
  const map: Record<string, TagType> = {
    online: 'success',
    offline: 'danger',
    maintenance: 'warning',
    alarm: 'danger'
  }
  return map[deviceData.value?.status || ''] || 'info'
})

const statusText = computed(() => {
  const map: Record<string, string> = {
    online: '在线',
    offline: '离线',
    maintenance: '维护中',
    alarm: '告警'
  }
  return map[deviceData.value?.status || ''] || deviceData.value?.status || '--'
})

function pointStatusType(status: string): TagType {
  const map: Record<string, TagType> = { normal: 'success', alarm: 'danger', offline: 'info' }
  return map[status] || 'info'
}

function pointStatusText(status: string): string {
  const map: Record<string, string> = { normal: '正常', alarm: '告警', offline: '离线' }
  return map[status] || status
}

function alarmLevelType(level: string): TagType {
  const map: Record<string, TagType> = {
    critical: 'danger',
    major: 'warning',
    minor: 'primary',
    info: 'info'
  }
  return map[level] || 'info'
}

function alarmLevelText(level: string): string {
  const map: Record<string, string> = {
    critical: '紧急',
    major: '重要',
    minor: '次要',
    info: '提示'
  }
  return map[level] || level
}

function qualityRowClass({ row }: { row: PointRealtimeItem }) {
  return row.quality === 2 ? 'unreliable-row' : ''
}

// ===== 数据加载 =====
async function loadDetail() {
  const id = Number(route.params.id)
  if (!id) return

  loading.value = true
  try {
    const res = await getDeviceDetail(id)
    deviceData.value = res.device
    points.value = res.points
    alarms.value = res.alarms
  } catch (e) {
    console.error('加载设备详情失败', e)
    ElMessage.error('加载设备详情失败')
  } finally {
    loading.value = false
  }
}

// ===== 展开行处理 =====
function handleExpandChange(row: PointRealtimeItem, expandedRows: PointRealtimeItem[]) {
  expandedRowKeys.value = expandedRows.map(r => r.id)
  if (row.point_type === 'AI' && expandedRows.some(r => r.id === row.id)) {
    if (!chartDurations[row.id]) {
      chartDurations[row.id] = 60
    }
    nextTick(() => {
      initChart(row.id)
      loadTrendData(row.id)
    })
  }
}

function initChart(pointId: number) {
  const el = chartRefs[pointId]
  if (!el) return
  if (chartInstances[pointId]) {
    chartInstances[pointId].dispose()
  }
  chartInstances[pointId] = echarts.init(el)
}

async function loadTrendData(pointId: number) {
  const duration = chartDurations[pointId] || 60
  const chart = chartInstances[pointId]
  if (!chart) return

  chart.showLoading()
  try {
    const data: TrendData[] = await getPointTrend(pointId, { duration, limit: 500 })
    const point = points.value.find(p => p.id === pointId)

    const option: echarts.EChartsOption = {
      tooltip: { trigger: 'axis' },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: {
        type: 'category',
        data: data.map(d => d.time),
        axisLabel: {
          rotate: 30,
          formatter: (value: string) => value.substring(5, 16)
        }
      },
      yAxis: {
        type: 'value',
        name: point?.unit || ''
      },
      series: [{
        name: point?.point_name || '数值',
        type: 'line',
        data: data.map(d => d.value),
        smooth: true,
        areaStyle: { opacity: 0.3 },
        itemStyle: { color: '#409eff' }
      }]
    }
    chart.setOption(option, true)
  } catch (e) {
    console.error('加载趋势数据失败', e)
  } finally {
    chart.hideLoading()
  }
}

// ===== Resize 处理 =====
function handleResize() {
  Object.values(chartInstances).forEach(chart => chart?.resize())
}

// ===== 自动刷新 =====
let refreshTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  loadDetail()
  refreshTimer = setInterval(loadDetail, 30000)
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
  window.removeEventListener('resize', handleResize)
  Object.values(chartInstances).forEach(chart => chart?.dispose())
})
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.device-detail-page {
  @include page-special;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .expand-chart-wrapper {
    padding: 12px 16px;

    .chart-toolbar {
      margin-bottom: 8px;
    }

    .trend-chart {
      height: 260px;
    }
  }

  :deep(.unreliable-row) {
    background-color: #FEF0F0 !important;
  }
}
</style>
