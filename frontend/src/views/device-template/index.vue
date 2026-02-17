<template>
  <div class="device-template-page">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>设备模板管理</span>
          <el-button type="primary" :icon="Plus" @click="handleAdd">新增模板</el-button>
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
    <el-dialog v-model="dialogVisible" :title="editMode ? '编辑模板' : '新增模板'" width="600px">
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
    <el-dialog v-model="dsDialogVisible" title="从模板创建数据源" width="600px">
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
            <el-input-number v-model="dsForm.connection_config.slave_id" :min="1" :max="247" />
          </el-form-item>
        </template>

        <!-- Modbus RTU -->
        <template v-if="dsForm.protocol_type === 'modbus_rtu'">
          <el-form-item label="串口">
            <el-input v-model="dsForm.connection_config.serial_port" placeholder="COM1 或 /dev/ttyUSB0" />
          </el-form-item>
          <el-form-item label="波特率">
            <el-select v-model="dsForm.connection_config.baudrate">
              <el-option v-for="r in [9600, 19200, 38400, 57600, 115200]" :key="r" :label="r" :value="r" />
            </el-select>
          </el-form-item>
          <el-form-item label="数据位">
            <el-select v-model="dsForm.connection_config.data_bits">
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
            <el-select v-model="dsForm.connection_config.stop_bits">
              <el-option v-for="s in [1, 2]" :key="s" :label="s" :value="s" />
            </el-select>
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
      </el-form>
      <template #footer>
        <el-button @click="dsDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmitDS">确定</el-button>
      </template>
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
      return { host: '', port: 502, slave_id: 1 }
    case 'modbus_rtu':
      return { serial_port: '', baudrate: 9600, data_bits: 8, parity: 'N', stop_bits: 1 }
    case 'snmp_v2c':
    case 'snmp_v3':
      return { host: '', port: 161, community: 'public' }
    default:
      return {}
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
  Object.assign(dsForm, {
    templateId: row.id,
    templateName: row.name,
    name: '',
    protocol_type: row.protocol_type,
    connection_config: getDefaultConfig(row.protocol_type),
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
