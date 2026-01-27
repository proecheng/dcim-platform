/**
 * 告警组合式函数
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useWebSocket } from './useWebSocket'
import { useSound } from './useSound'
import { ElNotification } from 'element-plus'
import {
  getActiveAlarms,
  getAlarmCount,
  acknowledgeAlarm,
  resolveAlarm,
  type AlarmInfo,
  type AlarmCount
} from '@/api/modules/alarm'

interface UseAlarmOptions {
  autoFetch?: boolean
  autoSubscribe?: boolean
  playSound?: boolean
  showNotification?: boolean
}

export function useAlarm(options: UseAlarmOptions = {}) {
  const {
    autoFetch = true,
    autoSubscribe = true,
    playSound = true,
    showNotification = true
  } = options

  const activeAlarms = ref<AlarmInfo[]>([])
  const alarmCount = ref<AlarmCount>({ critical: 0, major: 0, minor: 0, info: 0, total: 0 })
  const loading = ref(false)
  const error = ref<Error | null>(null)

  const { play: playAlarmSound, stop: stopAlarmSound } = useSound()

  // WebSocket 连接
  const { isConnected, subscribe, on, off, connect, disconnect } = useWebSocket({
    url: '/ws/alarms',
    autoConnect: false
  })

  // 获取活动告警
  const fetchActiveAlarms = async () => {
    loading.value = true
    try {
      activeAlarms.value = await getActiveAlarms()
      error.value = null
    } catch (e) {
      error.value = e as Error
    } finally {
      loading.value = false
    }
  }

  // 获取告警计数
  const fetchAlarmCount = async () => {
    try {
      alarmCount.value = await getAlarmCount()
    } catch (e) {
      console.error('获取告警计数失败:', e)
    }
  }

  // 处理新告警
  const handleNewAlarm = (alarm: AlarmInfo) => {
    // 添加到列表
    activeAlarms.value.unshift(alarm)

    // 更新计数
    alarmCount.value.total++
    alarmCount.value[alarm.alarm_level as keyof AlarmCount]++

    // 播放声音
    if (playSound) {
      const soundMap: Record<string, string> = {
        critical: '/sounds/alarm_critical.mp3',
        major: '/sounds/alarm_major.mp3',
        minor: '/sounds/alarm_minor.mp3',
        info: '/sounds/alarm_info.mp3'
      }
      playAlarmSound(soundMap[alarm.alarm_level], {
        loop: alarm.alarm_level === 'critical'
      })
    }

    // 显示通知
    if (showNotification) {
      const typeMap: Record<string, 'error' | 'warning' | 'info' | 'success'> = {
        critical: 'error',
        major: 'warning',
        minor: 'info',
        info: 'info'
      }
      ElNotification({
        title: `${alarm.alarm_level === 'critical' ? '紧急' : ''}告警`,
        message: alarm.alarm_message,
        type: typeMap[alarm.alarm_level],
        duration: alarm.alarm_level === 'critical' ? 0 : 5000,
        position: 'bottom-right'
      })
    }
  }

  // 处理告警确认
  const handleAlarmAck = (alarmId: number) => {
    const index = activeAlarms.value.findIndex(a => a.id === alarmId)
    if (index !== -1) {
      activeAlarms.value[index].status = 'acknowledged'
    }
  }

  // 处理告警解决
  const handleAlarmResolve = (alarmId: number) => {
    const index = activeAlarms.value.findIndex(a => a.id === alarmId)
    if (index !== -1) {
      const alarm = activeAlarms.value[index]
      activeAlarms.value.splice(index, 1)

      // 更新计数
      alarmCount.value.total--
      alarmCount.value[alarm.alarm_level as keyof AlarmCount]--
    }

    // 如果没有紧急告警了，停止声音
    if (!activeAlarms.value.some(a => a.alarm_level === 'critical' && a.status === 'active')) {
      stopAlarmSound()
    }
  }

  // 处理 WebSocket 消息
  const handleAlarmMessage = (message: any) => {
    if (message.type !== 'alarm') return

    const { action, data } = message

    switch (action) {
      case 'new':
        handleNewAlarm(data)
        break
      case 'ack':
        handleAlarmAck(data.id)
        break
      case 'resolve':
        handleAlarmResolve(data.id)
        break
    }
  }

  // 订阅告警
  const subscribeAlarms = () => {
    if (!isConnected.value) {
      connect()
    }

    on('alarm', handleAlarmMessage)

    subscribe({
      channels: ['alarms']
    })
  }

  // 确认告警
  const ackAlarm = async (id: number, remark?: string) => {
    await acknowledgeAlarm(id, { remark })
    handleAlarmAck(id)
  }

  // 解决告警
  const resolveAlarmById = async (id: number, remark?: string) => {
    await resolveAlarm(id, { remark, resolve_type: 'manual' })
    handleAlarmResolve(id)
  }

  // 批量确认
  const batchAck = async (ids: number[], remark?: string) => {
    for (const id of ids) {
      await ackAlarm(id, remark)
    }
  }

  // 按级别获取告警
  const getAlarmsByLevel = (level: string) => {
    return activeAlarms.value.filter(a => a.alarm_level === level)
  }

  // 计算属性
  const criticalAlarms = computed(() => getAlarmsByLevel('critical'))
  const majorAlarms = computed(() => getAlarmsByLevel('major'))
  const minorAlarms = computed(() => getAlarmsByLevel('minor'))
  const hasActiveAlarms = computed(() => activeAlarms.value.length > 0)
  const hasCriticalAlarms = computed(() => criticalAlarms.value.length > 0)

  onMounted(() => {
    if (autoFetch) {
      fetchActiveAlarms()
      fetchAlarmCount()
    }

    if (autoSubscribe) {
      subscribeAlarms()
    }
  })

  onUnmounted(() => {
    off('alarm', handleAlarmMessage)
    disconnect()
    stopAlarmSound()
  })

  return {
    activeAlarms: computed(() => activeAlarms.value),
    alarmCount: computed(() => alarmCount.value),
    loading: computed(() => loading.value),
    error: computed(() => error.value),
    criticalAlarms,
    majorAlarms,
    minorAlarms,
    hasActiveAlarms,
    hasCriticalAlarms,
    isConnected,
    fetchActiveAlarms,
    fetchAlarmCount,
    ackAlarm,
    resolveAlarm: resolveAlarmById,
    batchAck,
    getAlarmsByLevel
  }
}

export default useAlarm
