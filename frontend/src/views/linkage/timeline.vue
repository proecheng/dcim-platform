<template>
  <div class="linkage-timeline-page">
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
        highlight-current-row
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
        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click.stop="handleViewTimeline(row)">
              时间线
            </el-button>
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

    <!-- 时间线详情抽屉 -->
    <el-drawer
      v-model="drawerVisible"
      title="事件时间线报告"
      size="600px"
      direction="rtl"
    >
      <template v-if="timelineReport">
        <!-- 事件概要 -->
        <el-descriptions :column="2" border size="small" class="detail-desc">
          <el-descriptions-item label="事件ID" :span="2">{{ timelineReport.event_id }}</el-descriptions-item>
          <el-descriptions-item label="策略名称">{{ timelineReport.policy_name }}</el-descriptions-item>
          <el-descriptions-item label="级别">
            <el-tag size="small" :type="levelTag(timelineReport.level)">
              {{ levelText(timelineReport.level) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="触发来源">{{ timelineReport.trigger_source || '-' }}</el-descriptions-item>
          <el-descriptions-item label="触发时间">{{ formatTime(timelineReport.trigger_time) }}</el-descriptions-item>
          <el-descriptions-item label="总耗时">
            {{ timelineReport.total_duration_ms != null ? timelineReport.total_duration_ms + ' ms' : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="恢复耗时">
            {{ timelineReport.recovery_time_ms != null ? timelineReport.recovery_time_ms + ' ms' : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="操作人">{{ timelineReport.operator || '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag size="small" :type="statusTag(timelineReport.status)">
              {{ statusText(timelineReport.status) }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>

        <!-- 导出按钮 -->
        <div class="export-bar">
          <el-button type="primary" :icon="Download" :loading="exporting" @click="handleExport">
            导出 Excel
          </el-button>
        </div>

        <!-- 时间线 -->
        <div class="timeline-section">
          <h4 class="timeline-title">完整时间线</h4>
          <el-timeline v-if="timelineReport.events.length">
            <el-timeline-item
              v-for="(evt, idx) in timelineReport.events"
              :key="idx"
              :type="eventTimelineType(evt.status)"
              :timestamp="formatTime(evt.timestamp)"
              placement="top"
            >
              <div class="event-card">
                <div class="event-header">
                  <el-tag size="small" :type="phaseTag(evt.phase)" effect="plain">
                    {{ phaseText(evt.phase) }}
                  </el-tag>
                  <span class="event-type">{{ evt.event_type }}</span>
                  <el-tag size="small" :type="eventStatusTag(evt.status)">
                    {{ eventStatusText(evt.status) }}
                  </el-tag>
                  <span v-if="evt.duration_ms != null" class="event-duration">{{ evt.duration_ms }} ms</span>
                </div>
                <div class="event-detail">{{ evt.detail }}</div>
              </div>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无时间线数据" :image-size="60" />
        </div>
      </template>

      <div v-else-if="timelineLoading" v-loading="true" class="loading-placeholder" />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { Download } from '@element-plus/icons-vue'
import {
  getLinkageExecutions,
  getEventTimeline,
  exportEventTimeline,
  type LinkageExecution,
  type TimelineReport,
} from '@/api/modules/linkage'

// ==================== 列表数据 ====================
const loading = ref(false)
const executions = ref<LinkageExecution[]>([])
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })
const filters = reactive({
  policy_name: '',
  status: '',
  dateRange: null as [string, string] | null,
})

async function loadExecutions() {
  loading.value = true
  try {
    const params: Record<string, string | number> = {
      page: pagination.page,
      page_size: pagination.pageSize,
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

// ==================== 时间线详情 ====================
const drawerVisible = ref(false)
const timelineReport = ref<TimelineReport | null>(null)
const timelineLoading = ref(false)
const exporting = ref(false)
const currentExecutionId = ref<number | null>(null)

function handleRowClick(row: LinkageExecution) {
  handleViewTimeline(row)
}

async function handleViewTimeline(row: LinkageExecution) {
  currentExecutionId.value = row.id
  timelineReport.value = null
  timelineLoading.value = true
  drawerVisible.value = true
  try {
    timelineReport.value = await getEventTimeline(row.id)
  } catch {
    ElMessage.error('加载时间线报告失败')
  } finally {
    timelineLoading.value = false
  }
}

async function handleExport() {
  if (currentExecutionId.value == null) return
  exporting.value = true
  try {
    const blob = await exportEventTimeline(currentExecutionId.value)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `timeline_${timelineReport.value?.event_id || currentExecutionId.value}.xlsx`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch {
    ElMessage.error('导出失败')
  } finally {
    exporting.value = false
  }
}

// ==================== 辅助函数 ====================
function statusText(status: string): string {
  const map: Record<string, string> = {
    executing: '执行中',
    completed: '已完成',
    partial_failure: '部分失败',
    partial_recovery: '部分恢复',
    failed: '失败',
  }
  return map[status] || status
}

function statusTag(status: string): 'success' | 'warning' | 'info' | 'danger' {
  const map: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    executing: 'info',
    completed: 'success',
    partial_failure: 'warning',
    partial_recovery: 'warning',
    failed: 'danger',
  }
  return map[status] || 'info'
}

function levelText(level: string): string {
  const map: Record<string, string> = {
    fire_signal: '消防信号',
    critical: '关键',
    normal: '普通',
  }
  return map[level] || level
}

function levelTag(level: string): 'success' | 'warning' | 'info' | 'danger' {
  const map: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    fire_signal: 'danger',
    critical: 'warning',
    normal: 'info',
  }
  return map[level] || 'info'
}

function phaseText(phase: string): string {
  const map: Record<string, string> = {
    trigger: '触发',
    action: '联动动作',
    recovery: '恢复',
  }
  return map[phase] || phase
}

function phaseTag(phase: string): 'success' | 'warning' | 'info' | 'danger' {
  const map: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    trigger: 'danger',
    action: 'info',
    recovery: 'success',
  }
  return map[phase] || 'info'
}

function eventStatusText(status: string): string {
  const map: Record<string, string> = {
    success: '成功',
    failed: '失败',
    timeout: '超时',
    skipped: '跳过',
    pending: '待执行',
    executing: '执行中',
    completed: '已完成',
    partial_failure: '部分失败',
    partial_recovery: '部分恢复',
  }
  return map[status] || status
}

function eventStatusTag(status: string): 'success' | 'warning' | 'info' | 'danger' {
  const map: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    success: 'success',
    completed: 'success',
    failed: 'danger',
    timeout: 'warning',
    skipped: 'info',
    pending: 'info',
    executing: 'info',
    partial_failure: 'warning',
    partial_recovery: 'warning',
  }
  return map[status] || 'info'
}

function eventTimelineType(status: string): 'primary' | 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'danger' | 'info'> = {
    success: 'success',
    completed: 'success',
    failed: 'danger',
    timeout: 'warning',
    skipped: 'info',
    pending: 'info',
    executing: 'primary',
    partial_failure: 'warning',
    partial_recovery: 'warning',
  }
  return map[status] || 'info'
}

function formatTime(time: string | null | undefined): string {
  if (!time) return '-'
  try {
    const d = new Date(time)
    const pad = (n: number) => String(n).padStart(2, '0')
    const ms = String(d.getMilliseconds()).padStart(3, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${ms}`
  } catch {
    return time || '-'
  }
}

// ==================== 生命周期 ====================
onMounted(() => {
  loadExecutions()
})
</script>

<style lang="scss" scoped>
@use '@/styles/_mixins-25d' as *;

.linkage-timeline-page {
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
  margin-bottom: 16px;
}

.export-bar {
  margin-bottom: 16px;
  display: flex;
  justify-content: flex-end;
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

.event-card {
  padding: 6px 0;
}

.event-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.event-type {
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.event-duration {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  margin-left: auto;
}

.event-detail {
  margin-top: 6px;
  padding: 6px 10px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
  color: var(--el-text-color-regular);
  font-size: 13px;
  line-height: 1.5;
}

.loading-placeholder {
  min-height: 200px;
}
</style>
