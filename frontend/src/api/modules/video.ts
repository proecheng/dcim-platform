/**
 * 视频监控 API
 * Story 10-1: 摄像头元数据管理
 */
import request from '@/utils/request'
import type { PageParams, PageResponse } from './types'

// ==================== 类型定义 ====================

/** NVR 设备 */
export interface NVRItem {
  id: number
  name: string
  ip_address: string
  port: number
  username: string | null
  password_masked: string | null
  manufacturer: string | null
  model: string | null
  max_channels: number | null
  status: string
  description: string | null
  camera_count: number
  created_at: string | null
  updated_at: string | null
}

/** NVR 创建参数 */
export interface NVRCreateParams {
  name: string
  ip_address: string
  port?: number
  username?: string
  password?: string
  manufacturer?: string
  model?: string
  max_channels?: number
  description?: string
}

/** NVR 更新参数 */
export interface NVRUpdateParams {
  name?: string
  ip_address?: string
  port?: number
  username?: string
  password?: string
  manufacturer?: string
  model?: string
  max_channels?: number
  status?: string
  description?: string
}

/** 摄像头预置位 */
export interface CameraPreset {
  id: number
  camera_id: number
  preset_index: number
  name: string
  description: string | null
}

/** 预置位创建参数 */
export interface CameraPresetCreate {
  preset_index: number
  name: string
  description?: string
}

/** 摄像头 */
export interface CameraItem {
  id: number
  name: string
  code: string
  rtsp_url: string | null
  onvif_url: string | null
  hls_url: string | null
  nvr_id: number | null
  nvr_name: string | null
  channel_no: number | null
  area_code: string | null
  cabinet_id: number | null
  device_id: number | null
  location_description: string | null
  camera_type: string
  status: string
  is_enabled: boolean
  presets: CameraPreset[]
  created_at: string | null
  updated_at: string | null
}

/** 摄像头创建参数 */
export interface CameraCreateParams {
  name: string
  code: string
  rtsp_url?: string
  onvif_url?: string
  hls_url?: string
  nvr_id?: number
  channel_no?: number
  area_code?: string
  cabinet_id?: number
  device_id?: number
  location_description?: string
  camera_type?: string
  presets?: CameraPresetCreate[]
}

/** 摄像头更新参数 */
export interface CameraUpdateParams {
  name?: string
  code?: string
  rtsp_url?: string
  onvif_url?: string
  hls_url?: string
  nvr_id?: number | null
  channel_no?: number | null
  area_code?: string | null
  cabinet_id?: number | null
  device_id?: number | null
  location_description?: string
  camera_type?: string
  status?: string
  is_enabled?: boolean
  presets?: CameraPresetCreate[]
}

// ==================== NVR API ====================

/** 创建 NVR */
export function createNVR(data: NVRCreateParams): Promise<NVRItem> {
  return request.post('/v1/video/nvrs', data)
}

/** NVR 列表 */
export function getNVRList(params?: PageParams): Promise<PageResponse<NVRItem>> {
  return request.get('/v1/video/nvrs', { params })
}

/** NVR 详情 */
export function getNVR(id: number): Promise<NVRItem> {
  return request.get(`/v1/video/nvrs/${id}`)
}

/** 更新 NVR */
export function updateNVR(id: number, data: NVRUpdateParams): Promise<NVRItem> {
  return request.put(`/v1/video/nvrs/${id}`, data)
}

/** 删除 NVR */
export function deleteNVR(id: number): Promise<{ message: string }> {
  return request.delete(`/v1/video/nvrs/${id}`)
}

// ==================== Camera API ====================

/** 创建摄像头 */
export function createCamera(data: CameraCreateParams): Promise<CameraItem> {
  return request.post('/v1/video/cameras', data)
}

/** 摄像头列表 */
export function getCameraList(params?: PageParams & {
  nvr_id?: number
  area_code?: string
  status?: string
}): Promise<PageResponse<CameraItem>> {
  return request.get('/v1/video/cameras', { params })
}

/** 摄像头详情 */
export function getCamera(id: number): Promise<CameraItem> {
  return request.get(`/v1/video/cameras/${id}`)
}

/** 更新摄像头 */
export function updateCamera(id: number, data: CameraUpdateParams): Promise<CameraItem> {
  return request.put(`/v1/video/cameras/${id}`, data)
}

/** 删除摄像头 */
export function deleteCamera(id: number): Promise<{ message: string }> {
  return request.delete(`/v1/video/cameras/${id}`)
}

/** 按区域查询摄像头 */
export function getCamerasByArea(areaCode: string): Promise<CameraItem[]> {
  return request.get(`/v1/video/cameras/by-area/${areaCode}`)
}

/** 按设备查询摄像头 */
export function getCamerasByDevice(deviceId: number): Promise<CameraItem[]> {
  return request.get(`/v1/video/cameras/by-device/${deviceId}`)
}

/** 按告警查询关联摄像头 */
export function getCamerasByAlarm(alarmId: number): Promise<CameraItem[]> {
  return request.get(`/v1/video/cameras/by-alarm/${alarmId}`)
}

// ==================== PTZ / 录像 / 事件 API (Story 10-3) ====================

/** PTZ 控制参数 */
export interface PTZControlParams {
  camera_id: number
  action: string // up/down/left/right/zoom_in/zoom_out/stop
  speed?: number
}

/** 预置位调用参数 */
export interface PresetCallParams {
  camera_id: number
  preset_index: number
}

/** 录像控制参数 */
export interface RecordingParams {
  camera_id: number
  alarm_id?: number
  linkage_execution_id?: number
}

/** 视频事件 */
export interface VideoEventItem {
  id: number
  camera_id: number
  camera_name: string | null
  event_type: string
  trigger_source: string
  alarm_id: number | null
  linkage_execution_id: number | null
  detail: string | null
  operator: string | null
  created_at: string | null
}

/** 云台控制 */
export function ptzControl(data: PTZControlParams): Promise<VideoEventItem> {
  return request.post('/v1/video/ptz/control', data)
}

/** 调用预置位 */
export function callPreset(data: PresetCallParams): Promise<VideoEventItem> {
  return request.post('/v1/video/ptz/preset', data)
}

/** 开始录像 */
export function startRecording(data: RecordingParams): Promise<VideoEventItem> {
  return request.post('/v1/video/recording/start', data)
}

/** 停止录像 */
export function stopRecording(data: RecordingParams): Promise<VideoEventItem> {
  return request.post('/v1/video/recording/stop', data)
}

/** 视频事件列表 */
export function getVideoEvents(params?: PageParams & {
  camera_id?: number
  event_type?: string
}): Promise<PageResponse<VideoEventItem>> {
  return request.get('/v1/video/events', { params })
}

// ==================== 回放 API (Story 10-4) ====================

/** 告警摘要 */
export interface AlarmBrief {
  id: number
  alarm_level: string
  alarm_message: string
  alarm_time: string | null
}

/** 摄像头摘要（回放用） */
export interface CameraBrief {
  id: number
  name: string
  code: string
  rtsp_url: string | null
  hls_url: string | null
  location_description: string | null
}

/** 录像片段 */
export interface RecordingSegment {
  id: number
  camera_id: number
  camera_name: string | null
  start_time: string | null
  end_time: string | null
  alarm_id: number | null
  duration_seconds: number | null
}

/** 告警回放信息 */
export interface PlaybackInfo {
  alarm_info: AlarmBrief
  cameras: CameraBrief[]
  recording_events: VideoEventItem[]
  playback_url_template: string
}

/** 获取告警回放信息 */
export function getPlaybackInfo(alarmId: number): Promise<PlaybackInfo> {
  return request.get(`/v1/video/playback/alarm/${alarmId}`)
}

/** 查询录像片段列表 */
export function getRecordingSegments(params: PageParams & {
  camera_id: number
  start_time?: string
  end_time?: string
}): Promise<PageResponse<RecordingSegment>> {
  return request.get('/v1/video/playback/segments', { params })
}
