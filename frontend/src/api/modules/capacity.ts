/**
 * 容量管理 API
 */
import request from '@/utils/request'
import type { ResponseModel, PageParams } from './types'

// ==================== 类型定义 ====================

/** 容量状态 */
export type CapacityStatus = 'normal' | 'warning' | 'critical' | 'full'

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
  usage_rate: number | null
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
  capacity_type?: string
  total_capacity_kva?: number
  used_capacity_kva?: number
  total_capacity_kw?: number
  used_capacity_kw?: number
  redundancy_mode?: string
  warning_threshold: number
  critical_threshold: number
  status: CapacityStatus
  usage_rate: number | null
  created_at: string
  updated_at: string
}

/** 电力容量创建参数 */
export interface PowerCapacityCreate {
  name: string
  location?: string
  capacity_type?: string
  total_capacity_kva?: number
  used_capacity_kva?: number
  total_capacity_kw?: number
  used_capacity_kw?: number
  redundancy_mode?: string
  warning_threshold?: number
  critical_threshold?: number
  parent_id?: number
}

/** 制冷容量信息 */
export interface CoolingCapacity {
  id: number
  name: string
  location?: string
  total_cooling_kw?: number
  used_cooling_kw?: number
  target_temperature?: number
  current_temperature?: number
  humidity_target?: number
  current_humidity?: number
  warning_threshold: number
  critical_threshold: number
  status: CapacityStatus
  usage_rate: number | null
  created_at: string
  updated_at: string
}

/** 制冷容量创建参数 */
export interface CoolingCapacityCreate {
  name: string
  location?: string
  total_cooling_kw?: number
  used_cooling_kw?: number
  target_temperature?: number
  current_temperature?: number
  humidity_target?: number
  current_humidity?: number
  warning_threshold?: number
  critical_threshold?: number
}

/** 承重容量信息 */
export interface WeightCapacity {
  id: number
  name: string
  location?: string
  capacity_type?: string
  total_weight_kg?: number
  used_weight_kg?: number
  warning_threshold: number
  critical_threshold: number
  status: CapacityStatus
  usage_rate: number | null
  created_at: string
  updated_at: string
}

/** 承重容量创建参数 */
export interface WeightCapacityCreate {
  name: string
  location?: string
  capacity_type?: string
  total_weight_kg?: number
  used_weight_kg?: number
  warning_threshold?: number
  critical_threshold?: number
}

/** 容量规划 */
export interface CapacityPlan {
  id: number
  name: string
  description?: string
  device_count?: number
  required_u?: number
  required_power_kw?: number
  required_cooling_kw?: number
  required_weight_kg?: number
  target_cabinet_id?: number
  is_feasible?: boolean
  feasibility_notes?: string
  created_by?: string
  created_at: string
  updated_at: string
}

/** 容量规划创建参数 */
export interface CapacityPlanCreate {
  name: string
  description?: string
  device_count?: number
  required_u?: number
  required_power_kw?: number
  required_cooling_kw?: number
  required_weight_kg?: number
  target_cabinet_id?: number
  created_by?: string
}

/** 容量统计 - 空间 */
export interface SpaceStatistics {
  total_u_positions: number
  used_u_positions: number
  available_u_positions: number
  usage_rate: number
  count: number
}

/** 容量统计 - 电力 */
export interface PowerStatistics {
  total_capacity_kw: number
  used_capacity_kw: number
  available_capacity_kw: number
  usage_rate: number
  count: number
}

/** 容量统计 - 制冷 */
export interface CoolingStatistics {
  total_cooling_kw: number
  used_cooling_kw: number
  available_cooling_kw: number
  usage_rate: number
  count: number
}

/** 容量统计 - 承重 */
export interface WeightStatistics {
  total_weight_kg: number
  used_weight_kg: number
  available_weight_kg: number
  usage_rate: number
  count: number
}

/** 容量综合统计 */
export interface CapacityStatistics {
  space: SpaceStatistics
  power: PowerStatistics
  cooling: CoolingStatistics
  weight: WeightStatistics
  status_summary: Record<string, number>
  total_capacity_records: number
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

// ==================== 统计 API ====================

/** 获取容量综合统计 */
export function getCapacityStatistics() {
  return request.get<ResponseModel<CapacityStatistics>>('/v1/capacity/statistics')
}

/** 按位置获取容量统计 */
export function getCapacityByLocation(params?: {
  dimension?: 'area' | 'floor' | 'room'
}) {
  return request.get<ResponseModel<{
    items: Array<{
      location: string
      space: { total_u_positions: number; used_u_positions: number; usage_rate: number }
      power: { total_capacity_kw: number; used_capacity_kw: number; usage_rate: number }
      cooling: { total_cooling_kw: number; used_cooling_kw: number; usage_rate: number }
      weight: { total_weight_kg: number; used_weight_kg: number; usage_rate: number }
    }>
  }>>('/v1/capacity/statistics/by-location', { params })
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

/** 扩容建议 */
export interface ExpansionSuggestion {
  capacity_type: string
  current_usage_rate: number
  predicted_exceed_date: string
  predicted_usage_rate: number
  resource_gap: string
  suggestion: string
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
    is_demo: boolean
    expansion_suggestions: ExpansionSuggestion[]
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

// ==================== 智能上架推荐 ====================

/** 上架推荐请求 */
export interface RackingRecommendationRequest {
  required_u: number
  required_power_kw?: number
  required_cooling_kw?: number
  required_weight_kg?: number
  limit?: number
}

/** 机柜评分 */
export interface CabinetScore {
  cabinet_id: number
  cabinet_code: string
  cabinet_name: string
  location?: string
  space_score: number
  power_score: number
  cooling_score: number
  weight_score: number
  total_score: number
  available_u: number
  max_power?: number
  max_weight?: number
  notes: string
}

/** 上架推荐响应 */
export interface RackingRecommendationResponse {
  request: RackingRecommendationRequest
  candidates: CabinetScore[]
  total_cabinets_evaluated: number
  qualified_count: number
}

/** 获取上架推荐 */
export function getRackingRecommendation(data: RackingRecommendationRequest) {
  return request.post<ResponseModel<RackingRecommendationResponse>>('/v1/capacity/recommend', data)
}

/** 覆盖推荐机柜 */
export function overridePlanCabinet(planId: number, cabinetId: number) {
  return request.put<ResponseModel<CapacityPlan>>(`/v1/capacity/plans/${planId}/override-cabinet`, { target_cabinet_id: cabinetId })
}
