<template>
  <div class="linkage-execution-page">
    <!-- 顶部筛选栏 -->
    <el-card shadow="hover" class="filter-card">
      <el-form :inline="true" class="filter-form">
        <el-form-item label="策略名称">
          <el-input v-model="filters.policy_name" placeholder="搜索策略名称" clearable @keyup.enter="handleSearch" />
        </el-form-item>
        <el-form-item label="执行状态">
          <el-select v-model="filters.status" placeholder="全部" clearable>
            <el-option label="执行中" value="executing" />
            <el-option label="已完成" value="completed" />
            <el-option label="部分失败" value="partial_failure" />
            <el-option label="失败" value="failed" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="filters.dateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DDTHH:mm:ss"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 执行记录列表 -->
    <el-card shadow="hover" class="table-card">
      <el-table
        :data="executions"
        stripe
        border
        v-loading="loading"
        @row-click="handleRowClick"
        row-class-name="clickable-row"
      >
        <el-table-column prop="event_id" label="事件ID" width="180" show-overflow-tooltip />
        <el-table-column prop="policy_name" label="策略名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="trigger_source" label="触发来源" min-width="140" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="120" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="statusTag(row.status)">
              {{ statusText(row.status) }}
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
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        class="pagination"
        @size-change="loadExecutions"
        @current-change="loadExecutions"
      />
    </el-card>

    <!-- 执行详情抽屉 -->
    <el-drawer
      v-model="drawerVisible"
      title="执行详情"
      size="520px"
      direction="rtl"
    >
      <template v-if="currentExecution">
        <!-- 基本信息 -->
        <el-descriptions :column="1" border size="small" class="detail-desc">
          <el-descriptions-item label="事件ID">{{ currentExecution.event_id }}</el-descriptions-item>
          <el-descriptions-item label="策略名称">{{ currentExecution.policy_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="触发来源">{{ currentExecution.trigger_source }}</el-descriptions-item>
          <el-descriptions-item label="触发事件">{{ currentExecution.trigger_event }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag size="small" :type="statusTag(currentExecution.status)">
              {{ statusText(currentExecution.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ currentExecution.started_at }}</el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ currentExecution.completed_at || '-' }}</el-descriptions-item>
          <el-descriptions-item label="总耗时">
            {{ currentExecution.total_duration_ms != null ? currentExecution.total_duration_ms + ' ms' : '-' }}
          </el-descriptions-item>
        </el-descriptions>

        <!-- 动作执行时间线 -->
        <div class="timeline-section">
          <h4 class="timeline-title">动作执行日志</h4>
          <el-timeline v-if="currentExecution.logs && currentExecution.logs.length">
            <el-timeline-item
              v-for="log in currentExecution.logs"
              :key="log.id"
              :type="logTimelineType(log.status)"
              :timestamp="log.started_at"
              placement="top"
            >
              <div class="log-card">
                <div class="log-header">
                  <el-tag size="small" :type="logStatusTag(log.status)">
                    {{ logStatusText(log.status) }}
                  </el-tag>
                  <span class="log-action-type">{{ log.action_type }}</span>
                  <span v-if="log.duration_ms != null" class="log-duration">{{ log.duration_ms }} ms</span>
                </div>
                <div v-if="log.error_message" class="log-error">
                  {{ log.error_message }}
                </div>
              </div>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无执行日志" :image-size="60" />
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import {
  getLinkageExecutions,
  getLinkageExecution,
  type LinkageExecution
} from '@/api/modules/linkage'

// ==================== 列表数据 ====================
const loading = ref(false)
const executions = ref<LinkageExecution[]>([])
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })
const filters = reactive({
  policy_name: '',
  status: '',
  dateRange: null as [string, string] | null
})

async function loadExecutions() {
  loading.value = true
  try {
    const params: Record<string, string | number> = {
      page: pagination.page,
      page_size: pagination.pageSize
    }
    if (filters.policy_name) params.policy_name = filters.policy_name
    if (filters.status) params.status = filters.status
    if (filters.dateRange && filters.dateRange.length === 2) {
      params.start_time = filters.dateRange[0]
      params.end_time = filters.dateRange[1]
    }
    const result = await getLinkageExecutions(params)
    executions.value = result.items || []
    pagination.total = result.total || 0
  } catch {
    ElMessage.error('加载执行记录失败')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pagination.page = 1
  loadExecutions()
}

function resetFilters() {
  filters.policy_name = ''
  filters.status = ''
  filters.dateRange = null
  pagination.page = 1
  loadExecutions()
}

// ==================== 详情抽屉 ====================
const drawerVisible = ref(false)
const currentExecution = ref<LinkageExecution | null>(null)

async function handleRowClick(row: LinkageExecution) {
  try {
    const detail = await getLinkageExecution(row.id)
    currentExecution.value = detail
    drawerVisible.value = true
  } catch {
    ElMessage.error('加载执行详情失败')
  }
}

// ==================== 辅助函数 ====================
function statusText(status: string): string {
  const map: Record<string, string> = {
    executing: '执行中',
    completed: '已完成',
    partial_failure: '部分失败',
    failed: '失败'
  }
  return map[status] || status
}

function statusTag(status: string): 'success' | 'warning' | 'info' | 'danger' {
  const map: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    executing: 'info',
    completed: 'success',
    partial_failure: 'warning',
    failed: 'danger'
  }
  return map[status] || 'info'
}

function logStatusText(status: string): string {
  const map: Record<string, string> = {
    pending: '待执行',
    running: '执行中',
    success: '成功',
    failed: '失败',
    skipped: '跳过',
    timeout: '超时'
  }
  return map[status] || status
}

function logStatusTag(status: string): 'success' | 'warning' | 'info' | 'danger' {
  const map: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    pending: 'info',
    running: 'info',
    success: 'success',
    failed: 'danger',
    skipped: 'info',
    timeout: 'warning'
  }
  return map[status] || 'info'
}

function logTimelineType(status: string): 'primary' | 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'danger' | 'info'> = {
    pending: 'info',
    running: 'primary',
    success: 'success',
    failed: 'danger',
    skipped: 'info',
    timeout: 'warning'
  }
  return map[status] || 'info'
}

// ==================== 生命周期 ====================
onMounted(() => {
  loadExecutions()
})
</script>

<style lang="scss" scoped>
@use '@/styles/_mixins-25d' as *;

.linkage-execution-page {
  height: 100%;
  padding: 16px;
  overflow-y: auto;
  @include page-list;
}

.filter-card {
  margin-bottom: 16px;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
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

.log-error {
  margin-top: 6px;
  padding: 6px 10px;
  background: var(--el-color-danger-light-9);
  border-radius: 4px;
  color: var(--el-color-danger);
  font-size: 12px;
  line-height: 1.5;
}
</style>
