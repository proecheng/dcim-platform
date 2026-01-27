<template>
  <div class="report-page">
    <!-- 报表类型切换 -->
    <el-card shadow="hover" class="type-card">
      <el-radio-group v-model="reportType" @change="handleTypeChange">
        <el-radio-button label="daily">日报</el-radio-button>
        <el-radio-button label="weekly">周报</el-radio-button>
        <el-radio-button label="monthly">月报</el-radio-button>
        <el-radio-button label="custom">自定义报表</el-radio-button>
      </el-radio-group>
    </el-card>

    <!-- 日报 -->
    <template v-if="reportType === 'daily'">
      <el-card shadow="hover">
        <template #header>
          <div class="card-header">
            <span>日报 - {{ dailyDate }}</span>
            <div class="header-actions">
              <el-date-picker
                v-model="dailyDatePicker"
                type="date"
                placeholder="选择日期"
                :disabled-date="disabledFutureDate"
                @change="loadDailyReport"
              />
              <el-button type="primary" :icon="Download" @click="exportReport('daily')">导出</el-button>
            </div>
          </div>
        </template>

        <el-row :gutter="20" class="stats-row">
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-value">{{ dailyReport.points?.length || 0 }}</div>
              <div class="stat-label">监控点位</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card alarm">
              <div class="stat-value">{{ dailyReport.alarm_total || 0 }}</div>
              <div class="stat-label">告警次数</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-value">{{ getAlarmCount('critical') }}</div>
              <div class="stat-label">紧急告警</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-value">{{ getAlarmCount('major') }}</div>
              <div class="stat-label">重要告警</div>
            </div>
          </el-col>
        </el-row>

        <el-divider content-position="left">点位统计</el-divider>
        <el-table :data="dailyReport.points || []" stripe border max-height="400">
          <el-table-column prop="code" label="点位编码" width="150" />
          <el-table-column prop="name" label="点位名称" min-width="150" />
          <el-table-column prop="unit" label="单位" width="80" />
          <el-table-column prop="min" label="最小值" width="100">
            <template #default="{ row }">
              {{ row.min != null ? row.min : '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="max" label="最大值" width="100">
            <template #default="{ row }">
              {{ row.max != null ? row.max : '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="avg" label="平均值" width="100">
            <template #default="{ row }">
              {{ row.avg != null ? row.avg : '-' }}
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>

    <!-- 周报 -->
    <template v-if="reportType === 'weekly'">
      <el-card shadow="hover">
        <template #header>
          <div class="card-header">
            <span>周报 - {{ weeklyReport.title || '本周' }}</span>
            <div class="header-actions">
              <el-date-picker
                v-model="weeklyDatePicker"
                type="week"
                format="YYYY 第 ww 周"
                placeholder="选择周"
                @change="loadWeeklyReport"
              />
              <el-button type="primary" :icon="Download" @click="exportReport('weekly')">导出</el-button>
            </div>
          </div>
        </template>

        <el-row :gutter="20" class="stats-row">
          <el-col :span="8">
            <div class="stat-card">
              <div class="stat-value">{{ weeklyReport.total_alarms || 0 }}</div>
              <div class="stat-label">本周告警总数</div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="stat-card">
              <div class="stat-value">{{ weeklyReport.week_start || '-' }}</div>
              <div class="stat-label">开始日期</div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="stat-card">
              <div class="stat-value">{{ weeklyReport.week_end || '-' }}</div>
              <div class="stat-label">结束日期</div>
            </div>
          </el-col>
        </el-row>

        <el-divider content-position="left">每日告警趋势</el-divider>
        <div ref="weeklyChartRef" style="height: 300px;"></div>

        <el-divider content-position="left">每日明细</el-divider>
        <el-table :data="weeklyReport.daily_alarms || []" stripe border>
          <el-table-column prop="date" label="日期" width="120" />
          <el-table-column prop="weekday" label="星期" width="100" />
          <el-table-column prop="alarm_count" label="告警次数" width="120" />
          <el-table-column label="占比">
            <template #default="{ row }">
              <el-progress
                :percentage="getWeeklyPercentage(row.alarm_count)"
                :stroke-width="12"
                :format="() => row.alarm_count + '次'"
              />
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>

    <!-- 月报 -->
    <template v-if="reportType === 'monthly'">
      <el-card shadow="hover">
        <template #header>
          <div class="card-header">
            <span>月报 - {{ monthlyReport.title || '本月' }}</span>
            <div class="header-actions">
              <el-date-picker
                v-model="monthlyDatePicker"
                type="month"
                placeholder="选择月份"
                :disabled-date="disabledFutureMonth"
                @change="loadMonthlyReport"
              />
              <el-button type="primary" :icon="Download" @click="exportReport('monthly')">导出</el-button>
            </div>
          </div>
        </template>

        <el-row :gutter="20" class="stats-row">
          <el-col :span="6">
            <div class="stat-card">
              <div class="stat-value">{{ monthlyReport.total_alarms || 0 }}</div>
              <div class="stat-label">本月告警总数</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card critical">
              <div class="stat-value">{{ monthlyReport.alarm_by_level?.critical || 0 }}</div>
              <div class="stat-label">紧急告警</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card major">
              <div class="stat-value">{{ monthlyReport.alarm_by_level?.major || 0 }}</div>
              <div class="stat-label">重要告警</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="stat-card minor">
              <div class="stat-value">{{ monthlyReport.alarm_by_level?.minor || 0 }}</div>
              <div class="stat-label">次要告警</div>
            </div>
          </el-col>
        </el-row>

        <el-divider content-position="left">告警级别分布</el-divider>
        <div ref="monthlyChartRef" style="height: 300px;"></div>
      </el-card>
    </template>

    <!-- 自定义报表 -->
    <template v-if="reportType === 'custom'">
      <el-card shadow="hover">
        <template #header>
          <div class="card-header">
            <span>自定义报表</span>
          </div>
        </template>

        <el-form :model="customForm" label-width="100px" class="custom-form">
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="时间范围">
                <el-date-picker
                  v-model="customForm.dateRange"
                  type="daterange"
                  range-separator="至"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  :disabled-date="disabledFutureDate"
                />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="报表类型">
                <el-select v-model="customForm.reportType" placeholder="选择报表类型">
                  <el-option label="综合报表" value="comprehensive" />
                  <el-option label="告警报表" value="alarm" />
                  <el-option label="能耗报表" value="energy" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item>
            <el-button type="primary" @click="generateCustomReport" :loading="generating">
              生成报表
            </el-button>
          </el-form-item>
        </el-form>

        <el-divider content-position="left">历史报表记录</el-divider>
        <el-table :data="reportRecords" stripe border v-loading="loading">
          <el-table-column prop="report_name" label="报表名称" min-width="200" />
          <el-table-column prop="report_type" label="类型" width="100">
            <template #default="{ row }">
              <el-tag size="small">{{ getReportTypeName(row.report_type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="start_time" label="开始时间" width="150">
            <template #default="{ row }">
              {{ formatDate(row.start_time) }}
            </template>
          </el-table-column>
          <el-table-column prop="end_time" label="结束时间" width="150">
            <template #default="{ row }">
              {{ formatDate(row.end_time) }}
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="getStatusType(row.status)" size="small">
                {{ getStatusName(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="生成时间" width="150">
            <template #default="{ row }">
              {{ formatDate(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button
                type="primary"
                link
                :icon="Download"
                @click="downloadReportFile(row.id)"
                :disabled="row.status !== 'completed'"
              >
                下载
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Download } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import {
  getDailyReport,
  getWeeklyReport,
  getMonthlyReport,
  getReportRecords,
  generateReport,
  downloadReport,
  type ReportRecord
} from '@/api/modules/report'

const reportType = ref<'daily' | 'weekly' | 'monthly' | 'custom'>('daily')
const loading = ref(false)
const generating = ref(false)

// 日报相关
const dailyDatePicker = ref<Date>(new Date(Date.now() - 86400000)) // 默认昨天
const dailyDate = ref('')
const dailyReport = ref<any>({})

// 周报相关
const weeklyDatePicker = ref<Date>(new Date())
const weeklyReport = ref<any>({})
const weeklyChartRef = ref<HTMLElement>()
let weeklyChart: echarts.ECharts | null = null

// 月报相关
const monthlyDatePicker = ref<Date>(new Date())
const monthlyReport = ref<any>({})
const monthlyChartRef = ref<HTMLElement>()
let monthlyChart: echarts.ECharts | null = null

// 自定义报表
const customForm = reactive({
  dateRange: [] as Date[],
  reportType: 'comprehensive'
})
const reportRecords = ref<ReportRecord[]>([])

function formatDate(date: string): string {
  if (!date) return '-'
  return new Date(date).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function disabledFutureDate(date: Date): boolean {
  return date > new Date()
}

function disabledFutureMonth(date: Date): boolean {
  const now = new Date()
  return date.getFullYear() > now.getFullYear() ||
    (date.getFullYear() === now.getFullYear() && date.getMonth() > now.getMonth())
}

function getAlarmCount(level: string): number {
  return dailyReport.value.alarms?.[level] || 0
}

function getWeeklyPercentage(count: number): number {
  const total = weeklyReport.value.total_alarms || 1
  return Math.round((count / total) * 100)
}

function getReportTypeName(type: string): string {
  const names: Record<string, string> = {
    daily: '日报',
    weekly: '周报',
    monthly: '月报',
    custom: '自定义'
  }
  return names[type] || type
}

function getStatusType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  const types: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
    completed: 'success',
    generating: 'warning',
    failed: 'danger'
  }
  return types[status] || 'info'
}

function getStatusName(status: string): string {
  const names: Record<string, string> = {
    completed: '已完成',
    generating: '生成中',
    failed: '失败'
  }
  return names[status] || status
}

async function loadDailyReport() {
  if (!dailyDatePicker.value) return
  const date = dailyDatePicker.value
  dailyDate.value = date.toLocaleDateString('zh-CN')

  try {
    loading.value = true
    const dateStr = date.toISOString().split('T')[0]
    const data = await getDailyReport({ date: dateStr })
    dailyReport.value = data
  } catch (e) {
    console.error('加载日报失败', e)
    ElMessage.error('加载日报失败')
  } finally {
    loading.value = false
  }
}

async function loadWeeklyReport() {
  if (!weeklyDatePicker.value) return

  try {
    loading.value = true
    const date = weeklyDatePicker.value
    const dateStr = date.toISOString().split('T')[0]
    const data = await getWeeklyReport({ start_date: dateStr, end_date: dateStr })
    weeklyReport.value = data

    await nextTick()
    renderWeeklyChart()
  } catch (e) {
    console.error('加载周报失败', e)
    ElMessage.error('加载周报失败')
  } finally {
    loading.value = false
  }
}

async function loadMonthlyReport() {
  if (!monthlyDatePicker.value) return

  try {
    loading.value = true
    const date = monthlyDatePicker.value
    const data = await getMonthlyReport({
      year: date.getFullYear(),
      month: date.getMonth() + 1
    })
    monthlyReport.value = data

    await nextTick()
    renderMonthlyChart()
  } catch (e) {
    console.error('加载月报失败', e)
    ElMessage.error('加载月报失败')
  } finally {
    loading.value = false
  }
}

async function loadReportRecords() {
  try {
    loading.value = true
    const data = await getReportRecords({ page: 1, page_size: 20 })
    reportRecords.value = data.items || []
  } catch (e) {
    console.error('加载报表记录失败', e)
  } finally {
    loading.value = false
  }
}

function renderWeeklyChart() {
  if (!weeklyChartRef.value) return

  if (!weeklyChart) {
    weeklyChart = echarts.init(weeklyChartRef.value)
  }

  const dailyAlarms = weeklyReport.value.daily_alarms || []

  weeklyChart.setOption({
    tooltip: {
      trigger: 'axis'
    },
    xAxis: {
      type: 'category',
      data: dailyAlarms.map((d: any) => d.weekday)
    },
    yAxis: {
      type: 'value',
      name: '告警次数'
    },
    series: [{
      name: '告警数',
      type: 'bar',
      data: dailyAlarms.map((d: any) => d.alarm_count),
      itemStyle: {
        color: '#409eff'
      }
    }]
  })
}

function renderMonthlyChart() {
  if (!monthlyChartRef.value) return

  if (!monthlyChart) {
    monthlyChart = echarts.init(monthlyChartRef.value)
  }

  const alarmByLevel = monthlyReport.value.alarm_by_level || {}
  const data = [
    { name: '紧急', value: alarmByLevel.critical || 0 },
    { name: '重要', value: alarmByLevel.major || 0 },
    { name: '次要', value: alarmByLevel.minor || 0 },
    { name: '提示', value: alarmByLevel.info || 0 }
  ].filter(d => d.value > 0)

  monthlyChart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: 'left'
    },
    series: [{
      name: '告警级别',
      type: 'pie',
      radius: '60%',
      center: ['50%', '50%'],
      data: data,
      itemStyle: {
        color: (params: any) => {
          const colors: Record<string, string> = {
            '紧急': '#f56c6c',
            '重要': '#e6a23c',
            '次要': '#409eff',
            '提示': '#909399'
          }
          return colors[params.name] || '#409eff'
        }
      },
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowOffsetX: 0,
          shadowColor: 'rgba(0, 0, 0, 0.5)'
        }
      }
    }]
  })
}

async function generateCustomReport() {
  if (customForm.dateRange.length !== 2) {
    ElMessage.warning('请选择时间范围')
    return
  }

  try {
    generating.value = true
    await generateReport({
      report_type: 'custom',
      start_time: customForm.dateRange[0].toISOString(),
      end_time: customForm.dateRange[1].toISOString()
    })
    ElMessage.success('报表生成成功')
    await loadReportRecords()
  } catch (e) {
    console.error('生成报表失败', e)
    ElMessage.error('生成报表失败')
  } finally {
    generating.value = false
  }
}

async function downloadReportFile(id: number) {
  try {
    const blob = await downloadReport(id)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `report_${id}.json`
    link.click()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    console.error('下载报表失败', e)
    ElMessage.error('下载报表失败')
  }
}

function exportReport(type: string) {
  let data: any
  let filename: string

  if (type === 'daily') {
    data = dailyReport.value
    filename = `daily_report_${dailyDate.value}.json`
  } else if (type === 'weekly') {
    data = weeklyReport.value
    filename = `weekly_report_${weeklyReport.value.week_start}.json`
  } else {
    data = monthlyReport.value
    filename = `monthly_report_${monthlyReport.value.year}_${monthlyReport.value.month}.json`
  }

  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  window.URL.revokeObjectURL(url)
  ElMessage.success('导出成功')
}

function handleTypeChange() {
  if (reportType.value === 'daily') {
    loadDailyReport()
  } else if (reportType.value === 'weekly') {
    loadWeeklyReport()
  } else if (reportType.value === 'monthly') {
    loadMonthlyReport()
  } else if (reportType.value === 'custom') {
    loadReportRecords()
  }
}

onMounted(() => {
  loadDailyReport()
})

// 监听窗口大小变化，调整图表大小
window.addEventListener('resize', () => {
  weeklyChart?.resize()
  monthlyChart?.resize()
})
</script>

<style scoped lang="scss">
.report-page {
  .type-card {
    margin-bottom: 20px;
    text-align: center;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    color: var(--text-primary);

    .header-actions {
      display: flex;
      gap: 10px;
    }
  }

  .stats-row {
    margin-bottom: 20px;

    .stat-card {
      background: linear-gradient(135deg, rgba(102, 126, 234, 0.8) 0%, rgba(118, 75, 162, 0.8) 100%);
      border-radius: 8px;
      padding: 20px;
      color: #fff;
      text-align: center;
      border: 1px solid rgba(255, 255, 255, 0.1);

      &.alarm {
        background: linear-gradient(135deg, rgba(240, 147, 251, 0.8) 0%, rgba(245, 87, 108, 0.8) 100%);
      }

      &.critical {
        background: linear-gradient(135deg, rgba(255, 107, 107, 0.8) 0%, rgba(238, 90, 90, 0.8) 100%);
      }

      &.major {
        background: linear-gradient(135deg, rgba(255, 165, 2, 0.8) 0%, rgba(255, 127, 80, 0.8) 100%);
      }

      &.minor {
        background: linear-gradient(135deg, rgba(112, 161, 255, 0.8) 0%, rgba(83, 82, 237, 0.8) 100%);
      }

      .stat-value {
        font-size: 28px;
        font-weight: bold;
        margin-bottom: 5px;
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
      }

      .stat-label {
        font-size: 14px;
        opacity: 0.9;
      }
    }
  }

  .custom-form {
    max-width: 800px;
    margin-bottom: 20px;
  }
}
</style>
