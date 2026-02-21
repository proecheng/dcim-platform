/**
 * 网关管理 API
 */
import request from '@/utils/request'
import type { PageParams, PageResponse } from './types'

/** 网关信息 */
export interface GatewayInfo {
  id: number
  gateway_id: string
  name: string
  ip_address: string | null
  version: string | null
  status: 'online' | 'offline'
  capabilities: Record<string, unknown> | null
  cpu_usage: number | null
  memory_usage: number | null
  disk_usage: number | null
  last_heartbeat: string | null
  site_id: number | null
  is_enabled: boolean
  created_at: string | null
  updated_at: string | null
}

/** 网关状态汇总 */
export interface GatewaySummary {
  total: number
  online: number
  offline: number
}

/** 网关详情（含关联统计） */
export interface GatewayDetail extends GatewayInfo {
  datasource_count: number
  point_count: number
}

/** 网关事件 */
export interface GatewayEvent {
  id: number
  gateway_id: string
  event_type: string
  old_status: string | null
  new_status: string | null
  detail: Record<string, unknown> | null
  created_at: string | null
}

/** 获取网关列表 */
export function getGatewayList(params?: PageParams & {
  status?: string
  is_enabled?: boolean
  site_id?: number
  keyword?: string
}): Promise<PageResponse<GatewayInfo>> {
  return request.get('/v1/gateways', { params })
}

/** 获取网关状态汇总 */
export function getGatewaySummary(params?: {
  site_id?: number
}): Promise<GatewaySummary> {
  return request.get('/v1/gateways/summary', { params })
}

/** 获取网关详情 */
export function getGatewayDetail(id: number): Promise<GatewayDetail> {
  return request.get(`/v1/gateways/${id}`)
}

/** 配置下发响应 */
export interface ConfigPushResponse {
  id: number
  gateway_id: string
  status: 'pending' | 'delivered' | 'failed'
  error_message: string | null
  created_at: string | null
}

/** 配置下发历史记录 */
export interface ConfigPushRecord {
  id: number
  gateway_id: string
  config_snapshot: Record<string, unknown>
  status: string
  error_message: string | null
  created_at: string | null
  updated_at: string | null
}

/** 获取网关事件历史 */
export function getGatewayEvents(id: number, params?: PageParams & {
  event_type?: string
}): Promise<PageResponse<GatewayEvent>> {
  return request.get(`/v1/gateways/${id}/events`, { params })
}

/** 下发配置到网关 */
export function pushGatewayConfig(id: number): Promise<ConfigPushResponse> {
  return request.post(`/v1/gateways/${id}/push-config`)
}

/** 获取配置下发历史 */
export function getConfigHistory(id: number, params?: PageParams): Promise<PageResponse<ConfigPushRecord>> {
  return request.get(`/v1/gateways/${id}/config-history`, { params })
}
