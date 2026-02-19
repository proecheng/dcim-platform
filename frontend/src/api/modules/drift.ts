/**
 * 传感器数据漂移检测 API
 * Story 9-7: 传感器数据漂移检测
 */
import request from '@/utils/request'
import type { PageParams, PageResponse } from './types'

// ==================== 类型定义 ====================

/** 漂移检测结果 */
export interface DriftDetectionResult {
  id: number
  point_id: number
  point_code: string
  point_name: string
  area_code: string | null
  status: string // suspected / confirmed / resolved
  mean_value: number
  std_value: number
  current_value: number
  deviation_sigma: number
  cross_validation_result: string | null
  diagnosis: string
  detected_at: string | null
  resolved_at: string | null
  created_at: string | null
}

/** 漂移检测概览 */
export interface DriftDetectionSummary {
  total_checked: number
  suspected_count: number
  confirmed_count: number
  resolved_count: number
  skipped_count: number
}

/** 触发检测响应 */
export interface DriftDetectResponse {
  message: string
  total_checked: number
  new_suspected: number
  new_confirmed: number
  auto_resolved: number
}

// ==================== API 函数 ====================

/**
 * 触发漂移检测
 */
export function triggerDriftDetection(): Promise<DriftDetectResponse> {
  return request.post('/v1/drift/detect')
}

/**
 * 获取漂移检测结果列表
 */
export function getDriftResults(params?: PageParams & {
  status?: string
  area_code?: string
}): Promise<PageResponse<DriftDetectionResult>> {
  return request.get('/v1/drift/results', { params })
}

/**
 * 获取漂移检测结果详情
 */
export function getDriftResult(id: number): Promise<DriftDetectionResult> {
  return request.get(`/v1/drift/results/${id}`)
}

/**
 * 手动解除漂移标记
 */
export function resolveDrift(id: number): Promise<DriftDetectionResult> {
  return request.post(`/v1/drift/results/${id}/resolve`)
}

/**
 * 获取漂移检测概览
 */
export function getDriftSummary(): Promise<DriftDetectionSummary> {
  return request.get('/v1/drift/summary')
}
