/**
 * 阈值配置 API
 */
import request from '@/utils/request'
import type { PageParams, PageResponse } from './types'

export interface ThresholdInfo {
  id: number
  point_id: number
  point_code: string
  point_name: string
  threshold_type: 'high_high' | 'high' | 'low' | 'low_low' | 'equal' | 'change'
  threshold_value: number
  alarm_level: 'critical' | 'major' | 'minor' | 'info'
  alarm_message: string
  delay_seconds: number
  dead_band: number
  is_enabled: boolean
  priority: number
  created_at: string
  updated_at: string
}

export interface ThresholdCreateParams {
  point_id: number
  threshold_type: 'high_high' | 'high' | 'low' | 'low_low' | 'equal' | 'change'
  threshold_value: number
  alarm_level?: 'critical' | 'major' | 'minor' | 'info'
  alarm_message?: string
  delay_seconds?: number
  dead_band?: number
  priority?: number
}

export interface ThresholdUpdateParams extends Partial<ThresholdCreateParams> {
  is_enabled?: boolean
}

export interface ThresholdBatchCreateParams {
  point_ids: number[]
  thresholds: Omit<ThresholdCreateParams, 'point_id'>[]
}

export interface ThresholdCopyParams {
  source_point_id: number
  target_point_ids: number[]
  overwrite?: boolean
}

/**
 * 获取阈值配置列表
 */
export function getThresholdList(params?: PageParams & {
  point_id?: number
  threshold_type?: string
  alarm_level?: string
  is_enabled?: boolean
}): Promise<PageResponse<ThresholdInfo>> {
  return request.get('/v1/thresholds', { params })
}

/**
 * 获取点位阈值配置
 */
export function getPointThresholds(pointId: number): Promise<ThresholdInfo[]> {
  return request.get(`/v1/thresholds/point/${pointId}`)
}

/**
 * 获取阈值详情
 */
export function getThresholdById(id: number): Promise<ThresholdInfo> {
  return request.get(`/v1/thresholds/${id}`)
}

/**
 * 创建阈值配置
 */
export function createThreshold(data: ThresholdCreateParams): Promise<ThresholdInfo> {
  return request.post('/v1/thresholds', data)
}

/**
 * 更新阈值配置
 */
export function updateThreshold(id: number, data: ThresholdUpdateParams): Promise<ThresholdInfo> {
  return request.put(`/v1/thresholds/${id}`, data)
}

/**
 * 删除阈值配置
 */
export function deleteThreshold(id: number): Promise<void> {
  return request.delete(`/v1/thresholds/${id}`)
}

/**
 * 批量配置阈值
 */
export function batchCreateThresholds(data: ThresholdBatchCreateParams): Promise<{
  success: number
  failed: number
  errors: string[]
}> {
  return request.post('/v1/thresholds/batch', data)
}

/**
 * 复制阈值配置到其他点位
 */
export function copyThresholds(data: ThresholdCopyParams): Promise<{
  success: number
  failed: number
  errors: string[]
}> {
  return request.post('/v1/thresholds/copy', data)
}

// ==================== 4级阈值一体化配置 ====================

export interface FourLevelThresholdItem {
  value: number | null
  message?: string
  enabled?: boolean
}

export interface FourLevelThresholdParams {
  high_high?: FourLevelThresholdItem
  high?: FourLevelThresholdItem
  low?: FourLevelThresholdItem
  low_low?: FourLevelThresholdItem
  delay_seconds?: number
  dead_band?: number
}

export interface BatchByDeviceTypeParams {
  device_type: string
  thresholds: FourLevelThresholdParams
}

/**
 * 4级阈值一体化配置
 */
export function setFourLevelThresholds(
  pointId: number,
  data: FourLevelThresholdParams
): Promise<ThresholdInfo[]> {
  return request.put(`/v1/thresholds/point/${pointId}/four-level`, data)
}

/**
 * 按设备类型批量配置阈值
 */
export function batchSetByDeviceType(data: BatchByDeviceTypeParams): Promise<{
  success_count: number
  error_count: number
  errors: string[]
  total_points: number
}> {
  return request.post('/v1/thresholds/batch-by-device-type', data)
}

/**
 * 获取阈值配置版本号
 */
export function getThresholdVersion(): Promise<{
  version: number
  updated_at: string
}> {
  return request.get('/v1/thresholds/version')
}
