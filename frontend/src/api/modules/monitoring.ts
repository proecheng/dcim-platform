/**
 * 电费监控 API
 * 实时需量监控、预警、月度统计
 */
import request from '@/utils/request'
import type { ResponseModel } from './types'

// ==================== 类型定义 ====================

/** 需量状态 */
export interface DemandStatus {
  current_power: number
  window_avg_power: number
  demand_target: number
  declared_demand: number
  utilization_ratio: number
  remaining_capacity: number
  alert_level: 'normal' | 'warning' | 'critical'
  month_max_demand: number
  month_max_time: string | null
  trend: 'up' | 'down' | 'stable'
  timestamp: string
}

/** 需量预警 */
export interface DemandAlert {
  level: 'warning' | 'critical'
  message: string
  current_value: number
  threshold: number
  suggestion: string
}

/** 月度电费汇总 */
export interface MonthlyBillSummary {
  year_month: string
  total_energy: number
  max_demand: number
  demand_target: number
  energy_cost: number
  demand_cost: number
  power_factor_adjustment: number
  total_cost: number
  optimized_saving: number
  cost_breakdown: {
    energy_by_period: Record<string, number>
    cost_by_period: Record<string, number>
  }
}

/** 实时曲线数据点 */
export interface RealtimeCurvePoint {
  timestamp: string
  full_timestamp: string
  power: number
  demand_target: number
  utilization: number
  alert_level: string
}

/** 日需量趋势数据点 */
export interface DailyDemandPoint {
  time: string
  demand: number
  period: string
}

/** 历史月度数据 */
export interface MonthlyHistoryItem {
  year_month: string
  total_energy: number
  total_cost: number
  energy_cost: number
  demand_cost: number
  other_cost: number
  max_demand: number
}

// ==================== 实时监控 API ====================

/** 获取实时需量状态 */
export function getRealtimeStatus() {
  return request.get<ResponseModel<DemandStatus>>('/v1/monitoring/realtime/status')
}

/** 获取当前预警列表 */
export function getRealtimeAlerts() {
  return request.get<ResponseModel<DemandAlert[]>>('/v1/monitoring/realtime/alerts')
}

/** 获取实时功率曲线 */
export function getRealtimeCurve(hours: number = 4) {
  return request.get<ResponseModel<{
    data: RealtimeCurvePoint[]
    demand_target: number
    time_range: string
  }>>('/v1/monitoring/realtime/curve', { params: { hours } })
}

// ==================== 月度统计 API ====================

/** 获取当月电费汇总 */
export function getCurrentMonthSummary() {
  return request.get<ResponseModel<MonthlyBillSummary>>('/v1/monitoring/monthly/current')
}

/** 获取历史月度电费 */
export function getMonthlyHistory(months: number = 12) {
  return request.get<ResponseModel<{
    data: MonthlyHistoryItem[]
    months: number
  }>>('/v1/monitoring/monthly/history', { params: { months } })
}

// ==================== 需量趋势 API ====================

/** 获取日需量趋势 */
export function getDailyDemandTrend(date?: string) {
  return request.get<ResponseModel<{
    date: string
    declared_demand: number
    max_demand: number
    max_demand_time: string
    avg_demand: number
    data: DailyDemandPoint[]
  }>>('/v1/monitoring/demand/daily-trend', { params: { date_str: date } })
}

// ==================== 辅助函数 ====================

/** 获取预警级别颜色 */
export function getAlertColor(level: string): string {
  switch (level) {
    case 'critical': return '#f5222d'
    case 'warning': return '#faad14'
    default: return '#52c41a'
  }
}

/** 获取预警级别文字 */
export function getAlertText(level: string): string {
  switch (level) {
    case 'critical': return '超标'
    case 'warning': return '预警'
    default: return '正常'
  }
}

/** 获取时段颜色 */
export function getPeriodColor(period: string): string {
  const colors: Record<string, string> = {
    sharp: '#722ed1',
    peak: '#f5222d',
    flat: '#faad14',
    valley: '#52c41a',
    deep_valley: '#1890ff'
  }
  return colors[period] || '#1890ff'
}

/** 获取时段名称 */
export function getPeriodName(period: string): string {
  const names: Record<string, string> = {
    sharp: '尖峰',
    peak: '峰时',
    flat: '平时',
    valley: '谷时',
    deep_valley: '深谷'
  }
  return names[period] || period
}
