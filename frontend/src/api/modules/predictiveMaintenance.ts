/**
 * 预测性维护 API 模块 — Story 36.4
 */
import request from '@/utils/request'

// ==================== 类型定义 ====================

export interface DashboardSummary {
  total: number
  healthy: number
  attention: number
  warning: number
  danger: number
}

export interface DeviceHealthItem {
  device_id: number
  device_name: string | null
  device_type: string | null
  score: number
  health_level: '健康' | '关注' | '预警' | '危险'
  data_sufficiency: 'full' | 'partial' | 'minimal' | null
  degradation_score: number | null
  alarm_count: number
  calculated_at: string | null
}

export interface DashboardResponse {
  summary: DashboardSummary
  devices: DeviceHealthItem[]
}

export interface MaintenanceAdviceInfo {
  id: number
  device_id: number
  device_name: string | null
  device_type: string | null
  health_score: number | null
  urgency: 'high' | 'medium' | null
  reason: string | null
  suggested_action: string | null
  status: 'pending' | 'converted' | 'rejected' | 'auto_closed'
  feedback: string | null
  work_order_id: number | null
  created_at: string | null
  updated_at: string | null
  confirmed_at: string | null
  confirmed_by: number | null
}

export interface DeviceDetailResponse {
  health: DeviceHealthItem
  factors: {
    degradation?: { score: number; weight: number }
    alarm?: { score: number; weight: number; count: number }
    maintenance?: { score: number; weight: number; days_since: number | null }
    data_sufficiency?: string
    plugin_key?: string
  } | null
  advices: MaintenanceAdviceInfo[]
}

// ==================== API 函数 ====================

export function getDashboard(params?: {
  device_type?: string
  health_level?: string
  site_id?: number
}) {
  return request.get<DashboardResponse>('/v1/predictive-maintenance/dashboard', { params })
}

export function recalculateHealthScores() {
  return request.post<{
    total_devices: number
    calculated_at: string
    summary: Record<string, number>
    algorithm: string
  }>('/v1/reports/device-health/calculate', undefined, { timeout: 60000 })
}

export function getDeviceDetail(deviceId: number) {
  return request.get<DeviceDetailResponse>(`/v1/predictive-maintenance/devices/${deviceId}/detail`)
}

export function getAdviceList(params?: {
  status?: string
  device_type?: string
}) {
  return request.get<MaintenanceAdviceInfo[]>('/v1/predictive-maintenance/advices', { params })
}

export function confirmAdvice(adviceId: number) {
  return request.post<{ advice_id: number; work_order_id: number; work_order_no: string; status: string }>(
    `/v1/predictive-maintenance/advices/${adviceId}/confirm`
  )
}

export function rejectAdvice(adviceId: number, feedback: string) {
  return request.post<MaintenanceAdviceInfo>(
    `/v1/predictive-maintenance/advices/${adviceId}/reject`,
    { feedback }
  )
}
