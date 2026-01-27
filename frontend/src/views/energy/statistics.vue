<template>
  <div class="energy-statistics">
    <!-- 筛选条件 -->
    <el-card shadow="hover" class="filter-card">
      <el-form :inline="true" :model="filters">
        <el-form-item label="统计周期">
          <el-radio-group v-model="filters.period" @change="handlePeriodChange">
            <el-radio-button value="daily">日统计</el-radio-button>
            <el-radio-button value="monthly">月统计</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="filters.period === 'daily'" label="日期范围">
          <el-date-picker
            v-model="filters.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            :shortcuts="dateShortcuts"
          />
        </el-form-item>
        <el-form-item v-else label="年份">
          <el-date-picker
            v-model="filters.year"
            type="year"
            placeholder="选择年份"
            value-format="YYYY"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
          <el-button type="success" @click="handleExport">导出</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 统计汇总 -->
    <el-row :gutter="20" class="summary-cards">
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <el-statistic title="总用电量" :value="energyStat.total_energy || 0" suffix="kWh">
            <template #prefix>
              <el-icon><Lightning /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <el-statistic title="总电费" :value="energyStat.total_cost || 0" suffix="元" :precision="2">
            <template #prefix>
              <el-icon><Money /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <el-statistic title="平均功率" :value="energyStat.avg_power || 0" suffix="kW" :precision="1">
            <template #prefix>
              <el-icon><Odometer /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <el-statistic title="平均PUE" :value="energyStat.avg_pue || 0" :precision="2">
            <template #prefix>
              <el-icon><TrendCharts /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <!-- 能耗趋势图 -->
      <el-col :span="16">
        <el-card shadow="hover">
          <template #header>能耗趋势</template>
          <div ref="trendChartRef" class="chart"></div>
        </el-card>
      </el-col>

      <!-- 峰谷平分布 -->
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>峰谷平分布</template>
          <div ref="pieChartRef" class="chart"></div>
          <div class="pie-legend">
            <div class="legend-item">
              <span class="dot peak"></span>
              <span>峰时: {{ energyStat.peak_energy?.toFixed(0) || 0 }} kWh</span>
            </div>
            <div class="legend-item">
              <span class="dot normal"></span>
              <span>平时: {{ energyStat.normal_energy?.toFixed(0) || 0 }} kWh</span>
            </div>
            <div class="legend-item">
              <span class="dot valley"></span>
              <span>谷时: {{ energyStat.valley_energy?.toFixed(0) || 0 }} kWh</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px;">
      <!-- 电费分析 -->
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>电费分析</template>
          <div ref="costChartRef" class="chart"></div>
        </el-card>
      </el-col>

      <!-- 同环比对比 -->
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>同环比分析</template>
          <div class="comparison-content" v-if="comparison.current_period">
            <el-row :gutter="20">
              <el-col :span="12">
                <div class="comparison-item">
                  <div class="label">本期用电量</div>
                  <div class="value">{{ comparison.current_period.total_energy?.toFixed(0) }} kWh</div>
                  <div class="change" :class="comparison.energy_change_rate >= 0 ? 'up' : 'down'">
                    <el-icon v-if="comparison.energy_change_rate >= 0"><Top /></el-icon>
                    <el-icon v-else><Bottom /></el-icon>
                    {{ Math.abs(comparison.energy_change_rate * 100).toFixed(1) }}%
                  </div>
                </div>
              </el-col>
              <el-col :span="12">
                <div class="comparison-item">
                  <div class="label">本期电费</div>
                  <div class="value">{{ comparison.current_period.total_cost?.toFixed(0) }} 元</div>
                  <div class="change" :class="comparison.cost_change_rate >= 0 ? 'up' : 'down'">
                    <el-icon v-if="comparison.cost_change_rate >= 0"><Top /></el-icon>
                    <el-icon v-else><Bottom /></el-icon>
                    {{ Math.abs(comparison.cost_change_rate * 100).toFixed(1) }}%
                  </div>
                </div>
              </el-col>
            </el-row>
            <el-divider />
            <el-row :gutter="20">
              <el-col :span="12">
                <div class="comparison-item prev">
                  <div class="label">上期用电量</div>
                  <div class="value">{{ comparison.previous_period.total_energy?.toFixed(0) }} kWh</div>
                </div>
              </el-col>
              <el-col :span="12">
                <div class="comparison-item prev">
                  <div class="label">上期电费</div>
                  <div class="value">{{ comparison.previous_period.total_cost?.toFixed(0) }} 元</div>
                </div>
              </el-col>
            </el-row>
          </div>
          <el-empty v-else description="暂无对比数据" :image-size="80" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 明细数据 -->
    <el-card shadow="hover" style="margin-top: 20px;">
      <template #header>
        <div class="card-header">
          <span>{{ filters.period === 'daily' ? '日' : '月' }}能耗明细</span>
        </div>
      </template>

      <el-table :data="detailData" stripe border v-loading="loading">
        <el-table-column
          :prop="filters.period === 'daily' ? 'stat_date' : 'stat_month'"
          :label="filters.period === 'daily' ? '日期' : '月份'"
          width="120"
        >
          <template #default="{ row }">
            {{ filters.period === 'daily' ? row.stat_date : `${row.stat_year}-${String(row.stat_month).padStart(2, '0')}` }}
          </template>
        </el-table-column>
        <el-table-column prop="total_energy" label="总电量 (kWh)" width="120">
          <template #default="{ row }">{{ row.total_energy?.toFixed(1) }}</template>
        </el-table-column>
        <el-table-column prop="peak_energy" label="峰时电量" width="100">
          <template #default="{ row }">{{ row.peak_energy?.toFixed(1) }}</template>
        </el-table-column>
        <el-table-column prop="normal_energy" label="平时电量" width="100">
          <template #default="{ row }">{{ row.normal_energy?.toFixed(1) }}</template>
        </el-table-column>
        <el-table-column prop="valley_energy" label="谷时电量" width="100">
          <template #default="{ row }">{{ row.valley_energy?.toFixed(1) }}</template>
        </el-table-column>
        <el-table-column prop="max_power" label="最大功率 (kW)" width="120">
          <template #default="{ row }">{{ row.max_power?.toFixed(1) }}</template>
        </el-table-column>
        <el-table-column prop="avg_power" label="平均功率 (kW)" width="120">
          <template #default="{ row }">{{ row.avg_power?.toFixed(1) }}</template>
        </el-table-column>
        <el-table-column prop="energy_cost" label="电费 (元)" width="100">
          <template #default="{ row }">{{ row.energy_cost?.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="pue" label="PUE" width="80">
          <template #default="{ row }">
            {{ (row.pue || row.avg_pue)?.toFixed(2) || '-' }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Lightning, Money, Odometer, TrendCharts, Top, Bottom } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import {
  getDailyStatistics, getMonthlyStatistics, getEnergySummary,
  getEnergyTrend, getEnergyComparison, exportDailyData, exportMonthlyData,
  type EnergyDailyData, type EnergyMonthlyData, type EnergyStat, type EnergyComparison
} from '@/api/modules/energy'

const trendChartRef = ref<HTMLElement>()
const pieChartRef = ref<HTMLElement>()
const costChartRef = ref<HTMLElement>()
let trendChart: echarts.ECharts | null = null
let pieChart: echarts.ECharts | null = null
let costChart: echarts.ECharts | null = null

const loading = ref(false)
const detailData = ref<(EnergyDailyData | EnergyMonthlyData)[]>([])
const energyStat = ref<Partial<EnergyStat>>({})
const comparison = ref<Partial<EnergyComparison>>({})

const filters = reactive({
  period: 'daily' as 'daily' | 'monthly',
  dateRange: [] as string[],
  year: new Date().getFullYear().toString()
})

const dateShortcuts = [
  {
    text: '最近7天',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setTime(start.getTime() - 3600 * 1000 * 24 * 7)
      return [start, end]
    }
  },
  {
    text: '最近30天',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setTime(start.getTime() - 3600 * 1000 * 24 * 30)
      return [start, end]
    }
  },
  {
    text: '本月',
    value: () => {
      const now = new Date()
      const start = new Date(now.getFullYear(), now.getMonth(), 1)
      return [start, now]
    }
  }
]

onMounted(() => {
  initCharts()
  // 设置默认日期范围
  const end = new Date()
  const start = new Date()
  start.setTime(start.getTime() - 3600 * 1000 * 24 * 30)
  filters.dateRange = [
    start.toISOString().split('T')[0],
    end.toISOString().split('T')[0]
  ]
  loadData()
})

onUnmounted(() => {
  trendChart?.dispose()
  pieChart?.dispose()
  costChart?.dispose()
})

function initCharts() {
  if (trendChartRef.value) trendChart = echarts.init(trendChartRef.value)
  if (pieChartRef.value) pieChart = echarts.init(pieChartRef.value)
  if (costChartRef.value) costChart = echarts.init(costChartRef.value)

  window.addEventListener('resize', () => {
    trendChart?.resize()
    pieChart?.resize()
    costChart?.resize()
  })
}

function handlePeriodChange() {
  loadData()
}

async function loadData() {
  loading.value = true
  try {
    if (filters.period === 'daily') {
      if (!filters.dateRange || filters.dateRange.length !== 2) {
        ElMessage.warning('请选择日期范围')
        return
      }
      await Promise.all([
        loadDailyData(),
        loadDailySummary(),
        loadDailyTrend(),
        loadComparison()
      ])
    } else {
      await Promise.all([
        loadMonthlyData(),
        loadMonthlySummary(),
        loadMonthlyTrend(),
        loadComparison()
      ])
    }
  } finally {
    loading.value = false
  }
}

async function loadDailyData() {
  try {
    const res = await getDailyStatistics({
      start_date: filters.dateRange[0],
      end_date: filters.dateRange[1]
    })
    detailData.value = res.data || []
  } catch (e) {
    console.error('加载日统计失败', e)
  }
}

async function loadMonthlyData() {
  try {
    const res = await getMonthlyStatistics({
      year: parseInt(filters.year)
    })
    detailData.value = res.data || []
  } catch (e) {
    console.error('加载月统计失败', e)
  }
}

async function loadDailySummary() {
  try {
    const res = await getEnergySummary({
      start_date: filters.dateRange[0],
      end_date: filters.dateRange[1]
    })
    energyStat.value = res.data || {}
    updatePieChart()
  } catch (e) {
    console.error('加载汇总失败', e)
  }
}

async function loadMonthlySummary() {
  try {
    const startDate = `${filters.year}-01-01`
    const endDate = `${filters.year}-12-31`
    const res = await getEnergySummary({
      start_date: startDate,
      end_date: endDate
    })
    energyStat.value = res.data || {}
    updatePieChart()
  } catch (e) {
    console.error('加载汇总失败', e)
  }
}

async function loadDailyTrend() {
  try {
    const res = await getEnergyTrend({
      start_date: filters.dateRange[0],
      end_date: filters.dateRange[1],
      granularity: 'daily'
    })
    updateTrendChart(res.data?.data || [])
    updateCostChart(res.data?.data || [])
  } catch (e) {
    console.error('加载趋势失败', e)
  }
}

async function loadMonthlyTrend() {
  try {
    const res = await getEnergyTrend({
      start_date: `${filters.year}-01-01`,
      end_date: `${filters.year}-12-31`,
      granularity: 'monthly'
    })
    updateTrendChart(res.data?.data || [])
    updateCostChart(res.data?.data || [])
  } catch (e) {
    console.error('加载趋势失败', e)
  }
}

async function loadComparison() {
  try {
    const res = await getEnergyComparison({
      comparison_type: 'mom',
      period: filters.period === 'daily' ? 'day' : 'month'
    })
    comparison.value = res.data || {}
  } catch (e) {
    console.error('加载对比数据失败', e)
  }
}

// Theme colors for ECharts (matching CSS variables)
const themeColors = {
  primary: '#1890ff',
  success: '#52c41a',
  warning: '#faad14',
  error: '#f5222d',
  textPrimary: 'rgba(255, 255, 255, 0.95)',
  textSecondary: 'rgba(255, 255, 255, 0.65)',
  borderColor: 'rgba(255, 255, 255, 0.1)'
}

function updateTrendChart(data: any[]) {
  if (!trendChart) return

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: '#1a2a4a',
      borderColor: themeColors.borderColor,
      textStyle: { color: themeColors.textPrimary }
    },
    legend: {
      data: ['用电量', '电费'],
      textStyle: { color: themeColors.textSecondary }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: data.map(d => d.time_label),
      axisLabel: { rotate: 30, color: themeColors.textSecondary },
      axisLine: { lineStyle: { color: themeColors.borderColor } }
    },
    yAxis: [
      {
        type: 'value',
        name: 'kWh',
        position: 'left',
        nameTextStyle: { color: themeColors.textSecondary },
        axisLabel: { color: themeColors.textSecondary },
        axisLine: { lineStyle: { color: themeColors.borderColor } },
        splitLine: { lineStyle: { color: themeColors.borderColor } }
      },
      {
        type: 'value',
        name: '元',
        position: 'right',
        nameTextStyle: { color: themeColors.textSecondary },
        axisLabel: { color: themeColors.textSecondary },
        axisLine: { lineStyle: { color: themeColors.borderColor } },
        splitLine: { show: false }
      }
    ],
    series: [
      {
        name: '用电量',
        type: 'bar',
        data: data.map(d => d.energy),
        itemStyle: { color: themeColors.primary }
      },
      {
        name: '电费',
        type: 'line',
        yAxisIndex: 1,
        data: data.map(d => d.cost),
        itemStyle: { color: themeColors.success }
      }
    ]
  }
  trendChart.setOption(option)
}

function updatePieChart() {
  if (!pieChart) return

  const data = [
    { value: energyStat.value.peak_energy || 0, name: '峰时', itemStyle: { color: themeColors.error } },
    { value: energyStat.value.normal_energy || 0, name: '平时', itemStyle: { color: themeColors.primary } },
    { value: energyStat.value.valley_energy || 0, name: '谷时', itemStyle: { color: themeColors.success } }
  ]

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} kWh ({d}%)',
      backgroundColor: '#1a2a4a',
      borderColor: themeColors.borderColor,
      textStyle: { color: themeColors.textPrimary }
    },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      avoidLabelOverlap: false,
      label: {
        show: true,
        formatter: '{d}%',
        color: themeColors.textSecondary
      },
      data
    }]
  }
  pieChart.setOption(option)
}

function updateCostChart(data: any[]) {
  if (!costChart) return

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1a2a4a',
      borderColor: themeColors.borderColor,
      textStyle: { color: themeColors.textPrimary }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: data.map(d => d.time_label),
      axisLabel: { rotate: 30, color: themeColors.textSecondary },
      axisLine: { lineStyle: { color: themeColors.borderColor } }
    },
    yAxis: {
      type: 'value',
      name: '元',
      nameTextStyle: { color: themeColors.textSecondary },
      axisLabel: { color: themeColors.textSecondary },
      axisLine: { lineStyle: { color: themeColors.borderColor } },
      splitLine: { lineStyle: { color: themeColors.borderColor } }
    },
    series: [{
      type: 'line',
      data: data.map(d => d.cost),
      smooth: true,
      areaStyle: { opacity: 0.3 },
      itemStyle: { color: themeColors.error }
    }]
  }
  costChart.setOption(option)
}

async function handleExport() {
  try {
    let blob: Blob
    if (filters.period === 'daily') {
      blob = await exportDailyData({
        start_date: filters.dateRange[0],
        end_date: filters.dateRange[1],
        format: 'excel'
      })
    } else {
      blob = await exportMonthlyData({
        year: parseInt(filters.year),
        format: 'excel'
      })
    }

    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `能耗统计_${filters.period}_${Date.now()}.xlsx`
    a.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (e) {
    console.error('导出失败', e)
    ElMessage.error('导出失败')
  }
}
</script>

<style scoped lang="scss">
.energy-statistics {
  .filter-card {
    margin-bottom: 20px;
  }

  .summary-cards {
    margin-bottom: 20px;
  }

  .summary-card {
    :deep(.el-statistic__head) {
      font-size: 14px;
      color: var(--text-secondary);
    }

    :deep(.el-statistic__content) {
      font-size: 24px;
      color: var(--text-primary);
    }
  }

  // Dark theme styles for el-card
  :deep(.el-card) {
    background-color: var(--bg-card-solid);
    border-color: var(--border-color);

    .el-card__header {
      color: var(--text-primary);
      border-bottom-color: var(--border-color);
    }

    .el-card__body {
      color: var(--text-regular);
    }
  }

  // Dark theme styles for el-table
  :deep(.el-table) {
    background-color: var(--bg-card-solid);
    color: var(--text-regular);

    tr {
      background-color: var(--bg-card-solid);
    }

    th.el-table__cell {
      background-color: var(--bg-tertiary);
      color: var(--text-primary);
      border-bottom-color: var(--border-color);
    }

    td.el-table__cell {
      border-bottom-color: var(--border-color);
    }

    .el-table__row--striped td.el-table__cell {
      background-color: var(--bg-tertiary);
    }

    .el-table__border-left-patch,
    .el-table__border-bottom-patch {
      background-color: var(--border-color);
    }
  }

  :deep(.el-table--enable-row-hover) .el-table__body tr:hover > td.el-table__cell {
    background-color: rgba(255, 255, 255, 0.05);
  }

  :deep(.el-table::before) {
    background-color: var(--border-color);
  }

  // Dark theme styles for el-form
  :deep(.el-form) {
    .el-form-item__label {
      color: var(--text-secondary);
    }
  }

  // Dark theme for el-divider
  :deep(.el-divider) {
    border-color: var(--border-color);
  }

  // Dark theme for el-empty
  :deep(.el-empty__description p) {
    color: var(--text-secondary);
  }

  .chart {
    height: 300px;
  }

  .pie-legend {
    margin-top: 20px;
    display: flex;
    justify-content: center;
    gap: 20px;
    color: var(--text-regular);

    .legend-item {
      display: flex;
      align-items: center;
      gap: 8px;

      .dot {
        width: 12px;
        height: 12px;
        border-radius: 50%;

        &.peak { background: var(--error-color); }
        &.normal { background: var(--primary-color); }
        &.valley { background: var(--success-color); }
      }
    }
  }

  .comparison-content {
    .comparison-item {
      text-align: center;
      padding: 16px;

      .label {
        color: var(--text-secondary);
        margin-bottom: 8px;
      }

      .value {
        font-size: 24px;
        font-weight: bold;
        color: var(--text-primary);
      }

      .change {
        margin-top: 8px;
        font-size: 14px;

        &.up { color: var(--error-color); }
        &.down { color: var(--success-color); }
      }

      &.prev {
        .value {
          font-size: 18px;
          color: var(--text-secondary);
        }
      }
    }
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    color: var(--text-primary);
  }
}
</style>
