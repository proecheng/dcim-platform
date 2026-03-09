/**
 * 概率调参 API - Story 26.3
 */
import request from '@/utils/request'

export interface ProbabilityAdjustment {
  id: number
  tree_id: number
  tree_name: string
  node_id: number
  node_name: string
  node_type: string
  current_probability: number
  proposed_probability: number
  adjustment_percent: number
  sample_count: number
  accurate_count: number
  inaccurate_count: number
  accuracy_rate: number
  status: string
  reason?: string
  approved_by?: number
  approved_at?: string
  created_at: string
}

export interface ProbabilityAdjustmentListResponse {
  items: ProbabilityAdjustment[]
  total: number
}

export interface TriggerAnalysisResponse {
  analyzed_trees: number
  analyzed_nodes: number
  total_adjustments: number
  pending_approvals: number
}

/**
 * 触发概率调参分析
 */
export function triggerProbabilityAnalysis(treeId?: number) {
  return request<TriggerAnalysisResponse>({
    url: '/diagnosis/probability-tuning/trigger',
    method: 'post',
    params: treeId ? { tree_id: treeId } : undefined
  })
}

/**
 * 获取调参记录列表
 */
export function getProbabilityAdjustments(params: {
  tree_id?: number
  status?: string
  skip?: number
  limit?: number
}) {
  return request<ProbabilityAdjustmentListResponse>({
    url: '/diagnosis/probability-tuning/adjustments',
    method: 'get',
    params
  })
}

/**
 * 审批调参建议
 */
export function approveProbabilityAdjustment(adjustmentId: number, reason?: string) {
  return request({
    url: `/diagnosis/probability-tuning/adjustments/${adjustmentId}/approve`,
    method: 'post',
    data: { reason }
  })
}

/**
 * 拒绝调参建议
 */
export function rejectProbabilityAdjustment(adjustmentId: number, reason: string) {
  return request({
    url: `/diagnosis/probability-tuning/adjustments/${adjustmentId}/reject`,
    method: 'post',
    data: { reason }
  })
}

/**
 * 回滚故障树到上一个版本
 */
export function rollbackFaultTree(treeId: number) {
  return request({
    url: `/diagnosis/probability-tuning/rollback/${treeId}`,
    method: 'post'
  })
}
