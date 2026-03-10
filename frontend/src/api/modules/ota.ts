/**
 * OTA 升级管理 API — Story 15.5
 */
import request from '@/utils/request'
import type { PageParams } from './types'

// ==================== 类型定义 ====================

/** 固件包 */
export interface Firmware {
  id: number
  version: string
  filename: string
  file_size: number
  checksum_sha256: string
  download_url: string
  release_notes?: string
  min_version?: string
  is_active: boolean
  created_at?: string
}

/** 固件包创建参数 */
export interface FirmwareCreate {
  version: string
  filename: string
  file_size: number
  checksum_sha256: string
  download_url: string
  release_notes?: string
  min_version?: string
}

/** OTA 任务策略 */
export type OtaStrategy = 'immediate' | 'batch' | 'canary'

/** OTA 任务创建参数 */
export interface OtaTaskCreate {
  firmware_id: number
  gateway_ids: number[]
  strategy: OtaStrategy
  batch_size?: number
  batch_interval?: number
  canary_percent?: number
}

/** OTA 任务 */
export interface OtaTask {
  id: number
  task_id: string
  firmware_id: number
  target_version: string
  strategy: string
  batch_size: number
  batch_interval: number
  canary_percent: number
  status: string
  total_gateways: number
  success_count: number
  fail_count: number
  created_by?: string
  created_at?: string
  updated_at?: string
}

/** OTA 网关状态 */
export interface OtaGatewayStatus {
  gateway_id: string
  batch_index: number
  status: string
  old_version?: string
  progress: number
  error_message?: string
  started_at?: string
  completed_at?: string
}

/** OTA 任务详情 */
export interface OtaTaskDetail extends OtaTask {
  gateways: OtaGatewayStatus[]
}

// ==================== 固件包 API ====================

/** 获取固件包列表 */
export function getFirmwareList(params?: { is_active?: boolean }) {
  return request.get<Firmware[]>('/v1/ota/firmware', { params })
}

/** 注册固件包 */
export function createFirmware(data: FirmwareCreate) {
  return request.post<Firmware>('/v1/ota/firmware', data)
}

/** 删除固件包 */
export function deleteFirmware(id: number) {
  return request.delete(`/v1/ota/firmware/${id}`)
}

// ==================== OTA 任务 API ====================

/** 获取任务列表 */
export function getOtaTasks(params?: PageParams & { status?: string }) {
  return request.get<{ total: number; items: OtaTask[] }>('/v1/ota/tasks', { params })
}

/** 获取任务详情 */
export function getOtaTaskDetail(taskId: string) {
  return request.get<OtaTaskDetail>(`/v1/ota/tasks/${taskId}`)
}

/** 创建升级任务 */
export function createOtaTask(data: OtaTaskCreate) {
  return request.post<OtaTask>('/v1/ota/tasks', data)
}

/** 启动任务 */
export function startOtaTask(taskId: string) {
  return request.post(`/v1/ota/tasks/${taskId}/start`)
}

/** 取消任务 */
export function cancelOtaTask(taskId: string) {
  return request.post(`/v1/ota/tasks/${taskId}/cancel`)
}

/** 暂停任务 */
export function pauseOtaTask(taskId: string) {
  return request.post(`/v1/ota/tasks/${taskId}/pause`)
}

/** 恢复任务 */
export function resumeOtaTask(taskId: string) {
  return request.post(`/v1/ota/tasks/${taskId}/resume`)
}
