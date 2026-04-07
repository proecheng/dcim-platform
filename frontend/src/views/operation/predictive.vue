<template>
  <div class="predictive-page">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ dashboard.summary.total }}</div>
          <div class="stat-label">总设备</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value healthy">{{ dashboard.summary.healthy }}</div>
          <div class="stat-label">健康</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value attention">{{ dashboard.summary.attention }}</div>
          <div class="stat-label">关注</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value danger">{{ dashboard.summary.warning + dashboard.summary.danger }}</div>
          <div class="stat-label">预警+危险</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选栏 -->
    <el-card shadow="hover" class="filter-card">
      <el-form :inline="true">
        <el-form-item label="设备类型">
          <el-select v-model="filters.device_type" placeholder="全部类型" clearable @change="loadDashboard">
            <el-option v-for="t in typeOptions" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="健康等级">
          <el-select v-model="filters.health_level" placeholder="全部等级" clearable @change="loadDashboard">
            <el-option v-for="l in levelOptions" :key="l" :label="l" :value="l" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button :icon="Refresh" @click="loadDashboard">刷新</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 设备健康度卡片网格 -->
    <div v-if="dashboard.devices.length > 0" class="device-grid">
      <el-row :gutter="16">
        <el-col
          v-for="device in dashboard.devices"
          :key="device.device_id"
          :xs="24" :sm="12" :md="8" :lg="6"
          class="device-col"
        >
          <el-card
            shadow="hover"
            class="device-card"
            :class="levelClass(device.health_level)"
            @click="openDetail(device)"
          >
            <div class="card-header">
              <span class="device-name">{{ device.device_name || `设备${device.device_id}` }}</span>
              <el-tag size="small" :type="levelTagType(device.health_level)">
                {{ device.health_level }}
              </el-tag>
            </div>
            <div class="card-score" :style="{ color: levelColor(device.health_level) }">
              {{ device.score.toFixed(1) }}分
            </div>
            <div class="card-meta">
              <span>{{ device.device_type || '未知类型' }}</span>
              <span v-if="device.calculated_at">{{ formatTime(device.calculated_at) }}</span>
            </div>
            <el-tag
              v-if="sufficiencyText(device.data_sufficiency)"
              size="small"
              :type="sufficiencyType(device.data_sufficiency)"
              class="sufficiency-tag"
            >
              {{ sufficiencyText(device.data_sufficiency) }}
            </el-tag>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 空状态 -->
    <el-empty v-else description="暂无设备健康度数据" />

    <!-- 设备详情弹窗 -->
    <el-dialog
      v-model="detailVisible"
      title="设备健康度详情"
      width="680px"
      destroy-on-close
    >
      <div v-if="detailLoading" v-loading="true" style="min-height: 200px" />
      <div v-else-if="detail">
        <!-- 设备信息头 -->
        <div class="detail-header">
          <span class="detail-name">{{ detail.health.device_name || `设备${detail.health.device_id}` }}</span>
          <span class="detail-score" :style="{ color: levelColor(detail.health.health_level) }">
            {{ detail.health.score.toFixed(1) }}分
          </span>
          <el-tag :type="levelTagType(detail.health.health_level)">
            {{ detail.health.health_level }}
          </el-tag>
        </div>

        <!-- 评分因子明细 -->
        <div v-if="detail.factors" class="factor-section">
          <h4>评分因子明细</h4>
          <div v-if="detail.factors.degradation" class="factor-item">
            <span class="factor-label">劣化趋势</span>
            <span class="factor-value">{{ detail.factors.degradation.score.toFixed(1) }}分</span>
            <span class="factor-weight">(权重{{ (detail.factors.degradation.weight * 100).toFixed(0) }}%)</span>
          </div>
          <div v-if="detail.factors.alarm" class="factor-item">
            <span class="factor-label">告警频次</span>
            <span class="factor-value">{{ detail.factors.alarm.score.toFixed(1) }}分</span>
            <span class="factor-weight">
              (权重{{ (detail.factors.alarm.weight * 100).toFixed(0) }}%,
              近30天{{ detail.factors.alarm.count }}次)
            </span>
          </div>
          <div v-if="detail.factors.maintenance" class="factor-item">
            <span class="factor-label">维保记录</span>
            <span class="factor-value">{{ detail.factors.maintenance.score.toFixed(1) }}分</span>
            <span class="factor-weight">
              (权重{{ (detail.factors.maintenance.weight * 100).toFixed(0) }}%,
              {{ detail.factors.maintenance.days_since !== null ? `距上次${detail.factors.maintenance.days_since}天` : '无维保记录' }})
            </span>
          </div>
          <div v-if="detail.factors.data_sufficiency" class="factor-item">
            <span class="factor-label">数据充分度</span>
            <el-tag
              size="small"
              :type="sufficiencyType(detail.factors.data_sufficiency)"
            >
              {{ sufficiencyLabel(detail.factors.data_sufficiency) }}
            </el-tag>
          </div>
        </div>

        <!-- 维护建议列表 -->
        <div class="advice-section">
          <h4>维护建议</h4>
          <div v-if="detail.advices.length === 0" class="no-advice">暂无维护建议</div>
          <div v-for="advice in detail.advices" :key="advice.id" class="advice-item">
            <div class="advice-header">
              <el-tag size="small" :type="adviceStatusType(advice.status)">
                {{ adviceStatusLabel(advice.status) }}
              </el-tag>
              <span v-if="advice.urgency" class="advice-urgency">
                {{ advice.urgency === 'high' ? '紧急' : '一般' }}
              </span>
              <span class="advice-time">{{ formatTime(advice.created_at) }}</span>
            </div>
            <div class="advice-reason">{{ advice.reason }}</div>
            <div v-if="advice.suggested_action" class="advice-action">
              建议: {{ advice.suggested_action }}
            </div>
            <div v-if="advice.status === 'pending'" class="advice-actions">
              <el-button
                type="primary"
                size="small"
                :loading="confirmingId === advice.id"
                @click="handleConfirm(advice)"
              >
                确认转工单
              </el-button>
              <el-button
                size="small"
                :loading="rejectingId === advice.id"
                @click="openReject(advice)"
              >
                标记误报
              </el-button>
            </div>
            <div v-if="advice.status === 'converted' && advice.work_order_id" class="advice-wo">
              已转工单 #{{ advice.work_order_id }}
            </div>
            <div v-if="advice.status === 'rejected' && advice.feedback" class="advice-feedback">
              误报原因: {{ advice.feedback }}
            </div>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- 拒绝反馈弹窗 -->
    <el-dialog v-model="rejectVisible" title="标记误报" width="400px">
      <el-form>
        <el-form-item label="误报原因">
          <el-input
            v-model="rejectFeedback"
            type="textarea"
            :rows="3"
            placeholder="请输入误报原因（至少2个字）"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectVisible = false">取消</el-button>
        <el-button
          type="primary"
          :disabled="rejectFeedback.trim().length < 2"
          :loading="rejectingId !== null"
          @click="handleReject"
        >
          确认
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import {
  getDashboard,
  getDeviceDetail,
  confirmAdvice,
  rejectAdvice,
} from '@/api/modules/predictiveMaintenance'
import type {
  DashboardResponse,
  DeviceDetailResponse,
  DeviceHealthItem,
  MaintenanceAdviceInfo,
} from '@/api/modules/predictiveMaintenance'

const loading = ref(false)
const dashboard = ref<DashboardResponse>({
  summary: { total: 0, healthy: 0, attention: 0, warning: 0, danger: 0 },
  devices: [],
})

const filters = ref<{ device_type?: string; health_level?: string }>({})
const typeOptions = ['AC', 'UPS', 'PDU', 'BATTERY']
const levelOptions = ['健康', '关注', '预警', '危险']

// 详情弹窗
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<DeviceDetailResponse | null>(null)

// 拒绝弹窗
const rejectVisible = ref(false)
const rejectFeedback = ref('')
const rejectingAdvice = ref<MaintenanceAdviceInfo | null>(null)

// 操作状态
const confirmingId = ref<number | null>(null)
const rejectingId = ref<number | null>(null)

async function loadDashboard() {
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (filters.value.device_type) params.device_type = filters.value.device_type
    if (filters.value.health_level) params.health_level = filters.value.health_level
    dashboard.value = await getDashboard(params)
  } catch (e) {
    console.error('加载仪表盘失败', e)
  } finally {
    loading.value = false
  }
}

async function openDetail(device: DeviceHealthItem) {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await getDeviceDetail(device.device_id)
  } catch (e) {
    console.error('加载详情失败', e)
    ElMessage.error('加载设备详情失败')
  } finally {
    detailLoading.value = false
  }
}

async function handleConfirm(advice: MaintenanceAdviceInfo) {
  confirmingId.value = advice.id
  try {
    const res = await confirmAdvice(advice.id)
    ElMessage.success(`已创建工单 ${res.work_order_no}`)
    detail.value = await getDeviceDetail(advice.device_id)
  } catch (e: any) {
    if (e?.response?.status === 409) {
      ElMessage.warning('该建议状态已变更，请刷新')
      detail.value = await getDeviceDetail(advice.device_id)
    } else {
      ElMessage.error('确认失败')
    }
  } finally {
    confirmingId.value = null
  }
}

function openReject(advice: MaintenanceAdviceInfo) {
  rejectingAdvice.value = advice
  rejectFeedback.value = ''
  rejectVisible.value = true
}

async function handleReject() {
  if (!rejectingAdvice.value || rejectFeedback.value.trim().length < 2) return
  const advice = rejectingAdvice.value
  rejectingId.value = advice.id
  try {
    await rejectAdvice(advice.id, rejectFeedback.value.trim())
    rejectVisible.value = false
    ElMessage.success('已标记误报')
    detail.value = await getDeviceDetail(advice.device_id)
  } catch (e: any) {
    if (e?.response?.status === 409) {
      ElMessage.warning('该建议状态已变更，请刷新')
      detail.value = await getDeviceDetail(advice.device_id)
    } else {
      ElMessage.error('拒绝失败')
    }
  } finally {
    rejectingId.value = null
  }
}

// 工具函数
function levelColor(level: string): string {
  const map: Record<string, string> = {
    '健康': '#67C23A',
    '关注': '#E6A23C',
    '预警': '#F56C6C',
    '危险': '#C45656',
  }
  return map[level] || '#909399'
}

function levelClass(level: string): string {
  const map: Record<string, string> = {
    '健康': 'level-healthy',
    '关注': 'level-attention',
    '预警': 'level-warning',
    '危险': 'level-danger',
  }
  return map[level] || ''
}

function levelTagType(level: string): 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
    '健康': 'success',
    '关注': 'warning',
    '预警': 'danger',
    '危险': 'danger',
  }
  return map[level] || 'info'
}

function sufficiencyText(ds: string | null): string {
  if (ds === 'partial') return '评估精度：中等'
  if (ds === 'minimal') return '评估精度：有限'
  return ''
}

function sufficiencyType(ds: string | null | undefined): 'info' | 'warning' | 'danger' {
  if (ds === 'partial') return 'warning'
  if (ds === 'minimal') return 'danger'
  return 'info'
}

function sufficiencyLabel(ds: string): string {
  const map: Record<string, string> = {
    full: '充分',
    partial: '中等',
    minimal: '有限',
  }
  return map[ds] || ds
}

function adviceStatusType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
    pending: 'warning',
    converted: 'success',
    rejected: 'info',
    auto_closed: 'info',
  }
  return map[status] || 'info'
}

function adviceStatusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: '待处理',
    converted: '已转工单',
    rejected: '已拒绝',
    auto_closed: '自动关闭',
  }
  return map[status] || status
}

function formatTime(dt: string | null): string {
  if (!dt) return ''
  const d = new Date(dt)
  if (isNaN(d.getTime())) return ''
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

onMounted(() => {
  loadDashboard()
})
</script>

<style scoped>
.predictive-page {
  padding: 16px;
}

.stat-row {
  margin-bottom: 16px;
}

.stat-card {
  text-align: center;
  cursor: default;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}

.stat-value.healthy { color: #67C23A; }
.stat-value.attention { color: #E6A23C; }
.stat-value.danger { color: #F56C6C; }

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 4px;
}

.filter-card {
  margin-bottom: 16px;
}

.device-grid {
  margin-top: 8px;
}

.device-col {
  margin-bottom: 16px;
}

.device-card {
  cursor: pointer;
  transition: all 0.3s;
  border-left: 4px solid transparent;
}

.device-card:hover {
  transform: translateY(-2px);
}

.device-card.level-healthy { border-left-color: #67C23A; }
.device-card.level-attention { border-left-color: #E6A23C; }
.device-card.level-warning { border-left-color: #F56C6C; }
.device-card.level-danger {
  border-left-color: #C45656;
  animation: pulse-danger 2s infinite;
}

@keyframes pulse-danger {
  0%, 100% { box-shadow: 0 0 0 0 rgba(196, 86, 86, 0.2); }
  50% { box-shadow: 0 0 12px 4px rgba(196, 86, 86, 0.3); }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.device-name {
  font-weight: 600;
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 140px;
}

.card-score {
  font-size: 32px;
  font-weight: bold;
  text-align: center;
  margin: 12px 0;
}

.card-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #909399;
}

.sufficiency-tag {
  margin-top: 8px;
}

/* 详情弹窗 */
.detail-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid #ebeef5;
}

.detail-name {
  font-size: 18px;
  font-weight: 600;
}

.detail-score {
  font-size: 24px;
  font-weight: bold;
}

.factor-section {
  margin-bottom: 20px;
}

.factor-section h4 {
  margin: 0 0 12px;
  color: #303133;
}

.factor-item {
  padding: 8px 0;
  border-bottom: 1px dashed #ebeef5;
  display: flex;
  align-items: center;
  gap: 8px;
}

.factor-label {
  width: 80px;
  color: #606266;
}

.factor-value {
  font-weight: 600;
  color: #303133;
}

.factor-weight {
  color: #909399;
  font-size: 13px;
}

.advice-section h4 {
  margin: 0 0 12px;
  color: #303133;
}

.no-advice {
  color: #909399;
  text-align: center;
  padding: 20px;
}

.advice-item {
  padding: 12px;
  margin-bottom: 8px;
  background: #fafafa;
  border-radius: 4px;
}

.advice-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.advice-urgency {
  font-size: 12px;
  color: #F56C6C;
}

.advice-time {
  font-size: 12px;
  color: #909399;
  margin-left: auto;
}

.advice-reason {
  font-size: 14px;
  color: #303133;
  margin-bottom: 4px;
}

.advice-action {
  font-size: 13px;
  color: #606266;
  margin-bottom: 8px;
}

.advice-actions {
  display: flex;
  gap: 8px;
}

.advice-wo {
  font-size: 12px;
  color: #67C23A;
}

.advice-feedback {
  font-size: 12px;
  color: #909399;
  font-style: italic;
}
</style>
