/**
 * 实时数据 API
 */
import request from '@/utils/request'

export interface RealtimeData {
  point_id: number
  point_code: string
  point_name: string
  point_type: 'AI' | 'DI' | 'AO' | 'DO'
  device_type: string
  area_code: string
  raw_value: number
  value: number
  value_text: string
  unit: string
  quality: number
  status: 'normal' | 'alarm' | 'offline'
  alarm_level: string | null
  change_count: number
  last_change_at: string
  updated_at: string
}

export interface RealtimeSummary {
  total_points: number
  online_points: number
  offline_points: number
  alarm_points: number
  by_type: Record<string, {
    total: number
    alarm: number
    offline: number
  }>
  by_area: Record<string, {
    total: number
    alarm: number
    offline: number
  }>
}

export interface DashboardData {
  overview: {
    total_points: number
    online_points: number
    alarm_count: number
    device_count: number
  }
  realtime: RealtimeData[]
  alarms: any[]
  trends: {
    point_id: number
    point_name: string
    values: { time: string; value: number }[]
  }[]
}

export interface ControlCommand {
  point_id: number
  value: number
  remark?: string
}

/**
 * 获取所有点位实时数据
 */
export function getAllRealtimeData(params?: {
  point_ids?: number[]
  is_enabled?: boolean
}): Promise<RealtimeData[]> {
  return request.get('/v1/realtime', { params })
}

/**
 * 获取单个点位实时数据
 */
export function getPointRealtimeData(pointId: number): Promise<RealtimeData> {
  return request.get(`/v1/realtime/${pointId}`)
}

/**
 * 按类型获取实时数据
 */
export function getRealtimeByType(type: 'AI' | 'DI' | 'AO' | 'DO'): Promise<RealtimeData[]> {
  return request.get(`/v1/realtime/by-type/${type}`)
}

/**
 * 按区域获取实时数据
 */
export function getRealtimeByArea(areaCode: string): Promise<RealtimeData[]> {
  return request.get(`/v1/realtime/by-area/${areaCode}`)
}

/**
 * 按设备获取实时数据
 */
export function getRealtimeByDevice(deviceId: number): Promise<RealtimeData[]> {
  return request.get(`/v1/realtime/by-device/${deviceId}`)
}

/**
 * 按分组获取实时数据
 */
export function getRealtimeByGroup(groupId: number): Promise<RealtimeData[]> {
  return request.get(`/v1/realtime/by-group/${groupId}`)
}

/**
 * 获取实时数据汇总
 */
export function getRealtimeSummary(): Promise<RealtimeSummary> {
  return request.get('/v1/realtime/summary')
}

/**
 * 获取仪表盘数据
 */
export function getDashboardData(): Promise<DashboardData> {
  return request.get('/v1/realtime/dashboard')
}

/**
 * 下发控制指令
 */
export function sendControlCommand(pointId: number, command: ControlCommand): Promise<void> {
  return request.post(`/v1/realtime/control/${pointId}`, command)
}
