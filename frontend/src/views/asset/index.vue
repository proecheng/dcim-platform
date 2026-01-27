<template>
  <div class="asset-page">
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stat-cards">
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #409eff;">
            <el-icon :size="28"><Box /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ statistics.total_count || 0 }}</div>
            <div class="stat-label">资产总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #67c23a;">
            <el-icon :size="28"><CircleCheck /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ statistics.by_status?.in_use || 0 }}</div>
            <div class="stat-label">使用中</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #909399;">
            <el-icon :size="28"><Coin /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ statistics.by_status?.in_stock || 0 }}</div>
            <div class="stat-label">库存中</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #e6a23c;">
            <el-icon :size="28"><Tools /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ statistics.maintenance_count || 0 }}</div>
            <div class="stat-label">维护中</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #f56c6c;">
            <el-icon :size="28"><Money /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ formatValue(statistics.total_value) }}</div>
            <div class="stat-label">资产总值</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #f56c6c;">
            <el-icon :size="28"><Warning /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ statistics.warranty_expiring_count || 0 }}</div>
            <div class="stat-label">即将过保</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 工具栏 -->
    <el-card shadow="hover" class="toolbar-card">
      <div class="toolbar">
        <div class="toolbar-filters">
          <el-select
            v-model="filters.asset_type"
            placeholder="资产类型"
            clearable
            style="width: 140px"
          >
            <el-option label="服务器" value="server" />
            <el-option label="网络设备" value="network" />
            <el-option label="存储设备" value="storage" />
            <el-option label="UPS" value="ups" />
            <el-option label="PDU" value="pdu" />
            <el-option label="空调" value="ac" />
            <el-option label="机柜" value="cabinet" />
            <el-option label="传感器" value="sensor" />
            <el-option label="其他" value="other" />
          </el-select>
          <el-select
            v-model="filters.status"
            placeholder="状态"
            clearable
            style="width: 120px"
          >
            <el-option label="库存" value="in_stock" />
            <el-option label="使用中" value="in_use" />
            <el-option label="借出" value="borrowed" />
            <el-option label="维护中" value="maintenance" />
            <el-option label="报废" value="scrapped" />
          </el-select>
          <el-input
            v-model="filters.keyword"
            placeholder="搜索资产编码/名称"
            clearable
            style="width: 200px"
            :prefix-icon="Search"
            @keyup.enter="loadAssets"
          />
          <el-button type="primary" @click="loadAssets">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </div>
        <div class="toolbar-actions">
          <el-button type="primary" :icon="Plus" @click="showAddDialog">新增资产</el-button>
          <el-button :icon="Upload">导入</el-button>
          <el-button :icon="Download">导出</el-button>
        </div>
      </div>
    </el-card>

    <!-- 资产列表 -->
    <el-card shadow="hover" class="table-card">
      <el-table :data="assets" stripe border v-loading="loading">
        <el-table-column prop="asset_code" label="资产编码" width="140" />
        <el-table-column prop="asset_name" label="资产名称" min-width="150" />
        <el-table-column prop="asset_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getTypeTagType(row.asset_type)" size="small">
              {{ getTypeName(row.asset_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="brand" label="品牌" width="100" />
        <el-table-column prop="model" label="型号" width="120" />
        <el-table-column prop="cabinet_name" label="所在机柜" width="120" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusName(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="responsible_person" label="负责人" width="100" />
        <el-table-column prop="warranty_status" label="保修状态" width="100">
          <template #default="{ row }">
            <el-tag
              :type="row.warranty_status === 'valid' ? 'success' : row.warranty_status === 'expiring' ? 'warning' : 'danger'"
              size="small"
            >
              {{ row.warranty_status === 'valid' ? '在保' : row.warranty_status === 'expiring' ? '即将过保' : '已过保' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="viewAsset(row)">查看</el-button>
            <el-button type="primary" link @click="editAsset(row)">编辑</el-button>
            <el-button type="warning" link @click="showMaintenanceDialog(row)">维护</el-button>
            <el-button type="danger" link @click="confirmDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadAssets"
          @current-change="loadAssets"
        />
      </div>
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑资产' : '新增资产'"
      width="700px"
      destroy-on-close
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-width="100px"
      >
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="资产编码" prop="asset_code">
              <el-input v-model="form.asset_code" :disabled="isEdit" placeholder="请输入资产编码" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="资产名称" prop="asset_name">
              <el-input v-model="form.asset_name" placeholder="请输入资产名称" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="资产类型" prop="asset_type">
              <el-select v-model="form.asset_type" placeholder="请选择类型" style="width: 100%">
                <el-option label="服务器" value="server" />
                <el-option label="网络设备" value="network" />
                <el-option label="存储设备" value="storage" />
                <el-option label="UPS" value="ups" />
                <el-option label="PDU" value="pdu" />
                <el-option label="空调" value="ac" />
                <el-option label="机柜" value="cabinet" />
                <el-option label="传感器" value="sensor" />
                <el-option label="其他" value="other" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-select v-model="form.status" placeholder="请选择状态" style="width: 100%">
                <el-option label="库存" value="in_stock" />
                <el-option label="使用中" value="in_use" />
                <el-option label="借出" value="borrowed" />
                <el-option label="维护中" value="maintenance" />
                <el-option label="报废" value="scrapped" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="品牌" prop="brand">
              <el-input v-model="form.brand" placeholder="请输入品牌" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="型号" prop="model">
              <el-input v-model="form.model" placeholder="请输入型号" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="序列号" prop="serial_number">
              <el-input v-model="form.serial_number" placeholder="请输入序列号" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="负责人" prop="responsible_person">
              <el-input v-model="form.responsible_person" placeholder="请输入负责人" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="部门" prop="department">
              <el-input v-model="form.department" placeholder="请输入部门" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="供应商" prop="supplier">
              <el-input v-model="form.supplier" placeholder="请输入供应商" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="购买日期" prop="purchase_date">
              <el-date-picker
                v-model="form.purchase_date"
                type="date"
                placeholder="选择购买日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="购买价格" prop="purchase_price">
              <el-input-number
                v-model="form.purchase_price"
                :min="0"
                :precision="2"
                placeholder="请输入价格"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="保修开始" prop="warranty_start">
              <el-date-picker
                v-model="form.warranty_start"
                type="date"
                placeholder="选择保修开始日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="保修结束" prop="warranty_end">
              <el-date-picker
                v-model="form.warranty_end"
                type="date"
                placeholder="选择保修结束日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="请输入备注信息"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- 维护记录对话框 -->
    <el-dialog
      v-model="maintenanceDialogVisible"
      title="新建维护记录"
      width="500px"
      destroy-on-close
    >
      <el-form
        ref="maintenanceFormRef"
        :model="maintenanceForm"
        :rules="maintenanceRules"
        label-width="100px"
      >
        <el-form-item label="资产">
          <el-input :value="currentAsset?.asset_name" disabled />
        </el-form-item>
        <el-form-item label="维护类型" prop="maintenance_type">
          <el-select v-model="maintenanceForm.maintenance_type" placeholder="请选择维护类型" style="width: 100%">
            <el-option label="定期维护" value="routine" />
            <el-option label="故障维修" value="repair" />
            <el-option label="升级更新" value="upgrade" />
            <el-option label="巡检" value="inspection" />
          </el-select>
        </el-form-item>
        <el-form-item label="维护日期" prop="maintenance_date">
          <el-date-picker
            v-model="maintenanceForm.maintenance_date"
            type="date"
            placeholder="选择维护日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="维护人员" prop="maintenance_person">
          <el-input v-model="maintenanceForm.maintenance_person" placeholder="请输入维护人员" />
        </el-form-item>
        <el-form-item label="维护费用" prop="maintenance_cost">
          <el-input-number
            v-model="maintenanceForm.maintenance_cost"
            :min="0"
            :precision="2"
            placeholder="请输入费用"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="维护描述" prop="maintenance_description">
          <el-input
            v-model="maintenanceForm.maintenance_description"
            type="textarea"
            :rows="3"
            placeholder="请输入维护描述"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="maintenanceDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitMaintenance" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import {
  Plus, Upload, Download, Search,
  Box, CircleCheck, Coin, Tools, Money, Warning
} from '@element-plus/icons-vue'
import {
  getAssets, createAsset, updateAsset, deleteAsset,
  getAssetStatistics, createMaintenance,
  type Asset, type AssetType, type AssetStatus, type AssetStatistics
} from '@/api/modules/asset'

// 数据状态
const loading = ref(false)
const submitting = ref(false)
const assets = ref<Asset[]>([])
const statistics = ref<Partial<AssetStatistics>>({})

// 筛选条件
const filters = reactive({
  asset_type: '' as AssetType | '',
  status: '' as AssetStatus | '',
  keyword: ''
})

// 分页
const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

// 对话框状态
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref<FormInstance>()
const currentAssetId = ref<number | null>(null)

// 表单数据
const form = reactive({
  asset_code: '',
  asset_name: '',
  asset_type: '' as AssetType | '',
  status: 'in_stock' as AssetStatus,
  brand: '',
  model: '',
  serial_number: '',
  responsible_person: '',
  department: '',
  supplier: '',
  purchase_date: '',
  purchase_price: undefined as number | undefined,
  warranty_start: '',
  warranty_end: '',
  description: ''
})

// 表单校验规则
const formRules = {
  asset_code: [{ required: true, message: '请输入资产编码', trigger: 'blur' }],
  asset_name: [{ required: true, message: '请输入资产名称', trigger: 'blur' }],
  asset_type: [{ required: true, message: '请选择资产类型', trigger: 'change' }]
}

// 维护记录对话框
const maintenanceDialogVisible = ref(false)
const maintenanceFormRef = ref<FormInstance>()
const currentAsset = ref<Asset | null>(null)

const maintenanceForm = reactive({
  maintenance_type: '',
  maintenance_date: '',
  maintenance_person: '',
  maintenance_cost: undefined as number | undefined,
  maintenance_description: ''
})

const maintenanceRules = {
  maintenance_type: [{ required: true, message: '请选择维护类型', trigger: 'change' }],
  maintenance_date: [{ required: true, message: '请选择维护日期', trigger: 'change' }],
  maintenance_description: [{ required: true, message: '请输入维护描述', trigger: 'blur' }]
}

// 初始化加载
onMounted(() => {
  loadAssets()
  loadStatistics()
})

// 加载资产列表
async function loadAssets() {
  loading.value = true
  try {
    const params: Record<string, any> = {
      page: pagination.page,
      page_size: pagination.page_size
    }
    if (filters.asset_type) params.asset_type = filters.asset_type
    if (filters.status) params.status = filters.status
    if (filters.keyword) params.keyword = filters.keyword

    const res = await getAssets(params)
    if (res.data) {
      if (Array.isArray(res.data)) {
        assets.value = res.data
        pagination.total = res.data.length
      } else {
        assets.value = (res.data as any).items || []
        pagination.total = (res.data as any).total || 0
      }
    }
  } catch (e) {
    console.error('加载资产列表失败', e)
    ElMessage.error('加载资产列表失败')
  } finally {
    loading.value = false
  }
}

// 加载统计数据
async function loadStatistics() {
  try {
    const res = await getAssetStatistics()
    if (res.data) {
      statistics.value = res.data
    }
  } catch (e) {
    console.error('加载统计数据失败', e)
  }
}

// 重置筛选条件
function resetFilters() {
  filters.asset_type = ''
  filters.status = ''
  filters.keyword = ''
  pagination.page = 1
  loadAssets()
}

// 显示新增对话框
function showAddDialog() {
  isEdit.value = false
  currentAssetId.value = null
  resetForm()
  dialogVisible.value = true
}

// 编辑资产
function editAsset(row: Asset) {
  isEdit.value = true
  currentAssetId.value = row.id
  Object.assign(form, {
    asset_code: row.asset_code,
    asset_name: row.asset_name,
    asset_type: row.asset_type,
    status: row.status,
    brand: row.brand || '',
    model: row.model || '',
    serial_number: row.serial_number || '',
    responsible_person: row.responsible_person || '',
    department: row.department || '',
    supplier: row.supplier || '',
    purchase_date: row.purchase_date || '',
    purchase_price: row.purchase_price,
    warranty_start: '',
    warranty_end: row.warranty_date || '',
    description: row.description || ''
  })
  dialogVisible.value = true
}

// 查看资产详情
function viewAsset(row: Asset) {
  editAsset(row)
}

// 显示维护记录对话框
function showMaintenanceDialog(row: Asset) {
  currentAsset.value = row
  maintenanceForm.maintenance_type = ''
  maintenanceForm.maintenance_date = ''
  maintenanceForm.maintenance_person = ''
  maintenanceForm.maintenance_cost = undefined
  maintenanceForm.maintenance_description = ''
  maintenanceDialogVisible.value = true
}

// 提交表单
async function submitForm() {
  const valid = await formRef.value?.validate()
  if (!valid) return

  submitting.value = true
  try {
    const data = {
      asset_code: form.asset_code,
      asset_name: form.asset_name,
      asset_type: form.asset_type as AssetType,
      status: form.status,
      brand: form.brand || undefined,
      model: form.model || undefined,
      serial_number: form.serial_number || undefined,
      responsible_person: form.responsible_person || undefined,
      department: form.department || undefined,
      supplier: form.supplier || undefined,
      purchase_date: form.purchase_date || undefined,
      purchase_price: form.purchase_price,
      warranty_date: form.warranty_end || undefined,
      description: form.description || undefined
    }

    if (isEdit.value && currentAssetId.value) {
      await updateAsset(currentAssetId.value, data)
      ElMessage.success('更新成功')
    } else {
      await createAsset(data)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadAssets()
    loadStatistics()
  } catch (e) {
    console.error('操作失败', e)
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

// 提交维护记录
async function submitMaintenance() {
  const valid = await maintenanceFormRef.value?.validate()
  if (!valid || !currentAsset.value) return

  submitting.value = true
  try {
    await createMaintenance({
      asset_id: currentAsset.value.id,
      maintenance_type: maintenanceForm.maintenance_type,
      maintenance_date: maintenanceForm.maintenance_date,
      maintenance_person: maintenanceForm.maintenance_person || undefined,
      maintenance_cost: maintenanceForm.maintenance_cost,
      maintenance_description: maintenanceForm.maintenance_description
    })
    ElMessage.success('维护记录创建成功')
    maintenanceDialogVisible.value = false
  } catch (e) {
    console.error('创建维护记录失败', e)
    ElMessage.error('创建维护记录失败')
  } finally {
    submitting.value = false
  }
}

// 删除确认
function confirmDelete(row: Asset) {
  ElMessageBox.confirm(
    `确定要删除资产 "${row.asset_name}" 吗？`,
    '删除确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await deleteAsset(row.id)
      ElMessage.success('删除成功')
      loadAssets()
      loadStatistics()
    } catch (e) {
      console.error('删除失败', e)
      ElMessage.error('删除失败')
    }
  }).catch(() => {
    // 用户取消
  })
}

// 重置表单
function resetForm() {
  form.asset_code = ''
  form.asset_name = ''
  form.asset_type = ''
  form.status = 'in_stock'
  form.brand = ''
  form.model = ''
  form.serial_number = ''
  form.responsible_person = ''
  form.department = ''
  form.supplier = ''
  form.purchase_date = ''
  form.purchase_price = undefined
  form.warranty_start = ''
  form.warranty_end = ''
  form.description = ''
}

// 格式化资产总值
function formatValue(value: number | undefined) {
  if (!value) return '0'
  if (value >= 10000) {
    return (value / 10000).toFixed(1) + '万'
  }
  return value.toFixed(0)
}

// 获取类型名称
function getTypeName(type: AssetType) {
  const map: Record<AssetType, string> = {
    server: '服务器',
    network: '网络设备',
    storage: '存储设备',
    ups: 'UPS',
    pdu: 'PDU',
    ac: '空调',
    cabinet: '机柜',
    sensor: '传感器',
    other: '其他'
  }
  return map[type] || type
}

// 获取状态名称
function getStatusName(status: AssetStatus) {
  const map: Record<AssetStatus, string> = {
    in_stock: '库存',
    in_use: '使用中',
    borrowed: '借出',
    maintenance: '维护中',
    scrapped: '报废'
  }
  return map[status] || status
}

type TagType = 'success' | 'warning' | 'danger' | 'info' | 'primary'

// 获取类型标签样式
function getTypeTagType(type: AssetType): TagType {
  const map: Record<AssetType, TagType> = {
    server: 'primary',
    network: 'success',
    storage: 'warning',
    ups: 'danger',
    pdu: 'info',
    ac: 'success',
    cabinet: 'info',
    sensor: 'warning',
    other: 'info'
  }
  return map[type] || 'info'
}

// 获取状态标签样式
function getStatusType(status: AssetStatus): TagType {
  const map: Record<AssetStatus, TagType> = {
    in_stock: 'info',
    in_use: 'success',
    borrowed: 'warning',
    maintenance: 'danger',
    scrapped: 'info'
  }
  return map[status] || 'info'
}
</script>

<style scoped lang="scss">
.asset-page {
  .stat-cards {
    margin-bottom: 20px;
  }

  .stat-card {
    background: var(--bg-card);
    border-color: var(--border-color);

    :deep(.el-card__body) {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 16px;
    }

    .stat-icon {
      width: 56px;
      height: 56px;
      border-radius: var(--radius-lg, 8px);
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      box-shadow: var(--shadow-sm, 0 2px 8px rgba(0, 0, 0, 0.1));

      &[style*="409eff"] {
        box-shadow: 0 0 15px rgba(64, 158, 255, 0.4);
      }
      &[style*="67c23a"] {
        box-shadow: 0 0 15px rgba(82, 196, 26, 0.4);
      }
      &[style*="909399"] {
        box-shadow: 0 0 15px rgba(144, 147, 153, 0.4);
      }
      &[style*="e6a23c"] {
        box-shadow: 0 0 15px rgba(230, 162, 60, 0.4);
      }
      &[style*="f56c6c"] {
        box-shadow: 0 0 15px rgba(245, 108, 108, 0.4);
      }
    }

    .stat-info {
      .stat-value {
        font-size: 24px;
        font-weight: bold;
        color: var(--text-primary);
      }

      .stat-label {
        font-size: 13px;
        color: var(--text-secondary);
        margin-top: 4px;
      }
    }

    &:hover {
      border-color: var(--border-active, #409eff);
      box-shadow: var(--shadow-glow, 0 0 12px rgba(64, 158, 255, 0.2));
    }
  }

  .toolbar-card {
    margin-bottom: 20px;
    background: var(--bg-card);
    border-color: var(--border-color);

    .toolbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;

      .toolbar-filters {
        display: flex;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
      }

      .toolbar-actions {
        display: flex;
        gap: 12px;
      }
    }
  }

  .table-card {
    background: var(--bg-card);
    border-color: var(--border-color);

    .pagination-wrapper {
      margin-top: 20px;
      display: flex;
      justify-content: flex-end;
    }
  }
}
</style>
