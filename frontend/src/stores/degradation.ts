/**
 * 降级状态管理 — Story 4.5 优雅降级
 * 管理 Redis / WebSocket / MQTT 降级状态，供 DegradationBanner 消费
 */
import { defineStore } from 'pinia'
import { reactive } from 'vue'

/** 独立响应式标志，可在 Pinia 初始化前安全写入（如 axios 拦截器） */
export const degradationFlags = reactive({
  redisDown: false,
  websocketDown: false,
  mqttDown: false,
  degradedMessage: '',
})

export const useDegradationStore = defineStore('degradation', {
  state: () => ({
    redisDown: false,
    websocketDown: false,
    mqttDown: false,
    degradedMessage: '',
  }),
  getters: {
    hasDegradation: (state) => state.redisDown || state.websocketDown || state.mqttDown,
  },
  actions: {
    setRedisDown(down: boolean, message?: string) {
      this.redisDown = down
      degradationFlags.redisDown = down
      this.degradedMessage = message || ''
      degradationFlags.degradedMessage = message || ''
    },
    setWebsocketDown(down: boolean) {
      this.websocketDown = down
      degradationFlags.websocketDown = down
    },
    setMqttDown(down: boolean) {
      this.mqttDown = down
      degradationFlags.mqttDown = down
    },
    /** 从 degradationFlags 同步状态（供组件 onMounted 调用） */
    syncFromFlags() {
      this.redisDown = degradationFlags.redisDown
      this.websocketDown = degradationFlags.websocketDown
      this.mqttDown = degradationFlags.mqttDown
      this.degradedMessage = degradationFlags.degradedMessage
    },
  },
})
