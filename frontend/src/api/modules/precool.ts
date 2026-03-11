import request from '@/utils/request'

// ========== 类型定义 ==========

export interface PredictRequest {
  hours?: number // 预测时长(小时), 0.5-24.0, 默认1.0
  q_cool_schedule?: number[] // 制冷功率计划(kW), null则使用当前功率
}

export interface PredictResponse {
  zone_id: number
  predicted_temp: number
  prediction_horizon_min: number
  temperature_trajectory: number[]
  time_steps: string[]
  model_version: string // "TCL" | "THM-fallback"
  data_quality?: Record<string, any>
  thm_result?: Record<string, any>
}

export interface ValidationReport {
  zone_id: number
  mae_1h: number | null
  mae_3h: number | null
  max_deviation: number | null
  sample_count: number
  period_days: number
}

export interface DashboardZone {
  zone_id: number
  zone_name: string
  current_temp: number | null
  headroom: number | null
  model_mode: string // "TCL" | "THM"
  shiftable_ratio: number | null
}

export interface DashboardResponse {
  zones: DashboardZone[]
  status_summary: {
    total_zones: number
    thm_zones: number
    tcl_zones: number
    offline_zones: number
  }
  today_savings: number
}

// ========== API 函数 ==========

/** 温度预测 */
export function predictTemperature(zoneId: number, data: PredictRequest) {
  return request.post<{ code: number; message: string; data: PredictResponse }>(
    `/v1/precool/zones/${zoneId}/predict`,
    data
  )
}

/** 精度验证报告 */
export function getValidationReport(zoneId: number) {
  return request.get<{ code: number; message: string; data: ValidationReport }>(
    `/v1/precool/zones/${zoneId}/validation`
  )
}

/** 热力学参数 */
export function getThermalParameters(zoneId: number, params?: { skip?: number; limit?: number }) {
  return request.get<{ code: number; message: string; data: { items: any[]; total: number } }>(
    `/v1/precool/zones/${zoneId}/parameters`,
    { params }
  )
}

/** 预冷仪表盘 */
export function getDashboard() {
  return request.get<{ code: number; message: string; data: DashboardResponse }>(
    '/v1/precool/dashboard'
  )
}

// ========== 回退保护类型 ==========

export interface RollbackTriggerInfo {
  trigger_type: string
  since: string | null
  event_id: number | null
  recovering: boolean
}

export interface RollbackStatusResponse {
  zone_id: number
  has_active_rollback: boolean
  active_triggers: RollbackTriggerInfo[]
}

export interface RollbackEventItem {
  id: number
  zone_id: number
  trigger_type: string
  trigger_value: number | null
  threshold: number | null
  action: string
  status: string
  context_json: string | null
  created_at: string | null
  resolved_at: string | null
}

export interface RollbackOverviewResponse {
  total_zones: number
  zones_with_active_rollback: number
  total_active_triggers: number
  trigger_type_counts: Record<string, number>
  recent_events_24h: number
  zone_statuses: RollbackStatusResponse[]
}

// ========== 回退保护 API ==========

/** 查询 zone 回退状态 */
export function getRollbackStatus(zoneId: number) {
  return request.get<{ code: number; message: string; data: RollbackStatusResponse }>(
    `/v1/precool/zones/${zoneId}/rollback-status`
  )
}

/** 查询回退历史事件 */
export function getRollbackHistory(
  zoneId: number,
  params?: { skip?: number; limit?: number; status?: 'active' | 'resolved' }
) {
  return request.get<{ code: number; message: string; data: { items: RollbackEventItem[]; total: number } }>(
    `/v1/precool/zones/${zoneId}/rollback-history`,
    { params }
  )
}

/** 全局回退概览 */
export function getRollbackOverview() {
  return request.get<{ code: number; message: string; data: RollbackOverviewResponse }>(
    '/v1/precool/rollback-overview'
  )
}

// ========== 预冷计划类型 (Story 31.5) ==========

export interface ScheduleListItem {
  id: number
  cooling_zone_id: number
  schedule_date: string
  precool_start_time: string
  precool_end_time: string
  target_temp: number
  peak_start_time: string
  peak_end_time: string
  planned_savings_kwh: number | null
  actual_savings_kwh: number | null
  status: 'pending' | 'executing' | 'completed' | 'aborted'
  abort_reason: string | null
  is_validated: boolean
  created_at: string | null
  updated_at: string | null
}

export interface ScheduleDetail extends ScheduleListItem {
  temperature_trajectory: {
    predicted?: number[]
    actual?: number[]
    timestamps?: string[]
    q_cool?: number[]
    q_cool_actual?: number[]
    prices?: number[]
  } | null
  validated_at: string | null
}

export interface PrecoolConfig {
  zone_id: number
  precool_enabled: boolean
  precool_target_temp: number
}

// ========== 预冷计划 API (Story 31.5) ==========

/** 生成预冷计划 */
export function createSchedule(zoneId: number, data?: { schedule_date?: string }) {
  return request.post<{ code: number; message: string; data: ScheduleDetail }>(
    `/v1/precool/zones/${zoneId}/schedule`,
    data || {}
  )
}

/** 查询预冷计划列表 */
export function listSchedules(
  zoneId: number,
  params?: { schedule_date?: string; status?: string; skip?: number; limit?: number }
) {
  return request.get<{ code: number; message: string; data: { items: ScheduleListItem[]; total: number } }>(
    `/v1/precool/zones/${zoneId}/schedule`,
    { params }
  )
}

/** 查询预冷计划详情 */
export function getSchedule(scheduleId: number) {
  return request.get<{ code: number; message: string; data: ScheduleDetail }>(
    `/v1/precool/schedules/${scheduleId}`
  )
}

/** 中止预冷计划 */
export function abortSchedule(scheduleId: number, data?: { reason?: string }) {
  return request.post<{ code: number; message: string; data: { status: string; abort_reason: string | null } }>(
    `/v1/precool/schedules/${scheduleId}/abort`,
    data || {}
  )
}

/** 查询预冷配置 */
export function getPrecoolConfig(zoneId: number) {
  return request.get<{ code: number; message: string; data: PrecoolConfig }>(
    `/v1/precool/zones/${zoneId}/config`
  )
}

/** 更新预冷配置 */
export function updatePrecoolConfig(zoneId: number, data: { precool_enabled?: boolean; precool_target_temp?: number }) {
  return request.put<{ code: number; message: string; data: PrecoolConfig }>(
    `/v1/precool/zones/${zoneId}/config`,
    data
  )
}
