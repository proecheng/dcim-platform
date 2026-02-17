<template>
  <div class="energy-report">
    <!-- 筛选条件 -->
    <el-card shadow="hover" class="filter-card">
      <el-form :inline="true">
        <el-form-item label="选择月份">
          <el-date-picker
            v-model="selectedMonth"
            type="month"
            placeholder="选择月份"
            format="YYYY年MM月"
            value-format="YYYY-MM"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="generateReport" :loading="loading">
            <el-icon><DataAnalysis /></el-icon>生成报告
          </el-button>
        </el-form-item>
        <el-form-item v-if="reportData">
          <el-button type="success" @click="handleExport('excel')" :loading="exporting">
            <el-icon><Download /></el-icon>导出 Excel
          </el-button>
          <el-button type="warning" @click="handleExport('pdf')" :loading="exporting">
            <el-icon><Document /></el-icon>导出 PDF
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 关键指标卡片 -->
    <el-row v-if="reportData" :gutter="20" class="metrics-row">
      <el-col :span="6">
        <el-card shadow="hover" class="metric-card">
          <div class="metric-title">PUE 均值</div>
          <div class="metric-value">{{ reportData.pue_trend.month_avg_pue?.toFixed(2) || '--' }}</div>
          <div class="metric-change" :class="changeClass(reportData.pue_trend.mom_change)">
            环比 {{ formatChange(reportData.pue_trend.mom_change) }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="metric-card">
          <div class="metric-title">总能耗(kWh)</div>
          <div class="metric-value">{{ formatNumber(reportData.cost_comparison.current_month.total_energy) }}</div>
          <div class="metric-change" :class="changeClass(reportData.cost_comparison.mom_change_rate)">
            环比 {{ formatChange(reportData.cost_comparison.mom_change_rate) }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="metric-card">
          <div class="metric-title">总电费(元)</div>
          <div class="metric-value">{{ formatNumber(reportData.cost_comparison.current_month.total_cost) }}</div>
          <div class="metric-change" :class="changeClass(reportData.cost_comparison.yoy_change_rate)">
            同比 {{ formatChange(reportData.cost_comparison.yoy_change_rate) }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="metric-card">
          <div class="metric-title">节能金额(元)</div>
          <div class="metric-value saving">{{ formatNumber(reportData.energy_saving.total_saving_cost) }}</div>
          <div class="metric-sub">
            共 {{ reportData.energy_saving.executed_count }}/{{ reportData.energy_saving.opportunities_count }} 个方案
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- PUE 趋势图 -->
    <el-card v-if="reportData" shadow="hover" class="chart-card">
      <template #header>PUE 趋势</template>
      <div ref="pueChartRef" style="height: 350px"></div>
    </el-card>

    <!-- 电费对比表 -->
    <el-card v-if="reportData" shadow="hover" class="table-card">
      <template #header>电费对比</template>
      <el-table :data="costTableData" border stripe>
        <el-table-column prop="item" label="项目" width="120" />
        <el-table-column prop="current" label="本月" align="right" />
        <el-table-column prop="lastMonth" label="上月" align="right" />
        <el-table-column prop="lastYear" label="去年同月" align="right" />
        <el-table-column prop="mom" label="环比%" align="right" />
        <el-table-column prop="yoy" label="同比%" align="right" />
      </el-table>
    </el-card>

    <!-- 节能成果表 -->
    <el-card v-if="reportData" shadow="hover" class="table-card">
      <template #header>节能成果</template>
      <el-table :data="reportData.energy_saving.details" border stripe>
        <el-table-column prop="title" label="方案名称" />
        <el-table-column prop="category" label="类别" width="120">
          <template #default="{ row }">{{ categoryMap[row.category] || '未知' }}</template>
        </el-table-column>
        <el-table-column prop="saving_kwh" label="节能(kWh)" align="right" width="120">
          <template #default="{ row }">{{ row.saving_kwh?.toFixed(1) }}</template>
        </el-table-column>
        <el-table-column prop="saving_cost" label="节省费用(元)" align="right" width="130">
          <template #default="{ row }">{{ row.saving_cost?.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="achievement_rate" label="达成率" width="180">
          <template #default="{ row }">
            <el-progress
              :percentage="Math.min(row.achievement_rate || 0, 100)"
              :color="row.achievement_rate >= 80 ? '#67C23A' : row.achievement_rate >= 50 ? '#E6A23C' : '#F56C6C'"
            />
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { DataAnalysis, Download, Document } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { getEnergyReportPreview, exportEnergyReport } from '@/api/modules/energy'

const selectedMonth = ref('')
const loading = ref(false)
const exporting = ref(false)
const reportData = ref<any>(null)
const pueChartRef = ref<HTMLElement>()
let pueChart: echarts.ECharts | null = null

const categoryMap: Record<number, string> = {
  1: '电费结构优化',
  2: '设备运行优化',
  3: '设备改造升级',
  4: '综合能效提升'
}

// Theme colors matching existing energy pages
const themeColors = {
  primary: '#1890ff',
  success: '#52c41a',
  warning: '#faad14',
  error: '#f5222d',
  textPrimary: 'rgba(255, 255, 255, 0.95)',
  textSecondary: 'rgba(255, 255, 255, 0.65)',
  borderColor: 'rgba(255, 255, 255, 0.1)'
}

onMounted(() => {
  const now = new Date()
  selectedMonth.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
})

onUnmounted(() => {
  pueChart?.dispose()
})

async function generateReport() {
  if (!selectedMonth.value) {
    ElMessage.warning('请选择月份')
    return
  }
  loading.value = true
  try {
    const [yearStr, monthStr] = selectedMonth.value.split('-')
    const res = await getEnergyReportPreview({ year: parseInt(yearStr), month: parseInt(monthStr) })
    reportData.value = res.data || res
    await nextTick()
    renderPueChart()
    ElMessage.success('报告生成成功')
  } catch (e) {
    console.error('生成报告失败', e)
    ElMessage.error('生成报告失败')
  } finally {
    loading.value = false
  }
}

const costTableData = computed(() => {
  if (!reportData.value) return []
  const cc = reportData.value.cost_comparison
  const cur = cc.current_month
  const lm = cc.last_month
  const ly = cc.last_year_month

  function safeVal(obj: Record<string, number> | null, key: string): string {
    if (!obj || obj[key] == null) return '--'
    return obj[key].toFixed(1)
  }

  function calcChange(curVal: number, prevVal: number | null | undefined): string {
    if (prevVal == null || prevVal === 0) return '--'
    return ((curVal - prevVal) / prevVal * 100).toFixed(1)
  }

  const rows = [
    { key: 'total_energy', label: '总能耗(kWh)' },
    { key: 'total_cost', label: '总电费(元)' },
    { key: 'peak_energy', label: '峰时电量(kWh)' },
    { key: 'peak_cost', label: '峰时电费(元)' },
    { key: 'normal_energy', label: '平时电量(kWh)' },
    { key: 'normal_cost', label: '平时电费(元)' },
    { key: 'valley_energy', label: '谷时电量(kWh)' },
    { key: 'valley_cost', label: '谷时电费(元)' }
  ]

  return rows.map(r => ({
    item: r.label,
    current: cur[r.key]?.toFixed(1) ?? '--',
    lastMonth: safeVal(lm, r.key),
    lastYear: safeVal(ly, r.key),
    mom: calcChange(cur[r.key], lm?.[r.key]),
    yoy: calcChange(cur[r.key], ly?.[r.key])
  }))
})

function renderPueChart() {
  if (!pueChartRef.value || !reportData.value) return

  if (!pueChart) {
    pueChart = echarts.init(pueChartRef.value)
    window.addEventListener('resize', () => pueChart?.resize())
  }

  const dailyValues = reportData.value.pue_trend.daily_values || []

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1a2a4a',
      borderColor: themeColors.borderColor,
      textStyle: { color: themeColors.textPrimary }
    },
    legend: {
      data: ['平均PUE', '最小PUE', '最大PUE'],
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
      data: dailyValues.map((d: any) => d.date),
      axisLabel: { rotate: 30, color: themeColors.textSecondary },
      axisLine: { lineStyle: { color: themeColors.borderColor } }
    },
    yAxis: {
      type: 'value',
      name: 'PUE',
      min: (value: any) => (value.min - 0.05).toFixed(2),
      nameTextStyle: { color: themeColors.textSecondary },
      axisLabel: { color: themeColors.textSecondary },
      axisLine: { lineStyle: { color: themeColors.borderColor } },
      splitLine: { lineStyle: { color: themeColors.borderColor } }
    },
    series: [
      {
        name: '平均PUE',
        type: 'line',
        data: dailyValues.map((d: any) => d.avg_pue),
        smooth: true,
        itemStyle: { color: themeColors.primary },
        areaStyle: { opacity: 0.15 }
      },
      {
        name: '最小PUE',
        type: 'line',
        data: dailyValues.map((d: any) => d.min_pue),
        lineStyle: { type: 'dashed', width: 1 },
        itemStyle: { color: themeColors.success },
        symbol: 'none'
      },
      {
        name: '最大PUE',
        type: 'line',
        data: dailyValues.map((d: any) => d.max_pue),
        lineStyle: { type: 'dashed', width: 1 },
        itemStyle: { color: themeColors.error },
        symbol: 'none'
      }
    ]
  }
  pueChart.setOption(option, true)
}

async function handleExport(format: 'excel' | 'pdf') {
  exporting.value = true
  try {
    const [yearStr, monthStr] = selectedMonth.value.split('-')
    const blob = await exportEnergyReport({
      year: parseInt(yearStr),
      month: parseInt(monthStr),
      format
    })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `能效报告_${selectedMonth.value}.${format === 'excel' ? 'xlsx' : 'pdf'}`
    a.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (e) {
    console.error('导出失败', e)
    ElMessage.error('导出失败')
  } finally {
    exporting.value = false
  }
}

function formatNumber(val: number | null | undefined): string {
  if (val == null) return '--'
  if (val >= 10000) return (val / 10000).toFixed(2) + '万'
  return val.toFixed(1)
}

function formatChange(val: number | null | undefined): string {
  if (val == null) return '--'
  const pct = val.toFixed(1)
  return val >= 0 ? `+${pct}%` : `${pct}%`
}

function changeClass(val: number | null | undefined): string {
  if (val == null) return ''
  return val >= 0 ? 'up' : 'down'
}
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.energy-report {
  @include page-form;

  .filter-card {
    margin-bottom: 20px;
  }

  .metrics-row {
    margin-bottom: 20px;
  }

  .metric-card {
    text-align: center;

    .metric-title {
      font-size: 14px;
      color: var(--text-secondary, rgba(255, 255, 255, 0.65));
      margin-bottom: 8px;
    }

    .metric-value {
      font-size: 28px;
      font-weight: bold;
      color: var(--text-primary, rgba(255, 255, 255, 0.95));

      &.saving {
        color: var(--success-color, #52c41a);
      }
    }

    .metric-change {
      font-size: 12px;
      margin-top: 4px;

      &.up { color: var(--error-color, #F56C6C); }
      &.down { color: var(--success-color, #67C23A); }
    }

    .metric-sub {
      font-size: 12px;
      margin-top: 4px;
      color: var(--text-tertiary, rgba(255, 255, 255, 0.45));
    }
  }

  .chart-card, .table-card {
    margin-bottom: 20px;
  }

  // Dark theme styles for el-card (matching statistics.vue)
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
}
</style>
