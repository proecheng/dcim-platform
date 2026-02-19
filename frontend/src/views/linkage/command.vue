<template>
  <div class="linkage-command-page">
    <el-tabs v-model="activeTab" @tab-change="handleTabChange">
      <!-- 命令审批 -->
      <el-tab-pane label="命令审批" name="approvals">
        <el-card shadow="hover" class="table-card">
          <div class="section-header">
            <span class="section-title">审批工单列表</span>
            <div class="filter-bar">
              <el-select
                v-model="approvalStatusFilter"
                placeholder="状态筛选"
                clearable
                style="width: 140px"
                @change="loadApprovals"
              >
                <el-option label="待审批" value="pending" />
                <el-option label="已批准" value="approved" />
                <el-option label="已驳回" value="rejected" />
                <el-option label="已超时" value="timeout" />
              </el-select>
              <el-button type="primary" :icon="Refresh" @click="loadApprovals">刷新</el-button>
            </div>
          </div>
          <el-table
            :data="approvals"
            stripe
            border
            v-loading="loadingApprovals"
            row-key="id"
          >
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="command_type" label="命令类型" min-width="120" show-overflow-tooltip />
            <el-table-column prop="risk_level" label="风险等级" width="100" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="riskLevelTag(row.risk_level)">
                  {{ riskLevelText(row.risk_level) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="target_device_name" label="目标设备" min-width="140" show-overflow-tooltip />
            <el-table-column prop="requester_name" label="发起人" width="120" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="approvalStatusTag(row.status)">
                  {{ approvalStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="180" show-overflow-tooltip>
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160" align="center">
              <template #default="{ row }">
                <template v-if="row.status === 'pending'">
                  <el-button type="success" size="small" @click="handleApprove(row)">批准</el-button>
                  <el-button type="danger" size="small" @click="handleReject(row)">驳回</el-button>
                </template>
                <span v-else class="no-action">-</span>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-model:current-page="approvalPagination.page"
            v-model:page-size="approvalPagination.pageSize"
            :total="approvalPagination.total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next"
            class="pagination"
            @size-change="loadApprovals"
            @current-change="loadApprovals"
          />
        </el-card>
      </el-tab-pane>

      <!-- 审计日志 -->
      <el-tab-pane label="审计日志" name="audit">
        <el-card shadow="hover" class="table-card">
          <div class="section-header">
            <span class="section-title">命令审计日志</span>
            <div class="filter-bar">
              <el-input
                v-model="auditCommandTypeFilter"
                placeholder="命令类型"
                clearable
                style="width: 140px"
                @clear="loadAuditLogs"
                @keyup.enter="loadAuditLogs"
              />
              <el-input
                v-model="auditOperatorFilter"
                placeholder="操作人"
                clearable
                style="width: 140px"
                @clear="loadAuditLogs"
                @keyup.enter="loadAuditLogs"
              />
              <el-button type="primary" :icon="Refresh" @click="loadAuditLogs">刷新</el-button>
            </div>
          </div>
          <el-table
            :data="auditLogs"
            stripe
            border
            v-loading="loadingAuditLogs"
            row-key="id"
          >
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="command_type" label="命令类型" min-width="120" show-overflow-tooltip />
            <el-table-column prop="risk_level" label="风险等级" width="100" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="riskLevelTag(row.risk_level)">
                  {{ riskLevelText(row.risk_level) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="target_device_name" label="目标设备" min-width="140" show-overflow-tooltip />
            <el-table-column prop="operator_name" label="操作人" width="120" show-overflow-tooltip />
            <el-table-column prop="result" label="结果" width="100" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="auditResultTag(row.result)">
                  {{ auditResultText(row.result) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="result_message" label="结果描述" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">
                {{ row.result_message || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="时间" width="180" show-overflow-tooltip>
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-model:current-page="auditPagination.page"
            v-model:page-size="auditPagination.pageSize"
            :total="auditPagination.total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next"
            class="pagination"
            @size-change="loadAuditLogs"
            @current-change="loadAuditLogs"
          />
        </el-card>
      </el-tab-pane>

      <!-- 风险配置 -->
      <el-tab-pane label="风险配置" name="risk">
        <el-card shadow="hover" class="table-card">
          <div class="section-header">
            <span class="section-title">命令风险等级配置</span>
            <div class="filter-bar">
              <el-button type="primary" :loading="savingRisk" @click="handleSaveRiskConfigs">保存配置</el-button>
              <el-button :icon="Refresh" @click="loadRiskConfigs">刷新</el-button>
            </div>
          </div>
          <el-table
            :data="riskConfigs"
            stripe
            border
            v-loading="loadingRisk"
            row-key="command_type"
          >
            <el-table-column prop="command_type" label="命令类型" min-width="180" show-overflow-tooltip />
            <el-table-column prop="risk_level" label="风险等级" width="180" align="center">
              <template #default="{ row }">
                <el-select v-model="row.risk_level" style="width: 130px">
                  <el-option label="普通" value="normal" />
                  <el-option label="高危" value="critical" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="说明" min-width="260">
              <template #default="{ row }">
                <el-input v-model="row.description" placeholder="请输入说明" />
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import {
  getCommandApprovals,
  approveCommand,
  rejectCommand,
  getCommandAuditLogs,
  getRiskConfigs,
  updateRiskConfigs,
} from '@/api/modules/command'
import type { CommandApproval, CommandAuditLog, RiskConfigItem } from '@/api/modules/command'

// ==================== Tab 切换 ====================
const activeTab = ref('approvals')

function handleTabChange(tab: string) {
  if (tab === 'approvals') loadApprovals()
  else if (tab === 'audit') loadAuditLogs()
  else if (tab === 'risk') loadRiskConfigs()
}

// ==================== 命令审批 ====================
const loadingApprovals = ref(false)
const approvals = ref<CommandApproval[]>([])
const approvalStatusFilter = ref('')
const approvalPagination = reactive({ page: 1, pageSize: 20, total: 0 })

async function loadApprovals() {
  loadingApprovals.value = true
  try {
    const params: Record<string, unknown> = {
      page: approvalPagination.page,
      page_size: approvalPagination.pageSize,
    }
    if (approvalStatusFilter.value) {
      params.status = approvalStatusFilter.value
    }
    const result = await getCommandApprovals(params as any)
    approvals.value = result.items || []
    approvalPagination.total = result.total || 0
  } catch {
    ElMessage.error('加载审批列表失败')
  } finally {
    loadingApprovals.value = false
  }
}

async function handleApprove(row: CommandApproval) {
  try {
    await ElMessageBox.confirm(
      `确认批准命令 "${row.command_type}" 对设备 "${row.target_device_name}" 的操作？`,
      '批准确认',
      { confirmButtonText: '确认批准', cancelButtonText: '取消', type: 'warning' }
    )
    await approveCommand(row.id)
    ElMessage.success('已批准')
    loadApprovals()
  } catch (e: any) {
    if (e !== 'cancel' && e?.toString() !== 'cancel') {
      ElMessage.error('批准操作失败')
    }
  }
}

async function handleReject(row: CommandApproval) {
  try {
    const { value: reason } = await ElMessageBox.prompt(
      `请输入驳回命令 "${row.command_type}" 的原因：`,
      '驳回确认',
      {
        confirmButtonText: '确认驳回',
        cancelButtonText: '取消',
        inputPlaceholder: '请输入驳回原因',
        inputValidator: (val: string) => !!val?.trim() || '驳回原因不能为空',
        type: 'warning',
      }
    )
    await rejectCommand(row.id, reason!)
    ElMessage.success('已驳回')
    loadApprovals()
  } catch (e: any) {
    if (e !== 'cancel' && e?.toString() !== 'cancel') {
      ElMessage.error('驳回操作失败')
    }
  }
}

// ==================== 审计日志 ====================
const loadingAuditLogs = ref(false)
const auditLogs = ref<CommandAuditLog[]>([])
const auditCommandTypeFilter = ref('')
const auditOperatorFilter = ref('')
const auditPagination = reactive({ page: 1, pageSize: 20, total: 0 })

async function loadAuditLogs() {
  loadingAuditLogs.value = true
  try {
    const params: Record<string, unknown> = {
      page: auditPagination.page,
      page_size: auditPagination.pageSize,
    }
    if (auditCommandTypeFilter.value) {
      params.command_type = auditCommandTypeFilter.value
    }
    if (auditOperatorFilter.value) {
      params.operator_name = auditOperatorFilter.value
    }
    const result = await getCommandAuditLogs(params as any)
    auditLogs.value = result.items || []
    auditPagination.total = result.total || 0
  } catch {
    ElMessage.error('加载审计日志失败')
  } finally {
    loadingAuditLogs.value = false
  }
}

// ==================== 风险配置 ====================
const loadingRisk = ref(false)
const savingRisk = ref(false)
const riskConfigs = ref<RiskConfigItem[]>([])

async function loadRiskConfigs() {
  loadingRisk.value = true
  try {
    const result = await getRiskConfigs()
    riskConfigs.value = result || []
  } catch {
    ElMessage.error('加载风险配置失败')
  } finally {
    loadingRisk.value = false
  }
}

async function handleSaveRiskConfigs() {
  savingRisk.value = true
  try {
    const res = await updateRiskConfigs(riskConfigs.value)
    ElMessage.success(res.message || `已更新 ${res.updated} 条配置`)
  } catch {
    ElMessage.error('保存风险配置失败')
  } finally {
    savingRisk.value = false
  }
}

// ==================== 辅助函数 ====================
function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return dateStr
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function approvalStatusText(status: string): string {
  const map: Record<string, string> = {
    pending: '待审批', approved: '已批准', rejected: '已驳回', timeout: '已超时',
  }
  return map[status] || status
}

function approvalStatusTag(status: string): 'success' | 'warning' | 'info' | 'danger' {
  const map: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    pending: 'warning', approved: 'success', rejected: 'danger', timeout: 'info',
  }
  return map[status] || 'info'
}

function riskLevelText(level: string): string {
  const map: Record<string, string> = { normal: '普通', critical: '高危' }
  return map[level] || level
}

function riskLevelTag(level: string): 'success' | 'warning' | 'info' | 'danger' {
  const map: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    normal: 'info', critical: 'danger',
  }
  return map[level] || 'info'
}

function auditResultText(result: string): string {
  const map: Record<string, string> = {
    success: '成功', failed: '失败', pending: '待处理', timeout: '超时', cancelled: '已取消',
  }
  return map[result] || result
}

function auditResultTag(result: string): 'success' | 'warning' | 'info' | 'danger' {
  const map: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    success: 'success', failed: 'danger', pending: 'warning', timeout: 'info', cancelled: 'info',
  }
  return map[result] || 'info'
}

// ==================== 生命周期 ====================
onMounted(() => {
  loadApprovals()
})
</script>

<style lang="scss" scoped>
@use '@/styles/_mixins-25d' as *;

.linkage-command-page {
  height: 100%;
  padding: 16px;
  overflow-y: auto;
  @include page-list;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.table-card {
  margin-bottom: 16px;
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.no-action {
  color: var(--el-text-color-placeholder);
}
</style>
