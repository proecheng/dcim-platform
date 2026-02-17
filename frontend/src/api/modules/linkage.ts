/**
 * 联动管理 API
 */
import request from '@/utils/request'
import type { PageParams, PageResponse } from './types'

// ==================== 类型定义 ====================

/** 联动动作 */
export interface LinkageAction {
  id: number
  policy_id: number
  action_type: string
  action_config: Record<string, unknown>
  sort_order: number
  timeout_seconds: number
  retry_count: number
  created_at: string
}

/** 联动策略 */
export interface LinkagePolicy {
  id: number
  name: string
  description: string
  trigger_type: string
  trigger_condition: Record<string, unknown>
  priority: string
  is_enabled: boolean
  is_system: boolean
  actions: LinkageAction[]
  created_at: string
  updated_at: string
}

/** 创建联动动作参数 */
export interface LinkageActionCreate {
  action_type: string
  action_config: Record<string, unknown>
  sort_order?: number
  timeout_seconds?: number
  retry_count?: number
}

/** 创建联动策略参数 */
export interface LinkagePolicyCreate {
  name: string
  description?: string
  trigger_type: string
  trigger_condition: Record<string, unknown>
  priority?: string
  is_enabled?: boolean
  actions: LinkageActionCreate[]
}

/** 联动执行日志 */
export interface LinkageLog {
  id: number
  execution_id: number
  action_id: number
  action_type: string
  action_config: Record<string, unknown>
  status: string
  error_message: string | null
  started_at: string
  completed_at: string | null
  duration_ms: number | null
}

/** 联动执行记录 */
export interface LinkageExecution {
  id: number
  policy_id: number
  event_id: string
  trigger_source: string
  trigger_event: string
  status: string
  started_at: string
  completed_at: string | null
  total_duration_ms: number | null
  logs: LinkageLog[]
  policy_name?: string
}

/** 动作类型信息 */
export interface ActionTypeInfo {
  action_type: string
  description: string
  is_implemented: boolean
}

// ==================== API 函数 ====================

/**
 * 获取联动策略列表
 */
export function getLinkagePolicies(params?: PageParams & {
  name?: string
  trigger_type?: string
  is_enabled?: boolean
}): Promise<PageResponse<LinkagePolicy>> {
  return request.get('/v1/linkage/policies', { params })
}

/**
 * 获取联动策略详情
 */
export function getLinkagePolicy(id: number): Promise<LinkagePolicy> {
  return request.get(`/v1/linkage/policies/${id}`)
}

/**
 * 创建联动策略
 */
export function createLinkagePolicy(data: LinkagePolicyCreate): Promise<LinkagePolicy> {
  return request.post('/v1/linkage/policies', data)
}

/**
 * 更新联动策略
 */
export function updateLinkagePolicy(id: number, data: Partial<LinkagePolicyCreate>): Promise<LinkagePolicy> {
  return request.put(`/v1/linkage/policies/${id}`, data)
}

/**
 * 删除联动策略
 */
export function deleteLinkagePolicy(id: number): Promise<void> {
  return request.delete(`/v1/linkage/policies/${id}`)
}

/**
 * 切换联动策略启用状态
 */
export function toggleLinkagePolicy(id: number): Promise<{ message: string; is_enabled: boolean }> {
  return request.put(`/v1/linkage/policies/${id}/toggle`)
}

/**
 * 测试联动策略
 */
export function testLinkagePolicy(id: number, data?: Record<string, unknown>): Promise<{ message: string; execution_id?: number }> {
  return request.post(`/v1/linkage/policies/${id}/test`, data)
}

/**
 * 获取联动执行记录列表
 */
export function getLinkageExecutions(params?: PageParams & {
  policy_name?: string
  status?: string
  start_time?: string
  end_time?: string
}): Promise<PageResponse<LinkageExecution>> {
  return request.get('/v1/linkage/executions', { params })
}

/**
 * 获取联动执行记录详情
 */
export function getLinkageExecution(id: number): Promise<LinkageExecution> {
  return request.get(`/v1/linkage/executions/${id}`)
}

/**
 * 获取支持的动作类型列表
 */
export function getActionTypes(): Promise<ActionTypeInfo[]> {
  return request.get('/v1/linkage/action-types')
}

/**
 * 重载消防策略（从 YAML 重新加载）
 */
export function reloadFireProtection(): Promise<{ message: string; count: number }> {
  return request.post('/v1/linkage/fire-protection/reload')
}

/**
 * 获取消防策略加载状态
 */
export function getFireProtectionStatus(): Promise<{
  last_sync_time: string | null
  synced_count: number
  yaml_file: string
  yaml_exists: boolean
}> {
  return request.get('/v1/linkage/fire-protection/status')
}
