import request from '@/utils/request'

export function getAlarms(params?: any) {
  return request.get('/v1/alarms', { params })
}

export function getActiveAlarms() {
  return request.get('/v1/alarms/active')
}

export function getAlarmCount() {
  return request.get('/v1/alarms/count')
}

export function acknowledgeAlarm(id: number) {
  return request.put(`/v1/alarms/${id}/acknowledge`)
}

export function resolveAlarm(id: number) {
  return request.put(`/v1/alarms/${id}/resolve`)
}

export function batchAcknowledge(alarmIds: number[]) {
  return request.put('/v1/alarms/batch-acknowledge', { alarm_ids: alarmIds })
}
