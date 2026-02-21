<template>
  <div class="shield-management-page">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">总策略数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value enabled">{{ stats.active }}</div>
          <div class="stat-label">活跃中</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value types">{{ stats.scheduled }}</div>
          <div class="stat-label">计划中</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value disabled">{{ stats.expired }}</div>
          <div class="stat-label">已过期</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 时间线视图 -->
    <el-card shadow="hover" class="timeline-card">
      <template #header>
        <div class="timeline-header">
          <span class="timeline-title">屏蔽策略时间线</span>
          <div class="timeline-legend">
            <span class="legend-item"><i class="dot global" />全局</span>
            <span class="legend-item"><i class="dot area" />区域</span>
            <span class="legend-item"><i class="dot device-type" />设备类型</span>
            <span class="legend-item"><i class="dot device" />特定设备</span>
          </div>
        </div>
      </template>
      <div ref="chartRef" class="timeline-chart" />
    </el-card>

    <!-- 工具栏 -->
    <el-card shadow="hover" class="toolbar-card">
      <el-form :inline="true" class="filter-form">
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width: 120px">
            <el-option label="活跃" value="active" />
            <el-option label="计划中" value="scheduled" />
            <el-option label="已过期" value="expired" />
          </el-select>
        </el-form-item>
        <el-form-item label="屏蔽范围">
          <el-select v-model="filters.scope" placeholder="全部" clearable style="width: 130px">
            <el-option label="全局" value="global" />
            <el-option label="区域" value="area" />
            <el-option label="设备类型" value="device_type" />
            <el-option label="特定设备" value="device" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="applyFilters">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
      <div class="toolbar-actions">
        <el-button type="primary" @click="handleAdd">新增屏蔽策略</el-button>
      </div>
    </el-card>

    <!-- 屏蔽策略列表 -->
    <el-card shadow="hover" class="table-card">
      <el-table :data="pagedTableData" stripe border v-loading="loading" style="width: 100%">
        <el-table-column prop="name" label="策略名称" min-width="160" show-overflow-tooltip />
        <el-table-column label="屏蔽范围" width="160">
          <template #default="{ row }">
            <el-tag :type="scopeTagType(row.scope)" size="small">{{ scopeLabel(row.scope) }}</el-tag>
            <span v-if="row.scope_value" class="scope-detail">{{ row.scope_value }}</span>
          </template>
        </el-table-column>
        <el-table-column label="屏蔽时段" min-width="200">
          <template #default="{ row }">
            <div class="time-range">
              <span>{{ formatTime(row.start_time) }}</span>
              <span class="time-sep">&rarr;</span>
              <span>{{ formatTime(row.end_time) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="屏蔽告警级别" width="200">
          <template #default="{ row }">
            <template v-if="row.levels && row.levels.length">
              <el-tag v-for="lv in row.levels" :key="lv" :type="levelTagType(lv)" size="small" class="level-tag">{{ levelLabel(lv) }}</el-tag>
            </template>
            <el-tag v-else size="small" type="info">全部级别</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.computed_status)" size="small" effect="dark">{{ statusLabel(row.computed_status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="creator_name" label="创建者" width="100" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.computed_status === 'active'" type="warning" link @click="handleTerminate(row)">终止</el-button>
            <el-button v-if="row.computed_status === 'scheduled'" type="primary" link @click="handleEdit(row)">编辑</el-button>
            <el-button type="danger" link @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        class="pagination"
        @size-change="applyFilters"
        @current-change="applyFilters"
      />
    </el-card>

    <!-- 添加/编辑屏蔽策略对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑屏蔽策略' : '新增屏蔽策略'" width="680px" destroy-on-close top="5vh">
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="100px">
        <el-form-item label="策略名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入策略名称" />
        </el-form-item>
        <el-form-item label="屏蔽范围" prop="scope">
          <el-radio-group v-model="form.scope" @change="handleScopeChange">
            <el-radio value="global">全局</el-radio>
            <el-radio value="area">按区域</el-radio>
            <el-radio value="device_type">按设备类型</el-radio>
            <el-radio value="device">按特定设备</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.scope === 'area'" label="选择区域" prop="scopeValue">
          <el-select v-model="form.scopeValue" placeholder="请选择区域" filterable style="width: 100%">
            <el-option v-for="a in areaOptions" :key="a" :label="a" :value="a" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.scope === 'device_type'" label="设备类型" prop="scopeValue">
          <el-select v-model="form.scopeValue" placeholder="请选择设备类型" filterable style="width: 100%">
            <el-option v-for="dt in deviceTypeOptions" :key="dt" :label="dt" :value="dt" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.scope === 'device'" label="选择设备" prop="scopeValue">
          <el-select v-model="form.scopeValue" placeholder="请选择设备" filterable style="width: 100%">
            <el-option v-for="d in deviceOptions" :key="d.id" :label="d.device_name + ' (' + d.device_code + ')'" :value="String(d.id)" />
          </el-select>
        </el-form-item>
        <el-divider content-position="left">屏蔽时段</el-divider>
        <el-form-item label="生效方式">
          <el-radio-group v-model="form.immediate">
            <el-radio :value="true">立即生效</el-radio>
            <el-radio :value="false">定时生效</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="!form.immediate" label="开始时间" prop="startTime">
          <el-date-picker v-model="form.startTime" type="datetime" placeholder="选择开始时间" style="width: 100%" />
        </el-form-item>
        <el-form-item label="结束时间" prop="endTime">
          <el-date-picker v-model="form.endTime" type="datetime" placeholder="选择结束时间" style="width: 100%" />
        </el-form-item>
        <el-divider content-position="left">屏蔽告警级别</el-divider>
        <el-form-item label="告警级别" prop="levels">
          <el-checkbox-group v-model="form.levels">
            <el-checkbox value="info" label="提示" />
            <el-checkbox value="minor" label="次要" />
            <el-checkbox value="major" label="重要" />
            <el-checkbox value="critical" label="紧急" />
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="屏蔽原因">
          <el-input v-model="form.reason" type="textarea" :rows="3" placeholder="请输入屏蔽原因（如：设备维护、系统升级等）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>
<script setup lang="ts">
import * as echarts from 'echarts'
import {
  getAlarmShields, createAlarmShield, deleteAlarmShield,
  type AlarmShieldInfo, type AlarmShieldCreateParams
} from '@/api/modules/alarm'
import { getDeviceList, type DeviceInfo } from '@/api/modules/device'
import { getPointList, type PointInfo } from '@/api/modules/point'

// ==================== 扩展行类型 ====================
type ShieldScope = 'global' | 'area' | 'device_type' | 'device'
type ShieldStatus = 'active' | 'expired' | 'scheduled'

interface ShieldRow {
  id: number
  name: string
  scope: ShieldScope
  scope_value: string
  start_time: string
  end_time: string
  levels: string[]
  reason: string
  creator_name: string
  computed_status: ShieldStatus
  raw: AlarmShieldInfo
}

interface ShieldMeta {
  name: string
  scope: ShieldScope
  scope_value: string
  levels: string[]
  reason: string
}

// ==================== 状态 ====================
const loading = ref(false)
const submitting = ref(false)
const allRows = ref<ShieldRow[]>([])
const deviceOptions = ref<DeviceInfo[]>([])
const pointOptions = ref<PointInfo[]>([])

const stats = reactive({ total: 0, active: 0, scheduled: 0, expired: 0 })
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })
const filters = reactive({ status: '' as string, scope: '' as string })

// ==================== 选项计算 ====================
const areaOptions = computed(() => {
  const areas = new Set<string>()
  pointOptions.value.forEach(p => { if (p.area_code) areas.add(p.area_code) })
  deviceOptions.value.forEach(d => { if (d.area_code) areas.add(d.area_code) })
  return Array.from(areas)
})

const deviceTypeOptions = computed(() => {
  const types = new Set<string>()
  pointOptions.value.forEach(p => { if (p.device_type) types.add(p.device_type) })
  deviceOptions.value.forEach(d => { if (d.device_type) types.add(d.device_type) })
  return Array.from(types)
})

// ==================== 筛选与分页 ====================
const filteredRows = computed(() => {
  let rows = allRows.value
  if (filters.status) rows = rows.filter(r => r.computed_status === filters.status)
  if (filters.scope) rows = rows.filter(r => r.scope === filters.scope)
  return rows
})

const pagedTableData = computed(() => {
  const start = (pagination.page - 1) * pagination.pageSize
  return filteredRows.value.slice(start, start + pagination.pageSize)
})

function applyFilters() {
  pagination.total = filteredRows.value.length
}

function resetFilters() {
  filters.status = ''
  filters.scope = ''
  pagination.page = 1
  applyFilters()
}

// ==================== 初始化 ====================
onMounted(() => {
  loadOptions()
  loadData()
})

async function loadOptions() {
  try {
    const [devResult, ptResult] = await Promise.all([
      getDeviceList({ page: 1, page_size: 100 }),
      getPointList({ page: 1, page_size: 100 })
    ])
    deviceOptions.value = devResult.items || []
    pointOptions.value = ptResult.items || []
  } catch (e) {
    console.error('加载选项失败', e)
  }
}

// ==================== 状态计算 ====================
function computeStatus(shield: AlarmShieldInfo): ShieldStatus {
  const now = new Date()
  const start = new Date(shield.start_time)
  const end = new Date(shield.end_time)
  if (now > end) return 'expired'
  if (now < start) return 'scheduled'
  return 'active'
}

function parseMeta(shield: AlarmShieldInfo): ShieldMeta {
  const defaults: ShieldMeta = {
    name: '',
    scope: 'global',
    scope_value: '',
    levels: [],
    reason: ''
  }
  if (!shield.reason) return defaults
  try {
    const parsed = JSON.parse(shield.reason) as Partial<ShieldMeta>
    return {
      name: parsed.name || '',
      scope: parsed.scope || 'global',
      scope_value: parsed.scope_value || '',
      levels: parsed.levels || [],
      reason: parsed.reason || ''
    }
  } catch {
    return { ...defaults, reason: shield.reason }
  }
}

function toShieldRow(shield: AlarmShieldInfo): ShieldRow {
  const meta = parseMeta(shield)
  return {
    id: shield.id,
    name: meta.name || (shield.point_name ? '屏蔽-' + shield.point_name : '屏蔽策略#' + shield.id),
    scope: meta.scope,
    scope_value: meta.scope_value,
    start_time: shield.start_time,
    end_time: shield.end_time,
    levels: meta.levels.length ? meta.levels : (shield.alarm_level ? [shield.alarm_level] : []),
    reason: meta.reason,
    creator_name: shield.creator_name || '-',
    computed_status: computeStatus(shield),
    raw: shield
  }
}

// ==================== 数据加载 ====================
async function loadData() {
  loading.value = true
  try {
    const result = await getAlarmShields({ page: 1, page_size: 100 })
    const items = result.items || []
    allRows.value = items.map(toShieldRow)
    updateStats()
    applyFilters()
    nextTick(() => renderTimeline())
  } catch (e) {
    console.error('加载屏蔽策略失败', e)
    ElMessage.error('加载屏蔽策略列表失败')
  } finally {
    loading.value = false
  }
}

function updateStats() {
  stats.total = allRows.value.length
  stats.active = allRows.value.filter(r => r.computed_status === 'active').length
  stats.scheduled = allRows.value.filter(r => r.computed_status === 'scheduled').length
  stats.expired = allRows.value.filter(r => r.computed_status === 'expired').length
}

// ==================== ECharts 时间线 ====================
const chartRef = ref<HTMLDivElement>()
let chartInstance: echarts.ECharts | null = null

const SCOPE_COLORS: Record<ShieldScope, string> = {
  global: '#F56C6C',
  area: '#E6A23C',
  device_type: '#409EFF',
  device: '#67C23A'
}

function renderTimeline() {
  if (!chartRef.value) return
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }

  // 只显示活跃和计划中的策略
  const visibleRows = allRows.value.filter(r => r.computed_status !== 'expired')
  if (!visibleRows.length) {
    chartInstance.setOption({
      title: { text: '暂无活跃或计划中的屏蔽策略', left: 'center', top: 'center', textStyle: { color: '#999', fontSize: 14 } },
      xAxis: { show: false },
      yAxis: { show: false },
      series: []
    }, true)
    return
  }

  const categories = visibleRows.map(r => r.name)
  const data = visibleRows.map((r, idx) => ({
    name: r.name,
    value: [idx, new Date(r.start_time).getTime(), new Date(r.end_time).getTime(), r.scope],
    itemStyle: { color: SCOPE_COLORS[r.scope] }
  }))

  chartInstance.setOption({
    tooltip: {
      formatter: (params: Record<string, unknown>) => {
        const val = (params as { value: [number, number, number, string] }).value
        const start = new Date(val[1]).toLocaleString('zh-CN')
        const end = new Date(val[2]).toLocaleString('zh-CN')
        const scope = scopeLabel(val[3] as ShieldScope)
        return `${(params as { name: string }).name}<br/>范围: ${scope}<br/>${start} ~ ${end}`
      }
    },
    grid: { left: 160, right: 40, top: 10, bottom: 30 },
    xAxis: {
      type: 'time',
      axisLabel: { formatter: '{MM}-{dd} {HH}:{mm}' }
    },
    yAxis: {
      type: 'category',
      data: categories,
      axisLabel: {
        width: 140,
        overflow: 'truncate',
        fontSize: 12
      }
    },
    series: [{
      type: 'custom',
      renderItem: (params: Record<string, unknown>, api: Record<string, (...args: unknown[]) => unknown>) => {
        const catIdx = api.value(0) as number
        const startVal = api.coord([api.value(1), catIdx])
        const endVal = api.coord([api.value(2), catIdx])
        const height = (api.size([0, 1]) as number[])[1] * 0.6
        const rect = echarts.graphic.clipRectByRect(
          { x: startVal[0], y: startVal[1] - height / 2, width: endVal[0] - startVal[0], height },
          { x: (params as { coordSys: { x: number } }).coordSys.x, y: (params as { coordSys: { y: number } }).coordSys.y, width: (params as { coordSys: { width: number } }).coordSys.width, height: (params as { coordSys: { height: number } }).coordSys.height }
        )
        if (rect) {
          return {
            type: 'rect',
            transition: ['shape'],
            shape: rect,
            style: api.style()
          }
        }
        return undefined
      },
      encode: { x: [1, 2], y: 0 },
      data
    }]
  }, true)
}

onUnmounted(() => {
  chartInstance?.dispose()
  chartInstance = null
})

// ==================== 辅助函数 ====================
function scopeLabel(scope: string): string {
  const map: Record<string, string> = { global: '全局', area: '区域', device_type: '设备类型', device: '特定设备' }
  return map[scope] || scope
}

function scopeTagType(scope: string): 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info'> = { global: 'danger', area: 'warning', device_type: 'info', device: 'success' }
  return map[scope] || 'info'
}

function levelTagType(level: string): 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info'> = { critical: 'danger', major: 'warning', minor: 'info', info: 'info' }
  return map[level] || 'info'
}

function levelLabel(level: string): string {
  const map: Record<string, string> = { critical: '紧急', major: '重要', minor: '次要', info: '提示' }
  return map[level] || level
}

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info'> = { active: 'success', scheduled: 'info', expired: 'info' }
  return map[status] || 'info'
}

function statusLabel(status: string): string {
  const map: Record<string, string> = { active: '活跃', scheduled: '计划中', expired: '已过期' }
  return map[status] || status
}

function formatTime(t: string): string {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

// ==================== 对话框 ====================
const dialogVisible = ref(false)
const isEdit = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref()

interface ShieldForm {
  name: string
  scope: ShieldScope
  scopeValue: string
  immediate: boolean
  startTime: Date | null
  endTime: Date | null
  levels: string[]
  reason: string
}

const form = reactive<ShieldForm>({
  name: '',
  scope: 'global',
  scopeValue: '',
  immediate: true,
  startTime: null,
  endTime: null,
  levels: [],
  reason: ''
})

const formRules = {
  name: [{ required: true, message: '请输入策略名称', trigger: 'blur' }],
  scope: [{ required: true, message: '请选择屏蔽范围', trigger: 'change' }],
  endTime: [{ required: true, message: '请选择结束时间', trigger: 'change' }]
}

function handleScopeChange() {
  form.scopeValue = ''
}

function handleAdd() {
  isEdit.value = false
  editingId.value = null
  form.name = ''
  form.scope = 'global'
  form.scopeValue = ''
  form.immediate = true
  form.startTime = null
  form.endTime = null
  form.levels = []
  form.reason = ''
  dialogVisible.value = true
}

function handleEdit(row: ShieldRow) {
  isEdit.value = true
  editingId.value = row.id
  form.name = row.name
  form.scope = row.scope
  form.scopeValue = row.scope_value
  form.immediate = false
  form.startTime = new Date(row.start_time)
  form.endTime = new Date(row.end_time)
  form.levels = [...row.levels]
  form.reason = row.reason
  dialogVisible.value = true
}

async function submitForm() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  if (!form.endTime) {
    ElMessage.warning('请选择结束时间')
    return
  }

  submitting.value = true
  try {
    const startTime = form.immediate ? new Date().toISOString() : (form.startTime ? form.startTime.toISOString() : new Date().toISOString())
    const endTime = form.endTime.toISOString()

    // 将扩展信息编码到 reason 字段
    const meta: ShieldMeta = {
      name: form.name,
      scope: form.scope,
      scope_value: form.scopeValue,
      levels: form.levels,
      reason: form.reason
    }

    const data: AlarmShieldCreateParams = {
      point_id: null,
      alarm_level: form.levels.length === 1 ? form.levels[0] as AlarmShieldCreateParams['alarm_level'] : null,
      start_time: startTime,
      end_time: endTime,
      reason: JSON.stringify(meta)
    }

    // 如果是编辑，先删除旧的再创建新的（API 不支持 update）
    if (isEdit.value && editingId.value) {
      await deleteAlarmShield(editingId.value)
    }

    await createAlarmShield(data)
    ElMessage.success(isEdit.value ? '更新成功' : '创建成功')
    dialogVisible.value = false
    loadData()
  } catch (e) {
    console.error('保存失败', e)
    ElMessage.error('保存失败')
  } finally {
    submitting.value = false
  }
}

// ==================== 终止 ====================
async function handleTerminate(row: ShieldRow) {
  try {
    await ElMessageBox.confirm(
      `确认提前终止屏蔽策略「${row.name}」？`,
      '终止确认',
      { type: 'warning', confirmButtonText: '确认终止', cancelButtonText: '取消' }
    )
    // 终止 = 删除旧的 + 创建一个已过期的（end_time 设为当前）
    await deleteAlarmShield(row.id)
    const meta = parseMeta(row.raw)
    await createAlarmShield({
      point_id: row.raw.point_id,
      alarm_level: row.raw.alarm_level,
      start_time: row.start_time,
      end_time: new Date().toISOString(),
      reason: JSON.stringify(meta)
    })
    ElMessage.success('已终止屏蔽策略')
    loadData()
  } catch (e) {
    if (e !== 'cancel') {
      console.error('终止失败', e)
      ElMessage.error('终止失败')
    }
  }
}

// ==================== 删除 ====================
async function handleDelete(row: ShieldRow) {
  try {
    await ElMessageBox.confirm(
      `确认删除屏蔽策略「${row.name}」？`,
      '删除确认',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    )
    await deleteAlarmShield(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (e) {
    if (e !== 'cancel') {
      console.error('删除失败', e)
      ElMessage.error('删除失败')
    }
  }
}
</script>

<style lang="scss" scoped>
@use '@/styles/_mixins-25d' as d25;

.shield-management-page {
  @include d25.page-list;
  padding: 16px;

  .stat-row {
    margin-bottom: 16px;
  }

  .stat-card {
    text-align: center;
    .stat-value {
      font-size: 28px;
      font-weight: 700;
      color: var(--el-text-color-primary);
      &.enabled { color: #67C23A; }
      &.disabled { color: #909399; }
      &.types { color: #409EFF; }
    }
    .stat-label {
      font-size: 13px;
      color: var(--el-text-color-secondary);
      margin-top: 4px;
    }
  }

  .timeline-card {
    margin-bottom: 16px;
  }

  .toolbar-card {
    margin-bottom: 16px;
    .filter-form { margin-bottom: 8px; }
    .toolbar-actions {
      display: flex;
      gap: 8px;
    }
  }

  .table-card {
    .pagination {
      margin-top: 16px;
      justify-content: flex-end;
    }
  }
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.timeline-title {
  font-size: 15px;
  font-weight: 600;
}

.timeline-legend {
  display: flex;
  gap: 16px;

  .legend-item {
    display: flex;
    align-items: center;
    font-size: 12px;
    color: var(--el-text-color-secondary);

    .dot {
      display: inline-block;
      width: 12px;
      height: 4px;
      margin-right: 4px;
      border-radius: 2px;
      &.global { background: #F56C6C; }
      &.area { background: #E6A23C; }
      &.device-type { background: #409EFF; }
      &.device { background: #67C23A; }
    }
  }
}

.timeline-chart {
  width: 100%;
  height: 220px;
}

.scope-detail {
  margin-left: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.time-range {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;

  .time-sep {
    color: var(--el-text-color-placeholder);
    margin: 0 2px;
  }
}

.level-tag {
  margin-right: 4px;
  margin-bottom: 2px;
}
</style>
