<template>
  <div class="shift-plan-builder">
    <el-card shadow="hover" class="config-card">
      <template #header>
        <div class="card-header">
          <span>交互式转移方案规划</span>
          <div class="header-actions">
            <el-tag type="info" size="small">支持多设备多规则配置</el-tag>
          </div>
        </div>
      </template>

      <el-row :gutter="16">
      <!-- 左侧：设备选择 + 推荐方案 -->
      <el-col :span="12">
        <div class="section-title">可转移设备列表</div>
        <el-table
          ref="deviceTableRef"
          :data="shiftableDevices"
          size="small"
          max-height="200"
          @selection-change="handleDeviceSelection"
          class="device-select-table"
        >
          <el-table-column type="selection" width="32" :selectable="(row: DeviceShiftPotential) => row.is_shiftable" />
          <el-table-column prop="device_name" label="设备" width="180" show-overflow-tooltip />
          <el-table-column prop="device_type" label="类型" width="65" />
          <el-table-column prop="shiftable_power" label="可调节容量(kW)" width="110" align="right">
            <template #default="{ row }">
              <span :class="{ 'power-value': row.is_shiftable }">{{ row.shiftable_power }}</span>
            </template>
          </el-table-column>
        </el-table>

        <!-- 选中设备汇总 -->
        <div class="selection-summary" v-if="selectedDevices.length > 0">
          <div class="summary-row">
            <span>已选 {{ selectedDevices.length }} 台设备</span>
            <span class="total-power">总可转移: {{ totalSelectedPower.toFixed(1) }} kW</span>
          </div>
        </div>

        <!-- 推荐方案区域 -->
        <div class="recommend-section">
          <div class="section-title">智能推荐方案</div>
          <div class="strategy-select">
            <span class="strategy-label">优化策略:</span>
            <el-radio-group v-model="optimizationStrategy" size="small">
              <el-radio-button label="max_benefit">效益最大化</el-radio-button>
              <el-radio-button label="min_cost">成本最小化</el-radio-button>
            </el-radio-group>
          </div>
          <el-button
            type="primary"
            :loading="recommending"
            :disabled="selectedDevices.length === 0"
            @click="generateRecommendation"
            class="recommend-btn"
          >
            <el-icon><MagicStick /></el-icon>
            推荐方案
          </el-button>
          <div class="strategy-hint">
            <span v-if="optimizationStrategy === 'max_benefit'">
              效益最大化：优先将高价时段(尖峰/峰时)负荷转移至最低价时段(深谷)
            </span>
            <span v-else>
              成本最小化：平衡转移量与操作复杂度，选择最稳定的转移方案
            </span>
          </div>
        </div>

        <!-- 选中设备时段分析 -->
        <div class="period-analysis" v-if="selectedDevices.length > 0">
          <div class="section-title">选中设备时段能耗分布</div>
          <div class="period-bars">
            <div class="period-bar sharp">
              <span class="label">尖峰</span>
              <el-progress :percentage="avgSharpRatio * 100" :stroke-width="10" color="#722ed1" :show-text="false" />
              <span class="value">{{ (avgSharpRatio * 100).toFixed(0) }}%</span>
            </div>
            <div class="period-bar peak">
              <span class="label">峰时</span>
              <el-progress :percentage="avgPeakRatio * 100" :stroke-width="10" color="#f56c6c" :show-text="false" />
              <span class="value">{{ (avgPeakRatio * 100).toFixed(0) }}%</span>
            </div>
            <div class="period-bar valley">
              <span class="label">谷时</span>
              <el-progress :percentage="avgValleyRatio * 100" :stroke-width="10" color="#67c23a" :show-text="false" />
              <span class="value">{{ (avgValleyRatio * 100).toFixed(0) }}%</span>
            </div>
            <div class="period-bar deep-valley">
              <span class="label">深谷</span>
              <el-progress :percentage="avgDeepValleyRatio * 100" :stroke-width="10" color="#409eff" :show-text="false" />
              <span class="value">{{ (avgDeepValleyRatio * 100).toFixed(0) }}%</span>
            </div>
          </div>
        </div>
      </el-col>

      <!-- 右侧：设备转移规则配置 -->
      <el-col :span="12">
        <div class="section-title">
          设备转移规则配置
          <span class="config-hint">每个设备可配置多条转移规则</span>
        </div>

        <div class="device-rules-container" v-if="selectedDevices.length > 0">
          <div class="device-rule-card" v-for="device in selectedDevices" :key="device.device_id">
            <div class="device-header" @click="toggleDeviceExpand(device.device_id)">
              <div class="device-info">
                <span class="device-name">{{ device.device_name }}</span>
                <span class="device-type">{{ device.device_type }}</span>
              </div>
              <div class="device-power-info">
                <span class="shiftable">可转移: <strong>{{ device.shiftable_power }} kW</strong></span>
              </div>
              <div class="device-saving">
                <span class="saving-value">日省: ¥{{ getDeviceDailySaving(device.device_id).toFixed(2) }}</span>
              </div>
              <el-icon class="expand-icon" :class="{ expanded: expandedDevices.includes(device.device_id) }">
                <ArrowDown />
              </el-icon>
            </div>

            <!-- 设备的转移规则列表 -->
            <div class="device-rules" v-if="expandedDevices.includes(device.device_id)">
              <div
                class="shift-rule"
                v-for="(rule, ruleIdx) in getDeviceRules(device.device_id)"
                :key="ruleIdx"
              >
                <div class="rule-row">
                  <div class="rule-field">
                    <label>源时段</label>
                    <el-select v-model="rule.sourcePeriod" size="small" style="width: 90px;">
                      <el-option label="尖峰" value="sharp" />
                      <el-option label="峰时" value="peak" />
                      <el-option label="平时" value="flat" />
                    </el-select>
                  </div>
                  <div class="rule-arrow">→</div>
                  <div class="rule-field">
                    <label>目标时段</label>
                    <el-select v-model="rule.targetPeriod" size="small" style="width: 90px;">
                      <el-option label="平时" value="flat" />
                      <el-option label="谷时" value="valley" />
                      <el-option label="深谷" value="deep_valley" />
                    </el-select>
                  </div>
                  <div class="rule-field">
                    <label>功率</label>
                    <el-input-number
                      v-model="rule.power"
                      size="small"
                      :min="0"
                      :max="device.shiftable_power"
                      :step="5"
                      style="width: 100px;"
                    />
                    <span class="unit">kW</span>
                  </div>
                  <div class="rule-field">
                    <label>时长</label>
                    <el-input-number
                      v-model="rule.hours"
                      size="small"
                      :min="1"
                      :max="8"
                      style="width: 80px;"
                    />
                    <span class="unit">h</span>
                  </div>
                  <div class="rule-saving-preview">
                    <span class="daily">¥{{ calculateRuleDailySaving(rule).toFixed(2) }}/日</span>
                  </div>
                  <el-button
                    type="danger"
                    size="small"
                    circle
                    @click="removeRule(device.device_id, ruleIdx)"
                    v-if="getDeviceRules(device.device_id).length > 1"
                  >
                    <el-icon><Delete /></el-icon>
                  </el-button>
                </div>
              </div>
              <el-button
                type="primary"
                size="small"
                text
                @click="addRule(device.device_id)"
                class="add-rule-btn"
              >
                <el-icon><Plus /></el-icon> 添加转移规则
              </el-button>
            </div>
          </div>
        </div>

        <el-empty v-else description="请先选择要转移的设备" :image-size="80" />

        <!-- 效益计算汇总 -->
        <div class="calc-summary" v-if="hasAnyRules">
          <div class="section-title">效益计算汇总</div>
          <el-row :gutter="16">
            <el-col :span="6">
              <div class="summary-stat">
                <div class="stat-label">配置设备</div>
                <div class="stat-value">{{ configuredDeviceCount }} 台</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="summary-stat">
                <div class="stat-label">转移规则</div>
                <div class="stat-value">{{ totalRulesCount }} 条</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="summary-stat">
                <div class="stat-label">总转移功率</div>
                <div class="stat-value">{{ totalConfiguredPower.toFixed(1) }} kW</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="summary-stat highlight">
                <div class="stat-label">日节省</div>
                <div class="stat-value saving">¥{{ totalDailySaving.toFixed(2) }}</div>
              </div>
            </el-col>
          </el-row>
          <div class="annual-saving-row">
            <el-icon><TrendCharts /></el-icon>
            <span>预计年度收益: <strong>¥{{ formatNumber(totalAnnualSaving) }}</strong></span>
            <span class="formula">(= 日节省 × 250 工作日)</span>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="action-bar">
          <el-button
            type="success"
            size="large"
            :disabled="!hasAnyRules"
            @click="handleExecute"
          >
            <el-icon><VideoPlay /></el-icon>
            执行方案
          </el-button>
          <span class="action-hint" v-if="!hasAnyRules">
            请先配置转移规则后再执行
          </span>
        </div>
      </el-col>
    </el-row>
  </el-card>

  <!-- 负荷转移前后对比曲线 -->
  <LoadComparisonChart
    v-if="hasAnyRules"
    :device-rules="chartDeviceRules"
    @range-change="handleRangeChange"
  />

  <!-- 执行计划确认对话框 -->
  <ExecutionPlanDialog
    ref="executionDialogRef"
    v-model="showExecutionDialog"
    :strategy="optimizationStrategy"
    :daily-saving="totalDailySaving"
    :annual-saving="totalAnnualSaving"
    :device-rules="chartDeviceRules"
    @confirm="handleConfirmExecution"
  />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Delete, ArrowDown, MagicStick, TrendCharts, VideoPlay } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { DeviceShiftPotential } from '@/api/modules/energy'
import LoadComparisonChart from './LoadComparisonChart.vue'
import ExecutionPlanDialog from './ExecutionPlanDialog.vue'
import { createLoadShiftPlan, type DeviceShiftRule } from '@/api/modules/energy'

// 转移规则类型
interface ShiftRule {
  sourcePeriod: string
  targetPeriod: string
  power: number
  hours: number
}

// 待恢复配置数据类型
interface PendingRestoreData {
  strategy: string
  deviceRules: Array<{
    device_id: number
    device_name: string
    rules: Array<{
      source_period: string
      target_period: string
      power: number
      hours: number
    }>
  }>
}

const props = defineProps<{
  shiftableDevices: DeviceShiftPotential[]
  pendingRestore?: PendingRestoreData | null
}>()

const emit = defineEmits<{
  (e: 'plan-change', data: {
    shiftPower: number
    shiftHours: number
    sourcePeriod: string
    targetPeriod: string
    selectedDeviceIds: number[]
  }): void
  (e: 'restore-complete'): void
}>()

const router = useRouter()

// Dialog state
const showExecutionDialog = ref(false)
const executionDialogRef = ref<InstanceType<typeof ExecutionPlanDialog>>()

// State
const selectedDevices = ref<DeviceShiftPotential[]>([])
const expandedDevices = ref<number[]>([])
const deviceShiftRules = reactive<Record<number, ShiftRule[]>>({})
const optimizationStrategy = ref<'max_benefit' | 'min_cost'>('max_benefit')
const recommending = ref(false)

// Pricing config (元/kWh) - 5段式分时电价
const periodPrices: Record<string, number> = {
  sharp: 1.40,       // 尖峰
  peak: 1.00,        // 峰时
  flat: 0.65,        // 平时
  valley: 0.35,      // 谷时
  deep_valley: 0.20  // 深谷
}

// 时段名称
const periodNames: Record<string, string> = {
  sharp: '尖峰',
  peak: '峰时',
  flat: '平时',
  valley: '谷时',
  deep_valley: '深谷'
}

// Computed
const totalSelectedPower = computed(() =>
  selectedDevices.value.reduce((sum, d) => sum + d.shiftable_power, 0)
)

// 选中设备的平均各时段占比
const avgSharpRatio = computed(() => {
  if (selectedDevices.value.length === 0) return 0
  const sum = selectedDevices.value.reduce((acc, d) => acc + (d.sharp_energy_ratio || 0), 0)
  return sum / selectedDevices.value.length
})

const avgPeakRatio = computed(() => {
  if (selectedDevices.value.length === 0) return 0
  const sum = selectedDevices.value.reduce((acc, d) => acc + d.peak_energy_ratio, 0)
  return sum / selectedDevices.value.length
})

const avgValleyRatio = computed(() => {
  if (selectedDevices.value.length === 0) return 0
  const sum = selectedDevices.value.reduce((acc, d) => acc + d.valley_energy_ratio, 0)
  return sum / selectedDevices.value.length
})

const avgDeepValleyRatio = computed(() => {
  if (selectedDevices.value.length === 0) return 0
  const sum = selectedDevices.value.reduce((acc, d) => acc + (d.deep_valley_energy_ratio || 0), 0)
  return sum / selectedDevices.value.length
})

// 是否有配置的规则
const hasAnyRules = computed(() => {
  for (const deviceId of Object.keys(deviceShiftRules)) {
    const rules = deviceShiftRules[Number(deviceId)]
    if (rules && rules.length > 0 && rules.some(r => r.power > 0)) {
      return true
    }
  }
  return false
})

// 已配置设备数
const configuredDeviceCount = computed(() => {
  let count = 0
  for (const deviceId of Object.keys(deviceShiftRules)) {
    const rules = deviceShiftRules[Number(deviceId)]
    if (rules && rules.length > 0 && rules.some(r => r.power > 0)) {
      count++
    }
  }
  return count
})

// 总规则数
const totalRulesCount = computed(() => {
  let count = 0
  for (const deviceId of Object.keys(deviceShiftRules)) {
    const rules = deviceShiftRules[Number(deviceId)]
    if (rules) {
      count += rules.filter(r => r.power > 0).length
    }
  }
  return count
})

// 总配置功率
const totalConfiguredPower = computed(() => {
  let total = 0
  for (const deviceId of Object.keys(deviceShiftRules)) {
    const rules = deviceShiftRules[Number(deviceId)]
    if (rules) {
      total += rules.reduce((s, r) => s + (r.power || 0), 0)
    }
  }
  return total
})

// 总日节省
const totalDailySaving = computed(() => {
  let total = 0
  for (const deviceId of Object.keys(deviceShiftRules)) {
    const rules = deviceShiftRules[Number(deviceId)]
    if (rules) {
      total += rules.reduce((s, r) => s + calculateRuleDailySaving(r), 0)
    }
  }
  return total
})

const totalMonthlySaving = computed(() => totalDailySaving.value * 22)
const totalAnnualSaving = computed(() => totalDailySaving.value * 250)

// 方法
function calculateRuleDailySaving(rule: ShiftRule): number {
  const sourcePrice = periodPrices[rule.sourcePeriod] || 0
  const targetPrice = periodPrices[rule.targetPeriod] || 0
  const priceDiff = sourcePrice - targetPrice
  return (rule.power || 0) * (rule.hours || 0) * priceDiff
}

function getDeviceDailySaving(deviceId: number): number {
  const rules = deviceShiftRules[deviceId]
  if (!rules) return 0
  return rules.reduce((sum, r) => sum + calculateRuleDailySaving(r), 0)
}

function getDeviceRules(deviceId: number): ShiftRule[] {
  if (!deviceShiftRules[deviceId]) {
    deviceShiftRules[deviceId] = []
  }
  return deviceShiftRules[deviceId]
}

function toggleDeviceExpand(deviceId: number) {
  const idx = expandedDevices.value.indexOf(deviceId)
  if (idx >= 0) {
    expandedDevices.value.splice(idx, 1)
  } else {
    expandedDevices.value.push(deviceId)
    // 确保设备有规则
    if (!deviceShiftRules[deviceId] || deviceShiftRules[deviceId].length === 0) {
      initDeviceRules(deviceId)
    }
  }
}

function initDeviceRules(deviceId: number) {
  const device = selectedDevices.value.find(d => d.device_id === deviceId)
  const defaultPower = device?.shiftable_power || 10

  // 默认一条规则：峰→谷
  deviceShiftRules[deviceId] = [{
    sourcePeriod: 'peak',
    targetPeriod: 'valley',
    power: Math.min(Math.floor(defaultPower * 0.5), 50),
    hours: 4
  }]
}

function addRule(deviceId: number) {
  if (!deviceShiftRules[deviceId]) {
    deviceShiftRules[deviceId] = []
  }
  deviceShiftRules[deviceId].push({
    sourcePeriod: 'sharp',
    targetPeriod: 'deep_valley',
    power: 10,
    hours: 2
  })
}

function removeRule(deviceId: number, ruleIdx: number) {
  if (deviceShiftRules[deviceId] && deviceShiftRules[deviceId].length > ruleIdx) {
    deviceShiftRules[deviceId].splice(ruleIdx, 1)
  }
}

function handleDeviceSelection(devices: DeviceShiftPotential[]) {
  selectedDevices.value = devices

  // 清理已取消选择的设备规则
  const selectedIds = devices.map(d => d.device_id)
  for (const deviceId of Object.keys(deviceShiftRules)) {
    if (!selectedIds.includes(Number(deviceId))) {
      delete deviceShiftRules[Number(deviceId)]
    }
  }

  // 从expandedDevices中移除已取消选择的设备
  expandedDevices.value = expandedDevices.value.filter(id => selectedIds.includes(id))
}

// 生成推荐方案
function generateRecommendation() {
  if (selectedDevices.value.length === 0) {
    ElMessage.warning('请先选择要转移的设备')
    return
  }

  recommending.value = true

  setTimeout(() => {
    // 清空现有规则
    for (const key of Object.keys(deviceShiftRules)) {
      delete deviceShiftRules[Number(key)]
    }
    expandedDevices.value = []

    // 根据策略生成推荐方案
    for (const device of selectedDevices.value) {
      const shiftablePower = device.shiftable_power || 0
      if (shiftablePower <= 0) continue

      const rules: ShiftRule[] = []

      if (optimizationStrategy.value === 'max_benefit') {
        // 效益最大化策略：多条规则，最大化价差

        // 规则1：尖峰 → 深谷 (价差最大 1.40-0.20=1.20)
        if ((device.sharp_energy_ratio || 0) > 0.05) {
          rules.push({
            sourcePeriod: 'sharp',
            targetPeriod: 'deep_valley',
            power: Math.floor(shiftablePower * 0.4),
            hours: 2
          })
        }

        // 规则2：峰时 → 谷时 (价差 1.00-0.35=0.65)
        if (device.peak_energy_ratio > 0.1) {
          rules.push({
            sourcePeriod: 'peak',
            targetPeriod: 'valley',
            power: Math.floor(shiftablePower * 0.4),
            hours: 4
          })
        }

        // 规则3：峰时 → 深谷 (价差 1.00-0.20=0.80)
        if (device.peak_energy_ratio > 0.2) {
          rules.push({
            sourcePeriod: 'peak',
            targetPeriod: 'deep_valley',
            power: Math.floor(shiftablePower * 0.2),
            hours: 3
          })
        }
      } else {
        // 成本最小化策略：简单稳定的方案

        // 只用一条规则：峰 → 谷，但功率和时长更保守
        rules.push({
          sourcePeriod: 'peak',
          targetPeriod: 'valley',
          power: Math.floor(shiftablePower * 0.6),
          hours: 4
        })
      }

      // 确保至少有一条规则
      if (rules.length === 0) {
        rules.push({
          sourcePeriod: 'peak',
          targetPeriod: 'valley',
          power: Math.floor(shiftablePower * 0.5),
          hours: 4
        })
      }

      // 过滤掉功率为0的规则
      deviceShiftRules[device.device_id] = rules.filter(r => r.power > 0)

      // 展开设备
      if (!expandedDevices.value.includes(device.device_id)) {
        expandedDevices.value.push(device.device_id)
      }
    }

    recommending.value = false
    ElMessage.success(`已生成${optimizationStrategy.value === 'max_benefit' ? '效益最大化' : '成本最小化'}推荐方案`)
  }, 500)
}

// 执行方案 - 打开确认对话框
function handleExecute() {
  if (!hasAnyRules.value) {
    ElMessage.warning('请先配置转移规则')
    return
  }
  showExecutionDialog.value = true
}

// 确认创建执行计划
async function handleConfirmExecution(data: { planName: string; remark: string }) {
  console.log('[ShiftPlanBuilder] handleConfirmExecution called', data)

  // 收集所有规则数据
  const deviceRulesData: DeviceShiftRule[] = []

  for (const device of selectedDevices.value) {
    const rules = deviceShiftRules[device.device_id]
    if (rules && rules.length > 0 && rules.some(r => r.power > 0)) {
      deviceRulesData.push({
        device_id: device.device_id,
        device_name: device.device_name,
        rules: rules.filter(r => r.power > 0).map(r => ({
          source_period: r.sourcePeriod,
          target_period: r.targetPeriod,
          power: Number(r.power),  // 确保是数字
          hours: Math.round(Number(r.hours))  // 确保是整数
        }))
      })
    }
  }

  console.log('[ShiftPlanBuilder] deviceRulesData:', deviceRulesData)

  // 确保所有数值类型正确
  const requestPayload = {
    plan_name: data.planName,
    strategy: optimizationStrategy.value,
    daily_saving: Number(totalDailySaving.value) || 0,
    annual_saving: Number(totalAnnualSaving.value) || 0,
    device_rules: deviceRulesData,
    remark: data.remark || undefined
  }

  console.log('[ShiftPlanBuilder] Request payload:', requestPayload)

  try {
    console.log('[ShiftPlanBuilder] Calling createLoadShiftPlan API...')
    const res = await createLoadShiftPlan(requestPayload)

    console.log('[ShiftPlanBuilder] API response:', res)

    if (res.code === 0 && res.data) {
      ElMessage.success(`执行计划创建成功，共${res.data.task_count}个任务`)
      showExecutionDialog.value = false

      // 跳转到执行管理页面，高亮显示新计划
      console.log('[ShiftPlanBuilder] Navigating to execution page with plan_id:', res.data.plan_id)
      router.push({
        path: '/energy/execution',
        query: {
          highlight: res.data.plan_id.toString()
        }
      })
    } else {
      console.error('[ShiftPlanBuilder] API returned error:', res)
      ElMessage.error(res.message || '创建执行计划失败')
    }
  } catch (error: any) {
    console.error('[ShiftPlanBuilder] API call failed:', error)
    ElMessage.error(error.message || '创建执行计划失败')
  } finally {
    executionDialogRef.value?.setSubmitting(false)
  }
}

function formatNumber(num: number): string {
  return num >= 10000 ? (num / 10000).toFixed(2) + '万' : num.toFixed(0)
}

// 为LoadComparisonChart组件准备的设备规则数据
const chartDeviceRules = computed(() => {
  const result: Array<{
    deviceId: number
    deviceName: string
    rules: ShiftRule[]
  }> = []

  for (const device of selectedDevices.value) {
    const rules = deviceShiftRules[device.device_id]
    if (rules && rules.length > 0 && rules.some(r => r.power > 0)) {
      result.push({
        deviceId: device.device_id,
        deviceName: device.device_name,
        rules: rules.filter(r => r.power > 0)
      })
    }
  }

  return result
})

// 处理时间范围变化（1天/7天平均）
function handleRangeChange(range: string) {
  console.log('Data range changed to:', range)
}

// Watch for plan changes
watch([deviceShiftRules, selectedDevices], () => {
  // 计算汇总数据发送给父组件
  const totalPower = totalConfiguredPower.value
  emit('plan-change', {
    shiftPower: totalPower,
    shiftHours: 4, // 默认值
    sourcePeriod: 'peak',
    targetPeriod: 'valley',
    selectedDeviceIds: selectedDevices.value.map(d => d.device_id)
  })
}, { deep: true })

// Watch for pending restore data
watch(() => props.pendingRestore, (restoreData) => {
  if (restoreData) {
    restoreConfig(restoreData)
  }
}, { immediate: true })

// 恢复配置方法
function restoreConfig(data: PendingRestoreData) {
  // 设置优化策略
  optimizationStrategy.value = data.strategy as 'max_benefit' | 'min_cost'

  // 清空现有规则
  for (const key of Object.keys(deviceShiftRules)) {
    delete deviceShiftRules[Number(key)]
  }
  expandedDevices.value = []

  // 等待shiftableDevices数据加载后再恢复
  if (props.shiftableDevices.length === 0) {
    // 如果设备列表还没加载，监听一次加载完成后再恢复
    const stopWatch = watch(() => props.shiftableDevices, (devices) => {
      if (devices.length > 0) {
        doRestoreRules(data)
        stopWatch()
      }
    }, { immediate: true })
  } else {
    doRestoreRules(data)
  }
}

// 执行规则恢复
function doRestoreRules(data: PendingRestoreData) {
  // 找到要选中的设备
  const deviceIdsToSelect = data.deviceRules.map(dr => dr.device_id)
  const devicesToSelect = props.shiftableDevices.filter(d =>
    deviceIdsToSelect.includes(d.device_id)
  )

  // 选中设备
  selectedDevices.value = devicesToSelect

  // 恢复规则配置
  for (const deviceRule of data.deviceRules) {
    deviceShiftRules[deviceRule.device_id] = deviceRule.rules.map(r => ({
      sourcePeriod: r.source_period,
      targetPeriod: r.target_period,
      power: r.power,
      hours: r.hours
    }))
    // 展开设备
    if (!expandedDevices.value.includes(deviceRule.device_id)) {
      expandedDevices.value.push(deviceRule.device_id)
    }
  }

  ElMessage.success('已恢复原配置')
  emit('restore-complete')
}
</script>

<style scoped lang="scss">
.shift-plan-builder {
  margin-top: 20px;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .section-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-color);
    display: flex;
    justify-content: space-between;
    align-items: center;

    .config-hint {
      font-size: 11px;
      font-weight: normal;
      color: var(--text-secondary);
    }
  }

  .device-select-table {
    :deep(.el-table__header-wrapper th.el-table__cell),
    :deep(.el-table__body-wrapper td.el-table__cell) {
      padding: 0 !important;
      height: 32px !important;
      font-size: 12px !important;

      .cell {
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        padding: 0 4px !important;
        line-height: 32px !important;
        height: 32px !important;
      }
    }

    :deep(.el-table__header-wrapper th.el-table__cell) {
      background: var(--bg-tertiary) !important;
      color: var(--text-primary) !important;
      border-bottom: 1px solid var(--border-color) !important;
    }

    :deep(.el-table__body-wrapper tr.el-table__row) {
      height: 32px !important;
    }

    .power-value {
      color: var(--primary-color);
      font-weight: 600;
    }
  }

  .selection-summary {
    margin-top: 8px;
    font-size: 12px;
    padding: 8px 12px;
    background: rgba(64, 158, 255, 0.08);
    border-radius: 4px;

    .summary-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .total-power {
      color: var(--primary-color);
      font-weight: 600;
    }
  }

  .recommend-section {
    margin-top: 16px;
    padding: 16px;
    background: linear-gradient(135deg, rgba(64, 158, 255, 0.08), rgba(103, 194, 58, 0.08));
    border: 1px solid rgba(64, 158, 255, 0.2);
    border-radius: 8px;

    .strategy-select {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 12px;

      .strategy-label {
        font-size: 13px;
        color: var(--text-secondary);
      }
    }

    .recommend-btn {
      width: 100%;
      margin-bottom: 8px;
    }

    .strategy-hint {
      font-size: 11px;
      color: var(--text-secondary);
      line-height: 1.5;
    }
  }

  .period-analysis {
    margin-top: 16px;
    padding: 12px;
    background: var(--bg-tertiary);
    border-radius: 8px;

    .period-bars {
      margin-top: 8px;

      .period-bar {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;

        &:last-child {
          margin-bottom: 0;
        }

        .label {
          min-width: 36px;
          font-size: 11px;
          color: var(--text-secondary);
        }

        :deep(.el-progress) {
          flex: 1;
        }

        .value {
          min-width: 32px;
          text-align: right;
          font-size: 11px;
          font-weight: 600;
          color: var(--text-primary);
        }
      }
    }
  }

  .device-rules-container {
    max-height: 350px;
    overflow-y: auto;

    .device-rule-card {
      border: 1px solid var(--border-color);
      border-radius: 8px;
      margin-bottom: 12px;
      background: var(--bg-card-solid);
      overflow: hidden;

      .device-header {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 14px;
        cursor: pointer;
        transition: background 0.2s;

        &:hover {
          background: rgba(64, 158, 255, 0.05);
        }

        .device-info {
          flex: 1;

          .device-name {
            color: var(--text-primary);
            font-weight: 500;
            margin-right: 8px;
          }

          .device-type {
            color: var(--text-secondary);
            font-size: 11px;
          }
        }

        .device-power-info {
          font-size: 12px;
          color: var(--text-secondary);

          strong {
            color: var(--primary-color);
          }
        }

        .device-saving {
          .saving-value {
            font-size: 12px;
            color: var(--success-color);
            font-weight: 600;
          }
        }

        .expand-icon {
          color: var(--text-secondary);
          transition: transform 0.2s;

          &.expanded {
            transform: rotate(180deg);
          }
        }
      }

      .device-rules {
        padding: 12px 14px;
        background: var(--bg-tertiary);
        border-top: 1px solid var(--border-color);

        .shift-rule {
          margin-bottom: 10px;

          .rule-row {
            display: flex;
            align-items: flex-end;
            gap: 8px;
            flex-wrap: wrap;

            .rule-field {
              display: flex;
              flex-direction: column;
              gap: 2px;

              label {
                font-size: 10px;
                color: var(--text-secondary);
              }

              .unit {
                font-size: 11px;
                color: var(--text-secondary);
                margin-left: 4px;
              }
            }

            .rule-arrow {
              color: var(--text-secondary);
              font-size: 16px;
              padding-bottom: 4px;
            }

            .rule-saving-preview {
              padding: 4px 8px;
              background: rgba(82, 196, 26, 0.1);
              border-radius: 4px;
              font-size: 11px;

              .daily {
                color: var(--success-color);
                font-weight: 600;
              }
            }
          }
        }

        .add-rule-btn {
          margin-top: 4px;
        }
      }
    }
  }

  .calc-summary {
    margin-top: 16px;
    padding: 16px;
    background: var(--bg-tertiary);
    border-radius: 8px;

    .summary-stat {
      text-align: center;
      padding: 8px;

      .stat-label {
        font-size: 11px;
        color: var(--text-secondary);
        margin-bottom: 4px;
      }

      .stat-value {
        font-size: 16px;
        font-weight: 600;
        color: var(--text-primary);

        &.saving {
          color: var(--success-color);
        }
      }

      &.highlight {
        background: rgba(82, 196, 26, 0.1);
        border-radius: 6px;
      }
    }

    .annual-saving-row {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      margin-top: 16px;
      padding: 12px;
      background: rgba(82, 196, 26, 0.1);
      border: 1px solid rgba(82, 196, 26, 0.3);
      border-radius: 6px;
      font-size: 14px;
      color: var(--text-secondary);

      .el-icon {
        color: var(--success-color);
        font-size: 18px;
      }

      strong {
        color: var(--success-color);
        font-size: 18px;
      }

      .formula {
        font-size: 11px;
        color: var(--text-tertiary);
      }
    }
  }

  .action-bar {
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid var(--border-color);
    display: flex;
    align-items: center;
    gap: 12px;

    .action-hint {
      font-size: 12px;
      color: var(--text-secondary);
    }
  }
}
</style>

<!-- 非 scoped 样式，用于覆盖全局 el-table 样式 -->
<style lang="scss">
.device-select-table.el-table {
  .el-table__header-wrapper th.el-table__cell,
  .el-table__body-wrapper td.el-table__cell {
    padding: 0 !important;
    height: 32px !important;
    font-size: 12px !important;

    .cell {
      white-space: nowrap !important;
      overflow: hidden !important;
      text-overflow: ellipsis !important;
      padding: 0 4px !important;
      line-height: 32px !important;
      height: 32px !important;
    }
  }

  .el-table__header-wrapper th.el-table__cell {
    background: var(--bg-tertiary, #1a2332) !important;
    color: var(--text-primary, #fff) !important;
    border-bottom: 1px solid var(--border-color, #3a4a5a) !important;
  }

  .el-table__body-wrapper tr.el-table__row {
    height: 32px !important;
  }
}
</style>
