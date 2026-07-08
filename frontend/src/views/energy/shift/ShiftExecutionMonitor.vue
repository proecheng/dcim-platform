<template>
  <div class="shift-execution-monitor">
    <el-page-header @back="$router.back()" title="返回">
      <template #content>
        <span>实时监控 - {{ execution.execution_code }}</span>
      </template>
    </el-page-header>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="执行进度" :value="progress" suffix="%" />
          <el-progress :percentage="progress" :status="progressStatus" style="margin-top: 10px" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="目标功率" :value="execution.target_shift_power || 0" suffix="kW" :precision="1" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="实际功率" :value="realtimeData.actual_power || 0" suffix="kW" :precision="1" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="完成率" :value="completionRate" suffix="%" :precision="1" />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="hover" style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>功率曲线</span>
          <el-button-group>
            <el-button size="small" @click="refreshChart">刷新</el-button>
            <el-button size="small" @click="toggleAutoRefresh">
              {{ autoRefresh ? '停止自动刷新' : '开启自动刷新' }}
            </el-button>
          </el-button-group>
        </div>
      </template>
      <div ref="chartRef" style="width: 100%; height: 400px"></div>
    </el-card>

    <el-card shadow="hover" style="margin-top: 20px">
      <template #header>
        <span>设备执行状态</span>
      </template>
      <el-table :data="deviceStatus" border v-loading="loading">
        <el-table-column type="index" label="#" width="60" />
        <el-table-column prop="device_name" label="设备名称" min-width="180" />
        <el-table-column prop="shift_action" label="转移动作" width="120" />
        <el-table-column prop="target_power" label="目标功率 (kW)" width="140" align="right">
          <template #default="{ row }">
            {{ row.target_power?.toFixed(1) || 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="current_power" label="当前功率 (kW)" width="140" align="right">
          <template #default="{ row }">
            {{ row.current_power?.toFixed(1) || 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="执行状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getDeviceStatusType(row.status)">{{ getDeviceStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="120">
          <template #default="{ row }">
            <el-progress :percentage="row.progress || 0" :status="row.progress === 100 ? 'success' : undefined" />
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="hover" style="margin-top: 20px" v-if="alarms.length > 0">
      <template #header>
        <span>异常告警 ({{ alarms.length }})</span>
      </template>
      <el-timeline>
        <el-timeline-item
          v-for="(alarm, index) in alarms"
          :key="index"
          :timestamp="alarm.timestamp"
          :type="alarm.level === 'critical' ? 'danger' : 'warning'"
        >
          <h4>{{ alarm.title }}</h4>
          <p>{{ alarm.message }}</p>
        </el-timeline-item>
      </el-timeline>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  getExecutionDetail,
  getExecutionRealtime,
  type ShiftExecution,
  type ShiftExecutionRealtimePayload
} from '@/api/modules/shift'
import * as echarts from 'echarts'

const route = useRoute()
const loading = ref(false)
const execution = ref<Partial<ShiftExecution>>({})
const realtimeData = ref<Partial<ShiftExecutionRealtimePayload>>({})
const deviceStatus = ref<any[]>([])
const alarms = ref<any[]>([])
const chartRef = ref<HTMLElement>()
const chartInstance = ref<echarts.ECharts>()
const autoRefresh = ref(true)
const refreshTimer = ref<number>()

const progress = computed(() => {
  if (!execution.value.start_time) return 0
  const start = new Date(execution.value.start_time).getTime()
  const end = execution.value.end_time ? new Date(execution.value.end_time).getTime() : Date.now()
  const total = execution.value.duration || 60 * 60 * 1000 // Default 1 hour
  return Math.min(100, Math.floor((end - start) / total * 100))
})

const progressStatus = computed(() => {
  if (execution.value.status === 'completed') return 'success'
  if (execution.value.status === 'failed') return 'exception'
  return undefined
})

const completionRate = computed(() => {
  if (!execution.value.target_shift_power || execution.value.target_shift_power === 0) return 0
  return ((realtimeData.value.actual_power || 0) / execution.value.target_shift_power * 100)
})

const fetchDetail = async () => {
  try {
    const id = Number(route.params.id)
    const res = await getExecutionDetail(id)
    execution.value = res.data
  } catch (error: any) {
    ElMessage.error(error.message || '获取执行详情失败')
  }
}

const fetchRealtime = async () => {
  loading.value = true
  try {
    const id = Number(route.params.id)
    const res = await getExecutionRealtime(id)
    realtimeData.value = res.data
    deviceStatus.value = res.data.device_status || []
    if (res.data.alarms) {
      alarms.value = res.data.alarms
    }
    updateChart(res.data)
  } catch (error: any) {
    ElMessage.error(error.message || '获取实时数据失败')
  } finally {
    loading.value = false
  }
}

const initChart = () => {
  if (!chartRef.value) return
  chartInstance.value = echarts.init(chartRef.value)
  const option = {
    title: {
      text: '功率实时曲线'
    },
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      data: ['目标功率', '实际功率']
    },
    xAxis: {
      type: 'time',
      boundaryGap: false
    },
    yAxis: {
      type: 'value',
      name: '功率 (kW)'
    },
    series: [
      {
        name: '目标功率',
        type: 'line',
        data: [],
        smooth: true,
        lineStyle: {
          color: '#409EFF',
          width: 2
        }
      },
      {
        name: '实际功率',
        type: 'line',
        data: [],
        smooth: true,
        lineStyle: {
          color: '#67C23A',
          width: 2
        }
      }
    ]
  }
  chartInstance.value.setOption(option)
}

const updateChart = (data: ShiftExecutionRealtimePayload) => {
  if (!chartInstance.value) return
  const now = new Date()
  const targetData = chartInstance.value.getOption().series[0].data || []
  const actualData = chartInstance.value.getOption().series[1].data || []
  
  targetData.push([now, execution.value.target_shift_power || 0])
  actualData.push([now, data.actual_power || 0])
  
  // Keep last 100 points
  if (targetData.length > 100) targetData.shift()
  if (actualData.length > 100) actualData.shift()
  
  chartInstance.value.setOption({
    series: [
      { data: targetData },
      { data: actualData }
    ]
  })
}

const refreshChart = () => {
  fetchRealtime()
}

const toggleAutoRefresh = () => {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) {
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
}

const startAutoRefresh = () => {
  refreshTimer.value = window.setInterval(() => {
    fetchRealtime()
  }, 5000) // Refresh every 5 seconds
}

const stopAutoRefresh = () => {
  if (refreshTimer.value) {
    clearInterval(refreshTimer.value)
    refreshTimer.value = undefined
  }
}

type TagType = 'primary' | 'success' | 'info' | 'warning' | 'danger'

const getDeviceStatusType = (status: string): TagType => {
  const map: Record<string, TagType> = {
    pending: 'info',
    running: 'warning',
    completed: 'success',
    failed: 'danger'
  }
  return map[status] || 'info'
}

const getDeviceStatusLabel = (status: string) => {
  const map: Record<string, string> = {
    pending: '待执行',
    running: '执行中',
    completed: '已完成',
    failed: '失败'
  }
  return map[status] || status
}

onMounted(async () => {
  await fetchDetail()
  await fetchRealtime()
  initChart()
  if (autoRefresh.value) {
    startAutoRefresh()
  }
})

onUnmounted(() => {
  stopAutoRefresh()
  if (chartInstance.value) {
    chartInstance.value.dispose()
  }
})
</script>

<style scoped lang="scss">
.shift-execution-monitor {
  padding: 20px;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}
</style>
