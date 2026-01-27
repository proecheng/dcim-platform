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
export function downloadReport(id: number): Promise<Blob> {
  return request.get(`/v1/reports/download/${id}`, {
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
