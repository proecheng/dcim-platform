<template>
  <div class="device-template-page">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>设备模板管理</span>
          <div class="header-actions">
            <el-button @click="openBuiltinDialog">导入内置协议</el-button>
            <el-button type="primary" :icon="Plus" @click="handleAdd">新增模板</el-button>
          </div>
        </div>
      </template>

      <!-- 筛选条件 -->
      <el-form :inline="true" class="filter-form">
        <el-form-item label="厂商">
          <el-input v-model="filters.manufacturer" placeholder="厂商" clearable style="width: 150px" />
        </el-form-item>
        <el-form-item label="型号">
          <el-input v-model="filters.model_name" placeholder="型号" clearable style="width: 150px" />
        </el-form-item>
        <el-form-item label="协议类型">
          <el-select v-model="filters.protocol_type" style="width: 150px">
            <el-option label="全部" value="ALL" />
            <el-option label="Modbus TCP" value="modbus_tcp" />
            <el-option label="Modbus RTU" value="modbus_rtu" />
            <el-option label="SNMP v2c" value="snmp_v2c" />
            <el-option label="SNMP v3" value="snmp_v3" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="filters.keyword"
            placeholder="关键词搜索..."
            clearable
            style="width: 200px"
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 分页信息栏 -->
      <div class="pagination-bar">
        <span class="pagination-info">
          共 <strong>{{ total }}</strong> 条记录，第 <strong>{{ currentPage }}</strong> / <strong>{{ totalPages }}</strong> 页
        </span>
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100]"
          :total="total"
          layout="sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>

      <!-- 模板列表 -->
      <el-table :data="templates" stripe border style="width: 100%" table-layout="auto">
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column prop="manufacturer" label="厂商" min-width="120" />
        <el-table-column prop="model" label="型号" min-width="120" />
        <el-table-column prop="protocol_type" label="协议类型" width="130">
          <template #default="{ row }">
            <el-tag :type="getProtocolTagType(row.protocol_type)" size="small">
              {{ getProtocolLabel(row.protocol_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="点位数量" width="100">
          <template #default="{ row }">{{ (row.point_config || []).length }}</template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
            <el-button type="success" link @click="handleCreateDS(row)">创建数据源</el-button>
            <el-popconfirm title="确定删除该模板？" @confirm="handleDelete(row.id)">
              <template #reference>
                <el-button type="danger" link>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建/编辑模板对话框 -->
    <el-dialog append-to-body v-model="dialogVisible" :title="editMode ? '编辑模板' : '新增模板'" width="600px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入模板名称" />
        </el-form-item>
        <el-form-item label="厂商" prop="manufacturer">
          <el-input v-model="form.manufacturer" placeholder="请输入厂商" />
        </el-form-item>
        <el-form-item label="型号" prop="model">
          <el-input v-model="form.model" placeholder="请输入型号" />
        </el-form-item>
        <el-form-item label="协议类型" prop="protocol_type">
          <el-select v-model="form.protocol_type">
            <el-option v-for="opt in protocolOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="模板描述" />
        </el-form-item>
        <el-form-item label="点位配置" prop="point_config_str">
          <el-input
            v-model="form.point_config_str"
            type="textarea"
            :rows="8"
            placeholder='[{"address":"40001","data_type":"float32","scale":1.0,"offset":0.0,"description":"温度"}]'
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 从模板创建数据源对话框 -->
    <el-dialog append-to-body v-model="dsDialogVisible" title="从模板创建数据源" width="820px">
      <el-form ref="dsFormRef" :model="dsForm" :rules="dsRules" label-width="100px">
        <el-form-item label="模板名称">
          <span>{{ dsForm.templateName }}</span>
        </el-form-item>
        <el-form-item label="数据源名称" prop="name">
          <el-input v-model="dsForm.name" placeholder="请输入数据源名称" />
        </el-form-item>
        <el-form-item label="协议类型">
          <el-input :model-value="getProtocolLabel(dsForm.protocol_type)" disabled />
        </el-form-item>

        <!-- 协议动态配置 -->
        <el-divider content-position="left">协议配置</el-divider>

        <!-- Modbus TCP -->
        <template v-if="dsForm.protocol_type === 'modbus_tcp'">
          <el-form-item label="IP 地址">
            <el-input v-model="dsForm.connection_config.host" placeholder="192.168.1.100" />
          </el-form-item>
          <el-form-item label="端口">
            <el-input-number v-model="dsForm.connection_config.port" :min="1" :max="65535" />
          </el-form-item>
          <el-form-item label="从站地址">
            <el-input-number v-model="dsForm.connection_config.device_id" :min="1" :max="247" />
          </el-form-item>
        </template>

        <!-- Modbus RTU -->
        <template v-if="dsForm.protocol_type === 'modbus_rtu'">
          <el-form-item label="串口">
            <el-input v-model="dsForm.connection_config.port" placeholder="COM1 或 /dev/ttyUSB0" />
          </el-form-item>
          <el-form-item label="波特率">
            <el-select v-model="dsForm.connection_config.baudrate">
              <el-option v-for="r in [9600, 19200, 38400, 57600, 115200]" :key="r" :label="r" :value="r" />
            </el-select>
          </el-form-item>
          <el-form-item label="数据位">
            <el-select v-model="dsForm.connection_config.bytesize">
              <el-option v-for="b in [7, 8]" :key="b" :label="b" :value="b" />
            </el-select>
          </el-form-item>
          <el-form-item label="校验位">
            <el-select v-model="dsForm.connection_config.parity">
              <el-option label="无" value="N" />
              <el-option label="奇校验" value="O" />
              <el-option label="偶校验" value="E" />
            </el-select>
          </el-form-item>
          <el-form-item label="停止位">
            <el-select v-model="dsForm.connection_config.stopbits">
              <el-option v-for="s in [1, 2]" :key="s" :label="s" :value="s" />
            </el-select>
          </el-form-item>
          <el-form-item label="从站地址">
            <el-input-number v-model="dsForm.connection_config.device_id" :min="1" :max="247" />
          </el-form-item>
        </template>

        <!-- SNMP -->
        <template v-if="dsForm.protocol_type === 'snmp_v2c' || dsForm.protocol_type === 'snmp_v3'">
          <el-form-item label="目标地址">
            <el-input v-model="dsForm.connection_config.host" placeholder="192.168.1.100" />
          </el-form-item>
          <el-form-item label="端口">
            <el-input-number v-model="dsForm.connection_config.port" :min="1" :max="65535" />
          </el-form-item>
          <el-form-item label="团体名">
            <el-input v-model="dsForm.connection_config.community" placeholder="public" />
          </el-form-item>
        </template>

        <el-form-item label="采集周期">
          <el-input-number v-model="dsForm.collection_interval" :min="1" :max="60" />
          <span style="margin-left: 8px;">秒</span>
        </el-form-item>

        <el-divider content-position="left">业务设备</el-divider>
        <el-form-item label="设备编码">
          <el-input v-model="dsForm.connection_config.device_code" placeholder="如 UPS-A01 / FCOL-A01" />
        </el-form-item>
        <el-form-item label="设备名称">
          <el-input v-model="dsForm.connection_config.device_name" placeholder="业务设备名称" />
        </el-form-item>
        <el-form-item label="区域">
          <el-input v-model="dsForm.connection_config.area_code" placeholder="如 A1 / B1" />
        </el-form-item>
        <el-form-item label="额定功率">
          <el-input-number v-model="dsForm.connection_config.rated_power" :min="0" :precision="1" />
          <span style="margin-left: 8px;">kW</span>
        </el-form-item>
        <el-form-item label="额定电压">
          <el-input-number v-model="dsForm.connection_config.rated_voltage" :min="0" :precision="1" />
          <span style="margin-left: 8px;">V</span>
        </el-form-item>
        <el-form-item label="额定电流">
          <el-input-number v-model="dsForm.connection_config.rated_current" :min="0" :precision="1" />
          <span style="margin-left: 8px;">A</span>
        </el-form-item>
        <el-form-item label="细分负荷">
          <el-select
            v-model="dsForm.connection_config.load_subtype"
            clearable
            placeholder="请选择"
            style="width: 100%"
            @change="handleLoadSubtypeChange"
          >
            <el-option v-for="opt in loadSubtypeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="可控项">
          <el-select
            v-model="dsForm.connection_config.controllable_params"
            multiple
            collapse-tags
            collapse-tags-tooltip
            placeholder="选择可控参数"
            style="width: 100%"
          >
            <el-option v-for="opt in controlParamOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
        <template v-if="dsForm.connection_config.load_subtype === 'thermal_storage'">
          <el-form-item label="蓄冷容量">
            <el-input-number v-model="dsForm.connection_config.thermal_storage_config.capacity_kwh" :min="0" :precision="1" />
            <span style="margin-left: 8px;">kWh</span>
          </el-form-item>
          <el-form-item label="最大放冷">
            <el-input-number v-model="dsForm.connection_config.thermal_storage_config.max_discharge_kw" :min="0" :precision="1" />
            <span style="margin-left: 8px;">kW</span>
          </el-form-item>
          <el-form-item label="最大充冷">
            <el-input-number v-model="dsForm.connection_config.thermal_storage_config.max_charge_kw" :min="0" :precision="1" />
            <span style="margin-left: 8px;">kW</span>
          </el-form-item>
          <el-form-item label="等效COP">
            <el-input-number v-model="dsForm.connection_config.thermal_storage_config.equivalent_cop" :min="0.5" :max="12" :precision="2" />
          </el-form-item>
          <el-form-item label="放冷效率">
            <el-input-number v-model="dsForm.connection_config.thermal_storage_config.discharge_efficiency" :min="0.1" :max="1" :step="0.05" :precision="2" />
          </el-form-item>
          <el-form-item label="辅机功率">
            <el-input-number v-model="dsForm.connection_config.thermal_storage_config.auxiliary_power_kw" :min="0" :precision="1" />
            <span style="margin-left: 8px;">kW</span>
          </el-form-item>
          <el-form-item label="等效电功率">
            <el-input-number v-model="dsForm.connection_config.thermal_storage_config.equivalent_power_kw" :min="0" :precision="1" />
            <span style="margin-left: 8px;">kW</span>
          </el-form-item>
        </template>

        <el-divider content-position="left">资产台账</el-divider>
        <el-form-item label="资产编码">
          <el-input v-model="dsForm.connection_config.asset_code" placeholder="填写后自动创建/更新资产" />
        </el-form-item>
        <el-form-item label="资产名称">
          <el-input v-model="dsForm.connection_config.asset_name" placeholder="默认使用设备名称" />
        </el-form-item>
        <el-form-item label="机柜编码">
          <el-input v-model="dsForm.connection_config.cabinet_code" placeholder="需已存在，不填写则不绑定机柜" />
        </el-form-item>
        <el-form-item label="U位">
          <el-input-number v-model="dsForm.connection_config.u_position" :min="1" :max="60" />
          <span style="margin: 0 8px;">占用</span>
          <el-input-number v-model="dsForm.connection_config.u_height" :min="1" :max="60" />
          <span style="margin-left: 8px;">U</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dsDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmitDS">确定</el-button>
      </template>
    </el-dialog>

    <!-- 内置协议模板 -->
    <el-dialog append-to-body v-model="builtinDialogVisible" title="导入内置协议模板" width="760px">
      <el-table :data="builtinTemplates" v-loading="builtinLoading" stripe border table-layout="auto">
        <el-table-column prop="name" label="名称" min-width="220" />
        <el-table-column prop="model" label="型号" min-width="130" />
        <el-table-column prop="protocol_type" label="协议" width="120">
          <template #default="{ row }">{{ getProtocolLabel(row.protocol_type) }}</template>
        </el-table-column>
        <el-table-column prop="point_count" label="点位" width="80" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button
              type="primary"
              link
              :loading="installingBuiltinKey === row.key"
              @click="handleInstallBuiltin(row.key)"
            >
              安装
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { Plus, Search } from '@element-plus/icons-vue'
import {
  getTemplates,
  createTemplate,
  updateTemplate,
  deleteTemplate,
  createDatasourceFromTemplate,
  getBuiltinTemplates,
  installBuiltinTemplate,
  type BuiltinDeviceTemplate,
  type DeviceTemplate
} from '@/api/device-template'
import { ElMessage } from 'element-plus'

const templates = ref<DeviceTemplate[]>([])
const dialogVisible = ref(false)
const editMode = ref(false)
const formRef = ref()

// 创建数据源对话框
const dsDialogVisible = ref(false)
const dsFormRef = ref()
const builtinDialogVisible = ref(false)
const builtinTemplates = ref<BuiltinDeviceTemplate[]>([])
const builtinLoading = ref(false)
const installingBuiltinKey = ref('')

// 分页
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const totalPages = computed(() => Math.ceil(total.value / pageSize.value) || 1)

const filters = reactive({
  manufacturer: '',
  model_name: '',
  protocol_type: 'ALL',
  keyword: ''
})

const protocolOptions = [
  { label: 'Modbus TCP', value: 'modbus_tcp' },
  { label: 'Modbus RTU', value: 'modbus_rtu' },
  { label: 'SNMP v2c', value: 'snmp_v2c' },
  { label: 'SNMP v3', value: 'snmp_v3' },
]

const loadSubtypeOptions = [
  { label: '行级/微模块空调', value: 'row_ac' },
  { label: '柜类空调', value: 'cabinet_ac' },
  { label: '房间级空调', value: 'room_ac' },
  { label: '冷冻水末端', value: 'chilled_water_terminal' },
  { label: '大型水冷冷机', value: 'water_cooled_chiller' },
  { label: '变频水泵', value: 'pump_vfd' },
  { label: '冷却塔', value: 'cooling_tower' },
  { label: '蓄冷系统', value: 'thermal_storage' },
]

const defaultControlsBySubtype: Record<string, string[]> = {
  row_ac: ['temperature_setpoint', 'fan_speed', 'cooling_output'],
  cabinet_ac: ['temperature_setpoint', 'fan_speed', 'compressor_frequency'],
  room_ac: ['temperature_setpoint', 'fan_speed'],
  chilled_water_terminal: ['supply_air_temperature', 'chilled_water_valve', 'fan_speed'],
  water_cooled_chiller: ['chilled_water_supply_temperature', 'chilled_water_return_temperature', 'compressor_frequency', 'pump_frequency', 'flow_rate'],
  pump_vfd: ['pump_frequency', 'flow_rate'],
  cooling_tower: ['cooling_tower_fan'],
  thermal_storage: ['storage_charge', 'storage_discharge', 'storage_soc', 'pump_frequency'],
}

const controlParamOptions = [
  { label: '开关机控制', value: 'power_switch' },
  { label: '温度设定', value: 'temperature_setpoint' },
  { label: '湿度设定', value: 'humidity_setpoint' },
  { label: '送风温度', value: 'supply_air_temperature' },
  { label: '回风温度', value: 'return_air_temperature' },
  { label: '冷冻水供水温度', value: 'chilled_water_supply_temperature' },
  { label: '冷冻水回水温度', value: 'chilled_water_return_temperature' },
  { label: '冷冻水阀门开度', value: 'chilled_water_valve' },
  { label: '风机转速/风速', value: 'fan_speed' },
  { label: '室内风机输出', value: 'indoor_fan_output' },
  { label: '压缩机频率', value: 'compressor_frequency' },
  { label: '制冷输出', value: 'cooling_output' },
  { label: '水泵变频', value: 'pump_frequency' },
  { label: '水流量', value: 'flow_rate' },
  { label: '冷却塔风机', value: 'cooling_tower_fan' },
  { label: '蓄冷充冷', value: 'storage_charge' },
  { label: '蓄冷放冷', value: 'storage_discharge' },
  { label: '蓄冷余量', value: 'storage_soc' },
  { label: '照明亮度', value: 'brightness' },
]

type TagType = 'success' | 'warning' | 'danger' | 'info' | 'primary'

function getProtocolTagType(type: string): TagType {
  const map: Record<string, TagType> = {
    modbus_tcp: 'primary',
    modbus_rtu: 'warning',
    snmp_v2c: 'success',
    snmp_v3: 'danger'
  }
  return map[type] || 'info'
}

function getProtocolLabel(type: string): string {
  const map: Record<string, string> = {
    modbus_tcp: 'Modbus TCP',
    modbus_rtu: 'Modbus RTU',
    snmp_v2c: 'SNMP v2c',
    snmp_v3: 'SNMP v3'
  }
  return map[type] || type
}

function getDefaultConfig(protocolType: string): Record<string, any> {
  switch (protocolType) {
    case 'modbus_tcp':
      return { host: '', port: 502, device_id: 1, timeout: 3, word_order: 'big' }
    case 'modbus_rtu':
      return { port: 'COM1', baudrate: 9600, bytesize: 8, parity: 'N', stopbits: 1, device_id: 1, timeout: 3, word_order: 'big' }
    case 'snmp_v2c':
    case 'snmp_v3':
      return { host: '', port: 161, community: 'public' }
    default:
      return {}
  }
}

function inferDefaultSubtype(row: DeviceTemplate): string {
  const text = `${row.model || ''} ${row.name || ''}`.toLowerCase()
  if (text.includes('fusioncol') || text.includes('行级') || text.includes('微模块')) return 'row_ac'
  if (text.includes('chiller') || text.includes('冷机') || text.includes('水冷')) return 'water_cooled_chiller'
  if (text.includes('pump') || text.includes('水泵')) return 'pump_vfd'
  if (text.includes('蓄冷') || text.includes('storage') || text.includes('tes')) return 'thermal_storage'
  if (text.includes('ups')) return ''
  return ''
}

function handleLoadSubtypeChange(value: string) {
  dsForm.connection_config.controllable_params = defaultControlsBySubtype[value] ? [...defaultControlsBySubtype[value]] : []
  if (value === 'thermal_storage' && !dsForm.connection_config.thermal_storage_config) {
    dsForm.connection_config.thermal_storage_config = {}
  }
  if (value === 'thermal_storage') {
    dsForm.connection_config.thermal_storage_config = {
      equivalent_cop: 4,
      discharge_efficiency: 0.9,
      auxiliary_power_kw: 0,
      ...dsForm.connection_config.thermal_storage_config
    }
  }
}

async function openBuiltinDialog() {
  builtinDialogVisible.value = true
  if (builtinTemplates.value.length > 0) return
  await loadBuiltinTemplates()
}

async function loadBuiltinTemplates() {
  builtinLoading.value = true
  try {
    builtinTemplates.value = await getBuiltinTemplates()
  } catch (e) {
    console.error('加载内置协议模板失败', e)
  } finally {
    builtinLoading.value = false
  }
}

async function handleInstallBuiltin(key: string) {
  installingBuiltinKey.value = key
  try {
    await installBuiltinTemplate(key)
    ElMessage.success('内置协议模板已安装')
    builtinDialogVisible.value = false
    await loadTemplates()
  } catch (e) {
    console.error('安装内置协议模板失败', e)
  } finally {
    installingBuiltinKey.value = ''
  }
}

const form = reactive({
  id: 0,
  name: '',
  manufacturer: '',
  model: '',
  protocol_type: 'modbus_tcp',
  description: '',
  point_config_str: '[]'
})

const rules = {
  name: [{ required: true, message: '请输入模板名称', trigger: 'blur' }],
  manufacturer: [{ required: true, message: '请输入厂商', trigger: 'blur' }],
  model: [{ required: true, message: '请输入型号', trigger: 'blur' }],
  protocol_type: [{ required: true, message: '请选择协议类型', trigger: 'change' }],
}

const dsForm = reactive({
  templateId: 0,
  templateName: '',
  name: '',
  protocol_type: 'modbus_tcp',
  connection_config: {} as Record<string, any>,
  collection_interval: 5
})

const dsRules = {
  name: [{ required: true, message: '请输入数据源名称', trigger: 'blur' }],
}

onMounted(() => {
  loadTemplates()
})

async function loadTemplates() {
  try {
    const params: Record<string, any> = {
      page: currentPage.value,
      page_size: pageSize.value
    }
    if (filters.manufacturer && filters.manufacturer.trim()) {
      params.manufacturer = filters.manufacturer.trim()
    }
    if (filters.model_name && filters.model_name.trim()) {
      params.model_name = filters.model_name.trim()
    }
    if (filters.protocol_type && filters.protocol_type !== 'ALL') {
      params.protocol_type = filters.protocol_type
    }
    if (filters.keyword && filters.keyword.trim()) {
      params.keyword = filters.keyword.trim()
    }
    const result = await getTemplates(params)
    if (Array.isArray(result)) {
      templates.value = result
      total.value = result.length
    } else {
      templates.value = result.items || []
      total.value = result.total || 0
    }
  } catch (e) {
    console.error('加载模板失败', e)
  }
}

function handlePageChange(page: number) {
  currentPage.value = page
  loadTemplates()
}

function handleSizeChange(size: number) {
  pageSize.value = size
  currentPage.value = 1
  loadTemplates()
}

function handleSearch() {
  currentPage.value = 1
  loadTemplates()
}

function resetFilters() {
  filters.manufacturer = ''
  filters.model_name = ''
  filters.protocol_type = 'ALL'
  filters.keyword = ''
  currentPage.value = 1
  loadTemplates()
}

function handleAdd() {
  editMode.value = false
  Object.assign(form, {
    id: 0,
    name: '',
    manufacturer: '',
    model: '',
    protocol_type: 'modbus_tcp',
    description: '',
    point_config_str: '[]'
  })
  dialogVisible.value = true
}

function handleEdit(row: DeviceTemplate) {
  editMode.value = true
  Object.assign(form, {
    id: row.id,
    name: row.name,
    manufacturer: row.manufacturer,
    model: row.model,
    protocol_type: row.protocol_type,
    description: row.description || '',
    point_config_str: JSON.stringify(row.point_config || [], null, 2)
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate()
  if (!valid) return

  let pointConfig: Array<Record<string, any>>
  try {
    pointConfig = JSON.parse(form.point_config_str)
    if (!Array.isArray(pointConfig)) {
      ElMessage.error('点位配置必须是 JSON 数组')
      return
    }
  } catch {
    ElMessage.error('点位配置 JSON 格式错误')
    return
  }

  try {
    const data = {
      name: form.name,
      manufacturer: form.manufacturer,
      model: form.model,
      protocol_type: form.protocol_type,
      description: form.description || undefined,
      point_config: pointConfig
    }
    if (editMode.value) {
      await updateTemplate(form.id, data)
      ElMessage.success('更新成功')
    } else {
      await createTemplate(data)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadTemplates()
  } catch (e) {
    console.error('操作失败', e)
  }
}

async function handleDelete(id: number) {
  try {
    await deleteTemplate(id)
    ElMessage.success('删除成功')
    loadTemplates()
  } catch (e) {
    console.error('删除失败', e)
  }
}

function handleCreateDS(row: DeviceTemplate) {
  const templateDefaultConfig = row.extra_config?.default_connection_config || {}
  const loadSubtype = inferDefaultSubtype(row)
  const thermalStorageConfig = loadSubtype === 'thermal_storage'
    ? { equivalent_cop: 4, discharge_efficiency: 0.9, auxiliary_power_kw: 0 }
    : {}
  Object.assign(dsForm, {
    templateId: row.id,
    templateName: row.name,
    name: '',
    protocol_type: row.protocol_type,
    connection_config: {
      ...getDefaultConfig(row.protocol_type),
      ...templateDefaultConfig,
      device_code: '',
      device_name: '',
      area_code: 'A1',
      rated_power: undefined,
      rated_voltage: undefined,
      rated_current: undefined,
      load_subtype: loadSubtype,
      controllable_params: loadSubtype ? [...(defaultControlsBySubtype[loadSubtype] || [])] : [],
      thermal_storage_config: thermalStorageConfig,
      asset_code: '',
      asset_name: '',
      cabinet_code: '',
      u_position: undefined,
      u_height: undefined
    },
    collection_interval: 5
  })
  dsDialogVisible.value = true
}

async function handleSubmitDS() {
  const valid = await dsFormRef.value?.validate()
  if (!valid) return

  try {
    const data = {
      name: dsForm.name,
      protocol_type: dsForm.protocol_type,
      connection_config: dsForm.connection_config,
      collection_interval: dsForm.collection_interval
    }
    await createDatasourceFromTemplate(dsForm.templateId, data)
    ElMessage.success('数据源创建成功')
    dsDialogVisible.value = false
  } catch (e) {
    console.error('创建数据源失败', e)
  }
}
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.device-template-page {
  @include page-list;
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .header-actions {
    display: flex;
    gap: 8px;
  }

  .filter-form {
    margin-bottom: 20px;
  }

  .pagination-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    padding: 8px 12px;
    background: rgba(64, 158, 255, 0.05);
    border-radius: 4px;

    .pagination-info {
      font-size: 13px;
      color: #909399;

      strong {
        color: var(--el-color-primary);
        margin: 0 2px;
      }
    }
  }
}
</style>
