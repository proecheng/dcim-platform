<template>
  <div class="energy-config">
    <el-tabs v-model="activeTab" type="border-card">
      <!-- 变压器管理 -->
      <el-tab-pane label="变压器" name="transformer">
        <div class="tab-header">
          <el-button type="primary" @click="showTransformerDialog()">
            <el-icon><Plus /></el-icon>新增变压器
          </el-button>
        </div>
        <el-table :data="transformers" v-loading="loading.transformer" stripe>
          <el-table-column prop="transformer_code" label="编码" width="120" />
          <el-table-column prop="transformer_name" label="名称" min-width="150" />
          <el-table-column prop="rated_capacity" label="额定容量(kVA)" width="130" />
          <el-table-column prop="voltage_high" label="高压侧(kV)" width="100" />
          <el-table-column prop="voltage_low" label="低压侧(V)" width="100" />
          <el-table-column prop="location" label="位置" min-width="120" />
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="getStatusType(row.status)">{{ getStatusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="showTransformerDialog(row)">编辑</el-button>
              <el-button link type="danger" @click="handleDeleteTransformer(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 计量点管理 -->
      <el-tab-pane label="计量点" name="meter">
        <div class="tab-header">
          <el-button type="primary" @click="showMeterDialog()">
            <el-icon><Plus /></el-icon>新增计量点
          </el-button>
        </div>
        <el-table :data="meterPoints" v-loading="loading.meter" stripe>
          <el-table-column prop="meter_code" label="编码" width="120" />
          <el-table-column prop="meter_name" label="名称" min-width="150" />
          <el-table-column prop="meter_no" label="电表号" width="120" />
          <el-table-column prop="declared_demand" label="申报需量(kW)" width="120" />
          <el-table-column prop="demand_type" label="需量类型" width="100">
            <template #default="{ row }">
              {{ getDemandTypeText(row.demand_type) }}
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="getStatusType(row.status)">{{ getStatusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="showMeterDialog(row)">编辑</el-button>
              <el-button link type="danger" @click="handleDeleteMeter(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 配电柜管理 -->
      <el-tab-pane label="配电柜" name="panel">
        <div class="tab-header">
          <el-button type="primary" @click="showPanelDialog()">
            <el-icon><Plus /></el-icon>新增配电柜
          </el-button>
        </div>
        <el-table :data="panels" v-loading="loading.panel" stripe>
          <el-table-column prop="panel_code" label="编码" width="120" />
          <el-table-column prop="panel_name" label="名称" min-width="150" />
          <el-table-column prop="panel_type" label="类型" width="100">
            <template #default="{ row }">
              {{ getPanelTypeText(row.panel_type) }}
            </template>
          </el-table-column>
          <el-table-column prop="rated_current" label="额定电流(A)" width="110" />
          <el-table-column prop="rated_voltage" label="额定电压(V)" width="110" />
          <el-table-column prop="location" label="位置" min-width="120" />
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="getStatusType(row.status)">{{ getStatusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="showPanelDialog(row)">编辑</el-button>
              <el-button link type="danger" @click="handleDeletePanel(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 配电回路管理 -->
      <el-tab-pane label="配电回路" name="circuit">
        <div class="tab-header">
          <el-button type="primary" @click="showCircuitDialog()">
            <el-icon><Plus /></el-icon>新增回路
          </el-button>
        </div>
        <el-table :data="circuits" v-loading="loading.circuit" stripe>
          <el-table-column prop="circuit_code" label="编码" width="120" />
          <el-table-column prop="circuit_name" label="名称" min-width="150" />
          <el-table-column prop="load_type" label="负载类型" width="100" />
          <el-table-column prop="rated_current" label="额定电流(A)" width="110" />
          <el-table-column prop="breaker_type" label="断路器类型" width="110" />
          <el-table-column prop="is_shiftable" label="可转移" width="80">
            <template #default="{ row }">
              <el-tag :type="row.is_shiftable ? 'success' : 'info'" size="small">
                {{ row.is_shiftable ? '是' : '否' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="showCircuitDialog(row)">编辑</el-button>
              <el-button link type="danger" @click="handleDeleteCircuit(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 电价配置 -->
      <el-tab-pane label="电价配置" name="pricing">
        <div class="tab-header">
          <el-button type="primary" @click="showPricingDialog()">
            <el-icon><Plus /></el-icon>新增时段
          </el-button>
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :show-file-list="false"
            accept="image/*"
            :on-change="handleBillUpload"
            style="display: inline-block; margin-left: 12px;"
          >
            <el-button type="success">
              <el-icon><Upload /></el-icon>上传电费单识别
            </el-button>
          </el-upload>
        </div>

        <el-alert type="info" :closable="false" style="margin-bottom: 16px;">
          <template #title>电价说明</template>
          <p>电价配置用于计算用电成本。支持手动配置或上传电费单自动识别(OCR)。</p>
          <p>时段类型：<el-tag type="danger" size="small">尖峰</el-tag> <el-tag type="warning" size="small">高峰</el-tag> <el-tag size="small">平段</el-tag> <el-tag type="success" size="small">低谷</el-tag></p>
        </el-alert>

        <el-table :data="pricingList" v-loading="loading.pricing" stripe>
          <el-table-column prop="pricing_name" label="时段名称" min-width="120" />
          <el-table-column prop="period_type" label="时段类型" width="100">
            <template #default="{ row }">
              <el-tag :type="getPeriodTagType(row.period_type)" size="small">
                {{ getPeriodTypeText(row.period_type) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="start_time" label="开始时间" width="100" />
          <el-table-column prop="end_time" label="结束时间" width="100" />
          <el-table-column prop="price" label="电价(元/kWh)" width="120">
            <template #default="{ row }">
              <span class="price-value">¥{{ row.price?.toFixed(4) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="effective_date" label="生效日期" width="120" />
          <el-table-column prop="is_enabled" label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.is_enabled ? 'success' : 'info'" size="small">
                {{ row.is_enabled ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="showPricingDialog(row)">编辑</el-button>
              <el-button link type="danger" @click="handleDeletePricing(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 电价汇总卡片 -->
        <el-row :gutter="20" style="margin-top: 20px;">
          <el-col :span="6">
            <el-card shadow="hover" class="summary-card">
              <div class="summary-label">尖峰电价</div>
              <div class="summary-value danger">¥{{ getPriceByType('sharp')?.toFixed(4) || '-' }}</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover" class="summary-card">
              <div class="summary-label">高峰电价</div>
              <div class="summary-value warning">¥{{ getPriceByType('peak')?.toFixed(4) || '-' }}</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover" class="summary-card">
              <div class="summary-label">平段电价</div>
              <div class="summary-value">¥{{ getPriceByType('flat')?.toFixed(4) || '-' }}</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover" class="summary-card">
              <div class="summary-label">低谷电价</div>
              <div class="summary-value success">¥{{ getPriceByType('valley')?.toFixed(4) || '-' }}</div>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>

    <!-- 变压器对话框 -->
    <el-dialog v-model="dialogs.transformer" :title="transformerForm.id ? '编辑变压器' : '新增变压器'" width="500px">
      <el-form :model="transformerForm" label-width="100px">
        <el-form-item label="编码" required>
          <el-input v-model="transformerForm.transformer_code" :disabled="!!transformerForm.id" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="transformerForm.transformer_name" />
        </el-form-item>
        <el-form-item label="额定容量(kVA)" required>
          <el-input-number v-model="transformerForm.rated_capacity" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="高压侧(kV)">
          <el-input-number v-model="transformerForm.voltage_high" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="低压侧(V)">
          <el-input-number v-model="transformerForm.voltage_low" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="位置">
          <el-input v-model="transformerForm.location" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogs.transformer = false">取消</el-button>
        <el-button type="primary" @click="handleSaveTransformer" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 计量点对话框 -->
    <el-dialog v-model="dialogs.meter" :title="meterForm.id ? '编辑计量点' : '新增计量点'" width="500px">
      <el-form :model="meterForm" label-width="100px">
        <el-form-item label="编码" required>
          <el-input v-model="meterForm.meter_code" :disabled="!!meterForm.id" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="meterForm.meter_name" />
        </el-form-item>
        <el-form-item label="所属变压器">
          <el-select v-model="meterForm.transformer_id" clearable style="width: 100%">
            <el-option v-for="t in transformers" :key="t.id" :label="t.transformer_name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="电表号">
          <el-input v-model="meterForm.meter_no" />
        </el-form-item>
        <el-form-item label="申报需量(kW)">
          <el-input-number v-model="meterForm.declared_demand" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="需量类型">
          <el-select v-model="meterForm.demand_type" style="width: 100%">
            <el-option label="单一制" value="single" />
            <el-option label="两部制" value="multi" />
            <el-option label="峰谷制" value="peak_valley" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogs.meter = false">取消</el-button>
        <el-button type="primary" @click="handleSaveMeter" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 配电柜对话框 -->
    <el-dialog v-model="dialogs.panel" :title="panelForm.id ? '编辑配电柜' : '新增配电柜'" width="500px">
      <el-form :model="panelForm" label-width="100px">
        <el-form-item label="编码" required>
          <el-input v-model="panelForm.panel_code" :disabled="!!panelForm.id" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="panelForm.panel_name" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="panelForm.panel_type" style="width: 100%">
            <el-option label="主配电柜" value="main" />
            <el-option label="分配电柜" value="sub" />
            <el-option label="末端配电柜" value="final" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属计量点">
          <el-select v-model="panelForm.meter_point_id" clearable style="width: 100%">
            <el-option v-for="m in meterPoints" :key="m.id" :label="m.meter_name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="额定电流(A)">
          <el-input-number v-model="panelForm.rated_current" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="额定电压(V)">
          <el-input-number v-model="panelForm.rated_voltage" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="位置">
          <el-input v-model="panelForm.location" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogs.panel = false">取消</el-button>
        <el-button type="primary" @click="handleSavePanel" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 配电回路对话框 -->
    <el-dialog v-model="dialogs.circuit" :title="circuitForm.id ? '编辑回路' : '新增回路'" width="500px">
      <el-form :model="circuitForm" label-width="100px">
        <el-form-item label="编码" required>
          <el-input v-model="circuitForm.circuit_code" :disabled="!!circuitForm.id" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="circuitForm.circuit_name" />
        </el-form-item>
        <el-form-item label="所属配电柜" required>
          <el-select v-model="circuitForm.panel_id" style="width: 100%">
            <el-option v-for="p in panels" :key="p.id" :label="p.panel_name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="负载类型">
          <el-select v-model="circuitForm.load_type" clearable style="width: 100%">
            <el-option label="IT负载" value="IT" />
            <el-option label="空调" value="HVAC" />
            <el-option label="照明" value="LIGHTING" />
            <el-option label="UPS" value="UPS" />
            <el-option label="其他" value="OTHER" />
          </el-select>
        </el-form-item>
        <el-form-item label="额定电流(A)">
          <el-input-number v-model="circuitForm.rated_current" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="断路器类型">
          <el-input v-model="circuitForm.breaker_type" />
        </el-form-item>
        <el-form-item label="可转移负荷">
          <el-switch v-model="circuitForm.is_shiftable" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogs.circuit = false">取消</el-button>
        <el-button type="primary" @click="handleSaveCircuit" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 电价配置对话框 -->
    <el-dialog v-model="dialogs.pricing" :title="pricingForm.id ? '编辑电价时段' : '新增电价时段'" width="500px">
      <el-form :model="pricingForm" label-width="100px">
        <el-form-item label="时段名称" required>
          <el-input v-model="pricingForm.pricing_name" placeholder="如：尖峰时段1" />
        </el-form-item>
        <el-form-item label="时段类型" required>
          <el-select v-model="pricingForm.period_type" style="width: 100%">
            <el-option label="尖峰" value="sharp" />
            <el-option label="高峰" value="peak" />
            <el-option label="平段" value="flat" />
            <el-option label="低谷" value="valley" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始时间" required>
          <el-time-picker v-model="pricingForm.start_time" format="HH:mm" value-format="HH:mm" style="width: 100%" />
        </el-form-item>
        <el-form-item label="结束时间" required>
          <el-time-picker v-model="pricingForm.end_time" format="HH:mm" value-format="HH:mm" style="width: 100%" />
        </el-form-item>
        <el-form-item label="电价(元/kWh)" required>
          <el-input-number v-model="pricingForm.price" :min="0" :precision="4" :step="0.01" style="width: 100%" />
        </el-form-item>
        <el-form-item label="生效日期" required>
          <el-date-picker v-model="pricingForm.effective_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="启用状态">
          <el-switch v-model="pricingForm.is_enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogs.pricing = false">取消</el-button>
        <el-button type="primary" @click="handleSavePricing" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Upload } from '@element-plus/icons-vue'
import {
  getTransformers, createTransformer, updateTransformer, deleteTransformer,
  getMeterPoints, createMeterPoint, updateMeterPoint, deleteMeterPoint,
  getDistributionPanels, createDistributionPanel, updateDistributionPanel, deleteDistributionPanel,
  getDistributionCircuits, createDistributionCircuit, updateDistributionCircuit, deleteDistributionCircuit,
  getPricingList, createPricing, updatePricing, deletePricing,
  type Transformer, type MeterPoint, type DistributionPanel, type DistributionCircuit, type ElectricityPricing
} from '@/api/modules/energy'

const activeTab = ref('transformer')
const saving = ref(false)
const uploadRef = ref()

const loading = reactive({
  transformer: false,
  meter: false,
  panel: false,
  circuit: false,
  pricing: false
})

const dialogs = reactive({
  transformer: false,
  meter: false,
  panel: false,
  circuit: false,
  pricing: false
})

const transformers = ref<Transformer[]>([])
const meterPoints = ref<MeterPoint[]>([])
const panels = ref<DistributionPanel[]>([])
const circuits = ref<DistributionCircuit[]>([])
const pricingList = ref<ElectricityPricing[]>([])

const transformerForm = ref<any>({})
const meterForm = ref<any>({})
const panelForm = ref<any>({})
const circuitForm = ref<any>({})
const pricingForm = ref<any>({})

type TagType = 'success' | 'warning' | 'danger' | 'info' | 'primary'

const getStatusType = (status: string): TagType => {
  const map: Record<string, TagType> = { normal: 'success', warning: 'warning', fault: 'danger', offline: 'info' }
  return map[status] || 'info'
}

const getStatusText = (status: string) => {
  const map: Record<string, string> = { normal: '正常', warning: '告警', fault: '故障', offline: '离线' }
  return map[status] || status
}

const getDemandTypeText = (type: string) => {
  const map: Record<string, string> = { single: '单一制', multi: '两部制', peak_valley: '峰谷制' }
  return map[type] || type
}

const getPanelTypeText = (type: string) => {
  const map: Record<string, string> = { main: '主配电柜', sub: '分配电柜', final: '末端配电柜' }
  return map[type] || type
}

const getPeriodTypeText = (type: string) => {
  const map: Record<string, string> = { sharp: '尖峰', peak: '高峰', flat: '平段', valley: '低谷' }
  return map[type] || type
}

const getPeriodTagType = (type: string): TagType => {
  const map: Record<string, TagType> = { sharp: 'danger', peak: 'warning', flat: 'info', valley: 'success' }
  return map[type] || 'info'
}

const getPriceByType = (type: string) => {
  const item = pricingList.value.find(p => p.period_type === type && p.is_enabled)
  return item?.price
}

const loadTransformers = async () => {
  loading.transformer = true
  try {
    const res = await getTransformers()
    if (res.code === 0 && res.data) {
      transformers.value = res.data
    }
  } finally {
    loading.transformer = false
  }
}

const loadMeterPoints = async () => {
  loading.meter = true
  try {
    const res = await getMeterPoints()
    if (res.code === 0 && res.data) {
      meterPoints.value = res.data
    }
  } finally {
    loading.meter = false
  }
}

const loadPanels = async () => {
  loading.panel = true
  try {
    const res = await getDistributionPanels()
    if (res.code === 0 && res.data) {
      panels.value = res.data
    }
  } finally {
    loading.panel = false
  }
}

const loadCircuits = async () => {
  loading.circuit = true
  try {
    const res = await getDistributionCircuits()
    if (res.code === 0 && res.data) {
      circuits.value = res.data
    }
  } finally {
    loading.circuit = false
  }
}

const loadPricing = async () => {
  loading.pricing = true
  try {
    const res = await getPricingList()
    if (res.code === 0 && res.data) {
      pricingList.value = res.data
    }
  } finally {
    loading.pricing = false
  }
}

const showTransformerDialog = (row?: Transformer) => {
  transformerForm.value = row ? { ...row } : { voltage_high: 10, voltage_low: 400 }
  dialogs.transformer = true
}

const showMeterDialog = (row?: MeterPoint) => {
  meterForm.value = row ? { ...row } : { demand_type: 'multi' }
  dialogs.meter = true
}

const showPanelDialog = (row?: DistributionPanel) => {
  panelForm.value = row ? { ...row } : { panel_type: 'sub', rated_voltage: 380 }
  dialogs.panel = true
}

const showCircuitDialog = (row?: DistributionCircuit) => {
  circuitForm.value = row ? { ...row } : { is_shiftable: false }
  dialogs.circuit = true
}

const showPricingDialog = (row?: ElectricityPricing) => {
  if (row) {
    pricingForm.value = { ...row }
  } else {
    pricingForm.value = {
      period_type: 'flat',
      price: 0.7,
      effective_date: new Date().toISOString().split('T')[0],
      is_enabled: true
    }
  }
  dialogs.pricing = true
}

const handleSaveTransformer = async () => {
  saving.value = true
  try {
    if (transformerForm.value.id) {
      await updateTransformer(transformerForm.value.id, transformerForm.value)
    } else {
      await createTransformer(transformerForm.value)
    }
    ElMessage.success('保存成功')
    dialogs.transformer = false
    loadTransformers()
  } finally {
    saving.value = false
  }
}

const handleSaveMeter = async () => {
  saving.value = true
  try {
    if (meterForm.value.id) {
      await updateMeterPoint(meterForm.value.id, meterForm.value)
    } else {
      await createMeterPoint(meterForm.value)
    }
    ElMessage.success('保存成功')
    dialogs.meter = false
    loadMeterPoints()
  } finally {
    saving.value = false
  }
}

const handleSavePanel = async () => {
  saving.value = true
  try {
    if (panelForm.value.id) {
      await updateDistributionPanel(panelForm.value.id, panelForm.value)
    } else {
      await createDistributionPanel(panelForm.value)
    }
    ElMessage.success('保存成功')
    dialogs.panel = false
    loadPanels()
  } finally {
    saving.value = false
  }
}

const handleSaveCircuit = async () => {
  saving.value = true
  try {
    if (circuitForm.value.id) {
      await updateDistributionCircuit(circuitForm.value.id, circuitForm.value)
    } else {
      await createDistributionCircuit(circuitForm.value)
    }
    ElMessage.success('保存成功')
    dialogs.circuit = false
    loadCircuits()
  } finally {
    saving.value = false
  }
}

const handleDeleteTransformer = async (row: Transformer) => {
  await ElMessageBox.confirm('确定删除该变压器？', '提示', { type: 'warning' })
  await deleteTransformer(row.id)
  ElMessage.success('删除成功')
  loadTransformers()
}

const handleDeleteMeter = async (row: MeterPoint) => {
  await ElMessageBox.confirm('确定删除该计量点？', '提示', { type: 'warning' })
  await deleteMeterPoint(row.id)
  ElMessage.success('删除成功')
  loadMeterPoints()
}

const handleDeletePanel = async (row: DistributionPanel) => {
  await ElMessageBox.confirm('确定删除该配电柜？', '提示', { type: 'warning' })
  await deleteDistributionPanel(row.id)
  ElMessage.success('删除成功')
  loadPanels()
}

const handleDeleteCircuit = async (row: DistributionCircuit) => {
  await ElMessageBox.confirm('确定删除该回路？', '提示', { type: 'warning' })
  await deleteDistributionCircuit(row.id)
  ElMessage.success('删除成功')
  loadCircuits()
}

const handleSavePricing = async () => {
  saving.value = true
  try {
    if (pricingForm.value.id) {
      await updatePricing(pricingForm.value.id, pricingForm.value)
    } else {
      await createPricing(pricingForm.value)
    }
    ElMessage.success('保存成功')
    dialogs.pricing = false
    loadPricing()
  } finally {
    saving.value = false
  }
}

const handleDeletePricing = async (row: ElectricityPricing) => {
  await ElMessageBox.confirm('确定删除该电价时段？', '提示', { type: 'warning' })
  await deletePricing(row.id)
  ElMessage.success('删除成功')
  loadPricing()
}

const handleBillUpload = (file: any) => {
  // OCR功能预留 - 后续可接入百度/阿里云OCR识别电费单
  ElMessage.info('电费单OCR识别功能开发中，请手动添加电价配置')
  // 未来实现：
  // 1. 上传图片到后端
  // 2. 调用OCR接口识别电费单内容
  // 3. 解析识别结果，提取电价信息
  // 4. 自动填充pricingList
  console.log('上传文件:', file)
}

onMounted(() => {
  loadTransformers()
  loadMeterPoints()
  loadPanels()
  loadCircuits()
  loadPricing()
})
</script>

<style scoped lang="scss">
.energy-config {
  padding: 20px;

  // el-tabs border-card 深色主题样式
  :deep(.el-tabs--border-card) {
    background-color: var(--bg-card-solid);
    border-color: var(--border-color);

    > .el-tabs__header {
      background-color: var(--bg-tertiary);
      border-bottom-color: var(--border-color);

      .el-tabs__item {
        color: var(--text-secondary);
        border-color: var(--border-color);
        background-color: transparent;
        font-weight: 400;

        &:hover {
          color: var(--text-primary);
        }

        &.is-active {
          color: var(--primary-color);
          background-color: var(--bg-card-solid);
          border-bottom-color: var(--bg-card-solid);
          font-weight: 500;
        }
      }
    }

    > .el-tabs__content {
      background-color: var(--bg-card-solid);
      padding: 20px;
    }
  }

  // 表格深色样式
  :deep(.el-table) {
    background-color: transparent;
    color: var(--text-regular);

    th.el-table__cell {
      background-color: var(--bg-tertiary);
      color: var(--text-primary);
      border-color: var(--border-color);
      font-weight: 500;
    }

    td.el-table__cell {
      border-color: var(--border-color);
    }

    tr {
      background-color: transparent;

      &:hover > td.el-table__cell {
        background-color: var(--bg-hover);
      }
    }

    .el-table__body tr.el-table__row--striped td.el-table__cell {
      background-color: rgba(255, 255, 255, 0.02);
    }
  }

  // 对话框深色样式
  :deep(.el-dialog) {
    background-color: var(--bg-card-solid);
    border: 1px solid var(--border-color);

    .el-dialog__header {
      border-bottom: 1px solid var(--border-color);
    }

    .el-dialog__title {
      color: var(--text-primary);
    }

    .el-dialog__footer {
      border-top: 1px solid var(--border-color);
    }
  }

  // 表单样式
  :deep(.el-form-item__label) {
    color: var(--text-secondary);
  }

  :deep(.el-input__wrapper),
  :deep(.el-textarea__inner),
  :deep(.el-select .el-input__wrapper),
  :deep(.el-input-number) {
    background-color: rgba(255, 255, 255, 0.05);
    border-color: var(--border-color);

    &:hover {
      border-color: var(--primary-color);
    }
  }

  :deep(.el-input__inner),
  :deep(.el-textarea__inner) {
    color: var(--text-primary);

    &::placeholder {
      color: var(--text-placeholder);
    }
  }

  // Alert 样式
  :deep(.el-alert--info) {
    background-color: rgba(24, 144, 255, 0.1);
    border-color: rgba(24, 144, 255, 0.2);

    .el-alert__title {
      color: var(--primary-color);
    }

    .el-alert__description {
      color: var(--text-secondary);

      p {
        margin: 4px 0;
      }
    }
  }
}

.tab-header {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.summary-card {
  text-align: center;
  background-color: var(--bg-card-solid);
  border-color: var(--border-color);

  :deep(.el-card__body) {
    padding: 20px;
  }

  .summary-label {
    font-size: 14px;
    color: var(--text-secondary);
    margin-bottom: 8px;
  }

  .summary-value {
    font-size: 24px;
    font-weight: bold;
    color: var(--text-primary);

    &.danger {
      color: var(--error-color);
    }

    &.warning {
      color: var(--warning-color);
    }

    &.success {
      color: var(--success-color);
    }
  }
}

.price-value {
  font-weight: bold;
  color: var(--primary-color);
}
</style>
