/**
 * 配电与制冷拓扑配置 API
 */
import request from '@/utils/request'
import type { ResponseModel } from './types'

// ==================== 配电拓扑类型 ====================

/** 配电相位映射创建参数 */
export interface PowerPhaseMappingCreate {
  cabinet_id: number
  pdu_device_id: number
  phase: 'A' | 'B' | 'C'
  feed_type: 'primary' | 'backup'
  rated_current?: number
  description?: string
}

/** 配电相位映射响应 */
export interface PowerPhaseMappingResponse {
  id: number
  cabinet_id: number
  pdu_device_id: number
  phase: string
  feed_type: string
  rated_current: number | null
  description: string | null
  cabinet_code: string
  cabinet_name: string
  pdu_device_name: string
  pdu_device_code: string
}

/** 三相不平衡度响应 */
export interface PhaseBalanceResponse {
  pdu_device_id: number
  pdu_device_name: string
  phase_a_power: number
  phase_b_power: number
  phase_c_power: number
  imbalance_rate: number | null
  data_source: string
  phase_a_cabinets: string[]
  phase_b_cabinets: string[]
  phase_c_cabinets: string[]
}

// ==================== 制冷拓扑类型 ====================

/** 制冷区域创建参数 */
export interface CoolingZoneCreate {
  zone_name: string
  room_id?: number
  design_capacity_kw?: number
  description?: string
  cabinet_ids?: number[]
  cooling_unit_ids?: number[]
}

/** 制冷区域机柜信息 */
export interface CoolingZoneCabinetInfo {
  id: number
  cabinet_code: string
  cabinet_name: string
}

/** 制冷区域空调信息 */
export interface CoolingZoneUnitInfo {
  id: number
  device_code: string
  device_name: string
  cooling_capacity_kw: number | null
}

/** 制冷区域响应 */
export interface CoolingZoneResponse {
  id: number
  zone_code: string
  zone_name: string
  room_id: number | null
  design_capacity_kw: number | null
  description: string | null
  cabinets: CoolingZoneCabinetInfo[]
  cooling_units: CoolingZoneUnitInfo[]
}

/** 制冷区域容量响应 */
export interface CoolingZoneCapacityResponse {
  zone_id: number
  zone_name: string
  design_capacity_kw: number | null
  total_cabinet_power: number
  utilization_rate: number | null
}

/** 机柜拓扑汇总 */
export interface CabinetTopologySummary {
  cabinet_id: number
  cabinet_code: string
  cabinet_name: string
  spatial: { site_name: string; floor_name: string; room_name: string; row_name: string } | null
  power: Array<{ pdu_device_name: string; phase: string; feed_type: string }>
  cooling: Array<{ zone_name: string; design_capacity_kw: number | null }>
}

// ==================== 配电拓扑 API ====================

/** 获取配电相位映射列表（可选按 PDU 过滤） */
export function getPowerPhaseMappings(pdu_device_id?: number) {
  return request.get<ResponseModel<PowerPhaseMappingResponse[]>>('/v1/topology-config/power-phase', {
    params: { pdu_device_id }
  })
}

/** 按机柜获取相位映射 */
export function getPowerPhaseByCabinet(cabinetId: number) {
  return request.get<ResponseModel<PowerPhaseMappingResponse[]>>(`/v1/topology-config/power-phase/cabinet/${cabinetId}`)
}

/** 创建配电相位映射 */
export function createPowerPhaseMapping(data: PowerPhaseMappingCreate) {
  return request.post<ResponseModel<PowerPhaseMappingResponse>>('/v1/topology-config/power-phase', data)
}

/** 更新配电相位映射 */
export function updatePowerPhaseMapping(id: number, data: Partial<PowerPhaseMappingCreate>) {
  return request.put<ResponseModel<PowerPhaseMappingResponse>>(`/v1/topology-config/power-phase/${id}`, data)
}

/** 删除配电相位映射 */
export function deletePowerPhaseMapping(id: number) {
  return request.delete<ResponseModel>(`/v1/topology-config/power-phase/${id}`)
}

/** 获取 PDU 三相不平衡度 */
export function getPduPhaseBalance(pduDeviceId: number) {
  return request.get<ResponseModel<PhaseBalanceResponse>>(`/v1/topology-config/power-phase/pdu/${pduDeviceId}/balance`)
}

// ==================== 制冷拓扑 API ====================

/** 获取制冷区域列表 */
export function getCoolingZones() {
  return request.get<ResponseModel<CoolingZoneResponse[]>>('/v1/topology-config/cooling-zones')
}

/** 获取制冷区域详情 */
export function getCoolingZone(id: number) {
  return request.get<ResponseModel<CoolingZoneResponse>>(`/v1/topology-config/cooling-zones/${id}`)
}

/** 创建制冷区域 */
export function createCoolingZone(data: CoolingZoneCreate) {
  return request.post<ResponseModel<CoolingZoneResponse>>('/v1/topology-config/cooling-zones', data)
}

/** 更新制冷区域 */
export function updateCoolingZone(id: number, data: CoolingZoneCreate) {
  return request.put<ResponseModel<CoolingZoneResponse>>(`/v1/topology-config/cooling-zones/${id}`, data)
}

/** 删除制冷区域 */
export function deleteCoolingZone(id: number) {
  return request.delete<ResponseModel>(`/v1/topology-config/cooling-zones/${id}`)
}

/** 获取制冷区域容量 */
export function getCoolingZoneCapacity(id: number) {
  return request.get<ResponseModel<CoolingZoneCapacityResponse>>(`/v1/topology-config/cooling-zones/${id}/capacity`)
}

// ==================== 汇总 API ====================

/** 获取机柜拓扑汇总 */
export function getCabinetTopologySummary(cabinetId: number) {
  return request.get<ResponseModel<CabinetTopologySummary>>(`/v1/topology-config/cabinet/${cabinetId}/topology-summary`)
}

// ==================== 智能选址 ====================

export interface SmartSiteWeights {
  space: number
  power: number
  phase_balance: number
  temperature: number
  cooling: number
}

export interface SmartSiteRequest {
  required_u: number
  required_power_kw?: number
  required_weight_kg?: number
  limit?: number
  weights?: SmartSiteWeights
}

export interface DimensionScore {
  dimension: string
  score: number
  weight: number
  weighted_score: number
  data_available: boolean
  detail: string
}

export interface CabinetSiteScore {
  cabinet_id: number
  cabinet_code: string
  cabinet_name: string
  location: string | null
  room_name: string | null
  row_name: string | null
  available_u: number
  total_score: number
  confidence: 'high' | 'medium' | 'low'
  dimensions: DimensionScore[]
  grid_x: number | null
  grid_y: number | null
  aisle_type: string | null
}

export interface SmartSiteResponse {
  candidates: CabinetSiteScore[]
  total_evaluated: number
  qualified_count: number
}

export function getSmartSiteSelection(data: SmartSiteRequest) {
  return request.post<ResponseModel<SmartSiteResponse>>('/v1/topology-config/smart-site-selection', data)
}

// ==================== 故障影响分析 ====================

export interface FaultImpactRequest {
  fault_source_type: 'pdu' | 'panel'
  fault_source_id: number
}

export interface AffectedCabinet {
  cabinet_id: number
  cabinet_code: string
  cabinet_name: string
  location?: string
  feed_type?: string
  phase?: string
  asset_count: number
  impact_level: string
  has_redundancy: boolean
}

export interface AffectedAsset {
  asset_id: number
  asset_code: string
  asset_name: string
  asset_type?: string
  cabinet_code?: string
}

export interface CoolingImpactItem {
  zone_id: number
  zone_name: string
  affected_cabinet_count: number
  total_cabinet_count: number
  cooling_units: string[]
  same_power_circuit: boolean
  power_circuit_data_source: string
}

export interface RelatedAlarmItem {
  alarm_id: number
  alarm_no: string
  alarm_level: string
  alarm_message: string
  status: string
  created_at?: string
}

export interface FaultImpactResponse {
  fault_source_type: string
  fault_source_id: number
  fault_source_name?: string
  affected_cabinets: AffectedCabinet[]
  affected_assets: AffectedAsset[]
  cooling_impacts: CoolingImpactItem[]
  related_alarms: RelatedAlarmItem[]
  suggestions: string[]
  analysis_time?: string
}

/** 故障影响分析 */
export function getFaultImpactAnalysis(data: FaultImpactRequest) {
  return request.post<ResponseModel<FaultImpactResponse>>('/v1/topology-config/fault-impact-analysis', data)
}
