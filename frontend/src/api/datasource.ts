import request from '@/utils/request'

export interface DataSource {
  id: number
  name: string
  protocol_type: string
  gateway_id: number | null
  connection_config: Record<string, any>
  collection_interval: number
  write_enabled: boolean
  status: string
  last_communication: string | null
  consecutive_failures: number
  retry_base_delay: number
  retry_max_delay: number
  retry_max_failures: number
  site_id: number
  is_enabled: boolean
  created_at: string
  updated_at: string
}

export interface ConnectionTestResult {
  success: boolean
  message: string
  latency_ms: number | null
  sample_data: Record<string, any> | null
}

export function getDatasources(params?: any) {
  return request.get('/v1/datasources', { params })
}

export function getDatasource(id: number) {
  return request.get(`/v1/datasources/${id}`)
}

export function createDatasource(data: Partial<DataSource>) {
  return request.post('/v1/datasources', data)
}

export function updateDatasource(id: number, data: Partial<DataSource>) {
  return request.put(`/v1/datasources/${id}`, data)
}

export function deleteDatasource(id: number) {
  return request.delete(`/v1/datasources/${id}`)
}

export function testConnection(data: { protocol_type: string; connection_config: Record<string, any> }) {
  return request.post<ConnectionTestResult>('/v1/datasources/test-connection', data)
}

export function testExistingConnection(id: number) {
  return request.post<ConnectionTestResult>(`/v1/datasources/${id}/test-connection`)
}

export function toggleWritePermission(id: number) {
  return request.put<any>(`/v1/datasources/${id}/write-permission`)
}

export function validatePoints(datasourceId: number, file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post(`/v1/datasources/${datasourceId}/points/validate`, formData)
}

export function importPoints(datasourceId: number, file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post(`/v1/datasources/${datasourceId}/points/import`, formData)
}

export interface CommunicationStatusItem {
  id: number
  name: string
  protocol_type: string
  status: string
  last_communication: string | null
  consecutive_failures: number
  retry_max_failures: number
  interruption_duration_seconds: number | null
  affected_points: number
  affected_devices: number
}

export function getCommunicationStatus(): Promise<CommunicationStatusItem[]> {
  return request.get('/v1/datasources/communication-status')
}

export function exportReport(params?: any) {
  return request.get('/v1/datasources/export-report', {
    params,
    responseType: 'blob',
  } as any)
}
