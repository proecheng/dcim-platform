<template>
  <div class="battery-monitor">
    <el-card shadow="hover" class="table-card">
      <template #header>
        <div class="card-header">
          <span>电池组列表</span>
          <div class="header-actions">
            <el-button type="primary" link @click="openCreateDialog">新增电池组</el-button>
            <el-button type="primary" link @click="loadData">
              <el-icon><Refresh /></el-icon> 刷新
            </el-button>
          </div>
        </div>
      </template>

      <el-table
        :data="batteryList"
        stripe
        border
        v-loading="loading"
        @row-click="openDetail"
        highlight-current-row
        style="cursor: pointer;"
      >
        <el-table-column prop="group_name" label="组名" min-width="130" />
        <el-table-column prop="ups_name" label="关联UPS" width="160" />
        <el-table-column prop="battery_type" label="电池类型" width="120">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ batteryTypeLabel(row.battery_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="rated_capacity" label="额定容量(Ah)" width="120" align="center" />
        <el-table-column label="SOH(%)" width="160">
          <template #default="{ row }">
            <el-progress
              :percentage="Math.min(row.soh ?? 0, 100)"
              :stroke-width="14"
              :color="getSohColor(row.soh ?? 0)"
              :format="(p: number) => `${p.toFixed(1)}%`"
            />
          </template>
        </el-table-column>
        <el-table-column label="SOC(%)" width="160">
          <template #default="{ row }">
            <el-progress
              :percentage="Math.min(row.soc ?? 0, 100)"
              :stroke-width="14"
              :color="getSocColor(row.soc ?? 0)"
              :format="(p: number) => `${p.toFixed(1)}%`"
            />
          </template>
        </el-table-column>
        <el-table-column prop="voltage" label="电压(V)" width="100" align="center">
          <template #default="{ row }">{{ row.voltage?.toFixed(1) ?? '-' }}</template>
        </el-table-column>
        <el-table-column prop="temperature" label="温度(°C)" width="100" align="center">
          <template #default="{ row }">
            <span :class="{ 'temp-warn': (row.temperature ?? 0) > 40 }">{{ row.temperature?.toFixed(1) ?? '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="charge_status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="chargeStatusType(row.charge_status)" size="small">{{ chargeStatusLabel(row.charge_status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="openEditDialog(row)">编辑</el-button>
            <el-button link type="danger" @click.stop="confirmDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && batteryList.length === 0" description="暂无电池组数据" />
    </el-card>

    <el-drawer v-model="drawerVisible" title="电池组详情" size="480px" direction="rtl">
      <div v-if="detailLoading" v-loading="true" style="height: 200px;" />
      <template v-else-if="detail">
        <h4 class="section-title">基本信息</h4>
        <el-descriptions :column="1" border class="detail-desc">
          <el-descriptions-item label="电池类型">{{ batteryTypeLabel(detail.battery_type) }}</el-descriptions-item>
          <el-descriptions-item label="额定容量">{{ detail.rated_capacity }} Ah</el-descriptions-item>
          <el-descriptions-item label="额定电压">{{ detail.rated_voltage }} V</el-descriptions-item>
          <el-descriptions-item label="电芯数量">{{ detail.cell_count }}</el-descriptions-item>
        </el-descriptions>

        <h4 class="section-title">实时参数</h4>
        <el-descriptions :column="1" border class="detail-desc">
          <el-descriptions-item label="电流">{{ detailRealtime.current ?? '-' }} A</el-descriptions-item>
          <el-descriptions-item label="电压">{{ detailRealtime.voltage ?? '-' }} V</el-descriptions-item>
          <el-descriptions-item label="温度">{{ detailRealtime.temperature ?? '-' }} °C</el-descriptions-item>
          <el-descriptions-item label="内阻">{{ detailRealtime.resistance ?? '-' }} mΩ</el-descriptions-item>
          <el-descriptions-item label="备电时间">{{ detailRealtime.backup_time ?? '-' }} min</el-descriptions-item>
          <el-descriptions-item label="放电次数">{{ detailRealtime.discharge_count ?? '-' }}</el-descriptions-item>
        </el-descriptions>
      </template>
      <el-empty v-else description="暂无详情数据" />
    </el-drawer>

    <el-dialog v-model="createDialogVisible" title="新增电池组" width="560px">
      <el-form :model="createForm" label-width="120px">
        <el-form-item label="组名" required>
          <el-input v-model="createForm.group_name" />
        </el-form-item>
        <el-form-item label="关联UPS" required>
          <el-select v-model="createForm.ups_device_id" filterable style="width: 100%;" placeholder="请选择UPS设备">
            <el-option v-for="ups in upsOptions" :key="ups.id" :label="ups.label" :value="ups.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="电池类型" required>
          <el-select v-model="createForm.battery_type" style="width: 100%;">
            <el-option label="铅酸" value="lead_acid" />
            <el-option label="锂电" value="lithium" />
            <el-option label="镍氢" value="nickel" />
          </el-select>
        </el-form-item>
        <el-form-item label="额定容量(Ah)">
          <el-input-number v-model="createForm.rated_capacity" :min="1" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="额定电压(V)">
          <el-input-number v-model="createForm.rated_voltage" :min="1" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="电芯数量">
          <el-input-number v-model="createForm.cell_count" :min="1" style="width: 100%;" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitCreate">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editDialogVisible" title="编辑电池组" width="560px">
      <el-form :model="editForm" label-width="120px">
        <el-form-item label="组名" required>
          <el-input v-model="editForm.group_name" />
        </el-form-item>
        <el-form-item label="电池类型" required>
          <el-select v-model="editForm.battery_type" style="width: 100%;">
            <el-option label="铅酸" value="lead_acid" />
            <el-option label="锂电" value="lithium" />
            <el-option label="镍氢" value="nickel" />
          </el-select>
        </el-form-item>
        <el-form-item label="额定容量(Ah)">
          <el-input-number v-model="editForm.rated_capacity" :min="1" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="额定电压(V)">
          <el-input-number v-model="editForm.rated_voltage" :min="1" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="电芯数量">
          <el-input-number v-model="editForm.cell_count" :min="1" style="width: 100%;" />
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
import {
  getBatteryList,
  getBatteryDetail,
  createBatteryGroup,
  updateBatteryGroup,
  deleteBatteryGroup,
  getUPSList
} from '@/api/modules/power'
import { notifyBatteryChanged, subscribeBatteryChanged } from '@/utils/pduSync'

interface BatteryItem {
  id: number
  ups_device_id: number
  group_name: string
  ups_name: string
  battery_type: string
  rated_capacity: number
  rated_voltage: number
  cell_count: number
  soh?: number
  soc?: number
  voltage?: number
  temperature?: number
  charge_status: string
}

interface BatteryDetailData {
  battery_type: string
  rated_capacity: number
  rated_voltage: number
  cell_count: number
}

interface BatteryRealtime {
  current?: number
  voltage?: number
  temperature?: number
  resistance?: number
  backup_time?: number
  discharge_count?: number
}

interface UpsOption {
  id: number
  label: string
}

const loading = ref(false)
const saving = ref(false)
const drawerVisible = ref(false)
const detailLoading = ref(false)

const batteryList = ref<BatteryItem[]>([])
const detail = ref<BatteryDetailData | null>(null)
const detailRealtime = ref<BatteryRealtime>({})
const upsOptions = ref<UpsOption[]>([])

const createDialogVisible = ref(false)
const editDialogVisible = ref(false)
const editingId = ref<number | null>(null)

const createForm = reactive({
  group_name: '',
  ups_device_id: undefined as number | undefined,
  battery_type: 'lead_acid',
  rated_capacity: 100,
  rated_voltage: 432,
  cell_count: 36
})

const editForm = reactive({
  group_name: '',
  battery_type: 'lead_acid',
  rated_capacity: 100,
  rated_voltage: 432,
  cell_count: 36
})

function batteryTypeLabel(type: string): string {
  const map: Record<string, string> = { lead_acid: '铅酸', lithium: '锂电', nickel: '镍氢' }
  return map[type] || type
}

type TagType = 'success' | 'warning' | 'danger' | 'info'

function chargeStatusType(status: string): TagType {
  const map: Record<string, TagType> = { float: 'success', charging: 'warning', discharge: 'danger', idle: 'info' }
  return map[status] || 'info'
}

function chargeStatusLabel(status: string): string {
  const map: Record<string, string> = { float: '浮充', charging: '充电', discharge: '放电', idle: '静置' }
  return map[status] || status
}

function getSohColor(soh: number): string {
  if (soh >= 90) return '#52c41a'
  if (soh >= 70) return '#faad14'
  return '#f5222d'
}

function getSocColor(soc: number): string {
  if (soc >= 60) return '#52c41a'
  if (soc >= 30) return '#faad14'
  return '#f5222d'
}

async function loadUpsOptions() {
  try {
    const res = await getUPSList({ page: 1, page_size: 100 })
    const data = (res?.data ?? res) as { items?: Array<{ id: number; device_name?: string; device_code?: string }> }
    upsOptions.value = (data.items ?? []).map(item => ({
      id: item.id,
      label: `${item.device_name ?? 'UPS'} (${item.device_code ?? '-'})`
    }))
  } catch {
    upsOptions.value = []
  }
}

async function loadData() {
  loading.value = true
  try {
    const res = await getBatteryList({ page: 1, page_size: 100 })
    const data = (res?.data ?? res) as { items?: Array<Record<string, unknown>> }
    const rows = data.items ?? []
    const upsMap = new Map<number, string>()
    upsOptions.value.forEach(ups => upsMap.set(ups.id, ups.label))

    batteryList.value = rows.map(row => ({
      id: Number(row.id ?? 0),
      ups_device_id: Number(row.ups_device_id ?? 0),
      group_name: String(row.group_name ?? ''),
      ups_name: upsMap.get(Number(row.ups_device_id ?? 0)) ?? `UPS#${row.ups_device_id ?? '-'}`,
      battery_type: String(row.battery_type ?? 'lead_acid'),
      rated_capacity: Number(row.rated_capacity ?? 0),
      rated_voltage: Number(row.rated_voltage ?? 0),
      cell_count: Number(row.cell_count ?? 0),
      soh: Number(row.soh ?? 100),
      soc: Number(row.soc ?? 100),
      voltage: Number(row.voltage ?? row.rated_voltage ?? 0),
      temperature: Number(row.temperature ?? 0),
      charge_status: String(row.charge_status ?? 'idle')
    }))
  } catch {
    batteryList.value = []
    ElMessage.error('电池组数据加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

async function openDetail(row: BatteryItem) {
  drawerVisible.value = true
  detailLoading.value = true
  detail.value = null
  detailRealtime.value = {}

  try {
    const res = await getBatteryDetail(row.id)
    const data = (res?.data ?? res) as {
      battery_group?: Record<string, unknown>
      points?: Array<{ point_name?: string; value?: number }>
    }

    const source = data.battery_group ?? {}
    detail.value = {
      battery_type: String(source.battery_type ?? row.battery_type),
      rated_capacity: Number(source.rated_capacity ?? row.rated_capacity),
      rated_voltage: Number(source.rated_voltage ?? row.rated_voltage),
      cell_count: Number(source.cell_count ?? row.cell_count)
    }

    const points = data.points ?? []
    const findValue = (keyword: string) => points.find(p => String(p.point_name ?? '').includes(keyword))?.value
    detailRealtime.value = {
      current: findValue('电流'),
      voltage: findValue('电压'),
      temperature: findValue('温度'),
      resistance: findValue('内阻'),
      backup_time: findValue('备电'),
      discharge_count: findValue('放电')
    }
  } catch {
    detail.value = {
      battery_type: row.battery_type,
      rated_capacity: row.rated_capacity,
      rated_voltage: row.rated_voltage,
      cell_count: row.cell_count
    }
    detailRealtime.value = {}
  } finally {
    detailLoading.value = false
  }
}

function openCreateDialog() {
  createForm.group_name = ''
  createForm.ups_device_id = undefined
  createForm.battery_type = 'lead_acid'
  createForm.rated_capacity = 100
  createForm.rated_voltage = 432
  createForm.cell_count = 36
  createDialogVisible.value = true
}

async function submitCreate() {
  if (!createForm.group_name.trim() || !createForm.ups_device_id) {
    ElMessage.warning('请完整填写电池组信息')
    return
  }

  saving.value = true
  try {
    await createBatteryGroup({
      ups_device_id: createForm.ups_device_id,
      group_name: createForm.group_name.trim(),
      battery_type: createForm.battery_type,
      rated_capacity: createForm.rated_capacity,
      rated_voltage: createForm.rated_voltage,
      cell_count: createForm.cell_count
    })

    ElMessage.success('新增电池组成功')
    createDialogVisible.value = false
    notifyBatteryChanged('create')
    await loadData()
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : '新增失败'
    ElMessage.error(message)
  } finally {
    saving.value = false
  }
}

function openEditDialog(row: BatteryItem) {
  editingId.value = row.id
  editForm.group_name = row.group_name
  editForm.battery_type = row.battery_type
  editForm.rated_capacity = row.rated_capacity
  editForm.rated_voltage = row.rated_voltage
  editForm.cell_count = row.cell_count
  editDialogVisible.value = true
}

async function submitEdit() {
  if (!editingId.value || !editForm.group_name.trim()) {
    ElMessage.warning('请完整填写编辑信息')
    return
  }

  saving.value = true
  try {
    await updateBatteryGroup(editingId.value, {
      group_name: editForm.group_name.trim(),
      battery_type: editForm.battery_type,
      rated_capacity: editForm.rated_capacity,
      rated_voltage: editForm.rated_voltage,
      cell_count: editForm.cell_count
    })

    ElMessage.success('编辑电池组成功')
    editDialogVisible.value = false
    notifyBatteryChanged('update')
    await loadData()
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : '编辑失败'
    ElMessage.error(message)
  } finally {
    saving.value = false
  }
}

async function confirmDelete(row: BatteryItem) {
  const message = [
    `确定删除电池组「${row.group_name}」吗？`,
    '',
    '此操作将同时影响以下数据：',
    '1) 电池组页面中的该电池组记录',
    '2) UPS详情页中该电池组相关信息'
  ].join('<br/>')

  try {
    await ElMessageBox.confirm(message, '删除确认', {
      type: 'warning',
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      dangerouslyUseHTMLString: true
    })

    saving.value = true
    await deleteBatteryGroup(row.id)
    ElMessage.success('删除电池组成功')
    notifyBatteryChanged('delete')
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

let unsubscribeSync: (() => void) | null = null

onMounted(async () => {
  await loadUpsOptions()
  await loadData()
  unsubscribeSync = subscribeBatteryChanged(() => {
    loadData()
  })
})

onUnmounted(() => {
  unsubscribeSync?.()
})
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.battery-monitor {
  @include page-list;

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

  .temp-warn {
    color: var(--error-color, #f5222d);
    font-weight: 600;
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
}
</style>
