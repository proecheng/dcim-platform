/**
 * 统计分析 API
 */
import request from '@/utils/request'
import type { TimeRangeParams } from './types'

export interface SystemOverview {
  points: {
    total: number
    enabled: number
    online: number
    offline: number
    alarm: number
  }
  devices: {
    total: number
    online: number
    offline: number
    maintenance: number
  }
  alarms: {
    active: number
    today: number
    critical: number
    major: number
    minor: number
  }
  system: {
    uptime: number
    cpu_usage: number
    memory_usage: number
    disk_usage: number
  }
}

export interface PointStatistics {
  by_type: Record<string, number>
  by_area: Record<string, number>
  by_device_type: Record<string, number>
  by_status: Record<string, number>
  history: {
    date: string
    total: number
    enabled: number
    alarm: number
  }[]
}

export interface AlarmStatistics {
  total: number
  by_level: Record<string, number>
  by_type: Record<string, number>
  by_status: Record<string, number>
  top_points: {
    point_id: number
    point_name: string
    count: number
  }[]
  trend: {
    date: string
    critical: number
    major: number
    minor: number
    info: number
  }[]
  mttr: number
  mtbf: number
}

export interface EnergyStatistics {
  total_consumption: number
  by_device_type: Record<string, number>
  by_area: Record<string, number>
  daily: {
    date: string
    consumption: number
    cost: number
  }[]
  pue: number
  peak_power: number
  avg_power: number
}

export interface AvailabilityStatistics {
  overall: number
  by_device_type: Record<string, number>
  by_area: Record<string, number>
  daily: {
    date: string
    availability: number
    downtime_minutes: number
  }[]
}

export interface ComparisonData {
  current: {
    value: number
    start_time: string
    end_time: string
  }
  previous: {
    value: number
    start_time: string
    end_time: string
  }
  change_rate: number
  trend: 'up' | 'down' | 'stable'
}

/**
 * 获取系统概览统计
 */
export function getSystemOverview(): Promise<SystemOverview> {
  return request.get('/v1/statistics/overview')
}

/**
 * 获取点位统计
 */
export function getPointStatistics(params?: TimeRangeParams): Promise<PointStatistics> {
  return request.get('/v1/statistics/points', { params })
}

/**
 * 获取告警统计
 */
export function getAlarmStatistics(params?: TimeRangeParams): Promise<AlarmStatistics> {
  return request.get('/v1/statistics/alarms', { params })
}

/**
 * 获取能耗统计
 */
export function getEnergyStatistics(params?: TimeRangeParams): Promise<EnergyStatistics> {
  return request.get('/v1/statistics/energy', { params })
}

/**
 * 获取可用性统计
 */
export function getAvailabilityStatistics(params?: TimeRangeParams): Promise<AvailabilityStatistics> {
  return request.get('/v1/statistics/availability', { params })
}

/**
 * 获取同比/环比数据
 */
export function getComparisonData(params: {
  metric: 'alarm_count' | 'energy' | 'availability'
  compare_type: 'yoy' | 'mom' | 'wow' | 'dod'  // year-over-year, month-over-month, etc.
  date?: string
}): Promise<ComparisonData> {
  return request.get('/v1/statistics/comparison', { params })
}
