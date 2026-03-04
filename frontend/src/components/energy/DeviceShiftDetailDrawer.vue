<template>
  <el-drawer
    v-model="drawerVisible"
    title="设备用电详情"
    direction="rtl"
    size="640px"
    :before-close="handleClose"
    class="device-shift-detail-drawer"
  >
    <template #header>
      <div class="drawer-header">
        <div class="header-title">
          <span class="device-name">{{ device?.device_name }}</span>
          <el-tag size="small" style="margin-left: 8px;">{{ getDeviceTypeText(device?.device_type) }}</el-tag>
        </div>
        <div class="header-meta" style="margin-top: 4px; color: var(--text-secondary, #909399); font-size: 13px;">
          {{ device?.device_code }} · 额定功率 {{ device?.rated_power }} kW
        </div>
      </div>
    </template>

    <div class="drawer-content" v-loading="loading">
      <!-- 关键指标卡片 -->
      <div class="metric-cards">
        <div class="metric-card">
          <div class="metric-label">负载率</div>
          <div class="metric-value">
            {{ profile ? (profile.summary.load_rate * 100).toFixed(1) : '--' }}%
          </div>
          <div class="metric-sub">平均功率/额定功率</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">峰时用电占比</div>
          <div class="metric-value peak-color">
            {{ profile ? (profile.summary.peak_energy_ratio * 100).toFixed(1) : '--' }}%
          </div>
          <div class="metric-sub">尖峰+高峰时段占总用电</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">当前可调节容量</div>
          <div class="metric-value">
            {{ device ? device.current_shiftable_power.toFixed(1) : '--' }} kW
          </div>
          <div class="metric-sub">比例 {{ device ? (device.current_ratio * 100).toFixed(0) : '--' }}%</div>
        </div>
        <div class="metric-card highlight">
          <div class="metric-label">推荐可调节容量</div>
          <div class="metric-value recommend-color">
            {{ device ? device.recommended_shiftable_power.toFixed(1) : '--' }} kW
          </div>
          <div class="metric-sub">比例 {{ device ? (device.recommended_ratio * 100).toFixed(0) : '--' }}%</div>
        </div>
      </div>

      <!-- 24小时典型日功率曲线图 -->
      <div class="chart-section">
        <div class="section-header">
          <div class="section-title">
            {{ chartMode === 'trend' ? `${profileDays}天功率趋势` : '24小时典型日功率曲线' }}
          </div>
          <el-radio-group v-model="profileDays" size="small" @change="reloadProfile">
            <el-radio-button :value="30">30天</el-radio-button>
            <el-radio-button :value="90">90天</el-radio-button>
          </el-radio-group>
        </div>
        <div class="chart-info" v-if="trendData">
          基于过去 {{ trendData.days }} 天历史数据，共 {{ trendData.trend_data.length }} 个数据点
        </div>
        <div ref="chartRef" class="power-chart"></div>
      </div>

      <!-- 约束条件可视化 -->
      <div class="constraints-section" v-if="device?.calculation_details">
        <div class="section-title">约束条件分析</div>

        <!-- 错误提示：calculation_details 只有 error 字段时 -->
        <el-alert
          v-if="device.calculation_details.error"
          type="warning"
          :closable="false"
          show-icon
          style="margin-bottom: 12px;"
        >
          <template #title>无法计算约束条件</template>
          {{ device.calculation_details.error }}。请在设备管理中补充额定功率后重新分析。
        </el-alert>

        <!-- 警告信息 -->
        <el-alert
          v-if="device.calculation_details.warnings && device.calculation_details.warnings.length > 0"
          type="warning"
          :closable="false"
          show-icon
          style="margin-bottom: 12px;"
        >
          <template #title>注意事项</template>
          <ul style="margin: 0; padding-left: 20px;">
            <li v-for="(warning, idx) in device.calculation_details.warnings" :key="idx">
              {{ warning }}
            </li>
          </ul>
        </el-alert>

        <!-- 限制因素说明 -->
        <div v-if="device.calculation_details.limiting_factor" style="margin-bottom: 12px; padding: 8px; background: rgba(24,144,255,0.1); border-radius: 4px; font-size: 13px;">
          <strong>限制因素：</strong>
          <span style="color: #1890ff;">
            {{ device.calculation_details.limiting_factor === 'temperature' ? '温度约束' : 
               device.calculation_details.limiting_factor === 'redundancy' ? '冗余约束' :
               device.calculation_details.limiting_factor === 'pue' ? 'PUE约束' : '设备特性约束' }}
          </span>
        </div>

        <!-- 正常约束条件列表 -->
        <div class="constraint-list" v-if="constraintItems.length > 0">
          <div
            v-for="(c, idx) in constraintItems"
            :key="idx"
            class="constraint-item"
            :class="{ 'is-binding': c.isBinding }"
          >
            <div class="constraint-header">
              <span class="constraint-name">
                {{ c.name }}
                <el-tag v-if="c.isBinding" type="danger" size="small" style="margin-left: 6px;">决定性约束</el-tag>
              </span>
              <span class="constraint-value">{{ (c.value * 100).toFixed(1) }}%</span>
            </div>
            <el-progress
              :percentage="Math.min(c.value * 100, 100)"
              :color="c.isBinding ? '#ff4d4f' : '#1890ff'"
              :stroke-width="10"
              :show-text="false"
            />
            <div class="constraint-desc">{{ c.description }}</div>
          </div>
        </div>
      </div>
    </div> <!-- end drawer-content -->

    <!-- 底部操作按钮 -->
    <template #footer>
      <div class="drawer-footer">
        <el-button @click="handleClose">关闭</el-button>
        <el-button
          v-if="device?.has_change"
          type="primary"
          @click="handleAcceptRatio"
        >
          使用推荐值 ({{ device ? (device.recommended_ratio * 100).toFixed(0) : '' }}%)
        </el-button>
      </div>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, watch, computed, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import {
  getDeviceTypicalDayProfile,
  getDevicePowerTrend,
  type TypicalDayProfileResponse,
  type PowerTrendResponse,
type RatioRecommendation
} from '@/api/modules/energy'

const props = defineProps<{
  visible: boolean
  device: RatioRecommendation | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'accept-ratio', device: RatioRecommendation): void
}>()

const drawerVisible = computed({
  get: () => {
    console.log('[DeviceShiftDetailDrawer] drawerVisible get:', props.visible)
    return props.visible
  },
  set: () => {
    console.log('[DeviceShiftDetailDrawer] drawerVisible set - emitting close')
    emit('close')
  }
})

const loading = ref(false)
const profile = ref<TypicalDayProfileResponse | null>(null)
const trendData = ref<PowerTrendResponse | null>(null)
const chartMode = ref<'typical' | 'trend'>('trend')  // 默认显示趋势图
const profileDays = ref(30)
const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

const DEVICE_TYPE_MAP: Record<string, string> = {
  PUMP: '水泵', AC: '空调', HVAC: '暖通', LIGHTING: '照明',
  CHILLER: '冷机', COOLING_TOWER: '冷却塔', AHU: '空气处理机组',
  COMPRESSOR: '压缩机', UPS: 'UPS', IT_SERVER: 'IT服务器',
  IT_STORAGE: 'IT存储', MAIN: '总进线', PDU: 'PDU', IT: 'IT设备'
}

function getDeviceTypeText(type?: string) {
  return DEVICE_TYPE_MAP[(type || '').toUpperCase()] || type || '--'
}

// 约束条件计算
const constraintItems = computed(() => {
  const details = props.device?.calculation_details
  if (!details?.constraints) return []

  const constraints = details.constraints
  const limitingFactor = details.limiting_factor

  const items = []
  
  // 温度约束
  if (constraints.temperature && constraints.temperature.max_ratio !== null) {
    items.push({
      name: '温度约束',
      value: constraints.temperature.max_ratio,
      description: constraints.temperature.reason || '确保机柜温度不超限（ASHRAE 18-27℃）',
      isBinding: limitingFactor === 'temperature'
    })
  }
  
  // 冗余约束
  if (constraints.redundancy && constraints.redundancy.max_ratio !== null) {
    items.push({
      name: '冗余约束',
      value: constraints.redundancy.max_ratio,
      description: constraints.redundancy.reason || '确保N+1冗余，设备故障时系统仍可运行',
      isBinding: limitingFactor === 'redundancy'
    })
  }
  
  // PUE 约束
  if (constraints.pue && constraints.pue.max_ratio !== null) {
    items.push({
      name: 'PUE约束',
      value: constraints.pue.max_ratio,
      description: constraints.pue.reason || '保持数据中心能效在合理范围（1.2-2.0）',
      isBinding: limitingFactor === 'pue'
    })
  }
  
  // 设备特性约束
  if (constraints.device && constraints.device.max_ratio !== null) {
    items.push({
      name: '设备特性约束',
      value: constraints.device.max_ratio,
      description: constraints.device.reason || '设备启停特性、最小运行时间等',
      isBinding: limitingFactor === 'device'
    })
  }

  return items
})

// 颜色常量
const PERIOD_COLORS: Record<string, string> = {
  sharp: 'rgba(114,46,209,0.15)',
  peak: 'rgba(245,34,45,0.15)',
  flat: 'rgba(250,173,20,0.10)',
  valley: 'rgba(82,196,26,0.15)',
  deep_valley: 'rgba(24,144,255,0.15)'
}

const PERIOD_LABELS: Record<string, string> = {
  sharp: '尖峰', peak: '高峰', flat: '平段',
  valley: '低谷', deep_valley: '深谷'
}

function buildChart() {
  if (!chartRef.value || !profile.value) return

  if (chart) {
    chart.dispose()
  }

  chart = echarts.init(chartRef.value)

  const data = profile.value.hourly_profile
  const ratedPower = profile.value.rated_power
  const device = props.device

  const hours = data.map(d => `${d.hour}:00`)
  const avgPowers = data.map(d => d.avg_power)
  const maxPowers = data.map(d => d.max_power)
  const minPowers = data.map(d => d.min_power)

  // 可转移功率区域: 从 min_power 到 min_power + shiftable_power
  const shiftablePower = device ? device.recommended_shiftable_power : 0
  const shiftUpper = data.map(d => Math.min(d.min_power + shiftablePower, ratedPower))

  // 时段背景 markArea
  const markAreas: any[] = []
  let currentPeriod = data[0]?.period_type
  let startHour = 0

  for (let i = 1; i <= 24; i++) {
    const thisPeriod = i < 24 ? data[i].period_type : null
    if (thisPeriod !== currentPeriod || i === 24) {
      markAreas.push([
        {
          xAxis: `${startHour}:00`,
          itemStyle: { color: PERIOD_COLORS[currentPeriod] || 'transparent' }
        },
        { xAxis: i < 24 ? `${i}:00` : `${23}:00` }
      ])
      if (i < 24) {
        currentPeriod = thisPeriod!
        startHour = i
      }
    }
  }

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        if (!Array.isArray(params) || params.length === 0) return ''
        const hour = params[0].axisValue
        const point = data[params[0].dataIndex]
        const periodLabel = PERIOD_LABELS[point.period_type] || point.period_type
        let html = `<b>${hour}</b> (${periodLabel})<br/>`
        params.forEach((p: any) => {
          if (p.seriesName && p.value !== undefined) {
            html += `${p.marker}${p.seriesName}: ${p.value.toFixed(2)} kW<br/>`
          }
        })
        return html
      }
    },
    legend: {
      data: ['平均功率', '功率包络(最大)', '功率包络(最小)', '额定功率', '可转移上限'],
      bottom: 0,
      textStyle: { fontSize: 11 }
    },
    grid: { top: 30, right: 20, bottom: 50, left: 60 },
    xAxis: {
      type: 'category',
      data: hours,
      axisLabel: {
        interval: 2,
        fontSize: 11
      }
    },
    yAxis: {
      type: 'value',
      name: '功率 (kW)',
      nameTextStyle: { fontSize: 11 },
      axisLabel: { fontSize: 11 }
    },
    series: [
      // 功率包络区域 - min 到 max
      {
        name: '功率包络(最大)',
        type: 'line',
        data: maxPowers,
        lineStyle: { width: 0 },
        symbol: 'none',
        stack: 'envelope',
        areaStyle: { color: 'rgba(24,144,255,0.15)' }
      },
      {
        name: '功率包络(最小)',
        type: 'line',
        data: minPowers,
        lineStyle: { width: 0 },
        symbol: 'none',
        stack: 'envelope-base'
      },
      // 平均功率曲线
      {
        name: '平均功率',
        type: 'line',
        data: avgPowers,
        lineStyle: { color: '#1890ff', width: 2 },
        itemStyle: { color: '#1890ff' },
        symbol: 'circle',
        symbolSize: 4,
        markArea: { silent: true, data: markAreas }
      },
      // 额定功率参考线
      {
        name: '额定功率',
        type: 'line',
        data: hours.map(() => ratedPower),
        lineStyle: { color: '#ff4d4f', width: 1.5, type: 'dashed' },
        symbol: 'none',
        itemStyle: { color: '#ff4d4f' }
      },
      // 可转移功率区域
      {
        name: '可转移上限',
        type: 'line',
        data: shiftUpper,
        lineStyle: { color: 'rgba(82,196,26,0.6)', width: 1, type: 'dashed' },
        symbol: 'none',
        itemStyle: { color: '#52c41a' },
        areaStyle: {
          color: 'rgba(82,196,26,0.2)',
          origin: minPowers as any
        }
      }
    ]
  }

  chart.setOption(option)
}

// 构建趋势图表（30/90天）
function buildTrendChart() {
  if (!chartRef.value || !trendData.value) return

  if (chart) {
    chart.dispose()
  }

  chart = echarts.init(chartRef.value)

  const data = trendData.value.trend_data
  const ratedPower = trendData.value.rated_power

  const dates = data.map(d => d.date.substring(5))  // 只显示 MM-DD
  const avgPowers = data.map(d => d.avg_power)
  const maxPowers = data.map(d => d.max_power)
  const minPowers = data.map(d => d.min_power)

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        if (!Array.isArray(params) || params.length === 0) return ''
        const date = params[0].axisValue
        const point = data[params[0].dataIndex]
        let html = `<b>${point.date}</b><br/>`
        html += `平均功率: ${point.avg_power.toFixed(2)} kW<br/>`
        html += `最大功率: ${point.max_power.toFixed(2)} kW<br/>`
        html += `最小功率: ${point.min_power.toFixed(2)} kW<br/>`
        html += `总能耗: ${point.energy.toFixed(2)} kWh`
        return html
      }
    },
    legend: {
      data: ['平均功率', '功率包络(最大)', '功率包络(最小)', '额定功率'],
      bottom: 0,
      textStyle: { fontSize: 11 }
    },
    grid: { top: 30, right: 20, bottom: 50, left: 60 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: {
        interval: Math.floor(dates.length / 10),  // 自动调整间隔
        fontSize: 11,
        rotate: 45
      }
    },
    yAxis: {
      type: 'value',
      name: '功率 (kW)',
      nameTextStyle: { fontSize: 11 },
      axisLabel: { fontSize: 11 }
    },
    series: [
      // 功率包络区域
      {
        name: '功率包络(最大)',
        type: 'line',
        data: maxPowers,
        lineStyle: { width: 0 },
        symbol: 'none',
        stack: 'envelope',
        areaStyle: { color: 'rgba(24,144,255,0.15)' }
      },
      {
        name: '功率包络(最小)',
        type: 'line',
        data: minPowers,
        lineStyle: { width: 0 },
        symbol: 'none',
        stack: 'envelope-base'
      },
      // 平均功率曲线
      {
        name: '平均功率',
        type: 'line',
        data: avgPowers,
        lineStyle: { color: '#1890ff', width: 2 },
        itemStyle: { color: '#1890ff' },
        symbol: 'circle',
        symbolSize: 3
      },
      // 额定功率参考线
      {
        name: '额定功率',
        type: 'line',
        data: dates.map(() => ratedPower),
        lineStyle: { color: '#ff4d4f', width: 1.5, type: 'dashed' },
        symbol: 'none',
        itemStyle: { color: '#ff4d4f' }
      }
    ]
  }

  chart.setOption(option)
}


// 重新加载功率数据（切换天数时）
async function reloadProfile() {
  if (!props.device) return
  loading.value = true
  try {
    // 调用新的趋势 API
    const res = await getDevicePowerTrend(props.device.device_id, profileDays.value)
    if (res.code === 0 && res.data) {
      trendData.value = res.data
      await nextTick()
      buildTrendChart()
    }
  } catch (e) {
    console.error('加载设备功率趋势失败:', e)
  } finally {
    loading.value = false
  }
}

// 监听设备变化，加载数据
watch(() => props.device, async (newDevice) => {
  if (!newDevice) {
    trendData.value = null
    return
  }

  loading.value = true
  try {
    const res = await getDevicePowerTrend(newDevice.device_id, profileDays.value)
    if (res.code === 0 && res.data) {
      trendData.value = res.data
      await nextTick()
      buildTrendChart()
    }
  } catch (e) {
    console.error('加载设备功率趋势失败:', e)
  } finally {
    loading.value = false
  }
}, { immediate: true })

// resize
watch(() => props.visible, (v) => {
  if (v) {
    nextTick(() => {
      chart?.resize()
    })
  }
})

function handleClose() {
  emit('close')
}

function handleAcceptRatio() {
  if (props.device) {
    emit('accept-ratio', props.device)
  }
}

onUnmounted(() => {
  chart?.dispose()
  chart = null
})
</script>

<style scoped lang="scss">
.drawer-header {
  .header-title {
    display: flex;
    align-items: center;
    .device-name {
      font-size: 16px;
      font-weight: 600;
      color: var(--text-primary);
    }
  }
}

.drawer-content {
  padding: 0 4px;
}

.metric-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 20px;

  .metric-card {
    background: var(--bg-tertiary, rgba(17, 34, 64, 0.8));
    border-radius: 8px;
    padding: 12px;
    text-align: center;
    border: 1px solid var(--border-color);
    transition: border-color 0.3s;

    &.highlight {
      background: rgba(103, 194, 58, 0.15);
      border-color: rgba(103, 194, 58, 0.5);
    }

    .metric-label {
      font-size: 12px;
      color: var(--text-secondary);
      margin-bottom: 6px;
    }

    .metric-value {
      font-size: 20px;
      font-weight: 700;
      color: var(--text-primary);
      line-height: 1.3;

      &.peak-color { color: #f56c6c; }
      &.recommend-color { color: #67c23a; }
    }

    .metric-sub {
      font-size: 11px;
      color: var(--text-placeholder);
      margin-top: 4px;
    }
  }
}

.chart-section {
  margin-bottom: 20px;

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
  }

  .section-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .chart-info {
    font-size: 12px;
    color: var(--text-secondary);
    margin-bottom: 8px;
  }

  .power-chart {
    width: 100%;
    height: 320px;
  }
}

.constraints-section {
  .section-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 12px;
  }

  .constraint-list {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .constraint-item {
    padding: 10px 12px;
    border-radius: 6px;
    background: var(--bg-tertiary, rgba(17, 34, 64, 0.8));
    border: 1px solid var(--border-color);
    transition: all 0.3s;

    &.is-binding {
      background: rgba(245, 108, 108, 0.15);
      border-color: rgba(245, 108, 108, 0.5);
    }

    .constraint-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 6px;
    }

    .constraint-name {
      font-size: 13px;
      font-weight: 500;
      color: var(--text-primary);
    }

    .constraint-value {
      font-size: 14px;
      font-weight: 600;
      color: var(--text-regular);
    }

    .constraint-desc {
      font-size: 11px;
      color: var(--text-secondary);
      margin-top: 6px;
    }
  }
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
