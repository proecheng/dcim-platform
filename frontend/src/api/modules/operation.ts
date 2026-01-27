/**
 * 运维管理 API
 */
import request from '@/utils/request'
import type { ResponseModel, PageParams } from './types'

// ==================== 类型定义 ====================

/** 工单状态 */
export type WorkOrderStatus = 'pending' | 'assigned' | 'processing' | 'completed' | 'closed' | 'cancelled'

/** 工单类型 */
export type WorkOrderType = 'fault' | 'maintenance' | 'inspection' | 'change' | 'other'

/** 工单优先级 */
export type WorkOrderPriority = 'critical' | 'high' | 'medium' | 'low'

/** 巡检状态 */
export type InspectionStatus = 'pending' | 'in_progress' | 'completed' | 'overdue'

/** 工单信息 */
export interface WorkOrder {
  id: number
  order_no: string
  title: string
  description?: string
  order_type: WorkOrderType
  priority: WorkOrderPriority
  status: WorkOrderStatus
  device_id?: number
  device_name?: string
  location?: string
  reporter?: string
  reporter_phone?: string
  assignee?: string
  deadline?: string
  created_at: string
  assigned_at?: string
  started_at?: string
  completed_at?: string
  solution?: string
  root_cause?: string
}

/** 工单创建参数 */
export interface WorkOrderCreate {
  title: string
  description?: string
  order_type: WorkOrderType
  priority: WorkOrderPriority
  device_id?: number
  location?: string
  reporter?: string
  reporter_phone?: string
  deadline?: string
}

/** 工单更新参数 */
export interface WorkOrderUpdate {
  title?: string
  description?: string
  order_type?: WorkOrderType
  priority?: WorkOrderPriority
  device_id?: number
  location?: string
  reporter?: string
  reporter_phone?: string
  deadline?: string
}

/** 工单日志 */
export interface WorkOrderLog {
  id: number
  work_order_id: number
  action: string
  content: string
  operator?: string
  created_at: string
}

/** 巡检计划 */
export interface InspectionPlan {
  id: number
  plan_name: string
  description?: string
  plan_type: string
  frequency: string
  start_date: string
  end_date?: string
  devices?: number[]
  locations?: string[]
  inspector?: string
  checklist?: string[]
  is_active: boolean
  created_at: string
  updated_at: string
}

/** 巡检计划创建参数 */
export interface InspectionPlanCreate {
  plan_name: string
  description?: string
  plan_type: string
  frequency: string
  start_date: string
  end_date?: string
  devices?: number[]
  locations?: string[]
  inspector?: string
  checklist?: string[]
  is_active?: boolean
}

/** 巡检任务 */
export interface InspectionTask {
  id: number
  plan_id: number
  plan_name?: string
  task_no: string
  status: InspectionStatus
  inspector?: string
  scheduled_time: string
  started_at?: string
  completed_at?: string
  devices?: number[]
  locations?: string[]
  checklist?: string[]
  results?: Record<string, any>
  remarks?: string
  created_at: string
}

/** 巡检任务创建参数 */
export interface InspectionTaskCreate {
  plan_id: number
  inspector?: string
  scheduled_time: string
  devices?: number[]
  locations?: string[]
  checklist?: string[]
}

/** 知识库 */
export interface Knowledge {
  id: number
  title: string
  category: string
  content: string
  keywords?: string[]
  author?: string
  views: number
  likes: number
  is_published: boolean
  created_at: string
  updated_at: string
}

/** 知识库创建参数 */
export interface KnowledgeCreate {
  title: string
  category: string
  content: string
  keywords?: string[]
  author?: string
  is_published?: boolean
}

/** 运维统计 */
export interface OperationStatistics {
  total_workorders: number
  pending_workorders: number
  processing_workorders: number
  completed_workorders: number
  overdue_workorders: number
  total_inspections: number
  pending_inspections: number
  completed_inspections: number
  overdue_inspections: number
  total_knowledge: number
  workorder_completion_rate: number
  inspection_completion_rate: number
  average_resolution_time: number
}

// ==================== 工单管理 API ====================

/** 获取工单列表 */
export function getWorkOrders(params?: PageParams & {
  status?: WorkOrderStatus
  priority?: WorkOrderPriority
  order_type?: WorkOrderType
  keyword?: string
}) {
  return request.get<ResponseModel<WorkOrder[]>>('/v1/operation/workorders', { params })
}

/** 获取工单详情 */
export function getWorkOrder(id: number) {
  return request.get<ResponseModel<WorkOrder>>(`/v1/operation/workorders/${id}`)
}

/** 创建工单 */
export function createWorkOrder(data: WorkOrderCreate) {
  return request.post<ResponseModel<WorkOrder>>('/v1/operation/workorders', data)
}

/** 更新工单 */
export function updateWorkOrder(id: number, data: WorkOrderUpdate) {
  return request.put<ResponseModel<WorkOrder>>(`/v1/operation/workorders/${id}`, data)
}

/** 删除工单 */
export function deleteWorkOrder(id: number) {
  return request.delete<ResponseModel>(`/v1/operation/workorders/${id}`)
}

/** 分配工单 */
export function assignWorkOrder(id: number, assignee: string) {
  return request.post<ResponseModel<WorkOrder>>(`/v1/operation/workorders/${id}/assign`, { assignee })
}

/** 开始处理工单 */
export function startWorkOrder(id: number) {
  return request.post<ResponseModel<WorkOrder>>(`/v1/operation/workorders/${id}/start`)
}

/** 完成工单 */
export function completeWorkOrder(id: number, solution: string, root_cause?: string) {
  return request.post<ResponseModel<WorkOrder>>(`/v1/operation/workorders/${id}/complete`, { solution, root_cause })
}

/** 获取工单日志 */
export function getWorkOrderLogs(id: number) {
  return request.get<ResponseModel<WorkOrderLog[]>>(`/v1/operation/workorders/${id}/logs`)
}

/** 添加工单日志 */
export function addWorkOrderLog(id: number, action: string, content: string, operator?: string) {
  return request.post<ResponseModel<WorkOrderLog>>(`/v1/operation/workorders/${id}/logs`, { action, content, operator })
}

// ==================== 巡检计划 API ====================

/** 获取巡检计划列表 */
export function getInspectionPlans(params?: PageParams & {
  plan_type?: string
  is_active?: boolean
  keyword?: string
}) {
  return request.get<ResponseModel<InspectionPlan[]>>('/v1/operation/inspection-plans', { params })
}

/** 获取巡检计划详情 */
export function getInspectionPlan(id: number) {
  return request.get<ResponseModel<InspectionPlan>>(`/v1/operation/inspection-plans/${id}`)
}

/** 创建巡检计划 */
export function createInspectionPlan(data: InspectionPlanCreate) {
  return request.post<ResponseModel<InspectionPlan>>('/v1/operation/inspection-plans', data)
}

/** 更新巡检计划 */
export function updateInspectionPlan(id: number, data: Partial<InspectionPlanCreate>) {
  return request.put<ResponseModel<InspectionPlan>>(`/v1/operation/inspection-plans/${id}`, data)
}

/** 删除巡检计划 */
export function deleteInspectionPlan(id: number) {
  return request.delete<ResponseModel>(`/v1/operation/inspection-plans/${id}`)
}

// ==================== 巡检任务 API ====================

/** 获取巡检任务列表 */
export function getInspectionTasks(params?: PageParams & {
  plan_id?: number
  status?: InspectionStatus
  inspector?: string
  keyword?: string
}) {
  return request.get<ResponseModel<InspectionTask[]>>('/v1/operation/inspection-tasks', { params })
}

/** 获取巡检任务详情 */
export function getInspectionTask(id: number) {
  return request.get<ResponseModel<InspectionTask>>(`/v1/operation/inspection-tasks/${id}`)
}

/** 创建巡检任务 */
export function createInspectionTask(data: InspectionTaskCreate) {
  return request.post<ResponseModel<InspectionTask>>('/v1/operation/inspection-tasks', data)
}

/** 更新巡检任务 */
export function updateInspectionTask(id: number, data: Partial<InspectionTaskCreate>) {
  return request.put<ResponseModel<InspectionTask>>(`/v1/operation/inspection-tasks/${id}`, data)
}

/** 删除巡检任务 */
export function deleteInspectionTask(id: number) {
  return request.delete<ResponseModel>(`/v1/operation/inspection-tasks/${id}`)
}

/** 开始巡检任务 */
export function startInspectionTask(id: number) {
  return request.post<ResponseModel<InspectionTask>>(`/v1/operation/inspection-tasks/${id}/start`)
}

/** 完成巡检任务 */
export function completeInspectionTask(id: number, results: Record<string, any>, remarks?: string) {
  return request.post<ResponseModel<InspectionTask>>(`/v1/operation/inspection-tasks/${id}/complete`, { results, remarks })
}

// ==================== 知识库 API ====================

/** 获取知识库列表 */
export function getKnowledgeList(params?: PageParams & {
  category?: string
  is_published?: boolean
  keyword?: string
}) {
  return request.get<ResponseModel<Knowledge[]>>('/v1/operation/knowledge', { params })
}

/** 获取知识库详情 */
export function getKnowledge(id: number) {
  return request.get<ResponseModel<Knowledge>>(`/v1/operation/knowledge/${id}`)
}

/** 创建知识库 */
export function createKnowledge(data: KnowledgeCreate) {
  return request.post<ResponseModel<Knowledge>>('/v1/operation/knowledge', data)
}

/** 更新知识库 */
export function updateKnowledge(id: number, data: Partial<KnowledgeCreate>) {
  return request.put<ResponseModel<Knowledge>>(`/v1/operation/knowledge/${id}`, data)
}

/** 删除知识库 */
export function deleteKnowledge(id: number) {
  return request.delete<ResponseModel>(`/v1/operation/knowledge/${id}`)
}

// ==================== 统计 API ====================

/** 获取运维统计 */
export function getOperationStatistics() {
  return request.get<ResponseModel<OperationStatistics>>('/v1/operation/statistics')
}
