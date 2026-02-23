<template>
  <div class="linkage-recovery-page">
    <!-- 可恢复执行记录 -->
    <el-card shadow="hover" class="table-card">
      <div class="section-header">
        <span class="section-title">可恢复执行记录</span>
        <el-button type="primary" :icon="Refresh" @click="loadRecoverables">刷新</el-button>
      </div>
      <el-table
        :data="recoverables"
        stripe
        border
        v-loading="loadingRecoverables"
        row-key="id"
      >
        <el-table-column prop="event_id" label="事件ID" width="180" show-overflow-tooltip />
        <el-table-column prop="policy_name" label="策略名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="trigger_source" label="触发来源" min-width="140" show-overflow-tooltip />
        <el-table-column prop="status" label="执行状态" width="120" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="execStatusTag(row.status)">
              {{ execStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="started_at" label="执行时间" width="180" show-overflow-tooltip />
        <el-table-column label="操作" width="120" align="center">
          <template #default="{ row }">
            <el-button type="warning" size="small" @click="openRecoveryDialog(row)">恢复</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="recoverablePagination.page"
        v-model:page-size="recoverablePagination.pageSize"
        :total="recoverablePagination.total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        class="pagination"
        @size-change="loadRecoverables"
        @current-change="loadRecoverables"
      />
    </el-card>

    <!-- 恢复历史记录 -->
    <el-card shadow="hover" class="table-card">
      <div class="section-header">
        <span class="section-title">恢复历史记录</span>
        <el-button :icon="Refresh" @click="loadRecoveries">刷新</el-button>
      </div>
      <el-table
        :data="recoveries"
        stripe
        border
        v-loading="loadingRecoveries"
        row-key="id"
        @row-click="handleRecoveryRowClick"
        row-class-name="clickable-row"
      >
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="execution_id" label="关联执行ID" width="120" />
        <el-table-column prop="operator" label="操作人" min-width="120" show-overflow-tooltip />
        <el-table-column prop="mode" label="恢复模式" width="120" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.mode === 'auto' ? 'info' : 'warning'">
              {{ row.mode === 'auto' ? '自动' : '手动' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="recoveryStatusTag(row.status)">
              {{ recoveryStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="started_at" label="开始时间" width="180" show-overflow-tooltip />
        <el-table-column label="耗时(ms)" width="120" align="center">
          <template #default="{ row }">
            {{ row.total_duration_ms != null ? row.total_duration_ms : '-' }}
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="recoveryPagination.page"
        v-model:page-size="recoveryPagination.pageSize"
        :total="recoveryPagination.total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        class="pagination"
        @size-change="loadRecoveries"
        @current-change="loadRecoveries"
      />
    </el-card>

    <!-- 恢复操作对话框 -->
    <el-dialog append-to-body v-model="recoveryDialogVisible" title="联动恢复" width="500px">
      <div v-if="selectedExecution" class="recovery-dialog-body">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="事件ID">{{ selectedExecution.event_id }}</el-descriptions-item>
          <el-descriptions-item label="策略名称">{{ selectedExecution.policy_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="触发来源">{{ selectedExecution.trigger_source }}</el-descriptions-item>
        </el-descriptions>
        <div class="recovery-mode-section">
          <span class="mode-label">恢复模式：</span>
          <el-radio-group v-model="recoveryMode">
            <el-radio value="auto">自动恢复（一键执行所有步骤）</el-radio>
            <el-radio value="manual">手动恢复（逐步确认执行）</el-radio>
          </el-radio-group>
        </div>
      </div>
      <template #footer>
        <el-button @click="recoveryDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitRecovery">确认恢复</el-button>
      </template>
    </el-dialog>

    <!-- 恢复详情抽屉 -->
    <el-drawer v-model="drawerVisible" title="恢复详情" size="560px" direction="rtl">
      <template v-if="currentRecovery">
        <el-descriptions :column="1" border size="small" class="detail-desc">
          <el-descriptions-item label="恢复ID">{{ currentRecovery.id }}</el-descriptions-item>
          <el-descriptions-item label="关联执行ID">{{ currentRecovery.execution_id }}</el-descriptions-item>
          <el-descriptions-item label="操作人">{{ currentRecovery.operator }}</el-descriptions-item>
          <el-descriptions-item label="恢复模式">
            {{ currentRecovery.mode === 'auto' ? '自动' : '手动' }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag size="small" :type="recoveryStatusTag(currentRecovery.status)">
              {{ recoveryStatusText(currentRecovery.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ currentRecovery.started_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ currentRecovery.completed_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="总耗时">
            {{ currentRecovery.total_duration_ms != null ? currentRecovery.total_duration_ms + ' ms' : '-' }}
          </el-descriptions-item>
        </el-descriptions>
        <div class="timeline-section">
          <h4 class="timeline-title">恢复步骤</h4>
          <el-timeline v-if="currentRecovery.logs && currentRecovery.logs.length">
            <el-timeline-item
              v-for="log in currentRecovery.logs"
              :key="log.id"
              :type="stepTimelineType(log.status)"
              :timestamp="log.started_at || '待执行'"
              placement="top"
            >
              <div class="log-card">
                <div class="log-header">
                  <el-tag size="small" :type="stepStatusTag(log.status)">
                    {{ stepStatusText(log.status) }}
                  </el-tag>
                  <span class="log-action-type">步骤{{ log.step_order }} - {{ log.action_type || '未知' }}</span>
                  <span v-if="log.duration_ms != null" class="log-duration">{{ log.duration_ms }} ms</span>
                </div>
                <div v-if="log.recovery_command" class="log-command">
                  恢复命令: {{ log.recovery_command }}
                </div>
                <div v-if="log.error_message" class="log-error">
                  {{ log.error_message }}
                </div>
                <div v-if="currentRecovery.mode === 'manual' && log.status === 'pending'" class="step-actions">
                  <el-button
                    type="primary"
                    size="small"
                    :loading="executingStep === log.step_order"
                    @click="handleExecuteStep(log.step_order)"
                  >执行</el-button>
                  <el-button
                    size="small"
                    :loading="skippingStep === log.step_order"
                    @click="handleSkipStep(log.step_order)"
                  >跳过</el-button>
                </div>
              </div>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无恢复步骤" :image-size="60" />
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import {
  getRecoverableExecutions,
  createRecovery,
  getRecoveries,
  getRecovery,
  executeRecoveryStep,
  skipRecoveryStep,
} from '@/api/modules/linkage'
import type { LinkageExecution, LinkageRecovery } from '@/api/modules/linkage'

// ==================== 可恢复执行记录 ====================
const loadingRecoverables = ref(false)
const recoverables = ref<LinkageExecution[]>([])
const recoverablePagination = reactive({ page: 1, pageSize: 20, total: 0 })

async function loadRecoverables() {
  loadingRecoverables.value = true
  try {
    const result = await getRecoverableExecutions({
      page: recoverablePagination.page,
      page_size: recoverablePagination.pageSize
    })
    recoverables.value = result.items || []
    recoverablePagination.total = result.total || 0
  } catch {
    ElMessage.error('加载可恢复记录失败')
  } finally {
    loadingRecoverables.value = false
  }
}

// ==================== 恢复历史记录 ====================
const loadingRecoveries = ref(false)
const recoveries = ref<LinkageRecovery[]>([])
const recoveryPagination = reactive({ page: 1, pageSize: 20, total: 0 })

async function loadRecoveries() {
  loadingRecoveries.value = true
  try {
    const result = await getRecoveries({
      page: recoveryPagination.page,
      page_size: recoveryPagination.pageSize
    })
    recoveries.value = result.items || []
    recoveryPagination.total = result.total || 0
  } catch {
    ElMessage.error('加载恢复记录失败')
  } finally {
    loadingRecoveries.value = false
  }
}

// ==================== 恢复操作对话框 ====================
const recoveryDialogVisible = ref(false)
const selectedExecution = ref<LinkageExecution | null>(null)
const recoveryMode = ref<string>('auto')
const submitting = ref(false)

function openRecoveryDialog(row: LinkageExecution) {
  selectedExecution.value = row
  recoveryMode.value = 'auto'
  recoveryDialogVisible.value = true
}

async function submitRecovery() {
  if (!selectedExecution.value) return
  submitting.value = true
  try {
    const res = await createRecovery(selectedExecution.value.id, recoveryMode.value)
    ElMessage.success(`恢复已创建，共 ${res.steps_count} 个步骤`)
    recoveryDialogVisible.value = false
    loadRecoverables()
    loadRecoveries()
    if (recoveryMode.value === 'manual' && res.recovery_id) {
      const detail = await getRecovery(res.recovery_id)
      currentRecovery.value = detail
      drawerVisible.value = true
    }
  } catch {
    ElMessage.error('创建恢复失败')
  } finally {
    submitting.value = false
  }
}

// ==================== 恢复详情抽屉 ====================
const drawerVisible = ref(false)
const currentRecovery = ref<LinkageRecovery | null>(null)
const executingStep = ref<number | null>(null)
const skippingStep = ref<number | null>(null)

async function handleRecoveryRowClick(row: LinkageRecovery) {
  try {
    const detail = await getRecovery(row.id)
    currentRecovery.value = detail
    drawerVisible.value = true
  } catch {
    ElMessage.error('加载恢复详情失败')
  }
}

async function handleExecuteStep(stepOrder: number) {
  if (!currentRecovery.value) return
  executingStep.value = stepOrder
  try {
    await executeRecoveryStep(currentRecovery.value.id, stepOrder)
    ElMessage.success(`步骤 ${stepOrder} 执行完成`)
    const detail = await getRecovery(currentRecovery.value.id)
    currentRecovery.value = detail
  } catch {
    ElMessage.error(`步骤 ${stepOrder} 执行失败`)
  } finally {
    executingStep.value = null
  }
}

async function handleSkipStep(stepOrder: number) {
  if (!currentRecovery.value) return
  skippingStep.value = stepOrder
  try {
    await skipRecoveryStep(currentRecovery.value.id, stepOrder)
    ElMessage.success(`步骤 ${stepOrder} 已跳过`)
    const detail = await getRecovery(currentRecovery.value.id)
    currentRecovery.value = detail
  } catch {
    ElMessage.error(`步骤 ${stepOrder} 跳过失败`)
  } finally {
    skippingStep.value = null
  }
}

// ==================== 辅助函数 ====================
function execStatusText(status: string): string {
  const map: Record<string, string> = {
    executing: '执行中', completed: '已完成',
    partial_failure: '部分失败', failed: '失败'
  }
  return map[status] || status
}

function execStatusTag(status: string): 'success' | 'warning' | 'info' | 'danger' {
  const map: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    executing: 'info', completed: 'success',
    partial_failure: 'warning', failed: 'danger'
  }
  return map[status] || 'info'
}

function recoveryStatusText(status: string): string {
  const map: Record<string, string> = {
    pending: '待执行', executing: '执行中', completed: '已完成',
    partial_recovery: '部分恢复', failed: '失败'
  }
  return map[status] || status
}

function recoveryStatusTag(status: string): 'success' | 'warning' | 'info' | 'danger' {
  const map: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    pending: 'info', executing: 'info', completed: 'success',
    partial_recovery: 'warning', failed: 'danger'
  }
  return map[status] || 'info'
}

function stepStatusText(status: string): string {
  const map: Record<string, string> = {
    pending: '待执行', running: '执行中', success: '成功',
    failed: '失败', skipped: '已跳过'
  }
  return map[status] || status
}

function stepStatusTag(status: string): 'success' | 'warning' | 'info' | 'danger' {
  const map: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    pending: 'info', running: 'info', success: 'success',
    failed: 'danger', skipped: 'info'
  }
  return map[status] || 'info'
}

function stepTimelineType(status: string): 'primary' | 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'danger' | 'info'> = {
    pending: 'info', running: 'primary', success: 'success',
    failed: 'danger', skipped: 'info'
  }
  return map[status] || 'info'
}

// ==================== 生命周期 ====================
onMounted(() => {
  loadRecoverables()
  loadRecoveries()
})
</script>

<style lang="scss" scoped>
@use '@/styles/_mixins-25d' as *;

.linkage-recovery-page {
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

.table-card {
  margin-bottom: 16px;
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

:deep(.clickable-row) {
  cursor: pointer;
}

.recovery-dialog-body {
  .recovery-mode-section {
    margin-top: 16px;
    .mode-label {
      display: block;
      font-weight: 500;
      margin-bottom: 8px;
    }
    .el-radio {
      display: block;
      margin-bottom: 8px;
    }
  }
}

.detail-desc {
  margin-bottom: 20px;
}

.timeline-section {
  padding: 0 4px;
}

.timeline-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 16px;
  color: var(--el-text-color-primary);
}

.log-card {
  padding: 8px 0;
}

.log-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.log-action-type {
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.log-duration {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  margin-left: auto;
}

.log-command {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.log-error {
  margin-top: 6px;
  padding: 6px 10px;
  background: var(--el-color-danger-light-9);
  border-radius: 4px;
  color: var(--el-color-danger);
  font-size: 12px;
  line-height: 1.5;
}

.step-actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}
</style>
