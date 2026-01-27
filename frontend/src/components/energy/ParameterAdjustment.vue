<template>
  <div class="parameter-adjustment">
    <!-- 数据来源提示 -->
    <el-alert type="info" :closable="false" class="data-source-tip">
      <template #title>
        <el-icon><InfoFilled /></el-icon>
        电价数据来源：系统设置 → 电价配置 | 设备数据来源：系统设置 → 设备配置
      </template>
    </el-alert>

    <el-form :model="paramForm" label-width="100px" class="param-form">
      <!-- 设备选择（多选） -->
      <el-form-item label="参与设备">
        <div class="device-select-container">
          <el-checkbox-group v-model="paramForm.selected_devices" @change="handleParamChange">
            <div
              v-for="device in shiftableDevices"
              :key="device.device_id"
              class="device-checkbox-item"
            >
              <el-checkbox :label="device.device_id">
                <span class="device-name">{{ device.device_name }}</span>
                <el-tag size="small" type="success">
                  {{ device.shiftable_power?.toFixed(1) }}kW可转移
                </el-tag>
                <el-tooltip v-if="device.allowed_shift_hours?.length">
                  <template #content>
                    <div>调节方式: {{ device.regulation_method }}</div>
                    <div>允许转移时段: {{ formatHours(device.allowed_shift_hours) }}</div>
                    <div v-if="device.max_shift_duration">最大转移时长: {{ device.max_shift_duration }}h</div>
                  </template>
                  <el-icon class="info-icon"><QuestionFilled /></el-icon>
                </el-tooltip>
              </el-checkbox>
            </div>
          </el-checkbox-group>

          <div v-if="shiftableDevices.length === 0" class="no-devices">
            <el-empty description="暂无可转移设备，请在系统设置中配置" :image-size="60" />
          </div>
        </div>
      </el-form-item>

      <!-- 转移时长 -->
      <el-form-item label="转移时长">
        <div class="slider-container">
          <el-slider
            v-model="paramForm.shift_hours"
            :min="0.5"
            :max="8"
            :step="0.5"
            :marks="shiftMarks"
            show-stops
            @change="handleParamChange"
          />
          <el-input-number
            v-model="paramForm.shift_hours"
            :min="0.5"
            :max="8"
            :step="0.5"
            size="small"
            class="hours-input"
            @change="handleParamChange"
          />
          <span class="unit">小时/天</span>
        </div>
      </el-form-item>

      <!-- 转出时段（从数据库加载） -->
      <el-form-item label="转出时段">
        <el-select
          v-model="paramForm.source_period"
          placeholder="选择转出时段"
          @change="handleParamChange"
          class="period-select"
        >
          <el-option
            v-for="period in sourcePeriods"
            :key="period.type"
            :label="`${period.display_name}(${period.label}) - ${period.price}元/kWh`"
            :value="period.type"
          >
            <span>{{ period.display_name }}</span>
            <span class="period-price">{{ period.price }}元/kWh</span>
          </el-option>
        </el-select>
        <span class="period-hint" v-if="sourcePrice > 0">
          当前选择: {{ sourcePrice }}元/kWh
        </span>
      </el-form-item>

      <!-- 转入时段（从数据库加载） -->
      <el-form-item label="转入时段">
        <el-select
          v-model="paramForm.target_period"
          placeholder="选择转入时段"
          @change="handleParamChange"
          class="period-select"
        >
          <el-option
            v-for="period in targetPeriods"
            :key="period.type"
            :label="`${period.display_name}(${period.label}) - ${period.price}元/kWh`"
            :value="period.type"
          >
            <span>{{ period.display_name }}</span>
            <span class="period-price">{{ period.price }}元/kWh</span>
          </el-option>
        </el-select>
        <span class="period-hint" v-if="targetPrice > 0">
          当前选择: {{ targetPrice }}元/kWh
        </span>
      </el-form-item>
    </el-form>

    <!-- 实时计算结果 -->
    <el-card class="calculation-result" shadow="never" v-loading="calculating">
      <template #header>
        <div class="result-header">
          <span>计算结果（实时更新）</span>
          <el-tag v-if="hasChanges" size="small" type="warning">参数已调整</el-tag>
        </div>
      </template>

      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="选中设备总功率">
          <span class="value">{{ calculationResult.total_power?.toFixed(1) || 0 }}</span> kW
        </el-descriptions-item>
        <el-descriptions-item label="电价差">
          <span class="value highlight">{{ calculationResult.price_diff?.toFixed(3) || 0 }}</span> 元/kWh
        </el-descriptions-item>
        <el-descriptions-item label="日转移电量">
          <span class="value">{{ calculationResult.daily_energy?.toFixed(1) || 0 }}</span> kWh
        </el-descriptions-item>
        <el-descriptions-item label="日收益">
          <span class="value">{{ calculationResult.daily_saving?.toFixed(2) || 0 }}</span> 元
        </el-descriptions-item>
        <el-descriptions-item label="年收益" :span="2">
          <span class="value highlight large">
            {{ calculationResult.annual_saving?.toFixed(2) || 0 }} 元
          </span>
          <span class="sub-value">
            （约 {{ (calculationResult.annual_saving_wan || 0).toFixed(2) }} 万元）
          </span>
        </el-descriptions-item>
      </el-descriptions>

      <!-- 计算步骤展示 -->
      <el-collapse v-model="showSteps" class="steps-collapse">
        <el-collapse-item title="查看计算步骤" name="steps">
          <ol class="calculation-steps">
            <li v-for="(step, index) in calculationResult.steps" :key="index">
              {{ step }}
            </li>
          </ol>
          <div class="pricing-source" v-if="calculationResult.pricing_used">
            <el-divider content-position="left">使用的电价数据</el-divider>
            <p>转出时段({{ calculationResult.pricing_used?.source?.period }}):
              <strong>{{ calculationResult.pricing_used?.source?.price }}</strong> 元/kWh
            </p>
            <p>转入时段({{ calculationResult.pricing_used?.target?.period }}):
              <strong>{{ calculationResult.pricing_used?.target?.price }}</strong> 元/kWh
            </p>
          </div>
        </el-collapse-item>
      </el-collapse>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { debounce } from 'lodash-es'
import { InfoFilled, QuestionFilled } from '@element-plus/icons-vue'
import {
  getCurrentPricing,
  getShiftableDevices,
  recalculateSuggestion,
  type SuggestionDetail,
  type TimePeriod,
  type ShiftableDevice,
  type RecalculateResult
} from '@/api/modules/energy'

const props = defineProps<{
  suggestion: SuggestionDetail
}>()

const emit = defineEmits<{
  (e: 'paramsChanged', params: any, effects: any): void
}>()

// 从API加载真实数据
const sourcePeriods = ref<TimePeriod[]>([])
const targetPeriods = ref<TimePeriod[]>([])
const shiftableDevices = ref<ShiftableDevice[]>([])
const calculating = ref(false)
const showSteps = ref<string[]>([])

// 参数表单
const paramForm = reactive({
  selected_devices: [] as number[],
  shift_hours: 2,
  source_period: 'sharp',
  target_period: 'valley'
})

// 计算结果
const calculationResult = reactive({
  total_power: 0,
  price_diff: 0,
  daily_energy: 0,
  daily_saving: 0,
  annual_saving: 0,
  annual_saving_wan: 0,
  steps: [] as string[],
  pricing_used: null as any
})

// 滑块标记
const shiftMarks = {
  0.5: '0.5h',
  2: '2h',
  4: '4h',
  6: '6h',
  8: '8h'
}

// 计算源时段价格
const sourcePrice = computed(() => {
  const period = sourcePeriods.value.find(p => p.type === paramForm.source_period)
  return period?.price || 0
})

// 计算目标时段价格
const targetPrice = computed(() => {
  const period = targetPeriods.value.find(p => p.type === paramForm.target_period)
  return period?.price || 0
})

// 是否有变化
const hasChanges = computed(() => {
  const params = props.suggestion.parameters
  if (!params) return false

  const defaultDevices = params.adjustable_params?.find((p: any) => p.key === 'selected_devices')?.current_value || []
  const defaultHours = params.default_shift_hours || 2

  return (
    JSON.stringify(paramForm.selected_devices.sort()) !== JSON.stringify([...defaultDevices].sort()) ||
    paramForm.shift_hours !== defaultHours ||
    paramForm.source_period !== (params.sharp_price ? 'sharp' : 'peak') ||
    paramForm.target_period !== 'valley'
  )
})

onMounted(async () => {
  await loadData()
  initFormFromSuggestion()
  // 初始计算
  await doRecalculate()
})

async function loadData() {
  try {
    // 加载电价配置
    const pricingRes = await getCurrentPricing()
    if (pricingRes.code === 0 && pricingRes.data) {
      const allPeriods = pricingRes.data.time_periods || []
      sourcePeriods.value = allPeriods.filter(p => ['sharp', 'peak'].includes(p.type))
      targetPeriods.value = allPeriods.filter(p => ['valley', 'deep_valley', 'normal'].includes(p.type))
    }

    // 加载可转移设备
    const devicesRes = await getShiftableDevices()
    if (devicesRes.code === 0 && devicesRes.data) {
      shiftableDevices.value = devicesRes.data.devices || []
    }
  } catch (e) {
    console.error('加载数据失败', e)
  }
}

function initFormFromSuggestion() {
  const params = props.suggestion.parameters
  if (!params) return

  // 初始化设备选择
  const deviceParam = params.adjustable_params?.find((p: any) => p.key === 'selected_devices')
  if (deviceParam?.current_value) {
    paramForm.selected_devices = [...deviceParam.current_value]
  } else if (shiftableDevices.value.length > 0) {
    // 默认选择前3个设备
    paramForm.selected_devices = shiftableDevices.value.slice(0, 3).map(d => d.device_id)
  }

  // 初始化转移时长
  paramForm.shift_hours = params.default_shift_hours || 2

  // 初始化时段
  paramForm.source_period = params.sharp_price ? 'sharp' : 'peak'
  paramForm.target_period = 'valley'
}

// 防抖重算
const debouncedRecalculate = debounce(async () => {
  await doRecalculate()
}, 500)

async function doRecalculate() {
  if (paramForm.selected_devices.length === 0) {
    // 清空结果
    Object.assign(calculationResult, {
      total_power: 0,
      price_diff: 0,
      daily_energy: 0,
      daily_saving: 0,
      annual_saving: 0,
      annual_saving_wan: 0,
      steps: [],
      pricing_used: null
    })
    return
  }

  calculating.value = true
  try {
    const res = await recalculateSuggestion(props.suggestion.id, {
      selected_devices: paramForm.selected_devices,
      shift_hours: paramForm.shift_hours,
      source_period: paramForm.source_period,
      target_period: paramForm.target_period
    })

    if (res.code === 0 && res.data) {
      const data = res.data
      calculationResult.total_power = data.devices_used?.reduce((sum, d) => sum + (d.shiftable_power || 0), 0) || 0
      calculationResult.price_diff = (data.pricing_used?.source?.price || 0) - (data.pricing_used?.target?.price || 0)
      calculationResult.daily_energy = data.effects?.daily_energy_kwh || 0
      calculationResult.daily_saving = data.effects?.daily_saving_yuan || 0
      calculationResult.annual_saving = data.effects?.annual_saving_yuan || 0
      calculationResult.annual_saving_wan = data.effects?.annual_saving_wan || 0
      calculationResult.steps = data.calculation_steps || []
      calculationResult.pricing_used = data.pricing_used

      // 通知父组件
      emit('paramsChanged', { ...paramForm }, data.effects)
    }
  } catch (e) {
    console.error('重算失败', e)
  } finally {
    calculating.value = false
  }
}

function handleParamChange() {
  debouncedRecalculate()
}

function formatHours(hours: number[]): string {
  if (!hours || hours.length === 0) return '全天'
  // 合并连续时段
  const ranges: string[] = []
  let start = hours[0]
  let end = hours[0]

  for (let i = 1; i <= hours.length; i++) {
    if (i < hours.length && hours[i] === end + 1) {
      end = hours[i]
    } else {
      ranges.push(start === end ? `${start}:00` : `${start}:00-${end + 1}:00`)
      if (i < hours.length) {
        start = hours[i]
        end = hours[i]
      }
    }
  }
  return ranges.join(', ')
}

// 暴露给父组件
defineExpose({
  getParams: () => ({ ...paramForm }),
  getEffects: () => ({
    daily_energy_kwh: calculationResult.daily_energy,
    daily_saving_yuan: calculationResult.daily_saving,
    annual_saving_yuan: calculationResult.annual_saving
  })
})
</script>

<style scoped lang="scss">
.parameter-adjustment {
  .data-source-tip {
    margin-bottom: 20px;
    background: rgba(24, 144, 255, 0.1);
    border-color: rgba(24, 144, 255, 0.3);
  }

  .param-form {
    .device-select-container {
      max-height: 200px;
      overflow-y: auto;
      padding: 8px;
      background: var(--bg-color-overlay, rgba(0, 0, 0, 0.2));
      border-radius: 4px;
    }

    .device-checkbox-item {
      display: flex;
      align-items: center;
      padding: 8px 0;
      border-bottom: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));

      &:last-child {
        border-bottom: none;
      }

      .device-name {
        margin-right: 8px;
      }

      .info-icon {
        margin-left: 8px;
        color: var(--text-secondary, rgba(255, 255, 255, 0.65));
        cursor: help;
      }
    }

    .no-devices {
      padding: 20px;
      text-align: center;
    }

    .slider-container {
      display: flex;
      align-items: center;
      gap: 16px;

      .el-slider {
        flex: 1;
      }

      .hours-input {
        width: 100px;
      }

      .unit {
        color: var(--text-secondary, rgba(255, 255, 255, 0.65));
      }
    }

    .period-select {
      width: 100%;
    }

    .period-price {
      float: right;
      color: var(--success-color, #52c41a);
    }

    .period-hint {
      margin-left: 12px;
      font-size: 12px;
      color: var(--text-secondary, rgba(255, 255, 255, 0.65));
    }
  }

  .calculation-result {
    margin-top: 20px;
    background: var(--bg-card-solid, #1a2a4a);

    .result-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .value {
      font-weight: bold;
      color: var(--text-primary, rgba(255, 255, 255, 0.95));

      &.highlight {
        color: var(--success-color, #52c41a);
      }

      &.large {
        font-size: 18px;
      }
    }

    .sub-value {
      margin-left: 8px;
      color: var(--text-secondary, rgba(255, 255, 255, 0.65));
    }

    .steps-collapse {
      margin-top: 16px;
    }

    .calculation-steps {
      padding-left: 20px;
      line-height: 2;

      li {
        color: var(--text-regular, rgba(255, 255, 255, 0.85));
      }
    }

    .pricing-source {
      margin-top: 12px;
      padding: 12px;
      background: var(--bg-color-overlay, rgba(0, 0, 0, 0.2));
      border-radius: 4px;

      p {
        margin: 4px 0;
      }
    }
  }
}
</style>
