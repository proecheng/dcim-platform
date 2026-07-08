import request from '@/utils/request'

export type ShiftPeriod = 'peak' | 'sharp' | 'flat' | 'valley'
export type ShiftPlanStatus =
  | 'draft'
  | 'pending_approval'
  | 'approved'
  | 'rejected'
  | 'executing'
  | 'completed'
  | 'failed'
  | 'cancelled'

export interface ShiftPlan {
  id: number
  plan_code: string
  plan_name: string
  shift_from_period: ShiftPeriod
  shift_to_period: ShiftPeriod
  shift_date: string
  start_time: string
  end_time: string
  target_shift_power: number
  selected_devices: any[]
  constraints?: Record<string, unknown> | null
  expected_cost_saving?: number | null
  expected_energy_saving?: number | null
  description?: string | null
  status: ShiftPlanStatus
  approval_status: string
  execution_status: string
  actual_shift_power?: number | null
  actual_cost_saving?: number | null
  actual_energy_saving?: number | null
  created_by: number
  created_at: string
  updated_at: string
  approved_by?: number | null
  approved_at?: string | null
  approval_comment?: string | null
  executed_at?: string | null
  completed_at?: string | null
}

export interface ShiftPlanQuery {
  skip?: number
  limit?: number
  status?: ShiftPlanStatus | string
  shift_date_from?: string
  shift_date_to?: string
}

export interface ShiftOpportunity {
  id: number
  opportunity_code: string
  opportunity_name: string
  recommended_date?: string | null
  analysis_date?: string | null
  analysis_period?: string | null
  shift_from_period?: string | null
  shift_to_period?: string | null
  recommended_shift_from?: string | null
  recommended_shift_to?: string | null
  recommended_shift_power?: number | null
  recommended_devices: Array<Record<string, any> | number>
  estimated_cost_saving?: number | null
  estimated_energy_saving?: number | null
  predicted_cost_saving?: number | null
  predicted_energy_saving?: number | null
  confidence_score?: number | null
  analysis_data: Record<string, any>
  reason?: string | null
  status: string
  priority: string
  converted_plan_id?: number | null
  converted_to_plan_id?: number | null
  converted_at?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface ShiftOpportunityQuery {
  skip?: number
  limit?: number
  status?: string
  priority?: string
}

export interface AnalyzeOpportunitiesParams {
  analysis_date?: string
  lookback_days?: number
}

export interface ShiftOpportunityAnalyzeResponse {
  analysis_date: string
  opportunities_found: number
  opportunities: ShiftOpportunity[]
}

export interface ShiftExecution {
  id: number
  execution_code: string
  plan_id: number
  plan_name?: string | null
  status: string
  execution_status: string
  start_time?: string | null
  end_time?: string | null
  duration_minutes?: number | null
  duration: number
  target_shift_power?: number | null
  expected_cost_saving?: number | null
  expected_energy_saving?: number | null
  before_power?: number | null
  after_power?: number | null
  before_total_power?: number | null
  after_total_power?: number | null
  actual_shift_power?: number | null
  actual_cost_saving?: number | null
  actual_energy_saving?: number | null
  success_rate?: number | null
  device_execution_details: any[]
  device_execution_list: any[]
  device_executions: any[]
  cooling_linkage_data?: Record<string, any> | null
  cooling_linkage?: Record<string, any> | null
  error_message?: string | null
  failure_reason?: string | null
  error_details?: Record<string, any> | null
  executed_by?: number | null
  executor_name?: string | null
  notes?: string | null
  created_at?: string | null
}

export interface ShiftExecutionQuery {
  skip?: number
  limit?: number
  status?: string
  start_date?: string
  end_date?: string
}

export interface ShiftExecutionListResponse {
  data: ShiftExecution[]
  total: number
  skip: number
  limit: number
}

export interface ShiftExecutionDetailResponse {
  data: ShiftExecution
}

export interface ShiftExecutionRealtimePayload {
  execution_id: number
  execution_code: string
  status: string
  target_power: number
  actual_power: number
  completion_rate: number
  device_status: any[]
  alarms: any[]
  timestamp: string
}

export interface ShiftExecutionRealtimeResponse {
  data: ShiftExecutionRealtimePayload
}

// ========== 计划管理 ==========
export function getShiftPlans(params?: ShiftPlanQuery): Promise<ShiftPlan[]> {
  return request.get('/v1/energy/shift/plans', { params })
}

export function getShiftPlan(id: number): Promise<ShiftPlan> {
  return request.get(`/v1/energy/shift/plans/${id}`)
}

export function createShiftPlan(data: any) {
  return request.post('/v1/energy/shift/plans', data)
}

export function updateShiftPlan(id: number, data: any) {
  return request.put(`/v1/energy/shift/plans/${id}`, data)
}

export function deleteShiftPlan(id: number) {
  return request.delete(`/v1/energy/shift/plans/${id}`)
}

export function submitShiftPlan(id: number) {
  return request.post(`/v1/energy/shift/plans/${id}/submit`)
}

export function approveShiftPlan(id: number, data: any) {
  return request.post(`/v1/energy/shift/plans/${id}/approve`, data)
}

export function executeShiftPlan(id: number) {
  return request.post(`/v1/energy/shift/plans/${id}/execute`)
}

// ========== 分析接口 ==========
export function analyzeFeasibility(data: any) {
  return request.post('/v1/energy/shift/analysis/feasibility', data)
}

export function checkConstraints(data: any) {
  return request.post('/v1/energy/shift/analysis/constraints', data)
}

// ========== 约束管理接口 ==========
export function getShiftConstraints() {
  return request.get('/v1/energy/shift/constraints')
}

export function createShiftConstraint(data: any) {
  return request.post('/v1/energy/shift/constraints', data)
}

export function updateShiftConstraint(id: number, data: any) {
  return request.put(`/v1/energy/shift/constraints/${id}`, data)
}

export function deleteShiftConstraint(id: number) {
  return request.delete(`/v1/energy/shift/constraints/${id}`)
}

export function analyzeBenefit(data: any) {
  return request.post('/v1/energy/shift/analysis/benefit', data)
}

export function assessRisk(data: any) {
  return request.post('/v1/energy/shift/analysis/risk', data)
}
// ========== 机会分析接口 ==========
export function analyzeOpportunities(params?: AnalyzeOpportunitiesParams): Promise<ShiftOpportunityAnalyzeResponse> {
  return request.post('/v1/energy/shift/opportunities/analyze', null, { params })
}

export function getOpportunities(params?: ShiftOpportunityQuery): Promise<ShiftOpportunity[]> {
  return request.get('/v1/energy/shift/opportunities', { params })
}

export function getOpportunityDetail(id: number): Promise<ShiftOpportunity> {
  return request.get(`/v1/energy/shift/opportunities/${id}`)
}

export function convertOpportunityToPlan(id: number): Promise<ShiftPlan> {
  return request.post(`/v1/energy/shift/opportunities/${id}/convert`)
}

// ========== 设备接口 ==========
export function getShiftableDevices() {
  return request.get('/v1/energy/shift/devices/shiftable')
}

export function getDevicePotential(deviceId: number) {
  return request.get(`/v1/energy/shift/devices/${deviceId}/potential`)
}

// ========== 仪表盘接口 ==========
export function getDashboardOverview() {
  return request.get('/v1/energy/shift/dashboard/overview')
}

export function getRealtimeData() {
  return request.get('/v1/energy/shift/dashboard/realtime')
}

export function getTrends(days: number = 7) {
  return request.get('/v1/energy/shift/dashboard/trends', { params: { days } })
}

// ========== 统计接口 ==========
export function getStatisticsSummary(params?: any) {
  return request.get('/v1/energy/shift/statistics/summary', { params })
}

// ========== 执行记录接口 ==========
export function getExecutions(params?: ShiftExecutionQuery): Promise<ShiftExecutionListResponse> {
  return request.get('/v1/energy/shift/executions', { params })
}

export function getExecutionDetail(id: number): Promise<ShiftExecutionDetailResponse> {
  return request.get(`/v1/energy/shift/executions/${id}`)
}

export function getExecutionRealtime(id: number): Promise<ShiftExecutionRealtimeResponse> {
  return request.get(`/v1/energy/shift/executions/${id}/realtime`)
}

// ========== 制冷联动接口 ==========
export function getCoolingConfig() {
  return request.get('/v1/energy/shift/cooling/config')
}

export function updateCoolingConfig(data: any) {
  return request.put('/v1/energy/shift/cooling/config', data)
}

export function getCoolingStatus() {
  return request.get('/v1/energy/shift/cooling/status')
}

export function getCoolingHistory(params?: any) {
  return request.get('/v1/energy/shift/cooling/history', { params })
}
// ========== 报表接口 ==========
export function getShiftReport(params: any) {
  return request.get(`/v1/energy/shift/reports/${params.report_type}`, { params })
}
export function exportShiftReport(data: any) {
  return request.post('/v1/energy/shift/reports/export', data.report_data, { params: { format: data.format } })
}
