<template>
  <div class="spatial-page">
    <!-- 顶部工具栏 -->
    <div class="spatial-toolbar">
      <div class="toolbar-left">
        <el-upload
          ref="uploadRef"
          :auto-upload="false"
          :show-file-list="false"
          accept=".xlsx,.xls"
          :on-change="handleFileChange"
        >
          <el-button type="primary" :icon="Upload">导入 Excel</el-button>
        </el-upload>
        <el-button :icon="Download" @click="handleExport">导出 Excel</el-button>
      </div>
      <div class="toolbar-right">
        <el-select
          v-model="selectedTemplateId"
          placeholder="选择布局模板"
          clearable
          style="width: 200px"
        >
          <el-option
            v-for="t in templates"
            :key="t.id"
            :label="t.template_name"
            :value="t.id"
          />
        </el-select>
        <el-button
          type="success"
          :disabled="!selectedTemplateId || !selectedRoom"
          @click="handleApplyTemplate"
        >
          应用模板
        </el-button>
      </div>
    </div>

    <!-- 主体区域 -->
    <div class="spatial-body">
      <!-- 左侧树面板 -->
      <div class="spatial-tree-panel">
        <div class="tree-header">
          <span class="tree-title">空间层级</span>
          <el-button type="primary" size="small" text :icon="Plus" @click="openSiteDialog()">
            添加站点
          </el-button>
        </div>
        <el-scrollbar class="tree-scrollbar">
          <el-tree
            ref="treeRef"
            :data="treeData"
            :props="treeProps"
            node-key="nodeKey"
            highlight-current
            default-expand-all
            :expand-on-click-node="false"
            @node-click="handleNodeClick"
          >
            <template #default="{ data }">
              <div class="tree-node">
                <span class="tree-node-label">{{ data.label }}</span>
                <span class="tree-node-actions" @click.stop>
                  <el-button size="small" text :icon="Edit" @click="handleEditNode(data)" />
                  <el-button size="small" text :icon="Delete" @click="handleDeleteNode(data)" />
                  <el-button
                    v-if="data.nodeType !== 'row'"
                    size="small"
                    text
                    :icon="Plus"
                    @click="handleAddChild(data)"
                  />
                </span>
              </div>
            </template>
          </el-tree>
        </el-scrollbar>
      </div>

      <!-- 右侧网格面板 -->
      <div class="spatial-grid-panel">
        <template v-if="selectedRoom">
          <div class="grid-header">
            <span>{{ selectedRoom.room_name }} - 网格布局 ({{ selectedRoom.grid_cols }}×{{ selectedRoom.grid_rows }})</span>
          </div>
          <el-scrollbar class="grid-scrollbar">
            <div
              class="room-grid"
              :style="{
                gridTemplateColumns: `repeat(${selectedRoom.grid_cols}, 60px)`,
                gridTemplateRows: `repeat(${selectedRoom.grid_rows}, 60px)`
              }"
            >
              <div
                v-for="cell in gridCells"
                :key="`${cell.x}-${cell.y}`"
                class="grid-cell"
                :class="[
                  cell.cabinet ? `aisle-${cell.cabinet.aisle_type || 'none'}` : '',
                  { 'drag-over': dragOverCell?.x === cell.x && dragOverCell?.y === cell.y }
                ]"
                @dragover.prevent="handleDragOver(cell)"
                @dragleave="handleDragLeave"
                @drop="handleDrop(cell)"
              >
                <div
                  v-if="cell.cabinet"
                  class="cabinet-chip"
                  draggable="true"
                  @dragstart="handleDragStart(cell.cabinet)"
                >
                  {{ cell.cabinet.cabinet_code }}
                </div>
              </div>
            </div>
          </el-scrollbar>
          <!-- 未放置的机柜列表 -->
          <div v-if="unplacedCabinets.length" class="unplaced-list">
            <div class="unplaced-title">未放置的机柜</div>
            <div class="unplaced-items">
              <div
                v-for="cab in unplacedCabinets"
                :key="cab.id"
                class="unplaced-chip"
                draggable="true"
                @dragstart="handleDragStart(cab)"
              >
                {{ cab.cabinet_code }}
              </div>
            </div>
          </div>
        </template>
        <div v-else class="grid-placeholder">
          <el-empty description="请在左侧选择一个房间查看布局" />
        </div>
      </div>
    </div>

    <!-- 站点对话框 -->
    <el-dialog append-to-body v-model="siteDialogVisible" :title="isEdit ? '编辑站点' : '添加站点'" width="480px" @close="resetForm">
      <el-form ref="siteFormRef" :model="siteForm" :rules="siteRules" label-width="80px">
        <el-form-item label="站点编码" prop="site_code">
          <el-input v-model="siteForm.site_code" placeholder="请输入站点编码" />
        </el-form-item>
        <el-form-item label="站点名称" prop="site_name">
          <el-input v-model="siteForm.site_name" placeholder="请输入站点名称" />
        </el-form-item>
        <el-form-item label="地址" prop="address">
          <el-input v-model="siteForm.address" placeholder="请输入地址" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="siteForm.description" type="textarea" :rows="3" placeholder="请输入描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="siteDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitSite">确定</el-button>
      </template>
    </el-dialog>

    <!-- 楼层对话框 -->
    <el-dialog append-to-body v-model="floorDialogVisible" :title="isEdit ? '编辑楼层' : '添加楼层'" width="480px" @close="resetForm">
      <el-form ref="floorFormRef" :model="floorForm" :rules="floorRules" label-width="80px">
        <el-form-item label="楼层编码" prop="floor_code">
          <el-input v-model="floorForm.floor_code" placeholder="请输入楼层编码" />
        </el-form-item>
        <el-form-item label="楼层名称" prop="floor_name">
          <el-input v-model="floorForm.floor_name" placeholder="请输入楼层名称" />
        </el-form-item>
        <el-form-item label="排序" prop="sort_order">
          <el-input-number v-model="floorForm.sort_order" :min="0" :max="999" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="floorDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitFloor">确定</el-button>
      </template>
    </el-dialog>

    <!-- 房间对话框 -->
    <el-dialog append-to-body v-model="roomDialogVisible" :title="isEdit ? '编辑房间' : '添加房间'" width="520px" @close="resetForm">
      <el-form ref="roomFormRef" :model="roomForm" :rules="roomRules" label-width="100px">
        <el-form-item label="房间编码" prop="room_code">
          <el-input v-model="roomForm.room_code" placeholder="请输入房间编码" />
        </el-form-item>
        <el-form-item label="房间名称" prop="room_name">
          <el-input v-model="roomForm.room_name" placeholder="请输入房间名称" />
        </el-form-item>
        <el-form-item label="网格列数" prop="grid_cols">
          <el-input-number v-model="roomForm.grid_cols" :min="1" :max="50" />
        </el-form-item>
        <el-form-item label="网格行数" prop="grid_rows">
          <el-input-number v-model="roomForm.grid_rows" :min="1" :max="50" />
        </el-form-item>
        <el-form-item label="面积(㎡)" prop="area_sqm">
          <el-input-number v-model="roomForm.area_sqm" :min="0" :precision="2" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="roomForm.description" type="textarea" :rows="3" placeholder="请输入描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="roomDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitRoom">确定</el-button>
      </template>
    </el-dialog>

    <!-- 列对话框 -->
    <el-dialog append-to-body v-model="rowDialogVisible" :title="isEdit ? '编辑列' : '添加列'" width="480px" @close="resetForm">
      <el-form ref="rowFormRef" :model="rowForm" :rules="rowRules" label-width="80px">
        <el-form-item label="列编码" prop="row_code">
          <el-input v-model="rowForm.row_code" placeholder="请输入列编码" />
        </el-form-item>
        <el-form-item label="列名称" prop="row_name">
          <el-input v-model="rowForm.row_name" placeholder="请输入列名称" />
        </el-form-item>
        <el-form-item label="通道类型" prop="aisle_type">
          <el-select v-model="rowForm.aisle_type" placeholder="请选择通道类型">
            <el-option label="冷通道" value="cold" />
            <el-option label="热通道" value="hot" />
            <el-option label="无" value="none" />
          </el-select>
        </el-form-item>
        <el-form-item label="排序" prop="sort_order">
          <el-input-number v-model="rowForm.sort_order" :min="0" :max="999" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rowDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitRow">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Upload, Download, Plus, Edit, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, UploadFile } from 'element-plus'
import {
  getSpatialTree,
  createSite, updateSite, deleteSite,
  createFloor, updateFloor, deleteFloor,
  createRoom, updateRoom, deleteRoom,
  createRow, updateRow, deleteRow,
  updateCabinetPosition,
  importSpatialExcel, exportSpatialExcel,
  getTemplates, applyTemplate
} from '@/api/modules/spatial'
import type {
  SpatialTreeNode, TreeCabinet, TreeRoom, LayoutTemplate,
  SiteForm, FloorForm, RoomForm, RowForm
} from '@/api/modules/spatial'

// ==================== 树相关 ====================

interface TreeNodeData {
  nodeKey: string
  label: string
  nodeType: 'site' | 'floor' | 'room' | 'row'
  id: number
  parentId?: number
  raw: Record<string, unknown>
  children?: TreeNodeData[]
}

const treeRef = ref()
const treeData = ref<TreeNodeData[]>([])
const treeProps = { children: 'children', label: 'label' }

/** 选中的房间 */
const selectedRoom = ref<TreeRoom | null>(null)

/** 将后端树数据转换为 el-tree 格式 */
function buildTreeData(sites: SpatialTreeNode[]): TreeNodeData[] {
  return sites.map(site => ({
    nodeKey: `site-${site.id}`,
    label: `[站点] ${site.site_code} - ${site.site_name}`,
    nodeType: 'site' as const,
    id: site.id,
    raw: site as unknown as Record<string, unknown>,
    children: site.floors.map(floor => ({
      nodeKey: `floor-${floor.id}`,
      label: `[楼层] ${floor.floor_code} - ${floor.floor_name}`,
      nodeType: 'floor' as const,
      id: floor.id,
      parentId: site.id,
      raw: floor as unknown as Record<string, unknown>,
      children: floor.rooms.map(room => ({
        nodeKey: `room-${room.id}`,
        label: `[房间] ${room.room_code} - ${room.room_name}`,
        nodeType: 'room' as const,
        id: room.id,
        parentId: floor.id,
        raw: room as unknown as Record<string, unknown>,
        children: room.rows.map(row => ({
          nodeKey: `row-${row.id}`,
          label: `[列] ${row.row_code} - ${row.row_name}`,
          nodeType: 'row' as const,
          id: row.id,
          parentId: room.id,
          raw: row as unknown as Record<string, unknown>,
          children: [] as TreeNodeData[]
        }))
      }))
    }))
  }))
}

/** 原始树数据缓存，用于查找房间 */
const rawTreeData = ref<SpatialTreeNode[]>([])

/** 加载树数据 */
async function loadTree() {
  try {
    const res = await getSpatialTree()
    const sites = (res as unknown as { code: number; data: SpatialTreeNode[] }).data || []
    rawTreeData.value = sites
    treeData.value = buildTreeData(sites)
    // 如果之前选中了房间，刷新选中状态
    if (selectedRoom.value) {
      const roomId = selectedRoom.value.id
      let found: TreeRoom | null = null
      for (const site of sites) {
        for (const floor of site.floors) {
          for (const room of floor.rooms) {
            if (room.id === roomId) {
              found = room
              break
            }
          }
          if (found) break
        }
        if (found) break
      }
      selectedRoom.value = found
    }
  } catch {
    ElMessage.error('加载空间拓扑树失败')
  }
}

/** 点击树节点 */
function handleNodeClick(data: TreeNodeData) {
  if (data.nodeType === 'room') {
    // 从原始数据中找到对应房间
    for (const site of rawTreeData.value) {
      for (const floor of site.floors) {
        for (const room of floor.rooms) {
          if (room.id === data.id) {
            selectedRoom.value = room
            return
          }
        }
      }
    }
  }
}

// ==================== 网格相关 ====================

interface GridCell {
  x: number
  y: number
  cabinet: TreeCabinet | null
}

/** 网格单元格 */
const gridCells = computed<GridCell[]>(() => {
  const room = selectedRoom.value
  if (!room) return []
  const cells: GridCell[] = []
  // 收集所有机柜
  const allCabinets: TreeCabinet[] = []
  for (const row of room.rows) {
    for (const cab of row.cabinets) {
      allCabinets.push({ ...cab, aisle_type: cab.aisle_type || row.aisle_type })
    }
  }
  for (let y = 0; y < room.grid_rows; y++) {
    for (let x = 0; x < room.grid_cols; x++) {
      const cab = allCabinets.find(c => c.grid_x === x && c.grid_y === y) || null
      cells.push({ x, y, cabinet: cab })
    }
  }
  return cells
})

/** 未放置的机柜 */
const unplacedCabinets = computed<TreeCabinet[]>(() => {
  const room = selectedRoom.value
  if (!room) return []
  const list: TreeCabinet[] = []
  for (const row of room.rows) {
    for (const cab of row.cabinets) {
      if (cab.grid_x == null || cab.grid_y == null) {
        list.push({ ...cab, aisle_type: cab.aisle_type || row.aisle_type })
      }
    }
  }
  return list
})

// ==================== 拖拽相关 ====================

const dragOverCell = ref<{ x: number; y: number } | null>(null)
const draggingCabinet = ref<TreeCabinet | null>(null)

function handleDragStart(cabinet: TreeCabinet) {
  draggingCabinet.value = cabinet
}

function handleDragOver(cell: GridCell) {
  if (!cell.cabinet || cell.cabinet.id === draggingCabinet.value?.id) {
    dragOverCell.value = { x: cell.x, y: cell.y }
  }
}

function handleDragLeave() {
  dragOverCell.value = null
}

async function handleDrop(cell: GridCell) {
  dragOverCell.value = null
  const cab = draggingCabinet.value
  if (!cab) return
  if (cell.cabinet && cell.cabinet.id !== cab.id) {
    ElMessage.warning('该位置已有机柜')
    return
  }
  try {
    await updateCabinetPosition(cab.id, { grid_x: cell.x, grid_y: cell.y })
    ElMessage.success('机柜位置已更新')
    await loadTree()
  } catch {
    ElMessage.error('更新机柜位置失败')
  }
  draggingCabinet.value = null
}

// ==================== CRUD 对话框 ====================

const isEdit = ref(false)
const editingId = ref<number>(0)
const submitting = ref(false)

// 站点表单
const siteDialogVisible = ref(false)
const siteFormRef = ref<FormInstance>()
const siteForm = ref<SiteForm>({ site_code: '', site_name: '', address: '', description: '' })
const siteRules = {
  site_code: [{ required: true, message: '请输入站点编码', trigger: 'blur' }],
  site_name: [{ required: true, message: '请输入站点名称', trigger: 'blur' }]
}

// 楼层表单
const floorDialogVisible = ref(false)
const floorFormRef = ref<FormInstance>()
const floorForm = ref<FloorForm>({ floor_code: '', floor_name: '', site_id: 0, sort_order: 0 })
const floorRules = {
  floor_code: [{ required: true, message: '请输入楼层编码', trigger: 'blur' }],
  floor_name: [{ required: true, message: '请输入楼层名称', trigger: 'blur' }]
}

// 房间表单
const roomDialogVisible = ref(false)
const roomFormRef = ref<FormInstance>()
const roomForm = ref<RoomForm>({ room_code: '', room_name: '', floor_id: 0, grid_cols: 10, grid_rows: 10, area_sqm: undefined, description: '' })
const roomRules = {
  room_code: [{ required: true, message: '请输入房间编码', trigger: 'blur' }],
  room_name: [{ required: true, message: '请输入房间名称', trigger: 'blur' }],
  grid_cols: [{ required: true, message: '请输入网格列数', trigger: 'blur' }],
  grid_rows: [{ required: true, message: '请输入网格行数', trigger: 'blur' }]
}

// 列表单
const rowDialogVisible = ref(false)
const rowFormRef = ref<FormInstance>()
const rowForm = ref<RowForm>({ row_code: '', row_name: '', room_id: 0, aisle_type: 'none', sort_order: 0 })
const rowRules = {
  row_code: [{ required: true, message: '请输入列编码', trigger: 'blur' }],
  row_name: [{ required: true, message: '请输入列名称', trigger: 'blur' }]
}

function resetForm() {
  isEdit.value = false
  editingId.value = 0
}

/** 打开站点对话框 */
function openSiteDialog(site?: Record<string, unknown>) {
  if (site) {
    isEdit.value = true
    editingId.value = site.id as number
    siteForm.value = {
      site_code: site.site_code as string,
      site_name: site.site_name as string,
      address: (site.address as string) || '',
      description: (site.description as string) || ''
    }
  } else {
    isEdit.value = false
    siteForm.value = { site_code: '', site_name: '', address: '', description: '' }
  }
  siteDialogVisible.value = true
}

async function submitSite() {
  const valid = await siteFormRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (isEdit.value) {
      await updateSite(editingId.value, siteForm.value)
      ElMessage.success('站点已更新')
    } else {
      await createSite(siteForm.value)
      ElMessage.success('站点已创建')
    }
    siteDialogVisible.value = false
    await loadTree()
  } catch {
    ElMessage.error(isEdit.value ? '更新站点失败' : '创建站点失败')
  } finally {
    submitting.value = false
  }
}

async function submitFloor() {
  const valid = await floorFormRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (isEdit.value) {
      await updateFloor(editingId.value, floorForm.value)
      ElMessage.success('楼层已更新')
    } else {
      await createFloor(floorForm.value)
      ElMessage.success('楼层已创建')
    }
    floorDialogVisible.value = false
    await loadTree()
  } catch {
    ElMessage.error(isEdit.value ? '更新楼层失败' : '创建楼层失败')
  } finally {
    submitting.value = false
  }
}

async function submitRoom() {
  const valid = await roomFormRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (isEdit.value) {
      await updateRoom(editingId.value, roomForm.value)
      ElMessage.success('房间已更新')
    } else {
      await createRoom(roomForm.value)
      ElMessage.success('房间已创建')
    }
    roomDialogVisible.value = false
    await loadTree()
  } catch {
    ElMessage.error(isEdit.value ? '更新房间失败' : '创建房间失败')
  } finally {
    submitting.value = false
  }
}

async function submitRow() {
  const valid = await rowFormRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (isEdit.value) {
      await updateRow(editingId.value, rowForm.value)
      ElMessage.success('列已更新')
    } else {
      await createRow(rowForm.value)
      ElMessage.success('列已创建')
    }
    rowDialogVisible.value = false
    await loadTree()
  } catch {
    ElMessage.error(isEdit.value ? '更新列失败' : '创建列失败')
  } finally {
    submitting.value = false
  }
}

/** 编辑节点 */
function handleEditNode(data: TreeNodeData) {
  const raw = data.raw
  if (data.nodeType === 'site') {
    openSiteDialog(raw)
  } else if (data.nodeType === 'floor') {
    isEdit.value = true
    editingId.value = data.id
    floorForm.value = {
      floor_code: raw.floor_code as string,
      floor_name: raw.floor_name as string,
      site_id: data.parentId || 0,
      sort_order: (raw.sort_order as number) || 0
    }
    floorDialogVisible.value = true
  } else if (data.nodeType === 'room') {
    isEdit.value = true
    editingId.value = data.id
    roomForm.value = {
      room_code: raw.room_code as string,
      room_name: raw.room_name as string,
      floor_id: data.parentId || 0,
      grid_cols: (raw.grid_cols as number) || 10,
      grid_rows: (raw.grid_rows as number) || 10,
      area_sqm: raw.area_sqm as number | undefined,
      description: (raw.description as string) || ''
    }
    roomDialogVisible.value = true
  } else if (data.nodeType === 'row') {
    isEdit.value = true
    editingId.value = data.id
    rowForm.value = {
      row_code: raw.row_code as string,
      row_name: raw.row_name as string,
      room_id: data.parentId || 0,
      aisle_type: (raw.aisle_type as string) || 'none',
      sort_order: (raw.sort_order as number) || 0
    }
    rowDialogVisible.value = true
  }
}

/** 删除节点 */
async function handleDeleteNode(data: TreeNodeData) {
  const typeLabels: Record<string, string> = { site: '站点', floor: '楼层', room: '房间', row: '列' }
  const label = typeLabels[data.nodeType] || '节点'
  try {
    await ElMessageBox.confirm(`确定删除该${label}吗？`, '确认删除', { type: 'warning' })
  } catch {
    return
  }
  try {
    if (data.nodeType === 'site') await deleteSite(data.id)
    else if (data.nodeType === 'floor') await deleteFloor(data.id)
    else if (data.nodeType === 'room') await deleteRoom(data.id)
    else if (data.nodeType === 'row') await deleteRow(data.id)
    ElMessage.success(`${label}已删除`)
    if (data.nodeType === 'room' && selectedRoom.value?.id === data.id) {
      selectedRoom.value = null
    }
    await loadTree()
  } catch {
    ElMessage.error(`删除${label}失败`)
  }
}

/** 添加子节点 */
function handleAddChild(data: TreeNodeData) {
  isEdit.value = false
  if (data.nodeType === 'site') {
    floorForm.value = { floor_code: '', floor_name: '', site_id: data.id, sort_order: 0 }
    floorDialogVisible.value = true
  } else if (data.nodeType === 'floor') {
    roomForm.value = { room_code: '', room_name: '', floor_id: data.id, grid_cols: 10, grid_rows: 10, area_sqm: undefined, description: '' }
    roomDialogVisible.value = true
  } else if (data.nodeType === 'room') {
    rowForm.value = { row_code: '', row_name: '', room_id: data.id, aisle_type: 'none', sort_order: 0 }
    rowDialogVisible.value = true
  }
}

// ==================== 导入导出 ====================

async function handleFileChange(uploadFile: UploadFile) {
  if (!uploadFile.raw) return
  try {
    const res = await importSpatialExcel(uploadFile.raw)
    const result = (res as unknown as { code: number; data: { total: number; success: number; failed: number; skipped: number; errors: string[] } }).data
    if (result) {
      ElMessage.success(`导入完成：成功 ${result.success}，失败 ${result.failed}，跳过 ${result.skipped}`)
      if (result.errors.length) {
        console.warn('导入错误:', result.errors)
      }
    }
    await loadTree()
  } catch {
    ElMessage.error('导入失败')
  }
}

async function handleExport() {
  try {
    const res = await exportSpatialExcel()
    const blob = res instanceof Blob ? res : new Blob([res as unknown as BlobPart], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'spatial_topology.xlsx'
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    ElMessage.error('导出失败')
  }
}

// ==================== 模板 ====================

const templates = ref<LayoutTemplate[]>([])
const selectedTemplateId = ref<number | null>(null)

async function loadTemplates() {
  try {
    const res = await getTemplates()
    templates.value = (res as unknown as { code: number; data: LayoutTemplate[] }).data || []
  } catch {
    // 模板加载失败不阻塞页面
  }
}

async function handleApplyTemplate() {
  if (!selectedTemplateId.value || !selectedRoom.value) {
    ElMessage.warning('请先选择模板和房间')
    return
  }
  try {
    await ElMessageBox.confirm('应用模板将在当前房间创建列和机柜，确定继续？', '确认应用', { type: 'warning' })
  } catch {
    return
  }
  try {
    const res = await applyTemplate(selectedTemplateId.value, { room_id: selectedRoom.value.id })
    const result = (res as unknown as { code: number; data: { created_rows: number; created_cabinets: number; errors: string[] } }).data
    if (result) {
      ElMessage.success(`模板已应用：创建 ${result.created_rows} 列，${result.created_cabinets} 个机柜`)
    }
    await loadTree()
  } catch {
    ElMessage.error('应用模板失败')
  }
}

// ==================== 初始化 ====================

onMounted(() => {
  loadTree()
  loadTemplates()
})
</script>

<style scoped>
.spatial-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 800px;
  padding: 16px;
  gap: 16px;
  background: #f5f7fa;
}

.spatial-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.spatial-body {
  display: flex;
  flex: 1;
  gap: 16px;
  min-height: 0;
}

.spatial-tree-panel {
  width: 320px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

.tree-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #ebeef5;
}

.tree-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.tree-scrollbar {
  flex: 1;
}

.tree-node {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding-right: 4px;
}

.tree-node-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.tree-node-actions {
  display: none;
  flex-shrink: 0;
}

.tree-node:hover .tree-node-actions {
  display: flex;
}

.spatial-grid-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

.grid-header {
  padding: 12px 16px;
  border-bottom: 1px solid #ebeef5;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.grid-scrollbar {
  flex: 1;
  padding: 16px;
}

.grid-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.room-grid {
  display: grid;
  gap: 2px;
  width: fit-content;
}

.grid-cell {
  width: 60px;
  height: 60px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fafafa;
  transition: border-color 0.2s, background-color 0.2s;
}

.grid-cell.aisle-cold {
  background: #e6f7ff;
}

.grid-cell.aisle-hot {
  background: #fff1f0;
}

.grid-cell.aisle-none {
  background: #f5f5f5;
}

.grid-cell.drag-over {
  border-color: #409eff;
  border-width: 2px;
  background: rgba(64, 158, 255, 0.08);
}

.cabinet-chip {
  font-size: 11px;
  font-weight: 500;
  color: #303133;
  cursor: grab;
  text-align: center;
  word-break: break-all;
  line-height: 1.2;
  padding: 2px;
  user-select: none;
}

.cabinet-chip:active {
  cursor: grabbing;
}

.unplaced-list {
  padding: 12px 16px;
  border-top: 1px solid #ebeef5;
}

.unplaced-title {
  font-size: 13px;
  font-weight: 600;
  color: #606266;
  margin-bottom: 8px;
}

.unplaced-items {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.unplaced-chip {
  padding: 4px 10px;
  background: #f0f2f5;
  border: 1px dashed #c0c4cc;
  border-radius: 4px;
  font-size: 12px;
  color: #606266;
  cursor: grab;
  user-select: none;
}

.unplaced-chip:active {
  cursor: grabbing;
}
</style>
