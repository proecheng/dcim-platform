/**
 * 降级状态管理 — Story 4.5 优雅降级
 * 管理 Redis / WebSocket / MQTT 降级状态，供 DegradationBanner 消费
 */
import { defineStore } from 'pinia'
import { computed, reactive } from 'vue'

/** 独立响应式标志，可在 Pinia 初始化前安全写入（如 axios 拦截器） */
export const degradationFlags = reactive({
  redisDown: false,
  websocketDown: false,
  mqttDown: false,
  degradedMessage: '',
})

export const useDegradationStore = defineStore('degradation', () => {
  const redisDown = computed(() => degradationFlags.redisDown)
  const websocketDown = computed(() => degradationFlags.websocketDown)
  const mqttDown = computed(() => degradationFlags.mqttDown)
  const degradedMessage = computed(() => degradationFlags.degradedMessage)
  const hasDegradation = computed(
    () => degradationFlags.redisDown || degradationFlags.websocketDown || degradationFlags.mqttDown,
  )

  function setRedisDown(down: boolean, message?: string) {
    degradationFlags.redisDown = down
    degradationFlags.degradedMessage = message || ''
  }

  function setWebsocketDown(down: boolean) {
    degradationFlags.websocketDown = down
  }

  function setMqttDown(down: boolean) {
    degradationFlags.mqttDown = down
  }

  // 状态直接引用 degradationFlags，保留该方法兼容现有调用方。
  function syncFromFlags() {}

  return {
    redisDown,
    websocketDown,
    mqttDown,
    degradedMessage,
    hasDegradation,
    setRedisDown,
    setWebsocketDown,
    setMqttDown,
    syncFromFlags,
  }
})
