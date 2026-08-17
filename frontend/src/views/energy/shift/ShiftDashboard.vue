<template>
  <div class="shift-dashboard">
    <el-row :gutter="20" class="stat-cards">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-value">{{ overview.total_plans || 0 }}</div>
            <div class="stat-label">总计划数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-value warning">{{ overview.pending_approval || 0 }}</div>
            <div class="stat-label">待审批</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-value primary">{{ overview.executing || 0 }}</div>
            <div class="stat-label">执行中</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-value success">{{ overview.completed_today || 0 }}</div>
            <div class="stat-label">今日完成</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card opportunity-card" @click="goToOpportunities">
          <div class="stat-content">
            <div class="stat-value opportunity">{{ overview.opportunities_count || 0 }}</div>
            <div class="stat-label">转移机会</div>
          </div>
          <el-icon class="card-icon"><Opportunity /></el-icon>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-value cost">{{ overview.total_cost_saving_today?.toFixed(0) || 0 }}</div>
            <div class="stat-label">今日成本节省 (元)</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-value energy">{{ overview.total_energy_saving_today?.toFixed(0) || 0 }}</div>
            <div class="stat-label">今日节能量 (kWh)</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-value power">{{ overview.total_shift_power_today?.toFixed(1) || 0 }}</div>
            <div class="stat-label">今日转移功率 (kW)</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-value">{{ successRate.toFixed(1) }}%</div>
            <div class="stat-label">成功率</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="16">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>转移趋势</span>
              <el-radio-group v-model="trendDays" size="small" @change="loadTrends">
                <el-radio-button :value="7">近7天</el-radio-button>
                <el-radio-button :value="14">近14天</el-radio-button>
                <el-radio-button :value="30">近30天</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <div ref="trendChartRef" style="height: 350px"></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>
            <span>实时执行状态</span>
          </template>
          <div class="realtime-status">
            <div class="status-item">
              <span class="label">执行状态</span>
              <el-tag :type="isExecuting ? 'success' : 'info'">
                {{ isExecuting ? '执行中' : '空闲' }}
              </el-tag>
            </div>
            <div class="status-item">
              <span class="label">当前转移功率</span>
              <span class="value">{{ realtime.current_shift_power?.toFixed(1) || 0 }} kW</span>
            </div>
            <div class="status-item">
              <span class="label">目标转移功率</span>
              <span class="value">{{ realtime.target_shift_power?.toFixed(1) || 0 }} kW</span>
            </div>
            <div class="status-item">
              <span class="label">完成率</span>
              <el-progress :percentage="(realtime.completion_rate * 100) || 0" />
            </div>
            <div class="status-item">
              <span class="label">活跃设备数</span>
              <span class="value">{{ realtime.active_devices || 0 }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { getDashboardOverview, getRealtimeData, getTrends } from '@/api/modules/shift'
import { ElMessage } from 'element-plus'

const router = useRouter()

const overview = reactive<any>({})
const realtime = reactive<any>({})
const trendDays = ref(7)
const successRate = computed(() => {
  const rate = Number(overview.success_rate)
  return Number.isFinite(rate) ? rate * 100 : 0
})
const isExecuting = computed(() => ['executing', 'in_progress', 'running'].includes(realtime.execution_status))
const trendChartRef = ref<HTMLElement>()
let trendChart: echarts.ECharts | null = null
let refreshTimer: any = null

const loadOverview = async () => {
  try {
    const res = await getDashboardOverview()
    Object.assign(overview, (res as any)?.data ?? res ?? {})
  } catch (error: any) {
    ElMessage.error(error.message || '加载概览数据失败')
  }
}

const loadRealtime = async () => {
  try {
    const res = await getRealtimeData()
    Object.assign(realtime, (res as any)?.data ?? res ?? {})
  } catch (error: any) {
    console.error('加载实时数据失败', error)
  }
}

const loadTrends = async () => {
  try {
    const res = await getTrends(trendDays.value)
    const trends = Array.isArray(res) ? res : (res as any)?.data ?? []
    renderTrendChart(trends)
  } catch (error: any) {
    ElMessage.error(error.message || '加载趋势数据失败')
  }
}

const renderTrendChart = (trends: any[]) => {
  if (!trendChartRef.value) return
  if (!trendChart) {
    trendChart = echarts.init(trendChartRef.value)
  }

  const dates = trends.map((t: any) => t.date)
  const costSaving = trends.map((t: any) => t.cost_saving || 0)
  const energySaving = trends.map((t: any) => t.energy_saving || 0)
  const shiftPower = trends.map((t: any) => t.total_shift_power || 0)

  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['成本节省', '节能量', '转移功率'] },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: dates },
    yAxis: [
      { type: 'value', name: '成本/能量', position: 'left' },
      { type: 'value', name: '功率 (kW)', position: 'right' },
    ],
    series: [
      { name: '成本节省', type: 'bar', data: costSaving, yAxisIndex: 0 },
      { name: '节能量', type: 'bar', data: energySaving, yAxisIndex: 0 },
      { name: '转移功率', type: 'line', data: shiftPower, yAxisIndex: 1 },
    ],
  })
}

const goToOpportunities = () => {
  router.push('/energy/shift/opportunities')
}
const startRefresh = () => {
  refreshTimer = setInterval(() => {
    loadRealtime()
  }, 10000)
}

onMounted(() => {
  loadOverview()
  loadRealtime()
  loadTrends()
  startRefresh()
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
  if (trendChart) trendChart.dispose()
})
</script>

<style scoped lang="scss">
.shift-dashboard {
  .stat-cards {
    .stat-card {
      .stat-content {
        text-align: center;
        .stat-value {
          font-size: 32px;
          font-weight: bold;
          color: #409eff;
          &.warning { color: #e6a23c; }
          &.primary { color: #409eff; }
          &.success { color: #67c23a; }
          &.cost { color: #f56c6c; }
          &.energy { color: #67c23a; }
          &.power { color: #409eff; }
          &.opportunity { color: #e6a23c; }
        }
        .stat-label {
          margin-top: 8px;
          font-size: 14px;
          color: #909399;
        }
      }
    }
    .opportunity-card {
      cursor: pointer;
      position: relative;
      transition: all 0.3s;
      
      &:hover {
        transform: translateY(-4px);
        box-shadow: 0 4px 12px rgba(230, 162, 60, 0.3);
      }
      
      .card-icon {
        position: absolute;
        right: 20px;
        top: 50%;
        transform: translateY(-50%);
        font-size: 32px;
        color: #e6a23c;
        opacity: 0.3;
      }
    }
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .realtime-status {
    .status-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
      .label {
        font-size: 14px;
        color: #606266;
      }
      .value {
        font-size: 16px;
        font-weight: bold;
        color: #409eff;
      }
    }
  }
}
</style>
