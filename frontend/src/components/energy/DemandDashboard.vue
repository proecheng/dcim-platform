<template>
  <div class="demand-dashboard">
    <!-- 实时状态卡片 -->
    <el-row :gutter="20" class="status-row">
      <el-col :span="8">
        <el-card shadow="hover" class="status-card" :class="statusClass">
          <div class="gauge-container">
            <div ref="gaugeRef" class="gauge-chart"></div>
          </div>
          <div class="status-info">
            <div class="main-value">
              <span class="value">{{ status?.window_avg_power || 0 }}</span>
              <span class="unit">kW</span>
            </div>
            <div class="label">15分钟平均功率</div>
            <div class="status-tag">
              <el-tag :type="alertTagType" size="large">
                {{ alertText }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card shadow="hover" class="info-card">
          <template #header>需量目标</template>
          <div class="info-grid">
            <div class="info-item">
              <span class="label">申报需量</span>
              <span class="value">{{ status?.declared_demand || 0 }} kW</span>
            </div>
            <div class="info-item">
              <span class="label">当前功率</span>
              <span class="value">{{ status?.current_power || 0 }} kW</span>
            </div>
            <div class="info-item">
              <span class="label">利用率</span>
              <span class="value" :class="utilizationClass">{{ status?.utilization_ratio || 0 }}%</span>
            </div>
            <div class="info-item">
              <span class="label">剩余容量</span>
              <span class="value">{{ status?.remaining_capacity || 0 }} kW</span>
            </div>
          </div>
          <div class="trend-indicator">
            <span>趋势：</span>
            <el-icon v-if="status?.trend === 'up'" color="#f5222d"><Top /></el-icon>
            <el-icon v-else-if="status?.trend === 'down'" color="#52c41a"><Bottom /></el-icon>
            <el-icon v-else color="#faad14"><Minus /></el-icon>
            <span>{{ trendText }}</span>
          </div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card shadow="hover" class="info-card">
          <template #header>本月统计</template>
          <div class="info-grid">
            <div class="info-item">
              <span class="label">本月最大需量</span>
              <span class="value highlight">{{ status?.month_max_demand || 0 }} kW</span>
            </div>
            <div class="info-item">
              <span class="label">发生时间</span>
              <span class="value small">{{ status?.month_max_time || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="label">更新时间</span>
              <span class="value small">{{ status?.timestamp || '-' }}</span>
            </div>
          </div>
          <el-button type="primary" text @click="refresh" :loading="loading">
            <el-icon><Refresh /></el-icon> 刷新数据
          </el-button>
        </el-card>
      </el-col>
    </el-row>

    <!-- 预警信息 -->
    <div class="alerts-section" v-if="alerts.length > 0">
      <el-alert
        v-for="(alert, idx) in alerts"
        :key="idx"
        :type="alert.level === 'critical' ? 'error' : 'warning'"
        :title="alert.message"
        :closable="false"
        show-icon
        class="alert-item"
      >
        <template #default>
          <div class="alert-detail">
            <span>建议措施：{{ alert.suggestion }}</span>
          </div>
        </template>
      </el-alert>
    </div>

    <!-- 实时曲线 -->
    <el-card shadow="hover" class="curve-card">
      <template #header>
        <div class="card-header">
          <span>实时功率曲线</span>
          <el-radio-group v-model="curveHours" size="small" @change="loadCurve">
            <el-radio-button :value="1">1小时</el-radio-button>
            <el-radio-button :value="4">4小时</el-radio-button>
            <el-radio-button :value="8">8小时</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      <div ref="curveRef" class="curve-chart" v-loading="loadingCurve"></div>
    </el-card>

    <!-- 月度电费汇总 -->
    <el-row :gutter="20" class="monthly-row">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>当月电费构成</template>
          <div class="monthly-summary" v-if="monthlySummary">
            <div class="total-cost">
              <span class="label">总电费</span>
              <span class="value">¥ {{ monthlySummary.total_cost.toLocaleString() }}</span>
            </div>
            <div class="cost-breakdown">
              <div class="cost-item">
                <span class="label">电量电费</span>
                <span class="value">¥ {{ monthlySummary.energy_cost.toLocaleString() }}</span>
                <span class="percent">{{ ((monthlySummary.energy_cost / monthlySummary.total_cost) * 100).toFixed(1) }}%</span>
              </div>
              <div class="cost-item">
                <span class="label">需量电费</span>
                <span class="value">¥ {{ monthlySummary.demand_cost.toLocaleString() }}</span>
                <span class="percent">{{ ((monthlySummary.demand_cost / monthlySummary.total_cost) * 100).toFixed(1) }}%</span>
              </div>
              <div class="cost-item">
                <span class="label">力调电费</span>
                <span class="value" :class="monthlySummary.power_factor_adjustment < 0 ? 'positive' : 'negative'">
                  {{ monthlySummary.power_factor_adjustment >= 0 ? '+' : '' }}¥ {{ monthlySummary.power_factor_adjustment.toLocaleString() }}
                </span>
              </div>
            </div>
            <div class="saving-info" v-if="monthlySummary.optimized_saving > 0">
              <el-icon><TrendCharts /></el-icon>
              <span>本月优化节省：<strong>¥ {{ monthlySummary.optimized_saving.toLocaleString() }}</strong></span>
            </div>
          </div>
          <el-empty v-else description="暂无数据" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>分时用电分布</template>
          <div ref="pieRef" class="pie-chart" v-loading="loadingMonthly"></div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { Top, Bottom, Minus, Refresh, TrendCharts } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import {
  getRealtimeStatus,
  getRealtimeAlerts,
  getRealtimeCurve,
  getCurrentMonthSummary,
  getAlertColor,
  getAlertText,
  getPeriodColor,
  getPeriodName,
  type DemandStatus,
  type DemandAlert,
  type MonthlyBillSummary
} from '@/api/modules/monitoring'

const loading = ref(false)
const loadingCurve = ref(false)
const loadingMonthly = ref(false)

const status = ref<DemandStatus | null>(null)
const alerts = ref<DemandAlert[]>([])
const monthlySummary = ref<MonthlyBillSummary | null>(null)
const curveHours = ref(4)

const gaugeRef = ref<HTMLElement>()
const curveRef = ref<HTMLElement>()
const pieRef = ref<HTMLElement>()

let gaugeChart: echarts.ECharts | null = null
let curveChart: echarts.ECharts | null = null
let pieChart: echarts.ECharts | null = null
let refreshTimer: ReturnType<typeof setInterval> | null = null

// 计算属性
const statusClass = computed(() => {
  if (!status.value) return ''
  return `status-${status.value.alert_level}`
})

const alertTagType = computed(() => {
  if (!status.value) return 'success'
  switch (status.value.alert_level) {
    case 'critical': return 'danger'
    case 'warning': return 'warning'
    default: return 'success'
  }
})

const alertText = computed(() => {
  if (!status.value) return '正常'
  return getAlertText(status.value.alert_level)
})

const utilizationClass = computed(() => {
  if (!status.value) return ''
  if (status.value.utilization_ratio >= 100) return 'critical'
  if (status.value.utilization_ratio >= 90) return 'warning'
  return ''
})

const trendText = computed(() => {
  if (!status.value) return '-'
  switch (status.value.trend) {
    case 'up': return '上升'
    case 'down': return '下降'
    default: return '平稳'
  }
})

onMounted(async () => {
  await loadAllData()
  // 每30秒自动刷新
  refreshTimer = setInterval(async () => {
    await loadStatus()
    await loadAlerts()
  }, 30000)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
  gaugeChart?.dispose()
  curveChart?.dispose()
  pieChart?.dispose()
})

async function loadAllData() {
  await Promise.all([
    loadStatus(),
    loadAlerts(),
    loadCurve(),
    loadMonthlySummary()
  ])
}

async function refresh() {
  loading.value = true
  try {
    await loadAllData()
  } finally {
    loading.value = false
  }
}

async function loadStatus() {
  try {
    const res = await getRealtimeStatus()
    if (res.data) {
      status.value = res.data
      await nextTick()
      renderGauge()
    }
  } catch (e) {
    console.error('加载状态失败', e)
  }
}

async function loadAlerts() {
  try {
    const res = await getRealtimeAlerts()
    alerts.value = res.data || []
  } catch (e) {
    console.error('加载预警失败', e)
  }
}

async function loadCurve() {
  loadingCurve.value = true
  try {
    const res = await getRealtimeCurve(curveHours.value)
    if (res.data) {
      await nextTick()
      renderCurve(res.data.data, res.data.demand_target)
    }
  } catch (e) {
    console.error('加载曲线失败', e)
  } finally {
    loadingCurve.value = false
  }
}

async function loadMonthlySummary() {
  loadingMonthly.value = true
  try {
    const res = await getCurrentMonthSummary()
    if (res.data) {
      monthlySummary.value = res.data
      await nextTick()
      renderPie()
    }
  } catch (e) {
    console.error('加载月度数据失败', e)
  } finally {
    loadingMonthly.value = false
  }
}

function renderGauge() {
  if (!gaugeRef.value || !status.value) return

  if (gaugeChart) {
    gaugeChart.dispose()
  }
  gaugeChart = echarts.init(gaugeRef.value)

  const utilization = status.value.utilization_ratio
  const color = getAlertColor(status.value.alert_level)

  const option: echarts.EChartsOption = {
    series: [
      {
        type: 'gauge',
        startAngle: 200,
        endAngle: -20,
        min: 0,
        max: 120,
        splitNumber: 12,
        itemStyle: {
          color: color
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
            color: [[1, 'rgba(255,255,255,0.1)']]
          }
        },
        axisTick: {
          show: false
        },
        splitLine: {
          show: false
        },
        axisLabel: {
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
          offsetCenter: [0, '0%'],
          fontSize: 28,
          fontWeight: 'bolder',
          formatter: '{value}%',
          color: color
        },
        data: [
          {
            value: Math.min(utilization, 120)
          }
        ]
      }
    ]
  }

  gaugeChart.setOption(option)
}

function renderCurve(data: any[], demandTarget: number) {
  if (!curveRef.value) return

  if (curveChart) {
    curveChart.dispose()
  }
  curveChart = echarts.init(curveRef.value)

  const times = data.map(d => d.timestamp)
  const powers = data.map(d => d.power)

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const p = params[0]
        const point = data[p.dataIndex]
        const alertText = getAlertText(point.alert_level)
        return `${point.full_timestamp}<br/>
                功率: ${point.power} kW<br/>
                利用率: ${point.utilization}%<br/>
                状态: ${alertText}`
      }
    },
    grid: {
      top: 40,
      right: 30,
      bottom: 40,
      left: 60
    },
    xAxis: {
      type: 'category',
      data: times,
      axisLabel: {
        color: 'rgba(255,255,255,0.65)',
        fontSize: 11
      },
      axisLine: {
        lineStyle: { color: 'rgba(255,255,255,0.15)' }
      }
    },
    yAxis: {
      type: 'value',
      name: 'kW',
      nameTextStyle: {
        color: 'rgba(255,255,255,0.65)'
      },
      axisLabel: {
        color: 'rgba(255,255,255,0.65)',
        fontSize: 11
      },
      splitLine: {
        lineStyle: { color: 'rgba(255,255,255,0.1)' }
      }
    },
    series: [
      {
        name: '功率',
        type: 'line',
        data: powers,
        smooth: true,
        symbol: 'none',
        lineStyle: {
          width: 2,
          color: '#1890ff'
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(24,144,255,0.4)' },
            { offset: 1, color: 'rgba(24,144,255,0.05)' }
          ])
        },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: {
            color: '#f5222d',
            type: 'dashed',
            width: 2
          },
          data: [
            {
              yAxis: demandTarget,
              label: {
                formatter: `需量目标 ${demandTarget}kW`,
                position: 'end',
                color: '#f5222d'
              }
            },
            {
              yAxis: demandTarget * 0.9,
              lineStyle: { color: '#faad14' },
              label: {
                formatter: '90%预警线',
                position: 'end',
                color: '#faad14'
              }
            }
          ]
        }
      }
    ]
  }

  curveChart.setOption(option)

  // 响应式
  new ResizeObserver(() => curveChart?.resize()).observe(curveRef.value)
}

function renderPie() {
  if (!pieRef.value || !monthlySummary.value) return

  if (pieChart) {
    pieChart.dispose()
  }
  pieChart = echarts.init(pieRef.value)

  const breakdown = monthlySummary.value.cost_breakdown.energy_by_period
  const data = Object.entries(breakdown).map(([key, value]) => ({
    name: getPeriodName(key),
    value: value,
    itemStyle: { color: getPeriodColor(key) }
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
      textStyle: {
        color: 'rgba(255,255,255,0.85)'
      }
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
        label: {
          show: false
        },
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

  pieChart.setOption(option)

  new ResizeObserver(() => pieChart?.resize()).observe(pieRef.value)
}
</script>

<style scoped lang="scss">
.demand-dashboard {
  .status-row {
    margin-bottom: 20px;
  }

  .status-card {
    text-align: center;
    transition: all 0.3s;

    &.status-critical {
      border-color: #f5222d;
      box-shadow: 0 0 20px rgba(245, 34, 45, 0.3);
    }

    &.status-warning {
      border-color: #faad14;
      box-shadow: 0 0 20px rgba(250, 173, 20, 0.3);
    }

    .gauge-container {
      height: 160px;
    }

    .gauge-chart {
      height: 100%;
      width: 100%;
    }

    .status-info {
      .main-value {
        .value {
          font-size: 32px;
          font-weight: bold;
          color: var(--text-primary);
        }
        .unit {
          font-size: 14px;
          color: var(--text-secondary);
          margin-left: 4px;
        }
      }

      .label {
        font-size: 12px;
        color: var(--text-secondary);
        margin: 8px 0;
      }

      .status-tag {
        margin-top: 12px;
      }
    }
  }

  .info-card {
    height: 100%;

    .info-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;

      .info-item {
        display: flex;
        flex-direction: column;
        gap: 4px;

        .label {
          font-size: 12px;
          color: var(--text-secondary);
        }

        .value {
          font-size: 18px;
          font-weight: 600;
          color: var(--text-primary);

          &.small {
            font-size: 13px;
          }

          &.highlight {
            color: #1890ff;
          }

          &.critical {
            color: #f5222d;
          }

          &.warning {
            color: #faad14;
          }
        }
      }
    }

    .trend-indicator {
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid rgba(255, 255, 255, 0.1);
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
      color: var(--text-secondary);
    }
  }

  .alerts-section {
    margin-bottom: 20px;

    .alert-item {
      margin-bottom: 12px;

      .alert-detail {
        font-size: 13px;
        margin-top: 8px;
      }
    }
  }

  .curve-card {
    margin-bottom: 20px;

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .curve-chart {
      height: 300px;
    }
  }

  .monthly-row {
    .monthly-summary {
      .total-cost {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-bottom: 16px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        margin-bottom: 16px;

        .label {
          font-size: 14px;
          color: var(--text-secondary);
        }

        .value {
          font-size: 28px;
          font-weight: bold;
          color: #1890ff;
        }
      }

      .cost-breakdown {
        .cost-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 8px 0;

          .label {
            flex: 1;
            color: var(--text-secondary);
          }

          .value {
            flex: 1;
            text-align: right;
            font-weight: 500;

            &.positive {
              color: #52c41a;
            }

            &.negative {
              color: #f5222d;
            }
          }

          .percent {
            width: 60px;
            text-align: right;
            color: var(--text-secondary);
            font-size: 12px;
          }
        }
      }

      .saving-info {
        margin-top: 16px;
        padding: 12px;
        background: rgba(82, 196, 26, 0.1);
        border-radius: 8px;
        display: flex;
        align-items: center;
        gap: 8px;
        color: #52c41a;

        strong {
          font-size: 18px;
        }
      }
    }

    .pie-chart {
      height: 280px;
    }
  }
}
</style>
