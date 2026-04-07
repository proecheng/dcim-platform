<template>
  <div class="pdu-monitor">
    <el-card shadow="hover" class="table-card">
      <template #header>
        <div class="card-header">
          <div class="title-group">
            <span>机柜PDU监控（分页列表）</span>
            <span class="sub-title">当前页 {{ pagedList.length }}/{{ filteredList.length }} 条，系统总计 {{ total }} 条</span>
          </div>
          <div class="header-actions">
            <el-button type="info" link @click="goTopology">查看配电拓扑</el-button>
            <el-button type="primary" link @click="openCreateDialog">新增PDU</el-button>
            <el-button type="primary" link @click="loadData">
              <el-icon><Refresh /></el-icon> 刷新
            </el-button>
          </div>
        </div>
      </template>

      <div class="filters">
        <el-select v-model="floorFilter" clearable placeholder="楼层筛选（如 F3/F4）" style="width: 180px;">
          <el-option v-for="floor in floorOptions" :key="floor" :label="floor" :value="floor" />
        </el-select>
        <el-input
          v-model="keywordFilter"
          clearable
          placeholder="按设备编码/名称搜索（如 列头柜）"
          style="width: 260px;"
        />
      </div>

      <el-table
        :data="pagedList"
        stripe
        border
        v-loading="loading"
        @row-click="openDetail"
        highlight-current-row
        style="cursor: pointer;"
      >
        <el-table-column prop="device_code" label="设备编码" width="150" />
        <el-table-column prop="device_name" label="设备名称" min-width="150" />
        <el-table-column prop="floor" label="楼层" width="90" align="center" />
        <el-table-column prop="area" label="区域" width="120" />
        <el-table-column prop="circuit_name" label="所属回路" min-width="120" />
        <el-table-column prop="total_current" label="总电流(A)" width="110" align="center">
          <template #default="{ row }">
            {{ row.total_current?.toFixed(1) ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="temperature" label="温度(°C)" width="100" align="center">
          <template #default="{ row }">
            <span :class="{ 'temp-warn': (row.temperature ?? 0) > 45 }">
              {{ row.temperature?.toFixed(1) ?? '-' }}
            </span>
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

      <el-pagination
        class="table-pagination"
        background
        layout="total, sizes, prev, pager, next"
        :total="filteredList.length"
        :current-page="page"
        :page-size="pageSize"
        :page-sizes="[20, 50, 100]"
        @current-change="handlePageChange"
        @size-change="handleSizeChange"
      />

      <el-empty v-if="!loading && pduList.length === 0" description="暂无PDU数据" />
    </el-card>

    <el-drawer v-model="drawerVisible" :title="drawerTitle" size="620px" direction="rtl">
      <div v-if="detailLoading" v-loading="true" style="height: 200px;" />
      <template v-else-if="outlets.length > 0">
        <h4 class="section-title">插座信息</h4>
        <el-table :data="outlets" stripe border size="small">
          <el-table-column prop="outlet_no" label="插座编号" width="90" align="center" />
          <el-table-column prop="current" label="电流(A)" width="90" align="center">
            <template #default="{ row }">{{ row.current?.toFixed(2) ?? '-' }}</template>
          </el-table-column>
          <el-table-column prop="voltage" label="电压(V)" width="90" align="center">
            <template #default="{ row }">{{ row.voltage?.toFixed(1) ?? '-' }}</template>
          </el-table-column>
          <el-table-column prop="power" label="功率(W)" width="90" align="center">
            <template #default="{ row }">{{ row.power?.toFixed(1) ?? '-' }}</template>
          </el-table-column>
          <el-table-column prop="energy" label="电度(kWh)" width="100" align="center">
            <template #default="{ row }">{{ row.energy?.toFixed(2) ?? '-' }}</template>
          </el-table-column>
          <el-table-column label="通断状态" width="100" align="center">
            <template #default="{ row }">
              <el-switch
                :model-value="row.on_off"
                disabled
                active-text="通"
                inactive-text="断"
                inline-prompt
              />
            </template>
          </el-table-column>
        </el-table>
      </template>
      <el-empty v-else description="暂无插座数据" />
    </el-drawer>

    <el-dialog v-model="createDialogVisible" title="新增PDU" width="560px">
      <el-form :model="createForm" label-width="110px">
        <el-form-item label="设备编码" required>
          <el-input v-model="createForm.device_code" placeholder="例如 PDU-F3-101" />
        </el-form-item>
        <el-form-item label="设备名称" required>
          <el-input v-model="createForm.device_name" placeholder="例如 F3列头柜PDU-01" />
        </el-form-item>
        <el-form-item label="所属回路" required>
          <el-select v-model="createForm.circuit_id" filterable placeholder="请选择回路" style="width: 100%;">
            <el-option
              v-for="circuit in topologyCircuits"
              :key="circuit.id"
              :label="circuit.label"
              :value="circuit.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="额定功率(kW)">
          <el-input-number v-model="createForm.rated_power" :min="0" :precision="2" style="width: 100%;" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitCreate">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editDialogVisible" title="编辑PDU" width="560px">
      <el-form :model="editForm" label-width="110px">
        <el-form-item label="设备编码" required>
          <el-input v-model="editForm.device_code" />
        </el-form-item>
        <el-form-item label="设备名称" required>
          <el-input v-model="editForm.device_name" />
        </el-form-item>
        <el-form-item label="额定功率(kW)">
          <el-input-number v-model="editForm.rated_power" :min="0" :precision="2" style="width: 100%;" />
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
import { useRouter } from 'vue-router'
import { getPDUList } from '@/api/modules/power'
import {
  getDistributionTopology,
  createTopologyNode,
  updateTopologyNode,
  deleteTopologyNode,
  type TopologyNodeCreateRequest,
  type TopologyNodeUpdateRequest,
  type DistributionTopology
} from '@/api/modules/energy'
import { notifyPduTopologyChanged, subscribePduTopologyChanged } from '@/utils/pduSync'

interface OutletItem {
  outlet_no: string
  current?: number
  voltage?: number
  power?: number
  energy?: number
  on_off: boolean
}

interface PDUItem {
  id: number
  topology_id?: number
  device_code: string
  device_name: string
  floor: string
  area: string
  circuit_id?: number
  circuit_name?: string
  total_current?: number
  temperature?: number
  status: string
  outlets?: OutletItem[]
}

interface TopologyPDUNode {
  topology_id: number
  device_code: string
  device_name: string
  floor: string
  circuit_id: number
  circuit_name: string
}

interface CircuitOption {
  id: number
  label: string
}

interface PowerApiPoint {
  name?: string
  value?: number
}

interface PowerApiItem {
  device?: Record<string, unknown>
  points?: Record<string, PowerApiPoint>
}

const loading = ref(false)
const saving = ref(false)
const drawerVisible = ref(false)
const detailLoading = ref(false)
const drawerTitle = ref('PDU详情')

const pduList = ref<PDUItem[]>([])
const outlets = ref<OutletItem[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const floorFilter = ref('')
const keywordFilter = ref('')

const topologyPduMap = ref<Record<string, TopologyPDUNode>>({})
const topologyCircuits = ref<CircuitOption[]>([])

const createDialogVisible = ref(false)
const editDialogVisible = ref(false)
const editingTopologyId = ref<number | null>(null)

const createForm = reactive({
  device_code: '',
  device_name: '',
  circuit_id: undefined as number | undefined,
  rated_power: 22
})

const editForm = reactive({
  device_code: '',
  device_name: '',
  rated_power: 22
})

const router = useRouter()

const floorOptions = computed(() => {
  const floors = pduList.value.map(item => item.floor).filter(Boolean)
  return Array.from(new Set(floors))
})

const filteredList = computed(() => {
  const keyword = keywordFilter.value.trim().toUpperCase()
  return pduList.value.filter(item => {
    const matchFloor = !floorFilter.value || item.floor === floorFilter.value
    if (!matchFloor) return false
    if (!keyword) return true
    const target = `${item.device_code} ${item.device_name}`.toUpperCase()
    return target.includes(keyword)
  })
})

const pagedList = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredList.value.slice(start, start + pageSize.value)
})

function resolveFloor(source: string): string {
  const match = source.toUpperCase().match(/F\d+/)
  return match?.[0] ?? '未标注'
}

function generateMockOutlets(count: number): OutletItem[] {
  return Array.from({ length: count }, (_, i) => ({
    outlet_no: `#${i + 1}`,
    current: Math.random() * 8 + 0.5,
    voltage: 220 + Math.random() * 2 - 1,
    power: Math.random() * 1800 + 100,
    energy: Math.random() * 500 + 50,
    on_off: Math.random() > 0.15
  }))
}

function parseTopology(topology: DistributionTopology) {
  const pduMap: Record<string, TopologyPDUNode> = {}
  const circuits: CircuitOption[] = []

  topology.transformers.forEach(transformer => {
    transformer.meter_points.forEach(meter => {
      meter.panels.forEach(panel => {
        panel.circuits.forEach(circuit => {
          const floorSource = `${transformer.transformer_code} ${meter.meter_code} ${panel.panel_code} ${circuit.circuit_code}`
          const floor = resolveFloor(floorSource)

          circuits.push({
            id: circuit.circuit_id,
            label: `${floor} / ${panel.panel_name} / ${circuit.circuit_name}`
          })

          circuit.devices.forEach(device => {
            const deviceCode = device.device_code.toUpperCase()
            const isPdu = String(device.device_type).toUpperCase() === 'PDU' || deviceCode.includes('PDU')
            if (!isPdu) return

            pduMap[deviceCode] = {
              topology_id: device.id,
              device_code: device.device_code,
              device_name: device.device_name,
              floor,
              circuit_id: circuit.circuit_id,
              circuit_name: circuit.circuit_name
            }
          })
        })
      })
    })
  })

  topologyPduMap.value = pduMap
  topologyCircuits.value = circuits
}

async function loadAllPduPages(): Promise<PowerApiItem[]> {
  const allItems: PowerApiItem[] = []
  let requestPage = 1
  let apiTotal: number

  do {
    const res = await getPDUList({ page: requestPage, page_size: 100 })
    const data = (res?.data ?? res) as { items?: PowerApiItem[]; total?: number }
    const items = data.items ?? []
    apiTotal = typeof data.total === 'number' ? data.total : items.length
    allItems.push(...items)
    requestPage += 1
    if (items.length === 0) break
  } while (allItems.length < apiTotal)

  return allItems
}

function mapApiItemToPduItem(item: PowerApiItem): PDUItem | null {
  if (!item.device) return null

  const deviceCode = String(item.device.device_code ?? '')
  if (!deviceCode) return null

  const topo = topologyPduMap.value[deviceCode.toUpperCase()]
  if (!topo) return null

  const points = item.points ?? {}
  const pointValues = Object.values(points)
  const totalCurrent = pointValues.find(point => point.name?.includes('电流'))
  const temp = pointValues.find(point => point.name?.includes('温度'))
  const statusRaw = String(item.device.status ?? 'offline')

  return {
    id: Number(item.device.id ?? 0),
    topology_id: topo.topology_id,
    device_code: String(item.device.device_code ?? ''),
    device_name: String(item.device.device_name ?? ''),
    floor: topo.floor,
    area: String(item.device.area_code ?? ''),
    circuit_id: topo.circuit_id,
    circuit_name: topo.circuit_name,
    total_current: totalCurrent?.value,
    temperature: temp?.value,
    status: statusRaw === 'online' ? 'normal' : statusRaw
  }
}

async function loadData() {
  loading.value = true
  try {
    const topologyRes = await getDistributionTopology()
    const topology = (topologyRes.data ?? topologyRes) as DistributionTopology
    parseTopology(topology)

    const allRawItems = await loadAllPduPages()
    const list = allRawItems
      .map(mapApiItemToPduItem)
      .filter((item): item is PDUItem => item !== null)

    pduList.value = list
    total.value = list.length
    page.value = 1
  } catch {
    pduList.value = []
    total.value = 0
    ElMessage.error('PDU数据加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

function handlePageChange(nextPage: number) {
  page.value = nextPage
}

function handleSizeChange(nextSize: number) {
  pageSize.value = nextSize
  page.value = 1
}

function goTopology() {
  router.push('/power/topology')
}

type TagType = 'success' | 'warning' | 'danger' | 'info'

function statusTagType(status: string): TagType {
  const map: Record<string, TagType> = { normal: 'success', alarm: 'danger', warning: 'warning', offline: 'info' }
  return map[status] || 'info'
}

function statusLabel(status: string): string {
  const map: Record<string, string> = { normal: '正常', alarm: '告警', warning: '预警', offline: '离线' }
  return map[status] || status
}

function openDetail(row: PDUItem) {
  drawerTitle.value = `${row.device_name} — 插座详情`
  drawerVisible.value = true
  detailLoading.value = true

  setTimeout(() => {
    outlets.value = row.outlets?.length ? row.outlets : generateMockOutlets(8)
    detailLoading.value = false
  }, 300)
}

function openCreateDialog() {
  createForm.device_code = ''
  createForm.device_name = ''
  createForm.circuit_id = undefined
  createForm.rated_power = 22
  createDialogVisible.value = true
}

async function submitCreate() {
  if (!createForm.device_code.trim() || !createForm.device_name.trim() || !createForm.circuit_id) {
    ElMessage.warning('请完整填写PDU信息')
    return
  }

  saving.value = true
  try {
    const payload: TopologyNodeCreateRequest = {
      node_type: 'device',
      parent_id: createForm.circuit_id,
      parent_type: 'circuit',
      device_code: createForm.device_code.trim(),
      device_name: createForm.device_name.trim(),
      device_type: 'PDU',
      rated_power: createForm.rated_power
    }

    await createTopologyNode(payload)
    ElMessage.success('新增PDU成功')
    createDialogVisible.value = false
    notifyPduTopologyChanged('pdu', 'create')
    await loadData()
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : '新增失败'
    ElMessage.error(message)
  } finally {
    saving.value = false
  }
}

function openEditDialog(row: PDUItem) {
  if (!row.topology_id) {
    ElMessage.warning('未找到拓扑节点，无法编辑')
    return
  }
  editingTopologyId.value = row.topology_id
  editForm.device_code = row.device_code
  editForm.device_name = row.device_name
  editForm.rated_power = 22
  editDialogVisible.value = true
}

async function submitEdit() {
  if (!editingTopologyId.value || !editForm.device_code.trim() || !editForm.device_name.trim()) {
    ElMessage.warning('请完整填写编辑信息')
    return
  }

  saving.value = true
  try {
    const payload: TopologyNodeUpdateRequest = {
      node_id: editingTopologyId.value,
      node_type: 'device',
      code: editForm.device_code.trim(),
      name: editForm.device_name.trim(),
      rated_power: editForm.rated_power
    }

    await updateTopologyNode(payload)
    ElMessage.success('编辑PDU成功')
    editDialogVisible.value = false
    notifyPduTopologyChanged('pdu', 'update')
    await loadData()
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : '编辑失败'
    ElMessage.error(message)
  } finally {
    saving.value = false
  }
}

async function confirmDelete(row: PDUItem) {
  if (!row.topology_id) {
    ElMessage.warning('未找到拓扑节点，无法删除')
    return
  }

  const message = [
    `确定删除PDU「${row.device_name}」吗？`,
    '',
    '此操作将同时影响以下数据：',
    '1) 配电拓扑页中的该PDU节点',
    '2) 机柜PDU监控页中的该PDU记录',
    '3) 该PDU相关联的下级点位（如存在）'
  ].join('<br/>')

  try {
    await ElMessageBox.confirm(message, '删除确认', {
      type: 'warning',
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      dangerouslyUseHTMLString: true
    })

    saving.value = true
    await deleteTopologyNode({
      node_id: row.topology_id,
      node_type: 'device',
      cascade: true
    })

    ElMessage.success('删除PDU成功')
    notifyPduTopologyChanged('pdu', 'delete')
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

onMounted(() => {
  loadData()
  unsubscribeSync = subscribePduTopologyChanged(() => {
    loadData()
  })
})

onUnmounted(() => {
  unsubscribeSync?.()
})
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.pdu-monitor {
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

  .title-group {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .sub-title {
    font-size: 12px;
    color: var(--text-secondary);
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .filters {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
  }

  .table-pagination {
    margin-top: 14px;
    justify-content: flex-end;
  }

  .temp-warn {
    color: var(--error-color, #f5222d);
    font-weight: 600;
  }

  .section-title {
    margin: 0 0 12px;
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
  }
}
</style>
