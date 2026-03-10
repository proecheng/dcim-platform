<template>
  <div class="datasource-page">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>数据源管理</span>
          <div>
            <el-button :icon="Download" @click="handleExport">导出报告</el-button>
            <el-button type="primary" :icon="Plus" @click="handleAdd">新增数据源</el-button>
          </div>
        </div>
      </template>

      <!-- 筛选条件 -->
      <el-form :inline="true" class="filter-form">
        <el-form-item label="协议类型">
          <el-select v-model="filters.protocol_type" style="width: 150px">
            <el-option label="全部" value="ALL" />
            <el-option label="Modbus TCP" value="modbus_tcp" />
            <el-option label="Modbus RTU" value="modbus_rtu" />
            <el-option label="SNMP v2c" value="snmp_v2c" />
            <el-option label="SNMP v3" value="snmp_v3" />
            <el-option label="MQTT" value="mqtt" />
            <el-option label="HTTP REST" value="http_rest" />
            <el-option label="BACnet/IP" value="bacnet_ip" />
            <el-option label="OPC-UA" value="opc_ua" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" style="width: 130px">
            <el-option label="全部" value="ALL" />
            <el-option label="已连接" value="connected" />
            <el-option label="未连接" value="disconnected" />
            <el-option label="通信中断" value="interrupted" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="filters.keyword"
            placeholder="搜索数据源名称..."
            clearable
            style="width: 220px;"
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

      <!-- 数据源列表 -->
      <el-table :data="datasources" stripe border style="width: 100%" table-layout="auto" row-key="id">
        <el-table-column type="expand">
          <template #default="{ row }">
            <div v-if="getCommStatus(row.id)" class="impact-panel">
              <el-descriptions :column="3" border size="small">
                <el-descriptions-item label="受影响点位数">
                  <el-tag type="warning" size="small">{{ getCommStatus(row.id)?.affected_points ?? 0 }}</el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="受影响设备数">
                  <el-tag type="danger" size="small">{{ getCommStatus(row.id)?.affected_devices ?? 0 }}</el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="中断时长">
                  {{ formatDuration(getCommStatus(row.id)?.interruption_duration_seconds) }}
                </el-descriptions-item>
              </el-descriptions>
            </div>
            <div v-else style="padding: 12px; color: #909399;">暂无通信状态数据</div>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column prop="protocol_type" label="协议类型" width="130">
          <template #default="{ row }">
            <el-tag :type="getProtocolTagType(row.protocol_type)" size="small">
              {{ getProtocolLabel(row.protocol_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="collection_interval" label="采集周期" width="100">
          <template #default="{ row }">{{ row.collection_interval }}秒</template>
        </el-table-column>
        <el-table-column prop="write_enabled" label="写入权限" width="100">
          <template #default="{ row }">
            <el-switch
              v-model="row.write_enabled"
              @change="handleToggleWrite(row)"
              :before-change="() => confirmWriteChange(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="通信状态" width="110">
          <template #default="{ row }">
            <el-tag :type="commStatusType(row.status)" size="small">
              {{ commStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最后通信" min-width="170">
          <template #default="{ row }">
            {{ getCommStatus(row.id)?.last_communication || row.last_communication || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="连续失败" width="90">
          <template #default="{ row }">
            <span :style="{ color: (getCommStatus(row.id)?.consecutive_failures ?? row.consecutive_failures) > 0 ? '#E6A23C' : '' }">
              {{ getCommStatus(row.id)?.consecutive_failures ?? row.consecutive_failures }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="is_enabled" label="启用" width="70">
          <template #default="{ row }">
            <el-switch
              v-model="row.is_enabled"
              @change="handleToggle(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
            <el-button type="success" link @click="handleTestExisting(row)">测试连接</el-button>
            <el-button type="warning" link :icon="Upload" @click="handleOpenImport(row)">导入点位</el-button>
            <el-popconfirm title="确定删除该数据源？" @confirm="handleDelete(row.id)">
              <template #reference>
                <el-button type="danger" link>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建/编辑对话框 -->
    <el-dialog append-to-body v-model="dialogVisible" :title="editMode ? '编辑数据源' : '新增数据源'" width="600px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入数据源名称" />
        </el-form-item>
        <el-form-item label="协议类型" prop="protocol_type">
          <el-select v-model="form.protocol_type" :disabled="editMode" @change="handleProtocolChange">
            <el-option
              v-for="opt in protocolOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="采集周期" prop="collection_interval">
          <el-input-number v-model="form.collection_interval" :min="1" :max="60" />
          <span style="margin-left: 8px;">秒</span>
        </el-form-item>
        <el-form-item label="启用状态">
          <el-switch v-model="form.is_enabled" />
        </el-form-item>

        <!-- 协议动态配置 -->
        <el-divider content-position="left">协议配置</el-divider>

        <!-- Modbus TCP -->
        <template v-if="form.protocol_type === 'modbus_tcp'">
          <el-form-item label="IP 地址">
            <el-input v-model="form.connection_config.host" placeholder="192.168.1.100" />
          </el-form-item>
          <el-form-item label="端口">
            <el-input-number v-model="form.connection_config.port" :min="1" :max="65535" />
          </el-form-item>
          <el-form-item label="从站地址">
            <el-input-number v-model="form.connection_config.slave_id" :min="1" :max="247" />
          </el-form-item>
        </template>

        <!-- Modbus RTU -->
        <template v-if="form.protocol_type === 'modbus_rtu'">
          <el-form-item label="串口">
            <el-input v-model="form.connection_config.serial_port" placeholder="COM1 或 /dev/ttyUSB0" />
          </el-form-item>
          <el-form-item label="波特率">
            <el-select v-model="form.connection_config.baudrate">
              <el-option v-for="r in [9600, 19200, 38400, 57600, 115200]" :key="r" :label="r" :value="r" />
            </el-select>
          </el-form-item>
          <el-form-item label="数据位">
            <el-select v-model="form.connection_config.data_bits">
              <el-option v-for="b in [7, 8]" :key="b" :label="b" :value="b" />
            </el-select>
          </el-form-item>
          <el-form-item label="校验位">
            <el-select v-model="form.connection_config.parity">
              <el-option label="无" value="N" />
              <el-option label="奇校验" value="O" />
              <el-option label="偶校验" value="E" />
            </el-select>
          </el-form-item>
          <el-form-item label="停止位">
            <el-select v-model="form.connection_config.stop_bits">
              <el-option v-for="s in [1, 2]" :key="s" :label="s" :value="s" />
            </el-select>
          </el-form-item>
        </template>

        <!-- SNMP v2c -->
        <template v-if="form.protocol_type === 'snmp_v2c'">
          <el-form-item label="目标地址">
            <el-input v-model="form.connection_config.host" placeholder="192.168.1.100" />
          </el-form-item>
          <el-form-item label="端口">
            <el-input-number v-model="form.connection_config.port" :min="1" :max="65535" />
          </el-form-item>
          <el-form-item label="团体名">
            <el-input v-model="form.connection_config.community" placeholder="public" />
          </el-form-item>
        </template>

        <!-- SNMP v3 -->
        <template v-if="form.protocol_type === 'snmp_v3'">
          <el-form-item label="目标地址">
            <el-input v-model="form.connection_config.host" placeholder="192.168.1.100" />
          </el-form-item>
          <el-form-item label="端口">
            <el-input-number v-model="form.connection_config.port" :min="1" :max="65535" />
          </el-form-item>
          <el-form-item label="用户名">
            <el-input v-model="form.connection_config.username" placeholder="请输入SNMPv3用户名" />
          </el-form-item>
          <el-form-item label="认证协议">
            <el-select v-model="form.connection_config.auth_protocol" placeholder="请选择" style="width: 100%;">
              <el-option label="无" value="none" />
              <el-option label="MD5" value="MD5" />
              <el-option label="SHA" value="SHA" />
            </el-select>
          </el-form-item>
          <el-form-item label="认证密码" v-if="form.connection_config.auth_protocol && form.connection_config.auth_protocol !== 'none'">
            <el-input v-model="form.connection_config.auth_password" type="password" show-password placeholder="请输入认证密码" />
          </el-form-item>
          <el-form-item label="加密协议">
            <el-select v-model="form.connection_config.priv_protocol" placeholder="请选择" style="width: 100%;">
              <el-option label="无" value="none" />
              <el-option label="DES" value="DES" />
              <el-option label="AES" value="AES" />
            </el-select>
          </el-form-item>
          <el-form-item label="加密密码" v-if="form.connection_config.priv_protocol && form.connection_config.priv_protocol !== 'none'">
            <el-input v-model="form.connection_config.priv_password" type="password" show-password placeholder="请输入加密密码" />
          </el-form-item>
        </template>

        <!-- MQTT -->
        <template v-if="form.protocol_type === 'mqtt'">
          <el-form-item label="Broker地址">
            <el-input v-model="form.connection_config.broker" placeholder="broker.example.com" />
          </el-form-item>
          <el-form-item label="端口">
            <el-input-number v-model="form.connection_config.port" :min="1" :max="65535" />
          </el-form-item>
          <el-form-item label="Topic">
            <el-input v-model="form.connection_config.topic" placeholder="sensors/+/data" />
          </el-form-item>
          <el-form-item label="Client ID">
            <el-input v-model="form.connection_config.client_id" placeholder="可选，留空自动生成" />
          </el-form-item>
          <el-form-item label="用户名">
            <el-input v-model="form.connection_config.username" placeholder="MQTT 用户名（可选）" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="form.connection_config.password" type="password" show-password placeholder="MQTT 密码（可选）" />
          </el-form-item>
          <el-form-item label="消息格式">
            <el-select v-model="form.connection_config.message_format" style="width: 100%;">
              <el-option label="JSON" value="json" />
              <el-option label="自定义" value="custom" />
            </el-select>
          </el-form-item>
        </template>

        <!-- HTTP REST -->
        <template v-if="form.protocol_type === 'http_rest'">
          <el-form-item label="请求URL">
            <el-input v-model="form.connection_config.url" placeholder="https://api.example.com/data" />
          </el-form-item>
          <el-form-item label="请求方式">
            <el-select v-model="form.connection_config.method" style="width: 100%;">
              <el-option label="GET" value="GET" />
              <el-option label="POST" value="POST" />
            </el-select>
          </el-form-item>
          <el-form-item label="认证方式">
            <el-select v-model="form.connection_config.auth_type" style="width: 100%;">
              <el-option label="无" value="none" />
              <el-option label="Basic Auth" value="basic" />
              <el-option label="Bearer Token" value="bearer" />
            </el-select>
          </el-form-item>
          <el-form-item label="用户名" v-if="form.connection_config.auth_type === 'basic'">
            <el-input v-model="form.connection_config.username" placeholder="Basic Auth 用户名" />
          </el-form-item>
          <el-form-item label="密码" v-if="form.connection_config.auth_type === 'basic'">
            <el-input v-model="form.connection_config.password" type="password" show-password placeholder="Basic Auth 密码" />
          </el-form-item>
          <el-form-item label="Token" v-if="form.connection_config.auth_type === 'bearer'">
            <el-input v-model="form.connection_config.auth_token" placeholder="Bearer Token" />
          </el-form-item>
          <el-form-item label="数据路径">
            <el-input v-model="form.connection_config.data_path" placeholder="JSON 数据路径，如 data.sensors" />
          </el-form-item>
        </template>

        <!-- BACnet/IP -->
        <template v-if="form.protocol_type === 'bacnet_ip'">
          <el-form-item label="设备地址">
            <el-input v-model="form.connection_config.host" placeholder="192.168.1.100" />
          </el-form-item>
          <el-form-item label="端口">
            <el-input-number v-model="form.connection_config.port" :min="1" :max="65535" />
          </el-form-item>
          <el-form-item label="设备实例">
            <el-input-number v-model="form.connection_config.device_instance" :min="0" :max="4194302" />
          </el-form-item>
        </template>

        <!-- OPC-UA -->
        <template v-if="form.protocol_type === 'opc_ua'">
          <el-form-item label="端点URL">
            <el-input v-model="form.connection_config.endpoint_url" placeholder="opc.tcp://192.168.1.100:4840" />
          </el-form-item>
          <el-form-item label="安全模式">
            <el-select v-model="form.connection_config.security_mode" style="width: 100%;">
              <el-option label="无" value="None" />
              <el-option label="签名" value="Sign" />
              <el-option label="签名并加密" value="SignAndEncrypt" />
            </el-select>
          </el-form-item>
          <el-form-item label="用户名" v-if="form.connection_config.security_mode !== 'None'">
            <el-input v-model="form.connection_config.username" placeholder="OPC-UA 用户名" />
          </el-form-item>
          <el-form-item label="密码" v-if="form.connection_config.security_mode !== 'None'">
            <el-input v-model="form.connection_config.password" type="password" show-password placeholder="OPC-UA 密码" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <div style="display: flex; justify-content: space-between;">
          <el-button :loading="testing" @click="handleTestConnection">
            测试连接
          </el-button>
          <div>
            <el-button @click="dialogVisible = false">取消</el-button>
            <el-button type="primary" @click="handleSubmit">确定</el-button>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- 导入点位对话框 -->
    <el-dialog append-to-body v-model="importDialogVisible" title="批量导入点位" width="650px">
      <div>
        <p style="margin-bottom: 12px; color: #909399; font-size: 13px;">
          上传 .xlsx 格式的点位配置文件，系统将自动校验数据有效性。
          必填列：address（地址）、data_type（数据类型）。
          可选列：scale、offset、enum_mapping、is_dry_contact。
        </p>
        <el-upload
          ref="uploadRef"
          :auto-upload="false"
          :limit="1"
          accept=".xlsx"
          :on-change="handleFileChange"
          :on-exceed="() => ElMessage.warning('只能上传一个文件')"
          drag
        >
          <el-icon style="font-size: 40px; color: #909399;"><Upload /></el-icon>
          <div>将文件拖到此处，或<em>点击上传</em></div>
        </el-upload>

        <!-- 校验报告 -->
        <div v-if="importReport" style="margin-top: 16px;">
          <el-alert
            :title="`校验完成：共 ${importReport.total} 条，通过 ${importReport.passed} 条，失败 ${importReport.failed} 条`"
            :type="importReport.failed === 0 ? 'success' : 'warning'"
            :closable="false"
            show-icon
          />
          <el-table v-if="importReport.errors.length > 0" :data="importReport.errors" size="small" max-height="200" style="margin-top: 8px;" border>
            <el-table-column prop="row" label="行号" width="70" />
            <el-table-column prop="field" label="字段" width="120" />
            <el-table-column prop="message" label="错误信息" />
          </el-table>
        </div>
      </div>
      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button :loading="validating" @click="handleValidate">校验</el-button>
        <el-button
          type="primary"
          :loading="importing"
          :disabled="!importReport || importReport.failed > 0"
          @click="handleImport"
        >
          确认导入
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { Plus, Search, Upload, Download } from '@element-plus/icons-vue'
import {
  getDatasources,
  createDatasource,
  updateDatasource,
  deleteDatasource,
  testConnection,
  testExistingConnection,
  validatePoints,
  importPoints,
  toggleWritePermission,
  exportReport,
  getCommunicationStatus,
  type DataSource,
  type CommunicationStatusItem
} from '@/api/datasource'
import { ElMessageBox, ElMessage, type UploadFile } from 'element-plus'

const datasources = ref<DataSource[]>([])
const dialogVisible = ref(false)
const editMode = ref(false)
const formRef = ref()
const testing = ref(false)

// 导入点位状态
const importDialogVisible = ref(false)
const importDatasourceId = ref(0)
const importFile = ref<File | null>(null)
const importReport = ref<{ total: number; passed: number; failed: number; errors: { row: number; field: string; message: string }[] } | null>(null)
const validating = ref(false)
const importing = ref(false)
const uploadRef = ref()

// 分页状态
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const totalPages = computed(() => Math.ceil(total.value / pageSize.value) || 1)

const filters = reactive({
  protocol_type: 'ALL',
  status: 'ALL',
  keyword: ''
})

// 通信状态数据
const commStatusMap = ref<Map<number, CommunicationStatusItem>>(new Map())
let commStatusTimer: ReturnType<typeof setInterval> | null = null

const protocolOptions = [
  { label: 'Modbus TCP', value: 'modbus_tcp' },
  { label: 'Modbus RTU', value: 'modbus_rtu' },
  { label: 'SNMP v2c', value: 'snmp_v2c' },
  { label: 'SNMP v3', value: 'snmp_v3' },
  { label: 'MQTT', value: 'mqtt' },
  { label: 'HTTP REST', value: 'http_rest' },
  { label: 'BACnet/IP', value: 'bacnet_ip' },
  { label: 'OPC-UA', value: 'opc_ua' },
]

function getDefaultConfig(protocolType: string): Record<string, any> {
  switch (protocolType) {
    case 'modbus_tcp':
      return { host: '', port: 502, slave_id: 1 }
    case 'modbus_rtu':
      return { serial_port: '', baudrate: 9600, data_bits: 8, parity: 'N', stop_bits: 1 }
    case 'snmp_v2c':
      return { host: '', port: 161, community: 'public' }
    case 'snmp_v3':
      return { host: '', port: 161, username: '', auth_protocol: 'none', auth_password: '', priv_protocol: 'none', priv_password: '' }
    case 'mqtt':
      return { broker: '', port: 1883, topic: '', client_id: '', username: '', password: '', message_format: 'json' }
    case 'http_rest':
      return { url: '', method: 'GET', auth_type: 'none', auth_token: '', username: '', password: '', data_path: '' }
    case 'bacnet_ip':
      return { host: '', port: 47808, device_instance: 0 }
    case 'opc_ua':
      return { endpoint_url: '', security_mode: 'None', username: '', password: '' }
    default:
      return {}
  }
}

const form = reactive({
  id: 0,
  name: '',
  protocol_type: 'modbus_tcp',
  collection_interval: 5,
  is_enabled: true,
  connection_config: getDefaultConfig('modbus_tcp') as Record<string, any>
})

const rules = {
  name: [{ required: true, message: '请输入数据源名称', trigger: 'blur' }],
  protocol_type: [{ required: true, message: '请选择协议类型', trigger: 'change' }],
  collection_interval: [{ required: true, message: '请输入采集周期', trigger: 'blur' }]
}

type TagType = 'success' | 'warning' | 'danger' | 'info' | 'primary'

function getProtocolTagType(type: string): TagType {
  const map: Record<string, TagType> = {
    modbus_tcp: 'primary',
    modbus_rtu: 'warning',
    snmp_v2c: 'success',
    snmp_v3: 'danger',
    mqtt: 'info',
    http_rest: 'primary',
    bacnet_ip: 'warning',
    opc_ua: 'success'
  }
  return map[type] || 'info'
}

function getProtocolLabel(type: string): string {
  const map: Record<string, string> = {
    modbus_tcp: 'Modbus TCP',
    modbus_rtu: 'Modbus RTU',
    snmp_v2c: 'SNMP v2c',
    snmp_v3: 'SNMP v3',
    mqtt: 'MQTT',
    http_rest: 'HTTP REST',
    bacnet_ip: 'BACnet/IP',
    opc_ua: 'OPC-UA'
  }
  return map[type] || type
}

function getStatusType(status: string): TagType {
  const map: Record<string, TagType> = {
    connected: 'success',
    disconnected: 'info',
    interrupted: 'danger',
    communication_error: 'danger',
  }
  return map[status] || 'info'
}

function getStatusLabel(status: string): string {
  const map: Record<string, string> = {
    connected: '已连接',
    disconnected: '未连接',
    interrupted: '通信中断',
    communication_error: '通信中断',
  }
  return map[status] || status
}

function commStatusType(status: string): TagType {
  const map: Record<string, TagType> = {
    connected: 'success',
    disconnected: 'warning',
    interrupted: 'danger',
  }
  return map[status] || 'info'
}

function commStatusText(status: string): string {
  const map: Record<string, string> = {
    connected: '已连接',
    disconnected: '已断开',
    interrupted: '通信中断',
  }
  return map[status] || status
}

function getCommStatus(id: number): CommunicationStatusItem | undefined {
  return commStatusMap.value.get(id)
}

function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || seconds <= 0) return '—'
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (hours > 0) return `${hours}小时${minutes}分钟`
  return `${minutes}分钟`
}

onMounted(() => {
  loadDatasources()
  loadCommStatus()
  commStatusTimer = setInterval(loadCommStatus, 30000)
})

onUnmounted(() => {
  if (commStatusTimer) {
    clearInterval(commStatusTimer)
    commStatusTimer = null
  }
})

async function loadCommStatus() {
  try {
    const list = await getCommunicationStatus() as CommunicationStatusItem[]
    const items = Array.isArray(list) ? list : (list as any)?.data ?? []
    const map = new Map<number, CommunicationStatusItem>()
    for (const item of items) {
      map.set(item.id, item)
    }
    commStatusMap.value = map
  } catch (e) {
    console.error('加载通信状态失败', e)
  }
}

async function confirmWriteChange(row: DataSource): Promise<boolean> {
  const action = row.write_enabled ? '关闭' : '开启'
  try {
    await ElMessageBox.confirm(
      `确定${action}数据源 "${row.name}" 的写入权限？${action === '开启' ? '开启后可下发控制命令。' : ''}`,
      '写入权限变更',
      { type: 'warning' }
    )
    return true
  } catch {
    row.write_enabled = !row.write_enabled
    return false
  }
}

async function handleToggleWrite(row: DataSource) {
  try {
    const res = await toggleWritePermission(row.id)
    const data = (res as any)?.data ?? res
    // 兼容后端返回结构
    if (data?.write_enabled !== undefined) {
      row.write_enabled = data.write_enabled
    }
    ElMessage.success(row.write_enabled ? '写入权限已开启' : '写入权限已关闭')
  } catch (e) {
    row.write_enabled = !row.write_enabled
    console.error('切换写入权限失败', e)
  }
}

async function loadDatasources() {
  try {
    const params: Record<string, any> = {
      page: currentPage.value,
      page_size: pageSize.value
    }
    if (filters.protocol_type && filters.protocol_type !== 'ALL') {
      params.protocol_type = filters.protocol_type
    }
    if (filters.status && filters.status !== 'ALL') {
      params.status = filters.status
    }
    if (filters.keyword && filters.keyword.trim()) {
      params.keyword = filters.keyword.trim()
    }
    const result = await getDatasources(params)
    if (Array.isArray(result)) {
      datasources.value = result
      total.value = result.length
    } else {
      datasources.value = result.items || []
      total.value = result.total || 0
    }
  } catch (e) {
    console.error('加载数据源失败', e)
  }
}

function handlePageChange(page: number) {
  currentPage.value = page
  loadDatasources()
}

function handleSizeChange(size: number) {
  pageSize.value = size
  currentPage.value = 1
  loadDatasources()
}

function handleSearch() {
  currentPage.value = 1
  loadDatasources()
}

function resetFilters() {
  filters.protocol_type = 'ALL'
  filters.status = 'ALL'
  filters.keyword = ''
  currentPage.value = 1
  loadDatasources()
}

function handleProtocolChange(val: string) {
  form.connection_config = getDefaultConfig(val)
}

function handleAdd() {
  editMode.value = false
  Object.assign(form, {
    id: 0,
    name: '',
    protocol_type: 'modbus_tcp',
    collection_interval: 5,
    is_enabled: true,
    connection_config: getDefaultConfig('modbus_tcp')
  })
  dialogVisible.value = true
}

function handleEdit(row: DataSource) {
  editMode.value = true
  Object.assign(form, {
    id: row.id,
    name: row.name,
    protocol_type: row.protocol_type,
    collection_interval: row.collection_interval,
    is_enabled: row.is_enabled,
    connection_config: { ...row.connection_config }
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate()
  if (!valid) return

  try {
    const data = {
      name: form.name,
      protocol_type: form.protocol_type,
      collection_interval: form.collection_interval,
      is_enabled: form.is_enabled,
      connection_config: form.connection_config
    }
    if (editMode.value) {
      await updateDatasource(form.id, data)
      ElMessage.success('更新成功')
    } else {
      await createDatasource(data)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadDatasources()
  } catch (e) {
    console.error('操作失败', e)
  }
}

async function handleDelete(id: number) {
  try {
    await deleteDatasource(id)
    ElMessage.success('删除成功')
    loadDatasources()
  } catch (e) {
    console.error('删除失败', e)
  }
}

async function handleToggle(row: DataSource) {
  try {
    await updateDatasource(row.id, { is_enabled: row.is_enabled })
    ElMessage.success(row.is_enabled ? '已启用' : '已禁用')
  } catch (e) {
    row.is_enabled = !row.is_enabled
    console.error('操作失败', e)
  }
}

async function handleTestConnection() {
  testing.value = true
  try {
    const res = await testConnection({
      protocol_type: form.protocol_type,
      connection_config: form.connection_config
    })
    const result = (res as any)?.data ?? res
    if (result.success) {
      ElMessage.success(`连接成功，延迟 ${result.latency_ms}ms`)
    } else {
      ElMessage.error(`连接失败: ${result.message}`)
    }
  } catch (e: any) {
    ElMessage.error('测试连接失败: ' + (e.message || '未知错误'))
  } finally {
    testing.value = false
  }
}

async function handleTestExisting(row: DataSource) {
  try {
    const res = await testExistingConnection(row.id)
    const result = (res as any)?.data ?? res
    if (result.success) {
      ElMessage.success(`${row.name} 连接成功，延迟 ${result.latency_ms}ms`)
    } else {
      ElMessage.error(`${row.name} 连接失败: ${result.message}`)
    }
  } catch (e: any) {
    ElMessage.error('测试连接失败: ' + (e.message || '未知错误'))
  }
}

// ========== 导入点位 ==========

function handleOpenImport(row: DataSource) {
  importDatasourceId.value = row.id
  importFile.value = null
  importReport.value = null
  importDialogVisible.value = true
}

function resetImportState() {
  importFile.value = null
  importReport.value = null
  validating.value = false
  importing.value = false
}

function handleFileChange(uploadFile: UploadFile) {
  importFile.value = uploadFile.raw || null
  importReport.value = null
}

async function handleValidate() {
  if (!importFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  validating.value = true
  try {
    const res = await validatePoints(importDatasourceId.value, importFile.value)
    importReport.value = (res as any)?.data ?? res
  } catch (e: any) {
    ElMessage.error('校验失败: ' + (e.response?.data?.detail || e.message || '未知错误'))
  } finally {
    validating.value = false
  }
}

async function handleImport() {
  if (!importFile.value) return
  importing.value = true
  try {
    const res = await importPoints(importDatasourceId.value, importFile.value)
    const result = (res as any)?.data ?? res
    ElMessage.success(`成功导入 ${result.imported} 个点位`)
    importDialogVisible.value = false
  } catch (e: any) {
    ElMessage.error('导入失败: ' + (e.response?.data?.detail?.message || e.message || '未知错误'))
  } finally {
    importing.value = false
  }
}

async function handleExport() {
  try {
    const blob = await exportReport() as any
    const url = window.URL.createObjectURL(new Blob([blob]))
    const link = document.createElement('a')
    link.href = url
    link.download = `对接报告_${new Date().toISOString().slice(0, 10)}.xlsx`
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('报告导出成功')
  } catch (e) {
    console.error('导出失败', e)
    ElMessage.error('导出失败')
  }
}
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.datasource-page {
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

  .impact-panel {
    padding: 12px 20px;
  }
}
</style>
