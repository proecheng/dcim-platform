<template>
  <div class="optimization-report">
    <!-- 月份选择器 -->
    <div class="report-header">
      <el-date-picker
        v-model="selectedMonth"
        type="month"
        placeholder="选择月份"
        format="YYYY年MM月"
        value-format="YYYY-MM"
        :disabled-date="disabledDate"
        @change="loadReport"
      />
      <el-button type="primary" :icon="Refresh" @click="loadReport">刷新</el-button>
    </div>

    <el-row :gutter="20" class="summary-cards">
      <!-- 成本节省卡片 -->
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card saving-card">
          <div class="stat-icon">
            <el-icon :size="32"><Money /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">¥{{ formatNumber(report?.cost_analysis?.actual_saving || 0) }}</div>
            <div class="stat-label">实际节省</div>
            <div class="stat-sub">
              计划: ¥{{ formatNumber(report?.cost_analysis?.planned_saving || 0) }}
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 达成率卡片 -->
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card achievement-card">
          <div class="stat-icon">
            <el-icon :size="32"><TrendCharts /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ report?.cost_analysis?.saving_achievement || 0 }}%</div>
            <div class="stat-label">节省达成率</div>
            <div class="stat-progress">
              <el-progress
                :percentage="report?.cost_analysis?.saving_achievement || 0"
                :stroke-width="8"
                :show-text="false"
                :color="getAchievementColor(report?.cost_analysis?.saving_achievement)"
              />
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 执行统计卡片 -->
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card execution-card">
          <div class="stat-icon">
            <el-icon :size="32"><Finished /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ report?.execution_stats?.success_rate || 0 }}%</div>
            <div class="stat-label">执行成功率</div>
            <div class="stat-sub">
              {{ report?.execution_stats?.executed_schedules || 0 }} / {{ report?.execution_stats?.total_schedules || 0 }} 次调度
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 需量控制卡片 -->
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card demand-card">
          <div class="stat-icon">
            <el-icon :size="32"><Histogram /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ report?.demand_control?.utilization || 0 }}%</div>
            <div class="stat-label">需量利用率</div>
            <div class="stat-sub">
              超标 {{ report?.demand_control?.violations || 0 }} 次
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表区域 -->
    <el-row :gutter="20" class="chart-row">
      <!-- 计划vs实际对比 -->
      <el-col :span="14">
        <el-card shadow="hover" class="chart-card">
          <template #header>
            <div class="card-header">
              <span>计划 vs 实际对比</span>
              <el-date-picker
                v-model="comparisonDate"
                type="date"
                placeholder="选择日期"
                format="MM-DD"
                value-format="YYYY-MM-DD"
                size="small"
                @change="loadComparison"
              />
            </div>
          </template>
          <div ref="comparisonChartRef" class="chart-container"></div>
        </el-card>
      </el-col>

      <!-- 预测准确性 -->
      <el-col :span="10">
        <el-card shadow="hover" class="chart-card">
          <template #header>
            <span>预测准确性指标</span>
          </template>
          <div class="metrics-grid">
            <div class="metric-item">
              <div class="metric-label">MAE (平均绝对误差)</div>
              <div class="metric-value">{{ report?.forecast_quality?.mae || 0 }} kW</div>
              <div class="metric-bar">
                <el-progress
                  :percentage="getMetricPercentage(report?.forecast_quality?.mae, 100)"
                  :stroke-width="10"
                  :show-text="false"
                  color="#409eff"
                />
              </div>
            </div>
            <div class="metric-item">
              <div class="metric-label">MAPE (平均百分比误差)</div>
              <div class="metric-value">{{ report?.forecast_quality?.mape || 0 }}%</div>
              <div class="metric-bar">
                <el-progress
                  :percentage="Math.min(report?.forecast_quality?.mape || 0, 100)"
                  :stroke-width="10"
                  :show-text="false"
                  :color="getMapeColor(report?.forecast_quality?.mape)"
                />
              </div>
            </div>
            <div class="metric-item">
              <div class="metric-label">准确率 (偏差<10%)</div>
              <div class="metric-value">{{ report?.forecast_quality?.accuracy_rate || 0 }}%</div>
              <div class="metric-bar">
                <el-progress
                  :percentage="report?.forecast_quality?.accuracy_rate || 0"
                  :stroke-width="10"
                  :show-text="false"
                  :color="getAccuracyColor(report?.forecast_quality?.accuracy_rate)"
                />
              </div>
            </div>
            <div class="metric-item">
              <div class="metric-label">系统偏差</div>
              <div class="metric-value" :class="getBiasClass(report?.forecast_quality?.bias)">
                {{ formatBias(report?.forecast_quality?.bias) }}
              </div>
              <div class="metric-desc">
                {{ report?.forecast_quality?.bias > 0 ? '预测偏低' : report?.forecast_quality?.bias < 0 ? '预测偏高' : '无偏差' }}
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 需量控制详情 -->
    <el-row :gutter="20" class="chart-row">
      <el-col :span="12">
        <el-card shadow="hover" class="chart-card">
          <template #header>
            <span>需量控制统计</span>
          </template>
          <div ref="demandChartRef" class="chart-container"></div>
        </el-card>
      </el-col>

      <!-- 优化建议 -->
      <el-col :span="12">
        <el-card shadow="hover" class="recommendations-card">
          <template #header>
            <div class="card-header">
              <span>优化建议</span>
              <el-button type="primary" size="small" @click="runAutoAdjust" :loading="adjusting">
                自动调整
              </el-button>
            </div>
          </template>
          <div class="recommendations-list">
            <div
              v-for="(rec, index) in report?.recommendations || []"
              :key="index"
              class="recommendation-item"
            >
              <el-icon :size="18" class="rec-icon">
                <WarningFilled v-if="rec.includes('较低') || rec.includes('超标')" />
                <InfoFilled v-else />
              </el-icon>
              <span class="rec-text">{{ rec }}</span>
            </div>
            <el-empty v-if="!report?.recommendations?.length" description="暂无优化建议" />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Refresh, Money, TrendCharts, Finished, Histogram,
  WarningFilled, InfoFilled
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import {
  getOptimizationReport,
  getPlanActualComparison,
  runParameterAdjustment,
  type OptimizationReport,
  type PlanActualComparison
} from '@/api/modules/optimization'

// 状态
const selectedMonth = ref('')
const comparisonDate = ref('')
const report = ref<OptimizationReport | null>(null)
const comparison = ref<PlanActualComparison | null>(null)
const adjusting = ref(false)

// 图表引用
const comparisonChartRef = ref<HTMLDivElement>()
const demandChartRef = ref<HTMLDivElement>()
let comparisonChart: echarts.ECharts | null = null
let demandChart: echarts.ECharts | null = null

// 初始化
onMounted(() => {
  // 默认当前月份
  const now = new Date()
  selectedMonth.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  comparisonDate.value = new Date(now.getTime() - 86400000).toISOString().split('T')[0]

  loadReport()
  loadComparison()

  // 初始化图表
  nextTick(() => {
    initCharts()
  })
})

// 禁用未来日期
const disabledDate = (date: Date) => {
  return date > new Date()
}

// 加载报告
const loadReport = async () => {
  try {
    const res = await getOptimizationReport(selectedMonth.value)
    if (res.data.code === 0) {
      report.value = res.data.data
      updateDemandChart()
    }
  } catch (error) {
    console.error('加载报告失败:', error)
  }
}

// 加载对比数据
const loadComparison = async () => {
  if (!comparisonDate.value) return
  try {
    const res = await getPlanActualComparison(comparisonDate.value)
    if (res.data.code === 0) {
      comparison.value = res.data.data
      updateComparisonChart()
    }
  } catch (error) {
    console.error('加载对比数据失败:', error)
  }
}

// 初始化图表
const initCharts = () => {
  if (comparisonChartRef.value) {
    comparisonChart = echarts.init(comparisonChartRef.value)
  }
  if (demandChartRef.value) {
    demandChart = echarts.init(demandChartRef.value)
  }

  window.addEventListener('resize', () => {
    comparisonChart?.resize()
    demandChart?.resize()
  })
}

// 更新对比图表
const updateComparisonChart = () => {
  if (!comparisonChart || !comparison.value) return

  const hours = Array.from({ length: 96 }, (_, i) => {
    const h = Math.floor(i / 4)
    const m = (i % 4) * 15
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
  })

  const option: echarts.EChartsOption = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(50, 50, 50, 0.9)',
      borderColor: '#333',
      textStyle: { color: '#fff' },
      formatter: (params: any) => {
        let html = `<div style="font-weight:bold">${params[0].axisValue}</div>`
        params.forEach((p: any) => {
          html += `<div>${p.marker} ${p.seriesName}: ${p.value?.toFixed(1) || '-'} kW</div>`
        })
        return html
      }
    },
    legend: {
      data: ['计划负荷', '实际负荷'],
      textStyle: { color: '#ccc' },
      top: 5
    },
    grid: {
      left: 60,
      right: 30,
      top: 40,
      bottom: 30
    },
    xAxis: {
      type: 'category',
      data: hours,
      axisLabel: {
        color: '#999',
        interval: 15
      },
      axisLine: { lineStyle: { color: '#444' } }
    },
    yAxis: {
      type: 'value',
      name: 'kW',
      nameTextStyle: { color: '#999' },
      axisLabel: { color: '#999' },
      splitLine: { lineStyle: { color: '#333' } }
    },
    series: [
      {
        name: '计划负荷',
        type: 'line',
        data: comparison.value.planned_load,
        smooth: true,
        lineStyle: { width: 2, color: '#409eff' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
            { offset: 1, color: 'rgba(64, 158, 255, 0)' }
          ])
        },
        symbol: 'none'
      },
      {
        name: '实际负荷',
        type: 'line',
        data: comparison.value.actual_load,
        smooth: true,
        lineStyle: { width: 2, color: '#67c23a', type: 'dashed' },
        symbol: 'none'
      }
    ]
  }

  comparisonChart.setOption(option)
}

// 更新需量图表
const updateDemandChart = () => {
  if (!demandChart || !report.value) return

  const demandData = report.value.demand_control

  const option: echarts.EChartsOption = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(50, 50, 50, 0.9)',
      borderColor: '#333',
      textStyle: { color: '#fff' }
    },
    series: [
      {
        type: 'gauge',
        startAngle: 200,
        endAngle: -20,
        min: 0,
        max: demandData?.target || 800,
        splitNumber: 4,
        center: ['50%', '60%'],
        radius: '85%',
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: '#52c41a' },
            { offset: 0.5, color: '#faad14' },
            { offset: 1, color: '#f5222d' }
          ])
        },
        progress: {
          show: true,
          width: 20
        },
        pointer: {
          show: true,
          length: '60%',
          width: 6
        },
        axisLine: {
          lineStyle: {
            width: 20,
            color: [[1, 'rgba(255,255,255,0.1)']]
          }
        },
        axisTick: {
          distance: -30,
          lineStyle: { color: '#666', width: 1 }
        },
        splitLine: {
          distance: -35,
          length: 10,
          lineStyle: { color: '#666', width: 2 }
        },
        axisLabel: {
          distance: -20,
          color: '#999',
          fontSize: 12
        },
        anchor: {
          show: true,
          size: 15,
          itemStyle: {
            borderColor: '#409eff',
            borderWidth: 2
          }
        },
        title: {
          show: true,
          offsetCenter: [0, '75%'],
          color: '#ccc',
          fontSize: 14
        },
        detail: {
          valueAnimation: true,
          offsetCenter: [0, '45%'],
          fontSize: 28,
          fontWeight: 'bold',
          color: '#fff',
          formatter: '{value} kW'
        },
        data: [
          {
            value: demandData?.max_reached || 0,
            name: `目标: ${demandData?.target || 800} kW`
          }
        ]
      }
    ]
  }

  demandChart.setOption(option)
}

// 执行自动调整
const runAutoAdjust = async () => {
  adjusting.value = true
  try {
    const res = await runParameterAdjustment()
    if (res.data.code === 0) {
      ElMessage.success('参数已自动调整')
      loadReport()
    }
  } catch (error) {
    ElMessage.error('自动调整失败')
  } finally {
    adjusting.value = false
  }
}

// 格式化数字
const formatNumber = (num: number) => {
  if (num >= 10000) {
    return (num / 10000).toFixed(2) + '万'
  }
  return num.toFixed(2)
}

// 格式化偏差
const formatBias = (bias: number | undefined) => {
  if (bias === undefined) return '0 kW'
  const sign = bias > 0 ? '+' : ''
  return `${sign}${bias.toFixed(1)} kW`
}

// 获取达成率颜色
const getAchievementColor = (rate: number | undefined) => {
  if (!rate) return '#909399'
  if (rate >= 90) return '#67c23a'
  if (rate >= 70) return '#e6a23c'
  return '#f56c6c'
}

// 获取 MAPE 颜色
const getMapeColor = (mape: number | undefined) => {
  if (!mape) return '#67c23a'
  if (mape <= 10) return '#67c23a'
  if (mape <= 20) return '#e6a23c'
  return '#f56c6c'
}

// 获取准确率颜色
const getAccuracyColor = (rate: number | undefined) => {
  if (!rate) return '#909399'
  if (rate >= 85) return '#67c23a'
  if (rate >= 70) return '#e6a23c'
  return '#f56c6c'
}

// 获取偏差样式类
const getBiasClass = (bias: number | undefined) => {
  if (!bias) return ''
  if (Math.abs(bias) <= 10) return 'bias-normal'
  return bias > 0 ? 'bias-low' : 'bias-high'
}

// 获取指标百分比
const getMetricPercentage = (value: number | undefined, max: number) => {
  if (!value) return 0
  return Math.min((value / max) * 100, 100)
}

// 监听月份变化
watch(selectedMonth, () => {
  // 设置对比日期为该月最后一天
  const [year, month] = selectedMonth.value.split('-').map(Number)
  const lastDay = new Date(year, month, 0).getDate()
  const today = new Date()
  if (year === today.getFullYear() && month === today.getMonth() + 1) {
    comparisonDate.value = new Date(today.getTime() - 86400000).toISOString().split('T')[0]
  } else {
    comparisonDate.value = `${selectedMonth.value}-${lastDay}`
  }
})
</script>

<style lang="scss" scoped>
.optimization-report {
  padding: 20px;
}

.report-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.summary-cards {
  margin-bottom: 20px;
}

.stat-card {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border: 1px solid #2d3a4f;
  border-radius: 12px;

  :deep(.el-card__body) {
    display: flex;
    align-items: center;
    padding: 20px;
    gap: 16px;
  }

  .stat-icon {
    width: 60px;
    height: 60px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .stat-content {
    flex: 1;
  }

  .stat-value {
    font-size: 24px;
    font-weight: bold;
    color: #fff;
    margin-bottom: 4px;
  }

  .stat-label {
    font-size: 14px;
    color: #999;
    margin-bottom: 8px;
  }

  .stat-sub {
    font-size: 12px;
    color: #666;
  }

  .stat-progress {
    margin-top: 8px;
  }

  &.saving-card .stat-icon {
    background: rgba(103, 194, 58, 0.2);
    color: #67c23a;
  }

  &.achievement-card .stat-icon {
    background: rgba(64, 158, 255, 0.2);
    color: #409eff;
  }

  &.execution-card .stat-icon {
    background: rgba(230, 162, 60, 0.2);
    color: #e6a23c;
  }

  &.demand-card .stat-icon {
    background: rgba(144, 147, 153, 0.2);
    color: #909399;
  }
}

.chart-row {
  margin-bottom: 20px;
}

.chart-card {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border: 1px solid #2d3a4f;
  border-radius: 12px;

  :deep(.el-card__header) {
    background: transparent;
    border-bottom: 1px solid #2d3a4f;
    color: #fff;
    padding: 16px 20px;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}

.chart-container {
  height: 320px;
}

.metrics-grid {
  padding: 10px 0;
}

.metric-item {
  padding: 16px 0;
  border-bottom: 1px solid #2d3a4f;

  &:last-child {
    border-bottom: none;
  }

  .metric-label {
    font-size: 13px;
    color: #999;
    margin-bottom: 8px;
  }

  .metric-value {
    font-size: 20px;
    font-weight: bold;
    color: #fff;
    margin-bottom: 8px;

    &.bias-normal {
      color: #67c23a;
    }
    &.bias-low {
      color: #e6a23c;
    }
    &.bias-high {
      color: #409eff;
    }
  }

  .metric-bar {
    margin-top: 8px;
  }

  .metric-desc {
    font-size: 12px;
    color: #666;
    margin-top: 4px;
  }
}

.recommendations-card {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border: 1px solid #2d3a4f;
  border-radius: 12px;
  height: 100%;

  :deep(.el-card__header) {
    background: transparent;
    border-bottom: 1px solid #2d3a4f;
    color: #fff;
    padding: 16px 20px;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}

.recommendations-list {
  padding: 10px 0;
}

.recommendation-item {
  display: flex;
  align-items: flex-start;
  padding: 12px 0;
  border-bottom: 1px solid #2d3a4f;

  &:last-child {
    border-bottom: none;
  }

  .rec-icon {
    margin-right: 12px;
    margin-top: 2px;
    color: #e6a23c;
  }

  .rec-text {
    flex: 1;
    font-size: 14px;
    color: #ccc;
    line-height: 1.6;
  }
}
</style>
