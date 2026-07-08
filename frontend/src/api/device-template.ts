import request from '@/utils/request'

export interface DeviceTemplate {
  id: number
  name: string
  manufacturer: string
  model: string
  protocol_type: string
  description: string | null
  point_config: Array<Record<string, any>>
  extra_config?: Record<string, any> | null
  created_at: string
  updated_at: string
}

export interface BuiltinDeviceTemplate extends Omit<DeviceTemplate, 'id' | 'created_at' | 'updated_at'> {
  key: string
  point_count: number
}

export function getTemplates(params?: any) {
  return request.get('/v1/device-templates', { params })
}

export function getTemplate(id: number) {
  return request.get(`/v1/device-templates/${id}`)
}

export function createTemplate(data: Partial<DeviceTemplate>) {
  return request.post('/v1/device-templates', data)
}

export function updateTemplate(id: number, data: Partial<DeviceTemplate>) {
  return request.put(`/v1/device-templates/${id}`, data)
}

export function deleteTemplate(id: number) {
  return request.delete(`/v1/device-templates/${id}`)
}

export function createDatasourceFromTemplate(templateId: number, data: any) {
  return request.post(`/v1/device-templates/${templateId}/create-datasource`, data)
}

export function getBuiltinTemplates() {
  return request.get('/v1/device-templates/builtins')
}

export function installBuiltinTemplate(key: string) {
  return request.post(`/v1/device-templates/builtins/${key}/install`)
}
