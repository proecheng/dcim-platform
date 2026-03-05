/**
 * 告警组合式函数
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
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
import { useAlarmStore, type Alarm } from '@/stores/alarm'

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

  const error = ref<Error | null>(null)

  const { play: playAlarmSound, stop: stopAlarmSound } = useSound()
  const alarmStore = useAlarmStore()
  const { activeAlarms, alarmCount, loading } = storeToRefs(alarmStore)

  // Web Audio API 兜底：当 mp3 文件不存在时使用合成音
  let audioContext: AudioContext | null = null
  const playWebAudioFallback = (level: string) => {
    try {
      if (!audioContext) {
        audioContext = new AudioContext()
      }
      const oscillator = audioContext.createOscillator()
      const gainNode = audioContext.createGain()
      oscillator.connect(gainNode)
      gainNode.connect(audioContext.destination)

      const freqMap: Record<string, number> = {
        critical: 880, major: 660, minor: 520, info: 440
      }
      const durationMap: Record<string, number> = {
        critical: 0.5, major: 0.4, minor: 0.3, info: 0.2
      }
      oscillator.frequency.value = freqMap[level] || 440
      gainNode.gain.value = level === 'critical' ? 0.3 : 0.2
      oscillator.start()
      oscillator.stop(audioContext.currentTime + (durationMap[level] || 0.3))
    } catch (e) {
      console.warn('Web Audio API 告警提示音播放失败:', e)
    }
  }

  // WebSocket 连接
  const { isConnected, subscribe, on, off, connect, disconnect } = useWebSocket({
    url: '/ws/alarms',
    autoConnect: false
  })

  // 获取活动告警（委托给 AlarmStore）
  const fetchActiveAlarms = async () => {
    try {
      await alarmStore.fetchActiveAlarms()
      error.value = null
    } catch (e) {
      error.value = e as Error
    }
  }

  // 获取告警计数（现由 Store 自动维护，保留接口兼容）
  const fetchAlarmCount = async () => {
    // alarmCount 已由 AlarmStore.fetchActiveAlarms() 自动更新
  }

  // 处理新告警
  const handleNewAlarm = (alarm: AlarmInfo) => {
    // 添加到 AlarmStore（Store 会自动更新计数）
    alarmStore.addAlarm(alarm as unknown as Alarm)

    // 播放声音（检查 store 中的声音开关）
    if (playSound) {
      if (alarmStore.soundEnabled) {
        const soundMap: Record<string, string> = {
          critical: '/sounds/alarm_critical.mp3',
          major: '/sounds/alarm_major.mp3',
          minor: '/sounds/alarm_minor.mp3',
          info: '/sounds/alarm_info.mp3'
        }
        const soundSrc = soundMap[alarm.alarm_level]
        if (soundSrc) {
          // play() 内部异步调用 audio.play()，同步 try/catch 无法捕获
          // 使用 setTimeout 兜底：若 200ms 后仍未播放则用 Web Audio
          playAlarmSound(soundSrc, {
            loop: alarm.alarm_level === 'critical'
          })
        } else {
          playWebAudioFallback(alarm.alarm_level)
        }
      }
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

  // 处理告警确认（委托给 AlarmStore）
  const handleAlarmAck = (alarmId: number) => {
    alarmStore.updateAlarm(alarmId, { status: 'acknowledged' })
  }

  // 处理告警解决（委托给 AlarmStore）
  const handleAlarmResolve = (alarmId: number) => {
    alarmStore.updateAlarm(alarmId, { status: 'resolved' })

    // 如果没有紧急告警了，停止声音
    if (!activeAlarms.value.some(a => a.alarm_level === 'critical' && a.status === 'active')) {
      stopAlarmSound()
    }
  }

  // 处理 WebSocket 消息（所有状态操作委托给 AlarmStore）
  const handleAlarmMessage = (message: any) => {
    if (message.type !== 'alarm') return

    const { action, data } = message

    switch (action) {
      case 'new':
        handleNewAlarm(data)
        break
      case 'ack':
        alarmStore.updateAlarm(data.id, { status: 'acknowledged', ...data })
        window.dispatchEvent(new Event('alarm-status-changed'))
        break
      case 'update':
        if (data.id) {
          alarmStore.updateAlarm(data.id, data)
        }
        window.dispatchEvent(new Event('alarm-status-changed'))
        break
      case 'resolve':
        handleAlarmResolve(data.id)
        window.dispatchEvent(new Event('alarm-status-changed'))
        break
      case 'batch_ack':
        if (data.alarm_ids && Array.isArray(data.alarm_ids)) {
          for (const id of data.alarm_ids) {
            alarmStore.updateAlarm(id, { status: 'acknowledged' })
          }
        }
        window.dispatchEvent(new Event('alarm-status-changed'))
        break
      case 'escalate':
        alarmStore.updateAlarm(data.id, {
          alarm_level: data.alarm_level,
          escalated_from: data.previous_level
        })
        window.dispatchEvent(new Event('alarm-status-changed'))
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

  // 按级别获取告警（从 AlarmStore 派生）
  const getAlarmsByLevel = (level: string) => {
    return alarmStore.activeAlarms.filter(a => a.alarm_level === level)
  }

  // 计算属性（从 AlarmStore 派生）
  const criticalAlarms = computed(() => alarmStore.activeAlarms.filter(a => a.alarm_level === 'critical'))
  const majorAlarms = computed(() => alarmStore.activeAlarms.filter(a => a.alarm_level === 'major'))
  const minorAlarms = computed(() => alarmStore.activeAlarms.filter(a => a.alarm_level === 'minor'))
  const hasActiveAlarms = computed(() => alarmStore.activeAlarms.length > 0)
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

  // TODO: Story 27.5 - 迁移到 WebSocketManager 后移除此清理逻辑
  onUnmounted(() => {
    off('alarm', handleAlarmMessage)
    disconnect()
    stopAlarmSound()
  })

  return {
    activeAlarms,
    alarmCount,
    loading,
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
