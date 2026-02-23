<template>
  <div class="settings-page">
    <el-card shadow="hover">
      <el-tabs v-model="activeTab">
        <!-- 阈值配置 -->
        <el-tab-pane label="阈值配置" name="threshold">
          <div class="tab-header">
            <el-button type="primary" :icon="Plus" @click="handleAddThreshold">新增阈值</el-button>
            <el-button type="success" @click="handleFourLevelConfig">4级阈值配置</el-button>
            <el-button type="warning" @click="handleBatchByDeviceType">按设备类型批量配置</el-button>
          </div>

          <el-form :inline="true" class="filter-form">
            <el-form-item label="点位">
              <el-select v-model="thresholdFilters.point_id" placeholder="全部" clearable filterable style="width: 200px;">
                <el-option
                  v-for="p in pointList"
                  :key="p.id"
                  :label="`${p.point_code} - ${p.point_name}`"
                  :value="p.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="告警级别">
              <el-select v-model="thresholdFilters.alarm_level" placeholder="全部" clearable>
                <el-option label="紧急" value="critical" />
                <el-option label="重要" value="major" />
                <el-option label="一般" value="minor" />
                <el-option label="提示" value="info" />
              </el-select>
            </el-form-item>
            <el-form-item label="设备类型">
              <el-select v-model="thresholdFilters.device_type" placeholder="全部" clearable style="width: 150px;">
                <el-option v-for="dt in deviceTypeOptions" :key="dt.value" :label="dt.label" :value="dt.value" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadThresholds">查询</el-button>
            </el-form-item>
          </el-form>

          <el-table :data="thresholds" stripe border v-loading="thresholdLoading">
            <el-table-column prop="point_code" label="点位编码" width="140" />
            <el-table-column prop="point_name" label="点位名称" width="150" />
            <el-table-column prop="device_type" label="设备类型" width="110">
              <template #default="{ row }">
                {{ deviceTypeText[row.device_type] || row.device_type || '--' }}
              </template>
            </el-table-column>
            <el-table-column prop="threshold_type" label="阈值类型" width="100">
              <template #default="{ row }">
                {{ thresholdTypeText[row.threshold_type] }}
              </template>
            </el-table-column>
            <el-table-column prop="threshold_value" label="阈值" width="100" />
            <el-table-column prop="alarm_level" label="告警级别" width="100">
              <template #default="{ row }">
                <el-tag :type="alarmLevelType[row.alarm_level]" size="small">
                  {{ alarmLevelText[row.alarm_level] }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="alarm_message" label="告警消息" min-width="150" />
            <el-table-column prop="is_enabled" label="状态" width="80">
              <template #default="{ row }">
                <el-switch v-model="row.is_enabled" @change="toggleThreshold(row)" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link @click="handleEditThreshold(row)">编辑</el-button>
                <el-popconfirm title="确定删除？" @confirm="handleDeleteThreshold(row.id)">
                  <template #reference>
                    <el-button type="danger" link>删除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 用户管理（仅管理员可见） -->
        <el-tab-pane v-if="isAdmin" label="用户管理" name="user">
          <UserManagement />
        </el-tab-pane>

        <!-- 操作日志 -->
        <el-tab-pane label="操作日志" name="operation-log">
          <el-form :inline="true" class="filter-form">
            <el-form-item label="时间范围">
              <el-date-picker
                v-model="operationLogFilters.dateRange"
                type="daterange"
                range-separator="至"
                start-placeholder="开始"
                end-placeholder="结束"
                value-format="YYYY-MM-DD"
              />
            </el-form-item>
            <el-form-item label="操作类型">
              <el-select v-model="operationLogFilters.action" placeholder="全部" clearable style="width: 120px;">
                <el-option label="创建" value="create" />
                <el-option label="更新" value="update" />
                <el-option label="删除" value="delete" />
                <el-option label="查询" value="query" />
                <el-option label="导出" value="export" />
              </el-select>
            </el-form-item>
            <el-form-item label="模块">
              <el-select v-model="operationLogFilters.module" placeholder="全部" clearable style="width: 120px;">
                <el-option label="用户" value="user" />
                <el-option label="点位" value="point" />
                <el-option label="设备" value="device" />
                <el-option label="告警" value="alarm" />
                <el-option label="配置" value="config" />
                <el-option label="报表" value="report" />
              </el-select>
            </el-form-item>
            <el-form-item label="关键词">
              <el-input v-model="operationLogFilters.keyword" placeholder="目标名称/备注" clearable style="width: 150px;" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadOperationLogs">查询</el-button>
              <el-button @click="resetOperationLogFilters">重置</el-button>
              <el-button type="success" @click="exportOperationLogs">导出</el-button>
            </el-form-item>
          </el-form>

          <!-- 操作日志表格 -->
          <el-table :data="operationLogs" stripe border v-loading="operationLogLoading">
            <el-table-column prop="created_at" label="时间" width="160" />
            <el-table-column prop="username" label="用户" width="100" />
            <el-table-column prop="action" label="操作" width="90">
              <template #default="{ row }">
                <el-tag :type="actionType[row.action] || 'info'" size="small">
                  {{ actionText[row.action] || row.action }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="module" label="模块" width="90">
              <template #default="{ row }">
                {{ moduleText[row.module] || row.module }}
              </template>
            </el-table-column>
            <el-table-column prop="target_name" label="目标名称" min-width="150" show-overflow-tooltip />
            <el-table-column prop="ip_address" label="IP地址" width="130" />
            <el-table-column prop="response_code" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.response_code === 200 ? 'success' : 'danger'" size="small">
                  {{ row.response_code }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="remark" label="备注" min-width="150" show-overflow-tooltip />
          </el-table>

          <el-pagination
            v-model:current-page="operationLogPagination.page"
            v-model:page-size="operationLogPagination.page_size"
            :total="operationLogPagination.total"
            :page-sizes="[20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            style="margin-top: 20px; justify-content: flex-end;"
            @size-change="loadOperationLogs"
            @current-change="loadOperationLogs"
          />
        </el-tab-pane>

        <!-- 系统日志 -->
        <el-tab-pane label="系统日志" name="system-log">
          <el-form :inline="true" class="filter-form">
            <el-form-item label="时间范围">
              <el-date-picker
                v-model="systemLogFilters.dateRange"
                type="daterange"
                range-separator="至"
                start-placeholder="开始"
                end-placeholder="结束"
                value-format="YYYY-MM-DD"
              />
            </el-form-item>
            <el-form-item label="日志级别">
              <el-select v-model="systemLogFilters.log_level" placeholder="全部" clearable style="width: 120px;">
                <el-option label="DEBUG" value="debug" />
                <el-option label="INFO" value="info" />
                <el-option label="WARNING" value="warning" />
                <el-option label="ERROR" value="error" />
                <el-option label="FATAL" value="fatal" />
              </el-select>
            </el-form-item>
            <el-form-item label="模块">
              <el-select v-model="systemLogFilters.module" placeholder="全部" clearable style="width: 120px;">
                <el-option label="API" value="api" />
                <el-option label="数据库" value="database" />
                <el-option label="任务调度" value="scheduler" />
                <el-option label="WebSocket" value="websocket" />
                <el-option label="缓存" value="cache" />
              </el-select>
            </el-form-item>
            <el-form-item label="关键词">
              <el-input v-model="systemLogFilters.keyword" placeholder="消息内容" clearable style="width: 150px;" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadSystemLogs">查询</el-button>
              <el-button @click="resetSystemLogFilters">重置</el-button>
              <el-button type="success" @click="exportSystemLogs">导出</el-button>
            </el-form-item>
          </el-form>

          <!-- 系统日志表格 -->
          <el-table :data="systemLogs" stripe border v-loading="systemLogLoading">
            <el-table-column prop="created_at" label="时间" width="160" />
            <el-table-column prop="log_level" label="级别" width="90">
              <template #default="{ row }">
                <el-tag :type="logLevelType[row.log_level]" size="small">
                  {{ row.log_level?.toUpperCase() }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="module" label="模块" width="120" />
            <el-table-column prop="message" label="消息" min-width="300" show-overflow-tooltip />
            <el-table-column prop="exception" label="异常信息" min-width="200" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.exception" class="error-text">{{ row.exception }}</span>
                <span v-else>-</span>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination
            v-model:current-page="systemLogPagination.page"
            v-model:page-size="systemLogPagination.page_size"
            :total="systemLogPagination.total"
            :page-sizes="[20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            style="margin-top: 20px; justify-content: flex-end;"
            @size-change="loadSystemLogs"
            @current-change="loadSystemLogs"
          />
        </el-tab-pane>

        <!-- 授权信息 -->
        <el-tab-pane label="授权信息" name="license">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="授权类型">标准版</el-descriptions-item>
            <el-descriptions-item label="最大点位数">{{ licenseInfo.max_points }}</el-descriptions-item>
            <el-descriptions-item label="已用点位">{{ licenseInfo.used_points }}</el-descriptions-item>
            <el-descriptions-item label="剩余点位">{{ licenseInfo.max_points - licenseInfo.used_points }}</el-descriptions-item>
            <el-descriptions-item label="授权状态">
              <el-tag type="success">有效</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="到期时间">永久授权</el-descriptions-item>
          </el-descriptions>

          <el-divider />

          <el-descriptions title="系统信息" :column="2" border>
            <el-descriptions-item label="系统名称">{{ systemInfo.app_name }}</el-descriptions-item>
            <el-descriptions-item label="系统版本">{{ systemInfo.app_version }}</el-descriptions-item>
            <el-descriptions-item label="数据库">SQLite</el-descriptions-item>
            <el-descriptions-item label="运行时间">{{ systemInfo.uptime }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 阈值编辑对话框 -->
    <el-dialog append-to-body v-model="thresholdDialogVisible" :title="thresholdEditMode ? '编辑阈值' : '新增阈值'" width="500px">
      <el-form ref="thresholdFormRef" :model="thresholdForm" :rules="thresholdRules" label-width="100px">
        <el-form-item label="选择点位" prop="point_id">
          <el-select v-model="thresholdForm.point_id" filterable :disabled="thresholdEditMode" style="width: 100%;">
            <el-option
              v-for="p in pointList"
              :key="p.id"
              :label="`${p.point_code} - ${p.point_name}`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="阈值类型" prop="threshold_type">
          <el-select v-model="thresholdForm.threshold_type" style="width: 100%;">
            <el-option label="高高限" value="high_high" />
            <el-option label="高限" value="high" />
            <el-option label="低限" value="low" />
            <el-option label="低低限" value="low_low" />
          </el-select>
        </el-form-item>
        <el-form-item label="阈值" prop="threshold_value">
          <el-input-number v-model="thresholdForm.threshold_value" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="告警级别" prop="alarm_level">
          <el-select v-model="thresholdForm.alarm_level" style="width: 100%;">
            <el-option label="紧急" value="critical" />
            <el-option label="重要" value="major" />
            <el-option label="一般" value="minor" />
            <el-option label="提示" value="info" />
          </el-select>
        </el-form-item>
        <el-form-item label="告警消息" prop="alarm_message">
          <el-input v-model="thresholdForm.alarm_message" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="thresholdDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitThreshold">确定</el-button>
      </template>
    </el-dialog>

    <!-- 4级阈值配置对话框 -->
    <el-dialog append-to-body v-model="fourLevelDialogVisible" title="4级阈值配置" width="720px">
      <el-form :model="fourLevelForm" label-width="100px">
        <el-form-item label="选择点位" required>
          <el-select v-model="fourLevelForm.point_id" filterable placeholder="请选择AI点位"
            style="width: 100%;" @change="loadExistingThresholds">
            <el-option v-for="p in aiPointList" :key="p.id"
              :label="`${p.point_code} - ${p.point_name}`" :value="p.id" />
          </el-select>
        </el-form-item>

        <el-divider content-position="left">阈值配置</el-divider>

        <el-table :data="fourLevelRows" border size="small" style="margin-bottom: 16px;">
          <el-table-column prop="levelLabel" label="告警级别" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="alarmLevelType[row.alarmLevel]" size="small">{{ row.levelLabel }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="typeLabel" label="阈值类型" width="90" align="center" />
          <el-table-column label="阈值" width="150">
            <template #default="{ row }">
              <el-input-number v-model="row.value" :precision="2" size="small" controls-position="right" style="width: 120px;" />
            </template>
          </el-table-column>
          <el-table-column label="告警消息" min-width="180">
            <template #default="{ row }">
              <el-input v-model="row.message" size="small" placeholder="留空自动生成" />
            </template>
          </el-table-column>
          <el-table-column label="启用" width="70" align="center">
            <template #default="{ row }">
              <el-switch v-model="row.enabled" size="small" />
            </template>
          </el-table-column>
        </el-table>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="延迟触发">
              <el-input-number v-model="fourLevelForm.delay_seconds" :min="0" :max="300" size="small" />
              <span style="margin-left: 8px; color: var(--text-secondary); font-size: 12px;">秒</span>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="死区(回差)">
              <el-input-number v-model="fourLevelForm.dead_band" :min="0" :precision="2" size="small" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="fourLevelDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitFourLevel">确定</el-button>
      </template>
    </el-dialog>

    <!-- 按设备类型批量配置对话框 -->
    <el-dialog append-to-body v-model="batchDeviceTypeDialogVisible" title="按设备类型批量配置阈值" width="720px">
      <el-form :model="batchDeviceTypeForm" label-width="100px">
        <el-form-item label="设备类型" required>
          <el-select v-model="batchDeviceTypeForm.device_type" placeholder="请选择设备类型"
            style="width: 100%;" @change="onDeviceTypeChange">
            <el-option v-for="dt in deviceTypeOptions" :key="dt.value" :label="dt.label" :value="dt.value" />
          </el-select>
        </el-form-item>
        <el-alert v-if="batchDeviceTypeForm.device_type" :title="`该设备类型下共 ${batchDeviceTypePointCount} 个 AI 点位`"
          type="info" :closable="false" show-icon style="margin-bottom: 16px;" />

        <el-divider content-position="left">阈值模板</el-divider>

        <el-table :data="batchDeviceTypeRows" border size="small" style="margin-bottom: 16px;">
          <el-table-column prop="levelLabel" label="告警级别" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="alarmLevelType[row.alarmLevel]" size="small">{{ row.levelLabel }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="typeLabel" label="阈值类型" width="90" align="center" />
          <el-table-column label="阈值" width="150">
            <template #default="{ row }">
              <el-input-number v-model="row.value" :precision="2" size="small" controls-position="right" style="width: 120px;" />
            </template>
          </el-table-column>
          <el-table-column label="告警消息" min-width="180">
            <template #default="{ row }">
              <el-input v-model="row.message" size="small" placeholder="留空自动生成" />
            </template>
          </el-table-column>
          <el-table-column label="启用" width="70" align="center">
            <template #default="{ row }">
              <el-switch v-model="row.enabled" size="small" />
            </template>
          </el-table-column>
        </el-table>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="延迟触发">
              <el-input-number v-model="batchDeviceTypeForm.delay_seconds" :min="0" :max="300" size="small" />
              <span style="margin-left: 8px; color: var(--text-secondary); font-size: 12px;">秒</span>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="死区(回差)">
              <el-input-number v-model="batchDeviceTypeForm.dead_band" :min="0" :precision="2" size="small" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="batchDeviceTypeDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitBatchByDeviceType" :disabled="batchDeviceTypePointCount === 0">确定</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getPointList, type PointInfo } from '@/api/modules/point'
import {
  getThresholdList, createThreshold, updateThreshold, deleteThreshold,
  getPointThresholds, setFourLevelThresholds, batchSetByDeviceType,
  type ThresholdInfo, type FourLevelThresholdItem
} from '@/api/modules/threshold'
import {
  getOperationLogs, getSystemLogs, exportLogs as apiExportLogs,
  type OperationLog, type SystemLog
} from '@/api/modules/log'
import { useUserStore } from '@/stores/user'
import UserManagement from './UserManagement.vue'

const userStore = useUserStore()
const isAdmin = computed(() => userStore.isAdmin)

const activeTab = ref('threshold')

// 点位列表
const pointList = ref<PointInfo[]>([])

// ===== 阈值配置 =====
const thresholds = ref<ThresholdInfo[]>([])
const thresholdLoading = ref(false)
const thresholdDialogVisible = ref(false)
const thresholdEditMode = ref(false)
const thresholdFormRef = ref()

const thresholdFilters = reactive({
  point_id: null as number | null,
  alarm_level: '',
  device_type: ''
})

type ThresholdType = 'high' | 'low' | 'high_high' | 'low_low' | 'equal' | 'change'
type AlarmLevel = 'critical' | 'major' | 'minor' | 'info'

const thresholdForm = reactive({
  id: 0,
  point_id: null as number | null,
  threshold_type: 'high' as ThresholdType,
  threshold_value: 0,
  alarm_level: 'major' as AlarmLevel,
  alarm_message: ''
})

const thresholdRules = {
  point_id: [{ required: true, message: '请选择点位', trigger: 'change' }],
  threshold_type: [{ required: true, message: '请选择阈值类型', trigger: 'change' }],
  threshold_value: [{ required: true, message: '请输入阈值', trigger: 'blur' }]
}

// ===== 4级阈值配置 =====
const fourLevelDialogVisible = ref(false)
const fourLevelForm = reactive({
  point_id: null as number | null,
  delay_seconds: 0,
  dead_band: 0
})
const fourLevelRows = ref([
  { key: 'high_high', levelLabel: '紧急', typeLabel: '高高限', alarmLevel: 'critical' as string, value: null as number | null, message: '', enabled: true },
  { key: 'high', levelLabel: '重要', typeLabel: '高限', alarmLevel: 'major' as string, value: null as number | null, message: '', enabled: true },
  { key: 'low', levelLabel: '次要', typeLabel: '低限', alarmLevel: 'minor' as string, value: null as number | null, message: '', enabled: true },
  { key: 'low_low', levelLabel: '提示', typeLabel: '低低限', alarmLevel: 'info' as string, value: null as number | null, message: '', enabled: true },
])

// AI点位列表（仅AI类型）
const aiPointList = computed(() => pointList.value.filter(p => p.point_type === 'AI'))

// ===== 按设备类型批量配置 =====
const batchDeviceTypeDialogVisible = ref(false)
const batchDeviceTypeForm = reactive({
  device_type: '',
  delay_seconds: 0,
  dead_band: 0
})
const batchDeviceTypeRows = ref([
  { key: 'high_high', levelLabel: '紧急', typeLabel: '高高限', alarmLevel: 'critical' as string, value: null as number | null, message: '', enabled: true },
  { key: 'high', levelLabel: '重要', typeLabel: '高限', alarmLevel: 'major' as string, value: null as number | null, message: '', enabled: true },
  { key: 'low', levelLabel: '次要', typeLabel: '低限', alarmLevel: 'minor' as string, value: null as number | null, message: '', enabled: true },
  { key: 'low_low', levelLabel: '提示', typeLabel: '低低限', alarmLevel: 'info' as string, value: null as number | null, message: '', enabled: true },
])
const batchDeviceTypePointCount = ref(0)

const thresholdTypeText: Record<string, string> = {
  high_high: '高高限',
  high: '高限',
  low: '低限',
  low_low: '低低限',
  equal: '等于',
  change: '变化'
}

const alarmLevelText: Record<string, string> = {
  critical: '紧急',
  major: '重要',
  minor: '一般',
  info: '提示'
}

type TagType = 'success' | 'warning' | 'danger' | 'info' | 'primary'

const alarmLevelType: Record<string, TagType> = {
  critical: 'danger',
  major: 'warning',
  minor: 'primary',
  info: 'info'
}

const deviceTypeOptions = [
  { label: '温湿度传感器', value: 'TH' },
  { label: 'UPS', value: 'UPS' },
  { label: 'PDU', value: 'PDU' },
  { label: '精密空调', value: 'AC' },
  { label: '门禁', value: 'DOOR' },
  { label: '烟感', value: 'SMOKE' },
  { label: '漏水', value: 'WATER' },
  { label: '红外', value: 'IR' },
  { label: '风机', value: 'FAN' },
  { label: '照明', value: 'LIGHT' },
]

const deviceTypeText: Record<string, string> = {
  TH: '温湿度', UPS: 'UPS', PDU: 'PDU', AC: '精密空调',
  DOOR: '门禁', SMOKE: '烟感', WATER: '漏水', IR: '红外',
  FAN: '风机', LIGHT: '照明'
}

// ===== 操作日志 =====
const operationLogs = ref<OperationLog[]>([])
const operationLogLoading = ref(false)

const operationLogFilters = reactive({
  dateRange: [] as string[],
  action: '',
  module: '',
  keyword: ''
})

const operationLogPagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

// 操作类型映射
const actionType: Record<string, TagType> = {
  create: 'success',
  update: 'primary',
  delete: 'danger',
  query: 'info',
  export: 'warning'
}

const actionText: Record<string, string> = {
  create: '创建',
  update: '更新',
  delete: '删除',
  query: '查询',
  export: '导出'
}

const moduleText: Record<string, string> = {
  user: '用户',
  point: '点位',
  device: '设备',
  alarm: '告警',
  config: '配置',
  report: '报表'
}

// ===== 系统日志 =====
const systemLogs = ref<SystemLog[]>([])
const systemLogLoading = ref(false)

const systemLogFilters = reactive({
  dateRange: [] as string[],
  log_level: '',
  module: '',
  keyword: ''
})

const systemLogPagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const logLevelType: Record<string, TagType> = {
  debug: 'info',
  info: 'success',
  warning: 'warning',
  error: 'danger',
  fatal: 'danger'
}

// ===== 授权信息 =====
const licenseInfo = reactive({
  max_points: 100,
  used_points: 0
})

const systemInfo = reactive({
  app_name: '算力中心智能监控系统',
  app_version: '2.0.0',
  uptime: '-'
})

// ===== 生命周期 =====
onMounted(async () => {
  await loadPoints()
  loadThresholds()
  loadSystemInfo()
})

watch(activeTab, (val) => {
  if (val === 'operation-log') {
    loadOperationLogs()
  } else if (val === 'system-log') {
    loadSystemLogs()
  }
})

// ===== 通用方法 =====
async function loadPoints() {
  try {
    const result = await getPointList({})
    pointList.value = result.items
  } catch (e) {
    console.error('加载点位失败', e)
  }
}

async function loadSystemInfo() {
  try {
    // 从统计API获取点位总数
    const { getSystemOverview } = await import('@/api/modules/statistics')
    const overview = await getSystemOverview()
    licenseInfo.used_points = overview.points?.total || 0

    // 从配置API获取授权信息
    const { getLicenseInfo: getLicense } = await import('@/api/modules/config')
    const license = await getLicense()
    licenseInfo.max_points = license.max_points || 100
  } catch (e) {
    console.error('加载系统信息失败', e)
  }
}

// ===== 阈值方法 =====
async function loadThresholds() {
  thresholdLoading.value = true
  try {
    const params: any = { page: 1, page_size: 100 }
    if (thresholdFilters.point_id) params.point_id = thresholdFilters.point_id
    if (thresholdFilters.alarm_level) params.alarm_level = thresholdFilters.alarm_level
    if (thresholdFilters.device_type) params.device_type = thresholdFilters.device_type
    const res = await getThresholdList(params)
    thresholds.value = res.items
  } catch (e) {
    console.error('加载阈值失败', e)
  } finally {
    thresholdLoading.value = false
  }
}

function handleAddThreshold() {
  thresholdEditMode.value = false
  Object.assign(thresholdForm, {
    id: 0,
    point_id: null,
    threshold_type: 'high',
    threshold_value: 0,
    alarm_level: 'major',
    alarm_message: ''
  })
  thresholdDialogVisible.value = true
}

function handleEditThreshold(row: ThresholdInfo) {
  thresholdEditMode.value = true
  Object.assign(thresholdForm, row)
  thresholdDialogVisible.value = true
}

async function submitThreshold() {
  const valid = await thresholdFormRef.value?.validate()
  if (!valid) return

  try {
    if (thresholdEditMode.value) {
      await updateThreshold(thresholdForm.id, thresholdForm)
      ElMessage.success('更新成功')
    } else {
      await createThreshold(thresholdForm as any)
      ElMessage.success('创建成功')
    }
    thresholdDialogVisible.value = false
    loadThresholds()
  } catch (e) {
    console.error('操作失败', e)
  }
}

async function toggleThreshold(row: ThresholdInfo) {
  try {
    await updateThreshold(row.id, { is_enabled: row.is_enabled })
    ElMessage.success(row.is_enabled ? '已启用' : '已禁用')
  } catch (e) {
    row.is_enabled = !row.is_enabled
    console.error('操作失败', e)
  }
}

async function handleDeleteThreshold(id: number) {
  try {
    await deleteThreshold(id)
    ElMessage.success('删除成功')
    loadThresholds()
  } catch (e) {
    console.error('删除失败', e)
  }
}

// ===== 4级阈值配置方法 =====
function handleFourLevelConfig() {
  fourLevelForm.point_id = null
  fourLevelForm.delay_seconds = 0
  fourLevelForm.dead_band = 0
  fourLevelRows.value.forEach(row => {
    row.value = null
    row.message = ''
    row.enabled = true
  })
  fourLevelDialogVisible.value = true
}

async function loadExistingThresholds(pointId: number) {
  if (!pointId) return
  try {
    const existing = await getPointThresholds(pointId)
    // 回填已有阈值
    for (const t of existing) {
      const row = fourLevelRows.value.find(r => r.key === t.threshold_type)
      if (row) {
        row.value = t.threshold_value
        row.message = t.alarm_message || ''
        row.enabled = t.is_enabled
      }
    }
    if (existing.length > 0) {
      fourLevelForm.delay_seconds = existing[0].delay_seconds || 0
      fourLevelForm.dead_band = existing[0].dead_band || 0
    }
  } catch (e) {
    console.error('加载现有阈值失败', e)
  }
}

async function submitFourLevel() {
  if (!fourLevelForm.point_id) {
    ElMessage.warning('请选择点位')
    return
  }

  const data: Record<string, any> = {
    delay_seconds: fourLevelForm.delay_seconds,
    dead_band: fourLevelForm.dead_band
  }
  for (const row of fourLevelRows.value) {
    data[row.key] = {
      value: row.value,
      message: row.message || undefined,
      enabled: row.enabled
    }
  }

  try {
    await setFourLevelThresholds(fourLevelForm.point_id, data as any)
    ElMessage.success('4级阈值配置成功')
    fourLevelDialogVisible.value = false
    loadThresholds()
  } catch (e) {
    console.error('配置失败', e)
    ElMessage.error('配置失败')
  }
}

// ===== 按设备类型批量配置方法 =====
function handleBatchByDeviceType() {
  batchDeviceTypeForm.device_type = ''
  batchDeviceTypeForm.delay_seconds = 0
  batchDeviceTypeForm.dead_band = 0
  batchDeviceTypeRows.value.forEach(row => {
    row.value = null
    row.message = ''
    row.enabled = true
  })
  batchDeviceTypePointCount.value = 0
  batchDeviceTypeDialogVisible.value = true
}

async function onDeviceTypeChange(deviceType: string) {
  if (!deviceType) {
    batchDeviceTypePointCount.value = 0
    return
  }
  try {
    const result = await getPointList({ device_type: deviceType, point_type: 'AI', page_size: 1 } as any)
    batchDeviceTypePointCount.value = result.total || 0
  } catch (e) {
    batchDeviceTypePointCount.value = 0
  }
}

async function submitBatchByDeviceType() {
  if (!batchDeviceTypeForm.device_type) {
    ElMessage.warning('请选择设备类型')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定为设备类型「${deviceTypeText[batchDeviceTypeForm.device_type] || batchDeviceTypeForm.device_type}」下的 ${batchDeviceTypePointCount.value} 个 AI 点位批量设置阈值？`,
      '批量配置确认',
      { type: 'warning' }
    )
  } catch {
    return
  }

  const thresholds: Record<string, any> = {
    delay_seconds: batchDeviceTypeForm.delay_seconds,
    dead_band: batchDeviceTypeForm.dead_band
  }
  for (const row of batchDeviceTypeRows.value) {
    thresholds[row.key] = {
      value: row.value,
      message: row.message || undefined,
      enabled: row.enabled
    }
  }

  try {
    const result = await batchSetByDeviceType({
      device_type: batchDeviceTypeForm.device_type,
      thresholds: thresholds as any
    })
    ElMessage.success(`批量配置完成：成功 ${result.success_count} 个，失败 ${result.error_count} 个`)
    batchDeviceTypeDialogVisible.value = false
    loadThresholds()
  } catch (e) {
    console.error('批量配置失败', e)
    ElMessage.error('批量配置失败')
  }
}

// ===== 操作日志方法 =====
async function loadOperationLogs() {
  operationLogLoading.value = true
  try {
    const params: any = {
      page: operationLogPagination.page,
      page_size: operationLogPagination.page_size
    }
    if (operationLogFilters.dateRange && operationLogFilters.dateRange.length === 2) {
      params.start_time = operationLogFilters.dateRange[0] + 'T00:00:00'
      params.end_time = operationLogFilters.dateRange[1] + 'T23:59:59'
    }
    if (operationLogFilters.action) {
      params.action = operationLogFilters.action
    }
    if (operationLogFilters.module) {
      params.module = operationLogFilters.module
    }
    if (operationLogFilters.keyword) {
      params.keyword = operationLogFilters.keyword
    }

    const res = await getOperationLogs(params)
    operationLogs.value = res.items
    operationLogPagination.total = res.total
  } catch (e) {
    console.error('加载操作日志失败', e)
    ElMessage.error('加载操作日志失败')
  } finally {
    operationLogLoading.value = false
  }
}

function resetOperationLogFilters() {
  operationLogFilters.dateRange = []
  operationLogFilters.action = ''
  operationLogFilters.module = ''
  operationLogFilters.keyword = ''
  operationLogPagination.page = 1
  loadOperationLogs()
}

async function exportOperationLogs() {
  try {
    const params: any = {
      log_type: 'operation',
      format: 'csv'
    }
    if (operationLogFilters.dateRange && operationLogFilters.dateRange.length === 2) {
      params.start_time = operationLogFilters.dateRange[0]
      params.end_time = operationLogFilters.dateRange[1]
    }

    const blob = await apiExportLogs(params)
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `operation_logs_${Date.now()}.csv`
    a.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (e) {
    console.error('导出失败', e)
    ElMessage.error('导出失败')
  }
}

// ===== 系统日志方法 =====
async function loadSystemLogs() {
  systemLogLoading.value = true
  try {
    const params: any = {
      page: systemLogPagination.page,
      page_size: systemLogPagination.page_size
    }
    if (systemLogFilters.dateRange && systemLogFilters.dateRange.length === 2) {
      params.start_time = systemLogFilters.dateRange[0] + 'T00:00:00'
      params.end_time = systemLogFilters.dateRange[1] + 'T23:59:59'
    }
    if (systemLogFilters.log_level) {
      params.log_level = systemLogFilters.log_level
    }
    if (systemLogFilters.module) {
      params.module = systemLogFilters.module
    }
    if (systemLogFilters.keyword) {
      params.keyword = systemLogFilters.keyword
    }

    const res = await getSystemLogs(params)
    systemLogs.value = res.items
    systemLogPagination.total = res.total
  } catch (e) {
    console.error('加载系统日志失败', e)
    ElMessage.error('加载系统日志失败')
  } finally {
    systemLogLoading.value = false
  }
}

function resetSystemLogFilters() {
  systemLogFilters.dateRange = []
  systemLogFilters.log_level = ''
  systemLogFilters.module = ''
  systemLogFilters.keyword = ''
  systemLogPagination.page = 1
  loadSystemLogs()
}

async function exportSystemLogs() {
  try {
    const params: any = {
      log_type: 'system',
      format: 'csv'
    }
    if (systemLogFilters.dateRange && systemLogFilters.dateRange.length === 2) {
      params.start_time = systemLogFilters.dateRange[0]
      params.end_time = systemLogFilters.dateRange[1]
    }

    const blob = await apiExportLogs(params)
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `system_logs_${Date.now()}.csv`
    a.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (e) {
    console.error('导出失败', e)
    ElMessage.error('导出失败')
  }
}
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.settings-page {
  @include page-list;
  // 主卡片样式 - 确保深色背景
  :deep(.el-card) {
    background-color: var(--bg-card-solid);

    .el-card__body {
      background-color: var(--bg-card-solid);
      padding: 0;
    }
  }

  // Tabs 样式 - 核心修复
  :deep(.el-tabs) {
    .el-tabs__header {
      background-color: var(--bg-tertiary);
      padding: 0 20px;
      margin: 0;
      border-bottom: 1px solid var(--border-color);
    }

    .el-tabs__item {
      color: var(--text-secondary);
      font-size: 14px;
      padding: 0 20px;
      height: 50px;
      line-height: 50px;

      &:hover {
        color: var(--primary-color);
      }

      &.is-active {
        color: var(--primary-color);
        font-weight: 500;
      }
    }

    .el-tabs__active-bar {
      background-color: var(--primary-color);
    }

    .el-tabs__nav-wrap::after {
      background-color: transparent;
    }

    // 内容区域 - 关键：设置深色背景
    .el-tabs__content {
      background-color: var(--bg-card-solid);
      padding: 20px;
    }
  }

  .tab-header {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 16px;
  }

  .filter-form {
    margin-bottom: 16px;

    // 表单标签颜色
    :deep(.el-form-item__label) {
      color: var(--text-regular);
    }
  }

  // 表格样式增强
  :deep(.el-table) {
    background-color: transparent;

    th.el-table__cell {
      background-color: var(--bg-tertiary);
      color: var(--text-primary);
      border-bottom-color: var(--border-color);
    }

    td.el-table__cell {
      border-bottom-color: var(--border-color);
    }

    tr {
      background-color: transparent;

      &:hover > td.el-table__cell {
        background-color: var(--bg-hover);
      }
    }

    // 斑马纹
    .el-table__row--striped td.el-table__cell {
      background-color: rgba(255, 255, 255, 0.02);
    }
  }

  // 确保 el-descriptions 在设置页面中正确显示
  :deep(.el-descriptions) {
    .el-descriptions__title {
      color: var(--text-primary);
    }

    .el-descriptions__label {
      color: var(--text-secondary);
      background-color: var(--bg-tertiary);
    }

    .el-descriptions__content {
      color: var(--text-regular);
      background-color: var(--bg-card-solid);
    }

    .el-descriptions__cell {
      border-color: var(--border-color);
    }
  }

  // 确保 el-divider 正确显示
  :deep(.el-divider) {
    border-color: var(--border-color);

    .el-divider__text {
      color: var(--text-secondary);
      background-color: var(--bg-card-solid);
    }
  }

  // 确保 el-alert info 样式正确
  :deep(.el-alert--info) {
    background-color: rgba(24, 144, 255, 0.1);
    border-color: rgba(24, 144, 255, 0.2);

    .el-alert__title {
      color: var(--primary-color);
    }

    .el-alert__description {
      color: var(--text-secondary);
    }
  }

  // 分页器样式
  :deep(.el-pagination) {
    background-color: transparent;

    .el-pager li {
      background-color: var(--bg-tertiary);
      color: var(--text-secondary);

      &.is-active {
        background-color: var(--primary-color);
        color: #fff;
      }
    }

    button {
      background-color: var(--bg-tertiary);
      color: var(--text-secondary);
    }
  }

  // 开关样式
  :deep(.el-switch) {
    .el-switch__core {
      background-color: var(--bg-tertiary);
      border-color: var(--border-color);
    }

    &.is-checked .el-switch__core {
      background-color: var(--primary-color);
      border-color: var(--primary-color);
    }
  }
}
</style>
