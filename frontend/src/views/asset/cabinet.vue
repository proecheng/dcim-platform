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
                <div class="summary-value rate">{{ currentUsage.usage_rate.toFixed(1) }}%</div>
                <div class="summary-label">使用率</div>
              </div>
            </el-col>
          </el-row>
        </div>

        <div class="usage-visual">
          <div class="rack-container">
            <div
              v-for="(slot, idx) in rackSlots"
              :key="idx"
              class="rack-slot"
              :class="{
                'rack-slot--asset': slot.type === 'asset',
                'rack-slot--empty': slot.type === 'empty',
                'rack-slot--drop-target': isDragTarget(slot)
              }"
              :style="{
                height: slot.height * 28 + 'px',
                backgroundColor: slot.type === 'asset' && slot.asset ? statusColorMap[slot.asset.status] || '#409eff' : undefined
              }"
              :draggable="slot.type === 'asset' ? 'true' : 'false'"
              @dragstart="onDragStart($event, slot)"
              @dragover="onDragOver($event, slot)"
              @dragleave="onDragLeave($event)"
              @drop="onDrop($event, slot)"
            >
              <span class="slot-u-label">
                {{ slot.type === 'asset' && slot.height > 1 ? `${slot.u}-${slot.u + slot.height - 1}U` : `${slot.u}U` }}
              </span>
              <template v-if="slot.type === 'asset' && slot.asset">
                <el-tooltip placement="right" :show-after="300">
                  <template #content>
                    <div>编码: {{ slot.asset.asset_code }}</div>
                    <div>名称: {{ slot.asset.asset_name }}</div>
                    <div>品牌: {{ slot.asset.brand }}</div>
                    <div>型号: {{ slot.asset.model }}</div>
                    <div>状态: {{ statusNameMap[slot.asset.status] || slot.asset.status }}</div>
                    <div>U位: {{ slot.asset.u_position }}-{{ slot.asset.u_position + slot.asset.u_height - 1 }}U</div>
                  </template>
                  <span class="slot-asset-info">
                    {{ slot.asset.asset_name }}
                    <span v-if="slot.asset.model" class="slot-model">{{ slot.asset.model }}</span>
                  </span>
                </el-tooltip>
              </template>
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
                {{ row.u_position }}-{{ row.u_position + row.u_height - 1 }}U
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
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  getCabinets, createCabinet, updateCabinet, deleteCabinet, getCabinetUsage,
  moveAssetInCabinet,
  type Cabinet, type CabinetUsage, type CabinetAssetItem, type AssetType, type AssetStatus
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

// 状态颜色映射
const statusColorMap: Record<string, string> = {
  in_use: '#409eff',
  maintenance: '#e6a23c',
  borrowed: '#f2c037',
  in_stock: '#909399',
  scrapped: '#f56c6c',
}

// 状态名称映射
const statusNameMap: Record<string, string> = {
  in_use: '使用中',
  maintenance: '维护中',
  borrowed: '借出',
  in_stock: '库存',
  scrapped: '报废',
}

// 构建 U 位渲染列表
interface RackSlot {
  type: 'asset' | 'empty'
  u: number
  height: number
  asset?: CabinetAssetItem
}

const rackSlots = computed<RackSlot[]>(() => {
  if (!currentUsage.value) return []
  const totalU = currentUsage.value.total_u
  const assets = currentUsage.value.assets || []

  // 构建 U 位占用映射: u_number -> asset
  const uMap = new Map<number, CabinetAssetItem>()
  for (const asset of assets) {
    for (let u = asset.u_position; u < asset.u_position + asset.u_height; u++) {
      uMap.set(u, asset)
    }
  }

  const slots: RackSlot[] = []
  let u = totalU // 从顶部开始
  while (u >= 1) {
    const asset = uMap.get(u)
    if (asset && u === asset.u_position + asset.u_height - 1) {
      // 这是设备的最顶部 U 位，渲染整个设备块
      slots.push({ type: 'asset', u: asset.u_position, height: asset.u_height, asset })
      u -= asset.u_height
    } else if (asset) {
      // 这个 U 位被设备占用但不是起始位，跳过
      u--
    } else {
      // 空闲 U 位
      slots.push({ type: 'empty', u, height: 1 })
      u--
    }
  }
  return slots
})

// 拖拽状态
const dragAsset = ref<CabinetAssetItem | null>(null)
const dropTargetU = ref<number | null>(null)

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
  dragAsset.value = null
  dropTargetU.value = null
  usageDialogVisible.value = true

  try {
    const res = await getCabinetUsage(row.id)
    if (res) {
      currentUsage.value = res as unknown as CabinetUsage
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
        row_number: String(form.row_number),
        column_number: String(form.column_number),
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
        row_number: String(form.row_number),
        column_number: String(form.column_number),
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

// 检查U位是否被占用（用于拖拽预校验）
function isUnitOccupied(unitNumber: number): boolean {
  if (!currentUsage.value?.assets) return false
  return currentUsage.value.assets.some(
    asset => unitNumber >= asset.u_position && unitNumber < asset.u_position + asset.u_height
  )
}

// 拖拽功能
function onDragStart(event: DragEvent, slot: RackSlot) {
  if (slot.type !== 'asset' || !slot.asset) return
  dragAsset.value = slot.asset
  event.dataTransfer?.setData('text/plain', String(slot.asset.asset_id))
}

function onDragOver(event: DragEvent, slot: RackSlot) {
  if (!dragAsset.value || slot.type !== 'empty') return
  event.preventDefault()
  dropTargetU.value = slot.u
}

function onDragLeave(_event: DragEvent) {
  dropTargetU.value = null
}

function isDragTarget(slot: RackSlot): boolean {
  if (!dragAsset.value || !dropTargetU.value || slot.type !== 'empty') return false
  return slot.u === dropTargetU.value
}

async function onDrop(event: DragEvent, slot: RackSlot) {
  event.preventDefault()
  if (!dragAsset.value || slot.type !== 'empty' || !currentCabinet.value) {
    dragAsset.value = null
    dropTargetU.value = null
    return
  }

  const assetId = dragAsset.value.asset_id
  const newUPosition = slot.u

  dragAsset.value = null
  dropTargetU.value = null

  try {
    await moveAssetInCabinet(currentCabinet.value.id, {
      asset_id: assetId,
      new_u_position: newUPosition
    })
    ElMessage.success('移动成功')
    // 刷新 U 位图
    await viewUsage(currentCabinet.value)
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    const msg = err?.response?.data?.detail || '移动失败'
    ElMessage.error(typeof msg === 'string' ? msg : '移动失败：U位冲突或超出范围')
  }
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
@use '@/styles/mixins-25d' as *;

.cabinet-page {
  @include page-list;
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
        max-height: 500px;
        overflow-y: auto;
        border: 2px solid var(--border-color, #dcdfe6);
        border-radius: var(--radius-base, 4px);
        background: var(--bg-card, #1a2a4a);
      }

      .rack-slot {
        display: flex;
        align-items: center;
        min-height: 28px;
        padding: 0 12px;
        border-bottom: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
        font-size: 12px;
        transition: all 0.2s;
        cursor: default;

        &--asset {
          cursor: grab;
          border-left: 3px solid rgba(255, 255, 255, 0.3);
          color: #fff;

          &:active {
            cursor: grabbing;
          }
        }

        &--empty {
          background: var(--bg-card, #1a2a4a);
          color: var(--text-secondary, rgba(255, 255, 255, 0.45));
        }

        &--drop-target {
          background: rgba(64, 158, 255, 0.3) !important;
          border: 2px dashed #409eff;
        }

        .slot-u-label {
          width: 60px;
          font-weight: 500;
          flex-shrink: 0;
        }

        .slot-asset-info {
          flex: 1;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          font-weight: 500;
          cursor: pointer;
        }

        .slot-model {
          margin-left: 8px;
          opacity: 0.8;
          font-weight: normal;
          font-size: 11px;
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
