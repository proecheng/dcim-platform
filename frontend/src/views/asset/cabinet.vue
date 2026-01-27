<template>
  <div class="cabinet-page">
    <el-card shadow="hover" class="main-card">
      <template #header>
        <div class="card-header">
          <span>机柜管理</span>
          <el-button type="primary" :icon="Plus" @click="showAddDialog">新增机柜</el-button>
        </div>
      </template>

      <!-- 机柜列表 -->
      <el-table :data="cabinets" stripe border v-loading="loading">
        <el-table-column prop="cabinet_code" label="机柜编码" width="140" />
        <el-table-column prop="cabinet_name" label="机柜名称" min-width="150" />
        <el-table-column prop="location" label="位置" width="150" />
        <el-table-column prop="total_u" label="总U数" width="80" align="center" />
        <el-table-column label="U位使用率" width="200">
          <template #default="{ row }">
            <div class="usage-cell">
              <el-progress
                :percentage="getUsagePercentage(row)"
                :color="getProgressColor(getUsagePercentage(row))"
                :stroke-width="16"
                :format="() => `${row.used_u || 0}/${row.total_u}U`"
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="max_power" label="最大功率(kW)" width="120" align="center">
          <template #default="{ row }">
            {{ row.max_power ? row.max_power.toFixed(1) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="viewUsage(row)">U位图</el-button>
            <el-button type="primary" link @click="editCabinet(row)">编辑</el-button>
            <el-button type="danger" link @click="confirmDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑机柜' : '新增机柜'"
      width="600px"
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
            <el-form-item label="机柜编码" prop="cabinet_code">
              <el-input v-model="form.cabinet_code" :disabled="isEdit" placeholder="请输入机柜编码" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="机柜名称" prop="cabinet_name">
              <el-input v-model="form.cabinet_name" placeholder="请输入机柜名称" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="位置" prop="location">
          <el-input v-model="form.location" placeholder="请输入机柜位置" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="行号" prop="row_number">
              <el-input-number
                v-model="form.row_number"
                :min="1"
                placeholder="行号"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="列号" prop="column_number">
              <el-input-number
                v-model="form.column_number"
                :min="1"
                placeholder="列号"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="总U数" prop="total_u">
              <el-input-number
                v-model="form.total_u"
                :min="1"
                :max="52"
                placeholder="机柜U数"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="最大功率(kW)" prop="max_power">
              <el-input-number
                v-model="form.max_power"
                :min="0"
                :precision="1"
                placeholder="最大功率"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="最大承重(kg)" prop="max_weight">
          <el-input-number
            v-model="form.max_weight"
            :min="0"
            :precision="1"
            placeholder="最大承重"
            style="width: 200px"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- U位图对话框 -->
    <el-dialog
      v-model="usageDialogVisible"
      :title="`${currentCabinet?.cabinet_name || ''} - U位图`"
      width="800px"
      destroy-on-close
    >
      <div class="usage-container" v-if="currentUsage">
        <div class="usage-summary">
          <el-row :gutter="20">
            <el-col :span="6">
              <div class="summary-item">
                <div class="summary-value">{{ currentUsage.total_u }}</div>
                <div class="summary-label">总U数</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="summary-item">
                <div class="summary-value used">{{ currentUsage.used_u }}</div>
                <div class="summary-label">已使用</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="summary-item">
                <div class="summary-value available">{{ currentUsage.available_u }}</div>
                <div class="summary-label">可用</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="summary-item">
                <div class="summary-value rate">{{ (currentUsage.usage_rate * 100).toFixed(1) }}%</div>
                <div class="summary-label">使用率</div>
              </div>
            </el-col>
          </el-row>
        </div>

        <div class="usage-visual">
          <div class="rack-container">
            <div
              v-for="u in currentUsage.total_u"
              :key="u"
              class="rack-unit"
              :class="{ occupied: isUnitOccupied(currentUsage.total_u - u + 1) }"
            >
              <span class="unit-number">{{ currentUsage.total_u - u + 1 }}U</span>
              <span class="unit-asset" v-if="getAssetAtUnit(currentUsage.total_u - u + 1)">
                {{ getAssetAtUnit(currentUsage.total_u - u + 1)?.asset_name }}
              </span>
            </div>
          </div>
        </div>

        <div class="usage-assets" v-if="currentUsage.assets && currentUsage.assets.length > 0">
          <h4>设备清单</h4>
          <el-table :data="currentUsage.assets" stripe border size="small">
            <el-table-column prop="asset_code" label="资产编码" width="120" />
            <el-table-column prop="asset_name" label="资产名称" />
            <el-table-column prop="asset_type" label="类型" width="100">
              <template #default="{ row }">
                {{ getTypeName(row.asset_type) }}
              </template>
            </el-table-column>
            <el-table-column label="U位" width="100">
              <template #default="{ row }">
                {{ row.start_u }}-{{ row.end_u }}U
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">
                  {{ getStatusName(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
      <div v-else class="usage-empty">
        <el-empty description="暂无U位数据" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  getCabinets, createCabinet, updateCabinet, deleteCabinet, getCabinetUsage,
  type Cabinet, type CabinetUsage, type AssetType, type AssetStatus, type Asset
} from '@/api/modules/asset'

// 数据状态
const loading = ref(false)
const submitting = ref(false)
const cabinets = ref<Cabinet[]>([])

// 对话框状态
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref<FormInstance>()
const currentCabinetId = ref<number | null>(null)

// 表单数据
const form = reactive({
  cabinet_code: '',
  cabinet_name: '',
  location: '',
  row_number: 1,
  column_number: 1,
  total_u: 42,
  max_power: undefined as number | undefined,
  max_weight: undefined as number | undefined
})

// 表单校验规则
const formRules = {
  cabinet_code: [{ required: true, message: '请输入机柜编码', trigger: 'blur' }],
  cabinet_name: [{ required: true, message: '请输入机柜名称', trigger: 'blur' }],
  location: [{ required: true, message: '请输入机柜位置', trigger: 'blur' }],
  row_number: [{ required: true, message: '请输入行号', trigger: 'blur' }],
  column_number: [{ required: true, message: '请输入列号', trigger: 'blur' }],
  total_u: [{ required: true, message: '请输入总U数', trigger: 'blur' }]
}

// U位图对话框
const usageDialogVisible = ref(false)
const currentCabinet = ref<Cabinet | null>(null)
const currentUsage = ref<CabinetUsage | null>(null)

// 初始化加载
onMounted(() => {
  loadCabinets()
})

// 加载机柜列表
async function loadCabinets() {
  loading.value = true
  try {
    const res = await getCabinets()
    if (res.data) {
      if (Array.isArray(res.data)) {
        cabinets.value = res.data
      } else {
        cabinets.value = (res.data as any).items || []
      }
    }
  } catch (e) {
    console.error('加载机柜列表失败', e)
    ElMessage.error('加载机柜列表失败')
  } finally {
    loading.value = false
  }
}

// 显示新增对话框
function showAddDialog() {
  isEdit.value = false
  currentCabinetId.value = null
  resetForm()
  dialogVisible.value = true
}

// 编辑机柜
function editCabinet(row: Cabinet) {
  isEdit.value = true
  currentCabinetId.value = row.id
  Object.assign(form, {
    cabinet_code: row.cabinet_code,
    cabinet_name: row.cabinet_name,
    location: row.location,
    row_number: row.row_number,
    column_number: row.column_number,
    total_u: row.total_u,
    max_power: row.max_power,
    max_weight: row.max_weight
  })
  dialogVisible.value = true
}

// 查看U位图
async function viewUsage(row: Cabinet) {
  currentCabinet.value = row
  currentUsage.value = null
  usageDialogVisible.value = true

  try {
    const res = await getCabinetUsage(row.id)
    if (res.data) {
      currentUsage.value = res.data
    }
  } catch (e) {
    console.error('获取机柜使用情况失败', e)
    ElMessage.error('获取机柜使用情况失败')
  }
}

// 提交表单
async function submitForm() {
  const valid = await formRef.value?.validate()
  if (!valid) return

  submitting.value = true
  try {
    if (isEdit.value && currentCabinetId.value) {
      await updateCabinet(currentCabinetId.value, {
        cabinet_name: form.cabinet_name,
        location: form.location,
        row_number: form.row_number,
        column_number: form.column_number,
        total_u: form.total_u,
        max_power: form.max_power,
        max_weight: form.max_weight
      })
      ElMessage.success('更新成功')
    } else {
      await createCabinet({
        cabinet_code: form.cabinet_code,
        cabinet_name: form.cabinet_name,
        location: form.location,
        row_number: form.row_number,
        column_number: form.column_number,
        total_u: form.total_u,
        max_power: form.max_power,
        max_weight: form.max_weight
      })
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadCabinets()
  } catch (e) {
    console.error('操作失败', e)
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

// 删除确认
function confirmDelete(row: Cabinet) {
  ElMessageBox.confirm(
    `确定要删除机柜 "${row.cabinet_name}" 吗？删除后该机柜下的所有设备将失去关联。`,
    '删除确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await deleteCabinet(row.id)
      ElMessage.success('删除成功')
      loadCabinets()
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
  form.cabinet_code = ''
  form.cabinet_name = ''
  form.location = ''
  form.row_number = 1
  form.column_number = 1
  form.total_u = 42
  form.max_power = undefined
  form.max_weight = undefined
}

// 计算使用率百分比
function getUsagePercentage(row: Cabinet): number {
  if (!row.total_u) return 0
  return Math.round(((row.used_u || 0) / row.total_u) * 100)
}

// 获取进度条颜色 - use theme-aware colors
function getProgressColor(percentage: number): string {
  if (percentage < 60) return '#52c41a'  // var(--success-color)
  if (percentage < 80) return '#faad14'  // var(--warning-color)
  return '#f5222d'  // var(--error-color)
}

// 检查U位是否被占用
function isUnitOccupied(unitNumber: number): boolean {
  if (!currentUsage.value?.assets) return false
  return currentUsage.value.assets.some(
    asset => asset.start_u && asset.end_u &&
      unitNumber >= asset.start_u && unitNumber <= asset.end_u
  )
}

// 获取指定U位的设备
function getAssetAtUnit(unitNumber: number): Asset | undefined {
  if (!currentUsage.value?.assets) return undefined
  return currentUsage.value.assets.find(
    asset => asset.start_u && asset.end_u &&
      unitNumber >= asset.start_u && unitNumber <= asset.end_u
  )
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
.cabinet-page {
  .main-card {
    background: var(--bg-card);
    border-color: var(--border-color);
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    color: var(--text-primary);
  }

  .usage-cell {
    width: 100%;
    padding-right: 10px;
  }

  // U位图样式
  .usage-container {
    .usage-summary {
      margin-bottom: 24px;
      padding: 20px;
      background: var(--bg-tertiary, rgba(17, 34, 64, 0.8));
      border-radius: var(--radius-base, 4px);

      .summary-item {
        text-align: center;

        .summary-value {
          font-size: 28px;
          font-weight: bold;
          color: var(--text-primary, rgba(255, 255, 255, 0.95));

          &.used {
            color: var(--error-color, #f5222d);
          }

          &.available {
            color: var(--success-color, #52c41a);
          }

          &.rate {
            color: var(--primary-color, #1890ff);
          }
        }

        .summary-label {
          font-size: 13px;
          color: var(--text-secondary, rgba(255, 255, 255, 0.65));
          margin-top: 4px;
        }
      }
    }

    .usage-visual {
      margin-bottom: 24px;

      .rack-container {
        max-height: 400px;
        overflow-y: auto;
        border: 2px solid var(--border-color, #dcdfe6);
        border-radius: var(--radius-base, 4px);
        background: var(--bg-card, #1a2a4a);
      }

      .rack-unit {
        display: flex;
        align-items: center;
        height: 24px;
        padding: 0 12px;
        border-bottom: 1px solid var(--border-color, #ebeef5);
        font-size: 12px;
        background: var(--bg-card, #1a2a4a);
        transition: background-color 0.2s;

        &:last-child {
          border-bottom: none;
        }

        &.occupied {
          background: rgba(64, 158, 255, 0.15);
          border-left: 3px solid #409eff;
        }

        .unit-number {
          width: 50px;
          font-weight: 500;
          color: var(--text-secondary);
        }

        .unit-asset {
          flex: 1;
          color: var(--text-primary);
          font-weight: 500;
          padding-left: 12px;
        }
      }
    }

    .usage-assets {
      h4 {
        margin-bottom: 12px;
        color: var(--text-primary);
        font-size: 14px;
      }
    }
  }

  .usage-empty {
    padding: 40px;
  }
}
</style>
