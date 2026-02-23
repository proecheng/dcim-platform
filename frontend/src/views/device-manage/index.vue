<template>
  <div class="device-manage-page">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">总设备数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value online">{{ stats.online }}</div>
          <div class="stat-label">在线设备</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value offline">{{ stats.offline }}</div>
          <div class="stat-label">离线设备</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value alarm">{{ stats.alarm }}</div>
          <div class="stat-label">告警设备</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 搜索和操作栏 -->
    <div class="toolbar">
      <el-form :inline="true" class="filter-form">
        <el-form-item>
          <el-input
            v-model="filters.keyword"
            placeholder="搜索设备编码/名称"
            clearable
            style="width: 200px;"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item>
          <el-select v-model="filters.device_type" placeholder="全部类型" clearable style="width: 130px;">
            <el-option v-for="item in deviceTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-select v-model="filters.area_code" placeholder="全部区域" clearable style="width: 130px;">
            <el-option v-for="item in areaOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 130px;">
            <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
      <el-button type="primary" :icon="Plus" @click="handleAdd">新增设备</el-button>
    </div>

    <!-- 设备表格 -->
    <el-table :data="tableData" stripe border v-loading="loading" style="width: 100%;">
      <el-table-column prop="device_code" label="设备编码" width="130" />
      <el-table-column prop="device_name" label="设备名称" width="140" />
      <el-table-column prop="device_type" label="设备类型" width="130">
        <template #default="{ row }">
          <el-tag :type="deviceTypeTagMap[row.device_type] || 'info'" size="small">
            {{ getDeviceTypeLabel(row.device_type) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="area_code" label="区域" width="80" />
      <el-table-column prop="status" label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="statusTagMap[row.status]?.type || 'info'" size="small">
            {{ statusTagMap[row.status]?.text || row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="manufacturer" label="厂商" width="120" />
      <el-table-column prop="model" label="型号" width="120" />
      <el-table-column prop="is_enabled" label="启用" width="80">
        <template #default="{ row }">
          <el-switch
            :model-value="row.is_enabled"
            :before-change="() => handleToggleEnabled(row)"
          />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link @click="handleDetail(row)">详情</el-button>
          <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
          <el-button type="danger" link @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <el-pagination
      v-model:current-page="pagination.page"
      v-model:page-size="pagination.pageSize"
      :total="pagination.total"
      :page-sizes="[10, 20, 50]"
      layout="total, sizes, prev, pager, next"
      style="margin-top: 16px; justify-content: flex-end;"
      @size-change="loadData"
      @current-change="loadData"
    />

    <!-- 新增/编辑设备对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑设备' : '新增设备'" width="560px" @close="resetForm">
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="90px">
        <el-form-item label="设备编码" prop="device_code">
          <el-input v-model="form.device_code" :disabled="isEdit" placeholder="请输入设备编码" />
        </el-form-item>
        <el-form-item label="设备名称" prop="device_name">
          <el-input v-model="form.device_name" placeholder="请输入设备名称" />
        </el-form-item>
        <el-form-item label="设备类型" prop="device_type">
          <el-select v-model="form.device_type" placeholder="请选择设备类型" style="width: 100%;">
            <el-option v-for="item in deviceTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="区域" prop="area_code">
          <el-select v-model="form.area_code" placeholder="请选择区域" style="width: 100%;">
            <el-option v-for="item in areaOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="厂商" prop="manufacturer">
          <el-input v-model="form.manufacturer" placeholder="请输入厂商" />
        </el-form-item>
        <el-form-item label="型号" prop="model">
          <el-input v-model="form.model" placeholder="请输入型号" />
        </el-form-item>
        <el-form-item label="序列号" prop="serial_number">
          <el-input v-model="form.serial_number" placeholder="请输入序列号" />
        </el-form-item>
        <el-form-item label="安装日期" prop="install_date">
          <el-date-picker
            v-model="form.install_date"
            type="date"
            placeholder="选择安装日期"
            value-format="YYYY-MM-DD"
            style="width: 100%;"
          />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="请输入描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Plus } from '@element-plus/icons-vue'
import {
  getDeviceList,
  createDevice,
  updateDevice,
  deleteDevice,
  getDeviceStatusSummary,
  type DeviceInfo,
  type DeviceCreateParams,
  type DeviceUpdateParams
} from '@/api/modules/device'

// ===== 常量选项 =====
const router = useRouter()

const deviceTypeOptions = [
  { label: 'UPS', value: 'UPS' },
  { label: 'PDU', value: 'PDU' },
  { label: '精密空调(室内)', value: 'PRECISION_AC_INDOOR' },
  { label: '精密空调(室外)', value: 'PRECISION_AC_OUTDOOR' },
  { label: '空调', value: 'AC' },
  { label: '机柜', value: 'CABINET' },
  { label: '冷通道', value: 'COLD_AISLE' },
  { label: '温湿度', value: 'TH' },
  { label: '门禁', value: 'DOOR' },
  { label: '烟感', value: 'SMOKE' },
  { label: '水浸', value: 'WATER' },
]

const areaOptions = [
  { label: 'A区', value: 'A' },
  { label: 'A1', value: 'A1' },
  { label: 'A2', value: 'A2' },
  { label: 'B区', value: 'B' },
  { label: 'B1', value: 'B1' },
  { label: 'F1', value: 'F1' },
  { label: 'F2', value: 'F2' },
  { label: 'F3', value: 'F3' },
]

const statusOptions = [
  { label: '在线', value: 'online' },
  { label: '运行中', value: 'running' },
  { label: '离线', value: 'offline' },
  { label: '维护中', value: 'maintenance' },
  { label: '告警', value: 'alarm' },
]

// ===== 标签映射 =====
type TagType = 'success' | 'warning' | 'danger' | 'info' | 'primary'

const deviceTypeLabelMap: Record<string, string> = Object.fromEntries(
  deviceTypeOptions.map(item => [item.value, item.label])
)

function getDeviceTypeLabel(type: string): string {
  return deviceTypeLabelMap[type] || type
}

const deviceTypeTagMap: Record<string, TagType> = {
  UPS: 'danger',
  PDU: 'warning',
  PRECISION_AC_INDOOR: 'primary',
  PRECISION_AC_OUTDOOR: 'primary',
  AC: 'primary',
  CABINET: 'success',
  COLD_AISLE: 'success',
  TH: 'info',
  DOOR: 'info',
  SMOKE: 'info',
  WATER: 'info',
}

const statusTagMap: Record<string, { type: TagType; text: string }> = {
  online: { type: 'success', text: '在线' },
  running: { type: 'success', text: '运行中' },
  offline: { type: 'danger', text: '离线' },
  maintenance: { type: 'warning', text: '维护中' },
  alarm: { type: 'danger', text: '告警' },
}

// ===== 统计数据 =====
const stats = reactive({
  total: 0,
  online: 0,
  offline: 0,
  alarm: 0
})

// ===== 筛选条件 =====
const filters = reactive({
  keyword: '',
  device_type: '',
  area_code: '',
  status: ''
})

// ===== 表格数据 =====
const loading = ref(false)
const tableData = ref<DeviceInfo[]>([])
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

// ===== 新增/编辑对话框 =====
const dialogVisible = ref(false)
const isEdit = ref(false)
const submitLoading = ref(false)
const formRef = ref()
const editingId = ref(0)

const form = reactive({
  device_code: '',
  device_name: '',
  device_type: '',
  area_code: '',
  manufacturer: '',
  model: '',
  serial_number: '',
  install_date: '',
  description: ''
})

const formRules = {
  device_code: [
    { required: true, message: '请输入设备编码', trigger: 'blur' },
    { max: 50, message: '设备编码最多50个字符', trigger: 'blur' }
  ],
  device_name: [
    { required: true, message: '请输入设备名称', trigger: 'blur' },
    { max: 100, message: '设备名称最多100个字符', trigger: 'blur' }
  ],
  device_type: [
    { required: true, message: '请选择设备类型', trigger: 'change' }
  ],
  area_code: [
    { required: true, message: '请选择区域', trigger: 'change' }
  ]
}

// ===== 数据加载 =====
async function loadData() {
  loading.value = true
  try {
    const params: Record<string, string | number> = {
      page: pagination.page,
      page_size: pagination.pageSize
    }
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.device_type) params.device_type = filters.device_type
    if (filters.area_code) params.area_code = filters.area_code
    if (filters.status) params.status = filters.status

    const res = await getDeviceList(params)
    tableData.value = res.items
    pagination.total = res.total
  } catch (e) {
    console.error('加载设备列表失败', e)
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    const summary = await getDeviceStatusSummary()
    stats.total = summary.total
    stats.online = summary.online
    stats.offline = summary.offline
    stats.alarm = summary.alarm
  } catch (e) {
    console.error('加载统计数据失败', e)
  }
}

// ===== 搜索/重置 =====
function handleSearch() {
  pagination.page = 1
  loadData()
}

function handleReset() {
  filters.keyword = ''
  filters.device_type = ''
  filters.area_code = ''
  filters.status = ''
  pagination.page = 1
  loadData()
  loadStats()
}

// ===== 新增 =====
function handleAdd() {
  isEdit.value = false
  editingId.value = 0
  resetForm()
  dialogVisible.value = true
}

// ===== 详情 =====
function handleDetail(row: DeviceInfo) {
  router.push(`/collection/device-manage/detail/${row.id}`)
}

// ===== 编辑 =====
function handleEdit(row: DeviceInfo) {
  isEdit.value = true
  editingId.value = row.id
  Object.assign(form, {
    device_code: row.device_code,
    device_name: row.device_name,
    device_type: row.device_type,
    area_code: row.area_code,
    manufacturer: row.manufacturer || '',
    model: row.model || '',
    serial_number: row.serial_number || '',
    install_date: row.install_date || '',
    description: row.description || ''
  })
  dialogVisible.value = true
}

// ===== 提交新增/编辑 =====
async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitLoading.value = true
  try {
    if (isEdit.value) {
      const updateData: DeviceUpdateParams = {
        device_name: form.device_name,
        device_type: form.device_type,
        area_code: form.area_code,
        manufacturer: form.manufacturer || undefined,
        model: form.model || undefined,
        serial_number: form.serial_number || undefined,
        install_date: form.install_date || undefined,
        description: form.description || undefined
      }
      await updateDevice(editingId.value, updateData)
      ElMessage.success('更新成功')
    } else {
      const createData: DeviceCreateParams = {
        device_code: form.device_code,
        device_name: form.device_name,
        device_type: form.device_type,
        area_code: form.area_code,
        manufacturer: form.manufacturer || undefined,
        model: form.model || undefined,
        serial_number: form.serial_number || undefined,
        install_date: form.install_date || undefined,
        description: form.description || undefined
      }
      await createDevice(createData)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadData()
    loadStats()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    const msg = err?.response?.data?.detail || '操作失败'
    ElMessage.error(msg)
  } finally {
    submitLoading.value = false
  }
}

// ===== 切换启用状态 =====
async function handleToggleEnabled(row: DeviceInfo): Promise<boolean> {
  const newEnabled = !row.is_enabled
  try {
    const updateData: DeviceUpdateParams = { is_enabled: newEnabled }
    await updateDevice(row.id, updateData)
    row.is_enabled = newEnabled
    ElMessage.success(newEnabled ? '已启用' : '已禁用')
    return true
  } catch (e) {
    ElMessage.error('操作失败')
    return false
  }
}

// ===== 删除 =====
async function handleDelete(row: DeviceInfo) {
  try {
    await ElMessageBox.confirm(
      `确定删除设备「${row.device_name}」？此操作不可恢复。`,
      '确认删除',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    await deleteDevice(row.id)
    ElMessage.success('删除成功')
    loadData()
    loadStats()
  } catch (e: unknown) {
    if (e !== 'cancel') {
      const err = e as { response?: { data?: { detail?: string } } }
      const detail = err?.response?.data?.detail
      if (detail) {
        ElMessage.error(detail)
      }
    }
  }
}

// ===== 表单重置 =====
function resetForm() {
  Object.assign(form, {
    device_code: '',
    device_name: '',
    device_type: '',
    area_code: '',
    manufacturer: '',
    model: '',
    serial_number: '',
    install_date: '',
    description: ''
  })
  formRef.value?.clearValidate()
}

// ===== 初始化 =====
onMounted(() => {
  loadData()
  loadStats()
})
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.device-manage-page {
  @include page-dashboard(4);
  .stat-row {
    margin-bottom: 16px;
  }

  .stat-card {
    text-align: center;

    :deep(.el-card__body) {
      padding: 16px;
    }

    .stat-value {
      font-size: 28px;
      font-weight: 600;
      color: var(--text-primary);
      line-height: 1.4;

      &.online { color: #67c23a; }
      &.offline { color: #f56c6c; }
      &.alarm { color: #e6a23c; }
    }

    .stat-label {
      font-size: 13px;
      color: var(--text-secondary);
      margin-top: 4px;
    }
  }

  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 16px;

    .filter-form {
      margin-bottom: 0;
    }
  }
}
</style>
