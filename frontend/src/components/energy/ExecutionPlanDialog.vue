<template>
  <el-dialog
    v-model="visible"
    title="确认执行方案"
    width="520px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <el-form ref="formRef" :model="formData" :rules="rules" label-width="100px">
      <el-form-item label="方案名称" prop="planName">
        <el-input v-model="formData.planName" placeholder="请输入方案名称" maxlength="50" show-word-limit />
      </el-form-item>

      <el-form-item label="优化策略">
        <el-tag :type="props.strategy === 'max_benefit' ? 'success' : 'info'">
          {{ props.strategy === 'max_benefit' ? '效益最大化' : '成本最小化' }}
        </el-tag>
      </el-form-item>

      <el-form-item label="预期收益">
        <div class="saving-preview">
          <div class="saving-item">
            <span class="label">日节省</span>
            <span class="value">¥{{ props.dailySaving.toFixed(2) }}</span>
          </div>
          <div class="saving-item">
            <span class="label">年节省</span>
            <span class="value highlight">¥{{ formatNumber(props.annualSaving) }}</span>
          </div>
        </div>
      </el-form-item>

      <el-form-item label="涉及设备">
        <div class="device-tags">
          <el-tag v-for="device in props.deviceRules" :key="device.deviceId" size="small" class="device-tag">
            {{ device.deviceName }}
          </el-tag>
        </div>
      </el-form-item>

      <el-form-item label="备注" prop="remark">
        <el-input
          v-model="formData.remark"
          type="textarea"
          :rows="2"
          placeholder="可选，添加备注信息"
          maxlength="200"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleConfirm">
        确认创建执行计划
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, reactive, computed } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'

interface DeviceRule {
  deviceId: number
  deviceName: string
  rules: Array<{
    sourcePeriod: string
    targetPeriod: string
    power: number
    hours: number
  }>
}

const props = withDefaults(defineProps<{
  modelValue: boolean
  strategy: 'max_benefit' | 'min_cost'
  dailySaving: number
  annualSaving: number
  deviceRules: DeviceRule[]
}>(), {
  dailySaving: 0,
  annualSaving: 0,
  deviceRules: () => []
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'confirm', data: { planName: string; remark: string }): void
}>()

const visible = ref(props.modelValue)
const formRef = ref<FormInstance>()
const submitting = ref(false)

const formData = reactive({
  planName: '',
  remark: ''
})

const rules: FormRules = {
  planName: [
    { required: true, message: '请输入方案名称', trigger: 'blur' },
    { min: 2, max: 50, message: '名称长度在2-50个字符之间', trigger: 'blur' }
  ]
}

// 生成默认计划名称
function generateDefaultName(): string {
  const now = new Date()
  const dateStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
  return `负荷转移方案 - ${dateStr} ${timeStr}`
}

function formatNumber(num: number): string {
  return num >= 10000 ? (num / 10000).toFixed(2) + '万' : num.toFixed(0)
}

watch(() => props.modelValue, (val) => {
  visible.value = val
  if (val) {
    formData.planName = generateDefaultName()
    formData.remark = ''
    submitting.value = false  // Reset on open
  }
})

watch(visible, (val) => {
  emit('update:modelValue', val)
})

function handleClose() {
  visible.value = false
}

async function handleConfirm() {
  console.log('[ExecutionPlanDialog] handleConfirm called')
  if (!formRef.value) {
    console.log('[ExecutionPlanDialog] formRef is null')
    return
  }

  try {
    console.log('[ExecutionPlanDialog] Validating form...')
    await formRef.value.validate()
    console.log('[ExecutionPlanDialog] Form validation passed')
    submitting.value = true
    console.log('[ExecutionPlanDialog] Emitting confirm event with:', {
      planName: formData.planName,
      remark: formData.remark
    })
    emit('confirm', {
      planName: formData.planName,
      remark: formData.remark
    })
  } catch (e) {
    console.log('[ExecutionPlanDialog] Form validation failed:', e)
    // Validation failed, do nothing
  }
}

// 暴露方法供父组件调用
defineExpose({
  setSubmitting: (val: boolean) => { submitting.value = val }
})
</script>

<style scoped lang="scss">
.saving-preview {
  display: flex;
  gap: 24px;

  .saving-item {
    display: flex;
    flex-direction: column;

    .label {
      font-size: 12px;
      color: var(--text-secondary);
    }

    .value {
      font-size: 18px;
      font-weight: 600;
      color: var(--text-primary);

      &.highlight {
        color: var(--success-color);
        font-size: 22px;
      }
    }
  }
}

.device-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;

  .device-tag {
    margin: 0;
  }
}
</style>
