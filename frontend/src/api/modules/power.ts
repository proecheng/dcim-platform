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

export interface UPSDeviceCreate {
  device_id: number
  ups_type: string
  rated_capacity: number
  rated_voltage: number
  phase_count: number
  battery_group_count?: number
  bypass_enabled?: boolean
  description?: string | null
}

export interface UPSDeviceUpdate {
  ups_type?: string
  rated_capacity?: number
  rated_voltage?: number
  phase_count?: number
  battery_group_count?: number
  bypass_enabled?: boolean
  description?: string | null
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

export interface BatteryGroupCreate {
  ups_device_id: number
  group_name: string
  battery_type: string
  rated_capacity: number
  rated_voltage: number
  cell_count: number
  install_date?: string | null
  description?: string | null
}

export interface BatteryGroupUpdate {
  group_name?: string
  battery_type?: string
  rated_capacity?: number
  rated_voltage?: number
  cell_count?: number
  install_date?: string | null
  description?: string | null
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
  return request.get<PowerOverviewSummary>('/v1/power/overview')
}

/** 获取 UPS 列表 */
export function getUPSList(params?: { page?: number; page_size?: number; status?: string }) {
  return request.get<any>('/v1/power/ups', { params })
}

/** 获取 UPS 详情（含实时点位数据） */
export function getUPSDetail(id: number) {
  return request.get<any>(`/v1/power/ups/${id}`)
}

/** 创建 UPS 设备 */
export function createUPS(data: UPSDeviceCreate) {
  return request.post<any>('/v1/power/ups', data)
}

/** 更新 UPS 设备 */
export function updateUPS(id: number, data: UPSDeviceUpdate) {
  return request.put<any>(`/v1/power/ups/${id}`, data)
}

/** 删除 UPS 设备 */
export function deleteUPS(id: number) {
  return request.delete<any>(`/v1/power/ups/${id}`)
}

/** 获取电池组列表 */
export function getBatteryList(params?: { page?: number; page_size?: number }) {
  return request.get<any>('/v1/power/batteries', { params })
}

/** 获取电池组详情 */
export function getBatteryDetail(id: number) {
  return request.get<any>(`/v1/power/batteries/${id}`)
}

/** 创建电池组 */
export function createBatteryGroup(data: BatteryGroupCreate) {
  return request.post<any>('/v1/power/batteries', data)
}

/** 更新电池组 */
export function updateBatteryGroup(id: number, data: BatteryGroupUpdate) {
  return request.put<any>(`/v1/power/batteries/${id}`, data)
}

/** 删除电池组 */
export function deleteBatteryGroup(id: number) {
  return request.delete<any>(`/v1/power/batteries/${id}`)
}

/** 获取配电柜列表 */
export function getCabinetList(params?: { page?: number; page_size?: number }) {
  return request.get<any>('/v1/power/cabinets', { params })
}

/** 获取配电柜支路详情 */
export function getCabinetBranches(deviceId: number) {
  return request.get<any>(`/v1/power/cabinets/${deviceId}/branches`)
}

/** 获取 PDU 列表 */
export function getPDUList(params?: { page?: number; page_size?: number }) {
  return request.get<any>('/v1/power/pdus', { params })
}
