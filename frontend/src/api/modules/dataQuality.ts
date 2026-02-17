/**
 * 数据质量 API
 */
import request from '@/utils/request'

export interface DataQualityPointInfo {
  point_id: number
  point_code: string
  point_name: string
  device_type: string | null
  quality: number
  quality_text: string
  status: string | null
  updated_at: string | null
}

export interface DataQualityStatus {
  total: number
  normal_count: number
  uncertain_count: number
  unreliable_count: number
  unreliable_points: DataQualityPointInfo[]
}

export function getDataQualityStatus() {
  return request.get<DataQualityStatus>('/v1/data-quality/status')
}

export function getDataQualityPoints(params?: { quality?: number }) {
  return request.get<DataQualityPointInfo[]>('/v1/data-quality/points', { params })
}
