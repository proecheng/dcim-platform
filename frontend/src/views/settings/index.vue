<template>
  <div class="settings-page">
    <el-card shadow="hover">
      <el-tabs v-model="activeTab">
        <!-- 阈值配置 -->
        <el-tab-pane label="阈值配置" name="threshold">
          <div class="tab-header">
            <el-button type="primary" :icon="Plus" @click="handleAddThreshold">新增阈值</el-button>
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
            <el-form-item>
              <el-button type="primary" @click="loadThresholds">查询</el-button>
            </el-form-item>
          </el-form>

          <el-table :data="thresholds" stripe border v-loading="thresholdLoading">
            <el-table-column prop="point_code" label="点位编码" width="140" />
            <el-table-column prop="point_name" label="点位名称" width="150" />
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

        <!-- 用户管理 -->
        <el-tab-pane label="用户管理" name="user">
          <div class="tab-header">
            <el-button type="primary" :icon="Plus" @click="handleAddUser">新增用户</el-button>
          </div>

          <el-table :data="users" stripe border v-loading="userLoading">
            <el-table-column prop="username" label="用户名" width="120" />
            <el-table-column prop="real_name" label="姓名" width="100" />
            <el-table-column prop="email" label="邮箱" width="180" />
            <el-table-column prop="phone" label="电话" width="130" />
            <el-table-column prop="role" label="角色" width="100">
              <template #default="{ row }">
                <el-tag :type="roleType[row.role]" size="small">
                  {{ roleText[row.role] }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="department" label="部门" width="120" />
            <el-table-column prop="is_active" label="状态" width="80">
              <template #default="{ row }">
                <el-switch v-model="row.is_active" @change="toggleUserStatus(row)" />
              </template>
            </el-table-column>
            <el-table-column prop="last_login_at" label="最后登录" width="160" />
            <el-table-column label="操作" width="180" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link @click="handleEditUser(row)">编辑</el-button>
                <el-button type="warning" link @click="handleResetPwd(row)">重置密码</el-button>
                <el-popconfirm v-if="row.username !== 'admin'" title="确定删除？" @confirm="handleDeleteUser(row.id)">
                  <template #reference>
                    <el-button type="danger" link>删除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 系统日志 -->
        <el-tab-pane label="系统日志" name="log">
          <el-form :inline="true" class="filter-form">
            <el-form-item label="日志类型">
              <el-select v-model="logFilters.log_type" style="width: 120px;">
                <el-option label="操作日志" value="operation" />
                <el-option label="系统日志" value="system" />
              </el-select>
            </el-form-item>
            <el-form-item label="时间范围">
              <el-date-picker
                v-model="logFilters.dateRange"
                type="daterange"
                range-separator="至"
                start-placeholder="开始"
                end-placeholder="结束"
                value-format="YYYY-MM-DD"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadLogs">查询</el-button>
              <el-button type="success" @click="exportLogs">导出</el-button>
            </el-form-item>
          </el-form>

          <!-- 操作日志表格 -->
          <el-table v-if="logFilters.log_type === 'operation'" :data="operationLogs" stripe border v-loading="logLoading">
            <el-table-column prop="created_at" label="时间" width="160" />
            <el-table-column prop="username" label="用户" width="100" />
            <el-table-column prop="module" label="模块" width="100" />
            <el-table-column prop="action" label="操作" width="100" />
            <el-table-column prop="target_name" label="目标" width="150" />
            <el-table-column prop="ip_address" label="IP地址" width="130" />
            <el-table-column prop="response_code" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.response_code === 200 ? 'success' : 'danger'" size="small">
                  {{ row.response_code }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="remark" label="备注" min-width="150" />
          </el-table>

          <!-- 系统日志表格 -->
          <el-table v-else :data="systemLogs" stripe border v-loading="logLoading">
            <el-table-column prop="created_at" label="时间" width="160" />
            <el-table-column prop="log_level" label="级别" width="80">
              <template #default="{ row }">
                <el-tag :type="logLevelType[row.log_level]" size="small">
                  {{ row.log_level }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="module" label="模块" width="120" />
            <el-table-column prop="message" label="消息" min-width="300" />
          </el-table>

          <el-pagination
            v-model:current-page="logPagination.page"
            v-model:page-size="logPagination.page_size"
            :total="logPagination.total"
            :page-sizes="[20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            style="margin-top: 20px; justify-content: flex-end;"
            @size-change="loadLogs"
            @current-change="loadLogs"
          />
        </el-tab-pane>

        <!-- 电价配置 -->
        <el-tab-pane label="电价配置" name="pricing">
          <div class="tab-header">
            <el-button type="primary" :icon="Plus" @click="handleAddPricing">新增电价</el-button>
          </div>

          <el-table :data="pricings" stripe border v-loading="pricingLoading">
            <el-table-column prop="pricing_name" label="电价名称" width="150" />
            <el-table-column prop="period_type" label="时段类型" width="100">
              <template #default="{ row }">
                <el-tag :type="periodTypeTag[row.period_type]" size="small">
                  {{ periodTypeText[row.period_type] }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="start_time" label="开始时间" width="100" />
            <el-table-column prop="end_time" label="结束时间" width="100" />
            <el-table-column prop="price" label="单价 (元/kWh)" width="120">
              <template #default="{ row }">
                {{ row.price.toFixed(2) }}
              </template>
            </el-table-column>
            <el-table-column prop="effective_date" label="生效日期" width="110" />
            <el-table-column prop="is_enabled" label="状态" width="80">
              <template #default="{ row }">
                <el-switch v-model="row.is_enabled" @change="togglePricing(row)" />
              </template>
            </el-table-column>
            <el-table-column prop="remark" label="备注" min-width="150" />
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link @click="handleEditPricing(row)">编辑</el-button>
                <el-popconfirm title="确定删除？" @confirm="handleDeletePricing(row.id)">
                  <template #reference>
                    <el-button type="danger" link>删除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>

          <div class="pricing-tips">
            <el-alert
              title="说明"
              type="info"
              :closable="false"
              show-icon
            >
              <ul>
                <li>尖峰电价：用电最高峰时段，电价最高（如午高峰、晚高峰核心时段）</li>
                <li>高峰电价：用电高峰时段，电价较高（如白天工作时段）</li>
                <li>平段电价：正常用电时段，标准电价</li>
                <li>低谷电价：用电低谷时段，电价较低（如深夜时段）</li>
                <li>深谷电价：用电最低谷时段，电价最低（如凌晨时段）</li>
                <li>时段不能重叠，系统会自动检查时间冲突</li>
              </ul>
            </el-alert>
          </div>
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
    <el-dialog v-model="thresholdDialogVisible" :title="thresholdEditMode ? '编辑阈值' : '新增阈值'" width="500px">
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

    <!-- 用户编辑对话框 -->
    <el-dialog v-model="userDialogVisible" :title="userEditMode ? '编辑用户' : '新增用户'" width="500px">
      <el-form ref="userFormRef" :model="userForm" :rules="userRules" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="userForm.username" :disabled="userEditMode" />
        </el-form-item>
        <el-form-item v-if="!userEditMode" label="密码" prop="password">
          <el-input v-model="userForm.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="姓名" prop="real_name">
          <el-input v-model="userForm.real_name" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="userForm.email" />
        </el-form-item>
        <el-form-item label="电话" prop="phone">
          <el-input v-model="userForm.phone" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="userForm.role" style="width: 100%;">
            <el-option label="管理员" value="admin" />
            <el-option label="操作员" value="operator" />
            <el-option label="观察者" value="viewer" />
          </el-select>
        </el-form-item>
        <el-form-item label="部门" prop="department">
          <el-input v-model="userForm.department" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="userDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitUser">确定</el-button>
      </template>
    </el-dialog>

    <!-- 电价配置对话框 -->
    <el-dialog v-model="pricingDialogVisible" :title="pricingEditMode ? '编辑电价' : '新增电价'" width="500px">
      <el-form ref="pricingFormRef" :model="pricingForm" :rules="pricingRules" label-width="100px">
        <el-form-item label="电价名称" prop="pricing_name">
          <el-input v-model="pricingForm.pricing_name" placeholder="如：峰时电价" />
        </el-form-item>
        <el-form-item label="时段类型" prop="period_type">
          <el-select v-model="pricingForm.period_type" style="width: 100%;">
            <el-option label="尖峰 (最高峰时段)" value="sharp" />
            <el-option label="高峰 (用电高峰)" value="peak" />
            <el-option label="平段 (正常时段)" value="flat" />
            <el-option label="低谷 (用电低谷)" value="valley" />
            <el-option label="深谷 (最低谷时段)" value="deep_valley" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始时间" prop="start_time">
          <el-time-picker
            v-model="pricingForm.start_time"
            format="HH:mm"
            value-format="HH:mm:00"
            style="width: 100%;"
            placeholder="选择开始时间"
          />
        </el-form-item>
        <el-form-item label="结束时间" prop="end_time">
          <el-time-picker
            v-model="pricingForm.end_time"
            format="HH:mm"
            value-format="HH:mm:00"
            style="width: 100%;"
            placeholder="选择结束时间"
          />
        </el-form-item>
        <el-form-item label="单价" prop="price">
          <el-input-number
            v-model="pricingForm.price"
            :min="0"
            :max="10"
            :precision="2"
            :step="0.1"
            style="width: 100%;"
          />
          <span style="margin-left: 10px; color: #999;">元/kWh</span>
        </el-form-item>
        <el-form-item label="生效日期" prop="effective_date">
          <el-date-picker
            v-model="pricingForm.effective_date"
            type="date"
            value-format="YYYY-MM-DD"
            style="width: 100%;"
            placeholder="选择生效日期"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="pricingForm.remark" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pricingDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitPricing">确定</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码对话框 -->
    <el-dialog v-model="resetPwdDialogVisible" title="重置密码" width="400px">
      <el-form ref="resetPwdFormRef" :model="resetPwdForm" :rules="resetPwdRules" label-width="80px">
        <el-form-item label="新密码" prop="password">
          <el-input v-model="resetPwdForm.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input v-model="resetPwdForm.confirmPassword" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetPwdDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitResetPwd">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getPointList, type PointInfo } from '@/api/modules/point'
import {
  getThresholdList, createThreshold, updateThreshold, deleteThreshold,
  type ThresholdInfo
} from '@/api/modules/threshold'
import {
  getUserList, createUser, updateUser, deleteUser, toggleUserStatus as apiToggleUserStatus, resetPassword,
  type UserInfo
} from '@/api/modules/user'
import {
  getOperationLogs, getSystemLogs, exportLogs as apiExportLogs,
  type OperationLog, type SystemLog
} from '@/api/modules/log'
import {
  getPricingList, createPricing, updatePricing, deletePricing,
  type ElectricityPricing
} from '@/api/modules/energy'

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
  alarm_level: ''
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

// ===== 用户管理 =====
const users = ref<UserInfo[]>([])
const userLoading = ref(false)
const userDialogVisible = ref(false)
const userEditMode = ref(false)
const userFormRef = ref()
const resetPwdDialogVisible = ref(false)
const resetPwdFormRef = ref()
const resetPwdUserId = ref(0)

const userForm = reactive({
  id: 0,
  username: '',
  password: '',
  real_name: '',
  email: '',
  phone: '',
  role: 'operator',
  department: ''
})

const userRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const resetPwdForm = reactive({
  password: '',
  confirmPassword: ''
})

const resetPwdRules = {
  password: [{ required: true, message: '请输入新密码', trigger: 'blur' }],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (_: any, value: string, callback: any) => {
        if (value !== resetPwdForm.password) {
          callback(new Error('两次密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

const roleText: Record<string, string> = {
  admin: '管理员',
  operator: '操作员',
  viewer: '观察者'
}

const roleType: Record<string, TagType> = {
  admin: 'danger',
  operator: 'warning',
  viewer: 'info'
}

// ===== 系统日志 =====
const operationLogs = ref<OperationLog[]>([])
const systemLogs = ref<SystemLog[]>([])
const logLoading = ref(false)

const logFilters = reactive({
  log_type: 'operation' as 'operation' | 'system',
  dateRange: [] as string[]
})

const logPagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const logLevelType: Record<string, TagType> = {
  debug: 'info',
  info: 'success',
  warning: 'warning',
  error: 'danger',
  critical: 'danger'
}

// ===== 电价配置 =====
const pricings = ref<ElectricityPricing[]>([])
const pricingLoading = ref(false)
const pricingDialogVisible = ref(false)
const pricingEditMode = ref(false)
const pricingFormRef = ref()

const pricingForm = reactive({
  id: 0,
  pricing_name: '',
  period_type: 'peak',
  start_time: '',
  end_time: '',
  price: 1.0,
  effective_date: new Date().toISOString().split('T')[0],
  remark: ''
})

const pricingRules = {
  pricing_name: [{ required: true, message: '请输入电价名称', trigger: 'blur' }],
  period_type: [{ required: true, message: '请选择时段类型', trigger: 'change' }],
  start_time: [{ required: true, message: '请选择开始时间', trigger: 'change' }],
  end_time: [{ required: true, message: '请选择结束时间', trigger: 'change' }],
  price: [{ required: true, message: '请输入单价', trigger: 'blur' }],
  effective_date: [{ required: true, message: '请选择生效日期', trigger: 'change' }]
}

const periodTypeText: Record<string, string> = {
  sharp: '尖峰',
  peak: '高峰',
  flat: '平段',
  valley: '低谷',
  deep_valley: '深谷',
  normal: '平段' // 兼容旧数据
}

const periodTypeTag: Record<string, TagType> = {
  sharp: 'danger',
  peak: 'warning',
  flat: 'info',
  valley: 'success',
  deep_valley: 'primary',
  normal: 'info' // 兼容旧数据
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
  loadUsers()
  loadSystemInfo()
})

watch(activeTab, (val) => {
  if (val === 'log') {
    loadLogs()
  } else if (val === 'pricing') {
    loadPricings()
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

// ===== 用户方法 =====
async function loadUsers() {
  userLoading.value = true
  try {
    const res = await getUserList({ page: 1, page_size: 100 })
    users.value = res.items
  } catch (e) {
    console.error('加载用户失败', e)
  } finally {
    userLoading.value = false
  }
}

function handleAddUser() {
  userEditMode.value = false
  Object.assign(userForm, {
    id: 0,
    username: '',
    password: '',
    real_name: '',
    email: '',
    phone: '',
    role: 'operator',
    department: ''
  })
  userDialogVisible.value = true
}

function handleEditUser(row: UserInfo) {
  userEditMode.value = true
  Object.assign(userForm, row)
  userDialogVisible.value = true
}

async function submitUser() {
  const valid = await userFormRef.value?.validate()
  if (!valid) return

  try {
    if (userEditMode.value) {
      await updateUser(userForm.id, userForm)
      ElMessage.success('更新成功')
    } else {
      await createUser(userForm)
      ElMessage.success('创建成功')
    }
    userDialogVisible.value = false
    loadUsers()
  } catch (e) {
    console.error('操作失败', e)
  }
}

async function toggleUserStatus(row: UserInfo) {
  try {
    await apiToggleUserStatus(row.id, row.is_active)
    ElMessage.success(row.is_active ? '已启用' : '已禁用')
  } catch (e) {
    row.is_active = !row.is_active
    console.error('操作失败', e)
  }
}

async function handleDeleteUser(id: number) {
  try {
    await deleteUser(id)
    ElMessage.success('删除成功')
    loadUsers()
  } catch (e) {
    console.error('删除失败', e)
  }
}

function handleResetPwd(row: UserInfo) {
  resetPwdUserId.value = row.id
  resetPwdForm.password = ''
  resetPwdForm.confirmPassword = ''
  resetPwdDialogVisible.value = true
}

async function submitResetPwd() {
  const valid = await resetPwdFormRef.value?.validate()
  if (!valid) return

  try {
    await resetPassword(resetPwdUserId.value, resetPwdForm.password)
    ElMessage.success('密码重置成功')
    resetPwdDialogVisible.value = false
  } catch (e) {
    console.error('重置失败', e)
  }
}

// ===== 日志方法 =====
async function loadLogs() {
  logLoading.value = true
  try {
    const params: any = {
      page: logPagination.page,
      page_size: logPagination.page_size
    }
    if (logFilters.dateRange && logFilters.dateRange.length === 2) {
      params.start_time = logFilters.dateRange[0]
      params.end_time = logFilters.dateRange[1]
    }

    if (logFilters.log_type === 'operation') {
      const res = await getOperationLogs(params)
      operationLogs.value = res.items
      logPagination.total = res.total
    } else {
      const res = await getSystemLogs(params)
      systemLogs.value = res.items
      logPagination.total = res.total
    }
  } catch (e) {
    console.error('加载日志失败', e)
  } finally {
    logLoading.value = false
  }
}

async function exportLogs() {
  try {
    const params: any = {
      log_type: logFilters.log_type,
      format: 'xlsx'
    }
    if (logFilters.dateRange && logFilters.dateRange.length === 2) {
      params.start_time = logFilters.dateRange[0]
      params.end_time = logFilters.dateRange[1]
    }

    const blob = await apiExportLogs(params)
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${logFilters.log_type}_logs_${Date.now()}.xlsx`
    a.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (e) {
    console.error('导出失败', e)
    ElMessage.error('导出失败')
  }
}

// ===== 电价配置方法 =====
async function loadPricings() {
  pricingLoading.value = true
  try {
    const result = await getPricingList()
    pricings.value = result.data || []
  } catch (e) {
    console.error('加载电价配置失败', e)
    ElMessage.error('加载电价配置失败')
  } finally {
    pricingLoading.value = false
  }
}

function handleAddPricing() {
  pricingEditMode.value = false
  Object.assign(pricingForm, {
    id: 0,
    pricing_name: '',
    period_type: 'peak',
    start_time: '',
    end_time: '',
    price: 1.0,
    effective_date: new Date().toISOString().split('T')[0],
    remark: ''
  })
  pricingDialogVisible.value = true
}

function handleEditPricing(row: ElectricityPricing) {
  pricingEditMode.value = true
  Object.assign(pricingForm, {
    id: row.id,
    pricing_name: row.pricing_name,
    period_type: row.period_type,
    start_time: row.start_time,
    end_time: row.end_time,
    price: row.price,
    effective_date: row.effective_date,
    remark: ''
  })
  pricingDialogVisible.value = true
}

async function submitPricing() {
  if (!pricingFormRef.value) return

  await pricingFormRef.value.validate(async (valid: boolean) => {
    if (!valid) return

    try {
      const data = {
        pricing_name: pricingForm.pricing_name,
        period_type: pricingForm.period_type,
        start_time: pricingForm.start_time,
        end_time: pricingForm.end_time,
        price: pricingForm.price,
        effective_date: pricingForm.effective_date,
        is_enabled: true
      }

      if (pricingEditMode.value) {
        await updatePricing(pricingForm.id, data)
        ElMessage.success('更新成功')
      } else {
        await createPricing(data)
        ElMessage.success('创建成功')
      }
      pricingDialogVisible.value = false
      loadPricings()
    } catch (e) {
      console.error('保存失败', e)
      ElMessage.error('保存失败')
    }
  })
}

async function togglePricing(row: ElectricityPricing) {
  try {
    await updatePricing(row.id, { is_enabled: row.is_enabled })
    ElMessage.success(row.is_enabled ? '已启用' : '已禁用')
  } catch (e) {
    row.is_enabled = !row.is_enabled
    ElMessage.error('操作失败')
  }
}

async function handleDeletePricing(id: number) {
  try {
    await deletePricing(id)
    ElMessage.success('删除成功')
    loadPricings()
  } catch (e) {
    console.error('删除失败', e)
    ElMessage.error('删除失败')
  }
}
</script>

<style scoped lang="scss">
.settings-page {
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

  .pricing-tips {
    margin-top: 20px;

    ul {
      margin: 0;
      padding-left: 20px;
      list-style: disc;

      li {
        margin-bottom: 4px;
        color: var(--text-secondary);
      }
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
