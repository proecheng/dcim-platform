/**
 * 日志查询 API
 */
import request from '@/utils/request'
import type { PageParams, PageResponse, TimeRangeParams, ExportParams } from './types'

export interface OperationLog {
  id: number
  user_id: number
  username: string
  module: string
  action: string
  target_type: string
  target_id: number
  target_name: string
  old_value: string
  new_value: string
  ip_address: string
  response_code: number
  response_time_ms: number
  remark: string
  created_at: string
}

export interface SystemLog {
  id: number
  log_level: 'debug' | 'info' | 'warning' | 'error' | 'critical'
  module: string
  message: string
  exception: string
  stack_trace: string
  created_at: string
}

export interface CommunicationLog {
  id: number
  device_id: number
  device_name: string
  comm_type: 'request' | 'response' | 'error'
  protocol: string
  request_data: string
  response_data: string
  status: 'success' | 'failed' | 'timeout'
  error_message: string
  duration_ms: number
  created_at: string
}

export interface LogStatistics {
  total: number
  by_level: Record<string, number>
  by_module: Record<string, number>
  by_user: { user_id: number; username: string; count: number }[]
  trend: { date: string; count: number }[]
}

/**
 * 获取操作日志
 */
export function getOperationLogs(params?: PageParams & TimeRangeParams & {
  user_id?: number
  module?: string
  action?: string
  keyword?: string
}): Promise<PageResponse<OperationLog>> {
  return request.get('/v1/logs/operations', { params })
}

/**
 * 获取系统日志
 */
export function getSystemLogs(params?: PageParams & TimeRangeParams & {
  log_level?: string
  module?: string
  keyword?: string
}): Promise<PageResponse<SystemLog>> {
  return request.get('/v1/logs/systems', { params })
}

/**
 * 获取通讯日志
 */
export function getCommunicationLogs(params?: PageParams & TimeRangeParams & {
  device_id?: number
  protocol?: string
  status?: string
}): Promise<PageResponse<CommunicationLog>> {
  return request.get('/v1/logs/communications', { params })
}

/**
 * 导出日志
 */
export function exportLogs(params: ExportParams & {
  log_type: 'operation' | 'system' | 'communication'
}): Promise<Blob> {
  return request.get('/v1/logs/export', {
    params,
    responseType: 'blob'
  })
}

/**
 * 获取日志统计
 */
export function getLogStatistics(params?: TimeRangeParams & {
  log_type?: 'operation' | 'system' | 'communication'
}): Promise<LogStatistics> {
  return request.get('/v1/logs/statistics', { params })
}
