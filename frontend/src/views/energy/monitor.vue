<template>
  <div class="energy-monitor">
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stat-cards">
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-value">{{ summary.total_power?.toFixed(1) || 0 }}</div>
            <div class="stat-label">总功率 (kW)</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-value it">{{ summary.it_power?.toFixed(1) || 0 }}</div>
            <div class="stat-label">IT负载 (kW)</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-value cooling">{{ summary.cooling_power?.toFixed(1) || 0 }}</div>
            <div class="stat-label">制冷功率 (kW)</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card pue-card">
          <div class="stat-content">
            <div class="stat-value pue" :class="getPUEClass(summary.current_pue)">
              {{ summary.current_pue != null ? summary.current_pue.toFixed(2) : '--' }}
            </div>
            <div class="stat-label">当前 PUE</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-value">{{ summary.today_energy?.toFixed(0) || 0 }}</div>
            <div class="stat-label">今日用电 (kWh)</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-value cost">{{ summary.today_cost?.toFixed(0) || 0 }}</div>
            <div class="stat-label">今日电费 (元)</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <!-- PUE仪表盘 -->
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>PUE 实时监测</span>
              <el-tag
                :type="pueData.data_source === 'realtime' ? 'success' : 'info'"
                size="small"
              >
                {{ pueData.data_source === 'realtime' ? '实时数据' : '模拟数据' }}
              </el-tag>
            </div>
          </template>
          <div ref="pueChartRef" class="pue-chart"></div>
          <el-alert
            v-if="(pueData.unreliable_count ?? 0) > 0"
            type="warning"
            :closable="false"
            style="margin-bottom: 8px;"
          >
            <template #title>
              有 {{ pueData.unreliable_count }} 个点位数据不可靠，PUE 可能不准确
            </template>
          </el-alert>
          <div class="pue-breakdown">
            <div class="breakdown-item">
              <span class="label">总功率</span>
              <span class="value">{{ pueData.total_power != null ? pueData.total_power.toFixed(1) : '--' }} kW</span>
            </div>
            <div class="breakdown-item">
              <span class="label">IT负载</span>
              <span class="value">{{ pueData.it_power != null ? pueData.it_power.toFixed(1) : '--' }} kW</span>
            </div>
            <div class="breakdown-item">
              <span class="label">制冷功率</span>
              <span class="value">{{ pueData.cooling_power != null ? pueData.cooling_power.toFixed(1) : '--' }} kW</span>
            </div>
            <div class="breakdown-item">
              <span class="label">UPS损耗</span>
              <span class="value">{{ pueData.ups_loss != null ? pueData.ups_loss.toFixed(1) : '--' }} kW</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- PUE趋势 -->
      <el-col :span="16">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>PUE 趋势</span>
              <el-radio-group v-model="puePeriod" size="small" @change="loadPUETrend">
                <el-radio-button value="hour">小时</el-radio-button>
                <el-radio-button value="day">日</el-radio-button>
                <el-radio-button value="week">周</el-radio-button>
                <el-radio-button value="month">月</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <div ref="pueTrendChartRef" class="trend-chart"></div>
          <div class="trend-stats">
            <el-tag type="success">最低: {{ pueTrend.min_pue?.toFixed(2) || '-' }}</el-tag>
            <el-tag type="warning">平均: {{ pueTrend.avg_pue?.toFixed(2) || '-' }}</el-tag>
            <el-tag type="danger">最高: {{ pueTrend.max_pue?.toFixed(2) || '-' }}</el-tag>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- V2.3 增强: 需量状态、节能建议、成本分析 -->
    <el-row :gutter="20" style="margin-top: 20px;">
      <!-- 需量状态 -->
      <el-col :span="8">
        <el-card shadow="hover" class="dashboard-card">
          <template #header>
            <div class="card-header">
              <span>需量状态</span>
              <el-button type="primary" link @click="goToAnalysis">详情</el-button>
            </div>
          </template>
          <div ref="demandChartRef" class="demand-chart"></div>
          <div class="demand-info">
            <div class="info-row">
              <span class="label">当前需量</span>
              <span class="value">{{ dashboard.demand?.current_demand?.toFixed(1) || 0 }} kW</span>
            </div>
            <div class="info-row">
              <span class="label">申报需量</span>
              <span class="value">{{ dashboard.demand?.declared_demand || 0 }} kW</span>
            </div>
            <div class="info-row">
              <span class="label">今日最大</span>
              <span class="value">{{ dashboard.demand?.max_today?.toFixed(1) || 0 }} kW</span>
            </div>
            <div class="info-row" v-if="dashboard.demand?.over_declared_risk">
              <el-tag type="danger" size="small">超申报风险</el-tag>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 节能建议 -->
      <el-col :span="8">
        <el-card shadow="hover" class="dashboard-card suggestion-card">
          <template #header>
            <div class="card-header">
              <span>节能建议</span>
              <el-button type="primary" link @click="goToSuggestions">查看全部</el-button>
            </div>
          </template>
          <div class="suggestion-stats">
            <div class="stat-item">
              <div class="stat-number">{{ dashboard.suggestions?.pending_count || 0 }}</div>
              <div class="stat-label">待处理建议</div>
            </div>
            <div class="stat-item highlight">
              <div class="stat-number danger">{{ dashboard.suggestions?.high_priority_count || 0 }}</div>
              <div class="stat-label">高优先级</div>
            </div>
          </div>
          <div class="potential-saving">
            <div class="saving-title">潜在节能</div>
            <div class="saving-row">
              <span>节电量</span>
              <strong>{{ dashboard.suggestions?.potential_saving_kwh?.toFixed(0) || 0 }} kWh/月</strong>
            </div>
            <div class="saving-row">
              <span>节省费用</span>
              <strong class="cost">¥{{ dashboard.suggestions?.potential_saving_cost?.toFixed(0) || 0 }}/月</strong>
            </div>
          </div>
          <el-button type="success" style="width: 100%; margin-top: 12px;" @click="goToRegulation">
            立即调节
          </el-button>
        </el-card>
      </el-col>

      <!-- 成本分析 -->
      <el-col :span="8">
        <el-card shadow="hover" class="dashboard-card">
          <template #header>
            <div class="card-header">
              <span>成本分析</span>
              <el-button type="primary" link @click="goToStatistics">详情</el-button>
            </div>
          </template>
          <div class="cost-stats">
            <div class="cost-item">
              <div class="cost-label">今日电费</div>
              <div class="cost-value">¥{{ dashboard.cost?.today_cost?.toFixed(0) || 0 }}</div>
            </div>
            <div class="cost-item">
              <div class="cost-label">本月电费</div>
              <div class="cost-value large">¥{{ dashboard.cost?.month_cost?.toFixed(0) || 0 }}</div>
            </div>
          </div>
          <div class="peak-valley">
            <div class="pv-title">峰谷用电比例</div>
            <el-progress
              :percentage="dashboard.cost?.peak_ratio || 0"
              :stroke-width="20"
              :format="() => `峰 ${dashboard.cost?.peak_ratio || 0}%`"
              color="#f56c6c"
            />
            <el-progress
              :percentage="dashboard.cost?.valley_ratio || 0"
              :stroke-width="20"
              :format="() => `谷 ${dashboard.cost?.valley_ratio || 0}%`"
              color="#67c23a"
              style="margin-top: 8px;"
            />
            <div class="pv-hint">平均电价: ¥{{ dashboard.cost?.avg_price?.toFixed(2) || '0.80' }}/kWh</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 设备实时功率 -->
    <el-card shadow="hover" style="margin-top: 20px;">
      <template #header>
        <div class="card-header">
          <span>设备实时功率</span>
          <el-button type="primary" link @click="refreshPowerData">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
      </template>

      <el-table :data="powerData" stripe border v-loading="loading">
        <el-table-column prop="device_code" label="设备编码" width="120" />
        <el-table-column prop="device_name" label="设备名称" width="150" />
        <el-table-column prop="device_type" label="设备类型" width="100">
          <template #default="{ row }">
            <el-tag :type="deviceTypeTag[row.device_type]" size="small">
              {{ deviceTypeText[row.device_type] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="电压 (V)" width="150">
          <template #default="{ row }">
            <span v-if="row.voltage_a">
              A: {{ row.voltage_a?.toFixed(1) }}
              <template v-if="row.voltage_b"> / B: {{ row.voltage_b?.toFixed(1) }} / C: {{ row.voltage_c?.toFixed(1) }}</template>
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="电流 (A)" width="150">
          <template #default="{ row }">
            <span v-if="row.current_a">
              A: {{ row.current_a?.toFixed(1) }}
              <template v-if="row.current_b"> / B: {{ row.current_b?.toFixed(1) }} / C: {{ row.current_c?.toFixed(1) }}</template>
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="active_power" label="有功功率 (kW)" width="120">
          <template #default="{ row }">
            {{ row.active_power?.toFixed(2) || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="power_factor" label="功率因数" width="100">
          <template #default="{ row }">
            {{ row.power_factor?.toFixed(2) || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="load_rate" label="负载率（%）" width="120">
          <template #default="{ row }">
            <el-progress
              v-if="row.load_rate !== undefined"
              :percentage="Math.min(Number((row.load_rate * 100).toFixed(2)), 100)"
              :color="getLoadColor(row.load_rate * 100)"
              :stroke-width="12"
              :format="(p: number) => p.toFixed(2)"
            />
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="statusType[row.status]" size="small">
              {{ statusText[row.status] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="update_time" label="更新时间" width="160">
          <template #default="{ row }">
            {{ formatDateTime(row.update_time) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { useRouter } from 'vue-router'
import {
  getPowerSummary, getRealtimePower, getCurrentPUE, getPUETrend,
  getEnergyDashboard,
  type RealtimePowerSummary, type RealtimePowerData, type PUEData, type PUETrend,
  type EnergyDashboardData
} from '@/api/modules/energy'

const router = useRouter()
const pueChartRef = ref<HTMLElement>()
const pueTrendChartRef = ref<HTMLElement>()
const demandChartRef = ref<HTMLElement>()
let pueChart: echarts.ECharts | null = null
let pueTrendChart: echarts.ECharts | null = null
let demandChart: echarts.ECharts | null = null
let refreshTimer: number | null = null

const loading = ref(false)
const summary = ref<Partial<RealtimePowerSummary>>({})
const powerData = ref<RealtimePowerData[]>([])
const pueData = ref<Partial<PUEData>>({})
const pueTrend = ref<Partial<PUETrend>>({})
const puePeriod = ref<'hour' | 'day' | 'week' | 'month'>('day')
const dashboard = ref<Partial<EnergyDashboardData>>({})

const deviceTypeText: Record<string, string> = {
  MAIN: '总进线',
  UPS: 'UPS',
  PDU: '配电柜',
  AC: '空调',
  IT: 'IT设备'
}

type TagType = 'success' | 'warning' | 'danger' | 'info' | 'primary'

const deviceTypeTag: Record<string, TagType> = {
  MAIN: 'danger',
  UPS: 'warning',
  PDU: 'primary',
  AC: 'success',
  IT: 'info'
}

const statusText: Record<string, string> = {
  normal: '正常',
  warning: '告警',
  alarm: '故障',
  offline: '离线'
}

const statusType: Record<string, TagType> = {
  normal: 'success',
  warning: 'warning',
  alarm: 'danger',
  offline: 'info'
}

onMounted(async () => {
  initCharts()
  await refreshAllData()
  // 每30秒刷新一次
  refreshTimer = window.setInterval(refreshAllData, 30000)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
  pueChart?.dispose()
  pueTrendChart?.dispose()
  demandChart?.dispose()
})

function initCharts() {
  if (pueChartRef.value) {
    pueChart = echarts.init(pueChartRef.value)
  }
  if (pueTrendChartRef.value) {
    pueTrendChart = echarts.init(pueTrendChartRef.value)
  }
  if (demandChartRef.value) {
    demandChart = echarts.init(demandChartRef.value)
  }
  window.addEventListener('resize', () => {
    pueChart?.resize()
    pueTrendChart?.resize()
    demandChart?.resize()
  })
}

async function refreshAllData() {
  loading.value = true
  try {
    await Promise.all([
      loadSummary(),
      loadPowerData(),
      loadPUE(),
      loadPUETrend(),
      loadDashboard()
    ])
  } finally {
    loading.value = false
  }
}

async function loadSummary() {
  try {
    const res = await getPowerSummary()
    summary.value = res.data || {}
  } catch (e) {
    console.error('加载汇总数据失败', e)
  }
}

async function refreshPowerData() {
  loading.value = true
  try {
    await loadPowerData()
  } finally {
    loading.value = false
  }
}

async function loadPowerData() {
  try {
    const res = await getRealtimePower()
    powerData.value = res.data || []
  } catch (e) {
    console.error('加载功率数据失败', e)
  }
}

async function loadPUE() {
  try {
    const res = await getCurrentPUE()
    pueData.value = res.data || {}
    updatePUEChart()
  } catch (e) {
    console.error('加载PUE数据失败', e)
  }
}

async function loadPUETrend() {
  try {
    const res = await getPUETrend({ period: puePeriod.value })
    pueTrend.value = res.data || {}
    updatePUETrendChart()
  } catch (e) {
    console.error('加载PUE趋势失败', e)
  }
}

async function loadDashboard() {
  try {
    const res = await getEnergyDashboard()
    const data = (res as any)?.data ?? res
    dashboard.value = data && typeof data === 'object' ? data : {}
    updateDemandChart()
  } catch (e) {
    console.error('加载仪表盘数据失败', e)
    dashboard.value = {}
    updateDemandChart()
  }
}


// 图表主题色常量
const chartColors = {
  success: '#52c41a',
  warning: '#faad14',
  error: '#f5222d',
  primary: '#1890ff',
  accent: '#00d4ff',
  text: 'rgba(255, 255, 255, 0.65)',
  textSecondary: 'rgba(255, 255, 255, 0.45)',
  axisLine: 'rgba(255, 255, 255, 0.1)',
  splitLine: 'rgba(255, 255, 255, 0.05)'
}

function updateDemandChart() {
  if (!demandChart || !dashboard.value.demand) return

  const demand = dashboard.value.demand
  const utilization = demand.utilization_rate || 0
  const statusColor = utilization > 90 ? chartColors.error : utilization > 70 ? chartColors.warning : chartColors.success
  const option: echarts.EChartsOption = {
    series: [{
      type: 'gauge',
      startAngle: 180,
      endAngle: 0,
      min: 0,
      max: 100,
      splitNumber: 5,
      itemStyle: {
        color: statusColor
      },
      progress: {
        show: true,
        width: 18
      },
      pointer: {
        show: true,
        length: '60%',
        width: 6,
        itemStyle: { color: statusColor }
      },
      axisLine: {
        lineStyle: {
          width: 18,
          color: [[0.7, chartColors.success], [0.9, chartColors.warning], [1, chartColors.error]]
        }
      },
      axisTick: { show: false },
      splitLine: {
        distance: -18,
        length: 10,
        lineStyle: { width: 2, color: chartColors.text }
      },
      axisLabel: {
        distance: -30,
        color: chartColors.text,
        fontSize: 11,
        formatter: '{value}%'
      },
      title: {
        offsetCenter: [0, '70%'],
        fontSize: 14,
        color: chartColors.textSecondary
      },
      detail: {
        valueAnimation: true,
        offsetCenter: [0, '40%'],
        fontSize: 24,
        fontWeight: 'bold',
        formatter: '{value}%',
        color: statusColor
      },
      data: [{ value: parseFloat(utilization.toFixed(1)), name: '需量利用率' }]
    }]
  }
  demandChart.setOption(option)
}

function goToSuggestions() {
  // 跳转到节能中心的优化总览标签页
  router.push('/energy/analysis?tab=overview')
}

function goToRegulation() {
  router.push('/energy/regulation')
}

function goToAnalysis() {
  // 跳转到节能中心的需量分析标签页
  router.push('/energy/analysis?tab=demand')
}

function goToStatistics() {
  router.push('/energy/statistics')
}

// 格式化日期时间
function formatDateTime(dateTimeStr: string): string {
  if (!dateTimeStr) return '-'

  try {
    // 处理 ISO 格式时间字符串，如 "2024-01-15T10:30:00Z" 或 "2024-01-15T10:30:00.000Z"
    const date = new Date(dateTimeStr)

    // 检查是否是有效日期
    if (isNaN(date.getTime())) {
      // 如果已经是 YYYY-MM-DD HH:mm:ss 格式，直接返回
      if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(dateTimeStr)) {
        return dateTimeStr
      }
      return dateTimeStr
    }

    // 格式化为 YYYY-MM-DD HH:mm:ss
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    const seconds = String(date.getSeconds()).padStart(2, '0')

    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
  } catch (e) {
    console.error('格式化时间失败:', dateTimeStr, e)
    return dateTimeStr
  }
}

function updatePUEChart() {
  if (!pueChart) return

  const pue = pueData.value.current_pue
  if (pue == null) {
    // PUE 不可用时显示空仪表盘
    const option: echarts.EChartsOption = {
      series: [{
        type: 'gauge',
        startAngle: 200,
        endAngle: -20,
        min: 1,
        max: 3,
        splitNumber: 4,
        progress: { show: false },
        pointer: { show: false },
        axisLine: {
          lineStyle: {
            width: 20,
            color: [[1, 'rgba(255,255,255,0.1)']]
          }
        },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        anchor: { show: false },
        title: { show: false },
        detail: {
          valueAnimation: false,
          width: '60%',
          lineHeight: 40,
          borderRadius: 8,
          offsetCenter: [0, '20%'],
          fontSize: 32,
          fontWeight: 'bold',
          formatter: '--',
          color: chartColors.textSecondary
        },
        data: [{ value: 0 }]
      }]
    }
    pueChart.setOption(option)
    return
  }

  const pueColor = getPUEColor(pue)
  const option: echarts.EChartsOption = {
    series: [{
      type: 'gauge',
      startAngle: 200,
      endAngle: -20,
      min: 1,
      max: 3,
      splitNumber: 4,
      itemStyle: {
        color: pueColor
      },
      progress: {
        show: true,
        width: 20
      },
      pointer: {
        show: false
      },
      axisLine: {
        lineStyle: {
          width: 20,
          color: [[0.25, chartColors.success], [0.5, chartColors.warning], [0.75, chartColors.error], [1, '#c45656']]
        }
      },
      axisTick: {
        distance: -30,
        splitNumber: 5,
        lineStyle: { width: 1, color: chartColors.text }
      },
      splitLine: {
        distance: -35,
        length: 10,
        lineStyle: { width: 2, color: chartColors.text }
      },
      axisLabel: {
        distance: -20,
        color: chartColors.text,
        fontSize: 12
      },
      anchor: {
        show: false
      },
      title: {
        show: false
      },
      detail: {
        valueAnimation: true,
        width: '60%',
        lineHeight: 40,
        borderRadius: 8,
        offsetCenter: [0, '20%'],
        fontSize: 32,
        fontWeight: 'bold',
        formatter: '{value}',
        color: pueColor
      },
      data: [{ value: parseFloat(pue.toFixed(2)) }]
    }]
  }
  pueChart.setOption(option)
}

function updatePUETrendChart() {
  if (!pueTrendChart || !pueTrend.value.data) return

  const data = pueTrend.value.data
  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      renderMode: 'richText',
      backgroundColor: 'rgba(26, 42, 74, 0.95)',
      borderColor: 'rgba(0, 212, 255, 0.3)',
      textStyle: { color: 'rgba(255, 255, 255, 0.85)' },
      formatter: (params: any) => {
        const d = params[0]
        return `${d.axisValue}\nPUE: ${d.value?.toFixed(2)}`
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: data.map(d => d.record_time),
      axisLine: { lineStyle: { color: chartColors.axisLine } },
      axisLabel: {
        color: chartColors.text,
        rotate: 30,
        formatter: (value: string) => value.substring(5, 16)
      },
      splitLine: { lineStyle: { color: chartColors.splitLine } }
    },
    yAxis: {
      type: 'value',
      name: 'PUE',
      nameTextStyle: { color: chartColors.text },
      min: 1,
      max: 3,
      axisLine: { lineStyle: { color: chartColors.axisLine } },
      axisLabel: { color: chartColors.text },
      splitLine: { lineStyle: { color: chartColors.splitLine } }
    },
    series: [{
      name: 'PUE',
      type: 'line',
      data: data.map(d => d.pue),
      smooth: true,
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(0, 212, 255, 0.4)' },
            { offset: 1, color: 'rgba(0, 212, 255, 0.05)' }
          ]
        }
      },
      itemStyle: { color: chartColors.accent },
      lineStyle: { color: chartColors.accent, width: 2 },
      markLine: {
        data: [
          { yAxis: 1.5, name: '优秀', lineStyle: { color: chartColors.success } },
          { yAxis: 2.0, name: '良好', lineStyle: { color: chartColors.warning } }
        ]
      }
    }]
  }
  pueTrendChart.setOption(option)
}

function getPUEClass(pue: number | null | undefined) {
  if (pue == null) return ''
  if (pue < 1.5) return 'excellent'
  if (pue < 2.0) return 'good'
  if (pue < 2.5) return 'normal'
  return 'poor'
}

function getPUEColor(pue: number) {
  if (pue < 1.5) return chartColors.success
  if (pue < 2.0) return chartColors.warning
  if (pue < 2.5) return chartColors.error
  return '#c45656'
}

function getLoadColor(percent: number) {
  if (percent < 60) return chartColors.success
  if (percent < 80) return chartColors.warning
  return chartColors.error
}
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.energy-monitor {
  @include page-dashboard(6);
  .stat-cards {
    margin-bottom: 20px;
  }

  .stat-card {
    text-align: center;

    .stat-content {
      padding: 10px 0;
    }

    .stat-value {
      font-size: 28px;
      font-weight: bold;
      color: var(--primary-color);

      &.it { color: var(--success-color); }
      &.cooling { color: var(--warning-color); }
      &.cost { color: var(--error-color); }
      &.pue {
        &.excellent { color: var(--success-color); }
        &.good { color: var(--warning-color); }
        &.normal { color: var(--error-color); }
        &.poor { color: #c45656; }
      }
    }

    .stat-label {
      font-size: 14px;
      color: var(--text-secondary);
      margin-top: 8px;
    }
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .pue-chart {
    height: 200px;
  }

  .pue-breakdown {
    border-top: 1px solid var(--border-color);
    padding-top: 16px;
    margin-top: 16px;

    .breakdown-item {
      display: flex;
      justify-content: space-between;
      margin-bottom: 8px;

      .label {
        color: var(--text-secondary);
      }

      .value {
        font-weight: bold;
        color: var(--text-primary);
      }
    }
  }

  .trend-chart {
    height: 280px;
  }

  .trend-stats {
    display: flex;
    justify-content: center;
    gap: 20px;
    margin-top: 16px;
  }

  // V2.3 增强样式
  .dashboard-card {
    height: 100%;
  }

  .demand-chart {
    height: 160px;
  }

  .demand-info {
    border-top: 1px solid var(--border-color);
    padding-top: 12px;
    margin-top: 12px;

    .info-row {
      display: flex;
      justify-content: space-between;
      margin-bottom: 8px;

      .label {
        color: var(--text-secondary);
      }

      .value {
        font-weight: bold;
        color: var(--text-primary);
      }
    }
  }

  .suggestion-stats {
    display: flex;
    justify-content: space-around;
    padding: 16px 0;

    .stat-item {
      text-align: center;

      .stat-number {
        font-size: 32px;
        font-weight: bold;
        color: var(--primary-color);

        &.danger {
          color: var(--error-color);
        }
      }

      .stat-label {
        font-size: 12px;
        color: var(--text-secondary);
        margin-top: 4px;
      }

      &.highlight {
        padding: 8px 16px;
        background: rgba(245, 34, 45, 0.1);
        border-radius: 8px;
      }
    }
  }

  .potential-saving {
    background: var(--bg-tertiary);
    border-radius: 8px;
    padding: 12px;

    .saving-title {
      font-size: 12px;
      color: var(--text-secondary);
      margin-bottom: 8px;
    }

    .saving-row {
      display: flex;
      justify-content: space-between;
      margin-bottom: 4px;

      span {
        color: var(--text-regular);
      }

      strong {
        color: var(--success-color);

        &.cost {
          color: var(--error-color);
        }
      }
    }
  }

  .cost-stats {
    display: flex;
    justify-content: space-around;
    padding: 16px 0;
    border-bottom: 1px solid var(--border-color);

    .cost-item {
      text-align: center;

      .cost-label {
        font-size: 12px;
        color: var(--text-secondary);
        margin-bottom: 4px;
      }

      .cost-value {
        font-size: 20px;
        font-weight: bold;
        color: var(--error-color);

        &.large {
          font-size: 28px;
        }
      }
    }
  }

  .peak-valley {
    padding-top: 12px;

    .pv-title {
      font-size: 12px;
      color: var(--text-secondary);
      margin-bottom: 12px;
    }

    .pv-hint {
      font-size: 12px;
      color: var(--text-secondary);
      text-align: center;
      margin-top: 12px;
    }
  }
}
</style>
