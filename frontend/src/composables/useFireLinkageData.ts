/**
 * 消防联动可视化数据组合式函数
 * 封装联动策略、执行历史、执行详情、恢复记录的获取与统计
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import {
  getLinkagePolicies,
  getLinkageExecutions,
  getLinkageExecution,
  getRecoveries,
  type LinkagePolicy,
  type LinkageExecution,
  type LinkageLog,
  type LinkageRecovery,
} from '@/api/modules/linkage'

/** 联动级别 */
export type LinkageLevel = 'warning' | 'alarm'

/** 执行结果状态 */
export type ExecutionResult = 'success' | 'partial_failure' | 'failed'

/** 动作类型中文映射 */
export const ACTION_TYPE_LABELS: Record<string, string> = {
  ALARM_NOTIFY: '告警通知',
  WEBHOOK: 'Webhook回调',
  MQTT_COMMAND: '设备控制',
  VIDEO_RECORD: '视频录制',
  VIDEO_POPUP: '视频弹窗',
  close_hvac: '关闭空调',
  open_door: '开启门禁',
  cut_power: '切断电源',
  start_exhaust: '启动排烟',
  turn_on_lights: '开启照明',
  start_video: '启动视频',
}

/** 根据策略判断联动级别 */
export function getLinkageLevel(policy: LinkagePolicy): LinkageLevel {
  const triggerType = (policy.trigger_type || '').toLowerCase()
  const priority = (policy.priority || '').toLowerCase()
  if (priority === 'high' || priority === 'critical' || triggerType.includes('alarm') || triggerType.includes('fire_alarm')) {
    return 'alarm'
  }
  return 'warning'
}

/** 格式化执行结果 */
export function formatExecutionStatus(status: string): { label: string; type: 'success' | 'warning' | 'danger' | 'primary' | 'info' } {
  const map: Record<string, { label: string; type: 'success' | 'warning' | 'danger' | 'primary' | 'info' }> = {
    completed: { label: '全部成功', type: 'success' },
    partial_failure: { label: '部分失败', type: 'warning' },
    failed: { label: '失败', type: 'danger' },
    executing: { label: '执行中', type: 'primary' },
    pending: { label: '待执行', type: 'info' },
  }
  return map[status] || { label: status, type: 'info' }
}

/** 格式化持续时间 */
export function formatDuration(ms: number | null | undefined): string {
  if (ms == null) return '--'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60000).toFixed(1)}min`
}

/** 格式化时间戳 */
export function formatTime(t: string | null | undefined): string {
  if (!t) return '--'
  return t.replace('T', ' ').substring(0, 19)
}

/** 格式化触发条件显示 */
export function formatTriggerType(triggerType: string): string {
  const map: Record<string, string> = {
    fire_alarm: '多传感器联动',
    fire_warning: '单传感器预警',
    smoke_alarm: '烟雾告警',
    temperature_alarm: '温度告警',
  }
  return map[triggerType] || triggerType
}

export function useFireLinkageData() {
  // ── 状态 ──
  const policies = ref<LinkagePolicy[]>([])
  const executions = ref<LinkageExecution[]>([])
  const policiesLoading = ref(false)
  const executionsLoading = ref(false)
  const executionDetailLoading = ref(false)

  // 分页
  const executionPage = ref(1)
  const executionPageSize = ref(10)
  const executionTotal = ref(0)

  // 展开的执行详情缓存
  const executionDetails = ref<Map<number, LinkageExecution>>(new Map())
  const executionRecoveries = ref<Map<number, LinkageRecovery[]>>(new Map())

  let pollingTimer: number | null = null

  // ── 统计数据 ──
  const totalPolicies = computed(() => policies.value.length)
  const enabledPolicies = computed(() => policies.value.filter(p => p.is_enabled).length)
  const recentTriggerCount = ref(0)
  const avgResponseTime = ref(0)

  // ── 数据获取 ──
  async function fetchPolicies() {
    policiesLoading.value = true
    try {
      const res = await getLinkagePolicies({ page: 1, page_size: 100 })
      policies.value = res.items ?? []
    } catch (e) {
      console.error('联动策略加载失败', e)
      policies.value = []
    } finally {
      policiesLoading.value = false
    }
  }

  async function fetchExecutions() {
    executionsLoading.value = true
    try {
      const res = await getLinkageExecutions({
        page: executionPage.value,
        page_size: executionPageSize.value,
      })
      executions.value = res.items ?? []
      executionTotal.value = res.total ?? 0
    } catch (e) {
      console.error('执行历史加载失败', e)
      executions.value = []
    } finally {
      executionsLoading.value = false
    }
  }

  /** 获取最近30天统计 */
  async function fetchStats() {
    try {
      const now = new Date()
      const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
      const res = await getLinkageExecutions({
        start_time: thirtyDaysAgo.toISOString(),
        page: 1,
        page_size: 100,
      })
      const items = res.items ?? []
      recentTriggerCount.value = res.total ?? 0

      // 计算平均响应时间
      const durations = items
        .map(e => e.total_duration_ms)
        .filter((d): d is number => d != null && d > 0)
      avgResponseTime.value = durations.length > 0
        ? Math.round(durations.reduce((a, b) => a + b, 0) / durations.length)
        : 0
    } catch {
      recentTriggerCount.value = 0
      avgResponseTime.value = 0
    }
  }

  /** 获取执行详情（含日志） */
  async function fetchExecutionDetail(executionId: number): Promise<LinkageExecution | null> {
    if (executionDetails.value.has(executionId)) {
      return executionDetails.value.get(executionId) || null
    }
    executionDetailLoading.value = true
    try {
      const detail = await getLinkageExecution(executionId)
      executionDetails.value.set(executionId, detail)
      return detail
    } catch (e) {
      console.error('执行详情加载失败', e)
      return null
    } finally {
      executionDetailLoading.value = false
    }
  }

  /** 获取恢复记录 */
  async function fetchRecovery(executionId: number): Promise<LinkageRecovery[]> {
    if (executionRecoveries.value.has(executionId)) {
      return executionRecoveries.value.get(executionId) || []
    }
    try {
      const res = await getRecoveries({ execution_id: executionId, page: 1, page_size: 10 })
      const items = res.items ?? []
      executionRecoveries.value.set(executionId, items)
      return items
    } catch {
      return []
    }
  }

  /** 切换执行历史分页 */
  function handlePageChange(page: number) {
    executionPage.value = page
    fetchExecutions()
  }

  // ── 轮询 ──
  function startPolling() {
    stopPolling()
    pollingTimer = window.setInterval(() => {
      fetchStats()
    }, 10000)
  }

  function stopPolling() {
    if (pollingTimer) {
      clearInterval(pollingTimer)
      pollingTimer = null
    }
  }

  onMounted(() => {
    fetchPolicies()
    fetchExecutions()
    fetchStats()
    startPolling()
  })

  onUnmounted(() => {
    stopPolling()
  })

  return {
    // 数据
    policies,
    executions,
    policiesLoading,
    executionsLoading,
    executionDetailLoading,
    // 分页
    executionPage,
    executionPageSize,
    executionTotal,
    // 统计
    totalPolicies,
    enabledPolicies,
    recentTriggerCount,
    avgResponseTime,
    // 详情缓存
    executionDetails,
    executionRecoveries,
    // 操作
    fetchPolicies,
    fetchExecutions,
    fetchStats,
    fetchExecutionDetail,
    fetchRecovery,
    handlePageChange,
  }
}
