<template>
  <div class="schedule-dashboard">
    <!-- 顶部操作栏 -->
    <div class="header-bar">
      <el-date-picker
        v-model="selectedDate"
        type="date"
        placeholder="选择日期"
        value-format="YYYY-MM-DD"
        @change="loadSchedule"
        style="width: 180px;"
      />
      <el-button type="primary" @click="runOptimization" :loading="loading.optimize">
        <el-icon><Cpu /></el-icon>
        重新优化
      </el-button>
      <el-button @click="loadSchedule" :loading="loading.schedule">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>

    <!-- 汇总统计卡片 -->
    <el-row :gutter="20" class="summary-row" v-if="result">
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <div class="stat-item">
            <div class="label">优化状态</div>
            <div class="value">
              <el-tag :type="result.optimization?.status === 'success' ? 'success' : 'danger'">
                {{ result.optimization?.status === 'success' ? '优化成功' : '优化失败' }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <div class="stat-item">
            <div class="label">预计最大需量</div>
            <div class="value highlight">{{ result.optimization?.max_demand?.toFixed(1) || 0 }} kW</div>
            <div class="sub-text">目标: {{ result.optimization?.demand_target?.toFixed(1) || 0 }} kW</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <div class="stat-item">
            <div class="label">预计日电费</div>
            <div class="value">¥ {{ result.optimization?.cost_breakdown?.total_cost?.toFixed(2) || 0 }}</div>
            <div class="sub-text">
              电量费: ¥{{ result.optimization?.cost_breakdown?.energy_cost?.toFixed(2) || 0 }}
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card success">
          <div class="stat-item">
            <div class="label">预计节省</div>
            <div class="value success-text">¥ {{ result.optimization?.expected_saving?.toFixed(2) || 0 }}</div>
            <div class="sub-text">
              节省率: {{ result.optimization?.saving_ratio?.toFixed(1) || 0 }}%
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表区域 -->
    <el-row :gutter="20" class="chart-row">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>负荷预测曲线</span>
              <el-tag size="small" type="info">{{ selectedDate }}</el-tag>
            </div>
          </template>
          <div ref="forecastChartRef" class="chart-container" v-loading="loading.schedule"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>储能充放电计划</span>
              <el-tag size="small" :type="storageActive ? 'success' : 'info'">
                {{ storageActive ? '已启用' : '未配置' }}
              </el-tag>
            </div>
          </template>
          <div ref="storageChartRef" class="chart-container" v-loading="loading.schedule"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 调度甘特图 -->
    <el-card shadow="hover" class="gantt-card">
      <template #header>
        <div class="card-header">
          <span>设备调度甘特图</span>
          <span class="legend">
            <span class="legend-item"><span class="dot on"></span>运行</span>
            <span class="legend-item"><span class="dot charge"></span>充电</span>
            <span class="legend-item"><span class="dot discharge"></span>放电</span>
            <span class="legend-item"><span class="dot curtail"></span>削减</span>
          </span>
        </div>
      </template>
      <div ref="ganttChartRef" class="gantt-container" v-loading="loading.schedule"></div>
    </el-card>

    <!-- 成本分解 -->
    <el-row :gutter="20" class="cost-row" v-if="result?.optimization?.cost_breakdown">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>成本对比</template>
          <div ref="costChartRef" class="chart-container-small"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>各时段用电分布</template>
          <div ref="periodChartRef" class="chart-container-small"></div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed, nextTick } from 'vue'
import { Cpu, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import {
  getDayAheadSchedule,
  runDayAheadOptimization,
  getPeriodColor,
  getPeriodName,
  type DayAheadResult,
  type OptimizationParams
} from '@/api/modules/optimization'

const selectedDate = ref(new Date(Date.now() + 86400000).toISOString().split('T')[0]) // 明天

const loading = ref({
  schedule: false,
  optimize: false
})

const result = ref<DayAheadResult | null>(null)

// 图表引用
const forecastChartRef = ref<HTMLElement>()
const storageChartRef = ref<HTMLElement>()
const ganttChartRef = ref<HTMLElement>()
const costChartRef = ref<HTMLElement>()
const periodChartRef = ref<HTMLElement>()

let forecastChart: echarts.ECharts | null = null
let storageChart: echarts.ECharts | null = null
let ganttChart: echarts.ECharts | null = null
let costChart: echarts.ECharts | null = null
let periodChart: echarts.ECharts | null = null

const storageActive = computed(() => {
  return result.value?.optimization?.storage_schedule?.some(s => s.charge_power > 0 || s.discharge_power > 0)
})

onMounted(async () => {
  await loadSchedule()
})

onUnmounted(() => {
  forecastChart?.dispose()
  storageChart?.dispose()
  ganttChart?.dispose()
  costChart?.dispose()
  periodChart?.dispose()
})

async function loadSchedule() {
  loading.value.schedule = true
  try {
    const res = await getDayAheadSchedule(selectedDate.value)
    if (res.data) {
      result.value = res.data
      await nextTick()
      renderAllCharts()
    }
  } catch (e) {
    console.error('加载调度计划失败', e)
    ElMessage.error('加载调度计划失败')
  } finally {
    loading.value.schedule = false
  }
}

async function runOptimization() {
  loading.value.optimize = true
  try {
    const params: OptimizationParams = {
      target_date: selectedDate.value,
      use_storage: true,
    }
    const res = await runDayAheadOptimization(params)
    if (res.data) {
      ElMessage.success(`优化完成，预计节省 ¥${res.data.expected_saving?.toFixed(2) || 0}`)
      await loadSchedule()
    }
  } catch (e) {
    console.error('优化失败', e)
    ElMessage.error('优化失败')
  } finally {
    loading.value.optimize = false
  }
}

function renderAllCharts() {
  renderForecastChart()
  renderStorageChart()
  renderGanttChart()
  renderCostChart()
  renderPeriodChart()
}

function renderForecastChart() {
  if (!forecastChartRef.value || !result.value?.forecast) return

  if (forecastChart) forecastChart.dispose()
  forecastChart = echarts.init(forecastChartRef.value)

  const forecast = result.value.forecast
  const times = forecast.forecasts.map(f => f.time)
  const powers = forecast.forecasts.map(f => f.predicted_power)
  const lowerBounds = forecast.forecasts.map(f => f.lower_bound)
  const upperBounds = forecast.forecasts.map(f => f.upper_bound)

  const demandTarget = result.value.optimization?.demand_target || 800

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const p = params[0]
        const idx = p.dataIndex
        const point = forecast.forecasts[idx]
        return `${point.time}<br/>
                预测功率: ${point.predicted_power.toFixed(1)} kW<br/>
                时段: ${getPeriodName(point.period)}<br/>
                区间: [${point.lower_bound.toFixed(1)}, ${point.upper_bound.toFixed(1)}]`
      }
    },
    grid: { top: 40, right: 30, bottom: 50, left: 60 },
    xAxis: {
      type: 'category',
      data: times,
      axisLabel: {
        color: 'rgba(255,255,255,0.65)',
        interval: 7,
        rotate: 45
      }
    },
    yAxis: {
      type: 'value',
      name: 'kW',
      nameTextStyle: { color: 'rgba(255,255,255,0.65)' },
      axisLabel: { color: 'rgba(255,255,255,0.65)' },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }
    },
    series: [
      {
        name: '置信区间',
        type: 'line',
        data: upperBounds,
        lineStyle: { opacity: 0 },
        areaStyle: { color: 'rgba(24,144,255,0.15)' },
        symbol: 'none',
        stack: 'confidence'
      },
      {
        name: '下界',
        type: 'line',
        data: lowerBounds,
        lineStyle: { opacity: 0 },
        areaStyle: { color: '#1a2a4a' },
        symbol: 'none',
        stack: 'confidence'
      },
      {
        name: '预测功率',
        type: 'line',
        data: powers,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2, color: '#1890ff' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(24,144,255,0.4)' },
            { offset: 1, color: 'rgba(24,144,255,0.05)' }
          ])
        }
      },
      {
        name: '需量目标',
        type: 'line',
        data: times.map(() => demandTarget),
        lineStyle: { type: 'dashed', color: '#f5222d', width: 2 },
        symbol: 'none'
      }
    ]
  }

  forecastChart.setOption(option)
  new ResizeObserver(() => forecastChart?.resize()).observe(forecastChartRef.value)
}

function renderStorageChart() {
  if (!storageChartRef.value) return

  if (storageChart) storageChart.dispose()
  storageChart = echarts.init(storageChartRef.value)

  const storage = result.value?.optimization?.storage_schedule || []

  if (storage.length === 0) {
    // 无储能数据，显示空图表
    storageChart.setOption({
      title: {
        text: '暂无储能调度数据',
        left: 'center',
        top: 'middle',
        textStyle: { color: 'rgba(255,255,255,0.45)', fontSize: 14 }
      }
    })
    return
  }

  const times = storage.map(s => `${String(s.hour).padStart(2, '0')}:${String(s.minute).padStart(2, '0')}`)
  const charges = storage.map(s => s.charge_power)
  const discharges = storage.map(s => -s.discharge_power)
  const socs = storage.map(s => s.soc * 100)

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: {
      data: ['充电', '放电', 'SOC'],
      textStyle: { color: 'rgba(255,255,255,0.85)' }
    },
    grid: { top: 60, right: 60, bottom: 50, left: 60 },
    xAxis: {
      type: 'category',
      data: times,
      axisLabel: { color: 'rgba(255,255,255,0.65)', interval: 7, rotate: 45 }
    },
    yAxis: [
      {
        type: 'value',
        name: '功率 (kW)',
        nameTextStyle: { color: 'rgba(255,255,255,0.65)' },
        axisLabel: { color: 'rgba(255,255,255,0.65)' },
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }
      },
      {
        type: 'value',
        name: 'SOC (%)',
        min: 0,
        max: 100,
        nameTextStyle: { color: 'rgba(255,255,255,0.65)' },
        axisLabel: { color: 'rgba(255,255,255,0.65)' },
        splitLine: { show: false }
      }
    ],
    series: [
      {
        name: '充电',
        type: 'bar',
        data: charges,
        itemStyle: { color: '#52c41a' }
      },
      {
        name: '放电',
        type: 'bar',
        data: discharges,
        itemStyle: { color: '#f5222d' }
      },
      {
        name: 'SOC',
        type: 'line',
        yAxisIndex: 1,
        data: socs,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#faad14', width: 2 }
      }
    ]
  }

  storageChart.setOption(option)
  new ResizeObserver(() => storageChart?.resize()).observe(storageChartRef.value)
}

function renderGanttChart() {
  if (!ganttChartRef.value) return

  if (ganttChart) ganttChart.dispose()
  ganttChart = echarts.init(ganttChartRef.value)

  const schedules = result.value?.optimization?.schedule || []
  const storageSchedule = result.value?.optimization?.storage_schedule || []

  // 构建甘特图数据
  const categories: string[] = []
  const data: any[] = []

  // 添加储能行
  if (storageSchedule.length > 0) {
    categories.push('储能系统')

    storageSchedule.forEach((s, idx) => {
      if (s.charge_power > 0) {
        data.push({
          name: '充电',
          value: [0, idx, idx + 1, s.charge_power],
          itemStyle: { color: '#52c41a' }
        })
      }
      if (s.discharge_power > 0) {
        data.push({
          name: '放电',
          value: [0, idx, idx + 1, s.discharge_power],
          itemStyle: { color: '#f5222d' }
        })
      }
    })
  }

  // 添加设备行
  schedules.forEach((device, deviceIdx) => {
    categories.push(device.device_name)
    const catIdx = categories.length - 1

    device.actions.forEach(action => {
      const slot = action.time_slot
      let color = '#1890ff'
      if (action.action === 'on') color = '#1890ff'
      else if (action.action === 'curtail') color = '#faad14'

      data.push({
        name: action.action,
        value: [catIdx, slot, slot + 1, action.power || 0],
        itemStyle: { color }
      })
    })
  })

  // 如果没有数据
  if (categories.length === 0) {
    ganttChart.setOption({
      title: {
        text: '暂无设备调度计划',
        left: 'center',
        top: 'middle',
        textStyle: { color: 'rgba(255,255,255,0.45)', fontSize: 14 }
      }
    })
    return
  }

  // 生成24小时刻度
  const hours = Array.from({ length: 25 }, (_, i) => `${String(i).padStart(2, '0')}:00`)

  const option: echarts.EChartsOption = {
    tooltip: {
      formatter: (params: any) => {
        const d = params.data
        return `${categories[d.value[0]]}<br/>
                时段: ${Math.floor(d.value[1] / 4)}:${(d.value[1] % 4) * 15}0 - ${Math.floor(d.value[2] / 4)}:${(d.value[2] % 4) * 15}0<br/>
                动作: ${d.name}<br/>
                功率: ${d.value[3]} kW`
      }
    },
    grid: { top: 20, right: 30, bottom: 40, left: 120 },
    xAxis: {
      type: 'value',
      min: 0,
      max: 96,
      splitNumber: 24,
      axisLabel: {
        formatter: (val: number) => {
          const hour = Math.floor(val / 4)
          return hour % 4 === 0 ? `${String(hour).padStart(2, '0')}:00` : ''
        },
        color: 'rgba(255,255,255,0.65)'
      },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }
    },
    yAxis: {
      type: 'category',
      data: categories,
      axisLabel: { color: 'rgba(255,255,255,0.85)' }
    },
    series: [
      {
        type: 'custom',
        renderItem: (params: any, api: any) => {
          const catIdx = api.value(0)
          const start = api.coord([api.value(1), catIdx])
          const end = api.coord([api.value(2), catIdx])
          const height = api.size([0, 1])[1] * 0.6

          return {
            type: 'rect',
            shape: {
              x: start[0],
              y: start[1] - height / 2,
              width: end[0] - start[0],
              height: height
            },
            style: api.style()
          }
        },
        encode: {
          x: [1, 2],
          y: 0
        },
        data: data
      }
    ]
  }

  ganttChart.setOption(option)
  new ResizeObserver(() => ganttChart?.resize()).observe(ganttChartRef.value)
}

function renderCostChart() {
  if (!costChartRef.value || !result.value?.optimization) return

  if (costChart) costChart.dispose()
  costChart = echarts.init(costChartRef.value)

  const opt = result.value.optimization

  const option: echarts.EChartsOption = {
    tooltip: { trigger: 'axis' },
    legend: {
      data: ['基线成本', '优化成本'],
      textStyle: { color: 'rgba(255,255,255,0.85)' }
    },
    grid: { top: 60, right: 30, bottom: 30, left: 60 },
    xAxis: {
      type: 'category',
      data: ['总成本'],
      axisLabel: { color: 'rgba(255,255,255,0.65)' }
    },
    yAxis: {
      type: 'value',
      name: '元',
      nameTextStyle: { color: 'rgba(255,255,255,0.65)' },
      axisLabel: { color: 'rgba(255,255,255,0.65)' },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }
    },
    series: [
      {
        name: '基线成本',
        type: 'bar',
        data: [opt.baseline_cost],
        itemStyle: { color: '#f5222d' },
        barWidth: 40
      },
      {
        name: '优化成本',
        type: 'bar',
        data: [opt.cost_breakdown.total_cost],
        itemStyle: { color: '#52c41a' },
        barWidth: 40
      }
    ]
  }

  costChart.setOption(option)
}

function renderPeriodChart() {
  if (!periodChartRef.value || !result.value?.forecast) return

  if (periodChart) periodChart.dispose()
  periodChart = echarts.init(periodChartRef.value)

  const summary = result.value.forecast.period_summary

  const data = Object.entries(summary).map(([period, info]) => ({
    name: getPeriodName(period),
    value: info.energy,
    itemStyle: { color: getPeriodColor(period) }
  }))

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} kWh ({d}%)'
    },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 'center',
      textStyle: { color: 'rgba(255,255,255,0.85)' }
    },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['35%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 4,
          borderColor: '#1a2a4a',
          borderWidth: 2
        },
        label: { show: false },
        emphasis: {
          label: {
            show: true,
            fontSize: 14,
            fontWeight: 'bold',
            color: '#fff'
          }
        },
        data: data
      }
    ]
  }

  periodChart.setOption(option)
}
</script>

<style scoped lang="scss">
.schedule-dashboard {
  padding: 20px;

  .header-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 20px;
  }

  .summary-row {
    margin-bottom: 20px;
  }

  .summary-card {
    :deep(.el-card__body) {
      padding: 16px;
    }

    .stat-item {
      text-align: center;

      .label {
        font-size: 13px;
        color: var(--text-secondary);
        margin-bottom: 8px;
      }

      .value {
        font-size: 24px;
        font-weight: 600;
        color: var(--text-primary);

        &.highlight {
          color: #1890ff;
        }

        &.success-text {
          color: #52c41a;
        }
      }

      .sub-text {
        font-size: 12px;
        color: var(--text-secondary);
        margin-top: 4px;
      }
    }

    &.success {
      border-color: rgba(82, 196, 26, 0.3);
    }
  }

  .chart-row {
    margin-bottom: 20px;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .chart-container {
    height: 280px;
  }

  .chart-container-small {
    height: 200px;
  }

  .gantt-card {
    margin-bottom: 20px;

    .legend {
      display: flex;
      gap: 16px;
      font-size: 12px;
      color: var(--text-secondary);

      .legend-item {
        display: flex;
        align-items: center;
        gap: 4px;

        .dot {
          width: 12px;
          height: 12px;
          border-radius: 2px;

          &.on { background: #1890ff; }
          &.charge { background: #52c41a; }
          &.discharge { background: #f5222d; }
          &.curtail { background: #faad14; }
        }
      }
    }
  }

  .gantt-container {
    height: 200px;
  }

  .cost-row {
    margin-bottom: 20px;
  }
}
</style>
