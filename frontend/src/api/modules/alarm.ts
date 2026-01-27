/**
 * 告警管理 API
 */
import request from '@/utils/request'
import type { PageParams, PageResponse, TimeRangeParams, ExportParams } from './types'

export interface AlarmInfo {
  id: number
  alarm_no: string
  point_id: number
  point_code: string
  point_name: string
  threshold_id: number
  alarm_level: 'critical' | 'major' | 'minor' | 'info'
  alarm_type: 'threshold' | 'communication' | 'system'
  alarm_message: string
  trigger_value: number
  threshold_value: number
  status: 'active' | 'acknowledged' | 'resolved' | 'ignored'
  acknowledged_by: number | null
  acknowledged_at: string | null
  ack_remark: string | null
  resolved_by: number | null
  resolved_at: string | null
  resolve_remark: string | null
  resolve_type: 'manual' | 'auto' | 'timeout' | null
  duration_seconds: number | null
  is_notified: boolean
  notify_count: number
  created_at: string
}

export interface AlarmCount {
  critical: number
  major: number
  minor: number
  info: number
  total: number
}

export interface AlarmStatistics {
  total: number
  by_level: AlarmCount
  by_type: Record<string, number>
  by_status: Record<string, number>
  by_point: { point_id: number; point_name: string; count: number }[]
  avg_duration: number
  mttr: number // Mean Time To Repair
}

export interface AlarmTrend {
  date: string
  critical: number
  major: number
  minor: number
  info: number
  total: number
}

export interface AlarmAcknowledgeParams {
  remark?: string
}

export interface AlarmResolveParams {
  resolve_type?: 'manual' | 'auto' | 'timeout'
  remark?: string
}

/**
 * 获取告警列表
 */
export function getAlarmList(params?: PageParams & TimeRangeParams & {
  alarm_level?: string
  alarm_type?: string
  status?: string
  point_id?: number
  keyword?: string
}): Promise<PageResponse<AlarmInfo>> {
  return request.get('/v1/alarms', { params })
}

/**
 * 获取活动告警
 */
export function getActiveAlarms(params?: {
  alarm_level?: string
  point_id?: number
}): Promise<AlarmInfo[]> {
  return request.get('/v1/alarms/active', { params })
}

/**
 * 获取告警详情
 */
export function getAlarmById(id: number): Promise<AlarmInfo> {
  return request.get(`/v1/alarms/${id}`)
}

/**
 * 确认告警
 */
export function acknowledgeAlarm(id: number, data?: AlarmAcknowledgeParams): Promise<void> {
  return request.put(`/v1/alarms/${id}/acknowledge`, data)
}

/**
 * 解决告警
 */
export function resolveAlarm(id: number, data?: AlarmResolveParams): Promise<void> {
  return request.put(`/v1/alarms/${id}/resolve`, data)
}

/**
 * 批量确认告警
 */
export function batchAcknowledgeAlarms(ids: number[], data?: AlarmAcknowledgeParams): Promise<void> {
  return request.put('/v1/alarms/batch-acknowledge', { ids, ...data })
}

/**
 * 获取各级别告警数量
 */
export function getAlarmCount(): Promise<AlarmCount> {
  return request.get('/v1/alarms/count')
}

/**
 * 获取告警统计
 */
export function getAlarmStatistics(params?: TimeRangeParams): Promise<AlarmStatistics> {
  return request.get('/v1/alarms/statistics', { params })
}

/**
 * 获取告警趋势
 */
export function getAlarmTrend(params?: TimeRangeParams & {
  granularity?: 'hour' | 'day' | 'week' | 'month'
}): Promise<AlarmTrend[]> {
  return request.get('/v1/alarms/trend', { params })
}

/**
 * 获取高频告警点位
 */
export function getTopAlarmPoints(params?: TimeRangeParams & {
  limit?: number
}): Promise<{ point_id: number; point_name: string; count: number }[]> {
  return request.get('/v1/alarms/top-points', { params })
}

/**
 * 导出告警记录
 */
export function exportAlarms(params?: ExportParams & {
  alarm_level?: string
  alarm_type?: string
  status?: string
}): Promise<Blob> {
  return request.get('/v1/alarms/export', {
    params,
    responseType: 'blob'
  })
}
