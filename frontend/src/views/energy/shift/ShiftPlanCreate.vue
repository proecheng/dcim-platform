<template>
  <div class="shift-plan-create">
    <el-page-header @back="$router.back()" title="返回">
      <template #content>
        <span>{{ isEdit ? '编辑计划' : '新建计划' }}</span>
      </template>
    </el-page-header>

    <el-card shadow="hover" style="margin-top: 20px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="140px">
        <el-form-item label="计划名称" prop="plan_name">
          <el-input v-model="form.plan_name" placeholder="请输入计划名称" style="width: 400px" />
        </el-form-item>

        <el-form-item label="转移日期" prop="shift_date">
          <el-date-picker
            v-model="form.shift_date"
            type="date"
            placeholder="选择转移日期"
            value-format="YYYY-MM-DD"
            style="width: 400px"
          />
        </el-form-item>

        <el-form-item label="转出时段" prop="shift_from_period">
          <el-select v-model="form.shift_from_period" placeholder="选择转出时段" style="width: 400px">
            <el-option label="尖峰" value="peak" />
            <el-option label="高峰" value="sharp" />
            <el-option label="平段" value="flat" />
          </el-select>
        </el-form-item>

        <el-form-item label="转入时段" prop="shift_to_period">
          <el-select v-model="form.shift_to_period" placeholder="选择转入时段" style="width: 400px">
            <el-option label="平段" value="flat" />
            <el-option label="谷段" value="valley" />
          </el-select>
        </el-form-item>

        <el-form-item label="转移时间" required>
          <el-col :span="11">
            <el-form-item prop="start_time">
              <el-time-picker
                v-model="form.start_time"
                placeholder="开始时间"
                format="HH:mm:ss"
                value-format="HH:mm:ss"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="2" style="text-align: center">-</el-col>
          <el-col :span="11">
            <el-form-item prop="end_time">
              <el-time-picker
                v-model="form.end_time"
                placeholder="结束时间"
                format="HH:mm:ss"
                value-format="HH:mm:ss"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-form-item>

        <el-form-item label="目标转移功率" prop="target_shift_power">
          <el-input-number
            v-model="form.target_shift_power"
            :min="0"
            :precision="1"
            placeholder="请输入目标转移功率"
            style="width: 400px"
          />
          <span style="margin-left: 10px">kW</span>
        </el-form-item>

        <el-form-item label="选择设备" prop="selected_devices">
          <el-button type="primary" @click="deviceSelectorVisible = true">选择设备</el-button>
          <span style="margin-left: 10px">已选 {{ form.selected_devices.length }} 个设备</span>
        </el-form-item>

        <el-form-item label="预期成本节省">
          <el-input-number
            v-model="form.expected_cost_saving"
            :min="0"
            :precision="0"
            placeholder="预期成本节省"
            style="width: 400px"
          />
          <span style="margin-left: 10px">元</span>
        </el-form-item>

        <el-form-item label="预期节能量">
          <el-input-number
            v-model="form.expected_energy_saving"
            :min="0"
            :precision="0"
            placeholder="预期节能量"
            style="width: 400px"
          />
          <span style="margin-left: 10px">kWh</span>
        </el-form-item>

        <el-form-item label="计划描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="4"
            placeholder="请输入计划描述"
            style="width: 600px"
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleSubmit" :loading="submitting">保存</el-button>
          <el-button @click="handleAnalyze" :loading="analyzing">可行性分析</el-button>
          <el-button @click="$router.back()">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-dialog v-model="deviceSelectorVisible" title="选择设备" width="800px">
      <DeviceSelector v-model="form.selected_devices" />
      <template #footer>
        <el-button @click="deviceSelectorVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="analysisResultVisible" title="可行性分析结果" width="700px">
      <ConstraintCheckResult v-if="analysisResult" :result="analysisResult" />
      <template #footer>
        <el-button @click="analysisResultVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { getShiftPlan, createShiftPlan, updateShiftPlan, analyzeFeasibility } from '@/api/modules/shift'
import DeviceSelector from './components/DeviceSelector.vue'
import ConstraintCheckResult from './components/ConstraintCheckResult.vue'

const route = useRoute()
const router = useRouter()

const isEdit = ref(false)
const formRef = ref<FormInstance>()
const submitting = ref(false)
const analyzing = ref(false)
const deviceSelectorVisible = ref(false)
const analysisResultVisible = ref(false)
const analysisResult = ref<any>(null)

const form = reactive({
  plan_name: '',
  shift_date: '',
  shift_from_period: '',
  shift_to_period: '',
  start_time: '',
  end_time: '',
  target_shift_power: 0,
  selected_devices: [] as number[],
  expected_cost_saving: 0,
  expected_energy_saving: 0,
  description: '',
})

const rules: FormRules = {
  plan_name: [{ required: true, message: '请输入计划名称', trigger: 'blur' }],
  shift_date: [{ required: true, message: '请选择转移日期', trigger: 'change' }],
  shift_from_period: [{ required: true, message: '请选择转出时段', trigger: 'change' }],
  shift_to_period: [{ required: true, message: '请选择转入时段', trigger: 'change' }],
  start_time: [{ required: true, message: '请选择开始时间', trigger: 'change' }],
  end_time: [{ required: true, message: '请选择结束时间', trigger: 'change' }],
  target_shift_power: [{ required: true, message: '请输入目标转移功率', trigger: 'blur' }],
}

const loadPlan = async () => {
  try {
    const id = Number(route.params.id)
    const res = await getShiftPlan(id)
    const plan = res.data || {}
    Object.assign(form, {
      plan_name: plan.plan_name,
      shift_date: plan.shift_date,
      shift_from_period: plan.shift_from_period,
      shift_to_period: plan.shift_to_period,
      start_time: plan.start_time,
      end_time: plan.end_time,
      target_shift_power: plan.target_shift_power,
      selected_devices: plan.selected_devices || [],
      expected_cost_saving: plan.expected_cost_saving,
      expected_energy_saving: plan.expected_energy_saving,
      description: plan.description,
    })
  } catch (error: any) {
    ElMessage.error(error.message || '加载计划失败')
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return

    submitting.value = true
    try {
      if (isEdit.value) {
        await updateShiftPlan(Number(route.params.id), form)
        ElMessage.success('更新成功')
      } else {
        await createShiftPlan(form)
        ElMessage.success('创建成功')
      }
      router.back()
    } catch (error: any) {
      ElMessage.error(error.message || '保存失败')
    } finally {
      submitting.value = false
    }
  })
}

const handleAnalyze = async () => {
  if (!form.shift_date || !form.shift_from_period || !form.shift_to_period || !form.target_shift_power) {
    ElMessage.warning('请先填写转移日期、时段和目标功率')
    return
  }

  analyzing.value = true
  try {
    const res = await analyzeFeasibility({
      shift_date: form.shift_date,
      shift_from_period: form.shift_from_period,
      shift_to_period: form.shift_to_period,
      target_shift_power: form.target_shift_power,
      selected_devices: form.selected_devices,
    })
    analysisResult.value = res.data
    analysisResultVisible.value = true
  } catch (error: any) {
    ElMessage.error(error.message || '分析失败')
  } finally {
    analyzing.value = false
  }
}

onMounted(() => {
  if (route.params.id) {
    isEdit.value = true
    loadPlan()
  }
})
</script>

<style scoped lang="scss">
.shift-plan-create {
  // styles
}
</style>
