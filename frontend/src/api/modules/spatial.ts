/**
 * 空间拓扑管理 API
 */
import request from '@/utils/request'
import type { ResponseModel } from './types'

// ==================== 类型定义 ====================

/** 站点 */
export interface Site {
  id: number
  site_code: string
  site_name: string
  address?: string
  description?: string
  created_at: string
  updated_at: string
}

/** 站点创建/更新参数 */
export interface SiteForm {
  site_code: string
  site_name: string
  address?: string
  description?: string
}

/** 楼层 */
export interface Floor {
  id: number
  floor_code: string
  floor_name: string
  site_id: number
  sort_order: number
  created_at: string
  updated_at: string
}

/** 楼层创建/更新参数 */
export interface FloorForm {
  floor_code: string
  floor_name: string
  site_id: number
  sort_order: number
}

/** 房间 */
export interface Room {
  id: number
  room_code: string
  room_name: string
  floor_id: number
  grid_cols: number
  grid_rows: number
  area_sqm?: number
  description?: string
  created_at: string
  updated_at: string
}

/** 房间创建/更新参数 */
export interface RoomForm {
  room_code: string
  room_name: string
  floor_id: number
  grid_cols: number
  grid_rows: number
  area_sqm?: number
  description?: string
}

/** 列 */
export interface Row {
  id: number
  row_code: string
  row_name: string
  room_id: number
  aisle_type: string
  sort_order: number
  created_at: string
  updated_at: string
}

/** 列创建/更新参数 */
export interface RowForm {
  row_code: string
  row_name: string
  room_id: number
  aisle_type: string
  sort_order: number
}

/** 机柜树节点 */
export interface TreeCabinet {
  id: number
  cabinet_code: string
  cabinet_name: string
  grid_x?: number
  grid_y?: number
  aisle_type?: string
}

/** 列树节点 */
export interface TreeRow {
  id: number
  row_code: string
  row_name: string
  aisle_type: string
  cabinets: TreeCabinet[]
}

/** 房间树节点 */
export interface TreeRoom {
  id: number
  room_code: string
  room_name: string
  grid_cols: number
  grid_rows: number
  rows: TreeRow[]
}

/** 楼层树节点 */
export interface TreeFloor {
  id: number
  floor_code: string
  floor_name: string
  rooms: TreeRoom[]
}

/** 空间拓扑树节点 */
export interface SpatialTreeNode {
  id: number
  site_code: string
  site_name: string
  floors: TreeFloor[]
}

/** 布局模板 */
export interface LayoutTemplate {
  id: number
  template_code: string
  template_name: string
  description?: string
}

/** 导入结果 */
export interface ImportResult {
  total: number
  success: number
  failed: number
  skipped: number
  errors: string[]
}

/** 模板应用结果 */
export interface TemplateApplyResult {
  created_rows: number
  created_cabinets: number
  skipped_cabinets: number
  errors: string[]
}

// ==================== 站点 API ====================

/** 获取站点列表 */
export function getSites(keyword?: string) {
  return request.get<ResponseModel<Site[]>>('/v1/spatial/sites', { params: { keyword } })
}

/** 创建站点 */
export function createSite(data: SiteForm) {
  return request.post<ResponseModel<Site>>('/v1/spatial/sites', data)
}

/** 更新站点 */
export function updateSite(id: number, data: Partial<SiteForm>) {
  return request.put<ResponseModel<Site>>(`/v1/spatial/sites/${id}`, data)
}

/** 删除站点 */
export function deleteSite(id: number) {
  return request.delete<ResponseModel>(`/v1/spatial/sites/${id}`)
}

// ==================== 楼层 API ====================

/** 获取楼层列表 */
export function getFloors(site_id?: number) {
  return request.get<ResponseModel<Floor[]>>('/v1/spatial/floors', { params: { site_id } })
}

/** 创建楼层 */
export function createFloor(data: FloorForm) {
  return request.post<ResponseModel<Floor>>('/v1/spatial/floors', data)
}

/** 更新楼层 */
export function updateFloor(id: number, data: Partial<FloorForm>) {
  return request.put<ResponseModel<Floor>>(`/v1/spatial/floors/${id}`, data)
}

/** 删除楼层 */
export function deleteFloor(id: number) {
  return request.delete<ResponseModel>(`/v1/spatial/floors/${id}`)
}

// ==================== 房间 API ====================

/** 获取房间列表 */
export function getRooms(floor_id?: number) {
  return request.get<ResponseModel<Room[]>>('/v1/spatial/rooms', { params: { floor_id } })
}

/** 创建房间 */
export function createRoom(data: RoomForm) {
  return request.post<ResponseModel<Room>>('/v1/spatial/rooms', data)
}

/** 更新房间 */
export function updateRoom(id: number, data: Partial<RoomForm>) {
  return request.put<ResponseModel<Room>>(`/v1/spatial/rooms/${id}`, data)
}

/** 删除房间 */
export function deleteRoom(id: number) {
  return request.delete<ResponseModel>(`/v1/spatial/rooms/${id}`)
}

// ==================== 列 API ====================

/** 获取列列表 */
export function getRows(room_id?: number) {
  return request.get<ResponseModel<Row[]>>('/v1/spatial/rows', { params: { room_id } })
}

/** 创建列 */
export function createRow(data: RowForm) {
  return request.post<ResponseModel<Row>>('/v1/spatial/rows', data)
}

/** 更新列 */
export function updateRow(id: number, data: Partial<RowForm>) {
  return request.put<ResponseModel<Row>>(`/v1/spatial/rows/${id}`, data)
}

/** 删除列 */
export function deleteRow(id: number) {
  return request.delete<ResponseModel>(`/v1/spatial/rows/${id}`)
}

// ==================== 拓扑树 API ====================

/** 获取空间拓扑树 */
export function getSpatialTree() {
  return request.get<ResponseModel<SpatialTreeNode[]>>('/v1/spatial/tree')
}

// ==================== 机柜位置 API ====================

/** 更新机柜位置 */
export function updateCabinetPosition(cabinetId: number, data: { grid_x: number; grid_y: number }) {
  return request.put<ResponseModel>(`/v1/spatial/cabinets/${cabinetId}/position`, data)
}

// ==================== 导入导出 API ====================

/** 导入空间拓扑 Excel */
export function importSpatialExcel(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post<ResponseModel<ImportResult>>('/v1/spatial/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/** 导出空间拓扑 Excel */
export function exportSpatialExcel() {
  return request.get('/v1/spatial/export', { responseType: 'blob' })
}

// ==================== 模板 API ====================

/** 获取布局模板列表 */
export function getTemplates() {
  return request.get<ResponseModel<LayoutTemplate[]>>('/v1/spatial/templates')
}

/** 应用布局模板 */
export function applyTemplate(templateId: number, data: { room_id: number }) {
  return request.post<ResponseModel<TemplateApplyResult>>(`/v1/spatial/templates/${templateId}/apply`, data)
}
