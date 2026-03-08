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

// ==================== 标注管理 (Story 24.8) ====================

/** 诊断标注 */
export interface DiagnosisAnnotation {
  id: number
  session_id: number
  annotator_id: number | null
  annotation: 'accurate' | 'inaccurate' | 'unknown'
  actual_root_cause: string | null
  notes: string | null
  annotated_at: string
  created_at: string
  updated_at: string
}

/** 创建标注参数 */
export interface DiagnosisAnnotationCreate {
  session_id: number
  annotation: 'accurate' | 'inaccurate' | 'unknown'
  actual_root_cause?: string
  notes?: string
}

/** 标注统计 */
export interface DiagnosisAnnotationStats {
  total_annotations: number
  accurate_count: number
  inaccurate_count: number
  unknown_count: number
  accurate_rate: number
  user_stats: Array<{
    user_id: number
    username: string
    annotation_count: number
  }>
  top_annotators: Array<{
    user_id: number
    username: string
    annotation_count: number
  }>
}

/**
 * 创建诊断标注
 */
export function createDiagnosisAnnotation(data: DiagnosisAnnotationCreate): Promise<DiagnosisAnnotation> {
  return request.post('/v1/diagnosis/annotations', data)
}

/**
 * 获取标注列表
 */
export function getDiagnosisAnnotations(params?: PageParams & {
  session_id?: number
  annotator_id?: number
  annotation?: string
}): Promise<PageResponse<DiagnosisAnnotation>> {
  return request.get('/v1/diagnosis/annotations', { params })
}

/**
 * 删除标注
 */
export function deleteDiagnosisAnnotation(id: number): Promise<{ message: string }> {
  return request.delete(`/v1/diagnosis/annotations/${id}`)
}

/**
 * 获取标注统计
 */
export function getDiagnosisAnnotationStats(topN?: number): Promise<DiagnosisAnnotationStats> {
  return request.get('/v1/diagnosis/annotations/stats', {
    params: { top_n: topN || 10 }
  })
}

// ==================== 反事实分析 (Story 26.1) ====================

/** 反事实场景 */
export interface CounterfactualScenario {
  removed_evidence_id: number
  new_root_cause: string | null
  new_confidence: number
  confidence_change: number
  conclusion_changed: boolean
}

/** 反事实分析结果 */
export interface CounterfactualAnalysis {
  id: number
  session_id: number
  original_root_cause: string | null
  original_confidence: number
  top_evidences: Array<{
    node_id: number
    evidence_type: string
    probability: number
    sensor_weight: number
    path_length: number
  }>
  analysis_results: CounterfactualScenario[]
  analysis_time_ms: number
  fault_tree_version: string | null
  config_version: string
  created_at: string
}

/**
 * 获取反事实分析结果
 */
export function getCounterfactualAnalysis(sessionId: number): Promise<CounterfactualAnalysis> {
  return request.get(`/v1/diagnosis/counterfactual/${sessionId}`)
}

/**
 * 获取反事实分析列表
 */
export function getCounterfactualAnalysisList(params?: PageParams & {
  min_confidence?: number
  start_date?: string
  end_date?: string
}): Promise<PageResponse<CounterfactualAnalysis>> {
  return request.get('/v1/diagnosis/counterfactual', { params })
}

// ==================== 误诊反馈报告 (Story 26.2) ====================

/** 系统报告 */
export interface SystemReport {
  id: number
  report_type: string
  report_period: string
  report_version: string
  content: string
  summary: Record<string, unknown> | null
  generated_at: string
  generated_by: string | null
  deleted_at: string | null
  updated_at: string
}

/** 报告摘要 */
export interface ReportSummary {
  total_sessions: number
  annotated_count: number
  annotation_coverage: number
  false_positive_count: number
  false_negative_count: number
  accuracy_rate: number | null
}

/**
 * 获取误诊报告列表
 */
export function getMisdiagnosisReports(params?: PageParams & {
  start_period?: string
  end_period?: string
}): Promise<PageResponse<SystemReport>> {
  return request.get('/v1/diagnosis/reports/misdiagnosis', { params })
}

/**
 * 获取误诊报告详情
 */
export function getMisdiagnosisReport(reportId: number): Promise<SystemReport> {
  return request.get(`/v1/diagnosis/reports/misdiagnosis/${reportId}`)
}

/**
 * 手动生成误诊报告
 */
export function generateMisdiagnosisReport(period: string): Promise<{
  report_id: number
  message: string
}> {
  return request.post('/v1/diagnosis/reports/misdiagnosis/generate', null, {
    params: { period }
  })
}

/**
 * 导出误诊报告为 PDF
 */
export function exportMisdiagnosisReport(reportId: number): Promise<Blob> {
  return request.get(`/v1/diagnosis/reports/misdiagnosis/${reportId}/export`, {
    responseType: 'blob'
  })
}

// ==================== 时间窗口调参 API ====================

/** 时间窗口调整记录 */
export interface TimeWindowAdjustment {
  id: number
  device_type: string
  current_window_minutes: number
  proposed_window_minutes: number
  adjustment_percent: number
  sample_count: number
  p50_duration_seconds: number
  p90_duration_seconds: number
  status: string
  reason?: string
  approved_by?: number
  approved_at?: string
  created_at: string
  updated_at: string
}

/** 时间窗口调整查询参数 */
export interface TimeWindowAdjustmentQuery extends PageParams {
  device_type?: string
  status?: string
}

/** 审批/拒绝参数 */
export interface TimeWindowApprovalRequest {
  reason?: string
}

/**
 * 获取时间窗口调整记录列表
 */
export function getTimeWindowAdjustments(
  params: TimeWindowAdjustmentQuery
): Promise<PageResponse<TimeWindowAdjustment>> {
  return request.get('/v1/diagnosis/time-window-tuning/adjustments', { params })
}

/**
 * 触发时间窗口调参分析
 */
export function triggerTimeWindowAnalysis(): Promise<{
  analyzed_device_types: number
  total_adjustments: number
  pending_approvals: number
}> {
  return request.post('/v1/diagnosis/time-window-tuning/analyze')
}

/**
 * 审批时间窗口调整
 */
export function approveTimeWindowAdjustment(
  adjustmentId: number,
  data: TimeWindowApprovalRequest
): Promise<{
  message: string
  device_type: string
  new_window_minutes: number
}> {
  return request.post(`/v1/diagnosis/time-window-tuning/adjustments/${adjustmentId}/approve`, data)
}

/**
 * 拒绝时间窗口调整
 */
export function rejectTimeWindowAdjustment(
  adjustmentId: number,
  data: TimeWindowApprovalRequest
): Promise<{
  message: string
}> {
  return request.post(`/v1/diagnosis/time-window-tuning/adjustments/${adjustmentId}/reject`, data)
}
