/**
 * 系统配置 API
 */
import request from '@/utils/request'

export interface SystemConfig {
  id: number
  config_group: string
  config_key: string
  config_value: string
  value_type: 'string' | 'number' | 'boolean' | 'json'
  description: string
  is_editable: boolean
  updated_at: string
}

export interface SystemConfigUpdate {
  config_group: string
  config_key: string
  config_value: string
}

export interface Dictionary {
  id: number
  dict_type: string
  dict_code: string
  dict_name: string
  dict_value: string
  sort_order: number
  is_enabled: boolean
}

export interface LicenseInfo {
  id: number
  license_key: string
  license_type: 'basic' | 'standard' | 'enterprise' | 'unlimited'
  max_points: number
  features: string[]
  issue_date: string
  expire_date: string
  is_active: boolean
  activated_at: string
  status: 'active' | 'expired' | 'invalid'
  used_points: number
}

export interface LicenseActivateParams {
  license_key: string
  hardware_id?: string
}

/**
 * 获取系统配置
 */
export function getSystemConfigs(params?: {
  config_group?: string
}): Promise<SystemConfig[]> {
  return request.get('/v1/configs', { params })
}

/**
 * 更新系统配置
 */
export function updateSystemConfigs(data: SystemConfigUpdate[]): Promise<void> {
  return request.put('/v1/configs', data)
}

/**
 * 获取单个配置
 */
export function getSystemConfig(group: string, key: string): Promise<SystemConfig> {
  return request.get(`/v1/configs/${group}/${key}`)
}

/**
 * 获取数据字典
 */
export function getDictionaries(params?: {
  dict_type?: string
}): Promise<Dictionary[]> {
  return request.get('/v1/configs/dictionaries', { params })
}

/**
 * 获取字典选项（按类型）
 */
export function getDictionaryOptions(dictType: string): Promise<Dictionary[]> {
  return request.get(`/v1/configs/dictionaries/${dictType}`)
}

/**
 * 获取授权信息
 */
export function getLicenseInfo(): Promise<LicenseInfo> {
  return request.get('/v1/configs/license')
}

/**
 * 激活授权
 */
export function activateLicense(data: LicenseActivateParams): Promise<LicenseInfo> {
  return request.post('/v1/configs/license/activate', data)
}

/**
 * 导出系统配置（备份）
 */
export function exportConfigs(): Promise<Blob> {
  return request.get('/v1/configs/backup', {
    responseType: 'blob'
  })
}

/**
 * 导入系统配置（恢复）
 */
export function importConfigs(data: FormData): Promise<{ success: boolean; message: string }> {
  return request.post('/v1/configs/restore', data, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}
