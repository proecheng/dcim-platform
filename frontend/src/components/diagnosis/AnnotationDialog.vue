<template>
  <el-dialog
    v-model="visible"
    title="诊断结果标注"
    width="600px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="120px"
    >
      <el-form-item label="会话ID">
        <el-input v-model="sessionId" disabled />
      </el-form-item>

      <el-form-item label="标注结果" prop="annotation">
        <el-radio-group v-model="form.annotation">
          <el-radio value="accurate">准确</el-radio>
          <el-radio value="inaccurate">不准确</el-radio>
          <el-radio value="unknown">未知</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item
        v-if="form.annotation === 'inaccurate'"
        label="实际根因"
        prop="actual_root_cause"
      >
        <el-input
          v-model="form.actual_root_cause"
          type="textarea"
          :rows="3"
          maxlength="1000"
          show-word-limit
          placeholder="请描述实际根因"
        />
      </el-form-item>

      <el-form-item label="备注" prop="notes">
        <el-input
          v-model="form.notes"
          type="textarea"
          :rows="3"
          maxlength="2000"
          show-word-limit
          placeholder="可选，补充说明"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button
        type="primary"
        :loading="submitLoading"
        @click="handleSubmit"
      >
        提交
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { createDiagnosisAnnotation, type DiagnosisAnnotationCreate } from '@/api/modules/diagnosis'

interface Props {
  sessionId: number
}

const props = defineProps<Props>()

const emit = defineEmits<{
  success: []
}>()

const visible = ref(false)
const submitLoading = ref(false)
const formRef = ref<FormInstance>()

const form = reactive<DiagnosisAnnotationCreate>({
  session_id: props.sessionId,
  annotation: 'accurate',
  actual_root_cause: undefined,
  notes: undefined,
})

const rules: FormRules = {
  annotation: [
    { required: true, message: '请选择标注结果', trigger: 'change' },
  ],
  actual_root_cause: [
    {
      validator: (_rule, value, callback) => {
        if (form.annotation === 'inaccurate' && !value) {
          callback(new Error('标注为不准确时，必须填写实际根因'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

// 监听 annotation 变化，清空 actual_root_cause
watch(() => form.annotation, (newVal) => {
  if (newVal !== 'inaccurate') {
    form.actual_root_cause = undefined
  }
})

const open = () => {
  visible.value = true
  form.session_id = props.sessionId
  form.annotation = 'accurate'
  form.actual_root_cause = undefined
  form.notes = undefined
}

const handleClose = () => {
  visible.value = false
  formRef.value?.resetFields()
}

const handleSubmit = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    submitLoading.value = true
    try {
      await createDiagnosisAnnotation(form)
      ElMessage.success('标注提交成功')
      emit('success')
      handleClose()
    } catch (error: any) {
      ElMessage.error(error.message || '标注提交失败')
    } finally {
      submitLoading.value = false
    }
  })
}

defineExpose({
  open,
})
</script>
