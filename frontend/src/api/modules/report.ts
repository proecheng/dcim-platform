/**
 * 报表 API
 */
import request from '@/utils/request'
import type { PageParams, PageResponse, TimeRangeParams } from './types'

export interface ReportTemplate {
  id: number
  template_name: string
  template_type: 'daily' | 'weekly' | 'monthly' | 'custom'
  template_config: Record<string, any>
  point_ids: number[]
  is_enabled: boolean
  created_by: number
  created_at: string
  updated_at: string
}

export interface ReportTemplateCreateParams {
  template_name: string
  template_type: 'daily' | 'weekly' | 'monthly' | 'custom'
  template_config?: Record<string, any>
  point_ids?: number[]
  is_enabled?: boolean
}

export interface ReportRecord {
  id: number
  template_id: number
  template_name: string
  report_name: string
  report_type: string
  start_time: string
  end_time: string
  file_path: string
  file_size: number
  status: 'generating' | 'completed' | 'failed'
  error_message: string | null
  generated_by: number
  created_at: string
}

export interface ReportGenerateParams {
  template_id?: number
  report_type: 'daily' | 'weekly' | 'monthly' | 'custom'
  start_time: string
  end_time: string
  point_ids?: number[]
  format?: 'pdf' | 'excel' | 'html'
}

export interface DailyReportData {
  date: string
  summary: {
    total_points: number
    alarm_count: number
    avg_temperature: number
    avg_humidity: number
    power_consumption: number
  }
  points: {
    point_id: number
    point_name: string
    min_value: number
    max_value: number
    avg_value: number
    alarm_count: number
  }[]
  alarms: {
    time: string
    point_name: string
    level: string
    message: string
    status: string
  }[]
}

/**
 * 获取报表模板列表
 */
export function getReportTemplates(params?: PageParams & {
  template_type?: string
}): Promise<PageResponse<ReportTemplate>> {
  return request.get('/v1/reports/templates', { params })
}

/**
 * 获取报表模板详情
 */
export function getReportTemplateById(id: number): Promise<ReportTemplate> {
  return request.get(`/v1/reports/templates/${id}`)
}

/**
 * 创建报表模板
 */
export function createReportTemplate(data: ReportTemplateCreateParams): Promise<ReportTemplate> {
  return request.post('/v1/reports/templates', data)
}

/**
 * 更新报表模板
 */
export function updateReportTemplate(id: number, data: Partial<ReportTemplateCreateParams>): Promise<ReportTemplate> {
  return request.put(`/v1/reports/templates/${id}`, data)
}

/**
 * 删除报表模板
 */
export function deleteReportTemplate(id: number): Promise<void> {
  return request.delete(`/v1/reports/templates/${id}`)
}

/**
 * 生成报表
 */
export function generateReport(data: ReportGenerateParams): Promise<ReportRecord> {
  return request.post('/v1/reports/generate', data)
}

/**
 * 获取报表记录
 */
export function getReportRecords(params?: PageParams & TimeRangeParams & {
  report_type?: string
  status?: string
}): Promise<PageResponse<ReportRecord>> {
  return request.get('/v1/reports/records', { params })
}

/**
 * 下载报表
 */
export function downloadReport(id: number, format: 'json' | 'csv' | 'pdf' = 'json'): Promise<Blob> {
  return request.get(`/v1/reports/download/${id}`, {
    params: { format },
    responseType: 'blob'
  })
}

/**
 * 获取日报数据
 */
export function getDailyReport(params: { date: string }): Promise<DailyReportData> {
  return request.get('/v1/reports/daily', { params })
}

/**
 * 获取周报数据
 */
export function getWeeklyReport(params: { start_date: string; end_date: string }): Promise<any> {
  return request.get('/v1/reports/weekly', { params })
}

/**
 * 获取月报数据
 */
export function getMonthlyReport(params: { year: number; month: number }): Promise<any> {
  return request.get('/v1/reports/monthly', { params })
}

// ============================================================
// Story 12-1: 自动运行报表
// ============================================================

/** 报表调度配置 */
export interface ReportSchedule {
  id: number
  name: string
  report_type: 'daily' | 'weekly' | 'monthly'
  is_enabled: boolean
  last_run_at: string | null
  next_run_at: string | null
  created_by: number | null
  created_at: string
  updated_at: string
}

/** 创建报表调度参数 */
export interface ReportScheduleCreateParams {
  name: string
  report_type: 'daily' | 'weekly' | 'monthly'
  is_enabled?: boolean
}

/** 更新报表调度参数 */
export interface ReportScheduleUpdateParams {
  name?: string
  report_type?: 'daily' | 'weekly' | 'monthly'
  is_enabled?: boolean
}

/** 自动报表数据 */
export interface AutoReportData {
  report_type: string
  title: string
  period: { start: string; end: string }
  generated_at: string
  alarm_trends: {
    total: number
    by_level: Record<string, number>
    daily_trend: { date: string; count: number }[]
    top_alarm_points: { point_id: number; point_name: string; count: number }[]
    avg_resolve_duration_seconds: number
  }
  energy_comparison: {
    current_energy_kwh: number
    current_cost: number
    prev_energy_kwh: number
    prev_cost: number
    energy_change_percent: number
    cost_change_percent: number
    avg_pue: number
  }
  workorder_stats: {
    total: number
    by_status: Record<string, number>
    by_type: Record<string, number>
  }
  device_availability: {
    overall_percent: number
    by_device_type: Record<string, number>
    total_devices: number
    online_devices: number
    online_rate: number
  }
  comparison: {
    alarm_current: number
    alarm_prev_period: number
    alarm_mom_change_percent: number
    alarm_yoy_period: number
    alarm_yoy_change_percent: number
  }
}

/** 自动报表生成响应 */
export interface AutoReportResponse {
  record_id: number
  report_name: string
  data: AutoReportData
}

/**
 * 自动生成运行报表
 */
export function autoGenerateReport(reportType: 'daily' | 'weekly' | 'monthly'): Promise<AutoReportResponse> {
  return request.post('/v1/reports/auto-generate', { report_type: reportType })
}

/**
 * 获取报表调度列表
 */
export function getReportSchedules(): Promise<ReportSchedule[]> {
  return request.get('/v1/reports/schedules')
}

/**
 * 创建报表调度
 */
export function createReportSchedule(data: ReportScheduleCreateParams): Promise<ReportSchedule> {
  return request.post('/v1/reports/schedules', data)
}

/**
 * 更新报表调度
 */
export function updateReportSchedule(id: number, data: ReportScheduleUpdateParams): Promise<ReportSchedule> {
  return request.put(`/v1/reports/schedules/${id}`, data)
}

/**
 * 删除报表调度
 */
export function deleteReportSchedule(id: number): Promise<void> {
  return request.delete(`/v1/reports/schedules/${id}`)
}

// ============================================================
// Story 12-2: 智能摘要面板
// ============================================================

/** 摘要面板项 */
export interface SummaryPanelItem {
  type: string
  title: string
  priority: number
  count: number
  action: string
  link: string
}

/** 摘要面板响应 */
export interface SummaryPanelResponse {
  items: SummaryPanelItem[]
  total_items: number
  generated_at: string
}

/**
 * 获取智能摘要面板
 */
export function getSummaryPanel(): Promise<SummaryPanelResponse> {
  return request.get('/v1/reports/summary-panel')
}

// ============================================================
// Story 12-3: PDF 报表导出
// ============================================================

/**
 * 导出自动报表为 PDF
 */
export function exportAutoReportPdf(recordId: number): Promise<Blob> {
  return request.get(`/v1/reports/auto-report-pdf/${recordId}`, {
    responseType: 'blob'
  })
}

// ============================================================
// Story 12-4: 设备健康度评估
// ============================================================

/** 设备健康度评分 */
export interface DeviceHealthScore {
  id: number
  device_id: number
  device_name: string
  device_type: string
  score: number
  health_level: '健康' | '关注' | '预警' | '危险'
  alarm_count: number
  maintenance_count: number
  last_maintenance_at: string | null
  calculated_at: string | null
}

/** 健康度计算结果 */
export interface HealthCalculateResult {
  total_devices: number
  calculated_at: string
  summary: Record<string, number>
}

/**
 * 计算设备健康度
 */
export function calculateDeviceHealth(): Promise<HealthCalculateResult> {
  return request.post('/v1/reports/device-health/calculate')
}

/**
 * 获取设备健康度列表
 */
export function getDeviceHealthList(params?: {
  health_level?: string
  sort_by?: 'score' | 'alarm_count'
  sort_order?: 'asc' | 'desc'
}): Promise<DeviceHealthScore[]> {
  return request.get('/v1/reports/device-health', { params })
}

/**
 * 获取单个设备健康度
 */
export function getDeviceHealth(deviceId: number): Promise<DeviceHealthScore> {
  return request.get(`/v1/reports/device-health/${deviceId}`)
}
