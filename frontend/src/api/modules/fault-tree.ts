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
  return request<FaultTree>({
    url: `/api/v1/fault-trees/${id}`,
    method: 'get'
  })
}

/**
 * 创建故障树新版本
 */
export function createFaultTreeVersion(id: number, data: SaveFaultTreePayload) {
  return request<FaultTree>({
    url: `/api/v1/fault-trees/${id}/versions`,
    method: 'post',
    data
  })
}

/**
 * 搜索点位（用于叶节点关联）
 */
export function searchPoints(query: string, limit: number = 50) {
  return request<{ items: PointInfo[]; total: number }>({
    url: '/api/v1/points/search',
    method: 'get',
    params: {
      q: query,
      limit
    }
  })
}
