<template>
  <div class="shift-reports">
    <el-page-header @back="$router.back()" title="返回">
      <template #content>
        <span>收益报表</span>
      </template>
    </el-page-header>

    <el-card shadow="hover" style="margin-top: 20px">
      <template #header>
        <span>报表查询</span>
      </template>

      <el-form :model="queryForm" inline>
        <el-form-item label="报表类型">
          <el-select v-model="queryForm.report_type" placeholder="请选择报表类型" @change="handleTypeChange">
            <el-option label="月度报表" value="monthly" />
            <el-option label="年度报表" value="yearly" />
          </el-select>
        </el-form-item>

        <el-form-item label="时间范围" v-if="queryForm.report_type === 'monthly'">
          <el-date-picker
            v-model="queryForm.month"
            type="month"
            placeholder="选择月份"
            format="YYYY-MM"
            value-format="YYYY-MM"
          />
        </el-form-item>

        <el-form-item label="时间范围" v-if="queryForm.report_type === 'yearly'">
          <el-date-picker
            v-model="queryForm.year"
            type="year"
            placeholder="选择年份"
            format="YYYY"
            value-format="YYYY"
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleQuery" :loading="loading">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
          <el-button type="success" @click="handleExport('excel')" :disabled="!reportData">导出 Excel</el-button>
          <el-button type="warning" @click="handleExport('pdf')" :disabled="!reportData">导出 PDF</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-row :gutter="20" style="margin-top: 20px" v-if="reportData">
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="总成本节省" :value="reportData.total_cost_saving || 0" suffix="元" :precision="0" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="总节能量" :value="reportData.total_energy_saving || 0" suffix="kWh" :precision="0" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="执行次数" :value="reportData.execution_count || 0" suffix="次" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="成功率" :value="reportData.success_rate || 0" suffix="%" :precision="1" />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="hover" style="margin-top: 20px" v-if="reportData">
      <template #header>
        <span>成本节省趋势</span>
      </template>
      <div ref="costChartRef" style="width: 100%; height: 400px"></div>
    </el-card>

    <el-card shadow="hover" style="margin-top: 20px" v-if="reportData">
      <template #header>
        <span>节能量趋势</span>
      </template>
      <div ref="energyChartRef" style="width: 100%; height: 400px"></div>
    </el-card>

    <el-card shadow="hover" style="margin-top: 20px" v-if="reportData">
      <template #header>
        <span>执行统计</span>
      </template>
      <el-row :gutter="20">
        <el-col :span="12">
          <div ref="executionPieRef" style="width: 100%; height: 300px"></div>
        </el-col>
        <el-col :span="12">
          <div ref="periodPieRef" style="width: 100%; height: 300px"></div>
        </el-col>
      </el-row>
    </el-card>

    <el-card shadow="hover" style="margin-top: 20px" v-if="reportData">
      <template #header>
        <span>详细数据</span>
      </template>
      <el-table :data="reportData.details" border>
        <el-table-column type="index" label="#" width="60" />
        <el-table-column prop="date" label="日期" width="120" />
        <el-table-column prop="execution_count" label="执行次数" width="100" align="right" />
        <el-table-column prop="success_count" label="成功次数" width="100" align="right" />
        <el-table-column prop="failed_count" label="失败次数" width="100" align="right" />
        <el-table-column prop="total_shift_power" label="转移功率 (kW)" width="140" align="right">
          <template #default="{ row }">
            {{ row.total_shift_power?.toFixed(1) || 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="cost_saving" label="成本节省 (元)" width="140" align="right">
          <template #default="{ row }">
            {{ row.cost_saving?.toFixed(0) || 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="energy_saving" label="节能量 (kWh)" width="140" align="right">
          <template #default="{ row }">
            {{ row.energy_saving?.toFixed(0) || 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="success_rate" label="成功率" width="100" align="right">
          <template #default="{ row }">
            {{ row.success_rate?.toFixed(1) || 0 }}%
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'

interface QueryForm {
  report_type: string
  month: string
  year: string
}

interface ReportData {
  total_cost_saving: number
  total_energy_saving: number
  execution_count: number
  success_rate: number
  details: Array<any>
  trend_data: Array<any>
  execution_stats: any
  period_stats: any
}

const loading = ref(false)
const queryForm = ref<QueryForm>({
  report_type: 'monthly',
  month: new Date().toISOString().slice(0, 7),
  year: new Date().getFullYear().toString()
})
const reportData = ref<ReportData | null>(null)
const costChartRef = ref<HTMLElement>()
const energyChartRef = ref<HTMLElement>()
const executionPieRef = ref<HTMLElement>()
const periodPieRef = ref<HTMLElement>()
const costChartInstance = ref<echarts.ECharts>()
const energyChartInstance = ref<echarts.ECharts>()
const executionPieInstance = ref<echarts.ECharts>()
const periodPieInstance = ref<echarts.ECharts>()

const handleTypeChange = () => {
  reportData.value = null
}

const handleQuery = async () => {
  loading.value = true
  try {
    // TODO: 调用 API 获取报表数据
    // const res = await getShiftReport(queryForm.value)
    // reportData.value = res.data
    
    // 模拟数据
    const days = queryForm.value.report_type === 'monthly' ? 30 : 12
    const details = []
    const trendData = []
    
    for (let i = 1; i <= days; i++) {
      const date = queryForm.value.report_type === 'monthly' 
        ? `${queryForm.value.month}-${String(i).padStart(2, '0')}`
        : `${queryForm.value.year}-${String(i).padStart(2, '0')}`
      
      const executionCount = Math.floor(Math.random() * 5) + 1
      const successCount = Math.floor(executionCount * (0.8 + Math.random() * 0.2))
      const failedCount = executionCount - successCount
      const costSaving = Math.random() * 500 + 200
      const energySaving = Math.random() * 800 + 400
      
      details.push({
        date,
        execution_count: executionCount,
        success_count: successCount,
        failed_count: failedCount,
        total_shift_power: Math.random() * 200 + 100,
        cost_saving: costSaving,
        energy_saving: energySaving,
        success_rate: (successCount / executionCount) * 100
      })
      
      trendData.push({
        date,
        cost_saving: costSaving,
        energy_saving: energySaving
      })
    }
    
    const totalCostSaving = details.reduce((sum, item) => sum + item.cost_saving, 0)
    const totalEnergySaving = details.reduce((sum, item) => sum + item.energy_saving, 0)
    const totalExecutions = details.reduce((sum, item) => sum + item.execution_count, 0)
    const totalSuccess = details.reduce((sum, item) => sum + item.success_count, 0)
    
    reportData.value = {
      total_cost_saving: totalCostSaving,
      total_energy_saving: totalEnergySaving,
      execution_count: totalExecutions,
      success_rate: (totalSuccess / totalExecutions) * 100,
      details,
      trend_data: trendData,
      execution_stats: {
        success: totalSuccess,
        failed: totalExecutions - totalSuccess
      },
      period_stats: {
        peak_to_valley: Math.floor(totalExecutions * 0.6),
        valley_to_peak: Math.floor(totalExecutions * 0.3),
        peak_to_flat: Math.floor(totalExecutions * 0.1)
      }
    }
    
    setTimeout(() => {
      initCharts()
    }, 100)
  } catch (error: any) {
    ElMessage.error(error.message || '查询失败')
  } finally {
    loading.value = false
  }
}

const handleReset = () => {
  queryForm.value = {
    report_type: 'monthly',
    month: new Date().toISOString().slice(0, 7),
    year: new Date().getFullYear().toString()
  }
  reportData.value = null
}

const handleExport = async (format: 'excel' | 'pdf') => {
  try {
    // TODO: 调用 API 导出报表
    // const res = await exportShiftReport({ ...queryForm.value, format })
    // window.open(res.data.download_url)
    
    ElMessage.success(`正在导出 ${format.toUpperCase()} 格式报表...`)
  } catch (error: any) {
    ElMessage.error(error.message || '导出失败')
  }
}

const initCharts = () => {
  if (!reportData.value) return

  // 成本节省趋势图
  if (costChartRef.value) {
    costChartInstance.value = echarts.init(costChartRef.value)
    costChartInstance.value.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: reportData.value.trend_data.map(item => item.date)
      },
      yAxis: { type: 'value', name: '成本节省 (元)' },
      series: [{
        name: '成本节省',
        type: 'line',
        data: reportData.value.trend_data.map(item => item.cost_saving),
        smooth: true,
        areaStyle: { opacity: 0.3 },
        lineStyle: { color: '#67C23A' }
      }]
    })
  }

  // 节能量趋势图
  if (energyChartRef.value) {
    energyChartInstance.value = echarts.init(energyChartRef.value)
    energyChartInstance.value.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: reportData.value.trend_data.map(item => item.date)
      },
      yAxis: { type: 'value', name: '节能量 (kWh)' },
      series: [{
        name: '节能量',
        type: 'line',
        data: reportData.value.trend_data.map(item => item.energy_saving),
        smooth: true,
        areaStyle: { opacity: 0.3 },
        lineStyle: { color: '#409EFF' }
      }]
    })
  }

  // 执行统计饼图
  if (executionPieRef.value) {
    executionPieInstance.value = echarts.init(executionPieRef.value)
    executionPieInstance.value.setOption({
      title: { text: '执行成功率', left: 'center' },
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie',
        radius: '60%',
        data: [
          { value: reportData.value.execution_stats.success, name: '成功' },
          { value: reportData.value.execution_stats.failed, name: '失败' }
        ],
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

  // 时段分布饼图
  if (periodPieRef.value) {
    periodPieInstance.value = echarts.init(periodPieRef.value)
    periodPieInstance.value.setOption({
      title: { text: '转移时段分布', left: 'center' },
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie',
        radius: '60%',
        data: [
          { value: reportData.value.period_stats.peak_to_valley, name: '峰转谷' },
          { value: reportData.value.period_stats.valley_to_peak, name: '谷转峰' },
          { value: reportData.value.period_stats.peak_to_flat, name: '峰转平' }
        ],
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
}

onMounted(() => {
  handleQuery()
})

onUnmounted(() => {
  if (costChartInstance.value) costChartInstance.value.dispose()
  if (energyChartInstance.value) energyChartInstance.value.dispose()
  if (executionPieInstance.value) executionPieInstance.value.dispose()
  if (periodPieInstance.value) periodPieInstance.value.dispose()
})
</script>

<style scoped lang="scss">
.shift-reports {
  padding: 20px;
}
</style>
