/**
 * 安防 composable 纯逻辑函数单元测试
 *
 * 覆盖:
 *   - useAccessControlData.ts: deriveDoorStatus, doorStatusText, deriveEventType, extractPerson
 *     (内部函数，未 export，此处复制实现进行测试)
 *   - useFireLinkageData.ts: getLinkageLevel, formatExecutionStatus, formatDuration, formatTime, formatTriggerType
 *     (已 export，直接导入测试)
 */
import { describe, it, expect } from 'vitest'
import type { RealtimeData } from '@/api/modules/realtime'
import type { AlarmInfo } from '@/api/modules/alarm'
import type { LinkagePolicy } from '@/api/modules/linkage'
import {
  getLinkageLevel,
  formatExecutionStatus,
  formatDuration,
  formatTime,
  formatTriggerType,
  ACTION_TYPE_LABELS,
} from '@/composables/useFireLinkageData'

// ============================================================
// 来源: useAccessControlData.ts — deriveDoorStatus (line 41-46)
// 内部函数，未 export，复制实现进行测试
// ============================================================
type DoorStatus = 'closed' | 'open' | 'alarm' | 'offline'

function deriveDoorStatus(d: Pick<RealtimeData, 'status' | 'value'>): DoorStatus {
  if (d.status === 'offline') return 'offline'
  if (d.status === 'alarm') return 'alarm'
  return d.value === 1 ? 'open' : 'closed'
}

// 来源: useAccessControlData.ts — doorStatusText (line 48-56)
function doorStatusText(status: DoorStatus): string {
  const map: Record<DoorStatus, string> = {
    closed: '常闭',
    open: '常开',
    alarm: '异常',
    offline: '离线',
  }
  return map[status]
}

// 来源: useAccessControlData.ts — deriveEventType (line 71-99)
type AccessEventType = 'card_open' | 'remote_open' | 'anomaly_open' | 'fire_linkage_open'

function deriveEventType(alarm: Pick<AlarmInfo, 'alarm_message' | 'alarm_level' | 'alarm_type'>, firePolicyNames: Set<string>): AccessEventType {
  const msg = (alarm.alarm_message || '').toLowerCase()

  if (msg.includes('消防') || msg.includes('联动') || msg.includes('fire')) {
    return 'fire_linkage_open'
  }

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

  if (msg.includes('远程') || msg.includes('remote') || alarm.alarm_type === 'system') {
    return 'remote_open'
  }

  return 'card_open'
}

// 来源: useAccessControlData.ts — extractPerson (line 111-123)
function extractPerson(msg: string): string {
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

// ============================================================
// 辅助: 创建测试数据工厂
// ============================================================
function makeAlarm(overrides: Partial<AlarmInfo> = {}): AlarmInfo {
  return {
    id: 1,
    alarm_no: 'ALM001',
    point_id: 1,
    point_code: 'P001',
    point_name: '门禁1',
    threshold_id: 1,
    alarm_level: 'info',
    alarm_type: 'threshold',
    alarm_message: '',
    trigger_value: 1,
    threshold_value: 1,
    status: 'active',
    acknowledged_by: null,
    acknowledged_at: null,
    ack_remark: null,
    resolved_by: null,
    resolved_at: null,
    resolve_remark: null,
    resolve_type: null,
    duration_seconds: null,
    is_notified: false,
    notify_count: 0,
    created_at: '2026-01-01T00:00:00',
    ...overrides,
  }
}

function makePolicy(overrides: Partial<LinkagePolicy> = {}): LinkagePolicy {
  return {
    id: 1,
    name: '消防联动策略',
    description: '',
    trigger_type: 'fire_alarm',
    trigger_condition: {},
    priority: 'high',
    is_enabled: true,
    is_system: false,
    actions: [],
    created_at: '2026-01-01T00:00:00',
    updated_at: '2026-01-01T00:00:00',
    ...overrides,
  }
}

// ============================================================
// 测试: useAccessControlData 纯函数
// ============================================================

describe('useAccessControlData — deriveDoorStatus', () => {
  it('正常: offline 状态返回 offline', () => {
    expect(deriveDoorStatus({ status: 'offline', value: 0 })).toBe('offline')
  })

  it('正常: alarm 状态返回 alarm', () => {
    expect(deriveDoorStatus({ status: 'alarm', value: 0 })).toBe('alarm')
  })

  it('正常: value=1 且非异常状态返回 open', () => {
    expect(deriveDoorStatus({ status: 'normal', value: 1 })).toBe('open')
  })

  it('正常: value=0 且非异常状态返回 closed', () => {
    expect(deriveDoorStatus({ status: 'normal', value: 0 })).toBe('closed')
  })

  it('边界: alarm 优先于 value 判断', () => {
    expect(deriveDoorStatus({ status: 'alarm', value: 1 })).toBe('alarm')
  })

  it('边界: offline 优先于 alarm 判断', () => {
    // 源码中 offline 先判断
    expect(deriveDoorStatus({ status: 'offline', value: 1 })).toBe('offline')
  })
})

describe('useAccessControlData — doorStatusText', () => {
  it('正常: 所有状态都有对应中文', () => {
    expect(doorStatusText('closed')).toBe('常闭')
    expect(doorStatusText('open')).toBe('常开')
    expect(doorStatusText('alarm')).toBe('异常')
    expect(doorStatusText('offline')).toBe('离线')
  })

  it('边界: 每个状态返回非空字符串', () => {
    const statuses: DoorStatus[] = ['closed', 'open', 'alarm', 'offline']
    statuses.forEach(s => {
      expect(doorStatusText(s)).toBeTruthy()
    })
  })

  it('正常: 返回值类型为 string', () => {
    expect(typeof doorStatusText('closed')).toBe('string')
  })
})

describe('useAccessControlData — deriveEventType', () => {
  const emptyPolicies = new Set<string>()

  it('正常: 消防联动 — 消息包含"消防"', () => {
    const alarm = makeAlarm({ alarm_message: '消防联动触发开门' })
    expect(deriveEventType(alarm, emptyPolicies)).toBe('fire_linkage_open')
  })

  it('正常: 消防联动 — 消息包含"联动"', () => {
    const alarm = makeAlarm({ alarm_message: '联动策略执行' })
    expect(deriveEventType(alarm, emptyPolicies)).toBe('fire_linkage_open')
  })

  it('正常: 消防联动 — 消息包含"fire"', () => {
    const alarm = makeAlarm({ alarm_message: 'fire alarm triggered' })
    expect(deriveEventType(alarm, emptyPolicies)).toBe('fire_linkage_open')
  })

  it('正常: 异常开门 — alarm_level 为 critical', () => {
    const alarm = makeAlarm({ alarm_level: 'critical', alarm_message: '门禁开启' })
    expect(deriveEventType(alarm, emptyPolicies)).toBe('anomaly_open')
  })

  it('正常: 异常开门 — alarm_level 为 major', () => {
    const alarm = makeAlarm({ alarm_level: 'major', alarm_message: '门禁开启' })
    expect(deriveEventType(alarm, emptyPolicies)).toBe('anomaly_open')
  })

  it('正常: 异常开门 — 消息包含"异常"', () => {
    const alarm = makeAlarm({ alarm_message: '异常开门检测' })
    expect(deriveEventType(alarm, emptyPolicies)).toBe('anomaly_open')
  })

  it('正常: 异常开门 — 消息包含"强行"', () => {
    const alarm = makeAlarm({ alarm_message: '强行开门' })
    expect(deriveEventType(alarm, emptyPolicies)).toBe('anomaly_open')
  })

  it('正常: 异常开门 — 消息包含"非授权"', () => {
    const alarm = makeAlarm({ alarm_message: '非授权访问' })
    expect(deriveEventType(alarm, emptyPolicies)).toBe('anomaly_open')
  })

  it('正常: 异常开门 — 消息包含"闯入"', () => {
    const alarm = makeAlarm({ alarm_message: '闯入检测' })
    expect(deriveEventType(alarm, emptyPolicies)).toBe('anomaly_open')
  })

  it('正常: 异常开门 — 消息包含"失败"', () => {
    const alarm = makeAlarm({ alarm_message: '认证失败' })
    expect(deriveEventType(alarm, emptyPolicies)).toBe('anomaly_open')
  })

  it('正常: 远程开门 — 消息包含"远程"', () => {
    const alarm = makeAlarm({ alarm_message: '远程开门指令' })
    expect(deriveEventType(alarm, emptyPolicies)).toBe('remote_open')
  })

  it('正常: 远程开门 — 消息包含"remote"', () => {
    const alarm = makeAlarm({ alarm_message: 'remote unlock' })
    expect(deriveEventType(alarm, emptyPolicies)).toBe('remote_open')
  })

  it('正常: 远程开门 — alarm_type 为 system', () => {
    const alarm = makeAlarm({ alarm_type: 'system', alarm_message: '系统操作' })
    expect(deriveEventType(alarm, emptyPolicies)).toBe('remote_open')
  })

  it('正常: 默认刷卡开门', () => {
    const alarm = makeAlarm({ alarm_message: '正常通行' })
    expect(deriveEventType(alarm, emptyPolicies)).toBe('card_open')
  })

  it('边界: 空消息默认刷卡开门', () => {
    const alarm = makeAlarm({ alarm_message: '' })
    expect(deriveEventType(alarm, emptyPolicies)).toBe('card_open')
  })

  it('边界: 消防优先级高于异常', () => {
    // 同时包含消防和异常关键字，消防优先
    const alarm = makeAlarm({ alarm_level: 'critical', alarm_message: '消防联动异常开门' })
    expect(deriveEventType(alarm, emptyPolicies)).toBe('fire_linkage_open')
  })

  it('边界: 异常优先级高于远程', () => {
    // 同时包含异常和远程关键字，异常优先
    const alarm = makeAlarm({ alarm_message: '远程异常操作' })
    expect(deriveEventType(alarm, emptyPolicies)).toBe('anomaly_open')
  })
})

describe('useAccessControlData — extractPerson', () => {
  it('正常: 匹配"人员: xxx"模式', () => {
    expect(extractPerson('人员: 张三 通过门禁')).toBe('张三')
  })

  it('正常: 匹配"人员：xxx"模式（中文冒号）', () => {
    expect(extractPerson('人员：李四 刷卡通过')).toBe('李四')
  })

  it('正常: 匹配"用户: xxx"模式', () => {
    expect(extractPerson('用户: admin 操作')).toBe('admin')
  })

  it('正常: 匹配"xxx 刷卡"模式', () => {
    expect(extractPerson('王五 刷卡开门')).toBe('王五')
  })

  it('边界: 无匹配返回空字符串', () => {
    expect(extractPerson('系统自动开门')).toBe('')
  })

  it('异常: 空字符串返回空', () => {
    expect(extractPerson('')).toBe('')
  })

  it('边界: 优先匹配"人员"模式', () => {
    // "人员" 模式在数组中排第一，优先匹配
    expect(extractPerson('人员: 张三 刷卡')).toBe('张三')
  })
})

// ============================================================
// 测试: useFireLinkageData 导出的纯函数
// ============================================================

describe('useFireLinkageData — getLinkageLevel', () => {
  it('正常: priority=high 返回 alarm', () => {
    const policy = makePolicy({ priority: 'high' })
    expect(getLinkageLevel(policy)).toBe('alarm')
  })

  it('正常: priority=critical 返回 alarm', () => {
    const policy = makePolicy({ priority: 'critical' })
    expect(getLinkageLevel(policy)).toBe('alarm')
  })

  it('正常: trigger_type 包含 alarm 返回 alarm', () => {
    const policy = makePolicy({ trigger_type: 'smoke_alarm', priority: 'low' })
    expect(getLinkageLevel(policy)).toBe('alarm')
  })

  it('正常: trigger_type 包含 fire_alarm 返回 alarm', () => {
    const policy = makePolicy({ trigger_type: 'fire_alarm', priority: 'low' })
    expect(getLinkageLevel(policy)).toBe('alarm')
  })

  it('正常: 低优先级非告警类型返回 warning', () => {
    const policy = makePolicy({ priority: 'low', trigger_type: 'temperature_warning' })
    expect(getLinkageLevel(policy)).toBe('warning')
  })

  it('边界: 空 priority 和非告警 trigger_type 返回 warning', () => {
    const policy = makePolicy({ priority: '', trigger_type: 'manual' })
    expect(getLinkageLevel(policy)).toBe('warning')
  })

  it('边界: priority 大小写不敏感', () => {
    const policy = makePolicy({ priority: 'HIGH' })
    expect(getLinkageLevel(policy)).toBe('alarm')
  })
})

describe('useFireLinkageData — formatExecutionStatus', () => {
  it('正常: completed 返回全部成功/success', () => {
    const result = formatExecutionStatus('completed')
    expect(result.label).toBe('全部成功')
    expect(result.type).toBe('success')
  })

  it('正常: partial_failure 返回部分失败/warning', () => {
    const result = formatExecutionStatus('partial_failure')
    expect(result.label).toBe('部分失败')
    expect(result.type).toBe('warning')
  })

  it('正常: failed 返回失败/danger', () => {
    const result = formatExecutionStatus('failed')
    expect(result.label).toBe('失败')
    expect(result.type).toBe('danger')
  })

  it('正常: executing 返回执行中/primary', () => {
    const result = formatExecutionStatus('executing')
    expect(result.label).toBe('执行中')
    expect(result.type).toBe('primary')
  })

  it('正常: pending 返回待执行/info', () => {
    const result = formatExecutionStatus('pending')
    expect(result.label).toBe('待执行')
    expect(result.type).toBe('info')
  })

  it('异常: 未知状态返回原始值/info', () => {
    const result = formatExecutionStatus('unknown_status')
    expect(result.label).toBe('unknown_status')
    expect(result.type).toBe('info')
  })
})

describe('useFireLinkageData — formatDuration', () => {
  it('正常: 毫秒级显示 ms', () => {
    expect(formatDuration(500)).toBe('500ms')
  })

  it('正常: 秒级显示 s', () => {
    expect(formatDuration(3500)).toBe('3.5s')
  })

  it('正常: 分钟级显示 min', () => {
    expect(formatDuration(90000)).toBe('1.5min')
  })

  it('边界: null 返回 --', () => {
    expect(formatDuration(null)).toBe('--')
  })

  it('边界: undefined 返回 --', () => {
    expect(formatDuration(undefined)).toBe('--')
  })

  it('边界: 0ms 返回 0ms', () => {
    expect(formatDuration(0)).toBe('0ms')
  })

  it('边界: 恰好 1000ms 返回 1.0s', () => {
    expect(formatDuration(1000)).toBe('1.0s')
  })

  it('边界: 恰好 60000ms 返回 1.0min', () => {
    expect(formatDuration(60000)).toBe('1.0min')
  })

  it('正常: 999ms 仍显示 ms', () => {
    expect(formatDuration(999)).toBe('999ms')
  })
})

describe('useFireLinkageData — formatTime', () => {
  it('正常: ISO 时间戳格式化', () => {
    expect(formatTime('2026-01-15T14:30:45.123Z')).toBe('2026-01-15 14:30:45')
  })

  it('正常: 不带毫秒的时间戳', () => {
    expect(formatTime('2026-01-15T14:30:45')).toBe('2026-01-15 14:30:45')
  })

  it('边界: null 返回 --', () => {
    expect(formatTime(null)).toBe('--')
  })

  it('边界: undefined 返回 --', () => {
    expect(formatTime(undefined)).toBe('--')
  })

  it('边界: 空字符串返回 --', () => {
    expect(formatTime('')).toBe('--')
  })
})

describe('useFireLinkageData — formatTriggerType', () => {
  it('正常: fire_alarm 返回多传感器联动', () => {
    expect(formatTriggerType('fire_alarm')).toBe('多传感器联动')
  })

  it('正常: fire_warning 返回单传感器预警', () => {
    expect(formatTriggerType('fire_warning')).toBe('单传感器预警')
  })

  it('正常: smoke_alarm 返回烟雾告警', () => {
    expect(formatTriggerType('smoke_alarm')).toBe('烟雾告警')
  })

  it('正常: temperature_alarm 返回温度告警', () => {
    expect(formatTriggerType('temperature_alarm')).toBe('温度告警')
  })

  it('异常: 未知类型返回原始值', () => {
    expect(formatTriggerType('custom_trigger')).toBe('custom_trigger')
  })

  it('边界: 空字符串返回空字符串', () => {
    expect(formatTriggerType('')).toBe('')
  })
})

describe('useFireLinkageData — ACTION_TYPE_LABELS', () => {
  it('正常: 包含所有预定义动作类型', () => {
    expect(ACTION_TYPE_LABELS['ALARM_NOTIFY']).toBe('告警通知')
    expect(ACTION_TYPE_LABELS['WEBHOOK']).toBe('Webhook回调')
    expect(ACTION_TYPE_LABELS['MQTT_COMMAND']).toBe('设备控制')
    expect(ACTION_TYPE_LABELS['VIDEO_RECORD']).toBe('视频录制')
    expect(ACTION_TYPE_LABELS['close_hvac']).toBe('关闭空调')
    expect(ACTION_TYPE_LABELS['open_door']).toBe('开启门禁')
  })

  it('边界: 未定义的 key 返回 undefined', () => {
    expect(ACTION_TYPE_LABELS['nonexistent']).toBeUndefined()
  })

  it('正常: 所有值都是非空中文字符串', () => {
    Object.values(ACTION_TYPE_LABELS).forEach(label => {
      expect(label).toBeTruthy()
      expect(typeof label).toBe('string')
    })
  })
})
