/**
 * 智能诊断 API
 */
import request from '@/utils/request'
import type { PageParams, PageResponse } from './types'

// ==================== 类型定义 ====================

/** 诊断原因条目 */
export interface DiagnosisCause {
  cause: string
  confidence: number
  suggested_actions: string[]
  rule_code?: string
}

/** 诊断规则 */
export interface DiagnosisRule {
  id: number
  rule_code: string
  name: string
  description: string | null
  category: string
  trigger_condition: Record<string, unknown> | null
  diagnosis_logic: Record<string, unknown> | null
  priority: number
  is_enabled: boolean
  is_system: boolean
  created_at: string
  updated_at: string
}

/** 创建诊断规则参数 */
export interface DiagnosisRuleCreate {
  rule_code: string
  name: string
  description?: string
  category: string
  trigger_condition: Record<string, unknown>
  diagnosis_logic: Record<string, unknown>
  priority?: number
  is_enabled?: boolean
}

/** 更新诊断规则参数 */
export interface DiagnosisRuleUpdate {
  name?: string
  description?: string
  category?: string
  trigger_condition?: Record<string, unknown>
  diagnosis_logic?: Record<string, unknown>
  priority?: number
  is_enabled?: boolean
}

/** 诊断结果 */
export interface DiagnosisResult {
  id: number
  alarm_id: number | null
  alarm_no: string | null
  rule_id: number | null
  rule_code: string | null
  device_type: string | null
  zone: string | null
  causes: DiagnosisCause[] | null
  diagnosis_time_ms: number
  created_at: string
}

/** 诊断分类 */
export interface DiagnosisCategory {
  code: string
  name: string
  count: number
}

// ==================== API 函数 ====================

/**
 * 获取诊断规则列表
 */
export function getDiagnosisRules(params?: PageParams & {
  category?: string
  is_enabled?: boolean
  is_system?: boolean
}): Promise<PageResponse<DiagnosisRule>> {
  return request.get('/v1/diagnosis/rules', { params })
}

/**
 * 获取诊断规则详情
 */
export function getDiagnosisRule(id: number): Promise<DiagnosisRule> {
  return request.get(`/v1/diagnosis/rules/${id}`)
}

/**
 * 创建诊断规则
 */
export function createDiagnosisRule(data: DiagnosisRuleCreate): Promise<DiagnosisRule> {
  return request.post('/v1/diagnosis/rules', data)
}

/**
 * 更新诊断规则
 */
export function updateDiagnosisRule(id: number, data: DiagnosisRuleUpdate): Promise<DiagnosisRule> {
  return request.put(`/v1/diagnosis/rules/${id}`, data)
}

/**
 * 删除诊断规则
 */
export function deleteDiagnosisRule(id: number): Promise<{ message: string }> {
  return request.delete(`/v1/diagnosis/rules/${id}`)
}

/**
 * 启用/禁用诊断规则
 */
export function toggleDiagnosisRule(id: number): Promise<DiagnosisRule> {
  return request.put(`/v1/diagnosis/rules/${id}/toggle`)
}

/**
 * 重载 YAML 诊断规则
 */
export function reloadDiagnosisRules(): Promise<{ message: string; count: number }> {
  return request.get('/v1/diagnosis/rules/reload')
}

/**
 * 获取诊断结果列表
 */
export function getDiagnosisResults(params?: PageParams & {
  device_type?: string
  zone?: string
  start_time?: string
  end_time?: string
}): Promise<PageResponse<DiagnosisResult>> {
  return request.get('/v1/diagnosis/results', { params })
}

/**
 * 获取诊断结果详情
 */
export function getDiagnosisResult(id: number): Promise<DiagnosisResult> {
  return request.get(`/v1/diagnosis/results/${id}`)
}

/**
 * 按告警ID查询诊断结果
 */
export function getDiagnosisByAlarm(alarmId: number): Promise<DiagnosisResult[]> {
  return request.get(`/v1/diagnosis/results/by-alarm/${alarmId}`)
}

/**
 * 手动触发诊断
 */
export function manualDiagnose(alarmId: number): Promise<{ message: string; alarm_id: number }> {
  return request.post(`/v1/diagnosis/analyze/${alarmId}`)
}

/**
 * 获取诊断分类列表
 */
export function getDiagnosisCategories(): Promise<DiagnosisCategory[]> {
  return request.get('/v1/diagnosis/categories')
}
