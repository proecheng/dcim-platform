<template>
  <div class="cooling-topology-page">
    <!-- 顶部工具栏 -->
    <div class="cooling-toolbar">
      <span class="toolbar-title">制冷区域配置</span>
      <el-button type="primary" :icon="Plus" @click="openZoneDialog()">新增制冷区域</el-button>
    </div>

    <!-- 制冷区域表格 -->
    <div class="cooling-table-panel">
      <el-table :data="zoneList" size="small" v-loading="loading">
        <el-table-column prop="zone_code" label="区域编码" min-width="120" show-overflow-tooltip />
        <el-table-column prop="zone_name" label="区域名称" min-width="140" show-overflow-tooltip />
        <el-table-column prop="design_capacity_kw" label="设计容量(kW)" width="130" align="center">
          <template #default="{ row }">
            {{ row.design_capacity_kw ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column label="关联空调数" width="110" align="center">
          <template #default="{ row }">
            <el-tag size="small">{{ row.cooling_units?.length ?? 0 }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="关联机柜数" width="110" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="success">{{ row.cabinets?.length ?? 0 }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" text size="small" :icon="Edit" @click="openZoneDialog(row)">编辑</el-button>
            <el-button type="warning" text size="small" :icon="DataAnalysis" @click="openCapacityDialog(row)">容量</el-button>
            <el-button type="danger" text size="small" :icon="Delete" @click="handleDeleteZone(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 新增/编辑制冷区域对话框 -->
    <el-dialog
      v-model="zoneDialogVisible"
      :title="isEditZone ? '编辑制冷区域' : '新增制冷区域'"
      width="720px"
      
    >
      <el-form ref="zoneFormRef" :model="zoneForm" :rules="zoneRules" label-width="100px">
        <el-form-item label="区域名称" prop="zone_name">
          <el-input v-model="zoneForm.zone_name" placeholder="请输入区域名称" />
        </el-form-item>
        <el-form-item label="所属房间" prop="room_id">
          <el-select v-model="zoneForm.room_id" placeholder="请选择房间（可选）" clearable filterable style="width: 100%">
            <el-option
              v-for="room in roomOptions"
              :key="room.id"
              :label="`${room.room_code} - ${room.room_name}`"
              :value="room.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="设计容量(kW)" prop="design_capacity_kw">
          <el-input-number v-model="zoneForm.design_capacity_kw" :min="0" :precision="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="zoneForm.description" type="textarea" :rows="2" placeholder="请输入描述" />
        </el-form-item>

        <!-- 关联空调 -->
        <el-form-item label="关联空调">
          <el-transfer
            v-model="zoneForm.cooling_unit_ids"
            :data="coolingUnitTransferData"
            :titles="['可选空调', '已关联空调']"
            filterable
            filter-placeholder="搜索空调"
            :props="{ key: 'key', label: 'label' }"
          />
        </el-form-item>

        <!-- 关联机柜 -->
        <el-form-item label="关联机柜">
          <el-transfer
            v-model="zoneForm.cabinet_ids"
            :data="cabinetTransferData"
            :titles="['可选机柜', '已关联机柜']"
            filterable
            filter-placeholder="搜索机柜"
            :props="{ key: 'key', label: 'label' }"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="zoneDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitZone">确定</el-button>
      </template>
    </el-dialog>

    <!-- 容量查看对话框 -->
    <el-dialog v-model="capacityDialogVisible" title="制冷区域容量" width="480px">
      <div v-if="capacityData" class="capacity-detail">
        <div class="capacity-row">
          <span class="capacity-label">区域名称</span>
          <span class="capacity-value">{{ capacityData.zone_name }}</span>
        </div>
        <div class="capacity-row">
          <span class="capacity-label">设计容量</span>
          <span class="capacity-value">{{ capacityData.design_capacity_kw ?? '-' }} kW</span>
        </div>
        <div class="capacity-row">
          <span class="capacity-label">机柜总功率</span>
          <span class="capacity-value">{{ capacityData.total_cabinet_power }} kW</span>
        </div>
        <div class="capacity-row">
          <span class="capacity-label">使用率</span>
          <div class="capacity-progress">
            <el-progress
              :percentage="capacityData.utilization_rate ?? 0"
              :color="progressColor(capacityData.utilization_rate ?? 0)"
              :stroke-width="18"
              :text-inside="true"
            />
          </div>
        </div>
      </div>
      <div v-else class="capacity-loading">
        <el-empty description="暂无容量数据" />
      </div>
      <template #footer>
        <el-button @click="capacityDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Plus, Edit, Delete, DataAnalysis } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance } from 'element-plus'
import { getCoolingUnitList } from '@/api/modules/cooling'
import { getCabinets } from '@/api/modules/asset'
import { getRooms } from '@/api/modules/spatial'
import {
  getCoolingZones,
  createCoolingZone,
  updateCoolingZone,
  deleteCoolingZone,
  getCoolingZoneCapacity
} from '@/api/modules/topologyConfig'
import type {
  CoolingZoneResponse,
  CoolingZoneCreate,
  CoolingZoneCapacityResponse
} from '@/api/modules/topologyConfig'

// ==================== 制冷区域列表 ====================

const loading = ref(false)
const zoneList = ref<CoolingZoneResponse[]>([])

async function loadZoneList() {
  loading.value = true
  try {
    const res = await getCoolingZones()
    const data = (res as unknown as { data?: CoolingZoneResponse[] })
    zoneList.value = data.data || (Array.isArray(res) ? res as CoolingZoneResponse[] : [])
  } catch {
    ElMessage.error('加载制冷区域列表失败')
  } finally {
    loading.value = false
  }
}

// ==================== 选项数据 ====================

interface RoomOption {
  id: number
  room_code: string
  room_name: string
}

interface CoolingUnitOption {
  id: number
  device_code: string
  device_name: string
}

interface CabinetOption {
  id: number
  cabinet_code: string
  cabinet_name: string
}

const roomOptions = ref<RoomOption[]>([])
const coolingUnitOptions = ref<CoolingUnitOption[]>([])
const cabinetOptionsList = ref<CabinetOption[]>([])

const coolingUnitTransferData = computed(() =>
  coolingUnitOptions.value.map(u => ({
    key: u.id,
    label: `${u.device_code} - ${u.device_name}`
  }))
)

const cabinetTransferData = computed(() =>
  cabinetOptionsList.value.map(c => ({
    key: c.id,
    label: `${c.cabinet_code} - ${c.cabinet_name}`
  }))
)

async function loadOptions() {
  try {
    const [roomRes, unitRes, cabRes] = await Promise.all([
      getRooms(),
      getCoolingUnitList({ page: 1, page_size: 500 }),
      getCabinets({ page: 1, page_size: 1000 })
    ])

    // 房间
    const roomData = (roomRes as unknown as { data?: RoomOption[]; items?: RoomOption[] })
    roomOptions.value = roomData.data || roomData.items || (Array.isArray(roomRes) ? roomRes as RoomOption[] : [])

    // 空调
    const unitData = (unitRes as unknown as { data?: CoolingUnitOption[]; items?: CoolingUnitOption[] })
    coolingUnitOptions.value = unitData.items || unitData.data || (Array.isArray(unitRes) ? unitRes as CoolingUnitOption[] : [])

    // 机柜
    const cabData = (cabRes as unknown as { data?: CabinetOption[]; items?: CabinetOption[] })
    cabinetOptionsList.value = cabData.items || cabData.data || (Array.isArray(cabRes) ? cabRes as CabinetOption[] : [])
  } catch {
    // 选项加载失败不阻塞页面
  }
}

// ==================== 新增/编辑对话框 ====================

const zoneDialogVisible = ref(false)
const isEditZone = ref(false)
const editingZoneId = ref(0)
const submitting = ref(false)
const zoneFormRef = ref<FormInstance>()

interface ZoneFormData {
  zone_name: string
  room_id: number | undefined
  design_capacity_kw: number | undefined
  description: string
  cabinet_ids: number[]
  cooling_unit_ids: number[]
}

const zoneForm = ref<ZoneFormData>({
  zone_name: '',
  room_id: undefined,
  design_capacity_kw: undefined,
  description: '',
  cabinet_ids: [],
  cooling_unit_ids: []
})

const zoneRules = {
  zone_name: [{ required: true, message: '请输入区域名称', trigger: 'blur' }]
}

function openZoneDialog(row?: CoolingZoneResponse) {
  if (row) {
    isEditZone.value = true
    editingZoneId.value = row.id
    zoneForm.value = {
      zone_name: row.zone_name,
      room_id: row.room_id ?? undefined,
      design_capacity_kw: row.design_capacity_kw ?? undefined,
      description: row.description ?? '',
      cabinet_ids: row.cabinets?.map(c => c.id) ?? [],
      cooling_unit_ids: row.cooling_units?.map(u => u.id) ?? []
    }
  } else {
    isEditZone.value = false
    editingZoneId.value = 0
    zoneForm.value = {
      zone_name: '',
      room_id: undefined,
      design_capacity_kw: undefined,
      description: '',
      cabinet_ids: [],
      cooling_unit_ids: []
    }
  }
  zoneDialogVisible.value = true
}

function resetZoneForm() {
  isEditZone.value = false
  editingZoneId.value = 0
}

async function submitZone() {
  const valid = await zoneFormRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const payload: CoolingZoneCreate = {
      zone_name: zoneForm.value.zone_name,
      room_id: zoneForm.value.room_id,
      design_capacity_kw: zoneForm.value.design_capacity_kw,
      description: zoneForm.value.description || undefined,
      cabinet_ids: zoneForm.value.cabinet_ids,
      cooling_unit_ids: zoneForm.value.cooling_unit_ids
    }

    if (isEditZone.value) {
      await updateCoolingZone(editingZoneId.value, payload)
      ElMessage.success('制冷区域已更新')
    } else {
      await createCoolingZone(payload)
      ElMessage.success('制冷区域已创建')
    }
    zoneDialogVisible.value = false
    await loadZoneList()
  } catch {
    ElMessage.error(isEditZone.value ? '更新制冷区域失败' : '创建制冷区域失败')
  } finally {
    submitting.value = false
  }
}

async function handleDeleteZone(row: CoolingZoneResponse) {
  try {
    await ElMessageBox.confirm(`确定删除制冷区域「${row.zone_name}」吗？`, '确认删除', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteCoolingZone(row.id)
    ElMessage.success('制冷区域已删除')
    await loadZoneList()
  } catch {
    ElMessage.error('删除制冷区域失败')
  }
}

// ==================== 容量查看 ====================

const capacityDialogVisible = ref(false)
const capacityData = ref<CoolingZoneCapacityResponse | null>(null)

async function openCapacityDialog(row: CoolingZoneResponse) {
  capacityData.value = null
  capacityDialogVisible.value = true
  try {
    const res = await getCoolingZoneCapacity(row.id)
    capacityData.value = res.data || (res as unknown as CoolingZoneCapacityResponse)
  } catch {
    ElMessage.error('获取容量数据失败')
  }
}

function progressColor(percentage: number): string {
  if (percentage > 90) return '#f56c6c'
  if (percentage > 70) return '#e6a23c'
  return '#67c23a'
}

// ==================== 生命周期 ====================

onMounted(() => {
  loadZoneList()
  loadOptions()
})
</script>

<style scoped>
.cooling-topology-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 16px;
  gap: 16px;
  background: #f5f7fa;
}

.cooling-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  flex-shrink: 0;
}

.toolbar-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.cooling-table-panel {
  flex: 1;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  padding: 16px;
  overflow: auto;
}

/* 容量详情 */
.capacity-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 8px 0;
}

.capacity-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.capacity-label {
  width: 90px;
  flex-shrink: 0;
  font-size: 13px;
  color: #909399;
  text-align: right;
}

.capacity-value {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.capacity-progress {
  flex: 1;
}

.capacity-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 120px;
}

/* Transfer 组件样式调整 */
:deep(.el-transfer-panel) {
  width: 240px;
}
</style>
