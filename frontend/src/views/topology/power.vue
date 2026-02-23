<template>
  <div class="power-topology-page">
    <el-row :gutter="16" class="power-topology-body">
      <!-- 左侧: PDU 设备列表 -->
      <el-col :span="8">
        <div class="panel">
          <div class="panel-header">
            <span class="panel-title">PDU 设备列表</span>
          </div>
          <el-scrollbar class="panel-body">
            <el-table
              :data="pduList"
              highlight-current-row
              :current-row-key="selectedPdu?.id"
              row-key="id"
              size="small"
              @current-change="handlePduSelect"
            >
              <el-table-column prop="device_code" label="设备编码" min-width="120" show-overflow-tooltip />
              <el-table-column prop="device_name" label="设备名称" min-width="140" show-overflow-tooltip />
            </el-table>
          </el-scrollbar>
        </div>
      </el-col>

      <!-- 右侧: 三相接线配置 -->
      <el-col :span="16">
        <div class="panel">
          <div class="panel-header">
            <span class="panel-title">三相接线配置{{ selectedPdu ? ` - ${selectedPdu.device_name}` : '' }}</span>
            <el-button
              type="primary"
              size="small"
              :icon="Plus"
              :disabled="!selectedPdu"
              @click="openMappingDialog()"
            >
              添加接线
            </el-button>
          </div>

          <template v-if="selectedPdu">
            <!-- 接线表格 -->
            <el-table :data="phaseMappings" size="small" class="mapping-table">
              <el-table-column prop="cabinet_code" label="机柜编码" min-width="100" show-overflow-tooltip />
              <el-table-column prop="cabinet_name" label="机柜名称" min-width="120" show-overflow-tooltip />
              <el-table-column prop="phase" label="相位" width="80" align="center">
                <template #default="{ row }">
                  <el-tag :type="phaseTagType(row.phase)" size="small">{{ row.phase }}相</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="feed_type" label="供电路径" width="100" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.feed_type === 'primary' ? 'success' : 'warning'" size="small">
                    {{ row.feed_type === 'primary' ? '主路' : '备路' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="rated_current" label="额定电流(A)" width="110" align="center">
                <template #default="{ row }">
                  {{ row.rated_current ?? '-' }}
                </template>
              </el-table-column>
              <el-table-column label="操作" width="140" align="center" fixed="right">
                <template #default="{ row }">
                  <el-button type="primary" text size="small" :icon="Edit" @click="openMappingDialog(row)">
                    编辑
                  </el-button>
                  <el-button type="danger" text size="small" :icon="Delete" @click="handleDeleteMapping(row.id)">
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>

            <!-- 三相不平衡度仪表盘 -->
            <div class="balance-section">
              <div class="balance-header">三相不平衡度</div>
              <div class="balance-content">
                <div ref="gaugeChartRef" class="gauge-chart" />
                <div class="balance-info">
                  <div class="imbalance-rate">
                    <span class="imbalance-label">不平衡度</span>
                    <span class="imbalance-value" :class="imbalanceClass">
                      {{ balanceData ? `${(balanceData.imbalance_rate ?? 0).toFixed(1)}%` : '-' }}
                    </span>
                  </div>
                  <div class="data-source">
                    数据来源: {{ balanceData?.data_source ?? '-' }}
                  </div>
                  <div class="phase-cabinets">
                    <div v-for="p in phaseLabels" :key="p.key" class="phase-cabinet-item">
                      <el-tag :type="p.type" size="small">{{ p.label }}</el-tag>
                      <span class="cabinet-list">{{ (balanceData?.[p.key] as string[] ?? []).join(', ') || '无' }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>
          <div v-else class="panel-placeholder">
            <el-empty description="请在左侧选择一个 PDU 设备" />
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 添加/编辑接线对话框 -->
    <el-dialog
      v-model="mappingDialogVisible"
      :title="isEditMapping ? '编辑接线' : '添加接线'"
      width="520px"
      destroy-on-close
    >
      <el-form ref="mappingFormRef" :model="mappingForm" :rules="mappingRules" label-width="100px">
        <el-form-item label="机柜" prop="cabinet_id">
          <el-select v-model="mappingForm.cabinet_id" placeholder="请选择机柜" filterable style="width: 100%">
            <el-option
              v-for="cab in cabinetOptions"
              :key="cab.id"
              :label="`${cab.cabinet_code} - ${cab.cabinet_name}`"
              :value="cab.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="相位" prop="phase">
          <el-radio-group v-model="mappingForm.phase">
            <el-radio value="A">A 相</el-radio>
            <el-radio value="B">B 相</el-radio>
            <el-radio value="C">C 相</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="供电路径" prop="feed_type">
          <el-radio-group v-model="mappingForm.feed_type">
            <el-radio value="primary">主路</el-radio>
            <el-radio value="backup">备路</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="额定电流(A)" prop="rated_current">
          <el-input-number v-model="mappingForm.rated_current" :min="0" :max="1000" :precision="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="mappingForm.description" type="textarea" :rows="2" placeholder="请输入描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="mappingDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitMapping">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Plus, Edit, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance } from 'element-plus'
import * as echarts from 'echarts'
import { getPDUList } from '@/api/modules/power'
import { getCabinets } from '@/api/modules/asset'
import {
  getPowerPhaseMappings,
  createPowerPhaseMapping,
  updatePowerPhaseMapping,
  deletePowerPhaseMapping,
  getPduPhaseBalance
} from '@/api/modules/topologyConfig'
import type {
  PowerPhaseMappingResponse,
  PowerPhaseMappingCreate,
  PhaseBalanceResponse
} from '@/api/modules/topologyConfig'

// ==================== PDU 列表 ====================

interface PduItem {
  id: number
  device_code: string
  device_name: string
}

const pduList = ref<PduItem[]>([])
const selectedPdu = ref<PduItem | null>(null)

async function loadPduList() {
  try {
    const res = await getPDUList({ page: 1, page_size: 500 })
    const data = (res as unknown as { items?: PduItem[]; data?: PduItem[] })
    pduList.value = data.items || data.data || (Array.isArray(res) ? res as PduItem[] : [])
  } catch {
    ElMessage.error('加载 PDU 列表失败')
  }
}

function handlePduSelect(row: PduItem | null) {
  selectedPdu.value = row
  if (row) {
    loadPhaseMappings(row.id)
    loadPhaseBalance(row.id)
  } else {
    phaseMappings.value = []
    balanceData.value = null
  }
}

// ==================== 相位映射 ====================

const phaseMappings = ref<PowerPhaseMappingResponse[]>([])

async function loadPhaseMappings(pduDeviceId: number) {
  try {
    const res = await getPowerPhaseMappings(pduDeviceId)
    const data = (res as unknown as { data?: PowerPhaseMappingResponse[] })
    phaseMappings.value = data.data || (Array.isArray(res) ? res as PowerPhaseMappingResponse[] : [])
  } catch {
    phaseMappings.value = []
  }
}

function phaseTagType(phase: string): 'info' | 'success' | 'warning' {
  if (phase === 'A') return 'info'
  if (phase === 'B') return 'success'
  return 'warning'
}

// ==================== 三相不平衡度 ====================

const balanceData = ref<PhaseBalanceResponse | null>(null)
const gaugeChartRef = ref<HTMLElement>()
let gaugeChart: echarts.ECharts | null = null

const phaseLabels = [
  { key: 'phase_a_cabinets' as const, label: 'A 相', type: 'info' as const },
  { key: 'phase_b_cabinets' as const, label: 'B 相', type: 'success' as const },
  { key: 'phase_c_cabinets' as const, label: 'C 相', type: 'warning' as const }
]

const imbalanceClass = computed(() => {
  const rate = balanceData.value?.imbalance_rate ?? 0
  if (rate > 30) return 'danger'
  if (rate > 15) return 'warning'
  return 'normal'
})

async function loadPhaseBalance(pduDeviceId: number) {
  try {
    const res = await getPduPhaseBalance(pduDeviceId)
    balanceData.value = res.data || (res as unknown as PhaseBalanceResponse)
    renderGaugeChart()
  } catch {
    balanceData.value = null
  }
}

function renderGaugeChart() {
  if (!gaugeChartRef.value) return
  if (!gaugeChart) {
    gaugeChart = echarts.init(gaugeChartRef.value)
    nextTick(() => bindResizeObserver())
  }
  const bd = balanceData.value
  if (!bd) {
    gaugeChart.clear()
    return
  }

  const maxPower = Math.max(bd.phase_a_power, bd.phase_b_power, bd.phase_c_power, 1)
  const gaugeMax = Math.ceil(maxPower * 1.3)

  gaugeChart.setOption({
    tooltip: { trigger: 'item' },
    series: [
      {
        type: 'gauge',
        center: ['20%', '55%'],
        radius: '70%',
        min: 0,
        max: gaugeMax,
        startAngle: 210,
        endAngle: -30,
        title: { show: true, offsetCenter: [0, '80%'], fontSize: 12, color: '#606266' },
        detail: { formatter: '{value} kW', fontSize: 13, offsetCenter: [0, '55%'], color: '#303133' },
        axisLine: { lineStyle: { width: 10, color: [[0.3, '#67c23a'], [0.7, '#e6a23c'], [1, '#f56c6c']] } },
        axisTick: { show: false },
        splitLine: { length: 8, lineStyle: { width: 1 } },
        axisLabel: { show: false },
        pointer: { width: 4 },
        data: [{ value: bd.phase_a_power, name: 'A 相' }]
      },
      {
        type: 'gauge',
        center: ['50%', '55%'],
        radius: '70%',
        min: 0,
        max: gaugeMax,
        startAngle: 210,
        endAngle: -30,
        title: { show: true, offsetCenter: [0, '80%'], fontSize: 12, color: '#606266' },
        detail: { formatter: '{value} kW', fontSize: 13, offsetCenter: [0, '55%'], color: '#303133' },
        axisLine: { lineStyle: { width: 10, color: [[0.3, '#67c23a'], [0.7, '#e6a23c'], [1, '#f56c6c']] } },
        axisTick: { show: false },
        splitLine: { length: 8, lineStyle: { width: 1 } },
        axisLabel: { show: false },
        pointer: { width: 4 },
        data: [{ value: bd.phase_b_power, name: 'B 相' }]
      },
      {
        type: 'gauge',
        center: ['80%', '55%'],
        radius: '70%',
        min: 0,
        max: gaugeMax,
        startAngle: 210,
        endAngle: -30,
        title: { show: true, offsetCenter: [0, '80%'], fontSize: 12, color: '#606266' },
        detail: { formatter: '{value} kW', fontSize: 13, offsetCenter: [0, '55%'], color: '#303133' },
        axisLine: { lineStyle: { width: 10, color: [[0.3, '#67c23a'], [0.7, '#e6a23c'], [1, '#f56c6c']] } },
        axisTick: { show: false },
        splitLine: { length: 8, lineStyle: { width: 1 } },
        axisLabel: { show: false },
        pointer: { width: 4 },
        data: [{ value: bd.phase_c_power, name: 'C 相' }]
      }
    ]
  })
}

// ==================== 机柜选项 ====================

interface CabinetOption {
  id: number
  cabinet_code: string
  cabinet_name: string
}

const cabinetOptions = ref<CabinetOption[]>([])

async function loadCabinetOptions() {
  try {
    const res = await getCabinets({ page: 1, page_size: 1000 })
    const data = (res as unknown as { data?: CabinetOption[]; items?: CabinetOption[] })
    cabinetOptions.value = data.items || data.data || (Array.isArray(res) ? res as CabinetOption[] : [])
  } catch {
    cabinetOptions.value = []
  }
}

// ==================== 接线对话框 ====================

const mappingDialogVisible = ref(false)
const isEditMapping = ref(false)
const editingMappingId = ref(0)
const submitting = ref(false)
const mappingFormRef = ref<FormInstance>()

interface MappingFormData {
  cabinet_id: number | undefined
  phase: 'A' | 'B' | 'C'
  feed_type: 'primary' | 'backup'
  rated_current: number | undefined
  description: string
}

const mappingForm = ref<MappingFormData>({
  cabinet_id: undefined,
  phase: 'A',
  feed_type: 'primary',
  rated_current: undefined,
  description: ''
})

const mappingRules = {
  cabinet_id: [{ required: true, message: '请选择机柜', trigger: 'change' }],
  phase: [{ required: true, message: '请选择相位', trigger: 'change' }],
  feed_type: [{ required: true, message: '请选择供电路径', trigger: 'change' }]
}

function openMappingDialog(row?: PowerPhaseMappingResponse) {
  if (row) {
    isEditMapping.value = true
    editingMappingId.value = row.id
    mappingForm.value = {
      cabinet_id: row.cabinet_id,
      phase: row.phase as 'A' | 'B' | 'C',
      feed_type: row.feed_type as 'primary' | 'backup',
      rated_current: row.rated_current ?? undefined,
      description: row.description ?? ''
    }
  } else {
    isEditMapping.value = false
    editingMappingId.value = 0
    mappingForm.value = {
      cabinet_id: undefined,
      phase: 'A',
      feed_type: 'primary',
      rated_current: undefined,
      description: ''
    }
  }
  mappingDialogVisible.value = true
}

function resetMappingForm() {
  isEditMapping.value = false
  editingMappingId.value = 0
}

async function submitMapping() {
  const valid = await mappingFormRef.value?.validate().catch(() => false)
  if (!valid) return
  if (!selectedPdu.value || !mappingForm.value.cabinet_id) return

  submitting.value = true
  try {
    const payload: PowerPhaseMappingCreate = {
      cabinet_id: mappingForm.value.cabinet_id,
      pdu_device_id: selectedPdu.value.id,
      phase: mappingForm.value.phase,
      feed_type: mappingForm.value.feed_type,
      rated_current: mappingForm.value.rated_current,
      description: mappingForm.value.description || undefined
    }

    if (isEditMapping.value) {
      await updatePowerPhaseMapping(editingMappingId.value, payload)
      ElMessage.success('接线已更新')
    } else {
      await createPowerPhaseMapping(payload)
      ElMessage.success('接线已添加')
    }
    mappingDialogVisible.value = false
    loadPhaseMappings(selectedPdu.value.id)
    loadPhaseBalance(selectedPdu.value.id)
  } catch {
    ElMessage.error(isEditMapping.value ? '更新接线失败' : '添加接线失败')
  } finally {
    submitting.value = false
  }
}

async function handleDeleteMapping(id: number) {
  try {
    await ElMessageBox.confirm('确定删除该接线配置吗？', '确认删除', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deletePowerPhaseMapping(id)
    ElMessage.success('接线已删除')
    if (selectedPdu.value) {
      loadPhaseMappings(selectedPdu.value.id)
      loadPhaseBalance(selectedPdu.value.id)
    }
  } catch {
    ElMessage.error('删除接线失败')
  }
}

// ==================== 生命周期 ====================

onMounted(() => {
  loadPduList()
  loadCabinetOptions()
})

onBeforeUnmount(() => {
  gaugeChart?.dispose()
  gaugeChart = null
})

// 监听容器大小变化
const resizeObserver = ref<ResizeObserver | null>(null)

function bindResizeObserver() {
  resizeObserver.value?.disconnect()
  if (gaugeChartRef.value) {
    resizeObserver.value = new ResizeObserver(() => {
      gaugeChart?.resize()
    })
    resizeObserver.value.observe(gaugeChartRef.value)
  }
}

onMounted(() => {
  nextTick(() => {
    bindResizeObserver()
  })
})

onBeforeUnmount(() => {
  resizeObserver.value?.disconnect()
})
</script>

<style scoped>
.power-topology-page {
  height: 100%;
  padding: 16px;
  background: #f5f7fa;
}

.power-topology-body {
  height: 100%;
}

.panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #ebeef5;
  flex-shrink: 0;
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.panel-body {
  flex: 1;
  min-height: 0;
}

.panel-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.mapping-table {
  flex-shrink: 0;
}

.balance-section {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border-top: 1px solid #ebeef5;
}

.balance-header {
  padding: 10px 16px;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
}

.balance-content {
  flex: 1;
  display: flex;
  min-height: 0;
  padding: 12px 16px;
  gap: 16px;
}

.gauge-chart {
  flex: 1;
  min-height: 200px;
  min-width: 300px;
}

.balance-info {
  width: 220px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.imbalance-rate {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 8px;
}

.imbalance-label {
  font-size: 12px;
  color: #909399;
}

.imbalance-value {
  font-size: 28px;
  font-weight: 700;
  margin-top: 4px;
}

.imbalance-value.normal {
  color: #67c23a;
}

.imbalance-value.warning {
  color: #e6a23c;
}

.imbalance-value.danger {
  color: #f56c6c;
}

.data-source {
  font-size: 12px;
  color: #909399;
  text-align: center;
}

.phase-cabinets {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.phase-cabinet-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #606266;
}

.cabinet-list {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
