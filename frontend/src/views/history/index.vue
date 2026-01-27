<template>
  <div class="history-page">
    <!-- 查询条件 -->
    <el-card shadow="hover" class="filter-card">
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item label="选择点位">
          <el-select
            v-model="filters.point_id"
            placeholder="请选择点位"
            filterable
            style="width: 240px;"
          >
            <el-option
              v-for="point in pointList"
              :key="point.id"
              :label="`${point.point_code} - ${point.point_name}`"
              :value="point.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="filters.dateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            :shortcuts="dateShortcuts"
            value-format="YYYY-MM-DD HH:mm:ss"
          />
        </el-form-item>
        <el-form-item label="数据粒度">
          <el-select v-model="filters.granularity" style="width: 120px;">
            <el-option label="原始数据" value="raw" />
            <el-option label="分钟均值" value="minute" />
            <el-option label="小时均值" value="hour" />
            <el-option label="日均值" value="day" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleQuery">查询</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
          <el-button type="success" :icon="Download" @click="handleExport">导出</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-row :gutter="20">
      <!-- 趋势图表 -->
      <el-col :span="16">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>数据趋势</span>
              <el-radio-group v-model="chartType" size="small">
                <el-radio-button value="line">折线图</el-radio-button>
                <el-radio-button value="bar">柱状图</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <div ref="chartRef" class="trend-chart"></div>
        </el-card>
      </el-col>

      <!-- 统计信息 -->
      <el-col :span="8">
        <el-card shadow="hover" class="stats-card">
          <template #header>统计信息</template>
          <el-descriptions :column="1" border v-if="statistics">
            <el-descriptions-item label="数据点数">
              {{ statistics.count }} 条
            </el-descriptions-item>
            <el-descriptions-item label="最小值">
              <span class="stat-value min">{{ statistics.min_value?.toFixed(2) }}</span>
              {{ currentPoint?.unit }}
            </el-descriptions-item>
            <el-descriptions-item label="最大值">
              <span class="stat-value max">{{ statistics.max_value?.toFixed(2) }}</span>
              {{ currentPoint?.unit }}
            </el-descriptions-item>
            <el-descriptions-item label="平均值">
              <span class="stat-value avg">{{ statistics.avg_value?.toFixed(2) }}</span>
              {{ currentPoint?.unit }}
            </el-descriptions-item>
            <el-descriptions-item label="标准差">
              {{ statistics.std_dev?.toFixed(4) }}
            </el-descriptions-item>
            <el-descriptions-item label="变化率">
              <el-tag :type="statistics.change_rate >= 0 ? 'success' : 'danger'">
                {{ statistics.change_rate >= 0 ? '+' : '' }}{{ (statistics.change_rate * 100).toFixed(2) }}%
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="起始值">
              {{ statistics.first_value?.toFixed(2) }} {{ currentPoint?.unit }}
            </el-descriptions-item>
            <el-descriptions-item label="结束值">
              {{ statistics.last_value?.toFixed(2) }} {{ currentPoint?.unit }}
            </el-descriptions-item>
          </el-descriptions>
          <el-empty v-else description="请先查询数据" :image-size="80" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 数据表格 -->
    <el-card shadow="hover" style="margin-top: 20px;">
      <template #header>
        <div class="card-header">
          <span>历史数据明细</span>
          <span class="total-info">共 {{ pagination.total }} 条记录</span>
        </div>
      </template>
      <el-table :data="historyData" stripe border v-loading="loading">
        <el-table-column type="index" label="#" width="60" />
        <el-table-column prop="created_at" label="采集时间" width="180" />
        <el-table-column prop="value" label="数值" width="120">
          <template #default="{ row }">
            {{ row.value?.toFixed(2) }} {{ currentPoint?.unit }}
          </template>
        </el-table-column>
        <el-table-column prop="raw_value" label="原始值" width="120">
          <template #default="{ row }">
            {{ row.raw_value?.toFixed(4) }}
          </template>
        </el-table-column>
        <el-table-column prop="quality" label="质量码" width="100">
          <template #default="{ row }">
            <el-tag :type="row.quality === 0 ? 'success' : 'warning'" size="small">
              {{ row.quality === 0 ? '良好' : '异常' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.page_size"
        :total="pagination.total"
        :page-sizes="[20, 50, 100, 200]"
        layout="total, sizes, prev, pager, next, jumper"
        style="margin-top: 20px; justify-content: flex-end;"
        @size-change="handleQuery"
        @current-change="handleQuery"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Refresh, Download } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { getPointList, type PointInfo } from '@/api/modules/point'
import {
  getPointHistory, getPointTrend, getPointStatistics, exportHistory,
  type HistoryData, type TrendData, type HistoryStatistics
} from '@/api/modules/history'

const chartRef = ref<HTMLElement>()
let chartInstance: echarts.ECharts | null = null

const loading = ref(false)
const pointList = ref<PointInfo[]>([])
const historyData = ref<HistoryData[]>([])
const trendData = ref<TrendData[]>([])
const statistics = ref<HistoryStatistics | null>(null)
const chartType = ref<'line' | 'bar'>('line')

const filters = reactive({
  point_id: null as number | null,
  dateRange: [] as string[],
  granularity: 'raw' as 'raw' | 'minute' | 'hour' | 'day'
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const currentPoint = computed(() => {
  return pointList.value.find(p => p.id === filters.point_id)
})

const dateShortcuts = [
  {
    text: '最近1小时',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setTime(start.getTime() - 3600 * 1000)
      return [start, end]
    }
  },
  {
    text: '最近24小时',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setTime(start.getTime() - 3600 * 1000 * 24)
      return [start, end]
    }
  },
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
  }
]

onMounted(async () => {
  await loadPoints()
  initChart()
})

watch(chartType, () => {
  updateChart()
})

async function loadPoints() {
  try {
    const result = await getPointList({ point_type: 'AI' })
    pointList.value = result.items
  } catch (e) {
    console.error('加载点位失败', e)
  }
}

function initChart() {
  if (chartRef.value) {
    chartInstance = echarts.init(chartRef.value)
    window.addEventListener('resize', () => {
      chartInstance?.resize()
    })
  }
}

function updateChart() {
  if (!chartInstance || trendData.value.length === 0) return

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const data = params[0]
        return `${data.axisValue}<br/>数值: ${data.value?.toFixed(2)} ${currentPoint.value?.unit || ''}`
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
      data: trendData.value.map(d => d.time),
      axisLabel: {
        rotate: 30,
        formatter: (value: string) => {
          return value.substring(5, 16)
        }
      }
    },
    yAxis: {
      type: 'value',
      name: currentPoint.value?.unit || '',
      axisLabel: {
        formatter: '{value}'
      }
    },
    series: [{
      name: currentPoint.value?.point_name || '数值',
      type: chartType.value,
      data: trendData.value.map(d => d.value),
      smooth: true,
      areaStyle: chartType.value === 'line' ? { opacity: 0.3 } : undefined,
      itemStyle: {
        color: '#409eff'
      }
    }]
  }

  chartInstance.setOption(option)
}

async function handleQuery() {
  if (!filters.point_id) {
    ElMessage.warning('请选择点位')
    return
  }
  if (!filters.dateRange || filters.dateRange.length !== 2) {
    ElMessage.warning('请选择时间范围')
    return
  }

  loading.value = true
  try {
    const params = {
      start_time: filters.dateRange[0],
      end_time: filters.dateRange[1],
      granularity: filters.granularity
    }

    // 并行请求
    const [historyRes, trendRes, statsRes] = await Promise.all([
      getPointHistory(filters.point_id, {
        ...params,
        page: pagination.page,
        page_size: pagination.page_size
      }),
      getPointTrend(filters.point_id, { ...params, limit: 500 }),
      getPointStatistics(filters.point_id, params)
    ])

    historyData.value = historyRes.items
    pagination.total = historyRes.total
    trendData.value = trendRes
    statistics.value = statsRes

    await nextTick()
    updateChart()
  } catch (e) {
    console.error('查询失败', e)
    ElMessage.error('查询失败')
  } finally {
    loading.value = false
  }
}

function handleReset() {
  filters.point_id = null
  filters.dateRange = []
  filters.granularity = 'raw'
  pagination.page = 1
  historyData.value = []
  trendData.value = []
  statistics.value = null
  chartInstance?.clear()
}

async function handleExport() {
  if (!filters.point_id || !filters.dateRange || filters.dateRange.length !== 2) {
    ElMessage.warning('请先查询数据')
    return
  }

  try {
    const blob = await exportHistory({
      point_ids: [filters.point_id],
      start_time: filters.dateRange[0],
      end_time: filters.dateRange[1],
      granularity: filters.granularity,
      format: 'excel'
    })

    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `历史数据_${currentPoint.value?.point_code}_${Date.now()}.xlsx`
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
.history-page {
  .filter-card {
    margin-bottom: 20px;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    color: var(--text-primary);
  }

  .trend-chart {
    height: 350px;
  }

  .stats-card {
    .stat-value {
      font-weight: bold;
      font-size: 16px;

      &.min { color: var(--success-color); }
      &.max { color: var(--error-color); }
      &.avg { color: var(--primary-color); }
    }
  }

  .total-info {
    font-size: 14px;
    color: var(--text-secondary);
  }
}
</style>
