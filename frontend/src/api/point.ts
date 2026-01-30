import request from '@/utils/request'

export interface Point {
  id: number
  point_code: string
  point_name: string
  point_type: string
  device_type: string
  area_code: string
  unit: string
  data_type: string
  min_range: number
  max_range: number
  collect_interval: number
  is_enabled: boolean
  description: string
}

export function getPoints(params?: any) {
  return request.get('/v1/points', { params })
}

export function getPoint(id: number) {
  return request.get(`/v1/points/${id}`)
}

export function createPoint(data: Partial<Point>) {
  return request.post('/v1/points', data)
}

export function updatePoint(id: number, data: Partial<Point>) {
  return request.put(`/v1/points/${id}`, data)
}

export function deletePoint(id: number) {
  return request.delete(`/v1/points/${id}`)
}

export function enablePoint(id: number) {
  return request.put(`/v1/points/${id}/enable`)
}

export function disablePoint(id: number) {
  return request.put(`/v1/points/${id}/disable`)
}

export function getPointTypes() {
  return request.get('/v1/points/types')
}

/** 关联点位到用能设备 */
export function linkPointToDevice(pointId: number, energyDeviceId: number) {
  return request.put(`/v1/points/${pointId}/link-device`, null, {
    params: { energy_device_id: energyDeviceId }
  })
}

/** 取消点位与用能设备的关联 */
export function unlinkPointFromDevice(pointId: number) {
  return request.delete(`/v1/points/${pointId}/link-device`)
}
