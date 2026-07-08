<template>
  <el-dialog
    v-model="visible"
    title="电价方案管理"
    width="1200px"
    :before-close="handleClose"
    class="pricing-scheme-manager"
  >
    <div class="manager-content">
      <!-- 工具栏 -->
      <div class="toolbar">
        <el-button type="primary" @click="handleCreate">
          <el-icon><Plus /></el-icon>
          新建方案
        </el-button>
        <el-button @click="loadSchemes">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>

      <!-- 方案列表 -->
      <el-table
        v-loading="loading"
        :data="schemes"
        stripe
        class="scheme-table"
      >
        <el-table-column prop="scheme_name" label="方案名称" min-width="150" />
        <el-table-column prop="description" label="说明" min-width="200" show-overflow-tooltip />
        <el-table-column label="生效日期" width="120">
          <template #default="{ row }">
            {{ formatDate(row.effective_date) }}
          </template>
        </el-table-column>
        <el-table-column label="失效日期" width="120">
          <template #default="{ row }">
            {{ row.expire_date ? formatDate(row.expire_date) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.is_active" type="success">已激活</el-tag>
            <el-tag v-else type="info">未激活</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="校验状态" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.validation_result?.valid" type="success">
              <el-icon><CircleCheck /></el-icon>
              有效
            </el-tag>
            <el-tag v-else-if="row.validation_result" type="danger">
              <el-icon><CircleClose /></el-icon>
              无效
            </el-tag>
            <el-tag v-else type="info">未校验</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="覆盖率" width="100">
          <template #default="{ row }">
            <span v-if="row.validation_result">
              {{ row.validation_result.coverage }}/24h
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="!row.is_active"
              type="success"
              size="small"
              @click="handleActivate(row)"
            >
              激活
            </el-button>
            <el-button
              v-else
              type="warning"
              size="small"
              @click="handleDeactivate(row)"
            >
              停用
            </el-button>
            <el-button size="small" @click="handleValidate(row)">
              校验
            </el-button>
            <el-button
              size="small"
              :disabled="row.is_active"
              @click="handleEdit(row)"
            >
              编辑
            </el-button>
            <el-button
              type="danger"
              size="small"
              :disabled="row.is_active"
              @click="handleDelete(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 创建/编辑对话框 -->
    <el-dialog
      v-model="formVisible"
      :title="formMode === 'create' ? '新建方案' : '编辑方案'"
      width="800px"
      append-to-body
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="120px"
      >
        <el-form-item label="方案名称" prop="scheme_name">
          <el-input v-model="formData.scheme_name" placeholder="请输入方案名称" />
        </el-form-item>
        <el-form-item label="方案说明" prop="description">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="3"
            placeholder="请输入方案说明"
          />
        </el-form-item>
        <el-form-item label="生效日期" prop="effective_date">
          <el-date-picker
            v-model="formData.effective_date"
            type="date"
            placeholder="选择生效日期"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item label="失效日期" prop="expire_date">
          <el-date-picker
            v-model="formData.expire_date"
            type="date"
            placeholder="选择失效日期（可选）"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item label="选择时段" prop="pricing_ids">
          <el-transfer
            v-model="formData.pricing_ids"
            :data="availablePricings"
            :titles="['可用时段', '已选时段']"
            :props="{
              key: 'id',
              label: 'label'
            }"
          />
        </el-form-item>
        <el-form-item>
          <PricingTimeline
            v-if="formData.pricing_ids.length > 0"
            :pricing-ids="formData.pricing_ids"
            :all-pricings="pricings"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Refresh, CircleCheck, CircleClose } from '@element-plus/icons-vue'
import {
  getPricingSchemes,
  createPricingScheme,
  updatePricingScheme,
  deletePricingScheme,
  validatePricingScheme,
  activatePricingScheme,
  deactivatePricingScheme,
  getElectricityPricings,
  type PricingScheme,
  type PricingSchemeCreate,
  type PricingSchemeUpdate,
  type ElectricityPricing
} from '@/api/modules/energy'
import PricingTimeline from './PricingTimeline.vue'

// Props
const props = defineProps<{
  modelValue: boolean
}>()

// Emits
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'scheme-activated': []
}>()

// 响应式数据
const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const loading = ref(false)
const schemes = ref<PricingScheme[]>([])
const pricings = ref<ElectricityPricing[]>([])

const formVisible = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const formRef = ref<FormInstance>()
const currentSchemeId = ref<number>()

const formData = ref<PricingSchemeCreate>({
  scheme_name: '',
  description: '',
  effective_date: '',
  expire_date: '',
  pricing_ids: []
})

const formRules: FormRules = {
  scheme_name: [
    { required: true, message: '请输入方案名称', trigger: 'blur' },
    { max: 100, message: '方案名称不能超过100个字符', trigger: 'blur' }
  ],
  effective_date: [
    { required: true, message: '请选择生效日期', trigger: 'change' }
  ],
  pricing_ids: [
    { required: true, message: '请至少选择一个时段', trigger: 'change', type: 'array', min: 1 }
  ]
}

// 可用时段列表（用于穿梭框）
const availablePricings = computed(() => {
  return pricings.value.map(p => ({
    id: p.id,
    label: `${p.pricing_name} (${p.start_time}-${p.end_time})`
  }))
})

// 方法
const loadSchemes = async () => {
  loading.value = true
  try {
    const res = await getPricingSchemes()
    const body = (res as any).data ?? res
    if (body.code === 200 || body.code === 0 || Array.isArray(body.data)) {
      schemes.value = body.data ?? []
    }
  } catch {
    ElMessage.error('加载方案列表失败')
  } finally {
    loading.value = false
  }
}

const loadPricings = async () => {
  try {
    const res = await getElectricityPricings()
    const body = (res as any).data ?? res
    if (body.code === 200 || body.code === 0 || Array.isArray(body.data)) {
      pricings.value = body.data ?? []
    }
  } catch {
    ElMessage.error('加载时段列表失败')
  }
}

const handleCreate = () => {
  formMode.value = 'create'
  formData.value = {
    scheme_name: '',
    description: '',
    effective_date: new Date().toISOString().split('T')[0],
    expire_date: '',
    pricing_ids: []
  }
  formVisible.value = true
}

const handleEdit = (row: PricingScheme) => {
  formMode.value = 'edit'
  currentSchemeId.value = row.id
  formData.value = {
    scheme_name: row.scheme_name,
    description: row.description || '',
    effective_date: row.effective_date,
    expire_date: row.expire_date || '',
    pricing_ids: [] // TODO: 需要从后端获取关联的时段ID
  }
  formVisible.value = true
}

const handleSubmit = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    try {
      if (formMode.value === 'create') {
        const res = await createPricingScheme(formData.value)
        const body = (res as any).data ?? res
        if (body.code === 200 || body.code === 0) {
          ElMessage.success('创建成功')
          formVisible.value = false
          await loadSchemes()
        }
      } else {
        const updateData: PricingSchemeUpdate = { ...formData.value }
        const res = await updatePricingScheme(currentSchemeId.value!, updateData)
        const body = (res as any).data ?? res
        if (body.code === 200 || body.code === 0) {
          ElMessage.success('更新成功')
          formVisible.value = false
          await loadSchemes()
        }
      }
    } catch (error: any) {
      ElMessage.error(error.response?.data?.detail || '操作失败')
    }
  })
}

const handleDelete = async (row: PricingScheme) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除方案"${row.scheme_name}"吗？`,
      '确认删除',
      {
        type: 'warning'
      }
    )

    const res = await deletePricingScheme(row.id)
    const body = (res as any).data ?? res
    if (body.code === 200 || body.code === 0) {
      ElMessage.success('删除成功')
      await loadSchemes()
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  }
}

const handleValidate = async (row: PricingScheme) => {
  try {
    const res = await validatePricingScheme(row.id)
    const body = (res as any).data ?? res
    if (body.code === 200 || body.code === 0) {
      const result = body.data
      if (result.valid) {
        ElMessage.success(`校验通过！覆盖率: ${result.coverage}/24小时`)
      } else {
        ElMessage.warning(
          `校验失败！覆盖率: ${result.coverage}/24小时，` +
          `冲突: ${result.conflicts.length}处，缺失: ${result.gaps.length}处`
        )
      }
      await loadSchemes()
    }
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '校验失败')
  }
}

const handleActivate = async (row: PricingScheme) => {
  try {
    await ElMessageBox.confirm(
      `确定要激活方案"${row.scheme_name}"吗？激活后将停用当前激活的方案。`,
      '确认激活',
      {
        type: 'warning'
      }
    )

    const res = await activatePricingScheme(row.id)
    const body = (res as any).data ?? res
    if (body.code === 200 || body.code === 0) {
      ElMessage.success('激活成功')
      await loadSchemes()
      emit('scheme-activated')
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '激活失败')
    }
  }
}

const handleDeactivate = async (row: PricingScheme) => {
  try {
    await ElMessageBox.confirm(
      `确定要停用方案"${row.scheme_name}"吗？停用后系统将进入兼容模式。`,
      '确认停用',
      {
        type: 'warning'
      }
    )

    const res = await deactivatePricingScheme(row.id)
    const body = (res as any).data ?? res
    if (body.code === 200 || body.code === 0) {
      ElMessage.success('停用成功')
      if (body.data?.warning) {
        ElMessage.warning(body.data.warning)
      }
      await loadSchemes()
      emit('scheme-activated')
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '停用失败')
    }
  }
}

const handleClose = () => {
  visible.value = false
}

const formatDate = (dateStr: string) => {
  return dateStr.split('T')[0]
}

// 生命周期
onMounted(() => {
  loadSchemes()
  loadPricings()
})
</script>

<style scoped lang="scss">
.pricing-scheme-manager {
  .manager-content {
    .toolbar {
      margin-bottom: 16px;
      display: flex;
      gap: 8px;
    }

    .scheme-table {
      :deep(.el-tag) {
        .el-icon {
          margin-right: 4px;
        }
      }
    }
  }
}
</style>
