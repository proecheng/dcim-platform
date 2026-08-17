import request from '@/utils/request'
import type { ResponseModel } from './types'

export interface RLModelInfo {
  model_name: string
  is_trained: boolean
  is_available: boolean
  total_steps: number
  total_episodes: number
  exploration_rate: number
  exploration_phase: string
  avg_reward?: number | null
  avg_achievement_rate?: number | null
  best_reward?: number | null
  checkpoint_saved_at?: string | null
  state_dim?: number | null
  action_spec?: Record<string, unknown> | null
}

export interface RLAdjustment {
  value: unknown
  description: string
  unit?: string | null
  index?: number | null
}

export interface RLOptimizationResult {
  proposal_id: number
  success: boolean
  adjustments: Record<string, RLAdjustment>
  raw_actions?: Record<string, number> | null
  exploration: boolean
  exploration_rate: number
  confidence: number
  state_value?: number | null
  optimization_id?: number | null
}

export interface RLOptimizationHistoryItem {
  id: number
  proposal_id: number
  created_at: string
  exploration: boolean
  exploration_rate?: number | null
  confidence?: number | null
  applied: boolean
  reward?: number | null
  achievement_rate?: number | null
  adjustments?: Record<string, RLAdjustment> | null
}

export interface RLOptimizationHistory {
  total: number
  items: RLOptimizationHistoryItem[]
}

export interface RLTrainingParams {
  proposal_id?: number
  actual_saving: number
  expected_saving: number
  comfort_violation?: number
  safety_violation?: number
}

export interface RLTrainingResult {
  success: boolean
  reward: number
  achievement_rate: number
  exploration_rate: number
  step: number
  network_updated: boolean
  update_info?: Record<string, unknown> | null
  training_log_id?: number | null
}

export function getRLModelInfo() {
  return request.get<RLModelInfo>('/v1/proposals/rl/model-info')
}

export function updateRLExplorationRate(explorationRate: number, phase = 'manual') {
  return request.put<ResponseModel<{ old_rate: number; new_rate: number; phase: string }>>(
    '/v1/proposals/rl/exploration-rate',
    { exploration_rate: explorationRate, phase }
  )
}

export function saveRLCheckpoint() {
  return request.post<ResponseModel<{ checkpoint_path: string }>>('/v1/proposals/rl/save-checkpoint')
}

export function optimizeProposalWithRL(proposalId: number) {
  return request.post<RLOptimizationResult>(`/v1/proposals/${proposalId}/rl/optimize`, {})
}

export function getProposalRLHistory(proposalId: number, limit = 20) {
  return request.get<RLOptimizationHistory>(`/v1/proposals/${proposalId}/rl/history`, {
    params: { limit }
  })
}

export function applyProposalRLOptimization(proposalId: number, optimizationId: number) {
  return request.post<ResponseModel<{ optimization_id: number }>>(
    `/v1/proposals/${proposalId}/rl/apply/${optimizationId}`
  )
}

export function trainRLModel(data: RLTrainingParams) {
  return request.post<RLTrainingResult>('/v1/proposals/rl/train', data)
}

export function trainRLFromMonitoring(proposalId: number) {
  return request.post<ResponseModel<RLTrainingResult>>(
    `/v1/proposals/${proposalId}/rl/train-from-monitoring`
  )
}
