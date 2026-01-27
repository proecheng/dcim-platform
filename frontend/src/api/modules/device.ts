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
