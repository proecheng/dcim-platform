<template>
  <div class="threshold-enhanced-page">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">总规则数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value enabled">{{ stats.enabled }}</div>
          <div class="stat-label">已启用</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value disabled">{{ stats.disabled }}</div>
          <div class="stat-label">已禁用</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value types">{{ stats.deviceTypes }}</div>
          <div class="stat-label">设备类型数</div>
        </el-card>
      </el-col>
    </el-row>
    <!-- 工具栏 -->
    <el-card shadow="hover" class="toolbar-card">
      <el-form :inline="true" class="filter-form">
        <el-form-item label="设备类型">
          <el-select v-model="filters.deviceType" placeholder="全部" clearable style="width: 160px">
            <el-option v-for="dt in deviceTypeOptions" :key="dt" :label="dt" :value="dt" />
          </el-select>
        </el-form-item>
        <el-form-item label="阈值类型">
          <el-select v-model="filters.thresholdType" placeholder="全部" clearable style="width: 120px">
            <el-option label="高高" value="high_high" />
            <el-option label="高" value="high" />
            <el-option label="低" value="low" />
            <el-option label="低低" value="low_low" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用状态">
          <el-select v-model="filters.isEnabled" placeholder="全部" clearable style="width: 100px">
            <el-option label="启用" :value="true" />
            <el-option label="禁用" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
      <div class="toolbar-actions">
        <el-button type="primary" @click="handleAdd">新增阈值</el-button>
        <el-button type="success" :disabled="!selectedRows.length" @click="handleBatchEnable">
          批量启用 ({{ selectedRows.length }})
        </el-button>
        <el-button type="warning" :disabled="!selectedRows.length" @click="handleBatchDisable">
          批量禁用 ({{ selectedRows.length }})
        </el-button>
        <el-button type="info" @click="batchByTypeVisible = true">按设备类型批量配置</el-button>
      </div>
    </el-card>

    <!-- 阈值规则列表 -->
    <el-card shadow="hover" class="table-card">
      <el-table
        :data="tableData"
        stripe
        border
        v-loading="loading"
        @selection-change="handleSelectionChange"
        style="width: 100%"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column prop="point_name" label="点位名称" min-width="140" show-overflow-tooltip />
        <el-table-column prop="point_code" label="点位编码" width="130" show-overflow-tooltip />
        <el-table-column prop="device_type" label="设备类型" width="120">
          <template #default="{ row }">
            <el-tag size="small">{{ row.device_type || '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="提示阈值" width="90" align="center">
          <template #default="{ row }">
            <span class="threshold-val info">{{ formatThVal(row.info_value) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="次要阈值" width="90" align="center">
          <template #default="{ row }">
            <span class="threshold-val minor">{{ formatThVal(row.minor_value) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="重要阈值" width="90" align="center">
          <template #default="{ row }">
            <span class="threshold-val major">{{ formatThVal(row.major_value) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="紧急阈值" width="90" align="center">
          <template #default="{ row }">
            <span class="threshold-val critical">{{ formatThVal(row.critical_value) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="is_enabled" label="启用" width="80">
          <template #default="{ row }">
            <el-switch
              :model-value="row.is_enabled"
              :before-change="() => handleToggle(row)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="最后更新" width="170" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
            <el-button type="danger" link @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        class="pagination"
        @size-change="loadData"
        @current-change="loadData"
      />
    </el-card>

    <!-- 添加/编辑阈值对话框（含可视化预览） -->
    <el-dialog append-to-body
      v-model="dialogVisible"
      :title="isEdit ? '编辑阈值规则' : '新增阈值规则'"
      width="900px"
      
      @opened="initChart"
      @closed="disposeChart"
    >
      <el-row :gutter="20">
        <el-col :span="12">
          <el-form ref="formRef" :model="form" :rules="formRules" label-width="90px">
            <el-form-item label="点位" prop="point_id">
              <el-select
                v-model="form.point_id"
                placeholder="请选择点位"
                filterable
                style="width: 100%"
                :disabled="isEdit"
                @change="handlePointChange"
              >
                <el-option
                  v-for="p in pointOptions"
                  :key="p.id"
                  :label="`${p.point_name} (${p.point_code})`"
                  :value="p.id"
                />
              </el-select>
            </el-form-item>
            <el-divider content-position="left">4级阈值配置</el-divider>
            <el-form-item label="紧急(高高)">
              <el-input-number v-model="form.critical" :precision="2" style="width: 100%" @change="updateChartLines" />
            </el-form-item>
            <el-form-item label="重要(高)">
              <el-input-number v-model="form.major" :precision="2" style="width: 100%" @change="updateChartLines" />
            </el-form-item>
            <el-form-item label="次要(低)">
              <el-input-number v-model="form.minor" :precision="2" style="width: 100%" @change="updateChartLines" />
            </el-form-item>
            <el-form-item label="提示(低低)">
              <el-input-number v-model="form.info" :precision="2" style="width: 100%" @change="updateChartLines" />
            </el-form-item>
            <el-divider content-position="left">高级设置</el-divider>
            <el-form-item label="延迟秒数">
              <el-input-number v-model="form.delay_seconds" :min="0" style="width: 100%" />
            </el-form-item>
            <el-form-item label="死区">
              <el-input-number v-model="form.dead_band" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-form>
        </el-col>
        <el-col :span="12">
          <div class="chart-preview-title">趋势预览（最近24小时）</div>
          <div ref="chartRef" class="chart-container" />
          <div class="chart-legend">
            <span class="legend-item"><i class="dot info" />提示</span>
            <span class="legend-item"><i class="dot minor" />次要</span>
            <span class="legend-item"><i class="dot major" />重要</span>
            <span class="legend-item"><i class="dot critical" />紧急</span>
          </div>
        </el-col>
      </el-row>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- 按设备类型批量配置对话框 -->
    <el-dialog append-to-body v-model="batchByTypeVisible" title="按设备类型批量配置阈值" width="500px">
      <el-form :model="batchForm" label-width="100px">
        <el-form-item label="设备类型">
          <el-select v-model="batchForm.device_type" placeholder="请选择" style="width: 100%">
            <el-option v-for="dt in deviceTypeOptions" :key="dt" :label="dt" :value="dt" />
          </el-select>
        </el-form-item>
        <el-divider content-position="left">4级阈值</el-divider>
        <el-form-item label="紧急(高高)">
          <el-input-number v-model="batchForm.critical" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="重要(高)">
          <el-input-number v-model="batchForm.major" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="次要(低)">
          <el-input-number v-model="batchForm.minor" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="提示(低低)">
          <el-input-number v-model="batchForm.info" :precision="2" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchByTypeVisible = false">取消</el-button>
        <el-button type="primary" @click="submitBatchByType" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>
<script setup lang="ts">
import * as echarts from 'echarts'
import {
  getThresholdList, createThreshold, updateThreshold, deleteThreshold,
  setFourLevelThresholds, batchSetByDeviceType,
  type ThresholdInfo
} from '@/api/modules/threshold'
import { getPointList, type PointInfo } from '@/api/modules/point'
import { getPointTrend, type TrendData } from '@/api/modules/history'

// ==================== 聚合行类型 ====================
interface ThresholdRow {
  point_id: number
  point_name: string
  point_code: string
  device_type: string
  info_value: number | null
  minor_value: number | null
  major_value: number | null
  critical_value: number | null
  is_enabled: boolean
  updated_at: string
  // 原始阈值记录 ID 映射
  ids: Record<string, number>
}

// ==================== 状态 ====================
const loading = ref(false)
const submitting = ref(false)
const tableData = ref<ThresholdRow[]>([])
const selectedRows = ref<ThresholdRow[]>([])
const pointOptions = ref<PointInfo[]>([])
const rawThresholds = ref<ThresholdInfo[]>([])

const stats = reactive({ total: 0, enabled: 0, disabled: 0, deviceTypes: 0 })
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })
const filters = reactive({
  deviceType: '',
  thresholdType: '',
  isEnabled: undefined as boolean | undefined
})

// ==================== 设备类型选项 ====================
const deviceTypeOptions = computed(() => {
  const types = new Set<string>()
  pointOptions.value.forEach(p => {
    if (p.device_type) types.add(p.device_type)
  })
  return Array.from(types)
})

// ==================== 初始化 ====================
onMounted(() => {
  loadPointOptions()
  loadData()
})

async function loadPointOptions() {
  try {
    const result = await getPointList({ page_size: 100 })
    pointOptions.value = result.items || []
  } catch (e) {
    console.error('加载点位失败', e)
  }
}

// ==================== 数据加载与聚合 ====================
async function loadData() {
  loading.value = true
  try {
    const baseParams: Record<string, string | number | boolean> = {}
    if (filters.thresholdType) baseParams.threshold_type = filters.thresholdType
    if (typeof filters.isEnabled === 'boolean') baseParams.is_enabled = filters.isEnabled

    // ⚠️ 技术债务 [CR-09]: 当前方案为前端全量加载 + 内存聚合分页。
    // 当点位数 × 4 级阈值超过数千条时会产生性能瓶颈（多次 API 请求 + 大量内存占用）。
    // 后续应由后端提供按 point_id 聚合的分页 API，支持服务端筛选和排序。
    // 分页加载全部数据用于前端聚合（后端 page_size 上限 100）
    let allItems: ThresholdInfo[] = []
    let page = 1
    const pageSize = 100
    let total = 0
    do {
      const result = await getThresholdList({ ...baseParams, page, page_size: pageSize })
      allItems = allItems.concat(result.items || [])
      total = result.total || 0
      page++
    } while (allItems.length < total)

    rawThresholds.value = allItems
    aggregateAndFilter()
  } catch (e) {
    console.error('加载阈值失败', e)
    ElMessage.error('加载阈值列表失败')
  } finally {
    loading.value = false
  }
}

function aggregateAndFilter() {
  // 按 point_id 聚合
  const map = new Map<number, ThresholdRow>()
  const levelMap: Record<string, 'info_value' | 'minor_value' | 'major_value' | 'critical_value'> = {
    info: 'info_value',
    minor: 'minor_value',
    major: 'major_value',
    critical: 'critical_value'
  }
  const typeToLevel: Record<string, string> = {
    low_low: 'info',
    low: 'minor',
    high: 'major',
    high_high: 'critical'
  }

  for (const th of rawThresholds.value) {
    if (!map.has(th.point_id)) {
      const point = pointOptions.value.find(p => p.id === th.point_id)
      map.set(th.point_id, {
        point_id: th.point_id,
        point_name: th.point_name || point?.point_name || '',
        point_code: th.point_code || point?.point_code || '',
        device_type: point?.device_type || '',
        info_value: null,
        minor_value: null,
        major_value: null,
        critical_value: null,
        is_enabled: th.is_enabled,
        updated_at: th.updated_at || th.created_at || '',
        ids: {}
      })
    }
    const row = map.get(th.point_id)!
    const level = th.alarm_level || typeToLevel[th.threshold_type] || ''
    const field = levelMap[level]
    if (field) {
      row[field] = th.threshold_value
      row.ids[th.threshold_type] = th.id
    }
    // 更新时间取最新
    if (th.updated_at && th.updated_at > row.updated_at) {
      row.updated_at = th.updated_at
    }
    // 只要有一条启用就算启用
    if (th.is_enabled) row.is_enabled = true
  }

  let rows = Array.from(map.values())

  // 按设备类型筛选
  if (filters.deviceType) {
    rows = rows.filter(r => r.device_type === filters.deviceType)
  }

  // 统计
  const allRows = Array.from(map.values())
  const dtSet = new Set(allRows.map(r => r.device_type).filter(Boolean))
  stats.total = allRows.length
  stats.enabled = allRows.filter(r => r.is_enabled).length
  stats.disabled = allRows.filter(r => !r.is_enabled).length
  stats.deviceTypes = dtSet.size

  // 前端分页
  pagination.total = rows.length
  const start = (pagination.page - 1) * pagination.pageSize
  tableData.value = rows.slice(start, start + pagination.pageSize)
}

function resetFilters() {
  filters.deviceType = ''
  filters.thresholdType = ''
  filters.isEnabled = undefined
  pagination.page = 1
  loadData()
}

function handleSelectionChange(rows: ThresholdRow[]) {
  selectedRows.value = rows
}

function formatThVal(val: number | null): string {
  return val != null ? String(val) : '-'
}

// ==================== 单条启用/禁用切换 ====================
async function handleToggle(row: ThresholdRow): Promise<boolean> {
  try {
    const newEnabled = !row.is_enabled
    const ids = Object.values(row.ids)
    for (const id of ids) {
      await updateThreshold(id, { is_enabled: newEnabled })
    }
    ElMessage.success(newEnabled ? '已启用' : '已禁用')
    loadData()
    return true
  } catch (e) {
    console.error('切换状态失败', e)
    ElMessage.error('操作失败')
    return false
  }
}

// ==================== 批量启用/禁用 ====================
async function handleBatchEnable() {
  if (!selectedRows.value.length) return
  try {
    for (const row of selectedRows.value) {
      for (const id of Object.values(row.ids)) {
        await updateThreshold(id, { is_enabled: true })
      }
    }
    ElMessage.success(`已批量启用 ${selectedRows.value.length} 条规则`)
    loadData()
  } catch (e) {
    console.error('批量启用失败', e)
    ElMessage.error('批量启用失败')
  }
}

async function handleBatchDisable() {
  if (!selectedRows.value.length) return
  try {
    for (const row of selectedRows.value) {
      for (const id of Object.values(row.ids)) {
        await updateThreshold(id, { is_enabled: false })
      }
    }
    ElMessage.success(`已批量禁用 ${selectedRows.value.length} 条规则`)
    loadData()
  } catch (e) {
    console.error('批量禁用失败', e)
    ElMessage.error('批量禁用失败')
  }
}

// ==================== 删除 ====================
async function handleDelete(row: ThresholdRow) {
  try {
    await ElMessageBox.confirm(
      `确认删除点位「${row.point_name}」的所有阈值规则？`,
      '删除确认',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    )
    const ids = Object.values(row.ids)
    for (const id of ids) {
      await deleteThreshold(id)
    }
    ElMessage.success('删除成功')
    loadData()
  } catch (e) {
    if (e !== 'cancel') {
      console.error('删除失败', e)
      ElMessage.error('删除失败')
    }
  }
}

// ==================== 添加/编辑对话框 ====================
const dialogVisible = ref(false)
const isEdit = ref(false)
const editingPointId = ref<number | null>(null)
const formRef = ref()

const form = reactive({
  point_id: undefined as number | undefined,
  critical: undefined as number | undefined,
  major: undefined as number | undefined,
  minor: undefined as number | undefined,
  info: undefined as number | undefined,
  delay_seconds: 0,
  dead_band: 0
})

const formRules = {
  point_id: [{ required: true, message: '请选择点位', trigger: 'change' }]
}

function handleAdd() {
  isEdit.value = false
  editingPointId.value = null
  form.point_id = undefined
  form.critical = undefined
  form.major = undefined
  form.minor = undefined
  form.info = undefined
  form.delay_seconds = 0
  form.dead_band = 0
  trendData.value = []
  dialogVisible.value = true
}

function handleEdit(row: ThresholdRow) {
  isEdit.value = true
  editingPointId.value = row.point_id
  form.point_id = row.point_id
  form.critical = row.critical_value ?? undefined
  form.major = row.major_value ?? undefined
  form.minor = row.minor_value ?? undefined
  form.info = row.info_value ?? undefined
  form.delay_seconds = 0
  form.dead_band = 0
  dialogVisible.value = true
  // 加载趋势数据
  loadTrendData(row.point_id)
}

async function submitForm() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  if (!form.point_id) return

  submitting.value = true
  try {
    const data = {
      high_high: form.critical != null ? { value: form.critical, enabled: true } : undefined,
      high: form.major != null ? { value: form.major, enabled: true } : undefined,
      low: form.minor != null ? { value: form.minor, enabled: true } : undefined,
      low_low: form.info != null ? { value: form.info, enabled: true } : undefined,
      delay_seconds: form.delay_seconds,
      dead_band: form.dead_band
    }
    await setFourLevelThresholds(form.point_id, data)
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

// ==================== 按设备类型批量配置 ====================
const batchByTypeVisible = ref(false)
const batchForm = reactive({
  device_type: '',
  critical: undefined as number | undefined,
  major: undefined as number | undefined,
  minor: undefined as number | undefined,
  info: undefined as number | undefined
})

async function submitBatchByType() {
  if (!batchForm.device_type) {
    ElMessage.warning('请选择设备类型')
    return
  }
  submitting.value = true
  try {
    const result = await batchSetByDeviceType({
      device_type: batchForm.device_type,
      thresholds: {
        high_high: batchForm.critical != null ? { value: batchForm.critical, enabled: true } : undefined,
        high: batchForm.major != null ? { value: batchForm.major, enabled: true } : undefined,
        low: batchForm.minor != null ? { value: batchForm.minor, enabled: true } : undefined,
        low_low: batchForm.info != null ? { value: batchForm.info, enabled: true } : undefined
      }
    })
    ElMessage.success(`批量配置完成: ${result.success_count} 个点位成功`)
    batchByTypeVisible.value = false
    loadData()
  } catch (e) {
    console.error('批量配置失败', e)
    ElMessage.error('批量配置失败')
  } finally {
    submitting.value = false
  }
}

// ==================== ECharts 趋势图 ====================
const chartRef = ref<HTMLDivElement>()
const trendData = ref<TrendData[]>([])
let chartInstance: echarts.ECharts | null = null

// 阈值线颜色
const LEVEL_COLORS = {
  info: '#409EFF',
  minor: '#E6A23C',
  major: '#F56C0C',
  critical: '#F56C6C'
}

async function handlePointChange(pointId: number) {
  if (pointId) {
    await loadTrendData(pointId)
  }
}

async function loadTrendData(pointId: number) {
  try {
    const now = new Date()
    const start = new Date(now.getTime() - 24 * 60 * 60 * 1000)
    trendData.value = await getPointTrend(pointId, {
      start_time: start.toISOString(),
      end_time: now.toISOString(),
      granularity: 'minute',
      limit: 300
    })
    updateChartLines()
  } catch (e) {
    console.error('加载趋势数据失败', e)
    trendData.value = []
    updateChartLines()
  }
}

function buildMarkLines(): echarts.MarkLineComponentOption {
  const lines: Array<Record<string, unknown>> = []
  if (form.info != null) {
    lines.push({ yAxis: form.info, name: '提示', lineStyle: { color: LEVEL_COLORS.info, type: 'dashed', width: 2 }, label: { formatter: '提示: {c}', position: 'insideEndTop' } })
  }
  if (form.minor != null) {
    lines.push({ yAxis: form.minor, name: '次要', lineStyle: { color: LEVEL_COLORS.minor, type: 'dashed', width: 2 }, label: { formatter: '次要: {c}', position: 'insideEndTop' } })
  }
  if (form.major != null) {
    lines.push({ yAxis: form.major, name: '重要', lineStyle: { color: LEVEL_COLORS.major, type: 'dashed', width: 2 }, label: { formatter: '重要: {c}', position: 'insideEndTop' } })
  }
  if (form.critical != null) {
    lines.push({ yAxis: form.critical, name: '紧急', lineStyle: { color: LEVEL_COLORS.critical, type: 'dashed', width: 2 }, label: { formatter: '紧急: {c}', position: 'insideEndTop' } })
  }
  return { symbol: 'none', data: lines }
}

function initChart() {
  nextTick(() => {
    if (!chartRef.value) return
    chartInstance = echarts.init(chartRef.value)
    updateChartLines()
  })
}

function disposeChart() {
  chartInstance?.dispose()
  chartInstance = null
}

function updateChartLines() {
  if (!chartInstance) return
  const xData = trendData.value.map(d => d.time)
  const yData = trendData.value.map(d => d.value)

  chartInstance.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 20, bottom: 30 },
    xAxis: {
      type: 'category',
      data: xData,
      axisLabel: {
        formatter: (val: string) => {
          const d = new Date(val)
          return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
        }
      }
    },
    yAxis: { type: 'value' },
    series: [{
      type: 'line',
      data: yData,
      smooth: true,
      symbol: 'none',
      lineStyle: { color: '#67C23A', width: 1.5 },
      areaStyle: { color: 'rgba(103, 194, 58, 0.1)' },
      markLine: buildMarkLines()
    }]
  }, true)
}
</script>

<style lang="scss" scoped>
@use '@/styles/_mixins-25d' as d25;

.threshold-enhanced-page {
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

  .threshold-val {
    font-weight: 600;
    &.info { color: #409EFF; }
    &.minor { color: #E6A23C; }
    &.major { color: #F56C0C; }
    &.critical { color: #F56C6C; }
  }
}

.chart-preview-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--el-text-color-primary);
}

.chart-container {
  width: 100%;
  height: 320px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 4px;
}

.chart-legend {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-top: 8px;

  .legend-item {
    display: flex;
    align-items: center;
    font-size: 12px;
    color: var(--el-text-color-secondary);

    .dot {
      display: inline-block;
      width: 10px;
      height: 3px;
      margin-right: 4px;
      border-radius: 1px;
      &.info { background: #409EFF; }
      &.minor { background: #E6A23C; }
      &.major { background: #F56C0C; }
      &.critical { background: #F56C6C; }
    }
  }
}
</style>
