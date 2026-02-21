<template>
  <div class="fire-linkage-page">
    <!-- 顶部统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6" v-for="card in statCards" :key="card.label">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" :style="{ background: card.iconBg }">
              <el-icon :size="22"><component :is="card.icon" /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value" :class="card.valueClass">{{ card.value }}</div>
              <div class="stat-label">{{ card.label }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 策略配置区域 -->
    <el-card shadow="hover" class="section-card policy-section">
      <template #header>
        <div class="card-header">
          <el-icon :size="18"><Connection /></el-icon>
          <span>联动策略配置</span>
          <el-tag size="small" type="info" effect="plain" style="margin-left: 8px;">{{ totalPolicies }} 条</el-tag>
          <el-button type="primary" link @click="fetchPolicies" style="margin-left: auto;">刷新</el-button>
        </div>
      </template>
      <div v-loading="policiesLoading">
        <div
          v-for="policy in policies"
          :key="policy.id"
          class="policy-item"
          :class="{
            'policy-alarm': policyLevel(policy) === 'alarm',
            'policy-warning': policyLevel(policy) === 'warning',
            'policy-expanded': expandedPolicyId === policy.id,
          }"
        >
          <div class="policy-header" @click="togglePolicy(policy.id)">
            <div class="policy-info">
              <span class="policy-name">{{ policy.name }}</span>
              <el-tag :type="policyLevel(policy) === 'alarm' ? 'danger' : 'warning'" size="small" effect="dark">
                {{ policyLevel(policy) === 'alarm' ? '联动级' : '预警级' }}
              </el-tag>
              <el-tag size="small" type="info" effect="plain">{{ fmtTrigger(policy.trigger_type) }}</el-tag>
            </div>
            <div class="policy-meta">
              <span class="action-count">
                <el-icon :size="14"><Operation /></el-icon>
                {{ policy.actions?.length || 0 }} 个动作
              </span>
              <el-tag :type="policy.is_enabled ? 'success' : 'info'" size="small" :effect="policy.is_enabled ? 'dark' : 'plain'">
                {{ policy.is_enabled ? '已启用' : '未启用' }}
              </el-tag>
              <el-icon :size="16" class="expand-icon">
                <ArrowDown v-if="expandedPolicyId !== policy.id" />
                <ArrowUp v-else />
              </el-icon>
            </div>
          </div>
          <!-- 联动动作链可视化 -->
          <transition name="expand">
            <div v-if="expandedPolicyId === policy.id" class="action-chain-wrapper">
              <div class="action-chain">
                <div class="chain-node trigger-node">
                  <div class="node-icon"><el-icon :size="20"><Warning /></el-icon></div>
                  <div class="node-label">触发条件</div>
                  <div class="node-detail">{{ fmtTrigger(policy.trigger_type) }}</div>
                </div>
                <div class="chain-arrow" />
                <template v-for="(action, idx) in sortedActions(policy)" :key="action.id">
                  <div class="chain-node action-node" :class="{ 'node-warning': policyLevel(policy) === 'warning', 'node-alarm': policyLevel(policy) === 'alarm' }">
                    <div class="node-icon"><el-icon :size="20"><component :is="actionIcon(action.action_type)" /></el-icon></div>
                    <div class="node-label">{{ ACTION_LABELS[action.action_type] || action.action_type }}</div>
                    <div class="node-detail">{{ extractTarget(action.action_config) }}</div>
                    <div class="node-timeout" v-if="action.timeout_seconds">{{ action.timeout_seconds }}s</div>
                  </div>
                  <div class="chain-arrow" v-if="idx < (policy.actions?.length || 0) - 1" />
                </template>
                <div class="chain-arrow" />
                <div class="chain-node notify-node">
                  <div class="node-icon"><el-icon :size="20"><Bell /></el-icon></div>
                  <div class="node-label">通知</div>
                  <div class="node-detail">告警推送</div>
                </div>
              </div>
            </div>
          </transition>
        </div>
        <el-empty v-if="!policiesLoading && policies.length === 0" description="暂无联动策略" :image-size="60" />
      </div>
    </el-card>

    <!-- 执行历史区域 -->
    <el-card shadow="hover" class="section-card history-section">
      <template #header>
        <div class="card-header">
          <el-icon :size="18"><Clock /></el-icon>
          <span>执行历史</span>
          <el-tag size="small" type="info" effect="plain" style="margin-left: 8px;">{{ executionTotal }} 条</el-tag>
          <el-button type="primary" link @click="fetchExecutions" style="margin-left: auto;">刷新</el-button>
        </div>
      </template>
      <el-table :data="executions" stripe v-loading="executionsLoading" @expand-change="handleExpandChange" row-key="id">
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="timeline-wrapper" v-loading="executionDetailLoading">
              <template v-if="executionDetails.get(row.id)">
                <el-timeline>
                  <el-timeline-item
                    v-for="log in executionDetails.get(row.id)?.logs || []"
                    :key="log.id"
                    :timestamp="fmtTime(log.started_at)"
                    placement="top"
                    :color="log.status === 'success' ? '#52c41a' : log.status === 'failed' ? '#f5222d' : '#1890ff'"
                    :hollow="log.status === 'success'"
                    size="large"
                  >
                    <div class="timeline-event-card" :class="{ 'event-failed': log.status === 'failed' }">
                      <div class="event-header">
                        <span class="event-action">{{ ACTION_LABELS[log.action_type] || log.action_type }}</span>
                        <el-tag :type="log.status === 'success' ? 'success' : log.status === 'failed' ? 'danger' : 'primary'" size="small" effect="dark">
                          {{ log.status === 'success' ? '成功 ✓' : log.status === 'failed' ? '失败 ✗' : log.status }}
                        </el-tag>
                        <span class="event-duration" v-if="log.duration_ms != null">{{ fmtDuration(log.duration_ms) }}</span>
                      </div>
                      <div v-if="log.error_message" class="event-error">
                        <el-icon :size="12"><Warning /></el-icon>
                        {{ log.error_message }}
                      </div>
                    </div>
                  </el-timeline-item>
                </el-timeline>
                <!-- 恢复状态 -->
                <div class="recovery-section" v-if="executionRecoveries.get(row.id)?.length">
                  <div class="recovery-header"><el-icon :size="14"><RefreshRight /></el-icon>恢复状态</div>
                  <div v-for="recovery in executionRecoveries.get(row.id)" :key="recovery.id" class="recovery-item">
                    <el-tag :type="recovery.status === 'completed' ? 'success' : recovery.status === 'executing' ? 'primary' : 'warning'" size="small">
                      {{ recovery.status === 'completed' ? '已恢复' : recovery.status === 'executing' ? '恢复中' : '待恢复' }}
                    </el-tag>
                    <div class="recovery-steps" v-if="recovery.logs?.length">
                      <el-progress :percentage="recoveryProgress(recovery)" :stroke-width="6" :color="recovery.status === 'completed' ? '#52c41a' : '#1890ff'" style="width: 200px;" />
                      <span class="recovery-step-text">{{ recoveryDoneCount(recovery) }}/{{ recovery.logs.length }} 步骤完成</span>
                    </div>
                  </div>
                </div>
                <div class="recovery-section" v-else-if="executionRecoveries.has(row.id)">
                  <div class="recovery-header"><el-icon :size="14"><RefreshRight /></el-icon>恢复状态</div>
                  <el-tag type="info" size="small">无恢复记录</el-tag>
                </div>
              </template>
              <el-empty v-else description="加载中..." :image-size="40" />
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="started_at" label="触发时间" min-width="170">
          <template #default="{ row }">{{ fmtTime(row.started_at) }}</template>
        </el-table-column>
        <el-table-column prop="trigger_source" label="触发源" min-width="140">
          <template #default="{ row }">{{ row.trigger_source || '--' }}</template>
        </el-table-column>
        <el-table-column label="联动级别" width="100">
          <template #default="{ row }">
            <el-tag :type="execLevel(row) === 'alarm' ? 'danger' : 'warning'" size="small" effect="dark">
              {{ execLevel(row) === 'alarm' ? '联动' : '预警' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="执行结果" width="120">
          <template #default="{ row }">
            <el-tag :type="fmtStatus(row.status).type" size="small">{{ fmtStatus(row.status).label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="持续时间" width="110">
          <template #default="{ row }">{{ fmtDuration(row.total_duration_ms) }}</template>
        </el-table-column>
      </el-table>
      <div class="pagination-wrapper" v-if="executionTotal > executionPageSize">
        <el-pagination v-model:current-page="executionPage" :page-size="executionPageSize" :total="executionTotal" layout="total, prev, pager, next" @current-change="handlePageChange" />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import {
  Connection, Clock, Warning, Bell, ArrowDown, ArrowUp,
  Operation, Setting, VideoCamera, Monitor, Sunny,
  SwitchButton, Unlock, Promotion, RefreshRight,
} from '@element-plus/icons-vue'
import {
  useFireLinkageData,
  getLinkageLevel,
  formatExecutionStatus,
  formatDuration,
  formatTime,
  formatTriggerType,
  ACTION_TYPE_LABELS,
} from '@/composables/useFireLinkageData'
import type { LinkageAction, LinkageExecution, LinkagePolicy, LinkageRecovery } from '@/api/modules/linkage'

// ── composable 别名，模板中简短引用 ──
const policyLevel = getLinkageLevel
const fmtStatus = formatExecutionStatus
const fmtDuration = formatDuration
const fmtTime = formatTime
const fmtTrigger = formatTriggerType
const ACTION_LABELS = ACTION_TYPE_LABELS

const {
  policies,
  executions,
  policiesLoading,
  executionsLoading,
  executionDetailLoading,
  executionPage,
  executionPageSize,
  executionTotal,
  totalPolicies,
  enabledPolicies,
  recentTriggerCount,
  avgResponseTime,
  executionDetails,
  executionRecoveries,
  fetchPolicies,
  fetchExecutions,
  fetchExecutionDetail,
  fetchRecovery,
  handlePageChange,
} = useFireLinkageData()

// ── 统计卡片 ──
const statCards = computed(() => [
  { label: '联动策略总数', value: totalPolicies.value, icon: Connection, iconBg: 'rgba(64,158,255,0.15)', valueClass: 'primary' },
  { label: '已启用策略', value: enabledPolicies.value, icon: Operation, iconBg: 'rgba(82,196,26,0.15)', valueClass: 'success' },
  { label: '30天触发次数', value: recentTriggerCount.value, icon: Warning, iconBg: 'rgba(245,34,45,0.15)', valueClass: 'danger' },
  { label: '平均响应时间', value: avgResponseTime.value > 0 ? `${avgResponseTime.value}ms` : '--', icon: Clock, iconBg: 'rgba(250,173,20,0.15)', valueClass: 'warning' },
])

// ── 策略展开 ──
const expandedPolicyId = ref<number | null>(null)

function togglePolicy(id: number) {
  expandedPolicyId.value = expandedPolicyId.value === id ? null : id
}

function sortedActions(policy: LinkagePolicy): LinkageAction[] {
  if (!policy.actions) return []
  return [...policy.actions].sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))
}

// ── 动作图标 ──
const iconMap: Record<string, unknown> = {
  ALARM_NOTIFY: Bell,
  WEBHOOK: Connection,
  MQTT_COMMAND: Setting,
  VIDEO_RECORD: VideoCamera,
  VIDEO_POPUP: Monitor,
  close_hvac: Setting,
  open_door: Unlock,
  cut_power: SwitchButton,
  start_exhaust: Promotion,
  turn_on_lights: Sunny,
  start_video: VideoCamera,
}

function actionIcon(actionType: string) {
  return iconMap[actionType] || Setting
}

function extractTarget(config: Record<string, unknown> | null | undefined): string {
  if (!config) return '--'
  const t = config.target || config.device || config.device_name || config.url || ''
  return String(t) || '--'
}

// ── 执行历史展开 ──
async function handleExpandChange(row: LinkageExecution, expandedRows: LinkageExecution[]) {
  if (expandedRows.some(r => r.id === row.id)) {
    await Promise.all([fetchExecutionDetail(row.id), fetchRecovery(row.id)])
  }
}

function execLevel(execution: LinkageExecution): string {
  const p = policies.value.find(pol => pol.id === execution.policy_id)
  if (p) return getLinkageLevel(p)
  const t = (execution.trigger_event || '').toLowerCase()
  return t.includes('alarm') || t.includes('fire') ? 'alarm' : 'warning'
}

function recoveryProgress(recovery: LinkageRecovery): number {
  if (!recovery.logs?.length) return 0
  const done = recovery.logs.filter(l => l.status === 'completed' || l.status === 'skipped').length
  return Math.round((done / recovery.logs.length) * 100)
}

function recoveryDoneCount(recovery: LinkageRecovery): number {
  if (!recovery.logs?.length) return 0
  return recovery.logs.filter(l => l.status === 'completed' || l.status === 'skipped').length
}
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.fire-linkage-page {
  @include page-dashboard(4);

  .stat-row { margin-bottom: 16px; }

  .stat-card {
    background: var(--bg-card);
    border-color: var(--border-color);
    transition: transform 0.2s, box-shadow 0.2s;
    &:hover { transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0,0,0,0.3); }

    .stat-content { display: flex; align-items: center; gap: 12px; padding: 4px 0; }
    .stat-icon { width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
    .stat-info { flex: 1; min-width: 0; }
    .stat-value {
      font-size: 26px; font-weight: 700; line-height: 1.2;
      &.primary { color: var(--primary-color, #1890ff); }
      &.success { color: var(--success-color, #52c41a); }
      &.danger { color: var(--error-color, #f5222d); }
      &.warning { color: var(--warning-color, #faad14); }
    }
    .stat-label { font-size: 13px; color: var(--text-secondary); margin-top: 2px; }
  }

  .section-card {
    background: var(--bg-card);
    border-color: var(--border-color);
    margin-bottom: 16px;
    .card-header { display: flex; align-items: center; gap: 8px; font-size: 15px; font-weight: 600; color: var(--text-primary); }
  }

  .policy-section {
    transform: perspective(800px) rotateY(0.3deg);
    transition: all 0.4s cubic-bezier(0.25,0.46,0.45,0.94);
    &:hover { transform: perspective(800px) rotateY(0deg) translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.35); }
  }

  .history-section {
    transform: perspective(800px) rotateY(-0.3deg) translateZ(-3px);
    transition: all 0.4s cubic-bezier(0.25,0.46,0.45,0.94);
    &:hover { transform: perspective(800px) rotateY(0deg) translateZ(0) translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.35); }
  }
}

/* 策略项 */
.policy-item {
  border: 1px solid var(--border-color, rgba(255,255,255,0.08));
  border-radius: 8px;
  margin-bottom: 10px;
  overflow: hidden;
  transition: border-color 0.3s, box-shadow 0.3s;

  &.policy-alarm { border-left: 3px solid #f5222d; }
  &.policy-warning { border-left: 3px solid #faad14; }
  &.policy-expanded { box-shadow: 0 2px 12px rgba(0,0,0,0.2); }

  .policy-header {
    display: flex; align-items: center; gap: 12px; padding: 12px 16px; cursor: pointer;
    transition: background 0.2s;
    &:hover { background: rgba(255,255,255,0.03); }
  }

  .policy-info {
    display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0;
    .policy-name { font-size: 14px; font-weight: 600; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 240px; }
  }

  .policy-meta {
    display: flex; align-items: center; gap: 10px; flex-shrink: 0;
    .action-count { display: flex; align-items: center; gap: 4px; font-size: 13px; color: var(--text-secondary); }
    .expand-icon { color: var(--text-secondary); transition: transform 0.3s; }
  }
}

/* 动作链 */
.action-chain-wrapper {
  padding: 16px 20px 20px;
  border-top: 1px solid var(--border-color, rgba(255,255,255,0.06));
  background: rgba(0,0,0,0.15);
  overflow-x: auto;
}

.action-chain { display: flex; align-items: flex-start; gap: 0; min-width: max-content; padding: 8px 0; }

.chain-node {
  display: flex; flex-direction: column; align-items: center; gap: 6px; min-width: 90px; max-width: 110px; text-align: center;

  .node-icon {
    width: 44px; height: 44px; border-radius: 12px; display: flex; align-items: center; justify-content: center;
    background: rgba(64,158,255,0.15); color: #409eff;
    transition: transform 0.2s, box-shadow 0.2s;
    &:hover { transform: scale(1.1); box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
  }
  .node-label { font-size: 12px; font-weight: 600; color: var(--text-primary); line-height: 1.3; }
  .node-detail { font-size: 11px; color: var(--text-secondary); max-width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .node-timeout { font-size: 10px; color: var(--text-secondary); opacity: 0.7; }

  &.trigger-node .node-icon { background: rgba(250,173,20,0.2); color: #faad14; }
  &.notify-node .node-icon { background: rgba(82,196,26,0.15); color: #52c41a; }
  &.node-warning .node-icon { background: rgba(250,173,20,0.15); color: #faad14; }
  &.node-alarm .node-icon { background: rgba(245,34,45,0.15); color: #f5222d; }
}

.chain-arrow {
  display: flex; align-items: center; height: 44px; min-width: 32px; position: relative;
  &::before { content: ''; display: block; width: 100%; height: 2px; background: linear-gradient(90deg, rgba(255,255,255,0.1), rgba(255,255,255,0.25), rgba(255,255,255,0.1)); }
  &::after { content: ''; position: absolute; right: 0; top: 50%; transform: translateY(-50%); width: 0; height: 0; border-left: 6px solid rgba(255,255,255,0.3); border-top: 4px solid transparent; border-bottom: 4px solid transparent; }
}

/* 展开动画 */
.expand-enter-active, .expand-leave-active { transition: all 0.3s ease; max-height: 300px; overflow: hidden; }
.expand-enter-from, .expand-leave-to { max-height: 0; opacity: 0; padding-top: 0; padding-bottom: 0; }

/* 时间线 */
.timeline-wrapper { padding: 16px 24px; min-height: 80px; }

.timeline-event-card {
  padding: 8px 12px; border-radius: 6px; background: rgba(255,255,255,0.03);
  border: 1px solid var(--border-color, rgba(255,255,255,0.06)); transition: background 0.2s;
  &:hover { background: rgba(255,255,255,0.06); }
  &.event-failed { background: rgba(245,34,45,0.08); border-color: rgba(245,34,45,0.25); }

  .event-header {
    display: flex; align-items: center; gap: 8px;
    .event-action { font-size: 14px; font-weight: 500; color: var(--text-primary); }
    .event-duration { margin-left: auto; font-size: 12px; color: var(--text-secondary); }
  }
  .event-error { margin-top: 6px; font-size: 12px; color: #f5222d; display: flex; align-items: center; gap: 4px; }
}

/* 恢复状态 */
.recovery-section {
  margin-top: 16px; padding-top: 12px; border-top: 1px dashed var(--border-color, rgba(255,255,255,0.08));
  .recovery-header { display: flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600; color: var(--text-primary); margin-bottom: 8px; }
  .recovery-item { display: flex; align-items: center; gap: 12px; margin-bottom: 6px; }
  .recovery-steps { display: flex; align-items: center; gap: 8px; }
  .recovery-step-text { font-size: 12px; color: var(--text-secondary); white-space: nowrap; }
}

.pagination-wrapper { display: flex; justify-content: flex-end; padding: 12px 0 4px; }
</style>
