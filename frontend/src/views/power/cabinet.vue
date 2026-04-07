<template>
  <div class="cabinet-monitor">
    <el-card shadow="hover" class="table-card">
      <template #header>
        <div class="card-header">
          <div class="title-group">
            <span>配电柜监控</span>
            <span class="sub-title">当前 {{ cabinetList.length }} 台（与配电拓扑配电柜节点一致）</span>
          </div>
          <div class="header-actions">
            <el-button type="primary" link @click="openCreateDialog">新增配电柜</el-button>
            <el-button type="primary" link @click="loadData">
              <el-icon><Refresh /></el-icon> 刷新
            </el-button>
          </div>
        </div>
      </template>

      <el-table
        :data="cabinetList"
        stripe
        border
        v-loading="loading"
        @row-click="openDetail"
        highlight-current-row
        style="cursor: pointer;"
      >
        <el-table-column prop="device_code" label="设备编码" width="150" />
        <el-table-column prop="device_name" label="设备名称" min-width="160" />
        <el-table-column prop="floor" label="楼层" width="90" align="center" />
        <el-table-column prop="meter_name" label="所属计量点" min-width="140" />
        <el-table-column prop="area" label="区域" width="120" />
        <el-table-column prop="total_power" label="总功率(kW)" width="120" align="center">
          <template #default="{ row }">{{ row.total_power?.toFixed(1) ?? '-' }}</template>
        </el-table-column>
        <el-table-column prop="input_voltage" label="输入电压(V)" width="120" align="center">
          <template #default="{ row }">{{ row.input_voltage?.toFixed(1) ?? '-' }}</template>
        </el-table-column>
        <el-table-column prop="output_current" label="输出电流(A)" width="120" align="center">
          <template #default="{ row }">{{ row.output_current?.toFixed(1) ?? '-' }}</template>
        </el-table-column>
        <el-table-column prop="busbar_temp" label="母排温度(°C)" width="130" align="center">
          <template #default="{ row }">
            <span :class="{ 'temp-warn': (row.busbar_temp ?? 0) > 60 }">{{ row.busbar_temp?.toFixed(1) ?? '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click.stop="openEditDialog(row)">编辑</el-button>
            <el-button link type="danger" @click.stop="confirmDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && cabinetList.length === 0" description="暂无配电柜数据" />
    </el-card>

    <el-drawer v-model="drawerVisible" :title="drawerTitle" size="620px" direction="rtl">
      <div class="drawer-body" v-loading="detailLoading">
        <template v-if="activeCabinet">
          <el-descriptions :column="2" border size="small" class="detail-desc">
            <el-descriptions-item label="设备编码">{{ activeCabinet.device_code }}</el-descriptions-item>
            <el-descriptions-item label="设备名称">{{ activeCabinet.device_name }}</el-descriptions-item>
            <el-descriptions-item label="楼层">{{ activeCabinet.floor || '-' }}</el-descriptions-item>
            <el-descriptions-item label="区域">{{ activeCabinet.area || '-' }}</el-descriptions-item>
            <el-descriptions-item label="所属计量点">{{ activeCabinet.meter_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="statusTagType(activeCabinet.status)" size="small">{{ statusLabel(activeCabinet.status) }}</el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </template>

        <template v-if="!detailLoading && branches.length > 0">
          <h4 class="section-title">支路信息（{{ branches.length }} 条）</h4>
          <el-table :data="branches" stripe border size="small" max-height="520">
            <el-table-column prop="branch_name" label="支路名称" min-width="140" />
            <el-table-column prop="circuit_code" label="回路编码" min-width="120" />
            <el-table-column prop="load_type" label="负载类型" width="90" align="center" />
            <el-table-column prop="rated_current" label="额定电流(A)" width="110" align="center">
              <template #default="{ row }">{{ row.rated_current?.toFixed(1) ?? '-' }}</template>
            </el-table-column>
            <el-table-column prop="current" label="电流(A)" width="90" align="center">
              <template #default="{ row }">{{ row.current?.toFixed(1) ?? '-' }}</template>
            </el-table-column>
            <el-table-column prop="voltage" label="电压(V)" width="90" align="center">
              <template #default="{ row }">{{ row.voltage?.toFixed(1) ?? '-' }}</template>
            </el-table-column>
            <el-table-column prop="power" label="功率(kW)" width="90" align="center">
              <template #default="{ row }">{{ row.power?.toFixed(2) ?? '-' }}</template>
            </el-table-column>
            <el-table-column prop="breaker_status" label="开关状态" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="row.breaker_status === 'on' ? 'success' : 'danger'" size="small">
                  {{ row.breaker_status === 'on' ? '合闸' : '分闸' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </template>

        <el-empty
          v-else-if="!detailLoading"
          description="该配电柜暂无支路/回路数据，建议在配电拓扑中补充回路后再查看"
        />
      </div>
    </el-drawer>

    <el-dialog v-model="createDialogVisible" title="新增配电柜" width="560px">
      <el-form :model="createForm" label-width="110px">
        <el-form-item label="设备编码" required>
          <el-input v-model="createForm.panel_code" placeholder="例如 PNL-F3-101" />
        </el-form-item>
        <el-form-item label="设备名称" required>
          <el-input v-model="createForm.panel_name" placeholder="例如 F3列头柜-01" />
        </el-form-item>
        <el-form-item label="所属计量点" required>
          <el-select v-model="createForm.meter_point_id" filterable style="width: 100%;" placeholder="请选择计量点">
            <el-option v-for="meter in meterOptions" :key="meter.id" :label="meter.label" :value="meter.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitCreate">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editDialogVisible" title="编辑配电柜" width="560px">
      <el-form :model="editForm" label-width="110px">
        <el-form-item label="设备编码" required>
          <el-input v-model="editForm.panel_code" />
        </el-form-item>
        <el-form-item label="设备名称" required>
          <el-input v-model="editForm.panel_name" />
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
import { getCabinetList, getCabinetBranches } from '@/api/modules/power'
import {
  getDistributionTopology,
  createTopologyNode,
  updateTopologyNode,
  deleteTopologyNode,
  type TopologyNodeCreateRequest,
  type TopologyNodeUpdateRequest,
  type DistributionTopology
} from '@/api/modules/energy'
import { notifyPanelTopologyChanged, subscribePanelTopologyChanged } from '@/utils/pduSync'

interface BranchItem {
  branch_name: string
  circuit_code?: string
  rated_current?: number
  breaker_type?: string
  load_type?: string
  current?: number
  voltage?: number
  power?: number
  breaker_status: string
}

interface CabinetItem {
  id: number
  topology_id?: number
  device_code: string
  device_name: string
  floor: string
  meter_name: string
  area: string
  total_power?: number
  input_voltage?: number
  output_current?: number
  busbar_temp?: number
  status: string
}

interface TopologyPanelNode {
  topology_id: number
  panel_code: string
  panel_name: string
  floor: string
  meter_name: string
}

interface MeterOption {
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
const drawerTitle = ref('配电柜详情')

const cabinetList = ref<CabinetItem[]>([])
const branches = ref<BranchItem[]>([])
const activeCabinet = ref<CabinetItem | null>(null)
const topologyPanelMap = ref<Record<string, TopologyPanelNode>>({})
const meterOptions = ref<MeterOption[]>([])

const createDialogVisible = ref(false)
const editDialogVisible = ref(false)
const editingTopologyId = ref<number | null>(null)

const createForm = reactive({
  panel_code: '',
  panel_name: '',
  meter_point_id: undefined as number | undefined
})

const editForm = reactive({
  panel_code: '',
  panel_name: ''
})

function resolveFloor(source: string): string {
  const match = source.toUpperCase().match(/F\d+/)
  return match?.[0] ?? '未标注'
}

function parseTopology(topology: DistributionTopology) {
  const panelMap: Record<string, TopologyPanelNode> = {}
  const meters: MeterOption[] = []

  topology.transformers.forEach(transformer => {
    transformer.meter_points.forEach(meter => {
      const meterFloor = resolveFloor(`${transformer.transformer_code} ${meter.meter_code}`)
      meters.push({
        id: meter.meter_point_id,
        label: `${meterFloor} / ${meter.meter_name}`
      })

      meter.panels.forEach(panel => {
        const floor = resolveFloor(`${transformer.transformer_code} ${meter.meter_code} ${panel.panel_code}`)
        panelMap[panel.panel_code.toUpperCase()] = {
          topology_id: panel.panel_id,
          panel_code: panel.panel_code,
          panel_name: panel.panel_name,
          floor,
          meter_name: meter.meter_name
        }
      })
    })
  })

  topologyPanelMap.value = panelMap
  meterOptions.value = meters
}

async function loadAllCabinetPages(): Promise<PowerApiItem[]> {
  const allItems: PowerApiItem[] = []
  let requestPage = 1
  let apiTotal: number

  do {
    const res = await getCabinetList({ page: requestPage, page_size: 100 })
    const data = (res?.data ?? res) as { items?: PowerApiItem[]; total?: number }
    const items = data.items ?? []
    apiTotal = typeof data.total === 'number' ? data.total : items.length
    allItems.push(...items)
    requestPage += 1
    if (items.length === 0) break
  } while (allItems.length < apiTotal)

  return allItems
}

function mapApiToCabinet(item: PowerApiItem): CabinetItem | null {
  if (!item.device) return null
  const panelCode = String(item.device.device_code ?? '')
  if (!panelCode) return null

  const topo = topologyPanelMap.value[panelCode.toUpperCase()]
  if (!topo) return null

  const points = item.points ?? {}
  const pointValues = Object.values(points)
  const totalPower = pointValues.find(point => point.name?.includes('总功率') || point.name?.includes('有功功率'))
  const inputVoltage = pointValues.find(point => point.name?.includes('输入电压') || point.name?.includes('进线电压'))
  const outputCurrent = pointValues.find(point => point.name?.includes('输出电流') || point.name?.includes('出线电流'))
  const busTemp = pointValues.find(point => point.name?.includes('母排温度') || point.name?.includes('母线温度'))
  const statusRaw = String(item.device.status ?? 'offline')

  return {
    id: Number(item.device.id ?? 0),
    topology_id: topo.topology_id,
    device_code: panelCode,
    device_name: String(item.device.device_name ?? ''),
    floor: topo.floor,
    meter_name: topo.meter_name,
    area: String(item.device.area_code ?? ''),
    total_power: totalPower?.value,
    input_voltage: inputVoltage?.value,
    output_current: outputCurrent?.value,
    busbar_temp: busTemp?.value,
    status: statusRaw === 'online' ? 'normal' : statusRaw
  }
}

async function loadData() {
  loading.value = true
  try {
    const topologyRes = await getDistributionTopology()
    const topology = (topologyRes.data ?? topologyRes) as DistributionTopology
    parseTopology(topology)

    const rawItems = await loadAllCabinetPages()
    cabinetList.value = rawItems
      .map(mapApiToCabinet)
      .filter((item): item is CabinetItem => item !== null)
  } catch {
    cabinetList.value = []
    ElMessage.error('配电柜数据加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
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

function openCreateDialog() {
  createForm.panel_code = ''
  createForm.panel_name = ''
  createForm.meter_point_id = undefined
  createDialogVisible.value = true
}

async function submitCreate() {
  if (!createForm.panel_code.trim() || !createForm.panel_name.trim() || !createForm.meter_point_id) {
    ElMessage.warning('请完整填写配电柜信息')
    return
  }

  saving.value = true
  try {
    const payload: TopologyNodeCreateRequest = {
      node_type: 'panel',
      parent_id: createForm.meter_point_id,
      parent_type: 'meter_point',
      panel_code: createForm.panel_code.trim(),
      panel_name: createForm.panel_name.trim(),
      panel_type: 'distribution'
    }
    await createTopologyNode(payload)
    ElMessage.success('新增配电柜成功')
    createDialogVisible.value = false
    notifyPanelTopologyChanged('cabinet', 'create')
    await loadData()
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : '新增失败'
    ElMessage.error(message)
  } finally {
    saving.value = false
  }
}

function openEditDialog(row: CabinetItem) {
  if (!row.topology_id) {
    ElMessage.warning('未找到拓扑节点，无法编辑')
    return
  }
  editingTopologyId.value = row.topology_id
  editForm.panel_code = row.device_code
  editForm.panel_name = row.device_name
  editDialogVisible.value = true
}

async function submitEdit() {
  if (!editingTopologyId.value || !editForm.panel_code.trim() || !editForm.panel_name.trim()) {
    ElMessage.warning('请完整填写编辑信息')
    return
  }

  saving.value = true
  try {
    const payload: TopologyNodeUpdateRequest = {
      node_id: editingTopologyId.value,
      node_type: 'panel',
      code: editForm.panel_code.trim(),
      name: editForm.panel_name.trim()
    }
    await updateTopologyNode(payload)
    ElMessage.success('编辑配电柜成功')
    editDialogVisible.value = false
    notifyPanelTopologyChanged('cabinet', 'update')
    await loadData()
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : '编辑失败'
    ElMessage.error(message)
  } finally {
    saving.value = false
  }
}

async function confirmDelete(row: CabinetItem) {
  if (!row.topology_id) {
    ElMessage.warning('未找到拓扑节点，无法删除')
    return
  }

  const message = [
    `确定删除配电柜「${row.device_name}」吗？`,
    '',
    '此操作将同时影响以下数据：',
    '1) 配电拓扑页中的该配电柜节点',
    '2) 配电柜监控页中的该配电柜记录',
    '3) 该配电柜下级回路/设备/点位（如存在）'
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
      node_type: 'panel',
      cascade: true
    })

    ElMessage.success('删除配电柜成功')
    notifyPanelTopologyChanged('cabinet', 'delete')
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

function openDetail(row: CabinetItem) {
  activeCabinet.value = row
  drawerTitle.value = `${row.device_name} — 支路详情`
  drawerVisible.value = true
  detailLoading.value = true
  branches.value = []

  getCabinetBranches(row.id)
    .then(res => {
      const data = (res?.data ?? res) as { branches?: BranchItem[] }
      branches.value = data.branches ?? []
    })
    .catch(() => {
      branches.value = []
    })
    .finally(() => {
      detailLoading.value = false
    })
}

let unsubscribeSync: (() => void) | null = null

onMounted(() => {
  loadData()
  unsubscribeSync = subscribePanelTopologyChanged(() => {
    loadData()
  })
})

onUnmounted(() => {
  unsubscribeSync?.()
})
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.cabinet-monitor {
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

  .drawer-body {
    display: flex;
    flex-direction: column;
    gap: 14px;
    min-height: 260px;
  }

  .detail-desc {
    margin-bottom: 4px;
  }
}
</style>
