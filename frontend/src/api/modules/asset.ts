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
  row_number: string
  column_number: string
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
  row_number: string
  column_number: string
  total_u: number
  max_power?: number
  max_weight?: number
}

/** 机柜更新参数 */
export interface CabinetUpdate {
  cabinet_name?: string
  location?: string
  row_number?: string
  column_number?: string
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
  specifications?: string
  status: AssetStatus
  cabinet_id?: number
  cabinet_name?: string
  u_position?: number
  u_height?: number
  purchase_date?: string
  purchase_price?: number
  supplier?: string
  warranty_start?: string
  warranty_end?: string
  warranty_status?: string
  maintenance_vendor?: string
  owner?: string
  department?: string
  remark?: string
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
  specifications?: string
  status?: AssetStatus
  cabinet_id?: number
  u_position?: number
  u_height?: number
  purchase_date?: string
  purchase_price?: number
  supplier?: string
  warranty_start?: string
  warranty_end?: string
  maintenance_vendor?: string
  owner?: string
  department?: string
  remark?: string
}

/** 资产更新参数 */
export interface AssetUpdate {
  asset_name?: string
  asset_type?: AssetType
  brand?: string
  model?: string
  serial_number?: string
  specifications?: string
  status?: AssetStatus
  cabinet_id?: number
  u_position?: number
  u_height?: number
  purchase_date?: string
  purchase_price?: number
  supplier?: string
  warranty_start?: string
  warranty_end?: string
  maintenance_vendor?: string
  owner?: string
  department?: string
  remark?: string
}

/** 生命周期记录 */
export interface LifecycleRecord {
  id: number
  asset_id: number
  action: string
  action_date: string
  operator?: string
  from_location?: string
  to_location?: string
  remark?: string
  created_at: string
}

/** 维护记录 */
export interface MaintenanceRecord {
  id: number
  asset_id: number
  maintenance_type: string
  start_time: string
  end_time?: string
  technician?: string
  vendor?: string
  cost?: number
  description?: string
  result?: string
  created_at: string
}

/** 维护记录创建参数 */
export interface MaintenanceCreate {
  asset_id: number
  maintenance_type: string
  start_time: string
  end_time?: string
  technician?: string
  vendor?: string
  cost?: number
  description?: string
}

/** 盘点记录 */
export interface InventoryRecord {
  id: number
  inventory_code: string
  inventory_date: string
  operator?: string
  status: string
  total_count: number
  checked_count: number
  matched_count: number
  unmatched_count: number
  remark?: string
  created_at: string
  completed_at?: string
}

/** 盘点创建参数 */
export interface InventoryCreate {
  inventory_code: string
  inventory_date: string
  operator?: string
  remark?: string
}

/** 资产统计 */
export interface AssetStatistics {
  total_count: number
  by_status: Record<string, number>
  by_type: Record<string, number>
  by_department: Record<string, number>
  total_value: number
  warranty_expiring_count: number
}

/** U位图资产项 */
export interface CabinetAssetItem {
  asset_id: number
  asset_code: string
  asset_name: string
  asset_type: string
  model: string
  brand: string
  status: string
  u_position: number
  u_height: number
}

/** 机柜使用情况 */
export interface CabinetUsage {
  cabinet_id: number
  cabinet_name: string
  total_u: number
  used_u: number
  available_u: number
  usage_rate: number
  u_map: Record<string, { asset_id: number; asset_code: string; asset_name: string; asset_type: string }>
  assets: CabinetAssetItem[]
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
  return request.get<CabinetUsage>(`/v1/asset/cabinets/${cabinetId}/usage`)
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

/** 机柜内移动资产U位 */
export function moveAssetInCabinet(cabinetId: number, data: { asset_id: number; new_u_position: number }) {
  return request.put<ResponseModel>(`/v1/asset/cabinets/${cabinetId}/move-asset`, data)
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

// ==================== 导入导出 API ====================

/** 批量导入资产 */
export function importAssets(file: File, mode: 'preview' | 'confirm' = 'preview') {
  const formData = new FormData()
  formData.append('file', file)
  return request.post<ResponseModel>(`/v1/asset/assets/import?mode=${mode}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/** 导出资产列表 */
export function exportAssets(params?: {
  asset_type?: string
  status?: string
  cabinet_id?: number
  keyword?: string
}) {
  return request.get('/v1/asset/assets/export', {
    params,
    responseType: 'blob'
  })
}

/** 下载导入模板 */
export function downloadImportTemplate() {
  return request.get('/v1/asset/assets/export?template=true', {
    responseType: 'blob'
  })
}

// ==================== 保修预警 API ====================

/** 保修预警项 */
export interface WarrantyAlertItem {
  asset_id: number
  asset_code: string
  asset_name: string
  asset_type: string | null
  warranty_end: string
  days_remaining: number
  status: string | null
}

/** 保修预警汇总 */
export interface WarrantyAlertResponse {
  within_30_days: WarrantyAlertItem[]
  within_60_days: WarrantyAlertItem[]
  within_90_days: WarrantyAlertItem[]
  total_count: number
}

/** 获取保修预警汇总 */
export function getWarrantyAlerts() {
  return request.get<WarrantyAlertResponse>('/v1/asset/warranty-alerts')
}
