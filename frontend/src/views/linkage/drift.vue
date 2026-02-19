<template>
  <div class="drift-detection-page">
    <!-- 概览卡片 -->
    <el-row :gutter="16" class="summary-row">
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-number">{{ summary.total_checked }}</div>
          <div class="summary-label">总检测</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card summary-card--warning">
          <div class="summary-number">{{ summary.suspected_count }}</div>
          <div class="summary-label">疑似漂移</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card summary-card--danger">
          <div class="summary-number">{{ summary.confirmed_count }}</div>
          <div class="summary-label">确认漂移</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card summary-card--success">
          <div class="summary-number">{{ summary.resolved_count }}</div>
          <div class="summary-label">已解除</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 结果表格 -->
    <el-card shadow="hover" class="table-card">
      <div class="section-header">
        <span class="section-title">漂移检测结果</span>
        <div class="filter-bar">
          <el-select
            v-model="statusFilter"
            placeholder="状态筛选"
            clearable
            style="width: 140px"
            @change="loadResults"
          >
            <el-option label="疑似漂移" value="suspected" />
            <el-option label="确认漂移" value="confirmed" />
            <el-option label="已解除" value="resolved" />
          </el-select>
          <el-button
            type="primary"
            :loading="detecting"
            @click="handleTriggerDetection"
          >
            触发检测
          </el-button>
        </div>
      </div>
      <el-table
        :data="results"
        stripe
        border
        v-loading="loadingResults"
        row-key="id"
      >
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="point_code" label="点位编码" min-width="120" show-overflow-tooltip />
        <el-table-column prop="point_name" label="点位名称" min-width="140" show-overflow-tooltip />
        <el-table-column prop="area_code" label="区域" width="100" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.area_code || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="statusTagType(row.status)">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="偏差(σ)" width="100" align="center">
          <template #default="{ row }">
            <span :class="{ 'deviation-high': row.deviation_sigma > 5.0 }">
              {{ row.deviation_sigma.toFixed(1) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="交叉验证" width="100" align="center">
          <template #default="{ row }">
            <el-tag
              v-if="row.cross_validation_result"
              size="small"
              :type="crossValidationTagType(row.cross_validation_result)"
            >
              {{ crossValidationText(row.cross_validation_result) }}
            </el-tag>
            <span v-else class="no-action">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="diagnosis" label="诊断建议" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.diagnosis || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="检测时间" width="180" show-overflow-tooltip>
          <template #default="{ row }">
            {{ formatDate(row.detected_at || row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'suspected' || row.status === 'confirmed'"
              type="success"
              size="small"
              @click="handleResolve(row)"
            >
              解除
            </el-button>
            <span v-else class="no-action">-</span>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        class="pagination"
        @size-change="loadResults"
        @current-change="loadResults"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import {
  triggerDriftDetection,
  getDriftResults,
  resolveDrift,
  getDriftSummary,
} from '@/api/modules/drift'
import type {
  DriftDetectionResult,
  DriftDetectionSummary,
} from '@/api/modules/drift'

// ==================== 概览数据 ====================
const summary = reactive<DriftDetectionSummary>({
  total_checked: 0,
  suspected_count: 0,
  confirmed_count: 0,
  resolved_count: 0,
  skipped_count: 0,
})

async function loadSummary() {
  try {
    const result = await getDriftSummary()
    Object.assign(summary, result)
  } catch {
    ElMessage.error('加载概览数据失败')
  }
}

// ==================== 检测结果列表 ====================
const loadingResults = ref(false)
const results = ref<DriftDetectionResult[]>([])
const statusFilter = ref('')
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })

async function loadResults() {
  loadingResults.value = true
  try {
    const params: Record<string, unknown> = {
      page: pagination.page,
      page_size: pagination.pageSize,
    }
    if (statusFilter.value) {
      params.status = statusFilter.value
    }
    const result = await getDriftResults(params as any)
    results.value = result.items || []
    pagination.total = result.total || 0
  } catch {
    ElMessage.error('加载检测结果失败')
  } finally {
    loadingResults.value = false
  }
}

// ==================== 触发检测 ====================
const detecting = ref(false)

async function handleTriggerDetection() {
  detecting.value = true
  try {
    const res = await triggerDriftDetection()
    ElMessage.success(
      res.message || `检测完成: 检查 ${res.total_checked} 个点位, 新增疑似 ${res.new_suspected}, 确认 ${res.new_confirmed}`
    )
    loadSummary()
    loadResults()
  } catch {
    ElMessage.error('触发检测失败')
  } finally {
    detecting.value = false
  }
}

// ==================== 解除漂移 ====================
async function handleResolve(row: DriftDetectionResult) {
  try {
    await ElMessageBox.confirm(
      `确认解除点位 "${row.point_name}" (${row.point_code}) 的漂移标记？`,
      '解除确认',
      { confirmButtonText: '确认解除', cancelButtonText: '取消', type: 'warning' }
    )
    await resolveDrift(row.id)
    ElMessage.success('已解除漂移标记')
    loadSummary()
    loadResults()
  } catch (e: any) {
    if (e !== 'cancel' && e?.toString() !== 'cancel') {
      ElMessage.error('解除操作失败')
    }
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

function statusText(status: string): string {
  const map: Record<string, string> = {
    suspected: '疑似漂移',
    confirmed: '确认漂移',
    resolved: '已解除',
  }
  return map[status] || status
}

function statusTagType(status: string): 'success' | 'warning' | 'info' | 'danger' {
  const map: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    suspected: 'warning',
    confirmed: 'danger',
    resolved: 'success',
  }
  return map[status] || 'info'
}

function crossValidationText(result: string): string {
  const map: Record<string, string> = {
    pass: '通过',
    fail: '未通过',
    skipped: '跳过',
  }
  return map[result] || result
}

function crossValidationTagType(result: string): 'success' | 'warning' | 'info' | 'danger' {
  const map: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    pass: 'success',
    fail: 'danger',
    skipped: 'info',
  }
  return map[result] || 'info'
}

// ==================== 生命周期 ====================
onMounted(() => {
  loadSummary()
  loadResults()
})
</script>

<style lang="scss" scoped>
@use '@/styles/_mixins-25d' as *;

.drift-detection-page {
  height: 100%;
  padding: 16px;
  overflow-y: auto;
  @include page-list;
}

.summary-row {
  margin-bottom: 16px;
}

.summary-card {
  text-align: center;
  padding: 8px 0;

  .summary-number {
    font-size: 28px;
    font-weight: 700;
    color: var(--el-text-color-primary);
    line-height: 1.4;
  }

  .summary-label {
    font-size: 13px;
    color: var(--el-text-color-secondary);
    margin-top: 4px;
  }

  &--warning .summary-number {
    color: var(--el-color-warning);
  }

  &--danger .summary-number {
    color: var(--el-color-danger);
  }

  &--success .summary-number {
    color: var(--el-color-success);
  }
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

.deviation-high {
  color: var(--el-color-danger);
  font-weight: 600;
}
</style>
