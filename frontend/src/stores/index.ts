/**
 * Pinia 状态管理导出
 */
import { createPinia } from 'pinia'

export const pinia = createPinia()

export { useUserStore } from './user'
export { useAlarmStore } from './alarm'
export { useRealtimeStore } from './realtime'
export { useAppStore } from './app'
export { useEnergyStore } from './energy'
export { useOpportunityStore } from './opportunity'
