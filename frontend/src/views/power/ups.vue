<template>
  <div class="ups-monitor">
    <!-- 顶部汇总 -->
    <el-row :gutter="16" class="summary-bar">
      <el-col :span="8">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-content">
            <span class="summary-label">UPS总数</span>
            <span class="summary-value primary">{{ totalCount }}</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-content">
            <span class="summary-label">在线</span>
            <span class="summary-value success">{{ onlineCount }}</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-content">
            <span class="summary-label">告警</span>
            <span class="summary-value danger">{{ alarmCount }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- UPS列表 -->
    <el-card shadow="hover" class="table-card">
      <template #header>
        <div class="card-header">
          <span>UPS设备列表</span>
          <div class="header-actions">
            <el-button type="primary" link @click="openCreateDialog">新增UPS</el-button>
            <el-button type="primary" link @click="loadData">
              <el-icon><Refresh /></el-icon> 刷新
            </el-button>
          </div>
        </div>
      </template>
      <el-table
        :data="upsList"
        stripe
        border
        v-loading="loading"
        @row-click="openDetail"
        highlight-current-row
        style="cursor: pointer;"
      >
        <el-table-column prop="device_code" label="设备编码" width="140" />
        <el-table-column prop="device_name" label="设备名称" min-width="150" />
        <el-table-column prop="ups_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="row.ups_type === 'modular' ? 'warning' : 'primary'" size="small">
              {{ row.ups_type === 'modular' ? '模块化' : '单机' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="rated_capacity" label="额定容量(kVA)" width="130" align="center" />
        <el-table-column prop="load_rate" label="负载率(%)" width="160">
          <template #default="{ row }">
            <el-progress
              v-if="row.load_rate !== undefined"
              :percentage="Math.min(row.load_rate, 100)"
              :stroke-width="14"
              :color="getLoadColor(row.load_rate)"
              :format="(p: number) => `${p.toFixed(1)}%`"
            />
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="openEditDialog(row)">编辑</el-button>
            <el-button link type="danger" @click.stop="confirmDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && upsList.length === 0" description="暂无UPS设备数据" />
    </el-card>

    <!-- 详情抽屉 -->
    <el-drawer v-model="drawerVisible" title="UPS详情" size="480px" direction="rtl">
      <div v-if="detailLoading" v-loading="true" style="height: 200px;" />
      <template v-else-if="detail">
        <el-descriptions :column="1" border class="detail-desc">
          <el-descriptions-item label="设备编码">{{ detail.device_code }}</el-descriptions-item>
          <el-descriptions-item label="设备名称">{{ detail.device_name }}</el-descriptions-item>
          <el-descriptions-item label="类型">
            {{ detail.ups_type === 'modular' ? '模块化' : '单机' }}
          </el-descriptions-item>
          <el-descriptions-item label="额定容量">{{ detail.rated_capacity }} kVA</el-descriptions-item>
        </el-descriptions>

        <h4 class="section-title">实时参数</h4>
        <el-descriptions :column="1" border class="detail-desc">
          <el-descriptions-item
            v-for="param in detailParams"
            :key="param.key"
            :label="param.label"
          >
            <div class="param-row">
              <span>{{ param.value }} {{ param.unit }}</span>
              <el-tag
                :type="param.status === 'alarm' ? 'danger' : 'success'"
                size="small"
              >
                {{ param.status === 'alarm' ? '告警' : '正常' }}
              </el-tag>
            </div>
          </el-descriptions-item>
        </el-descriptions>
      </template>
      <el-empty v-else description="暂无详情数据" />
    </el-drawer>

    <!-- 新增弹窗 -->
    <el-dialog v-model="createDialogVisible" title="新增UPS设备" width="560px">
      <el-form :model="createForm" label-width="120px">
        <el-form-item label="关联设备" required>
          <el-select v-model="createForm.device_id" filterable style="width: 100%;" placeholder="请选择设备">
            <el-option v-for="dev in deviceOptions" :key="dev.id" :label="dev.label" :value="dev.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="UPS类型" required>
          <el-select v-model="createForm.ups_type" style="width: 100%;">
            <el-option label="模块化" value="modular" />
            <el-option label="单机" value="standalone" />
          </el-select>
        </el-form-item>
        <el-form-item label="额定容量(kVA)">
          <el-input-number v-model="createForm.rated_capacity" :min="1" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="额定电压(V)">
          <el-input-number v-model="createForm.rated_voltage" :min="1" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="相数">
          <el-input-number v-model="createForm.phase_count" :min="1" :max="3" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="电池组数量">
          <el-input-number v-model="createForm.battery_group_count" :min="0" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="旁路功能">
          <el-switch v-model="createForm.bypass_enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitCreate">确定</el-button>
      </template>
    </el-dialog>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="editDialogVisible" title="编辑UPS设备" width="560px">
      <el-form :model="editForm" label-width="120px">
        <el-form-item label="UPS类型" required>
          <el-select v-model="editForm.ups_type" style="width: 100%;">
            <el-option label="模块化" value="modular" />
            <el-option label="单机" value="standalone" />
          </el-select>
        </el-form-item>
        <el-form-item label="额定容量(kVA)">
          <el-input-number v-model="editForm.rated_capacity" :min="1" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="额定电压(V)">
          <el-input-number v-model="editForm.rated_voltage" :min="1" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="相数">
          <el-input-number v-model="editForm.phase_count" :min="1" :max="3" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="电池组数量">
          <el-input-number v-model="editForm.battery_group_count" :min="0" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="旁路功能">
          <el-switch v-model="editForm.bypass_enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getUPSList, getUPSDetail, createUPS, updateUPS, deleteUPS } from '@/api/modules/power'
import { getDeviceList } from '@/api/modules/device'

const loading = ref(false)
const drawerVisible = ref(false)
const detailLoading = ref(false)
const saving = ref(false)
const createDialogVisible = ref(false)
const editDialogVisible = ref(false)
const editingId = ref<number | null>(null)

interface UPSItem {
  id: number
  device_code: string
  device_name: string
  ups_type: string
  rated_capacity: number
  load_rate?: number
  status: string
}

interface UPSDetailData {
  device_code: string
  device_name: string
  ups_type: string
  rated_capacity: number
  points?: Array<{
    point_name: string
    value: number | null
    unit: string
    status: string
  }>
}

interface DetailParam {
  key: string
  label: string
  value: string
  unit: string
  status: string
}
interface DeviceOption {
  id: number
  label: string
}

const upsList = ref<UPSItem[]>([])
const totalCount = ref(0)  // UPS总数
const detail = ref<UPSDetailData | null>(null)
const detailParams = ref<DetailParam[]>([])
const createForm = reactive({
  device_id: undefined as number | undefined,
  ups_type: 'modular',
  rated_capacity: 200,
  rated_voltage: 380,
  phase_count: 3,
  battery_group_count: 1,
  bypass_enabled: true
})
const editForm = reactive({
  ups_type: 'modular',
  rated_capacity: 200,
  rated_voltage: 380,
  phase_count: 3,
  battery_group_count: 1,
  bypass_enabled: true
})
const deviceOptions = ref<DeviceOption[]>([])

const mockUPSList: UPSItem[] = [
  { id: 1, device_code: 'UPS-F1-01', device_name: 'F1 1号UPS', ups_type: 'modular', rated_capacity: 200, load_rate: 58.3, status: 'normal' },
  { id: 2, device_code: 'UPS-B01', device_name: 'B栋主UPS', ups_type: 'standalone', rated_capacity: 120, load_rate: 72.1, status: 'normal' }
]

const mockDetailParams: DetailParam[] = [
  { key: 'input_voltage', label: '输入电压', value: '380.2', unit: 'V', status: 'normal' },
  { key: 'output_voltage', label: '输出电压', value: '220.1', unit: 'V', status: 'normal' },
  { key: 'input_freq', label: '输入频率', value: '50.01', unit: 'Hz', status: 'normal' },
  { key: 'output_freq', label: '输出频率', value: '50.00', unit: 'Hz', status: 'normal' },
  { key: 'power_factor', label: '功率因数', value: '0.98', unit: '', status: 'normal' },
  { key: 'load_rate', label: '负载率', value: '58.3', unit: '%', status: 'normal' },
  { key: 'backup_time', label: '备电时间', value: '30', unit: 'min', status: 'normal' },
  { key: 'busbar_temp', label: '母排温度', value: '38.5', unit: '°C', status: 'normal' },
  { key: 'mains_status', label: '市电状态', value: '正常', unit: '', status: 'normal' },
  { key: 'spd_status', label: '防雷器状态', value: '正常', unit: '', status: 'normal' }
]

const onlineCount = computed(() => upsList.value.filter(u => u.status === 'normal' || u.status === 'online').length)
const alarmCount = computed(() => upsList.value.filter(u => u.status === 'alarm' || u.status === 'warning').length)

type TagType = 'success' | 'warning' | 'danger' | 'info'

function statusTagType(status: string): TagType {
  const map: Record<string, TagType> = { normal: 'success', online: 'success', alarm: 'danger', warning: 'warning', offline: 'info' }
  return map[status] || 'info'
}

function statusLabel(status: string): string {
  const map: Record<string, string> = { normal: '正常', online: '在线', alarm: '告警', warning: '预警', offline: '离线' }
  return map[status] || status
}

function getLoadColor(rate: number): string {
  if (rate < 60) return '#52c41a'
  if (rate < 80) return '#faad14'
  return '#f5222d'
}

async function loadData() {
  loading.value = true
  try {
    const res = await getUPSList()
    const data = res?.data ?? res
    upsList.value = Array.isArray(data) ? data : (data?.items ?? [])
    totalCount.value = data?.total ?? upsList.value.length
  } catch {
    console.warn('UPS列表API未就绪，使用模拟数据')
    upsList.value = mockUPSList
  } finally {
    loading.value = false
  }
}

async function openDetail(row: UPSItem) {
  drawerVisible.value = true
  detailLoading.value = true
  detail.value = null
  detailParams.value = []
  try {
    const res = await getUPSDetail(row.id)
    const data = res?.data ?? res
    detail.value = data as UPSDetailData
    if (detail.value?.points && detail.value.points.length > 0) {
      detailParams.value = detail.value.points.map((p, i) => ({
        key: String(i),
        label: p.point_name,
        value: p.value !== null ? String(p.value) : '-',
        unit: p.unit || '',
        status: p.status || 'normal'
      }))
    } else {
      detailParams.value = []
    }
  } catch {
    console.warn('UPS详情API未就绪，使用模拟数据')
    detail.value = { device_code: row.device_code, device_name: row.device_name, ups_type: row.ups_type, rated_capacity: row.rated_capacity }
    detailParams.value = mockDetailParams
  } finally {
    detailLoading.value = false
  }
}
async function loadDeviceOptions() {
  try {
    const res = await getDeviceList({ page: 1, page_size: 100, device_type: 'UPS' })
    const data = res as { items?: Array<{ id: number; device_name?: string; device_code?: string }> }
    deviceOptions.value = (data.items ?? []).map(item => ({
      id: item.id,
      label: `${item.device_name ?? 'UPS'} (${item.device_code ?? '-'})`
    }))
  } catch {
    deviceOptions.value = []
  }
}
function openCreateDialog() {
  createForm.device_id = undefined
  createForm.ups_type = 'modular'
  createForm.rated_capacity = 200
  createForm.rated_voltage = 380
  createForm.phase_count = 3
  createForm.battery_group_count = 1
  createForm.bypass_enabled = true
  createDialogVisible.value = true
}
async function submitCreate() {
  if (!createForm.device_id) {
    ElMessage.warning('请选择关联设备')
    return
  }
  saving.value = true
  try {
    await createUPS({
      device_id: createForm.device_id,
      ups_type: createForm.ups_type,
      rated_capacity: createForm.rated_capacity,
      rated_voltage: createForm.rated_voltage,
      phase_count: createForm.phase_count,
      battery_group_count: createForm.battery_group_count,
      bypass_enabled: createForm.bypass_enabled
    })
    ElMessage.success('新增UPS设备成功')
    createDialogVisible.value = false
    await loadData()
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : '新增失败'
    ElMessage.error(message)
  } finally {
    saving.value = false
  }
}
function openEditDialog(row: UPSItem) {
  editingId.value = row.id
  editForm.ups_type = row.ups_type
  editForm.rated_capacity = row.rated_capacity
  editForm.rated_voltage = 380
  editForm.phase_count = 3
  editForm.battery_group_count = 1
  editForm.bypass_enabled = true
  editDialogVisible.value = true
}
async function submitEdit() {
  if (!editingId.value) {
    ElMessage.warning('编辑信息不完整')
    return
  }
  saving.value = true
  try {
    await updateUPS(editingId.value, {
      ups_type: editForm.ups_type,
      rated_capacity: editForm.rated_capacity,
      rated_voltage: editForm.rated_voltage,
      phase_count: editForm.phase_count,
      battery_group_count: editForm.battery_group_count,
      bypass_enabled: editForm.bypass_enabled
    })
    ElMessage.success('编辑UPS设备成功')
    editDialogVisible.value = false
    await loadData()
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : '编辑失败'
    ElMessage.error(message)
  } finally {
    saving.value = false
  }
}
async function confirmDelete(row: UPSItem) {
  const message = [
    `确定删除UPS设备「${row.device_name}」吗？`,
    '',
    '此操作将同时删除关联的电池组和点位数据。'
  ].join('<br/>')
  try {
    await ElMessageBox.confirm(message, '删除确认', {
      type: 'warning',
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      dangerouslyUseHTMLString: true
    })
    saving.value = true
    await deleteUPS(row.id)
    ElMessage.success('删除UPS设备成功')
    await loadData()
  } catch (error: unknown) {
    if (error !== 'cancel') {
      const messageText = error instanceof Error ? error.message : '删除失败'
      ElMessage.error(messageText)
    }
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadDeviceOptions()
  await loadData()
})
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.ups-monitor {
  @include page-list;
  .summary-bar {
    margin-bottom: 16px;
  }

  .summary-card {
    background: var(--bg-card);
    border-color: var(--border-color);

    .summary-content {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 4px 0;
    }

    .summary-label {
      font-size: 14px;
      color: var(--text-secondary);
    }

    .summary-value {
      font-size: 28px;
      font-weight: 700;

      &.primary { color: var(--primary-color, #1890ff); }
      &.success { color: var(--success-color, #52c41a); }
      &.danger { color: var(--error-color, #f5222d); }
    }
  }

  .table-card {
    background: var(--bg-card);
    border-color: var(--border-color);
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    color: var(--text-primary);
  }
  .header-actions {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .text-muted {
    color: var(--text-secondary);
  }

  .section-title {
    margin: 20px 0 12px;
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .detail-desc {
    margin-bottom: 8px;
  }

  .param-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
  }
}
</style>
