/**
 * Degradation Store & Opportunity Store 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// Mock opportunities API
vi.mock('@/api/modules/opportunities', () => ({
  getOpportunityDashboard: vi.fn().mockResolvedValue({
    code: 0,
    data: {
      summary_cards: {
        annual_potential_saving: 50000,
        pending_opportunities: 3,
        executing_plans: 1,
        monthly_actual_saving: 4200,
      },
      opportunities: [
        { id: 1, category: 1, title: '峰谷电价优化', priority: 'high', potential_saving: 20000, confidence: 0.85, status: 'discovered' },
        { id: 2, category: 2, title: '空调温度调节', priority: 'medium', potential_saving: 15000, confidence: 0.7, status: 'ready' },
        { id: 3, category: 1, title: '功率因数优化', priority: 'high', potential_saving: 15000, confidence: 0.9, status: 'discovered' },
      ],
      by_category: { '1': [{ id: 1 }], '2': [{ id: 2 }] },
      total_count: 3,
    },
  }),
  getOpportunities: vi.fn().mockResolvedValue({
    code: 0,
    data: {
      items: [
        { id: 1, category: 1, title: '峰谷电价优化', priority: 'high', status: 'discovered', potential_saving: 20000, confidence: 0.85 },
      ],
      total: 1,
    },
  }),
  getOpportunityDetail: vi.fn().mockResolvedValue({
    code: 0,
    data: {
      id: 1, category: 1, title: '峰谷电价优化', priority: 'high', status: 'discovered',
      potential_saving: 20000, confidence: 0.85,
      measures: [{ id: 10, opportunity_id: 1, measure_type: 'peak_shift', execution_mode: 'auto', sort_order: 1 }],
    },
  }),
  getExecutionPlans: vi.fn().mockResolvedValue({
    code: 0,
    data: { items: [{ id: 100, opportunity_id: 1, plan_name: '计划A', expected_saving: 5000, status: 'pending' }], total: 1 },
  }),
  getExecutionPlanDetail: vi.fn().mockResolvedValue({
    code: 0,
    data: {
      plan: { id: 100, opportunity_id: 1, plan_name: '计划A', expected_saving: 5000, status: 'executing' },
      tasks: [
        { id: 1, plan_id: 100, task_type: 'regulation', task_name: '调节空调', execution_mode: 'auto', status: 'pending', sort_order: 1 },
        { id: 2, plan_id: 100, task_type: 'regulation', task_name: '调节照明', execution_mode: 'manual', status: 'completed', sort_order: 2 },
      ],
      task_stats: { total: 2, pending: 1, executing: 0, completed: 1, failed: 0 },
      auto_task_count: 1,
      manual_task_count: 1,
      results: [],
      progress_percentage: 50,
    },
  }),
  getExecutionStats: vi.fn().mockResolvedValue({
    code: 0,
    data: {
      plans: { total: 5, by_status: {}, total_expected_saving: 100000 },
      results: { completed_count: 3, total_actual_saving: 80000, overall_achievement_rate: 0.8 },
    },
  }),
  getAvailableDevices: vi.fn().mockResolvedValue({
    code: 0,
    data: {
      available_devices: [
        { device_id: 1, device_code: 'AC-01', device_name: '空调1', device_type: 'ac', rated_power: 10, regulations: [], total_adjustable_power: 5, execution_mode: 'auto' },
        { device_id: 2, device_code: 'AC-02', device_name: '空调2', device_type: 'ac', rated_power: 8, regulations: [], total_adjustable_power: 3, execution_mode: 'manual' },
      ],
    },
  }),
  OpportunityCategoryNames: { 1: '电费结构优化', 2: '设备运行优化', 3: '设备改造升级', 4: '综合能效提升' },
  OpportunityCategoryKeys: { 1: 'bill_optimization', 2: 'device_operation', 3: 'equipment_upgrade', 4: 'comprehensive' },
}))

// ==================== Degradation Store ====================

describe('useDegradationStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('初始状态 — 所有降级标志为 false', async () => {
    const { useDegradationStore } = await import('@/stores/degradation')
    const store = useDegradationStore()
    expect(store.redisDown).toBe(false)
    expect(store.websocketDown).toBe(false)
    expect(store.mqttDown).toBe(false)
    expect(store.degradedMessage).toBe('')
    expect(store.hasDegradation).toBe(false)
  })

  it('setRedisDown 设置 Redis 降级状态和消息', async () => {
    const { useDegradationStore, degradationFlags } = await import('@/stores/degradation')
    const store = useDegradationStore()
    store.setRedisDown(true, 'Redis 连接超时')
    expect(store.redisDown).toBe(true)
    expect(store.degradedMessage).toBe('Redis 连接超时')
    expect(store.hasDegradation).toBe(true)
    expect(degradationFlags.redisDown).toBe(true)
    expect(degradationFlags.degradedMessage).toBe('Redis 连接超时')
  })

  it('setRedisDown(false) 恢复并清空消息', async () => {
    const { useDegradationStore } = await import('@/stores/degradation')
    const store = useDegradationStore()
    store.setRedisDown(true, '故障')
    store.setRedisDown(false)
    expect(store.redisDown).toBe(false)
    expect(store.degradedMessage).toBe('')
    expect(store.hasDegradation).toBe(false)
  })

  it('setWebsocketDown 设置 WebSocket 降级', async () => {
    const { useDegradationStore, degradationFlags } = await import('@/stores/degradation')
    const store = useDegradationStore()
    store.setWebsocketDown(true)
    expect(store.websocketDown).toBe(true)
    expect(store.hasDegradation).toBe(true)
    expect(degradationFlags.websocketDown).toBe(true)
  })

  it('setMqttDown 设置 MQTT 降级', async () => {
    const { useDegradationStore, degradationFlags } = await import('@/stores/degradation')
    const store = useDegradationStore()
    store.setMqttDown(true)
    expect(store.mqttDown).toBe(true)
    expect(store.hasDegradation).toBe(true)
    expect(degradationFlags.mqttDown).toBe(true)
  })

  it('hasDegradation 多标志组合', async () => {
    const { useDegradationStore } = await import('@/stores/degradation')
    const store = useDegradationStore()
    store.setRedisDown(true)
    store.setWebsocketDown(true)
    expect(store.hasDegradation).toBe(true)
    store.setRedisDown(false)
    expect(store.hasDegradation).toBe(true) // websocket 仍 down
    store.setWebsocketDown(false)
    expect(store.hasDegradation).toBe(false)
  })

  it('syncFromFlags 从全局标志同步状态', async () => {
    const { useDegradationStore, degradationFlags } = await import('@/stores/degradation')
    degradationFlags.redisDown = true
    degradationFlags.websocketDown = true
    degradationFlags.mqttDown = false
    degradationFlags.degradedMessage = '外部写入'
    const store = useDegradationStore()
    store.syncFromFlags()
    expect(store.redisDown).toBe(true)
    expect(store.websocketDown).toBe(true)
    expect(store.mqttDown).toBe(false)
    expect(store.degradedMessage).toBe('外部写入')
    // 清理
    degradationFlags.redisDown = false
    degradationFlags.websocketDown = false
    degradationFlags.degradedMessage = ''
  })
})

// ==================== Opportunity Store ====================

describe('useOpportunityStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('初始状态 — 空数据', async () => {
    const { useOpportunityStore } = await import('@/stores/opportunity')
    const store = useOpportunityStore()
    expect(store.dashboard).toBeNull()
    expect(store.opportunities).toEqual([])
    expect(store.opportunitiesTotal).toBe(0)
    expect(store.currentOpportunity).toBeNull()
    expect(store.simulationResult).toBeNull()
    expect(store.availableDevices).toEqual([])
    expect(store.selectedDeviceIds).toEqual([])
    expect(store.executionPlans).toEqual([])
    expect(store.currentPlan).toBeNull()
    expect(store.executionStats).toBeNull()
    expect(store.lastUpdateTime).toBeNull()
  })

  it('计算属性初始值', async () => {
    const { useOpportunityStore } = await import('@/stores/opportunity')
    const store = useOpportunityStore()
    expect(store.pendingCount).toBe(0)
    expect(store.executingCount).toBe(0)
    expect(store.annualPotentialSaving).toBe(0)
    expect(store.monthlyActualSaving).toBe(0)
    expect(store.highPriorityOpportunities).toEqual([])
    expect(store.totalSelectedPower).toBe(0)
    expect(store.currentPlanProgress).toBe(0)
  })

  it('loadDashboard 加载仪表盘数据', async () => {
    const { useOpportunityStore } = await import('@/stores/opportunity')
    const store = useOpportunityStore()
    await store.loadDashboard()
    expect(store.dashboard).not.toBeNull()
    expect(store.pendingCount).toBe(3)
    expect(store.executingCount).toBe(1)
    expect(store.annualPotentialSaving).toBe(50000)
    expect(store.monthlyActualSaving).toBe(4200)
    expect(store.highPriorityOpportunities).toHaveLength(2)
    expect(store.lastUpdateTime).toBeInstanceOf(Date)
  })

  it('loadOpportunities 加载机会列表', async () => {
    const { useOpportunityStore } = await import('@/stores/opportunity')
    const store = useOpportunityStore()
    await store.loadOpportunities()
    expect(store.opportunities).toHaveLength(1)
    expect(store.opportunitiesTotal).toBe(1)
  })

  it('loadOpportunityDetail 加载机会详情', async () => {
    const { useOpportunityStore } = await import('@/stores/opportunity')
    const store = useOpportunityStore()
    await store.loadOpportunityDetail(1)
    expect(store.currentOpportunity).not.toBeNull()
    expect(store.currentOpportunity?.id).toBe(1)
    expect(store.currentOpportunity?.measures).toHaveLength(1)
  })

  it('loadAvailableDevices 加载可选设备', async () => {
    const { useOpportunityStore } = await import('@/stores/opportunity')
    const store = useOpportunityStore()
    await store.loadAvailableDevices(1)
    expect(store.availableDevices).toHaveLength(2)
  })

  it('toggleDeviceSelection 选择/取消设备', async () => {
    const { useOpportunityStore } = await import('@/stores/opportunity')
    const store = useOpportunityStore()
    await store.loadAvailableDevices(1)
    store.toggleDeviceSelection(1)
    expect(store.selectedDeviceIds).toEqual([1])
    expect(store.totalSelectedPower).toBe(5)
    store.toggleDeviceSelection(2)
    expect(store.selectedDeviceIds).toEqual([1, 2])
    expect(store.totalSelectedPower).toBe(8)
    store.toggleDeviceSelection(1)
    expect(store.selectedDeviceIds).toEqual([2])
    expect(store.totalSelectedPower).toBe(3)
  })

  it('selectAllDevices 全选/取消全选', async () => {
    const { useOpportunityStore } = await import('@/stores/opportunity')
    const store = useOpportunityStore()
    await store.loadAvailableDevices(1)
    store.selectAllDevices(true)
    expect(store.selectedDeviceIds).toEqual([1, 2])
    expect(store.totalSelectedPower).toBe(8)
    store.selectAllDevices(false)
    expect(store.selectedDeviceIds).toEqual([])
    expect(store.totalSelectedPower).toBe(0)
  })

  it('setSimulationResult 设置模拟结果', async () => {
    const { useOpportunityStore } = await import('@/stores/opportunity')
    const store = useOpportunityStore()
    const mockResult = {
      is_feasible: true,
      current_state: {},
      simulated_state: {},
      benefit: { daily_saving_kwh: 100, daily_saving_yuan: 50, annual_saving_yuan: 18000 },
      confidence: 0.9,
      warnings: [],
      recommendations: [],
    }
    store.setSimulationResult(mockResult)
    expect(store.simulationResult).toEqual(mockResult)
    store.setSimulationResult(null)
    expect(store.simulationResult).toBeNull()
  })

  it('loadExecutionPlans 加载执行计划', async () => {
    const { useOpportunityStore } = await import('@/stores/opportunity')
    const store = useOpportunityStore()
    await store.loadExecutionPlans()
    expect(store.executionPlans).toHaveLength(1)
    expect(store.plansTotal).toBe(1)
  })

  it('loadPlanDetail 加载计划详情', async () => {
    const { useOpportunityStore } = await import('@/stores/opportunity')
    const store = useOpportunityStore()
    await store.loadPlanDetail(100)
    expect(store.currentPlan).not.toBeNull()
    expect(store.currentPlanProgress).toBe(50)
  })

  it('updateTaskStatus 更新任务状态并重算统计', async () => {
    const { useOpportunityStore } = await import('@/stores/opportunity')
    const store = useOpportunityStore()
    await store.loadPlanDetail(100)
    store.updateTaskStatus(1, 'completed')
    expect(store.currentPlan!.tasks[0].status).toBe('completed')
    expect(store.currentPlan!.task_stats.completed).toBe(2)
    expect(store.currentPlan!.task_stats.pending).toBe(0)
    expect(store.currentPlan!.progress_percentage).toBe(100)
  })

  it('loadExecutionStats 加载执行统计', async () => {
    const { useOpportunityStore } = await import('@/stores/opportunity')
    const store = useOpportunityStore()
    await store.loadExecutionStats()
    expect(store.executionStats).not.toBeNull()
    expect(store.executionStats!.plans.total).toBe(5)
  })

  it('getCategoryName / getCategoryKey 分类辅助', async () => {
    const { useOpportunityStore } = await import('@/stores/opportunity')
    const store = useOpportunityStore()
    expect(store.getCategoryName(1)).toBe('电费结构优化')
    expect(store.getCategoryName(3)).toBe('设备改造升级')
    expect(store.getCategoryKey(2)).toBe('device_operation')
    expect(store.getCategoryKey(4)).toBe('comprehensive')
  })

  it('clearData 清空所有数据', async () => {
    const { useOpportunityStore } = await import('@/stores/opportunity')
    const store = useOpportunityStore()
    await store.loadDashboard()
    await store.loadOpportunities()
    store.clearData()
    expect(store.dashboard).toBeNull()
    expect(store.opportunities).toEqual([])
    expect(store.currentOpportunity).toBeNull()
    expect(store.executionPlans).toEqual([])
    expect(store.lastUpdateTime).toBeNull()
  })

  it('clearCurrentSelection 清空当前选择', async () => {
    const { useOpportunityStore } = await import('@/stores/opportunity')
    const store = useOpportunityStore()
    await store.loadOpportunityDetail(1)
    await store.loadAvailableDevices(1)
    store.toggleDeviceSelection(1)
    store.clearCurrentSelection()
    expect(store.currentOpportunity).toBeNull()
    expect(store.simulationResult).toBeNull()
    expect(store.availableDevices).toEqual([])
    expect(store.selectedDeviceIds).toEqual([])
    expect(store.currentPlan).toBeNull()
  })
})
