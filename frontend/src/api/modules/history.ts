/**
 * 历史数据 API
 */
import request from '@/utils/request'
import type { PageParams, PageResponse, TimeRangeParams, ExportParams } from './types'

export interface HistoryData {
  id: number
  point_id: number
  raw_value: number
  value: number
  quality: number
  created_at: string
}

export interface TrendData {
  time: string
  value: number
  min?: number
  max?: number
  avg?: number
}

export interface HistoryStatistics {
  point_id: number
  point_name: string
  start_time: string
  end_time: string
  count: number
  min_value: number
  max_value: number
  avg_value: number
  sum_value: number
  std_dev: number
  first_value: number
  last_value: number
  change_rate: number
}

export interface CompareData {
  point_id: number
  point_name: string
  data: TrendData[]
}

export interface ChangeRecord {
  id: number
  point_id: number
  old_value: number
  new_value: number
  old_text: string
  new_text: string
  change_type: string
  created_at: string
}

/**
 * 获取点位历史数据
 */
export function getPointHistory(pointId: number, params: TimeRangeParams & PageParams & {
  granularity?: 'raw' | 'minute' | 'hour' | 'day'
}): Promise<PageResponse<HistoryData>> {
  return request.get(`/v1/history/${pointId}`, { params })
}

/**
 * 获取趋势数据（用于图表）
 */
export function getPointTrend(pointId: number, params: TimeRangeParams & {
  granularity?: 'raw' | 'minute' | 'hour' | 'day'
  limit?: number
}): Promise<TrendData[]> {
  return request.get(`/v1/history/${pointId}/trend`, { params })
}

/**
 * 获取统计数据
 */
export function getPointStatistics(pointId: number, params: TimeRangeParams): Promise<HistoryStatistics> {
  return request.get(`/v1/history/${pointId}/statistics`, { params })
}

/**
 * 多点位对比查询
 */
export function getPointsCompare(params: TimeRangeParams & {
  point_ids: number[]
  granularity?: 'raw' | 'minute' | 'hour' | 'day'
}): Promise<CompareData[]> {
  return request.get('/v1/history/compare', { params })
}

/**
 * 导出历史数据
 */
export function exportHistory(params: ExportParams & {
  point_ids: number[]
  granularity?: 'raw' | 'minute' | 'hour' | 'day'
}): Promise<Blob> {
  return request.get('/v1/history/export', {
    params,
    responseType: 'blob'
  })
}

/**
 * 获取变化记录（DI 点位）
 */
export function getChangeRecords(pointId: number, params?: TimeRangeParams & PageParams): Promise<PageResponse<ChangeRecord>> {
  return request.get(`/v1/history/changes/${pointId}`, { params })
}

/**
 * 清理过期数据
 */
export function cleanupHistory(params: {
  before_date: string
  granularity?: 'raw' | 'minute' | 'hour' | 'day'
}): Promise<{ deleted_count: number }> {
  return request.delete('/v1/history/cleanup', { params })
}
