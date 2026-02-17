/**
 * 制冷系统 API
 */
import request from '@/utils/request'

// ===== 类型定义 =====

export interface CoolingOverviewSummary {
  ac_total: number
  ac_running: number
  ac_stopped: number
  ac_alarm: number
  avg_supply_temp: number
  avg_return_temp: number
  cold_aisle_total: number
  group_total: number
  group_linked: number
}

export interface CoolingUnitInfo {
  id: number
  device_id: number
  unit_type: string
  cooling_capacity_kw: number
  refrigerant_type: string | null
  compressor_count: number
  fan_count: number
  group_id: number | null
  description: string | null
  created_at: string
  updated_at: string
  // 关联的 Device 信息（由后端 join 返回）
  device_code?: string
  device_name?: string
  area_code?: string
  status?: string
}

export interface CoolingGroupInfo {
  id: number
  group_name: string
  group_mode: string
  description: string | null
  created_at: string
  updated_at: string
}

export interface ColdAisleInfo {
  id: number
  device_id: number
  aisle_code: string
  aisle_name: string
  skylight_count: number
  location: string | null
  description: string | null
  created_at: string
  updated_at: string
}

// ===== API 调用 =====

/** 获取制冷系统总览 */
export function getCoolingOverview() {
  return request.get<any, CoolingOverviewSummary>('/v1/cooling/overview')
}

/** 获取空调列表 */
export function getCoolingUnitList(params?: { page?: number; page_size?: number; unit_type?: string; group_id?: number }) {
  return request.get<any, any>('/v1/cooling/units', { params })
}

/** 获取空调详情（含实时点位数据） */
export function getCoolingUnitDetail(id: number) {
  return request.get<any, any>(`/v1/cooling/units/${id}`)
}

/** 获取群控组列表 */
export function getCoolingGroupList(params?: { page?: number; page_size?: number }) {
  return request.get<any, any>('/v1/cooling/groups', { params })
}

/** 获取冷通道列表 */
export function getColdAisleList(params?: { page?: number; page_size?: number }) {
  return request.get<any, any>('/v1/cooling/cold-aisles', { params })
}

/** 获取冷通道详情 */
export function getColdAisleDetail(id: number) {
  return request.get<any, any>(`/v1/cooling/cold-aisles/${id}`)
}
