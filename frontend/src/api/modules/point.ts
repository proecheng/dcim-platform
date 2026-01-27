/**
 * 点位管理 API
 */
import request from '@/utils/request'
import type { PageParams, PageResponse } from './types'

export interface PointInfo {
  id: number
  point_code: string
  point_name: string
  point_type: 'AI' | 'DI' | 'AO' | 'DO'
  device_id: number
  device_type: string
  area_code: string
  unit: string
  data_type: string
  min_range: number
  max_range: number
  precision: number
  collect_interval: number
  store_interval: number
  is_enabled: boolean
  is_virtual: boolean
  calc_formula: string
  description: string
  sort_order: number
  created_at: string
  updated_at: string
}

export interface PointCreateParams {
  point_code: string
  point_name: string
  point_type: 'AI' | 'DI' | 'AO' | 'DO'
  device_id?: number
  device_type: string
  area_code: string
  unit?: string
  data_type?: string
  min_range?: number
  max_range?: number
  precision?: number
  collect_interval?: number
  store_interval?: number
  is_virtual?: boolean
  calc_formula?: string
  description?: string
  sort_order?: number
}

export interface PointUpdateParams extends Partial<PointCreateParams> {
  is_enabled?: boolean
}

export interface PointTypesSummary {
  total: number
  enabled: number
  AI: number
  DI: number
  AO: number
  DO: number
  by_area: Record<string, number>
  by_device_type: Record<string, number>
}

export interface PointGroup {
  id: number
  group_name: string
  group_type: 'area' | 'device_type' | 'custom'
  parent_id: number | null
  sort_order: number
  point_count: number
}

export interface PointGroupCreateParams {
  group_name: string
  group_type: 'area' | 'device_type' | 'custom'
  parent_id?: number
  sort_order?: number
  point_ids?: number[]
}

/**
 * 获取点位列表
 */
export function getPointList(params?: PageParams & {
  point_type?: string
  device_type?: string
  area_code?: string
  device_id?: number
  is_enabled?: boolean
  keyword?: string
}): Promise<PageResponse<PointInfo>> {
  return request.get('/v1/points', { params })
}

/**
 * 获取点位详情
 */
export function getPointById(id: number): Promise<PointInfo> {
  return request.get(`/v1/points/${id}`)
}

/**
 * 创建点位
 */
export function createPoint(data: PointCreateParams): Promise<PointInfo> {
  return request.post('/v1/points', data)
}

/**
 * 更新点位
 */
export function updatePoint(id: number, data: PointUpdateParams): Promise<PointInfo> {
  return request.put(`/v1/points/${id}`, data)
}

/**
 * 删除点位
 */
export function deletePoint(id: number): Promise<void> {
  return request.delete(`/v1/points/${id}`)
}

/**
 * 启用点位
 */
export function enablePoint(id: number): Promise<void> {
  return request.put(`/v1/points/${id}/enable`)
}

/**
 * 禁用点位
 */
export function disablePoint(id: number): Promise<void> {
  return request.put(`/v1/points/${id}/disable`)
}

/**
 * 批量导入点位
 */
export function batchImportPoints(data: FormData): Promise<{ success: number; failed: number; errors: string[] }> {
  return request.post('/v1/points/batch-import', data, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/**
 * 导出点位配置
 */
export function exportPoints(params?: {
  point_type?: string
  device_type?: string
  area_code?: string
  format?: 'excel' | 'csv' | 'json'
}): Promise<Blob> {
  return request.get('/v1/points/export', {
    params,
    responseType: 'blob'
  })
}

/**
 * 获取点位类型统计
 */
export function getPointTypesSummary(): Promise<PointTypesSummary> {
  return request.get('/v1/points/types-summary')
}

/**
 * 获取点位分组
 */
export function getPointGroups(params?: { group_type?: string }): Promise<PointGroup[]> {
  return request.get('/v1/points/groups', { params })
}

/**
 * 创建点位分组
 */
export function createPointGroup(data: PointGroupCreateParams): Promise<PointGroup> {
  return request.post('/v1/points/groups', data)
}
