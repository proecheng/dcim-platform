<template>
  <div class="constraint-editor">
    <el-form :model="constraint" label-width="120px">
      <el-form-item label="约束类型">
        <el-select v-model="constraint.type" placeholder="请选择约束类型" @change="handleTypeChange">
          <el-option label="设备约束" value="device" />
          <el-option label="时间约束" value="time" />
          <el-option label="功率约束" value="power" />
          <el-option label="三相平衡" value="phase_balance" />
          <el-option label="温度约束" value="temperature" />
          <el-option label="设备寿命" value="device_lifetime" />
          <el-option label="算力中心负载占比" value="datacenter_load" />
          <el-option label="UPS容量约束" value="ups_capacity" />
        </el-select>
      </el-form-item>

      <el-form-item label="约束名称">
        <el-input v-model="constraint.name" placeholder="请输入约束名称" />
      </el-form-item>

      <el-form-item label="约束描述">
        <el-input v-model="constraint.description" type="textarea" :rows="2" placeholder="请输入约束描述" />
      </el-form-item>

      <!-- 设备约束 -->
      <template v-if="constraint.type === 'device'">
        <el-form-item label="设备选择">
          <el-select v-model="constraint.params.device_ids" multiple placeholder="请选择设备">
            <el-option
              v-for="device in availableDevices"
              :key="device.id"
              :label="device.name"
              :value="device.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="约束条件">
          <el-select v-model="constraint.params.condition" placeholder="请选择条件">
            <el-option label="不可同时转移" value="not_simultaneous" />
            <el-option label="必须同时转移" value="must_simultaneous" />
            <el-option label="转移顺序限制" value="sequence_required" />
          </el-select>
        </el-form-item>
      </template>

      <!-- 时间约束 -->
      <template v-if="constraint.type === 'time'">
        <el-form-item label="时间范围">
          <el-time-picker
            v-model="constraint.params.time_range"
            is-range
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            format="HH:mm"
          />
        </el-form-item>
        <el-form-item label="星期限制">
          <el-checkbox-group v-model="constraint.params.weekdays">
            <el-checkbox :label="1">周一</el-checkbox>
            <el-checkbox :label="2">周二</el-checkbox>
            <el-checkbox :label="3">周三</el-checkbox>
            <el-checkbox :label="4">周四</el-checkbox>
            <el-checkbox :label="5">周五</el-checkbox>
            <el-checkbox :label="6">周六</el-checkbox>
            <el-checkbox :label="7">周日</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </template>

      <!-- 功率约束 -->
      <template v-if="constraint.type === 'power'">
        <el-form-item label="最小转移功率">
          <el-input-number v-model="constraint.params.min_power" :min="0" :step="10" />
          <span style="margin-left: 10px">kW</span>
        </el-form-item>
        <el-form-item label="最大转移功率">
          <el-input-number v-model="constraint.params.max_power" :min="0" :step="10" />
          <span style="margin-left: 10px">kW</span>
        </el-form-item>
        <el-form-item label="功率变化率限制">
          <el-input-number v-model="constraint.params.max_power_rate" :min="0" :max="100" :step="5" />
          <span style="margin-left: 10px">% / 分钟</span>
        </el-form-item>
      </template>

      <!-- 三相平衡约束 -->
      <template v-if="constraint.type === 'phase_balance'">
        <el-form-item label="最大不平衡度">
          <el-input-number v-model="constraint.params.max_imbalance" :min="0" :max="30" :step="1" :precision="1" />
          <span style="margin-left: 10px">%（建议 &lt;10%）</span>
        </el-form-item>
        <el-form-item label="检查范围">
          <el-select v-model="constraint.params.check_scope" placeholder="请选择检查范围">
            <el-option label="单个配电柜" value="single_cabinet" />
            <el-option label="整个配电系统" value="entire_system" />
          </el-select>
        </el-form-item>
      </template>

      <!-- 温度约束 -->
      <template v-if="constraint.type === 'temperature'">
        <el-form-item label="最高温度限制">
          <el-input-number v-model="constraint.params.max_temp" :min="0" :max="50" :step="1" :precision="1" />
          <span style="margin-left: 10px">°C</span>
        </el-form-item>
        <el-form-item label="温度上升速率限制">
          <el-input-number v-model="constraint.params.max_temp_rate" :min="0" :max="10" :step="0.5" :precision="1" />
          <span style="margin-left: 10px">°C / 分钟</span>
        </el-form-item>
      </template>

      <!-- 设备寿命约束 -->
      <template v-if="constraint.type === 'device_lifetime'">
        <el-form-item label="最大启停次数">
          <el-input-number v-model="constraint.params.max_start_stop_count" :min="0" :step="1" />
          <span style="margin-left: 10px">次 / 天</span>
        </el-form-item>
        <el-form-item label="最小运行间隔">
          <el-input-number v-model="constraint.params.min_run_interval" :min="0" :step="5" />
          <span style="margin-left: 10px">分钟</span>
        </el-form-item>
        <el-form-item label="寿命损失系数">
          <el-input-number v-model="constraint.params.lifetime_loss_factor" :min="0" :max="1" :step="0.01" :precision="2" />
          <span style="margin-left: 10px">（0-1，建议 0.15-0.25）</span>
        </el-form-item>
      </template>

      <!-- 算力中心负载占比约束 -->
      <template v-if="constraint.type === 'datacenter_load'">
        <el-form-item label="IT负载占比范围">
          <el-input-number v-model="constraint.params.it_load_ratio_min" :min="0.5" :max="0.95" :step="0.01" :precision="2" />
          <span style="margin: 0 8px">~</span>
          <el-input-number v-model="constraint.params.it_load_ratio_max" :min="0.5" :max="0.95" :step="0.01" :precision="2" />
        </el-form-item>
        <el-form-item label="制冷占比">
          <el-input-number v-model="constraint.params.cooling_ratio" :min="0" :max="1" :step="0.01" :precision="2" />
        </el-form-item>
        <el-form-item label="配电占比">
          <el-input-number v-model="constraint.params.distribution_ratio" :min="0" :max="1" :step="0.01" :precision="2" />
        </el-form-item>
        <el-form-item label="其他占比">
          <el-input-number v-model="constraint.params.other_ratio" :min="0" :max="1" :step="0.01" :precision="2" />
        </el-form-item>
        <el-form-item label="制冷可转移系数">
          <el-input-number v-model="constraint.params.cooling_transferable_ratio" :min="0" :max="1" :step="0.01" :precision="2" />
        </el-form-item>
        <el-form-item label="其他可转移系数">
          <el-input-number v-model="constraint.params.other_transferable_ratio" :min="0" :max="1" :step="0.01" :precision="2" />
        </el-form-item>
        <el-form-item label="总功率估值">
          <el-input-number v-model="constraint.params.total_power" :min="0" :step="10" />
          <span style="margin-left: 10px">kW</span>
        </el-form-item>
        <el-alert
          v-if="datacenterPreview"
          :type="datacenterPreview.ratioSumValid ? 'success' : 'warning'"
          :title="`可转移上限约 ${datacenterPreview.maxTransferPower.toFixed(1)} kW`"
          :description="`占比合计(按上限近似): ${(datacenterPreview.ratioSum * 100).toFixed(1)}%`"
          show-icon
          :closable="false"
        />
      </template>

      <!-- UPS容量约束 -->
      <template v-if="constraint.type === 'ups_capacity'">
        <el-form-item label="UPS设备">
          <el-select v-model="constraint.params.ups_device_ids" multiple placeholder="请选择UPS设备">
            <el-option v-for="device in availableDevices" :key="device.id" :label="device.name" :value="device.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="安全系数">
          <el-input-number v-model="constraint.params.safety_factor" :min="0.1" :max="0.99" :step="0.01" :precision="2" />
        </el-form-item>
        <el-form-item label="当前负载估值">
          <el-input-number v-model="constraint.params.current_load" :min="0" :step="10" />
          <span style="margin-left: 10px">kW</span>
        </el-form-item>
        <el-form-item label="目标转移功率">
          <el-input-number v-model="constraint.params.target_shift_power" :min="0" :step="10" />
          <span style="margin-left: 10px">kW</span>
        </el-form-item>
        <el-form-item label="超限策略">
          <el-switch v-model="constraint.params.auto_adjust" active-text="自动降功率" />
          <span style="margin: 0 12px"></span>
          <el-switch v-model="constraint.params.reject_on_exceed" active-text="超限直接拒绝" />
        </el-form-item>
        <el-alert
          v-if="upsPreview"
          :type="upsPreview.overload ? 'error' : 'success'"
          :title="upsPreview.overload ? '容量超限' : '容量充足'"
          :description="`转移后峰值 ${upsPreview.projected.toFixed(1)} kW / 允许上限 ${upsPreview.allowed.toFixed(1)} kW`"
          show-icon
          :closable="false"
        />
      </template>

      <el-form-item label="约束优先级">
        <el-radio-group v-model="constraint.priority">
          <el-radio label="high">高</el-radio>
          <el-radio label="medium">中</el-radio>
          <el-radio label="low">低</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="启用状态">
        <el-switch v-model="constraint.enabled" />
      </el-form-item>

      <el-form-item>
        <el-button type="primary" @click="handleSave">保存</el-button>
        <el-button @click="handleCancel">取消</el-button>
        <el-button type="info" @click="handleValidate">验证约束</el-button>
      </el-form-item>
    </el-form>

    <el-card shadow="hover" style="margin-top: 20px" v-if="validationResult">
      <template #header>
        <span>验证结果</span>
      </template>
      <el-alert
        :title="validationResult.valid ? '约束配置有效' : '约束配置无效'"
        :type="validationResult.valid ? 'success' : 'error'"
        :description="validationResult.message"
        show-icon
        :closable="false"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'

interface Constraint {
  id?: number
  type: string
  name: string
  description: string
  params: Record<string, any>
  priority: string
  enabled: boolean
}

const props = defineProps<{
  modelValue?: Constraint
  availableDevices?: Array<{ id: number; name: string; rated_power?: number }>
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: Constraint): void
  (e: 'save', value: Constraint): void
  (e: 'cancel'): void
}>()

const constraint = reactive<Constraint>({
  type: '',
  name: '',
  description: '',
  params: {},
  priority: 'medium',
  enabled: true,
  ...props.modelValue
})

const validationResult = ref<{ valid: boolean; message: string } | null>(null)

watch(
  () => props.modelValue,
  (newValue) => {
    if (newValue) {
      Object.assign(constraint, newValue)
    }
  },
  { deep: true }
)

watch(
  constraint,
  (newValue) => {
    emit('update:modelValue', newValue)
  },
  { deep: true }
)

const handleTypeChange = () => {
  // 重置参数
  switch (constraint.type) {
    case 'datacenter_load':
      constraint.params = {
        it_load_ratio_min: 0.6,
        it_load_ratio_max: 0.8,
        cooling_ratio: 0.2,
        distribution_ratio: 0.04,
        other_ratio: 0.06,
        cooling_transferable_ratio: 0.4,
        other_transferable_ratio: 0.6,
        total_power: 1000,
      }
      break
    case 'ups_capacity':
      constraint.params = {
        ups_device_ids: [],
        safety_factor: 0.8,
        current_load: 500,
        target_shift_power: 100,
        auto_adjust: true,
        reject_on_exceed: true,
      }
      break
    default:
      constraint.params = {}
  }
  validationResult.value = null
}

const datacenterPreview = computed(() => {
  if (constraint.type !== 'datacenter_load') return null
  const p = constraint.params || {}
  const totalPower = Number(p.total_power || 1000)
  const coolingRatio = Number(p.cooling_ratio ?? 0.2)
  const otherRatio = Number(p.other_ratio ?? 0.06)
  const coolingTransferableRatio = Number(p.cooling_transferable_ratio ?? 0.4)
  const otherTransferableRatio = Number(p.other_transferable_ratio ?? 0.6)
  const maxTransferPower = totalPower * (coolingRatio * coolingTransferableRatio + otherRatio * otherTransferableRatio)
  const ratioSum =
    Number(p.it_load_ratio_max ?? 0.8) +
    Number(p.cooling_ratio ?? 0.2) +
    Number(p.distribution_ratio ?? 0.04) +
    Number(p.other_ratio ?? 0.06)
  return {
    totalPower,
    maxTransferPower,
    ratioSum,
    ratioSumValid: Math.abs(ratioSum - 1) < 0.15,
  }
})

const upsPreview = computed(() => {
  if (constraint.type !== 'ups_capacity') return null
  const p = constraint.params || {}
  const selectedIds: number[] = Array.isArray(p.ups_device_ids) ? p.ups_device_ids : []
  const selected = (props.availableDevices || []).filter((d) => selectedIds.includes(d.id))
  const totalUpsCapacity = selected.reduce((sum, d) => sum + Number(d.rated_power || 100), 0)
  const safetyFactor = Number(p.safety_factor ?? 0.8)
  const currentLoad = Number(p.current_load ?? 500)
  const targetShiftPower = Number(p.target_shift_power ?? 100)
  const allowed = totalUpsCapacity * safetyFactor
  const projected = currentLoad + targetShiftPower
  return {
    totalUpsCapacity,
    safetyFactor,
    currentLoad,
    projected,
    allowed,
    overload: projected > allowed,
  }
})

const handleSave = () => {
  if (!constraint.type) {
    ElMessage.error('请选择约束类型')
    return
  }
  if (!constraint.name) {
    ElMessage.error('请输入约束名称')
    return
  }
  emit('save', constraint)
}

const handleCancel = () => {
  emit('cancel')
}

const handleValidate = () => {
  // 验证约束配置
  let valid = true
  let message = ''

  if (!constraint.type) {
    valid = false
    message = '请选择约束类型'
  } else if (!constraint.name) {
    valid = false
    message = '请输入约束名称'
  } else {
    // 根据类型验证参数
    switch (constraint.type) {
      case 'device':
        if (!constraint.params.device_ids || constraint.params.device_ids.length === 0) {
          valid = false
          message = '请选择至少一个设备'
        } else if (!constraint.params.condition) {
          valid = false
          message = '请选择约束条件'
        }
        break
      case 'time':
        if (!constraint.params.time_range || constraint.params.time_range.length !== 2) {
          valid = false
          message = '请选择时间范围'
        }
        break
      case 'power':
        if (constraint.params.min_power >= constraint.params.max_power) {
          valid = false
          message = '最小功率必须小于最大功率'
        }
        break
      case 'phase_balance':
        if (!constraint.params.max_imbalance || constraint.params.max_imbalance <= 0) {
          valid = false
          message = '请设置最大不平衡度'
        } else if (constraint.params.max_imbalance > 10) {
          message = '警告：不平衡度超过 10% 可能影响设备安全'
        }
        break
      case 'temperature':
        if (!constraint.params.max_temp || constraint.params.max_temp <= 0) {
          valid = false
          message = '请设置最高温度限制'
        }
        break
      case 'device_lifetime':
        if (!constraint.params.max_start_stop_count || constraint.params.max_start_stop_count <= 0) {
          valid = false
          message = '请设置最大启停次数'
        }
        break
      case 'datacenter_load':
        if (constraint.params.it_load_ratio_min >= constraint.params.it_load_ratio_max) {
          valid = false
          message = 'IT负载占比最小值必须小于最大值'
        }
        break
      case 'ups_capacity':
        if (!constraint.params.ups_device_ids || constraint.params.ups_device_ids.length === 0) {
          valid = false
          message = '请至少选择一个UPS设备'
        } else if (!constraint.params.safety_factor || constraint.params.safety_factor <= 0 || constraint.params.safety_factor >= 1) {
          valid = false
          message = '安全系数必须在 0~1 之间'
        }
        break
    }
  }

  if (valid && !message) {
    message = '约束配置有效，可以保存'
  }

  validationResult.value = { valid, message }
}
</script>

<style scoped lang="scss">
.constraint-editor {
  padding: 20px;
}
</style>
