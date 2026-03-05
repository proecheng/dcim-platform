import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getActiveAlarms } from '@/api/modules/alarm'

export interface Alarm {
  id: number
  point_id?: number
  point_code: string
  point_name: string
  alarm_level: string
  alarm_message: string
  status: string
  created_at: string
  trigger_value?: number
  threshold_value?: number
  acknowledged_by?: number
  acknowledged_at?: string
  process_remark?: string
  processed_by?: number
  processed_at?: string
  resolved_by?: number
  resolved_at?: string
  duration_seconds?: number
  escalation_count?: number
  escalated_from?: string | null
  escalation_remark?: string | null
  data_source?: string
}

export const useAlarmStore = defineStore('alarm', () => {
  const activeAlarms = ref<Alarm[]>([])
  const alarmCount = ref({
    critical: 0,
    major: 0,
    minor: 0,
    info: 0,
    total: 0
  })
  const loading = ref(false)

  async function fetchActiveAlarms() {
    if (loading.value) return
    loading.value = true
    try {
      const alarms = await getActiveAlarms()
      activeAlarms.value = alarms as unknown as Alarm[]
      updateCount()
    } finally {
      loading.value = false
    }
  }

  function addAlarm(alarm: Alarm) {
    // 去重：相同 id 不重复添加
    if (alarm.id && activeAlarms.value.some(a => a.id === alarm.id)) return
    activeAlarms.value.unshift(alarm)
    // 限制列表长度，防止内存溢出
    if (activeAlarms.value.length > 1000) {
      activeAlarms.value = activeAlarms.value.slice(0, 1000)
    }
    updateCount()
  }

  function removeAlarm(id: number) {
    activeAlarms.value = activeAlarms.value.filter(a => a.id !== id)
    updateCount()
  }

  function updateCount() {
    alarmCount.value = {
      critical: activeAlarms.value.filter(a => a.alarm_level === 'critical').length,
      major: activeAlarms.value.filter(a => a.alarm_level === 'major').length,
      minor: activeAlarms.value.filter(a => a.alarm_level === 'minor').length,
      info: activeAlarms.value.filter(a => a.alarm_level === 'info').length,
      total: activeAlarms.value.length
    }
  }

  function updateAlarm(id: number, fields: Partial<Alarm>) {
    const index = activeAlarms.value.findIndex(a => a.id === id)
    if (index !== -1) {
      Object.assign(activeAlarms.value[index], fields)
      if (fields.status === 'resolved') {
        activeAlarms.value.splice(index, 1)
      }
      updateCount()
    }
  }

  return {
    activeAlarms,
    alarmCount,
    loading,
    fetchActiveAlarms,
    addAlarm,
    removeAlarm,
    updateAlarm,
  }
})
