/**
 * 资产管理 API
 */
import request from '@/utils/request'
import type { ResponseModel, PageParams } from './types'

// ==================== 类型定义 ====================

/** 资产状态 */
export type AssetStatus = 'in_stock' | 'in_use' | 'borrowed' | 'maintenance' | 'scrapped'

/** 资产类型 */
export type AssetType = 'server' | 'network' | 'storage' | 'ups' | 'pdu' | 'ac' | 'cabinet' | 'sensor' | 'other'

/** 机柜信息 */
export interface Cabinet {
  id: number
  cabinet_code: string
  cabinet_name: string
  location: string
  row_number: number
  column_number: number
  total_u: number
  max_power: number
  max_weight: number
  used_u: number
  available_u: number
  created_at: string
  updated_at: string
}

/** 机柜创建参数 */
export interface CabinetCreate {
  cabinet_code: string
  cabinet_name: string
  location: string
  row_number: number
  column_number: number
  total_u: number
  max_power?: number
  max_weight?: number
}

/** 机柜更新参数 */
export interface CabinetUpdate {
  cabinet_name?: string
  location?: string
  row_number?: number
  column_number?: number
  total_u?: number
  max_power?: number
  max_weight?: number
}

/** 资产信息 */
export interface Asset {
  id: number
  asset_code: string
  asset_name: string
  asset_type: AssetType
  brand: string
  model: string
  serial_number: string
  status: AssetStatus
  cabinet_id?: number
  cabinet_name?: string
  start_u?: number
  end_u?: number
  purchase_date?: string
  warranty_date?: string
  warranty_status?: string
  purchase_price?: number
  supplier?: string
  responsible_person?: string
  department?: string
  description?: string
  created_at: string
  updated_at: string
}

/** 资产创建参数 */
export interface AssetCreate {
  asset_code: string
  asset_name: string
  asset_type: AssetType
  brand?: string
  model?: string
  serial_number?: string
  status?: AssetStatus
  cabinet_id?: number
  start_u?: number
  end_u?: number
  purchase_date?: string
  warranty_date?: string
  purchase_price?: number
  supplier?: string
  responsible_person?: string
  department?: string
  description?: string
}

/** 资产更新参数 */
export interface AssetUpdate {
  asset_name?: string
  asset_type?: AssetType
  brand?: string
  model?: string
  serial_number?: string
  status?: AssetStatus
  cabinet_id?: number
  start_u?: number
  end_u?: number
  purchase_date?: string
  warranty_date?: string
  purchase_price?: number
  supplier?: string
  responsible_person?: string
  department?: string
  description?: string
}

/** 生命周期记录 */
export interface LifecycleRecord {
  id: number
  asset_id: number
  event_type: string
  event_description: string
  operator?: string
  event_time: string
  created_at: string
}

/** 维护记录 */
export interface MaintenanceRecord {
  id: number
  asset_id: number
  asset_code?: string
  asset_name?: string
  maintenance_type: string
  maintenance_description: string
  maintenance_date: string
  maintenance_person?: string
  maintenance_cost?: number
  status: string
  result?: string
  completed_at?: string
  created_at: string
  updated_at: string
}

/** 维护记录创建参数 */
export interface MaintenanceCreate {
  asset_id: number
  maintenance_type: string
  maintenance_description: string
  maintenance_date: string
  maintenance_person?: string
  maintenance_cost?: number
}

/** 盘点记录 */
export interface InventoryRecord {
  id: number
  inventory_no: string
  inventory_name: string
  inventory_type: string
  status: string
  start_time?: string
  end_time?: string
  operator?: string
  total_count: number
  checked_count: number
  normal_count: number
  abnormal_count: number
  missing_count: number
  remark?: string
  created_at: string
  updated_at: string
}

/** 盘点创建参数 */
export interface InventoryCreate {
  inventory_name: string
  inventory_type: string
  remark?: string
}

/** 资产统计 */
export interface AssetStatistics {
  total_count: number
  by_status: Record<AssetStatus, number>
  by_type: Record<AssetType, number>
  total_value: number
  warranty_expiring_count: number
  maintenance_count: number
}

/** 机柜使用情况 */
export interface CabinetUsage {
  cabinet_id: number
  cabinet_code: string
  cabinet_name: string
  total_u: number
  used_u: number
  available_u: number
  usage_rate: number
  max_power: number
  current_power?: number
  power_usage_rate?: number
  max_weight: number
  current_weight?: number
  weight_usage_rate?: number
  assets: Asset[]
}

// ==================== 机柜 API ====================

/** 获取机柜列表 */
export function getCabinets(params?: PageParams & {
  location?: string
  keyword?: string
}) {
  return request.get<ResponseModel<Cabinet[]>>('/v1/asset/cabinets', { params })
}

/** 获取机柜详情 */
export function getCabinet(cabinetId: number) {
  return request.get<ResponseModel<Cabinet>>(`/v1/asset/cabinets/${cabinetId}`)
}

/** 获取机柜使用情况 */
export function getCabinetUsage(cabinetId: number) {
  return request.get<{ code: number; data: CabinetUsage }>(`/v1/asset/cabinets/${cabinetId}/usage`)
}

/** 创建机柜 */
export function createCabinet(data: CabinetCreate) {
  return request.post<ResponseModel<Cabinet>>('/v1/asset/cabinets', data)
}

/** 更新机柜 */
export function updateCabinet(cabinetId: number, data: CabinetUpdate) {
  return request.put<ResponseModel<Cabinet>>(`/v1/asset/cabinets/${cabinetId}`, data)
}

/** 删除机柜 */
export function deleteCabinet(cabinetId: number) {
  return request.delete<ResponseModel>(`/v1/asset/cabinets/${cabinetId}`)
}

// ==================== 资产 API ====================

/** 获取资产列表 */
export function getAssets(params?: PageParams & {
  asset_type?: AssetType
  status?: AssetStatus
  cabinet_id?: number
  keyword?: string
}) {
  return request.get<ResponseModel<Asset[]>>('/v1/asset/assets', { params })
}

/** 获取资产详情 */
export function getAsset(assetId: number) {
  return request.get<ResponseModel<Asset>>(`/v1/asset/assets/${assetId}`)
}

/** 创建资产 */
export function createAsset(data: AssetCreate) {
  return request.post<ResponseModel<Asset>>('/v1/asset/assets', data)
}

/** 更新资产 */
export function updateAsset(assetId: number, data: AssetUpdate) {
  return request.put<ResponseModel<Asset>>(`/v1/asset/assets/${assetId}`, data)
}

/** 删除资产 */
export function deleteAsset(assetId: number) {
  return request.delete<ResponseModel>(`/v1/asset/assets/${assetId}`)
}

/** 获取资产生命周期记录 */
export function getAssetLifecycle(assetId: number) {
  return request.get<ResponseModel<LifecycleRecord[]>>(`/v1/asset/assets/${assetId}/lifecycle`)
}

// ==================== 维护 API ====================

/** 创建维护记录 */
export function createMaintenance(data: MaintenanceCreate) {
  return request.post<ResponseModel<MaintenanceRecord>>('/v1/asset/maintenance', data)
}

/** 完成维护 */
export function completeMaintenance(recordId: number, result?: string) {
  return request.put<ResponseModel<MaintenanceRecord>>(`/v1/asset/maintenance/${recordId}/complete`, { result })
}

/** 获取维护记录列表 */
export function getMaintenanceRecords(params?: PageParams & {
  asset_id?: number
  maintenance_type?: string
  status?: string
}) {
  return request.get<ResponseModel<MaintenanceRecord[]>>('/v1/asset/maintenance', { params })
}

// ==================== 盘点 API ====================

/** 创建盘点任务 */
export function createInventory(data: InventoryCreate) {
  return request.post<ResponseModel<InventoryRecord>>('/v1/asset/inventory', data)
}

/** 获取盘点记录列表 */
export function getInventoryList(params?: PageParams & {
  status?: string
  inventory_type?: string
}) {
  return request.get<ResponseModel<InventoryRecord[]>>('/v1/asset/inventory', { params })
}

/** 获取盘点明细 */
export function getInventoryItems(inventoryId: number) {
  return request.get<{ code: number; data: any[] }>(`/v1/asset/inventory/${inventoryId}/items`)
}

/** 更新盘点明细 */
export function updateInventoryItem(itemId: number, data: {
  check_status?: string
  check_result?: string
  remark?: string
}) {
  return request.put<ResponseModel>(`/v1/asset/inventory/items/${itemId}`, data)
}

// ==================== 统计 API ====================

/** 获取资产统计 */
export function getAssetStatistics() {
  return request.get<ResponseModel<AssetStatistics>>('/v1/asset/statistics')
}

/** 获取即将过保资产 */
export function getWarrantyExpiringAssets(days?: number) {
  return request.get<ResponseModel<Asset[]>>('/v1/asset/warranty-expiring', { params: { days } })
}
