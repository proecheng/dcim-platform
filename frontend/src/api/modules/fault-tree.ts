/**
 * 故障树 API
 * Story 25.8: 故障树图形化编辑器
 */

import request from '@/utils/request'
import type { FaultTree, SaveFaultTreePayload, PointInfo } from '@/types/fault-tree'

/**
 * 获取故障树详情
 */
export function getFaultTree(id: number) {
  return request.get<FaultTree>(`/v1/fault-trees/${id}`)
}

/**
 * 创建故障树新版本
 */
export function createFaultTreeVersion(id: number, data: SaveFaultTreePayload) {
  return request.post<FaultTree>(`/v1/fault-trees/${id}/versions`, data)
}

/**
 * 搜索点位（用于叶节点关联）
 */
export function searchPoints(query: string, limit: number = 50) {
  return request.get<{ items: PointInfo[]; total: number }>(
    '/v1/points/search',
    { params: { q: query, limit } }
  )
}
