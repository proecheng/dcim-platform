/**
 * 设备管理 API
 */
import request from '@/utils/request'
import type { PageParams, PageResponse } from './types'

export interface DeviceInfo {
  id: number
  device_code: string
  device_name: string
  device_type: string
  area_code: string
  manufacturer: string
  model: string
  serial_number: string
  install_date: string
  status: 'online' | 'offline' | 'maintenance'
  location_x: number
  location_y: number
  description: string
  is_enabled: boolean
  created_at: string
  updated_at: string
}

export interface DeviceCreateParams {
  device_code: string
  device_name: string
  device_type: string
  area_code: string
  manufacturer?: string
  model?: string
  serial_number?: string
  install_date?: string
  location_x?: number
  location_y?: number
  description?: string
}

export interface DeviceUpdateParams extends Partial<DeviceCreateParams> {
  status?: 'online' | 'offline' | 'maintenance'
  is_enabled?: boolean
}

export interface DeviceTreeNode {
  id: number
  label: string
  type: 'area' | 'device_type' | 'device'
  children?: DeviceTreeNode[]
  data?: DeviceInfo
}

export interface DeviceStatusSummary {
  total: number
  online: number
  offline: number
  maintenance: number
  alarm: number
  by_type: Record<string, number>
}

/**
 * 获取设备列表
 */
export function getDeviceList(params?: PageParams & {
  device_type?: string
  area_code?: string
  status?: string
  keyword?: string
}): Promise<PageResponse<DeviceInfo>> {
  return request.get('/v1/devices', { params })
}

/**
 * 获取设备详情
 */
export function getDeviceById(id: number): Promise<DeviceInfo> {
  return request.get(`/v1/devices/${id}`)
}

/**
 * 创建设备
 */
export function createDevice(data: DeviceCreateParams): Promise<DeviceInfo> {
  return request.post('/v1/devices', data)
}

/**
 * 更新设备
 */
export function updateDevice(id: number, data: DeviceUpdateParams): Promise<DeviceInfo> {
  return request.put(`/v1/devices/${id}`, data)
}

/**
 * 删除设备
 */
export function deleteDevice(id: number): Promise<void> {
  return request.delete(`/v1/devices/${id}`)
}

/**
 * 设备详情聚合响应 — 点位实时数据项
 */
export interface PointRealtimeItem {
  id: number
  point_code: string
  point_name: string
  point_type: string
  device_type: string | null
  unit: string | null
  value: number | null
  value_text: string | null
  status: string
  alarm_level: string | null
  quality: number | null
  updated_at: string | null
}

/**
 * 设备详情聚合响应 — 告警项
 */
export interface AlarmItem {
  id: number
  alarm_no: string
  point_id: number
  alarm_level: string
  alarm_message: string
  trigger_value: number | null
  threshold_value: number | null
  status: string
  created_at: string | null
}

/**
 * 设备详情聚合响应
 */
export interface DeviceDetailResponse {
  device: DeviceInfo
  points: PointRealtimeItem[]
  alarms: AlarmItem[]
}

/**
 * 获取设备详情（聚合：设备信息 + 点位实时数据 + 活动告警）
 */
export function getDeviceDetail(id: number): Promise<DeviceDetailResponse> {
  return request.get(`/v1/devices/${id}/detail`)
}

/**
 * 获取设备下的点位
 */
export function getDevicePoints(id: number): Promise<any[]> {
  return request.get(`/v1/devices/${id}/points`)
}

/**
 * 获取设备树结构
 */
export function getDeviceTree(): Promise<DeviceTreeNode[]> {
  return request.get('/v1/devices/tree')
}

/**
 * 获取设备状态汇总
 */
export function getDeviceStatusSummary(): Promise<DeviceStatusSummary> {
  return request.get('/v1/devices/status-summary')
}

/**
 * 设备状态看板 — 状态项
 */
export interface DeviceStatusItem {
  id: number
  device_code: string
  device_name: string
  status: string
}

/**
 * 设备状态看板 — 分组
 */
export interface DeviceStatusGroup {
  area_code: string
  device_type: string
  devices: DeviceStatusItem[]
  stats: { online: number; offline: number; alarm: number; maintenance: number }
}

/**
 * 设备状态看板 — 响应
 */
export interface DeviceStatusBoardResponse {
  summary: { total: number; online: number; offline: number; alarm: number; maintenance: number }
  groups: DeviceStatusGroup[]
}

/**
 * 获取设备状态看板
 */
export function getDeviceStatusBoard(params?: { area_code?: string; device_type?: string }): Promise<DeviceStatusBoardResponse> {
  return request.get('/v1/devices/status-board', { params })
}
