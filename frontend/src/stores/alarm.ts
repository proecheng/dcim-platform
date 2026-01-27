import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Alarm {
  id: number
  point_code: string
  point_name: string
  alarm_level: string
  alarm_message: string
  status: string
  created_at: string
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

  function addAlarm(alarm: Alarm) {
    activeAlarms.value.unshift(alarm)
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

  return {
    activeAlarms,
    alarmCount,
    addAlarm,
    removeAlarm
  }
})
