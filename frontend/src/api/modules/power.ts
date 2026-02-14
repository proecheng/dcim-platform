/**
 * 供配电管理 API
 */
import request from '@/utils/request'

// ===== 类型定义 =====

export interface PowerOverviewSummary {
  ups_total: number
  ups_online: number
  ups_offline: number
  ups_alarm: number
  battery_total: number
  battery_avg_soh: number
  battery_lowest_soc: number
  cabinet_total: number
  pdu_total: number
  total_load_kw: number
  avg_load_rate: number
}

export interface UPSDeviceInfo {
  id: number
  device_id: number
  ups_type: string
  rated_capacity: number
  rated_voltage: number
  phase_count: number
  battery_group_count: number
  bypass_enabled: boolean
  description: string | null
  created_at: string
  updated_at: string
  // 关联的 Device 信息（由后端 join 返回）
  device_code?: string
  device_name?: string
  area_code?: string
  status?: string
}

export interface BatteryGroupInfo {
  id: number
  ups_device_id: number
  group_name: string
  battery_type: string
  rated_capacity: number
  rated_voltage: number
  cell_count: number
  install_date: string | null
  description: string | null
  created_at: string
  updated_at: string
}

export interface PointRealtimeValue {
  point_code: string
  point_name: string
  value: number | null
  unit: string
  status: string
}

// ===== API 调用 =====

/** 获取供配电总览 */
export function getPowerOverview() {
  return request.get<any, PowerOverviewSummary>('/v1/power/overview')
}

/** 获取 UPS 列表 */
export function getUPSList(params?: { page?: number; page_size?: number; status?: string }) {
  return request.get<any, any>('/v1/power/ups', { params })
}

/** 获取 UPS 详情（含实时点位数据） */
export function getUPSDetail(id: number) {
  return request.get<any, any>(`/v1/power/ups/${id}`)
}

/** 获取电池组列表 */
export function getBatteryList(params?: { page?: number; page_size?: number }) {
  return request.get<any, any>('/v1/power/batteries', { params })
}

/** 获取电池组详情 */
export function getBatteryDetail(id: number) {
  return request.get<any, any>(`/v1/power/batteries/${id}`)
}

/** 获取配电柜列表 */
export function getCabinetList(params?: { page?: number; page_size?: number }) {
  return request.get<any, any>('/v1/power/cabinets', { params })
}

/** 获取 PDU 列表 */
export function getPDUList(params?: { page?: number; page_size?: number }) {
  return request.get<any, any>('/v1/power/pdus', { params })
}
