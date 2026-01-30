/**
 * 用电管理 API
 */
import request from '@/utils/request'
import type { ResponseModel, PageParams } from './types'

// ==================== 类型定义 ====================

/** 用电设备 */
export interface PowerDevice {
  id: number
  device_code: string
  device_name: string
  device_type: 'MAIN' | 'UPS' | 'PDU' | 'AC' | 'IT'
  rated_power?: number
  rated_voltage?: number
  rated_current?: number
  phase_type: '1P' | '3P'
  parent_device_id?: number
  circuit_no?: string
  is_metered: boolean
  is_it_load: boolean
  area_code?: string
  description?: string
  is_enabled: boolean
  created_at: string
  updated_at: string
}

export interface PowerDeviceCreate {
  device_code: string
  device_name: string
  device_type: string
  rated_power?: number
  rated_voltage?: number
  rated_current?: number
  phase_type?: string
  parent_device_id?: number
  circuit_no?: string
  is_metered?: boolean
  is_it_load?: boolean
  area_code?: string
  description?: string
}

export interface PowerDeviceUpdate {
  device_name?: string
  device_type?: string
  rated_power?: number
  rated_voltage?: number
  rated_current?: number
  phase_type?: string
  parent_device_id?: number
  circuit_no?: string
  is_metered?: boolean
  is_it_load?: boolean
  area_code?: string
  description?: string
  is_enabled?: boolean
}

export interface PowerDeviceTree extends PowerDevice {
  children: PowerDeviceTree[]
}

/** 实时电力数据 */
export interface RealtimePowerData {
  device_id: number
  device_code: string
  device_name: string
  device_type: string
  voltage_a?: number
  voltage_b?: number
  voltage_c?: number
  current_a?: number
  current_b?: number
  current_c?: number
  active_power?: number
  reactive_power?: number
  apparent_power?: number
  power_factor?: number
  frequency?: number
  total_energy?: number
  load_rate?: number
  status: 'normal' | 'warning' | 'alarm' | 'offline'
  update_time: string
}

export interface RealtimePowerSummary {
  total_power: number
  it_power: number
  cooling_power: number
  ups_power: number
  other_power: number
  current_pue: number
  today_energy: number
  today_cost: number
  month_energy: number
  month_cost: number
}

/** PUE数据 */
export interface PUEData {
  current_pue: number
  total_power: number
  it_power: number
  cooling_power: number
  ups_loss: number
  lighting_power: number
  other_power: number
  update_time: string
}

export interface PUEHistoryItem {
  record_time: string
  pue: number
  total_power: number
  it_power: number
}

export interface PUETrend {
  period: string
  data: PUEHistoryItem[]
  avg_pue: number
  min_pue: number
  max_pue: number
}

/** 能耗统计 */
export interface EnergyDailyData {
  id: number
  device_id: number
  stat_date: string
  total_energy: number
  peak_energy: number
  normal_energy: number
  valley_energy: number
  max_power: number
  avg_power: number
  max_power_time?: string
  energy_cost: number
  pue?: number
}

export interface EnergyMonthlyData {
  id: number
  device_id: number
  stat_year: number
  stat_month: number
  total_energy: number
  peak_energy: number
  normal_energy: number
  valley_energy: number
  max_power: number
  avg_power: number
  max_power_date?: string
  energy_cost: number
  peak_cost: number
  normal_cost: number
  valley_cost: number
  avg_pue?: number
}

export interface EnergyStat {
  total_energy: number
  peak_energy: number
  normal_energy: number
  valley_energy: number
  total_cost: number
  peak_cost: number
  normal_cost: number
  valley_cost: number
  avg_power: number
  max_power: number
  avg_pue?: number
}

export interface EnergyTrendItem {
  time_label: string
  energy: number
  cost: number
  power?: number
}

export interface EnergyTrend {
  granularity: string
  data: EnergyTrendItem[]
  total_energy: number
  total_cost: number
}

export interface EnergyComparison {
  current_period: EnergyStat
  previous_period: EnergyStat
  energy_change: number
  energy_change_rate: number
  cost_change: number
  cost_change_rate: number
}

/** 电价配置 */
export interface ElectricityPricing {
  id: number
  pricing_name: string
  period_type: 'sharp' | 'peak' | 'flat' | 'valley' | 'deep_valley'
  start_time: string
  end_time: string
  price: number
  effective_date: string
  expire_date?: string
  is_enabled: boolean
  created_at: string
  updated_at: string
}

export interface ElectricityPricingCreate {
  pricing_name: string
  period_type: string
  start_time: string
  end_time: string
  price: number
  effective_date: string
  expire_date?: string
}

export interface ElectricityPricingUpdate {
  pricing_name?: string
  period_type?: string
  start_time?: string
  end_time?: string
  price?: number
  effective_date?: string
  expire_date?: string
  is_enabled?: boolean
}

/** 节能建议 */
export interface EnergySuggestion {
  id: number
  rule_id: string
  rule_name?: string
  template_id?: string
  device_id?: number
  trigger_value?: number
  threshold_value?: number
  suggestion: string
  priority: 'high' | 'medium' | 'low'
  potential_saving?: number
  potential_cost_saving?: number
  status: 'pending' | 'accepted' | 'rejected' | 'completed'
  accepted_by?: number
  accepted_at?: string
  completed_at?: string
  actual_saving?: number
  remark?: string
  created_at: string
  updated_at: string
}

export interface SavingPotential {
  total_potential_saving: number
  total_cost_saving: number
  high_priority_count: number
  medium_priority_count: number
  low_priority_count: number
  pending_count: number
  accepted_count: number
  completed_count: number
  actual_saving_ytd: number
}

/** 配电节点 */
export interface DistributionNode {
  device_id: number
  device_code: string
  device_name: string
  device_type: string
  power?: number
  load_rate?: number
  status: string
  children: DistributionNode[]
}

export interface DistributionDiagram {
  root: DistributionNode
  total_power: number
  timestamp: string
}

// ==================== API 函数 ====================

/** 获取用电设备列表 */
export function getPowerDevices(params?: {
  device_type?: string
  area_code?: string
  is_enabled?: boolean
  keyword?: string
}) {
  return request.get<ResponseModel<PowerDevice[]>>('/v1/energy/devices', { params })
}

/** 获取用电设备树 */
export function getPowerDeviceTree() {
  return request.get<ResponseModel<PowerDeviceTree[]>>('/v1/energy/devices/tree')
}

/** 创建用电设备 */
export function createPowerDevice(data: PowerDeviceCreate) {
  return request.post<ResponseModel<PowerDevice>>('/v1/energy/devices', data)
}

/** 获取用电设备详情 */
export function getPowerDevice(deviceId: number) {
  return request.get<ResponseModel<PowerDevice>>(`/v1/energy/devices/${deviceId}`)
}

/** 更新用电设备 */
export function updatePowerDevice(deviceId: number, data: PowerDeviceUpdate) {
  return request.put<ResponseModel<PowerDevice>>(`/v1/energy/devices/${deviceId}`, data)
}

/** 删除用电设备 */
export function deletePowerDevice(deviceId: number) {
  return request.delete<ResponseModel>(`/v1/energy/devices/${deviceId}`)
}

/** 获取实时电力数据 */
export function getRealtimePower(params?: {
  device_type?: string
  area_code?: string
}) {
  return request.get<ResponseModel<RealtimePowerData[]>>('/v1/energy/realtime', { params })
}

/** 获取电力汇总 */
export function getPowerSummary() {
  return request.get<ResponseModel<RealtimePowerSummary>>('/v1/energy/realtime/summary')
}

/** 获取设备实时电力 */
export function getDeviceRealtimePower(deviceId: number) {
  return request.get<ResponseModel<RealtimePowerData>>(`/v1/energy/realtime/${deviceId}`)
}

/** 获取当前PUE */
export function getCurrentPUE() {
  return request.get<ResponseModel<PUEData>>('/v1/energy/pue')
}

/** 获取PUE趋势 */
export function getPUETrend(params?: {
  period?: 'hour' | 'day' | 'week' | 'month'
  start_time?: string
  end_time?: string
}) {
  return request.get<ResponseModel<PUETrend>>('/v1/energy/pue/trend', { params })
}

/** 获取日能耗统计 */
export function getDailyStatistics(params: {
  device_id?: number
  device_type?: string
  start_date: string
  end_date: string
}) {
  return request.get<ResponseModel<EnergyDailyData[]>>('/v1/energy/statistics/daily', { params })
}

/** 获取月能耗统计 */
export function getMonthlyStatistics(params: {
  device_id?: number
  device_type?: string
  year: number
}) {
  return request.get<ResponseModel<EnergyMonthlyData[]>>('/v1/energy/statistics/monthly', { params })
}

/** 获取能耗汇总 */
export function getEnergySummary(params: {
  device_id?: number
  device_type?: string
  area_code?: string
  start_date: string
  end_date: string
}) {
  return request.get<ResponseModel<EnergyStat>>('/v1/energy/statistics/summary', { params })
}

/** 获取能耗趋势 */
export function getEnergyTrend(params: {
  device_id?: number
  device_type?: string
  start_date: string
  end_date: string
  granularity?: 'hourly' | 'daily' | 'monthly'
}) {
  return request.get<ResponseModel<EnergyTrend>>('/v1/energy/statistics/trend', { params })
}

/** 获取能耗对比 */
export function getEnergyComparison(params: {
  device_id?: number
  comparison_type?: 'mom' | 'yoy'
  period?: 'day' | 'week' | 'month'
}) {
  return request.get<ResponseModel<EnergyComparison>>('/v1/energy/statistics/comparison', { params })
}

/** 获取日电费统计 */
export function getDailyCost(params: {
  start_date: string
  end_date: string
}) {
  return request.get<ResponseModel<any>>('/v1/energy/cost/daily', { params })
}

/** 获取月电费统计 */
export function getMonthlyCost(params: {
  year: number
  month?: number
}) {
  return request.get<ResponseModel<any>>('/v1/energy/cost/monthly', { params })
}

/** 获取电价配置 */
export function getPricingList(params?: { is_enabled?: boolean }) {
  return request.get<ResponseModel<ElectricityPricing[]>>('/v1/energy/pricing', { params })
}

/** 创建电价配置 */
export function createPricing(data: ElectricityPricingCreate) {
  return request.post<ResponseModel<ElectricityPricing>>('/v1/energy/pricing', data)
}

/** 更新电价配置 */
export function updatePricing(pricingId: number, data: ElectricityPricingUpdate) {
  return request.put<ResponseModel<ElectricityPricing>>(`/v1/energy/pricing/${pricingId}`, data)
}

/** 删除电价配置 */
export function deletePricing(pricingId: number) {
  return request.delete<ResponseModel>(`/v1/energy/pricing/${pricingId}`)
}

/** 获取节能建议 */
export function getSuggestions(params?: PageParams & {
  status?: string
  priority?: string
}) {
  return request.get<ResponseModel<EnergySuggestion[]>>('/v1/proposals/as-suggestions', { params })
}

/** 获取建议详情 */
export function getSuggestion(suggestionId: number) {
  return request.get<ResponseModel<EnergySuggestion>>(`/v1/energy/suggestions/${suggestionId}`)
}

/** 接受建议 */
export function acceptSuggestion(suggestionId: number, data?: { remark?: string }) {
  return request.put<ResponseModel<EnergySuggestion>>(`/v1/energy/suggestions/${suggestionId}/accept`, data)
}

/** 拒绝建议 */
export function rejectSuggestion(suggestionId: number, data: { remark: string }) {
  return request.put<ResponseModel<EnergySuggestion>>(`/v1/energy/suggestions/${suggestionId}/reject`, data)
}

/** 完成建议 */
export function completeSuggestion(suggestionId: number, data?: {
  actual_saving?: number
  remark?: string
}) {
  return request.put<ResponseModel<EnergySuggestion>>(`/v1/energy/suggestions/${suggestionId}/complete`, data)
}

/** 获取节能潜力 */
export function getSavingPotential() {
  return request.get<ResponseModel<SavingPotential>>('/v1/proposals/saving-potential')
}

/** 获取配电图数据 */
export function getDistributionDiagram() {
  return request.get<ResponseModel<DistributionDiagram>>('/v1/energy/distribution')
}

/** 导出日能耗数据 */
export function exportDailyData(params: {
  start_date: string
  end_date: string
  format?: 'excel' | 'csv'
}) {
  return request.get('/v1/energy/export/daily', {
    params,
    responseType: 'blob'
  })
}

/** 导出月能耗数据 */
export function exportMonthlyData(params: {
  year: number
  format?: 'excel' | 'csv'
}) {
  return request.get('/v1/energy/export/monthly', {
    params,
    responseType: 'blob'
  })
}

// ==================== 分析插件系统 ====================

/** 分析插件信息 */
export interface AnalysisPlugin {
  plugin_id: string
  name: string
  description: string
  suggestion_type: string
  enabled: boolean
  execution_order: number
}

/** 分析建议结果 */
export interface AnalysisSuggestion {
  suggestion_type: string
  priority: string
  title: string
  description: string
  detail: string
  estimated_saving: number
  estimated_cost_saving: number
  implementation_difficulty: number
  payback_period?: number
  related_devices: string[]
  confidence: number
  created_at: string
}

/** 分析运行结果 */
export interface AnalysisResult {
  total: number
  suggestions: AnalysisSuggestion[]
}

/** 分析汇总 */
export interface AnalysisSummary {
  status_summary: {
    pending: number
    accepted: number
    rejected: number
    completed: number
  }
  type_summary: Record<string, number>
  potential_saving: {
    energy_kwh: number
    cost_yuan: number
  }
  actual_saving: {
    energy_kwh: number
    cost_yuan: number
  }
  plugins: {
    total: number
    enabled: number
  }
}

/** 获取分析插件列表 */
export function getAnalysisPlugins() {
  return request.get<ResponseModel<AnalysisPlugin[]>>('/v1/energy/analysis/plugins')
}

/** 启用插件 */
export function enablePlugin(pluginId: string) {
  return request.post<ResponseModel<{ message: string }>>(`/v1/energy/analysis/plugins/${pluginId}/enable`)
}

/** 禁用插件 */
export function disablePlugin(pluginId: string) {
  return request.post<ResponseModel<{ message: string }>>(`/v1/energy/analysis/plugins/${pluginId}/disable`)
}

/** 执行节能分析 */
export function runAnalysis(params?: {
  plugin_ids?: string[]
  days?: number
  save_results?: boolean
}) {
  return request.post<ResponseModel<AnalysisResult>>('/v1/energy/analysis/run', null, { params })
}

/** 执行单个插件分析 */
export function runSingleAnalysis(pluginId: string, params?: {
  days?: number
  save_results?: boolean
}) {
  return request.post<ResponseModel<AnalysisResult & { plugin_id: string; plugin_name: string }>>(
    `/v1/energy/analysis/run/${pluginId}`,
    null,
    { params }
  )
}

/** 获取分析汇总 */
export function getAnalysisSummary() {
  return request.get<ResponseModel<AnalysisSummary>>('/v1/energy/analysis/summary')
}

// ==================== 配电系统配置 ====================

/** 变压器 */
export interface Transformer {
  id: number
  transformer_code: string
  transformer_name: string
  rated_capacity: number
  voltage_high: number
  voltage_low: number
  location?: string
  status: 'normal' | 'warning' | 'fault' | 'offline'
  is_enabled: boolean
  // 需量配置字段
  declared_demand?: number
  demand_type: 'kW' | 'kVA'
  demand_warning_ratio: number
  created_at: string
  updated_at: string
}

export interface TransformerCreate {
  transformer_code: string
  transformer_name: string
  rated_capacity: number
  voltage_high?: number
  voltage_low?: number
  location?: string
  declared_demand?: number
  demand_type?: 'kW' | 'kVA'
  demand_warning_ratio?: number
}

export interface TransformerUpdate {
  transformer_name?: string
  rated_capacity?: number
  voltage_high?: number
  voltage_low?: number
  location?: string
  status?: string
  is_enabled?: boolean
  declared_demand?: number
  demand_type?: 'kW' | 'kVA'
  demand_warning_ratio?: number
}

/** 计量点 */
export interface MeterPoint {
  id: number
  meter_code: string
  meter_name: string
  transformer_id?: number
  meter_no?: string
  declared_demand?: number
  demand_type?: 'single' | 'multi' | 'peak_valley'
  customer_no?: string
  status: 'normal' | 'warning' | 'fault' | 'offline'
  is_enabled: boolean
  created_at: string
  updated_at: string
}

export interface MeterPointCreate {
  meter_code: string
  meter_name: string
  transformer_id?: number
  meter_no?: string
  declared_demand?: number
  demand_type?: string
  customer_no?: string
}

export interface MeterPointUpdate {
  meter_name?: string
  transformer_id?: number
  meter_no?: string
  declared_demand?: number
  demand_type?: string
  customer_no?: string
  status?: string
  is_enabled?: boolean
}

/** 配电柜 */
export interface DistributionPanel {
  id: number
  panel_code: string
  panel_name: string
  panel_type: 'main' | 'sub' | 'final'
  meter_point_id?: number
  parent_panel_id?: number
  rated_current?: number
  rated_voltage?: number
  location?: string
  status: 'normal' | 'warning' | 'fault' | 'offline'
  is_enabled: boolean
  created_at: string
  updated_at: string
}

export interface DistributionPanelCreate {
  panel_code: string
  panel_name: string
  panel_type?: string
  meter_point_id?: number
  parent_panel_id?: number
  rated_current?: number
  rated_voltage?: number
  location?: string
}

export interface DistributionPanelUpdate {
  panel_name?: string
  panel_type?: string
  meter_point_id?: number
  parent_panel_id?: number
  rated_current?: number
  rated_voltage?: number
  location?: string
  status?: string
  is_enabled?: boolean
}

/** 配电回路 */
export interface DistributionCircuit {
  id: number
  circuit_code: string
  circuit_name: string
  panel_id: number
  load_type?: string
  rated_current?: number
  breaker_type?: string
  is_shiftable: boolean
  shift_priority?: number
  is_enabled: boolean
  created_at: string
  updated_at: string
}

export interface DistributionCircuitCreate {
  circuit_code: string
  circuit_name: string
  panel_id: number
  load_type?: string
  rated_current?: number
  breaker_type?: string
  is_shiftable?: boolean
  shift_priority?: number
}

export interface DistributionCircuitUpdate {
  circuit_name?: string
  panel_id?: number
  load_type?: string
  rated_current?: number
  breaker_type?: string
  is_shiftable?: boolean
  shift_priority?: number
  is_enabled?: boolean
}

/** 配电系统拓扑 */
export interface TopologyCircuitNode {
  circuit_id: number
  circuit_code: string
  circuit_name: string
  load_type?: string
  is_shiftable: boolean
  devices: PowerDevice[]
}

export interface TopologyPanelNode {
  panel_id: number
  panel_code: string
  panel_name: string
  panel_type: string
  circuits: TopologyCircuitNode[]
}

export interface TopologyMeterNode {
  meter_point_id: number
  meter_code: string
  meter_name: string
  declared_demand?: number
  demand_type?: string
  panels: TopologyPanelNode[]
}

export interface TopologyTransformerNode {
  transformer_id: number
  transformer_code: string
  transformer_name: string
  rated_capacity: number
  meter_points: TopologyMeterNode[]
}

export interface DistributionTopology {
  transformers: TopologyTransformerNode[]
  total_capacity: number
  total_meter_points: number
  total_devices: number
}

/** 功率曲线 */
export interface PowerCurvePoint {
  timestamp: string
  meter_point_id?: number
  device_id?: number
  active_power: number
  reactive_power: number
  power_factor: number
  demand_15min: number
  time_period: 'sharp' | 'peak' | 'flat' | 'valley'
}

export interface PowerCurveResponse {
  meter_point_id?: number
  device_id?: number
  data: PowerCurvePoint[]
  max_power: number
  avg_power: number
  max_demand: number
}

/** 需量历史 */
export interface DemandHistoryItem {
  month: string
  declared_demand: number
  max_demand: number
  avg_demand: number
  demand_95th: number
  over_declared_times: number
  demand_cost: number
  utilization_rate: number
}

export interface DemandHistoryResponse {
  meter_point_id: number
  meter_name: string
  declared_demand: number
  history: DemandHistoryItem[]
}

/** 设备负荷转移分析 */
export interface DeviceShiftPotential {
  device_id: number
  device_name: string
  device_type: string
  rated_power: number
  current_power: number
  is_shiftable: boolean
  shiftable_power: number
  // 5段式时段能耗占比
  sharp_energy_ratio?: number       // 尖峰占比
  peak_energy_ratio: number         // 峰时占比
  flat_energy_ratio?: number        // 平时占比
  valley_energy_ratio: number       // 谷时占比
  deep_valley_energy_ratio?: number // 深谷占比
  shift_potential_saving: number
  allowed_shift_hours: number[]
  forbidden_shift_hours: number[]
  is_critical: boolean
}

export interface DeviceShiftAnalysisResult {
  analysis_time: string
  total_devices: number
  shiftable_devices: number
  total_shiftable_power: number
  total_potential_saving: number
  devices: DeviceShiftPotential[]
  recommendations: string[]
}

/** 需量配置分析 */
export interface DemandConfigAnalysisItem {
  meter_point_id: number
  meter_name: string
  declared_demand: number
  max_demand_12m: number
  avg_demand_12m: number
  demand_95th: number
  utilization_rate: number
  optimal_demand: number
  is_over_declared: boolean
  is_under_declared: boolean
  potential_saving: number
  over_demand_risk: number
  recommendation: string
}

export interface DemandConfigAnalysisResult {
  analysis_time: string
  total_meter_points: number
  over_declared_count: number
  under_declared_count: number
  optimal_count: number
  total_potential_saving: number
  items: DemandConfigAnalysisItem[]
}

// ==================== 配电系统配置 API ====================

/** 获取变压器列表 */
export function getTransformers(params?: { status?: string; is_enabled?: boolean }) {
  return request.get<ResponseModel<Transformer[]>>('/v1/energy/transformers', { params })
}

/** 创建变压器 */
export function createTransformer(data: TransformerCreate) {
  return request.post<ResponseModel<Transformer>>('/v1/energy/transformers', data)
}

/** 获取变压器详情 */
export function getTransformer(transformerId: number) {
  return request.get<ResponseModel<Transformer>>(`/v1/energy/transformers/${transformerId}`)
}

/** 更新变压器 */
export function updateTransformer(transformerId: number, data: TransformerUpdate) {
  return request.put<ResponseModel<Transformer>>(`/v1/energy/transformers/${transformerId}`, data)
}

/** 删除变压器 */
export function deleteTransformer(transformerId: number) {
  return request.delete<ResponseModel>(`/v1/energy/transformers/${transformerId}`)
}

/** 获取计量点列表 */
export function getMeterPoints(params?: { transformer_id?: number; is_enabled?: boolean }) {
  return request.get<ResponseModel<MeterPoint[]>>('/v1/energy/meter-points', { params })
}

/** 创建计量点 */
export function createMeterPoint(data: MeterPointCreate) {
  return request.post<ResponseModel<MeterPoint>>('/v1/energy/meter-points', data)
}

/** 获取计量点详情 */
export function getMeterPoint(meterPointId: number) {
  return request.get<ResponseModel<MeterPoint>>(`/v1/energy/meter-points/${meterPointId}`)
}

/** 更新计量点 */
export function updateMeterPoint(meterPointId: number, data: MeterPointUpdate) {
  return request.put<ResponseModel<MeterPoint>>(`/v1/energy/meter-points/${meterPointId}`, data)
}

/** 删除计量点 */
export function deleteMeterPoint(meterPointId: number) {
  return request.delete<ResponseModel>(`/v1/energy/meter-points/${meterPointId}`)
}

/** 获取配电柜列表 */
export function getDistributionPanels(params?: { panel_type?: string; meter_point_id?: number; is_enabled?: boolean }) {
  return request.get<ResponseModel<DistributionPanel[]>>('/v1/energy/panels', { params })
}

/** 获取配电柜详情 */
export function getDistributionPanel(panelId: number) {
  return request.get<ResponseModel<DistributionPanel>>(`/v1/energy/panels/${panelId}`)
}

/** 创建配电柜 */
export function createDistributionPanel(data: DistributionPanelCreate) {
  return request.post<ResponseModel<DistributionPanel>>('/v1/energy/panels', data)
}

/** 更新配电柜 */
export function updateDistributionPanel(panelId: number, data: DistributionPanelUpdate) {
  return request.put<ResponseModel<DistributionPanel>>(`/v1/energy/panels/${panelId}`, data)
}

/** 删除配电柜 */
export function deleteDistributionPanel(panelId: number) {
  return request.delete<ResponseModel>(`/v1/energy/panels/${panelId}`)
}

/** 获取配电回路列表 */
export function getDistributionCircuits(params?: { panel_id?: number; load_type?: string; is_shiftable?: boolean }) {
  return request.get<ResponseModel<DistributionCircuit[]>>('/v1/energy/circuits', { params })
}

/** 获取配电回路详情 */
export function getDistributionCircuit(circuitId: number) {
  return request.get<ResponseModel<DistributionCircuit>>(`/v1/energy/circuits/${circuitId}`)
}

/** 创建配电回路 */
export function createDistributionCircuit(data: DistributionCircuitCreate) {
  return request.post<ResponseModel<DistributionCircuit>>('/v1/energy/circuits', data)
}

/** 更新配电回路 */
export function updateDistributionCircuit(circuitId: number, data: DistributionCircuitUpdate) {
  return request.put<ResponseModel<DistributionCircuit>>(`/v1/energy/circuits/${circuitId}`, data)
}

/** 删除配电回路 */
export function deleteDistributionCircuit(circuitId: number) {
  return request.delete<ResponseModel>(`/v1/energy/circuits/${circuitId}`)
}

/** 获取配电系统拓扑 */
export function getDistributionTopology() {
  return request.get<ResponseModel<DistributionTopology>>('/v1/energy/topology')
}

/** 获取功率曲线 */
export function getPowerCurve(params: {
  start_time: string
  end_time: string
  meter_point_id?: number
  device_id?: number
}) {
  return request.get<ResponseModel<PowerCurveResponse>>('/v1/energy/power-curve', { params })
}

/** 获取需量历史 */
export function getDemandHistory(meterPointId: number, params?: { months?: number }) {
  return request.get<ResponseModel<DemandHistoryResponse>>(`/v1/energy/demand-history/${meterPointId}`, { params })
}

/** 设备负荷转移分析 */
export function analyzeDeviceShift() {
  return request.get<ResponseModel<DeviceShiftAnalysisResult>>('/v1/energy/analysis/device-shift')
}

/** 需量配置分析 */
export function analyzeDemandConfig() {
  return request.get<ResponseModel<DemandConfigAnalysisResult>>('/v1/energy/analysis/demand-config')
}

// ==================== V2.3 负荷调节 ====================

/** 负荷调节配置 */
export interface LoadRegulationConfig {
  id: number
  device_id: number
  regulation_type: 'temperature' | 'brightness' | 'mode' | 'load'
  min_value: number
  max_value: number
  current_value?: number
  default_value?: number
  step_size: number
  unit?: string
  power_factor?: number
  base_power?: number
  priority: number
  comfort_impact?: string
  performance_impact?: string
  power_curve?: any[]
  is_enabled: boolean
  is_auto: boolean
  created_at: string
  updated_at: string
  device_name?: string
  device_type?: string
  rated_power?: number
}

export interface LoadRegulationConfigCreate {
  device_id: number
  regulation_type: string
  min_value: number
  max_value: number
  current_value?: number
  default_value?: number
  step_size: number
  unit?: string
  power_factor?: number
  base_power?: number
  priority?: number
  comfort_impact?: string
  performance_impact?: string
  power_curve?: any[]
  is_auto?: boolean
}

export interface LoadRegulationConfigUpdate {
  min_value?: number
  max_value?: number
  current_value?: number
  default_value?: number
  step_size?: number
  power_factor?: number
  base_power?: number
  priority?: number
  comfort_impact?: string
  performance_impact?: string
  power_curve?: any[]
  is_enabled?: boolean
  is_auto?: boolean
}

/** 调节模拟结果 */
export interface RegulationSimulateResponse {
  config_id: number
  device_id: number
  device_name: string
  regulation_type: string
  current_value: number
  target_value: number
  current_power: number
  estimated_power: number
  power_change: number
  comfort_impact?: string
  performance_impact?: string
}

/** 调节历史记录 */
export interface RegulationHistory {
  id: number
  config_id: number
  device_id: number
  device_name?: string
  regulation_type: string
  old_value?: number
  new_value: number
  power_before?: number
  power_after?: number
  power_saved?: number
  trigger_reason: string
  status: string
  executed_at?: string
  created_at: string
}

/** 调节建议 */
export interface RegulationRecommendation {
  config_id: number
  device_id: number
  device_name: string
  regulation_type: string
  current_value: number
  recommended_value: number
  power_saving: number
  reason: string
  priority: string
}

/** 获取负荷调节配置列表 */
export function getRegulationConfigs(params?: {
  device_id?: number
  regulation_type?: string
  is_enabled?: boolean
}) {
  return request.get<ResponseModel<LoadRegulationConfig[]>>('/v1/regulation/configs', { params })
}

/** 获取单个调节配置 */
export function getRegulationConfig(configId: number) {
  return request.get<ResponseModel<LoadRegulationConfig>>(`/v1/regulation/configs/${configId}`)
}

/** 创建调节配置 */
export function createRegulationConfig(data: LoadRegulationConfigCreate) {
  return request.post<ResponseModel<LoadRegulationConfig>>('/v1/regulation/configs', data)
}

/** 更新调节配置 */
export function updateRegulationConfig(configId: number, data: LoadRegulationConfigUpdate) {
  return request.put<ResponseModel<LoadRegulationConfig>>(`/v1/regulation/configs/${configId}`, data)
}

/** 删除调节配置 */
export function deleteRegulationConfig(configId: number) {
  return request.delete<ResponseModel>(`/v1/regulation/configs/${configId}`)
}

/** 模拟调节效果 */
export function simulateRegulation(data: { config_id: number; target_value: number }) {
  return request.post<ResponseModel<RegulationSimulateResponse>>('/v1/regulation/simulate', data)
}

/** 应用调节方案 */
export function applyRegulation(data: {
  config_id: number
  target_value: number
  reason?: string
  remark?: string
}) {
  return request.post<ResponseModel<RegulationHistory>>('/v1/regulation/apply', data)
}

/** 获取调节历史 */
export function getRegulationHistory(params?: {
  device_id?: number
  config_id?: number
  limit?: number
}) {
  return request.get<ResponseModel<RegulationHistory[]>>('/v1/regulation/history', { params })
}

/** 获取调节建议 */
export function getRegulationRecommendations(params?: {
  current_demand?: number
  declared_demand?: number
}) {
  return request.get<ResponseModel<RegulationRecommendation[]>>('/v1/regulation/recommendations', { params })
}

// ==================== V2.3 电费分析增强 ====================

/** 15分钟需量数据点 */
export interface Demand15MinDataPoint {
  timestamp: string
  average_power: number
  rolling_demand?: number
  is_over_declared: boolean
}

/** 15分钟需量曲线响应 */
export interface Demand15MinCurveResponse {
  meter_point_id: number
  date: string
  declared_demand?: number
  max_demand: number
  over_declared_count: number
  data_points: Demand15MinDataPoint[]
  total_points: number
}

/** 需量峰值分析响应 */
export interface DemandPeakAnalysisResponse {
  meter_point_id: number
  meter_name: string
  declared_demand: number
  analysis_period: {
    start: string
    end: string
    days: number
  }
  statistics: {
    max_demand: number
    avg_demand: number
    utilization_rate: number
    over_declared_count: number
    over_declared_ratio: number
  }
  hourly_distribution: Record<string, number>
  peak_hours: number[]
  over_declared_records: Array<{
    timestamp: string
    demand: number
    over_ratio: number
  }>
}

/** 需量优化方案响应 */
export interface DemandOptimizationPlanResponse {
  meter_point_id: number
  meter_name: string
  current_declared: number
  statistics: {
    max_demand: number
    avg_demand: number
    p95_demand: number
    utilization_rate: number
  }
  optimization: {
    recommended_demand: number
    annual_saving: number
    recommendations: Array<{
      type: string
      title: string
      description: string
      action: string
      saving: string
    }>
  }
}

/** 需量预测响应 */
export interface DemandForecastResponse {
  meter_point_id: number
  meter_name: string
  declared_demand: number
  forecast_period: {
    start: string
    hours: number
    points: number
  }
  summary: {
    max_predicted: number
    peak_risk_count: number
    peak_risk_ratio: number
  }
  forecast_points: Array<{
    timestamp: string
    predicted_demand: number
    confidence: number
    is_peak_risk: boolean
  }>
}

/** 获取15分钟需量曲线 */
export function getDemand15MinCurve(params: {
  meter_point_id: number
  date?: string
}) {
  return request.get<ResponseModel<Demand15MinCurveResponse>>('/v1/energy/demand/15min-curve', { params })
}

/** 获取需量峰值分析 */
export function getDemandPeakAnalysis(params: {
  meter_point_id: number
  days?: number
}) {
  return request.get<ResponseModel<DemandPeakAnalysisResponse>>('/v1/energy/demand/peak-analysis', { params })
}

/** 获取需量优化方案 */
export function getDemandOptimizationPlan(params: { meter_point_id: number }) {
  return request.get<ResponseModel<DemandOptimizationPlanResponse>>('/v1/energy/demand/optimization-plan', { params })
}

/** 需量预测 */
export function forecastDemand(params: {
  meter_point_id: number
  forecast_hours?: number
}) {
  return request.post<ResponseModel<DemandForecastResponse>>('/v1/energy/demand/forecast', null, { params })
}

// ==================== V2.3 节能建议引擎 ====================

/** 建议模板 */
export interface SuggestionTemplate {
  template_id: string
  name: string
  category: string
  priority: string
  difficulty: string
}

/** 增强版节能建议 */
export interface EnhancedSuggestion {
  id: number
  template_id?: string
  category?: string
  rule_name?: string
  suggestion: string
  problem_description?: string
  analysis_detail?: string
  implementation_steps?: Array<{
    step: number
    description: string
    duration?: string
  }>
  expected_effect?: {
    description: string
    saving_kwh: number
    saving_cost: number
  }
  priority: string
  difficulty?: string
  potential_saving?: number
  potential_cost_saving?: number
  parameters?: Record<string, any>
  status: string
  created_at?: string
  updated_at?: string
}

/** 建议分析结果 */
export interface SuggestionAnalyzeResult {
  analyzed_count: number
  new_suggestions: number
  updated_suggestions: number
  categories_analyzed: string[]
  analysis_time: string
}

/** 建议汇总统计 */
export interface SuggestionSummary {
  total_count: number
  pending_count: number
  accepted_count: number
  completed_count: number
  urgent_count: number
  high_count: number
  medium_count: number
  low_count: number
  potential_saving_kwh: number
  potential_saving_cost: number
}

/** 获取建议模板列表 */
export function getSuggestionTemplates() {
  return request.get<ResponseModel<{ total: number; templates: SuggestionTemplate[] }>>('/v1/proposals/templates')
}

/** 触发建议分析 - 生成新的节能方案 */
export function triggerSuggestionAnalysis(params?: {
  categories?: string[]
  force_refresh?: boolean
}) {
  // 生成所有模板的方案
  return request.post<ResponseModel<SuggestionAnalyzeResult>>('/v1/proposals/analyze', null, { params })
}

/** 获取增强版建议列表 */
export function getEnhancedSuggestions(params?: {
  category?: string
  priority?: string
  status?: string
  limit?: number
}) {
  return request.get<ResponseModel<{ total: number; suggestions: EnhancedSuggestion[] }>>('/v1/energy/suggestions/enhanced', { params })
}

/** 获取增强版建议详情 */
export function getEnhancedSuggestionDetail(suggestionId: number) {
  return request.get<ResponseModel<EnhancedSuggestion>>(`/v1/energy/suggestions/enhanced/${suggestionId}`)
}

/** 获取建议汇总统计 */
export function getSuggestionsSummary() {
  return request.get<ResponseModel<SuggestionSummary>>('/v1/energy/suggestions/summary')
}

// ==================== V2.3 能源仪表盘 ====================

/** 能源仪表盘数据 */
export interface EnergyDashboardData {
  realtime: {
    total_power: number
    it_power: number
    cooling_power: number
    other_power: number
    today_energy: number
    month_energy: number
  }
  efficiency: {
    pue: number
    pue_target: number
    pue_trend: 'up' | 'down' | 'stable'
    cooling_ratio: number
    it_ratio: number
  }
  demand: {
    current_demand: number
    declared_demand: number
    utilization_rate: number
    max_today: number
    over_declared_risk: boolean
  }
  cost: {
    today_cost: number
    month_cost: number
    peak_ratio: number
    valley_ratio: number
    avg_price: number
  }
  suggestions: {
    pending_count: number
    high_priority_count: number
    potential_saving_kwh: number
    potential_saving_cost: number
  }
  trends: {
    power_1h: number[]
    pue_24h: number[]
    demand_24h: number[]
  }
  update_time: string
}

/** 获取能源仪表盘数据 */
export function getEnergyDashboard() {
  return request.get<ResponseModel<EnergyDashboardData>>('/v1/realtime/energy-dashboard')
}

// ==================== V2.4 数据驱动 - 电价和设备能力查询 ====================

/** 电价时段信息 */
export interface PricingPeriod {
  id: number
  start_time: string
  end_time: string
  price: number
  name: string
}

/** 时段显示信息 */
export interface TimePeriod {
  type: string
  label: string
  display_name: string
  price: number
  time_ranges: PricingPeriod[]
}

/** 电价配置响应 */
export interface CurrentPricingResponse {
  pricing: Record<string, PricingPeriod[]>
  time_periods: TimePeriod[]
  data_source: {
    source: string
    status: string
    message: string
    config_count: number
    effective_date?: string
    period_types?: string[]
  }
}

/** 可转移设备 */
export interface ShiftableDevice {
  device_id: number
  device_code: string
  device_name: string
  device_type: string
  rated_power: number
  shiftable_power: number
  shiftable_ratio: number
  allowed_shift_hours: number[]
  forbidden_shift_hours: number[]
  min_continuous_runtime?: number
  max_shift_duration?: number
  shift_notice_time?: number
  requires_manual_approval?: boolean
  is_critical?: boolean
  regulation_method: string
  area_code?: string
}

/** 可转移设备响应 */
export interface ShiftableDevicesResponse {
  devices: ShiftableDevice[]
  total_count: number
  total_shiftable_power: number
  data_source: {
    shift_config_source: string
    regulation_config_source: string
    device_source: string
    shiftable_config_count: number
    regulation_config_count: number
    message: string
  }
}

/** 可调节设备 */
export interface AdjustableDevice {
  device_id: number
  device_code: string
  device_name: string
  device_type: string
  rated_power: number
  config_id: number
  regulation_type: 'temperature' | 'brightness' | 'mode' | 'load'
  current_value?: number
  default_value?: number
  min_value: number
  max_value: number
  step_size: number
  unit?: string
  power_factor?: number
  base_power?: number
  power_curve?: any[]
  power_range: {
    min_power: number
    max_power: number
    max_change: number
  }
  priority: number
  comfort_impact?: string
  performance_impact?: string
  is_auto?: boolean
  regulation_method: string
  area_code?: string
}

/** 可调节设备响应 */
export interface AdjustableDevicesResponse {
  devices: AdjustableDevice[]
  total_count: number
  by_regulation_type: Record<string, number>
  data_source: any
}

/** 重算请求参数 */
export interface RecalculateRequest {
  selected_devices: number[]
  shift_hours: number
  source_period: string
  target_period: string
}

/** 重算结果 */
export interface RecalculateResult {
  calculation_steps: string[]
  effects: {
    daily_energy_kwh: number
    daily_saving_yuan: number
    annual_saving_yuan: number
    annual_saving_wan: number
  }
  pricing_used: {
    source: { period: string; price: number }
    target: { period: string; price: number }
  }
  devices_used: ShiftableDevice[]
}

/** 建议完整详情 */
export interface SuggestionDetail {
  id: number
  rule_id: string
  rule_name?: string
  template_id?: string
  category?: string
  suggestion: string
  problem_description?: string
  analysis_detail?: string
  implementation_steps?: Array<{
    step: number
    description: string
    duration?: string
  }>
  expected_effect?: {
    description: string
    saving_kwh: number
    saving_cost: number
  }
  priority: string
  difficulty?: string
  potential_saving?: number
  potential_cost_saving?: number
  status: string
  created_at?: string
  parameters?: {
    pricing_source?: string
    device_source?: string
    sharp_price?: number
    peak_price?: number
    flat_price?: number
    normal_price?: number
    valley_price?: number
    price_diff?: number
    total_shiftable_power?: number
    adjustable_params?: AdjustableParam[]
    devices?: DeviceInSuggestion[]
    time_config?: TimeConfig
    calculation_formula?: CalculationFormula
    default_shift_hours?: number
    daily_saving?: number
    annual_saving?: number
    data_sources?: any
    user_adjusted_params?: any
  }
  // 实时数据
  current_pricing?: Record<string, PricingPeriod[]>
  time_periods?: TimePeriod[]
  shiftable_devices?: ShiftableDevice[]
  data_sources?: {
    pricing: any
    devices: any
  }
}

/** 可调参数定义 */
export interface AdjustableParam {
  key: string
  name: string
  type: 'number' | 'device_select' | 'period_select'
  current_value: any
  min?: number
  max?: number
  step?: number
  unit?: string
  options?: any[]
}

/** 建议中的设备信息 */
export interface DeviceInSuggestion {
  device_id: number
  device_code: string
  device_name: string
  device_type: string
  rated_power: number
  shiftable_power: number
  regulation_method: string
  constraints: {
    allowed_hours: number[]
    forbidden_hours: number[]
    min_runtime?: number
  }
}

/** 时间配置 */
export interface TimeConfig {
  source_periods: PricingPeriod[]
  target_periods: PricingPeriod[]
  all_periods: TimePeriod[]
}

/** 计算公式 */
export interface CalculationFormula {
  formula: string
  variables_from_db: Record<string, string>
  steps: Array<{
    step: number
    desc: string
  }>
}

/** 获取当前电价配置 */
export function getCurrentPricing() {
  return request.get<ResponseModel<CurrentPricingResponse>>('/v1/energy/pricing/current')
}

/** 获取可转移负荷设备列表 */
export function getShiftableDevices() {
  return request.get<ResponseModel<ShiftableDevicesResponse>>('/v1/energy/devices/shiftable')
}

/** 获取可调节参数设备列表 */
export function getAdjustableDevices() {
  return request.get<ResponseModel<AdjustableDevicesResponse>>('/v1/energy/devices/adjustable')
}

/** 重算建议效果 */
export function recalculateSuggestion(
  suggestionId: number,
  params: RecalculateRequest
) {
  return request.post<ResponseModel<RecalculateResult>>(
    `/v1/energy/suggestions/${suggestionId}/recalculate`,
    params
  )
}

/** 获取建议完整详情 */
export function getSuggestionFullDetail(suggestionId: number) {
  return request.get<ResponseModel<SuggestionDetail>>(
    `/v1/proposals/${suggestionId}/enhanced`
  )
}

// ==================== V2.5 负荷转移执行计划 ====================

/** 转移规则类型 */
export interface ShiftRule {
  source_period: string
  target_period: string
  power: number
  hours: number
}

/** 设备转移规则类型 */
export interface DeviceShiftRule {
  device_id: number
  device_name: string
  rules: ShiftRule[]
}

/** 创建负荷转移执行计划请求 */
export interface CreateLoadShiftPlanRequest {
  plan_name: string
  strategy: 'max_benefit' | 'min_cost'
  daily_saving: number
  annual_saving: number
  device_rules: DeviceShiftRule[]
  remark?: string
  meter_point_id?: number
}

/** 创建负荷转移执行计划响应 */
export interface CreateLoadShiftPlanResponse {
  plan_id: number
  opportunity_id: number
  plan_name: string
  expected_saving: number
  task_count: number
}

/** 从负荷转移配置创建执行计划 */
export function createLoadShiftPlan(data: CreateLoadShiftPlanRequest) {
  return request.post<ResponseModel<CreateLoadShiftPlanResponse>>('/v1/execution/plans/from-shift', data)
}

// ==================== V2.7 拓扑编辑 ====================

/** 拓扑节点类型 */
export type TopologyNodeTypeEnum = 'transformer' | 'meter_point' | 'panel' | 'circuit' | 'device' | 'point'

/** 拓扑节点位置 */
export interface TopologyNodePosition {
  x: number
  y: number
}

/** 创建拓扑节点请求 */
export interface TopologyNodeCreateRequest {
  node_type: TopologyNodeTypeEnum
  parent_id?: number
  parent_type?: TopologyNodeTypeEnum
  position?: TopologyNodePosition
  // 变压器
  transformer_code?: string
  transformer_name?: string
  rated_capacity?: number
  voltage_high?: number
  voltage_low?: number
  // 计量点
  meter_code?: string
  meter_name?: string
  meter_type?: string
  ct_ratio?: number
  pt_ratio?: number
  measurement_types?: string[]
  // 配电柜
  panel_code?: string
  panel_name?: string
  panel_type?: string
  // 回路
  circuit_code?: string
  circuit_name?: string
  circuit_type?: string
  rated_current?: number
  // 设备
  device_code?: string
  device_name?: string
  device_type?: string
  rated_power?: number
  // 采集点位
  point_code?: string
  point_name?: string
  point_type?: string
  measurement_type?: string
  register_address?: string
  data_type?: string
  scale_factor?: number
}

/** 更新拓扑节点请求 */
export interface TopologyNodeUpdateRequest {
  node_id: number
  node_type: TopologyNodeTypeEnum
  position?: TopologyNodePosition
  name?: string
  code?: string
  status?: string
  is_enabled?: boolean
  location?: string
  remark?: string
  rated_capacity?: number
  rated_power?: number
  rated_current?: number
  voltage_high?: number
  voltage_low?: number
  ct_ratio?: number
  pt_ratio?: number
  declared_demand?: number
  meter_type?: string
  measurement_types?: string[]
  // 采集点位
  point_type?: string
  measurement_type?: string
  register_address?: string
  data_type?: string
  scale_factor?: number
}

/** 删除拓扑节点请求 */
export interface TopologyNodeDeleteRequest {
  node_id: number
  node_type: TopologyNodeTypeEnum
  cascade: boolean
}

/** 批量操作请求 */
export interface TopologyBatchOperationRequest {
  creates: TopologyNodeCreateRequest[]
  updates: TopologyNodeUpdateRequest[]
  deletes: TopologyNodeDeleteRequest[]
  connections_add: Array<{
    source_id: number
    source_type: TopologyNodeTypeEnum
    target_id: number
    target_type: TopologyNodeTypeEnum
  }>
  connections_remove: Array<{
    source_id: number
    source_type: TopologyNodeTypeEnum
    target_id: number
    target_type: TopologyNodeTypeEnum
  }>
}

/** 批量操作结果 */
export interface TopologyBatchResult {
  success: boolean
  created_count: number
  updated_count: number
  deleted_count: number
  connections_added: number
  connections_removed: number
  errors: string[]
  created_ids: Record<string, number>
}

/** 设备测点配置 */
export interface DevicePointConfig {
  point_code: string
  point_name: string
  point_type: string
  device_type?: string
  area_code?: string
  data_type?: string
  unit?: string
  min_range?: number | null
  max_range?: number | null
  collect_interval?: number
  description?: string
  device_id?: number
  register_address?: string
  function_code?: number
  scale_factor?: number
  offset?: number
  alarm_enabled?: boolean
  alarm_high?: number
  alarm_low?: number
}

/** 设备测点响应 */
export interface DevicePointConfigResponse {
  id: number
  energy_device_id: number
  point_code: string
  point_name: string
  point_type: string
  device_type?: string
  area_code?: string
  data_type: string
  unit?: string
  min_range?: number | null
  max_range?: number | null
  collect_interval?: number
  description?: string
  device_id?: number
  register_address?: string
  function_code?: number
  scale_factor: number
  offset: number
  alarm_enabled: boolean
  alarm_high?: number
  alarm_low?: number
  current_value?: number
  last_update_time?: string
}

// --- 拓扑编辑 API ---

/** 创建拓扑节点 */
export function createTopologyNode(data: TopologyNodeCreateRequest) {
  return request.post<ResponseModel<{ success: boolean; node_id: number; node_type: string }>>('/v1/topology/nodes', data)
}

/** 更新拓扑节点 */
export function updateTopologyNode(data: TopologyNodeUpdateRequest) {
  return request.put<ResponseModel<{ success: boolean }>>('/v1/topology/nodes', data)
}

/** 删除拓扑节点 */
export function deleteTopologyNode(data: TopologyNodeDeleteRequest) {
  return request.delete<ResponseModel<{ success: boolean; deleted: Record<string, number> }>>('/v1/topology/nodes', { data })
}

/** 批量拓扑操作 */
export function batchTopologyOperation(data: TopologyBatchOperationRequest) {
  return request.post<ResponseModel<TopologyBatchResult>>('/v1/topology/batch', data)
}

/** 导出拓扑数据 */
export function exportTopology() {
  return request.get<ResponseModel<any>>('/v1/topology/export')
}

/** 导入拓扑数据 */
export function importTopology(data: any) {
  return request.post<ResponseModel<TopologyBatchResult>>('/v1/topology/import', data)
}

/** 创建拓扑连接 */
export function createTopologyConnection(data: {
  source_id: number
  source_type: TopologyNodeTypeEnum
  target_id: number
  target_type: TopologyNodeTypeEnum
}) {
  return request.post<ResponseModel<{ success: boolean }>>('/v1/topology/connections', data)
}

/** 删除拓扑连接 */
export function deleteTopologyConnection(data: {
  target_id: number
  target_type: TopologyNodeTypeEnum
}) {
  return request.delete<ResponseModel<{ success: boolean }>>('/v1/topology/connections', { data })
}

/** 创建设备测点 */
export function createDevicePoints(data: { energy_device_id: number; points: DevicePointConfig[] }) {
  return request.post<ResponseModel<{ success: boolean; point_ids: number[] }>>('/v1/topology/device-points', data)
}

/** 获取设备测点 */
export function getDevicePoints(deviceId: number) {
  return request.get<ResponseModel<{ device_id: number; points: DevicePointConfigResponse[] }>>(`/v1/topology/device-points/${deviceId}`)
}

/** 更新设备测点 */
export function updateDevicePoint(pointId: number, data: Partial<DevicePointConfig>) {
  return request.put<ResponseModel<{ success: boolean }>>(`/v1/topology/device-points/${pointId}`, data)
}

/** 删除设备所有测点 */
export function deleteDevicePoints(deviceId: number) {
  return request.delete<ResponseModel<{ success: boolean; deleted_count: number }>>(`/v1/topology/device-points/${deviceId}`)
}

/** 删除单个点位 */
export function deleteDevicePointById(pointId: number) {
  return request.delete<ResponseModel<{ success: boolean; point_id: number }>>(`/v1/topology/device-points/point/${pointId}`)
}

// ==================== V2.8 设备点位同步 ====================

/** 设备关联点位信息 */
export interface DeviceLinkedPoint {
  id: number
  point_code: string
  point_name: string
  point_type: string
  device_type?: string
  area_code?: string
  unit?: string
  data_type?: string
  min_range?: number | null
  max_range?: number | null
  collect_interval?: number
  description?: string
  role: 'power' | 'current' | 'energy' | 'voltage' | 'power_factor' | 'associated'
  realtime?: {
    value: number | null
    value_text?: string
    status: string
    quality: number
    updated_at?: string
  }
}

/** 设备关联点位响应 */
export interface DeviceLinkedPointsResponse {
  device_id: number
  device_code: string
  device_name: string
  device_type: string
  rated_power?: number
  points: DeviceLinkedPoint[]
  point_count: number
}

/** 同步状态统计 */
export interface SyncStatistics {
  total_devices: number
  linked_devices: number
  orphan_devices: number
  total_points: number
  linked_points: number
  device_link_rate: number
  point_link_rate: number
}

/** 获取设备关联的所有点位 */
export function getDeviceLinkedPoints(deviceId: number) {
  return request.get<ResponseModel<DeviceLinkedPointsResponse>>(`/v1/topology/device/${deviceId}/points`)
}

/** 触发设备点位同步 */
export function syncDevicePointRelations() {
  return request.post<ResponseModel<{
    success: boolean
    updated_devices: number
    updated_points: number
    matched_count: number
    statistics: SyncStatistics
  }>>('/v1/topology/sync')
}

/** 获取同步状态统计 */
export function getSyncStatus() {
  return request.get<ResponseModel<SyncStatistics & { success: boolean }>>('/v1/topology/sync/status')
}
