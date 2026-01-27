/**
 * 通用类型定义
 */

/**
 * 分页参数
 */
export interface PageParams {
  page?: number
  page_size?: number
}

/**
 * 分页响应
 */
export interface PageResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

/**
 * 通用响应
 */
export interface ResponseModel<T = any> {
  code: number
  message: string
  data: T
}

/**
 * 时间范围参数
 */
export interface TimeRangeParams {
  start_time?: string
  end_time?: string
}

/**
 * 导出参数
 */
export interface ExportParams extends TimeRangeParams {
  format?: 'excel' | 'csv' | 'pdf' | 'json'
  columns?: string[]
}
