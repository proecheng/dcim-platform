/**
 * 控制命令分级确认 API
 * Story 9-6: 控制命令分级确认
 */
import request from '@/utils/request'
import type { PageParams, PageResponse } from './types'

// ==================== 类型定义 ====================

/** 命令提交请求 */
export interface CommandSubmitRequest {
  command_type: string
  target_device_id: number
  target_device_name: string
  command_content: Record<string, unknown>
}

/** 命令提交响应 */
export interface CommandSubmitResponse {
  status: string // executed / pending_approval
  message: string
  approval_id?: number
  audit_log_id?: number
}

/** 审批工单 */
export interface CommandApproval {
  id: number
  command_type: string
  risk_level: string
  target_device_id: number
  target_device_name: string
  command_content: Record<string, unknown> | null
  requester_id: number
  requester_name: string
  approver_id: number | null
  approver_name: string | null
  status: string
  reject_reason: string | null
  timeout_minutes: number
  created_at: string
  approved_at: string | null
  executed_at: string | null
  expired_at: string
}

/** 审计日志 */
export interface CommandAuditLog {
  id: number
  command_type: string
  risk_level: string
  target_device_id: number
  target_device_name: string
  command_content: Record<string, unknown> | null
  operator_id: number
  operator_name: string
  approval_id: number | null
  result: string
  result_message: string | null
  created_at: string
}

/** 风险配置项 */
export interface RiskConfigItem {
  command_type: string
  risk_level: 'normal' | 'critical'
  minimum_risk: 'normal' | 'critical'
  description?: string
}

// ==================== API 函数 ====================

/**
 * 提交控制命令
 */
export function submitCommand(data: CommandSubmitRequest): Promise<CommandSubmitResponse> {
  return request.post('/v1/command/submit', data)
}

/**
 * 获取审批工单列表
 */
export function getCommandApprovals(params?: PageParams & {
  status?: string
  requester_name?: string
}): Promise<PageResponse<CommandApproval>> {
  return request.get('/v1/command/approvals', { params })
}

/**
 * 获取审批工单详情
 */
export function getCommandApproval(id: number): Promise<CommandApproval> {
  return request.get(`/v1/command/approvals/${id}`)
}

/**
 * 批准审批
 */
export function approveCommand(id: number): Promise<CommandApproval> {
  return request.post(`/v1/command/approvals/${id}/approve`)
}

/**
 * 驳回审批
 */
export function rejectCommand(id: number, reason: string): Promise<CommandApproval> {
  return request.post(`/v1/command/approvals/${id}/reject`, { reason })
}

/**
 * 获取审计日志列表
 */
export function getCommandAuditLogs(params?: PageParams & {
  command_type?: string
  operator_name?: string
  result?: string
}): Promise<PageResponse<CommandAuditLog>> {
  return request.get('/v1/command/audit-logs', { params })
}

/**
 * 获取风险等级配置
 */
export function getRiskConfigs(): Promise<RiskConfigItem[]> {
  return request.get('/v1/command/risk-configs')
}

/**
 * 更新风险等级配置
 */
export function updateRiskConfigs(configs: RiskConfigItem[]): Promise<{ message: string; updated: number }> {
  return request.put('/v1/command/risk-configs', { configs })
}
