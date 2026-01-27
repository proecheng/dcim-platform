<template>
  <div class="execution-management">
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stat-cards">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-value">{{ stats?.plans.total || 0 }}</div>
            <div class="stat-label">
              总计划数
              <el-tooltip content="所有状态的执行计划数量" placement="top">
                <el-icon class="info-icon"><InfoFilled /></el-icon>
              </el-tooltip>
            </div>
            <div class="stat-detail" v-if="stats?.plans.by_status">
              <span class="status-item pending">待执行: {{ stats.plans.by_status.pending?.count || 0 }}</span>
              <span class="status-item executing">执行中: {{ stats.plans.by_status.executing?.count || 0 }}</span>
              <span class="status-item completed">已完成: {{ stats.plans.by_status.completed?.count || 0 }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-value highlight">{{ formatMoney(stats?.plans.total_expected_saving || 0) }}</div>
            <div class="stat-label">
              预期年节省 (万元)
              <el-tooltip content="所有计划的预期年度节省总和，基于方案配置计算" placement="top">
                <el-icon class="info-icon"><InfoFilled /></el-icon>
              </el-tooltip>
            </div>
            <div class="stat-detail">&nbsp;</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-value success">{{ formatMoney(stats?.results.total_actual_saving || 0) }}</div>
            <div class="stat-label">
              实际年节省 (万元)
              <el-tooltip placement="top">
                <template #content>
                  <div style="max-width: 280px;">
                    <p>已完成追踪的计划实际年化节省总和</p>
                    <p style="margin-top: 4px; color: #aaa;">计算方式：基于追踪期实际电费变化年化计算</p>
                    <p style="margin-top: 4px; color: #aaa;">负荷转移方案：转移功率×时长×电价差×250工作日</p>
                  </div>
                </template>
                <el-icon class="info-icon"><InfoFilled /></el-icon>
              </el-tooltip>
            </div>
            <div class="stat-detail">
              {{ stats?.results.completed_count ? `已追踪: ${stats.results.completed_count} 个计划` : '暂无追踪' }}
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-value" :class="getAchievementClass(stats?.results.overall_achievement_rate)">
              {{ (stats?.results.overall_achievement_rate || 0).toFixed(1) }}%
            </div>
            <div class="stat-label">
              总体达成率
              <el-tooltip placement="top">
                <template #content>
                  <div style="max-width: 280px;">
                    <p>已追踪计划的实际节省 / 预期节省 × 100%</p>
                    <p style="margin-top: 4px; color: #aaa;">仅统计已完成效果追踪的计划</p>
                  </div>
                </template>
                <el-icon class="info-icon"><InfoFilled /></el-icon>
              </el-tooltip>
            </div>
            <div class="stat-detail">&nbsp;</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 计划列表 -->
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>执行计划</span>
          <div class="header-actions">
            <el-select v-model="statusFilter" placeholder="全部状态" clearable style="width: 120px;" @change="loadPlans">
              <el-option label="待执行" value="pending" />
              <el-option label="执行中" value="executing" />
              <el-option label="已完成" value="completed" />
              <el-option label="失败" value="failed" />
            </el-select>
          </div>
        </div>
      </template>

      <el-table :data="plans" v-loading="loading" stripe :row-class-name="getRowClassName">
        <el-table-column prop="id" label="ID" width="60">
          <template #default="{ row }">
            <span :data-plan-id="row.id">{{ row.id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="plan_name" label="计划名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="expected_saving" label="预期节省(元/年)" width="140">
          <template #default="{ row }">
            <span class="saving">{{ formatSaving(row.expected_saving) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getPlanStatusType(row.status)" size="small">
              {{ planStatusText[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160" />
        <el-table-column prop="started_at" label="开始时间" width="160" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="viewPlanDetail(row)">
              详情
            </el-button>
            <el-button
              v-if="row.status === 'pending'"
              type="success" link size="small"
              @click="startPlan(row)"
            >
              开始执行
            </el-button>
            <el-button
              v-if="row.status === 'completed'"
              type="warning" link size="small"
              @click="viewTracking(row)"
            >
              效果追踪
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper" v-if="total > pageSize">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="loadPlans"
        />
      </div>
    </el-card>

    <!-- 计划详情抽屉 -->
    <el-drawer
      v-model="detailVisible"
      size="700px"
      direction="rtl"
    >
      <template #header>
        <div class="drawer-header">
          <span>{{ currentPlan?.plan.plan_name || '计划详情' }}</span>
          <el-button
            v-if="canViewOriginalConfig"
            type="primary"
            link
            @click="goToOriginalConfig"
          >
            <el-icon><Setting /></el-icon>
            查看原配置
          </el-button>
        </div>
      </template>
      <div v-if="currentPlan" class="plan-detail">
        <!-- 进度概览 -->
        <div class="progress-section">
          <el-progress
            :percentage="currentPlan.progress_percentage"
            :stroke-width="20"
            :format="(p: number) => p.toFixed(0) + '%'"
          />
          <div class="progress-stats">
            <span>自动: {{ currentPlan.auto_task_count }}</span>
            <span>手动: {{ currentPlan.manual_task_count }}</span>
            <span>已完成: {{ currentPlan.task_stats.completed }}/{{ currentPlan.task_stats.total }}</span>
          </div>
        </div>

        <!-- 任务列表 -->
        <div class="task-list">
          <h4>任务清单</h4>
          <div v-for="task in currentPlan.tasks" :key="task.id" class="task-item">
            <div class="task-header">
              <el-tag :type="getTaskStatusType(task.status)" size="small">
                {{ taskStatusText[task.status] }}
              </el-tag>
              <el-tag size="small" :type="task.execution_mode === 'auto' ? 'success' : 'warning'">
                {{ task.execution_mode === 'auto' ? '自动' : '手动' }}
              </el-tag>
              <span class="task-name">{{ task.task_name }}</span>
            </div>
            <div class="task-meta">
              <span v-if="task.target_object">目标: {{ task.target_object }}</span>
              <span v-if="task.executed_at">执行: {{ task.executed_at }}</span>
            </div>
            <div class="task-actions" v-if="task.status === 'pending'">
              <el-button
                v-if="task.execution_mode === 'auto'"
                type="primary" size="small"
                @click="executeTask(task.id)"
              >
                执行
              </el-button>
              <el-button
                v-else
                type="success" size="small"
                @click="completeTask(task.id)"
              >
                标记完成
              </el-button>
            </div>
          </div>
        </div>

        <!-- 追踪结果 -->
        <div class="tracking-section" v-if="currentPlan.results.length">
          <h4>效果追踪</h4>
          <div v-for="result in currentPlan.results" :key="result.id" class="tracking-item">
            <div class="tracking-header">
              <el-tag :type="result.status === 'completed' ? 'success' : 'info'" size="small">
                {{ result.status === 'completed' ? '已完成' : '追踪中' }}
              </el-tag>
              <span>追踪周期: {{ result.tracking_period }}天</span>
            </div>
            <div class="tracking-data">
              <div class="data-item">
                <span class="label">实际节省</span>
                <span class="value">{{ result.actual_saving.toFixed(2) }} 元</span>
              </div>
              <div class="data-item">
                <span class="label">达成率</span>
                <span class="value" :class="getAchievementClass(result.achievement_rate)">
                  {{ result.achievement_rate.toFixed(1) }}%
                </span>
              </div>
            </div>
            <div class="tracking-conclusion" v-if="result.analysis_conclusion">
              {{ result.analysis_conclusion }}
            </div>
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Setting, InfoFilled } from '@element-plus/icons-vue'
import {
  getExecutionPlans,
  getExecutionPlanDetail,
  updatePlanStatus,
  executeAutoTask,
  completeManualTask,
  getExecutionStats,
  getTrackingData
} from '@/api/modules/opportunities'
import type { ExecutionPlan, PlanDetail, ExecutionStats } from '@/api/modules/opportunities'

const router = useRouter()
const route = useRoute()

const loading = ref(false)
const plans = ref<ExecutionPlan[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const statusFilter = ref('')
const stats = ref<ExecutionStats | null>(null)

const detailVisible = ref(false)
const currentPlan = ref<PlanDetail | null>(null)

// 高亮的计划ID（从URL query获取）
const highlightPlanId = ref<number | null>(null)

const planStatusText: Record<string, string> = {
  pending: '待执行',
  executing: '执行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消'
}

const taskStatusText: Record<string, string> = {
  pending: '待执行',
  executing: '执行中',
  completed: '已完成',
  failed: '失败',
  skipped: '已跳过'
}

onMounted(async () => {
  // 检查URL参数
  if (route.query.highlight) {
    highlightPlanId.value = parseInt(route.query.highlight as string)
  }

  await Promise.all([loadPlans(), loadStats()])

  // 如果有高亮计划，自动展开其详情
  if (highlightPlanId.value) {
    const plan = plans.value.find(p => p.id === highlightPlanId.value)
    if (plan) {
      viewPlanDetail(plan)
      // 滚动到该计划
      nextTick(() => {
        const row = document.querySelector(`[data-plan-id="${highlightPlanId.value}"]`)
        row?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      })
    }
  }
})

async function loadPlans() {
  loading.value = true
  try {
    const params: any = {
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value
    }
    if (statusFilter.value) params.status = statusFilter.value
    const res = await getExecutionPlans(params)
    if (res.code === 0 && res.data) {
      plans.value = res.data.items
      total.value = res.data.total
    }
  } catch {
    console.error('加载计划失败')
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    console.log('[Execution] Loading stats...')
    const res = await getExecutionStats()
    console.log('[Execution] Stats raw response:', res)

    // 检查响应格式
    if (res && res.code === 0 && res.data) {
      stats.value = res.data
      console.log('[Execution] Stats loaded successfully:', {
        total: stats.value?.plans?.total,
        expected: stats.value?.plans?.total_expected_saving,
        actual: stats.value?.results?.total_actual_saving,
        rate: stats.value?.results?.overall_achievement_rate
      })
    } else if (res && res.plans) {
      // 直接返回data的情况
      stats.value = res as any
      console.log('[Execution] Stats loaded (direct format):', stats.value)
    } else {
      console.error('[Execution] Invalid stats response format:', res)
    }
  } catch (error: any) {
    console.error('[Execution] 加载统计失败:', error?.message || error)
    console.error('[Execution] Error details:', error?.response?.data || error)
  }
}

async function viewPlanDetail(plan: ExecutionPlan) {
  try {
    const res = await getExecutionPlanDetail(plan.id)
    if (res.code === 0 && res.data) {
      currentPlan.value = res.data
      detailVisible.value = true
    }
  } catch {
    ElMessage.error('加载详情失败')
  }
}

async function startPlan(plan: ExecutionPlan) {
  try {
    await ElMessageBox.confirm('确定开始执行此计划？', '确认')
    const res = await updatePlanStatus(plan.id, { status: 'executing' })
    if (res.code === 0) {
      ElMessage.success('计划已开始执行')
      loadPlans()
    }
  } catch {
    // cancelled
  }
}

async function executeTask(taskId: number) {
  try {
    const res = await executeAutoTask(taskId)
    if (res.code === 0) {
      ElMessage.success('任务执行成功')
      // 刷新详情
      if (currentPlan.value) {
        const detailRes = await getExecutionPlanDetail(currentPlan.value.plan.id)
        if (detailRes.code === 0 && detailRes.data) {
          currentPlan.value = detailRes.data
        }
      }
    }
  } catch {
    ElMessage.error('任务执行失败')
  }
}

async function completeTask(taskId: number) {
  try {
    const res = await completeManualTask(taskId)
    if (res.code === 0) {
      ElMessage.success('任务已完成')
      if (currentPlan.value) {
        const detailRes = await getExecutionPlanDetail(currentPlan.value.plan.id)
        if (detailRes.code === 0 && detailRes.data) {
          currentPlan.value = detailRes.data
        }
      }
    }
  } catch {
    ElMessage.error('操作失败')
  }
}

async function viewTracking(plan: ExecutionPlan) {
  try {
    const res = await getTrackingData(plan.id)
    if (res.code === 0) {
      await viewPlanDetail(plan)
    }
  } catch {
    ElMessage.warning('暂无追踪数据')
  }
}

function formatMoney(value: number): string {
  return (value / 10000).toFixed(2)
}

function formatSaving(value: number): string {
  if (value >= 10000) return (value / 10000).toFixed(1) + '万'
  return value.toFixed(0)
}

function getPlanStatusType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
    pending: 'info',
    executing: 'warning',
    completed: 'success',
    failed: 'danger',
    cancelled: 'info'
  }
  return map[status] || 'info'
}

function getTaskStatusType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
    pending: 'info',
    executing: 'warning',
    completed: 'success',
    failed: 'danger',
    skipped: 'info'
  }
  return map[status] || 'info'
}

function getAchievementClass(rate?: number): string {
  if (!rate) return ''
  if (rate >= 100) return 'excellent'
  if (rate >= 80) return 'good'
  if (rate >= 50) return 'medium'
  return 'low'
}

function getRowClassName({ row }: { row: any }) {
  if (row.id === highlightPlanId.value) {
    return 'highlight-row'
  }
  return ''
}

// 判断是否可以查看原配置
const canViewOriginalConfig = computed(() => {
  if (!currentPlan.value?.opportunity) return false
  return !!currentPlan.value.opportunity.source_plugin && !!currentPlan.value.opportunity.analysis_data
})

// 跳转到原配置页面
function goToOriginalConfig() {
  if (!currentPlan.value?.opportunity?.analysis_data) return

  const sourcePlugin = currentPlan.value.opportunity.source_plugin
  const planId = currentPlan.value.plan.id.toString()

  // 根据不同的来源插件跳转到不同页面
  switch (sourcePlugin) {
    case 'peak_valley_optimizer':
      // 负荷转移分析
      router.push({
        path: '/energy/analysis',
        query: {
          tab: 'shift',
          plan_id: planId,
          restore: 'true'
        }
      })
      break

    case 'demand_controller':
      // 需量控制分析
      router.push({
        path: '/energy/analysis',
        query: {
          tab: 'demand',
          plan_id: planId,
          restore: 'true'
        }
      })
      break

    case 'device_optimizer':
      // 设备运行优化
      router.push({
        path: '/energy/analysis',
        query: {
          tab: 'device',
          plan_id: planId,
          restore: 'true'
        }
      })
      break

    case 'vpp_response':
      // VPP需求响应
      router.push({
        path: '/vpp/response',
        query: {
          plan_id: planId,
          restore: 'true'
        }
      })
      break

    case 'dispatch_scheduler':
      // 日前调度优化
      router.push({
        path: '/optimization/schedule',
        query: {
          plan_id: planId,
          restore: 'true'
        }
      })
      break

    default:
      ElMessage.warning('该方案类型暂不支持查看原配置')
  }
}
</script>

<style scoped lang="scss">
.execution-management {
  .stat-cards {
    margin-bottom: 20px;
  }

  .stat-card {
    background: var(--bg-card-solid, #1a2a4a);
    height: 140px; // 固定高度确保对齐

    :deep(.el-card__body) {
      height: 100%;
      padding: 20px;
    }

    .stat-content {
      text-align: center;
      height: 100%;
      display: flex;
      flex-direction: column;
      justify-content: center;

      .stat-value {
        font-size: 28px;
        font-weight: bold;
        color: var(--text-primary, rgba(255, 255, 255, 0.95));

        &.highlight { color: var(--primary-color, #1890ff); }
        &.success { color: var(--success-color, #52c41a); }
        &.excellent { color: #52c41a; }
        &.good { color: #1890ff; }
        &.medium { color: #faad14; }
        &.low { color: #f5222d; }
      }

      .stat-label {
        font-size: 14px;
        color: var(--text-secondary, rgba(255, 255, 255, 0.65));
        margin-top: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 4px;

        .info-icon {
          font-size: 12px;
          color: rgba(255, 255, 255, 0.45);
          cursor: help;

          &:hover {
            color: var(--primary-color, #1890ff);
          }
        }
      }

      .stat-detail {
        font-size: 12px;
        color: var(--text-tertiary, rgba(255, 255, 255, 0.45));
        margin-top: 8px;
        min-height: 18px; // 固定最小高度，即使没有内容也占位
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;

        .status-item {
          &.pending { color: var(--info-color, #909399); }
          &.executing { color: var(--warning-color, #faad14); }
          &.completed { color: var(--success-color, #52c41a); }
        }
      }
    }
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .saving {
    color: var(--success-color, #52c41a);
    font-weight: 500;
  }

  .pagination-wrapper {
    margin-top: 16px;
    display: flex;
    justify-content: flex-end;
  }
}

.plan-detail {
  .progress-section {
    background: rgba(13, 27, 42, 0.5);
    border: 1px solid rgba(64, 158, 255, 0.15);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 24px;

    .progress-stats {
      display: flex;
      gap: 24px;
      margin-top: 12px;
      color: var(--text-secondary, rgba(255, 255, 255, 0.65));
    }
  }

  h4 {
    font-size: 16px;
    margin-bottom: 16px;
    color: rgba(255, 255, 255, 0.95);
    font-weight: 500;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(64, 158, 255, 0.2);
  }

  .task-list {
    background: rgba(0, 0, 0, 0.2);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 20px;
  }

  .task-item {
    background: rgba(13, 27, 42, 0.5);
    border: 1px solid rgba(64, 158, 255, 0.2);
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 12px;
    transition: all 0.3s ease;

    &:hover {
      background: rgba(13, 27, 42, 0.7);
      border-color: rgba(64, 158, 255, 0.4);
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
    }

    .task-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;

      .task-name {
        font-weight: 500;
        color: var(--text-primary, rgba(255, 255, 255, 0.95));
      }
    }

    .task-meta {
      display: flex;
      gap: 16px;
      font-size: 13px;
      color: var(--text-secondary, rgba(255, 255, 255, 0.65));
      margin-bottom: 8px;
    }

    .task-actions {
      display: flex;
      gap: 8px;
    }
  }

  .tracking-section {
    margin-top: 24px;
    padding: 16px;
    background: rgba(0, 0, 0, 0.2);
    border-radius: 8px;
    border-top: none;
  }

  .tracking-item {
    background: linear-gradient(135deg, rgba(13, 27, 42, 0.6) 0%, rgba(27, 38, 59, 0.6) 100%);
    border: 1px solid rgba(64, 158, 255, 0.2);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
    transition: all 0.3s ease;

    &:hover {
      border-color: rgba(64, 158, 255, 0.4);
      box-shadow: 0 2px 12px rgba(64, 158, 255, 0.1);
    }

    .tracking-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 12px;
    }

    .tracking-data {
      display: flex;
      gap: 32px;

      .data-item {
        .label {
          color: var(--text-secondary, rgba(255, 255, 255, 0.65));
          margin-right: 8px;
        }

        .value {
          font-weight: 600;
          color: var(--text-primary, rgba(255, 255, 255, 0.95));

          &.excellent { color: #52c41a; }
          &.good { color: #1890ff; }
          &.medium { color: #faad14; }
          &.low { color: #f5222d; }
        }
      }
    }

    .tracking-conclusion {
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px dashed var(--border-color, rgba(255, 255, 255, 0.1));
      color: var(--text-secondary, rgba(255, 255, 255, 0.65));
      font-size: 13px;
    }
  }
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

// 深色科技风 - 覆盖 el-drawer 默认白色背景
:deep(.el-drawer) {
  background: linear-gradient(180deg, #0d1b2a 0%, #1b263b 100%) !important;
  border-left: 1px solid rgba(64, 158, 255, 0.2);
  box-shadow: -4px 0 20px rgba(0, 0, 0, 0.5);

  .el-drawer__header {
    background: rgba(13, 27, 42, 0.95);
    border-bottom: 1px solid rgba(64, 158, 255, 0.15);
    padding: 16px 20px;
    margin-bottom: 0;

    .el-drawer__title {
      color: rgba(255, 255, 255, 0.95);
      font-size: 16px;
      font-weight: 500;
    }

    .el-drawer__close-btn {
      color: rgba(255, 255, 255, 0.65);

      &:hover {
        color: #409eff;
      }
    }
  }

  .el-drawer__body {
    background: transparent;
    padding: 20px;
    color: rgba(255, 255, 255, 0.85);
  }
}

// 深色科技风 - 进度条样式
:deep(.el-progress) {
  .el-progress-bar__outer {
    background-color: rgba(255, 255, 255, 0.1);
  }

  .el-progress-bar__inner {
    background: linear-gradient(90deg, #1890ff 0%, #52c41a 100%);
  }

  .el-progress__text {
    color: rgba(255, 255, 255, 0.85);
  }
}

:deep(.highlight-row) {
  background-color: rgba(64, 158, 255, 0.1) !important;
  animation: highlight-fade 3s ease-out;
}

@keyframes highlight-fade {
  0% {
    background-color: rgba(64, 158, 255, 0.3);
  }
  100% {
    background-color: rgba(64, 158, 255, 0.1);
  }
}
</style>
