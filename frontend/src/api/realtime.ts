import request from '@/utils/request'

export function getRealtimeData(params?: any) {
  return request.get('/v1/realtime', { params })
}

export function getRealtimeSummary() {
  return request.get('/v1/realtime/summary')
}

export function getPointRealtime(pointId: number) {
  return request.get(`/v1/realtime/${pointId}`)
}
