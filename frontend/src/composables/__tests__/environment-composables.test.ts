/**
 * 环境监测 composable 纯逻辑函数单元测试
 *
 * 覆盖:
 *   - useTemperatureData.ts: 区域分组逻辑、平均值计算、传感器筛选
 *   - useWaterLeakData.ts: 区域分组逻辑、状态统计
 *   - useSmokeInfraredData.ts: 区域分组逻辑、按类型统计
 *
 * 这些函数定义在 composable 内部（computed 或闭包中），未 export，
 * 因此在此复制核心逻辑进行测试。
 */
import { describe, it, expect } from 'vitest'
import type { RealtimeData } from '@/api/modules/realtime'

// ============================================================
// 辅助: 创建 RealtimeData 测试数据工厂
// ============================================================
function makeRealtimeData(overrides: Partial<RealtimeData> = {}): RealtimeData {
  return {
    point_id: 1,
    point_code: 'P001',
    point_name: '传感器1',
    point_type: 'AI',
    device_type: 'TH',
    area_code: 'A区',
    raw_value: 25,
    value: 25,
    value_text: '25',
    unit: '°C',
    quality: 100,
    status: 'normal',
    alarm_level: null,
    change_count: 0,
    last_change_at: '2026-01-01T00:00:00',
    updated_at: '2026-01-01T00:00:00',
    ...overrides,
  }
}

// ============================================================
// 来源: useTemperatureData.ts — computed thSensors / tempSensors / humiditySensors 筛选逻辑
// ============================================================
function filterTHSensors(data: RealtimeData[]): RealtimeData[] {
  return data.filter(d => d.device_type === 'TH')
}

function filterTempSensors(thSensors: RealtimeData[]): RealtimeData[] {
  return thSensors.filter(d => d.unit === '°C')
}

function filterHumiditySensors(thSensors: RealtimeData[]): RealtimeData[] {
  return thSensors.filter(d => d.unit === '%')
}

// 来源: useTemperatureData.ts — computed avgTemp (line 61-65)
function calcAvgTemp(tempSensors: RealtimeData[]): number | null {
  const valid = tempSensors.filter(d => d.value != null && d.status !== 'offline')
  if (!valid.length) return null
  return valid.reduce((s, d) => s + (d.value ?? 0), 0) / valid.length
}

// 来源: useTemperatureData.ts — computed avgHumidity (line 67-71)
function calcAvgHumidity(humiditySensors: RealtimeData[]): number | null {
  const valid = humiditySensors.filter(d => d.value != null && d.status !== 'offline')
  if (!valid.length) return null
  return valid.reduce((s, d) => s + (d.value ?? 0), 0) / valid.length
}

// 来源: useTemperatureData.ts — computed zoneGroups (line 74-106)
interface ZoneGroup {
  areaCode: string
  sensors: RealtimeData[]
  tempSensors: RealtimeData[]
  humiditySensors: RealtimeData[]
  avgTemp: number | null
  avgHumidity: number | null
  minTemp: number | null
  maxTemp: number | null
  alarmCount: number
  hasDrift: boolean
  hasAlarm: boolean
}

function buildTempZoneGroups(thSensors: RealtimeData[], driftPointIds: Set<number>): ZoneGroup[] {
  const map = new Map<string, RealtimeData[]>()
  thSensors.forEach(d => {
    const area = d.area_code || '未分区'
    if (!map.has(area)) map.set(area, [])
    map.get(area)!.push(d)
  })

  return Array.from(map.entries()).map(([areaCode, sensors]) => {
    const temps = sensors.filter(s => s.unit === '°C')
    const humids = sensors.filter(s => s.unit === '%')
    const validTemps = temps.filter(s => s.value != null && s.status !== 'offline')
    const validHumids = humids.filter(s => s.value != null && s.status !== 'offline')

    const tempValues = validTemps.map(s => s.value ?? 0)
    const alarms = sensors.filter(s => s.status === 'alarm').length
    const hasDrift = sensors.some(s => driftPointIds.has(s.point_id))

    return {
      areaCode,
      sensors,
      tempSensors: temps,
      humiditySensors: humids,
      avgTemp: validTemps.length ? validTemps.reduce((s, d) => s + (d.value ?? 0), 0) / validTemps.length : null,
      avgHumidity: validHumids.length ? validHumids.reduce((s, d) => s + (d.value ?? 0), 0) / validHumids.length : null,
      minTemp: tempValues.length ? Math.min(...tempValues) : null,
      maxTemp: tempValues.length ? Math.max(...tempValues) : null,
      alarmCount: alarms,
      hasDrift,
      hasAlarm: alarms > 0,
    }
  }).sort((a, b) => a.areaCode.localeCompare(b.areaCode))
}

// ============================================================
// 来源: useWaterLeakData.ts — computed zoneGroups (line 39-65)
// ============================================================
interface WaterLeakZoneGroup {
  areaCode: string
  sensors: RealtimeData[]
  normalCount: number
  alarmCount: number
  offlineCount: number
  hasAlarm: boolean
}

function buildWaterLeakZoneGroups(wlSensors: RealtimeData[]): WaterLeakZoneGroup[] {
  const map = new Map<string, RealtimeData[]>()
  wlSensors.forEach(d => {
    const area = d.area_code || '未分区'
    if (!map.has(area)) map.set(area, [])
    map.get(area)!.push(d)
  })

  return Array.from(map.entries()).map(([areaCode, sensors]) => {
    const normalCount = sensors.filter(s => s.status === 'normal').length
    const alarmCnt = sensors.filter(s => s.status === 'alarm').length
    const offlineCount = sensors.filter(s => s.status === 'offline').length

    return {
      areaCode,
      sensors,
      normalCount,
      alarmCount: alarmCnt,
      offlineCount,
      hasAlarm: alarmCnt > 0,
    }
  }).sort((a, b) => {
    if (a.hasAlarm !== b.hasAlarm) return a.hasAlarm ? -1 : 1
    return a.areaCode.localeCompare(b.areaCode)
  })
}

// ============================================================
// 来源: useSmokeInfraredData.ts — computed zoneGroups (line 49-81)
// ============================================================
interface SmokeIRZoneGroup {
  areaCode: string
  sensors: RealtimeData[]
  smokeCount: number
  irCount: number
  smokeAlarmCount: number
  irAlarmCount: number
  normalCount: number
  alarmCount: number
  offlineCount: number
  hasAlarm: boolean
}

function buildSmokeIRZoneGroups(siSensors: RealtimeData[]): SmokeIRZoneGroup[] {
  const map = new Map<string, RealtimeData[]>()
  siSensors.forEach(d => {
    const area = d.area_code || '未分区'
    if (!map.has(area)) map.set(area, [])
    map.get(area)!.push(d)
  })

  return Array.from(map.entries()).map(([areaCode, sensors]) => {
    const smokeSensorsInZone = sensors.filter(s => s.device_type === 'SMOKE')
    const irSensorsInZone = sensors.filter(s => s.device_type === 'IR')
    const normalCount = sensors.filter(s => s.status === 'normal').length
    const alarmCnt = sensors.filter(s => s.status === 'alarm').length
    const offlineCount = sensors.filter(s => s.status === 'offline').length

    return {
      areaCode,
      sensors,
      smokeCount: smokeSensorsInZone.length,
      irCount: irSensorsInZone.length,
      smokeAlarmCount: smokeSensorsInZone.filter(s => s.status === 'alarm').length,
      irAlarmCount: irSensorsInZone.filter(s => s.status === 'alarm').length,
      normalCount,
      alarmCount: alarmCnt,
      offlineCount,
      hasAlarm: alarmCnt > 0,
    }
  }).sort((a, b) => {
    if (a.hasAlarm !== b.hasAlarm) return a.hasAlarm ? -1 : 1
    return a.areaCode.localeCompare(b.areaCode)
  })
}

// ============================================================
// 测试
// ============================================================

describe('useTemperatureData — 传感器筛选', () => {
  it('正常: 只筛选 device_type === TH 的传感器', () => {
    const data = [
      makeRealtimeData({ point_id: 1, device_type: 'TH' }),
      makeRealtimeData({ point_id: 2, device_type: 'WL' }),
      makeRealtimeData({ point_id: 3, device_type: 'TH' }),
    ]
    expect(filterTHSensors(data)).toHaveLength(2)
    expect(filterTHSensors(data).every(d => d.device_type === 'TH')).toBe(true)
  })

  it('边界: 空数组返回空', () => {
    expect(filterTHSensors([])).toHaveLength(0)
  })

  it('边界: 无匹配类型返回空', () => {
    const data = [
      makeRealtimeData({ device_type: 'SMOKE' }),
      makeRealtimeData({ device_type: 'IR' }),
    ]
    expect(filterTHSensors(data)).toHaveLength(0)
  })

  it('正常: 温度传感器按 unit === °C 筛选', () => {
    const thSensors = [
      makeRealtimeData({ unit: '°C', value: 25 }),
      makeRealtimeData({ unit: '%', value: 60 }),
      makeRealtimeData({ unit: '°C', value: 28 }),
    ]
    expect(filterTempSensors(thSensors)).toHaveLength(2)
  })

  it('正常: 湿度传感器按 unit === % 筛选', () => {
    const thSensors = [
      makeRealtimeData({ unit: '°C', value: 25 }),
      makeRealtimeData({ unit: '%', value: 60 }),
    ]
    expect(filterHumiditySensors(thSensors)).toHaveLength(1)
    expect(filterHumiditySensors(thSensors)[0].value).toBe(60)
  })
})

describe('useTemperatureData — 平均值计算', () => {
  it('正常: 计算多个温度传感器的平均值', () => {
    const sensors = [
      makeRealtimeData({ value: 20, unit: '°C', status: 'normal' }),
      makeRealtimeData({ value: 30, unit: '°C', status: 'normal' }),
      makeRealtimeData({ value: 25, unit: '°C', status: 'normal' }),
    ]
    expect(calcAvgTemp(sensors)).toBe(25)
  })

  it('边界: 排除 offline 传感器', () => {
    const sensors = [
      makeRealtimeData({ value: 20, status: 'normal' }),
      makeRealtimeData({ value: 100, status: 'offline' }),
    ]
    expect(calcAvgTemp(sensors)).toBe(20)
  })

  it('边界: 全部 offline 返回 null', () => {
    const sensors = [
      makeRealtimeData({ value: 20, status: 'offline' }),
      makeRealtimeData({ value: 30, status: 'offline' }),
    ]
    expect(calcAvgTemp(sensors)).toBeNull()
  })

  it('异常: 空数组返回 null', () => {
    expect(calcAvgTemp([])).toBeNull()
  })

  it('正常: 计算湿度平均值', () => {
    const sensors = [
      makeRealtimeData({ value: 40, unit: '%', status: 'normal' }),
      makeRealtimeData({ value: 60, unit: '%', status: 'normal' }),
    ]
    expect(calcAvgHumidity(sensors)).toBe(50)
  })

  it('边界: 湿度全部 offline 返回 null', () => {
    const sensors = [
      makeRealtimeData({ value: 40, unit: '%', status: 'offline' }),
    ]
    expect(calcAvgHumidity(sensors)).toBeNull()
  })

  it('异常: 湿度空数组返回 null', () => {
    expect(calcAvgHumidity([])).toBeNull()
  })
})

describe('useTemperatureData — 区域分组 (buildTempZoneGroups)', () => {
  it('正常: 按 area_code 分组并计算统计', () => {
    const sensors = [
      makeRealtimeData({ point_id: 1, area_code: 'A区', unit: '°C', value: 20, status: 'normal' }),
      makeRealtimeData({ point_id: 2, area_code: 'A区', unit: '°C', value: 30, status: 'normal' }),
      makeRealtimeData({ point_id: 3, area_code: 'A区', unit: '%', value: 50, status: 'normal' }),
      makeRealtimeData({ point_id: 4, area_code: 'B区', unit: '°C', value: 22, status: 'normal' }),
    ]
    const groups = buildTempZoneGroups(sensors, new Set())

    expect(groups).toHaveLength(2)
    expect(groups[0].areaCode).toBe('A区')
    expect(groups[0].sensors).toHaveLength(3)
    expect(groups[0].tempSensors).toHaveLength(2)
    expect(groups[0].humiditySensors).toHaveLength(1)
    expect(groups[0].avgTemp).toBe(25)
    expect(groups[0].avgHumidity).toBe(50)
    expect(groups[0].minTemp).toBe(20)
    expect(groups[0].maxTemp).toBe(30)
    expect(groups[1].areaCode).toBe('B区')
    expect(groups[1].avgTemp).toBe(22)
  })

  it('边界: 空 area_code 归入"未分区"', () => {
    const sensors = [
      makeRealtimeData({ point_id: 1, area_code: '', unit: '°C', value: 25, status: 'normal' }),
    ]
    const groups = buildTempZoneGroups(sensors, new Set())
    expect(groups[0].areaCode).toBe('未分区')
  })

  it('正常: 告警统计和 hasAlarm 标记', () => {
    const sensors = [
      makeRealtimeData({ point_id: 1, area_code: 'A区', unit: '°C', value: 25, status: 'alarm' }),
      makeRealtimeData({ point_id: 2, area_code: 'A区', unit: '°C', value: 26, status: 'normal' }),
    ]
    const groups = buildTempZoneGroups(sensors, new Set())
    expect(groups[0].alarmCount).toBe(1)
    expect(groups[0].hasAlarm).toBe(true)
  })

  it('正常: 漂移检测标记', () => {
    const sensors = [
      makeRealtimeData({ point_id: 10, area_code: 'A区', unit: '°C', value: 25, status: 'normal' }),
      makeRealtimeData({ point_id: 20, area_code: 'B区', unit: '°C', value: 26, status: 'normal' }),
    ]
    const driftIds = new Set([10])
    const groups = buildTempZoneGroups(sensors, driftIds)
    expect(groups[0].hasDrift).toBe(true)  // A区 有漂移
    expect(groups[1].hasDrift).toBe(false) // B区 无漂移
  })

  it('边界: 全部 offline 时 avgTemp/avgHumidity 为 null', () => {
    const sensors = [
      makeRealtimeData({ point_id: 1, area_code: 'A区', unit: '°C', value: 25, status: 'offline' }),
      makeRealtimeData({ point_id: 2, area_code: 'A区', unit: '%', value: 50, status: 'offline' }),
    ]
    const groups = buildTempZoneGroups(sensors, new Set())
    expect(groups[0].avgTemp).toBeNull()
    expect(groups[0].avgHumidity).toBeNull()
  })

  it('异常: 空数组返回空分组', () => {
    expect(buildTempZoneGroups([], new Set())).toHaveLength(0)
  })

  it('正常: 分组按 areaCode 字母排序', () => {
    const sensors = [
      makeRealtimeData({ point_id: 1, area_code: 'C区', unit: '°C', value: 25, status: 'normal' }),
      makeRealtimeData({ point_id: 2, area_code: 'A区', unit: '°C', value: 26, status: 'normal' }),
      makeRealtimeData({ point_id: 3, area_code: 'B区', unit: '°C', value: 27, status: 'normal' }),
    ]
    const groups = buildTempZoneGroups(sensors, new Set())
    expect(groups.map(g => g.areaCode)).toEqual(['A区', 'B区', 'C区'])
  })
})

describe('useWaterLeakData — 区域分组 (buildWaterLeakZoneGroups)', () => {
  it('正常: 按区域分组并统计各状态数量', () => {
    const sensors = [
      makeRealtimeData({ point_id: 1, device_type: 'WL', area_code: 'A区', status: 'normal' }),
      makeRealtimeData({ point_id: 2, device_type: 'WL', area_code: 'A区', status: 'alarm' }),
      makeRealtimeData({ point_id: 3, device_type: 'WL', area_code: 'A区', status: 'offline' }),
      makeRealtimeData({ point_id: 4, device_type: 'WL', area_code: 'B区', status: 'normal' }),
    ]
    const groups = buildWaterLeakZoneGroups(sensors)

    expect(groups).toHaveLength(2)
    // A区有告警，排在前面
    expect(groups[0].areaCode).toBe('A区')
    expect(groups[0].normalCount).toBe(1)
    expect(groups[0].alarmCount).toBe(1)
    expect(groups[0].offlineCount).toBe(1)
    expect(groups[0].hasAlarm).toBe(true)
    expect(groups[1].areaCode).toBe('B区')
    expect(groups[1].hasAlarm).toBe(false)
  })

  it('正常: 有告警的区域排在前面', () => {
    const sensors = [
      makeRealtimeData({ point_id: 1, device_type: 'WL', area_code: 'A区', status: 'normal' }),
      makeRealtimeData({ point_id: 2, device_type: 'WL', area_code: 'B区', status: 'alarm' }),
    ]
    const groups = buildWaterLeakZoneGroups(sensors)
    expect(groups[0].areaCode).toBe('B区') // 有告警排前面
    expect(groups[1].areaCode).toBe('A区')
  })

  it('边界: 空 area_code 归入"未分区"', () => {
    const sensors = [
      makeRealtimeData({ point_id: 1, device_type: 'WL', area_code: '', status: 'normal' }),
    ]
    const groups = buildWaterLeakZoneGroups(sensors)
    expect(groups[0].areaCode).toBe('未分区')
  })

  it('异常: 空数组返回空', () => {
    expect(buildWaterLeakZoneGroups([])).toHaveLength(0)
  })

  it('边界: 全部 offline', () => {
    const sensors = [
      makeRealtimeData({ point_id: 1, device_type: 'WL', area_code: 'A区', status: 'offline' }),
      makeRealtimeData({ point_id: 2, device_type: 'WL', area_code: 'A区', status: 'offline' }),
    ]
    const groups = buildWaterLeakZoneGroups(sensors)
    expect(groups[0].normalCount).toBe(0)
    expect(groups[0].alarmCount).toBe(0)
    expect(groups[0].offlineCount).toBe(2)
    expect(groups[0].hasAlarm).toBe(false)
  })

  it('正常: 同告警状态下按 areaCode 字母排序', () => {
    const sensors = [
      makeRealtimeData({ point_id: 1, device_type: 'WL', area_code: 'C区', status: 'normal' }),
      makeRealtimeData({ point_id: 2, device_type: 'WL', area_code: 'A区', status: 'normal' }),
    ]
    const groups = buildWaterLeakZoneGroups(sensors)
    expect(groups[0].areaCode).toBe('A区')
    expect(groups[1].areaCode).toBe('C区')
  })
})

describe('useSmokeInfraredData — 区域分组 (buildSmokeIRZoneGroups)', () => {
  it('正常: 按区域分组并分别统计烟雾和红外', () => {
    const sensors = [
      makeRealtimeData({ point_id: 1, device_type: 'SMOKE', area_code: 'A区', status: 'normal' }),
      makeRealtimeData({ point_id: 2, device_type: 'SMOKE', area_code: 'A区', status: 'alarm' }),
      makeRealtimeData({ point_id: 3, device_type: 'IR', area_code: 'A区', status: 'normal' }),
      makeRealtimeData({ point_id: 4, device_type: 'IR', area_code: 'A区', status: 'alarm' }),
    ]
    const groups = buildSmokeIRZoneGroups(sensors)

    expect(groups).toHaveLength(1)
    expect(groups[0].smokeCount).toBe(2)
    expect(groups[0].irCount).toBe(2)
    expect(groups[0].smokeAlarmCount).toBe(1)
    expect(groups[0].irAlarmCount).toBe(1)
    expect(groups[0].normalCount).toBe(2)
    expect(groups[0].alarmCount).toBe(2)
    expect(groups[0].hasAlarm).toBe(true)
  })

  it('正常: 有告警的区域排在前面', () => {
    const sensors = [
      makeRealtimeData({ point_id: 1, device_type: 'SMOKE', area_code: 'A区', status: 'normal' }),
      makeRealtimeData({ point_id: 2, device_type: 'IR', area_code: 'B区', status: 'alarm' }),
    ]
    const groups = buildSmokeIRZoneGroups(sensors)
    expect(groups[0].areaCode).toBe('B区')
    expect(groups[1].areaCode).toBe('A区')
  })

  it('正常: 只有烟雾传感器的区域', () => {
    const sensors = [
      makeRealtimeData({ point_id: 1, device_type: 'SMOKE', area_code: 'A区', status: 'normal' }),
    ]
    const groups = buildSmokeIRZoneGroups(sensors)
    expect(groups[0].smokeCount).toBe(1)
    expect(groups[0].irCount).toBe(0)
  })

  it('正常: 只有红外传感器的区域', () => {
    const sensors = [
      makeRealtimeData({ point_id: 1, device_type: 'IR', area_code: 'A区', status: 'normal' }),
    ]
    const groups = buildSmokeIRZoneGroups(sensors)
    expect(groups[0].smokeCount).toBe(0)
    expect(groups[0].irCount).toBe(1)
  })

  it('边界: 空 area_code 归入"未分区"', () => {
    const sensors = [
      makeRealtimeData({ point_id: 1, device_type: 'SMOKE', area_code: '', status: 'normal' }),
    ]
    const groups = buildSmokeIRZoneGroups(sensors)
    expect(groups[0].areaCode).toBe('未分区')
  })

  it('异常: 空数组返回空', () => {
    expect(buildSmokeIRZoneGroups([])).toHaveLength(0)
  })

  it('边界: 全部 offline 时 hasAlarm 为 false', () => {
    const sensors = [
      makeRealtimeData({ point_id: 1, device_type: 'SMOKE', area_code: 'A区', status: 'offline' }),
      makeRealtimeData({ point_id: 2, device_type: 'IR', area_code: 'A区', status: 'offline' }),
    ]
    const groups = buildSmokeIRZoneGroups(sensors)
    expect(groups[0].offlineCount).toBe(2)
    expect(groups[0].alarmCount).toBe(0)
    expect(groups[0].hasAlarm).toBe(false)
  })

  it('正常: 多区域混合排序', () => {
    const sensors = [
      makeRealtimeData({ point_id: 1, device_type: 'SMOKE', area_code: 'C区', status: 'normal' }),
      makeRealtimeData({ point_id: 2, device_type: 'IR', area_code: 'A区', status: 'alarm' }),
      makeRealtimeData({ point_id: 3, device_type: 'SMOKE', area_code: 'B区', status: 'normal' }),
    ]
    const groups = buildSmokeIRZoneGroups(sensors)
    // A区有告警排第一，B区和C区按字母排
    expect(groups[0].areaCode).toBe('A区')
    expect(groups[1].areaCode).toBe('B区')
    expect(groups[2].areaCode).toBe('C区')
  })
})
