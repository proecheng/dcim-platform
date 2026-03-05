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
  escalation_count?: number
  escalated_from?: string | null
  escalation_remark?: string | null
  data_source?: string
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

export interface AlarmProcessParams {
  process_remark: string
}

/**
 * 获取告警列表
 */
export function getAlarmList(params?: PageParams & TimeRangeParams & {
  alarm_level?: string
  alarm_type?: string
  status?: string
  point_id?: number
  device_type?: string
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
 * 处理告警
 */
export function processAlarm(id: number, data: AlarmProcessParams): Promise<void> {
  return request.put(`/v1/alarms/${id}/process`, data)
}

/**
 * 批量确认告警
 */
export function batchAcknowledgeAlarms(ids: number[], remark?: string): Promise<void> {
  return request.put('/v1/alarms/batch-acknowledge', { alarm_ids: ids, remark })
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

// ==================== 告警规则管理 ====================

export interface AlarmRuleInfo {
  id: number
  rule_name: string
  rule_type: 'and' | 'or' | 'sequence'
  condition_expr: string | null
  alarm_level: 'critical' | 'major' | 'minor' | 'info'
  alarm_message: string | null
  is_enabled: boolean
  created_at: string
}

export interface AlarmRuleCreateParams {
  rule_name: string
  rule_type?: 'and' | 'or' | 'sequence'
  condition_expr?: string
  alarm_level?: 'critical' | 'major' | 'minor' | 'info'
  alarm_message?: string
  is_enabled?: boolean
}

export interface AlarmRuleUpdateParams {
  rule_name?: string
  rule_type?: 'and' | 'or' | 'sequence'
  condition_expr?: string
  alarm_level?: 'critical' | 'major' | 'minor' | 'info'
  alarm_message?: string
  is_enabled?: boolean
}

/**
 * 获取告警规则列表
 */
export function getAlarmRules(params?: PageParams & {
  rule_type?: string
  alarm_level?: string
  is_enabled?: boolean
}): Promise<PageResponse<AlarmRuleInfo>> {
  return request.get('/v1/alarms/rules', { params })
}

/**
 * 创建告警规则
 */
export function createAlarmRule(data: AlarmRuleCreateParams): Promise<AlarmRuleInfo> {
  return request.post('/v1/alarms/rules', data)
}

/**
 * 获取告警规则详情
 */
export function getAlarmRuleById(id: number): Promise<AlarmRuleInfo> {
  return request.get(`/v1/alarms/rules/${id}`)
}

/**
 * 更新告警规则
 */
export function updateAlarmRule(id: number, data: AlarmRuleUpdateParams): Promise<AlarmRuleInfo> {
  return request.put(`/v1/alarms/rules/${id}`, data)
}

/**
 * 删除告警规则
 */
export function deleteAlarmRule(id: number): Promise<void> {
  return request.delete(`/v1/alarms/rules/${id}`)
}

/**
 * 切换告警规则启用状态
 */
export function toggleAlarmRule(id: number): Promise<{ message: string; is_enabled: boolean }> {
  return request.put(`/v1/alarms/rules/${id}/toggle`)
}

// ==================== 告警屏蔽管理 ====================

export interface AlarmShieldInfo {
  id: number
  point_id: number | null
  point_code: string | null
  point_name: string | null
  alarm_level: 'critical' | 'major' | 'minor' | 'info' | null
  start_time: string
  end_time: string
  reason: string | null
  created_by: number | null
  creator_name: string | null
  created_at: string
  status: 'active' | 'expired' | null
}

export interface AlarmShieldCreateParams {
  point_id?: number | null
  alarm_level?: 'critical' | 'major' | 'minor' | 'info' | null
  start_time: string
  end_time: string
  reason?: string
}

/**
 * 获取告警屏蔽列表
 */
export function getAlarmShields(params?: PageParams & {
  point_id?: number
  alarm_level?: string
}): Promise<PageResponse<AlarmShieldInfo>> {
  return request.get('/v1/alarms/shields', { params })
}

/**
 * 创建告警屏蔽
 */
export function createAlarmShield(data: AlarmShieldCreateParams): Promise<AlarmShieldInfo> {
  return request.post('/v1/alarms/shields', data)
}

/**
 * 删除告警屏蔽
 */
export function deleteAlarmShield(id: number): Promise<void> {
  return request.delete(`/v1/alarms/shields/${id}`)
}

// ==================== 告警升级规则管理 ====================

export interface AlarmEscalationInfo {
  id: number
  rule_name: string
  source_level: string
  timeout_minutes: number
  target_level: string
  notify_user_ids: number[]
  is_enabled: boolean
  description: string | null
  escalation_chain: string | null
  created_at: string | null
  updated_at: string | null
}

export interface AlarmEscalationCreateParams {
  rule_name: string
  source_level: string
  timeout_minutes: number
  target_level: string
  notify_user_ids: number[]
  is_enabled?: boolean
  description?: string
  escalation_chain?: string
}

export interface AlarmEscalationUpdateParams {
  rule_name?: string
  source_level?: string
  timeout_minutes?: number
  target_level?: string
  notify_user_ids?: number[]
  is_enabled?: boolean
  description?: string
  escalation_chain?: string
}

export function getEscalations(params?: { source_level?: string; is_enabled?: boolean; page?: number; page_size?: number }) {
  return request.get('/v1/escalations', { params })
}

export function createEscalation(data: AlarmEscalationCreateParams) {
  return request.post('/v1/escalations', data)
}

export function getEscalation(id: number) {
  return request.get(`/v1/escalations/${id}`)
}

export function updateEscalation(id: number, data: AlarmEscalationUpdateParams) {
  return request.put(`/v1/escalations/${id}`, data)
}

export function deleteEscalation(id: number) {
  return request.delete(`/v1/escalations/${id}`)
}

export function toggleEscalation(id: number) {
  return request.put(`/v1/escalations/${id}/toggle`)
}
