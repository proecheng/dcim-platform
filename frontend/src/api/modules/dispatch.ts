/**
 * 可调度资源配置 API
 * 包括：可调度设备、储能系统、光伏系统的配置管理
 */
import request from '@/utils/request'
import type { ResponseModel } from './types'

// ==================== 类型定义 ====================

/** 设备类型枚举 */
export type DeviceType = 'shiftable' | 'curtailable' | 'modulating' | 'generation' | 'storage' | 'rigid'

/** 设备类型中文映射 */
export const deviceTypeLabels: Record<DeviceType, string> = {
  shiftable: '时移型',
  curtailable: '削减型',
  modulating: '调节型',
  generation: '发电型',
  storage: '储能型',
  rigid: '刚性型'
}

/** 设备类型描述 */
export const deviceTypeDescriptions: Record<DeviceType, string> = {
  shiftable: '固定能量需求，可灵活选择运行时间',
  curtailable: '可在高峰时段临时降低或关闭',
  modulating: '功率可在一定范围内连续调节',
  generation: '提供发电能力（如光伏、发电机）',
  storage: '可充可放，双向调节',
  rigid: '不可调度，作为优化约束条件'
}

/** 可调度设备 */
export interface DispatchableDevice {
  id: number
  name: string
  device_type: DeviceType
  rated_power: number
  min_power?: number
  max_power?: number

  // 时移型参数
  run_duration?: number
  daily_runs?: number
  allowed_periods?: number[]
  forbidden_periods?: number[]

  // 削减型参数
  curtail_ratio?: number
  max_curtail_duration?: number
  max_curtail_per_day?: number
  recovery_time?: number

  // 调节型参数
  ramp_rate?: number
  response_delay?: number

  // 发电型参数
  generation_cost?: number
  is_controllable?: boolean

  // 通用参数
  priority: number
  is_active: boolean
  meter_point_id?: number
  power_device_id?: number
  description?: string
}

/** 创建/更新可调度设备 */
export interface DispatchableDeviceInput {
  name: string
  device_type: DeviceType
  rated_power: number
  min_power?: number
  max_power?: number
  run_duration?: number
  daily_runs?: number
  allowed_periods?: number[]
  forbidden_periods?: number[]
  curtail_ratio?: number
  max_curtail_duration?: number
  max_curtail_per_day?: number
  recovery_time?: number
  ramp_rate?: number
  response_delay?: number
  generation_cost?: number
  is_controllable?: boolean
  priority?: number
  is_active?: boolean
  meter_point_id?: number
  power_device_id?: number
  description?: string
}

/** 储能系统配置 */
export interface StorageConfig {
  id: number
  name: string
  capacity: number
  max_charge_power: number
  max_discharge_power: number
  charge_efficiency: number
  discharge_efficiency: number
  min_soc: number
  max_soc: number
  cycle_cost: number
  is_active: boolean
  meter_point_id?: number
  description?: string
}

/** 创建/更新储能配置 */
export interface StorageConfigInput {
  name: string
  capacity: number
  max_charge_power: number
  max_discharge_power: number
  charge_efficiency?: number
  discharge_efficiency?: number
  min_soc?: number
  max_soc?: number
  cycle_cost?: number
  is_active?: boolean
  meter_point_id?: number
  description?: string
}

/** 光伏系统配置 */
export interface PVConfig {
  id: number
  name: string
  rated_capacity: number
  efficiency: number
  is_controllable: boolean
  is_active: boolean
  meter_point_id?: number
  description?: string
}

/** 创建/更新光伏配置 */
export interface PVConfigInput {
  name: string
  rated_capacity: number
  efficiency?: number
  is_controllable?: boolean
  is_active?: boolean
  meter_point_id?: number
  description?: string
}

/** 设备统计 */
export interface DeviceStats {
  total: number
  active_count: number
  by_type: Array<{
    type: DeviceType
    count: number
    total_power: number
  }>
}

/** 资源汇总 */
export interface DispatchSummary {
  dispatchable_devices: {
    count: number
    total_power: number
  }
  storage_systems: {
    count: number
    total_capacity: number
    total_charge_power: number
    total_discharge_power: number
  }
  pv_systems: {
    count: number
    total_capacity: number
  }
}

// ==================== 可调度设备 API ====================

/** 获取可调度设备列表 */
export function getDispatchableDevices(params?: {
  device_type?: DeviceType
  is_active?: boolean
}) {
  return request.get<ResponseModel<DispatchableDevice[]>>('/v1/dispatch/devices', { params })
}

/** 获取单个可调度设备 */
export function getDispatchableDevice(id: number) {
  return request.get<ResponseModel<DispatchableDevice>>(`/v1/dispatch/devices/${id}`)
}

/** 创建可调度设备 */
export function createDispatchableDevice(data: DispatchableDeviceInput) {
  return request.post<ResponseModel<DispatchableDevice>>('/v1/dispatch/devices', data)
}

/** 更新可调度设备 */
export function updateDispatchableDevice(id: number, data: Partial<DispatchableDeviceInput>) {
  return request.put<ResponseModel<DispatchableDevice>>(`/v1/dispatch/devices/${id}`, data)
}

/** 删除可调度设备 */
export function deleteDispatchableDevice(id: number) {
  return request.delete<ResponseModel<{ message: string }>>(`/v1/dispatch/devices/${id}`)
}

/** 获取设备统计 */
export function getDeviceStats() {
  return request.get<ResponseModel<DeviceStats>>('/v1/dispatch/devices/summary/stats')
}

// ==================== 储能系统 API ====================

/** 获取储能系统列表 */
export function getStorageSystems(params?: { is_active?: boolean }) {
  return request.get<ResponseModel<StorageConfig[]>>('/v1/dispatch/storage', { params })
}

/** 获取单个储能系统 */
export function getStorageSystem(id: number) {
  return request.get<ResponseModel<StorageConfig>>(`/v1/dispatch/storage/${id}`)
}

/** 创建储能系统 */
export function createStorageSystem(data: StorageConfigInput) {
  return request.post<ResponseModel<StorageConfig>>('/v1/dispatch/storage', data)
}

/** 更新储能系统 */
export function updateStorageSystem(id: number, data: Partial<StorageConfigInput>) {
  return request.put<ResponseModel<StorageConfig>>(`/v1/dispatch/storage/${id}`, data)
}

/** 删除储能系统 */
export function deleteStorageSystem(id: number) {
  return request.delete<ResponseModel<{ message: string }>>(`/v1/dispatch/storage/${id}`)
}

// ==================== 光伏系统 API ====================

/** 获取光伏系统列表 */
export function getPVSystems(params?: { is_active?: boolean }) {
  return request.get<ResponseModel<PVConfig[]>>('/v1/dispatch/pv', { params })
}

/** 获取单个光伏系统 */
export function getPVSystem(id: number) {
  return request.get<ResponseModel<PVConfig>>(`/v1/dispatch/pv/${id}`)
}

/** 创建光伏系统 */
export function createPVSystem(data: PVConfigInput) {
  return request.post<ResponseModel<PVConfig>>('/v1/dispatch/pv', data)
}

/** 更新光伏系统 */
export function updatePVSystem(id: number, data: Partial<PVConfigInput>) {
  return request.put<ResponseModel<PVConfig>>(`/v1/dispatch/pv/${id}`, data)
}

/** 删除光伏系统 */
export function deletePVSystem(id: number) {
  return request.delete<ResponseModel<{ message: string }>>(`/v1/dispatch/pv/${id}`)
}

// ==================== 汇总 API ====================

/** 获取所有可调度资源汇总 */
export function getDispatchSummary() {
  return request.get<ResponseModel<DispatchSummary>>('/v1/dispatch/summary')
}

/** 初始化演示数据 */
export function initDemoData() {
  return request.post<ResponseModel<{
    message: string
    created: boolean
    data?: { devices: number; storage: number; pv: number }
  }>>('/v1/dispatch/init-demo-data')
}
