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
          {{ device?.device_code }} · {{ device?.load_subtype_label || getLoadSubtypeText(device?.load_subtype) }} · 额定功率 {{ device?.rated_power }} kW
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
        <!-- 空数据提示 -->
        <el-empty v-if="trendData && trendData.trend_data.length === 0" description="该设备暂无历史数据" :image-size="120" />
        <div v-else ref="chartRef" class="power-chart"></div>
      </div>

      <!-- 约束条件可视化 -->
      <div class="constraints-section" v-if="device?.calculation_details">
        <div class="section-title">约束条件分析</div>
        <div v-if="device.control_modes && device.control_modes.length > 0" class="control-tags">
          <el-tag v-for="mode in device.control_modes" :key="mode" size="small" type="info">
            {{ getControlText(mode) }}
          </el-tag>
        </div>

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
            {{ getLimitingFactorText(device.calculation_details.limiting_factor) }}
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

        <div v-if="device.calculation_details.cooling_strategy" class="cooling-strategy">
          <div class="section-subtitle">水冷/蓄冷执行策略</div>
          <div class="strategy-summary">
            <span>策略版本 {{ device.calculation_details.cooling_strategy.version }}</span>
            <span>推荐削峰 {{ device.calculation_details.cooling_strategy.recommended_shift_kw.toFixed(1) }} kW</span>
          </div>
          <div class="strategy-steps">
            <div
              v-for="step in device.calculation_details.cooling_strategy.steps"
              :key="`${step.phase}-${step.period}`"
              class="strategy-step"
            >
              <div class="strategy-step-head">
                <el-tag size="small">{{ step.period }}</el-tag>
                <strong>{{ step.action }}</strong>
              </div>
              <div class="strategy-step-target">{{ step.target }}</div>
              <div class="strategy-step-controls" v-if="step.controls && step.controls.length">
                <el-tag v-for="mode in step.controls" :key="`${step.phase}-${mode}`" size="small" type="info">
                  {{ getControlText(mode) }}
                </el-tag>
              </div>
            </div>
          </div>
          <div
            v-if="device.calculation_details.cooling_strategy.storage_metrics && Object.keys(device.calculation_details.cooling_strategy.storage_metrics).length"
            class="strategy-metrics"
          >
            <div
              v-for="(value, key) in device.calculation_details.cooling_strategy.storage_metrics"
              :key="key"
              class="strategy-metric"
            >
              <span>{{ getStrategyMetricText(key) }}</span>
              <strong>{{ Number(value).toFixed(2) }}</strong>
            </div>
          </div>
          <div v-if="device.calculation_details.cooling_strategy.formulas?.length" class="strategy-formulas">
            <div
              v-for="formula in device.calculation_details.cooling_strategy.formulas"
              :key="formula.name"
              class="strategy-formula"
            >
              <div class="formula-title">{{ formula.name }}</div>
              <code>{{ formula.expression }}</code>
              <div class="formula-meaning">{{ formula.meaning }}</div>
            </div>
          </div>
          <div v-if="device.calculation_details.cooling_strategy.interlocks?.length" class="strategy-interlocks">
            <div class="interlock-title">执行联锁</div>
            <ul>
              <li v-for="item in device.calculation_details.cooling_strategy.interlocks" :key="item">{{ item }}</li>
            </ul>
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

function getLoadSubtypeText(subtype?: string) {
  const map: Record<string, string> = {
    row_ac: '行级/微模块空调',
    cabinet_ac: '柜类空调',
    room_ac: '房间级空调',
    chilled_water_terminal: '冷冻水末端',
    water_cooled_chiller: '大型水冷冷机',
    pump_vfd: '变频水泵',
    cooling_tower: '冷却塔',
    thermal_storage: '蓄冷系统',
    lighting: '照明',
    ups: 'UPS',
    other: '其他'
  }
  return subtype ? (map[subtype] || subtype) : '--'
}

function getControlText(mode: string) {
  const map: Record<string, string> = {
    power_switch: '开关机控制',
    temperature_setpoint: '温度设定',
    humidity_setpoint: '湿度设定',
    supply_air_temperature: '送风温度',
    return_air_temperature: '回风温度',
    chilled_water_supply_temperature: '冷冻水供水温度',
    chilled_water_return_temperature: '冷冻水回水温度',
    chilled_water_valve: '冷冻水阀门',
    fan_speed: '风机转速',
    indoor_fan_output: '室内风机输出',
    compressor_frequency: '压缩机频率',
    cooling_output: '制冷输出',
    pump_frequency: '水泵变频',
    flow_rate: '水流量',
    cooling_tower_fan: '冷却塔风机',
    storage_charge: '蓄冷充冷',
    storage_discharge: '蓄冷放冷',
    storage_soc: '蓄冷余量',
    brightness: '照明亮度'
  }
  return map[mode] || mode
}

function getLimitingFactorText(factor?: string) {
  const map: Record<string, string> = {
    minimum_power: '最低运行约束',
    load_variability: '波动空间约束',
    peak_window: '峰时转移约束',
    control_capability: '控制能力约束',
    thermal_storage: '蓄冷能力约束',
    device: '设备安全上限',
    temperature: '温度约束',
    redundancy: '冗余约束',
    pue: 'PUE约束'
  }
  return factor ? (map[factor] || factor) : '--'
}

function getStrategyMetricText(key: string) {
  const map: Record<string, string> = {
    usable_cooling_kwh: '可用蓄冷量(kWh)',
    discharge_kwth: '峰时放冷(kWth)',
    charge_kwth: '谷时充冷(kWth)',
    equivalent_reduction_kw: '等效削峰(kW)',
    equivalent_ratio: '等效比例',
    recommended_kw: '推荐功率(kW)',
    peak_duration_hours: '峰时持续(h)',
    charge_duration_hours: '充冷持续(h)'
  }
  return map[key] || key
}

// 约束条件计算
const constraintItems = computed(() => {
  const details = props.device?.calculation_details
  if (!details?.constraints) return []

  const constraints = details.constraints
  const limitingFactor = details.limiting_factor

  const labelMap: Record<string, string> = {
    minimum_power: '最低运行约束',
    load_variability: '波动空间约束',
    peak_window: '峰时转移约束',
    control_capability: '控制能力约束',
    thermal_storage: '蓄冷能力约束',
    device: '设备安全上限',
    temperature: '温度约束',
    redundancy: '冗余约束',
    pue: 'PUE约束'
  }

  const items = Object.entries(constraints)
    .filter(([, value]: any) => value && value.max_ratio !== null)
    .map(([key, value]: any) => ({
      name: labelMap[key] || key,
      value: value.max_ratio,
      description: value.reason || '该约束限制可转移比例',
      isBinding: limitingFactor === key
    }))

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

function _buildChart() {
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
      renderMode: 'richText',
      formatter: (params: any) => {
        if (!Array.isArray(params) || params.length === 0) return ''
        const hour = params[0].axisValue
        const point = data[params[0].dataIndex]
        const periodLabel = PERIOD_LABELS[point.period_type] || point.period_type
        let text = `${hour} (${periodLabel})\n`
        params.forEach((p: any) => {
          if (p.seriesName && p.value !== undefined) {
            text += `${p.seriesName}: ${p.value.toFixed(2)} kW\n`
          }
        })
        return text
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
      renderMode: 'richText',
      formatter: (params: any) => {
        if (!Array.isArray(params) || params.length === 0) return ''
        const _date = params[0].axisValue
        const point = data[params[0].dataIndex]
        let text = `${point.date}\n`
        text += `平均功率: ${point.avg_power.toFixed(2)} kW\n`
        text += `最大功率: ${point.max_power.toFixed(2)} kW\n`
        text += `最小功率: ${point.min_power.toFixed(2)} kW\n`
        text += `总能耗: ${point.energy.toFixed(2)} kWh`
        return text
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


// 规范化趋势数据：后端返回 daily_data/query_days，前端期望 trend_data/days
function normalizeTrendData(raw: any): PowerTrendResponse | null {
  if (!raw) return null
  return {
    ...raw,
    trend_data: raw.trend_data ?? raw.daily_data ?? [],
    days: raw.days ?? raw.query_days ?? 30,
  }
}

// 重新加载功率数据（切换天数时）
async function reloadProfile() {
  if (!props.device) return
  loading.value = true
  try {
    // 调用新的趋势 API
    const res = await getDevicePowerTrend(props.device.device_id, profileDays.value) as any
    const data = res?.data ?? res
    if (data) {
      trendData.value = normalizeTrendData(data)
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
    const res = await getDevicePowerTrend(newDevice.device_id, profileDays.value) as any
    const data = res?.data ?? res
    if (data) {
      trendData.value = normalizeTrendData(data)
      await nextTick()
      buildTrendChart()
    }

    // 加载典型日功率分析（负载率、峰时用电占比）
    try {
      const profileRes = await getDeviceTypicalDayProfile(newDevice.device_id, profileDays.value) as any
      const profileData = profileRes?.data ?? profileRes
      if (profileData) {
        profile.value = profileData
      }
    } catch (profileErr) {
      console.warn('加载典型日功率分析失败:', profileErr)
    }
  } catch (e) {
    console.error('加载设备功率趋势失败:', e)
  } finally {
    loading.value = false
  }
}, { immediate: false })  // 修复：移除immediate，避免组件创建时执行

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

  .control-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
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

  .cooling-strategy {
    margin-top: 18px;
    padding-top: 14px;
    border-top: 1px solid var(--border-color);
  }

  .section-subtitle {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 8px;
  }

  .strategy-summary {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 16px;
    font-size: 12px;
    color: var(--text-secondary);
    margin-bottom: 10px;
  }

  .strategy-steps {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .strategy-step {
    padding: 10px 12px;
    border-radius: 6px;
    border: 1px solid var(--border-color);
    background: rgba(24, 144, 255, 0.06);
  }

  .strategy-step-head {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: var(--text-primary);
  }

  .strategy-step-target {
    margin-top: 6px;
    font-size: 12px;
    line-height: 1.5;
    color: var(--text-secondary);
  }

  .strategy-step-controls {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 8px;
  }

  .strategy-metrics {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
    margin-top: 12px;
  }

  .strategy-metric {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    padding: 8px 10px;
    border-radius: 6px;
    background: var(--bg-tertiary, rgba(17, 34, 64, 0.8));
    font-size: 12px;
    color: var(--text-secondary);

    strong {
      color: var(--text-primary);
      white-space: nowrap;
    }
  }

  .strategy-formulas {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 12px;
  }

  .strategy-formula {
    padding: 8px 10px;
    border-radius: 6px;
    background: rgba(103, 194, 58, 0.08);
    font-size: 12px;

    .formula-title {
      font-weight: 600;
      color: var(--text-primary);
      margin-bottom: 4px;
    }

    code {
      display: block;
      color: #67c23a;
      white-space: normal;
      word-break: break-word;
      margin-bottom: 4px;
    }

    .formula-meaning {
      color: var(--text-secondary);
      line-height: 1.5;
    }
  }

  .strategy-interlocks {
    margin-top: 12px;
    font-size: 12px;
    color: var(--text-secondary);

    .interlock-title {
      font-weight: 600;
      color: var(--text-primary);
      margin-bottom: 4px;
    }

    ul {
      margin: 0;
      padding-left: 18px;
      line-height: 1.6;
    }
  }
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
