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
