/**
 * 容量管理 API
 */
import request from '@/utils/request'
import type { ResponseModel, PageParams } from './types'

// ==================== 类型定义 ====================

/** 容量状态 */
export type CapacityStatus = 'normal' | 'warning' | 'critical' | 'full'

/** 计划状态 */
export type PlanStatus = 'draft' | 'pending' | 'approved' | 'in_progress' | 'completed' | 'cancelled'

/** 空间容量信息 */
export interface SpaceCapacity {
  id: number
  name: string
  location?: string
  total_area: number
  used_area: number
  total_cabinets: number
  used_cabinets: number
  total_u_positions: number
  used_u_positions: number
  warning_threshold: number
  critical_threshold: number
  status: CapacityStatus
  usage_rate: number
  created_at: string
  updated_at: string
}

/** 空间容量创建参数 */
export interface SpaceCapacityCreate {
  name: string
  location?: string
  total_area: number
  used_area?: number
  total_cabinets: number
  used_cabinets?: number
  total_u_positions: number
  used_u_positions?: number
  warning_threshold?: number
  critical_threshold?: number
}

/** 电力容量信息 */
export interface PowerCapacity {
  id: number
  name: string
  location?: string
  total_power: number
  used_power: number
  reserved_power: number
  available_power: number
  warning_threshold: number
  critical_threshold: number
  status: CapacityStatus
  usage_rate: number
  pue?: number
  created_at: string
  updated_at: string
}

/** 电力容量创建参数 */
export interface PowerCapacityCreate {
  name: string
  location?: string
  total_power: number
  used_power?: number
  reserved_power?: number
  warning_threshold?: number
  critical_threshold?: number
}

/** 制冷容量信息 */
export interface CoolingCapacity {
  id: number
  name: string
  location?: string
  total_cooling: number
  used_cooling: number
  reserved_cooling: number
  available_cooling: number
  warning_threshold: number
  critical_threshold: number
  status: CapacityStatus
  usage_rate: number
  created_at: string
  updated_at: string
}

/** 制冷容量创建参数 */
export interface CoolingCapacityCreate {
  name: string
  location?: string
  total_cooling: number
  used_cooling?: number
  reserved_cooling?: number
  warning_threshold?: number
  critical_threshold?: number
}

/** 承重容量信息 */
export interface WeightCapacity {
  id: number
  name: string
  location?: string
  total_weight: number
  used_weight: number
  warning_threshold: number
  critical_threshold: number
  status: CapacityStatus
  usage_rate: number
  created_at: string
  updated_at: string
}

/** 承重容量创建参数 */
export interface WeightCapacityCreate {
  name: string
  location?: string
  total_weight: number
  used_weight?: number
  warning_threshold?: number
  critical_threshold?: number
}

/** 容量规划 */
export interface CapacityPlan {
  id: number
  plan_name: string
  plan_type: string
  description?: string
  target_date: string
  space_requirement?: number
  power_requirement?: number
  cooling_requirement?: number
  weight_requirement?: number
  status: PlanStatus
  priority: number
  created_by?: string
  approved_by?: string
  approved_at?: string
  created_at: string
  updated_at: string
}

/** 容量规划创建参数 */
export interface CapacityPlanCreate {
  plan_name: string
  plan_type: string
  description?: string
  target_date: string
  space_requirement?: number
  power_requirement?: number
  cooling_requirement?: number
  weight_requirement?: number
  priority?: number
}

/** 容量统计 - 空间 */
export interface SpaceStatistics {
  total_area: number
  used_area: number
  available_area: number
  usage_rate: number
  total_cabinets: number
  used_cabinets: number
  total_u_positions: number
  used_u_positions: number
}

/** 容量统计 - 电力 */
export interface PowerStatistics {
  total_power: number
  used_power: number
  reserved_power: number
  available_power: number
  usage_rate: number
  average_pue: number
}

/** 容量统计 - 制冷 */
export interface CoolingStatistics {
  total_cooling: number
  used_cooling: number
  reserved_cooling: number
  available_cooling: number
  usage_rate: number
}

/** 容量统计 - 承重 */
export interface WeightStatistics {
  total_weight: number
  used_weight: number
  available_weight: number
  usage_rate: number
}

/** 容量综合统计 */
export interface CapacityStatistics {
  space: SpaceStatistics
  power: PowerStatistics
  cooling: CoolingStatistics
  weight: WeightStatistics
  warning_count: number
  critical_count: number
  plan_count: number
}

// ==================== 空间容量 API ====================

/** 获取空间容量列表 */
export function getSpaceCapacities(params?: PageParams & {
  location?: string
  status?: CapacityStatus
  keyword?: string
}) {
  return request.get<ResponseModel<SpaceCapacity[]>>('/v1/capacity/space', { params })
}

/** 获取空间容量详情 */
export function getSpaceCapacity(id: number) {
  return request.get<ResponseModel<SpaceCapacity>>(`/v1/capacity/space/${id}`)
}

/** 创建空间容量 */
export function createSpaceCapacity(data: SpaceCapacityCreate) {
  return request.post<ResponseModel<SpaceCapacity>>('/v1/capacity/space', data)
}

/** 更新空间容量 */
export function updateSpaceCapacity(id: number, data: Partial<SpaceCapacityCreate>) {
  return request.put<ResponseModel<SpaceCapacity>>(`/v1/capacity/space/${id}`, data)
}

/** 删除空间容量 */
export function deleteSpaceCapacity(id: number) {
  return request.delete<ResponseModel>(`/v1/capacity/space/${id}`)
}

// ==================== 电力容量 API ====================

/** 获取电力容量列表 */
export function getPowerCapacities(params?: PageParams & {
  location?: string
  status?: CapacityStatus
  keyword?: string
}) {
  return request.get<ResponseModel<PowerCapacity[]>>('/v1/capacity/power', { params })
}

/** 获取电力容量详情 */
export function getPowerCapacity(id: number) {
  return request.get<ResponseModel<PowerCapacity>>(`/v1/capacity/power/${id}`)
}

/** 创建电力容量 */
export function createPowerCapacity(data: PowerCapacityCreate) {
  return request.post<ResponseModel<PowerCapacity>>('/v1/capacity/power', data)
}

/** 更新电力容量 */
export function updatePowerCapacity(id: number, data: Partial<PowerCapacityCreate>) {
  return request.put<ResponseModel<PowerCapacity>>(`/v1/capacity/power/${id}`, data)
}

/** 删除电力容量 */
export function deletePowerCapacity(id: number) {
  return request.delete<ResponseModel>(`/v1/capacity/power/${id}`)
}

// ==================== 制冷容量 API ====================

/** 获取制冷容量列表 */
export function getCoolingCapacities(params?: PageParams & {
  location?: string
  status?: CapacityStatus
  keyword?: string
}) {
  return request.get<ResponseModel<CoolingCapacity[]>>('/v1/capacity/cooling', { params })
}

/** 获取制冷容量详情 */
export function getCoolingCapacity(id: number) {
  return request.get<ResponseModel<CoolingCapacity>>(`/v1/capacity/cooling/${id}`)
}

/** 创建制冷容量 */
export function createCoolingCapacity(data: CoolingCapacityCreate) {
  return request.post<ResponseModel<CoolingCapacity>>('/v1/capacity/cooling', data)
}

/** 更新制冷容量 */
export function updateCoolingCapacity(id: number, data: Partial<CoolingCapacityCreate>) {
  return request.put<ResponseModel<CoolingCapacity>>(`/v1/capacity/cooling/${id}`, data)
}

/** 删除制冷容量 */
export function deleteCoolingCapacity(id: number) {
  return request.delete<ResponseModel>(`/v1/capacity/cooling/${id}`)
}

// ==================== 承重容量 API ====================

/** 获取承重容量列表 */
export function getWeightCapacities(params?: PageParams & {
  location?: string
  status?: CapacityStatus
  keyword?: string
}) {
  return request.get<ResponseModel<WeightCapacity[]>>('/v1/capacity/weight', { params })
}

/** 获取承重容量详情 */
export function getWeightCapacity(id: number) {
  return request.get<ResponseModel<WeightCapacity>>(`/v1/capacity/weight/${id}`)
}

/** 创建承重容量 */
export function createWeightCapacity(data: WeightCapacityCreate) {
  return request.post<ResponseModel<WeightCapacity>>('/v1/capacity/weight', data)
}

/** 更新承重容量 */
export function updateWeightCapacity(id: number, data: Partial<WeightCapacityCreate>) {
  return request.put<ResponseModel<WeightCapacity>>(`/v1/capacity/weight/${id}`, data)
}

/** 删除承重容量 */
export function deleteWeightCapacity(id: number) {
  return request.delete<ResponseModel>(`/v1/capacity/weight/${id}`)
}

// ==================== 容量规划 API ====================

/** 获取容量规划列表 */
export function getCapacityPlans(params?: PageParams & {
  plan_type?: string
  status?: PlanStatus
  keyword?: string
}) {
  return request.get<ResponseModel<CapacityPlan[]>>('/v1/capacity/plans', { params })
}

/** 获取容量规划详情 */
export function getCapacityPlan(id: number) {
  return request.get<ResponseModel<CapacityPlan>>(`/v1/capacity/plans/${id}`)
}

/** 创建容量规划 */
export function createCapacityPlan(data: CapacityPlanCreate) {
  return request.post<ResponseModel<CapacityPlan>>('/v1/capacity/plans', data)
}

/** 更新容量规划 */
export function updateCapacityPlan(id: number, data: Partial<CapacityPlanCreate>) {
  return request.put<ResponseModel<CapacityPlan>>(`/v1/capacity/plans/${id}`, data)
}

/** 删除容量规划 */
export function deleteCapacityPlan(id: number) {
  return request.delete<ResponseModel>(`/v1/capacity/plans/${id}`)
}

/** 审批容量规划 */
export function approveCapacityPlan(id: number, approved: boolean, comment?: string) {
  return request.post<ResponseModel<CapacityPlan>>(`/v1/capacity/plans/${id}/approve`, { approved, comment })
}

/** 更新容量规划状态 */
export function updateCapacityPlanStatus(id: number, status: PlanStatus) {
  return request.put<ResponseModel<CapacityPlan>>(`/v1/capacity/plans/${id}/status`, { status })
}

// ==================== 统计 API ====================

/** 获取容量综合统计 */
export function getCapacityStatistics() {
  return request.get<ResponseModel<CapacityStatistics>>('/v1/capacity/statistics')
}

/** 获取容量趋势数据 */
export function getCapacityTrend(params?: {
  type?: 'space' | 'power' | 'cooling' | 'weight'
  start_time?: string
  end_time?: string
  interval?: 'hour' | 'day' | 'week' | 'month'
}) {
  return request.get<ResponseModel<{
    timestamps: string[]
    total: number[]
    used: number[]
    usage_rate: number[]
  }>>('/v1/capacity/trend', { params })
}

/** 获取容量预测数据 */
export function getCapacityForecast(params?: {
  type?: 'space' | 'power' | 'cooling' | 'weight'
  days?: number
}) {
  return request.get<ResponseModel<{
    timestamps: string[]
    predicted_usage: number[]
    confidence_upper: number[]
    confidence_lower: number[]
  }>>('/v1/capacity/forecast', { params })
}

/** 获取容量告警列表 */
export function getCapacityAlerts(params?: PageParams & {
  type?: 'space' | 'power' | 'cooling' | 'weight'
  status?: CapacityStatus
}) {
  return request.get<ResponseModel<{
    id: number
    type: string
    name: string
    location: string
    status: CapacityStatus
    usage_rate: number
    threshold: number
    created_at: string
  }[]>>('/v1/capacity/alerts', { params })
}
