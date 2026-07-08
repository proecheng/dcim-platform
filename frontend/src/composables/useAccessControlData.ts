/**
 * 门禁管理数据组合式函数
 * 封装门禁设备数据获取、统计计算、出入事件记录获取
 * 门禁设备为 DI 类型（干接点信号），device_type === 'DOOR'
 */
import { ref, computed, onMounted } from 'vue'
import { type RealtimeData } from '@/api/modules/realtime'
import { getAlarmList, type AlarmInfo } from '@/api/modules/alarm'
import { getLinkagePolicies, type LinkagePolicy } from '@/api/modules/linkage'
import { useRealtimeStore } from '@/stores/realtime'

/** 门禁事件类型 */
export type AccessEventType = 'card_open' | 'remote_open' | 'anomaly_open' | 'fire_linkage_open'

/** 门禁事件记录（从告警记录推导） */
export interface AccessEvent {
  id: number
  time: string
  eventType: AccessEventType
  eventLabel: string
  person: string
  result: 'success' | 'failure'
  isAnomaly: boolean
  isFireLinkage: boolean
  policyName: string
  rawAlarm: AlarmInfo
}

/** 门禁设备状态 */
export type DoorStatus = 'closed' | 'open' | 'alarm' | 'offline'

/** 门禁设备信息（扩展 RealtimeData） */
export interface DoorDevice extends RealtimeData {
  doorStatus: DoorStatus
  doorStatusText: string
}

/**
 * 从 RealtimeData 推导门禁状态
 */
function deriveDoorStatus(d: RealtimeData): DoorStatus {
  if (d.status === 'offline') return 'offline'
  if (d.status === 'alarm') return 'alarm'
  // DI 类型: value=0 常闭, value=1 常开
  return d.value === 1 ? 'open' : 'closed'
}

function doorStatusText(status: DoorStatus): string {
  const map: Record<DoorStatus, string> = {
    closed: '常闭',
    open: '常开',
    alarm: '异常',
    offline: '离线',
  }
  return map[status]
}

/**
 * 从告警记录推导事件类型
 *
 * 门禁设备为 DI 类型，事件类型不是直接字段，而是从告警记录的多个字段组合推导。
 * 推导优先级（从高到低）：
 *   1. 消防联动开门 — alarm_message 包含 "消防"/"联动"/"fire" 关键字
 *   2. 异常开门 — alarm_level 为 critical/major，或 alarm_message 包含 "异常"/"强行"/"非授权"/"闯入"/"失败"
 *   3. 远程开门 — alarm_message 包含 "远程"/"remote"，或 alarm_type === 'system'
 *   4. 刷卡开门 — 默认（以上均不匹配时）
 *
 * ⚠️ 技术债务: 此映射关系依赖后端告警分类规则。如果后端修改了 alarm_type/alarm_level 的
 *    语义或新增了告警类型，此推导逻辑需要同步更新。
 */
function deriveEventType(alarm: AlarmInfo, _firePolicyNames: Set<string>): AccessEventType {
  const msg = (alarm.alarm_message || '').toLowerCase()

  // 消防联动: 告警消息包含消防/联动关键字
  if (msg.includes('消防') || msg.includes('联动') || msg.includes('fire')) {
    return 'fire_linkage_open'
  }

  // 异常开门: 高级别告警或包含异常关键字
  if (
    alarm.alarm_level === 'critical' ||
    alarm.alarm_level === 'major' ||
    msg.includes('异常') ||
    msg.includes('强行') ||
    msg.includes('非授权') ||
    msg.includes('闯入') ||
    msg.includes('失败')
  ) {
    return 'anomaly_open'
  }

  // 远程开门
  if (msg.includes('远程') || msg.includes('remote') || alarm.alarm_type === 'system') {
    return 'remote_open'
  }

  // 默认: 刷卡开门
  return 'card_open'
}

const EVENT_LABELS: Record<AccessEventType, string> = {
  card_open: '刷卡开门',
  remote_open: '远程开门',
  anomaly_open: '异常开门',
  fire_linkage_open: '消防联动开门',
}

/**
 * 从告警消息中提取人员信息
 */
function extractPerson(msg: string): string {
  // 尝试匹配常见模式: "张三 刷卡", "用户: 张三", "人员: xxx"
  const patterns = [
    /人员[：:]\s*(\S+)/,
    /用户[：:]\s*(\S+)/,
    /(\S+)\s*刷卡/,
  ]
  for (const p of patterns) {
    const m = msg.match(p)
    if (m) return m[1]
  }
  return ''
}

export function useAccessControlData() {
  const realtimeStore = useRealtimeStore()
  const allData = computed(() => realtimeStore.dataMap)
  const loading = computed(() => realtimeStore.loading)
  const eventsLoading = ref(false)
  const wsConnected = computed(() => realtimeStore.wsConnected)
  const firePolicies = ref<LinkagePolicy[]>([])
  const eventRecords = ref<AlarmInfo[]>([])

  // ── 筛选门禁设备 ──
  const doorDevices = computed<DoorDevice[]>(() =>
    Array.from(allData.value.values())
      .filter(d => d.device_type === 'DOOR')
      .map(d => {
        const ds = deriveDoorStatus(d)
        return { ...d, doorStatus: ds, doorStatusText: doorStatusText(ds) }
      })
      .sort((a, b) => {
        // 告警设备排前面
        if (a.doorStatus === 'alarm' && b.doorStatus !== 'alarm') return -1
        if (a.doorStatus !== 'alarm' && b.doorStatus === 'alarm') return 1
        return a.point_name.localeCompare(b.point_name)
      })
  )

  // ── 统计数据 ──
  const totalCount = computed(() => doorDevices.value.length)
  const onlineCount = computed(() => doorDevices.value.filter(d => d.doorStatus !== 'offline').length)
  const alarmCount = computed(() => doorDevices.value.filter(d => d.doorStatus === 'alarm').length)
  const todayEventCount = ref(0)

  // ── 消防联动策略名称集合 ──
  const firePolicyNames = computed(() =>
    new Set(firePolicies.value.map(p => p.name))
  )

  // ── 事件记录转换 ──
  const accessEvents = computed<AccessEvent[]>(() =>
    eventRecords.value.map(alarm => {
      const eventType = deriveEventType(alarm, firePolicyNames.value)
      return {
        id: alarm.id,
        time: alarm.created_at,
        eventType,
        eventLabel: EVENT_LABELS[eventType],
        person: extractPerson(alarm.alarm_message || ''),
        result: alarm.status === 'resolved' || alarm.alarm_level === 'info' ? 'success' : 'failure',
        isAnomaly: eventType === 'anomaly_open',
        isFireLinkage: eventType === 'fire_linkage_open',
        policyName: eventType === 'fire_linkage_open' && firePolicies.value.length > 0
          ? firePolicies.value[0].name
          : '',
        rawAlarm: alarm,
      }
    })
  )

  // ── 数据获取（委托给 store）──
  async function fetchData() {
    try {
      await realtimeStore.fetchAllData()
    } catch (e) {
      console.error('门禁设备数据加载失败', e)
    }
  }

  /** 获取今日事件数 */
  async function fetchTodayEventCount() {
    try {
      const now = new Date()
      const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate())
      const res = await getAlarmList({
        start_time: todayStart.toISOString(),
        end_time: now.toISOString(),
        page: 1,
        page_size: 1,
      })
      todayEventCount.value = res.total ?? 0
    } catch {
      todayEventCount.value = 0
    }
  }

  /** 获取指定设备的事件记录 */
  async function fetchDeviceEvents(pointId: number, startTime?: string, endTime?: string) {
    eventsLoading.value = true
    try {
      const params: Record<string, unknown> = {
        point_id: pointId,
        page: 1,
        page_size: 100,
      }
      if (startTime) params.start_time = startTime
      if (endTime) params.end_time = endTime
      const res = await getAlarmList(params as Parameters<typeof getAlarmList>[0])
      eventRecords.value = res.items ?? []
    } catch {
      eventRecords.value = []
    } finally {
      eventsLoading.value = false
    }
  }

  /** 获取消防联动策略 */
  async function fetchFirePolicies() {
    try {
      const res = await getLinkagePolicies({
        trigger_type: 'fire_alarm',
        page: 1,
        page_size: 100,
      })
      firePolicies.value = res.items ?? []
    } catch {
      firePolicies.value = []
    }
  }

  // WS/轮询由 RealtimeStore + useRealtime composable 统一管理

  onMounted(() => {
    if (realtimeStore.totalPoints === 0) {
      fetchData()
    }
    fetchTodayEventCount()
    fetchFirePolicies()
  })

  return {
    // 原始数据
    allData,
    doorDevices,
    loading,
    eventsLoading,
    wsConnected,
    // 统计
    totalCount,
    onlineCount,
    alarmCount,
    todayEventCount,
    // 事件
    eventRecords,
    accessEvents,
    // 联动策略
    firePolicies,
    firePolicyNames,
    // 操作
    fetchData,
    fetchTodayEventCount,
    fetchDeviceEvents,
    fetchFirePolicies,
  }
}
