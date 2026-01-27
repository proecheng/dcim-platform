/**
 * 需量板块嵌入式 API
 * 供节能中心详情页嵌入组件调用
 */
import request from '@/utils/request'
import type { ResponseModel } from './types'

// ==================== 类型定义 ====================

/** 需量配置对比数据 */
export interface DemandComparisonData {
  meter_point_id?: number
  meter_point_name: string
  current_declared: number
  max_demand_12m: number
  avg_demand_12m: number
  utilization_rate: number
  over_declared: number
  recommendation: {
    suggested_demand: number
    reduce_amount: number
    monthly_saving: number
    risk_level: 'low' | 'medium' | 'high'
  }
}

/** 需量曲线数据点 */
export interface DemandCurvePoint {
  month: string
  max_demand: number
  avg_demand?: number
  declared_demand?: number
}

/** 迷你需量曲线数据 */
export interface DemandCurveMiniData {
  data: DemandCurvePoint[]
  max_value: number
  max_month: string
  declared_demand?: number
}

/** 小时负荷数据点 */
export interface HourlyLoadPoint {
  hour: number
  power: number
  period: 'sharp' | 'peak' | 'flat' | 'valley' | 'deep_valley'
}

/** 时段汇总 */
export interface PeriodSummary {
  total_kwh: number
  avg_power: number
  hours: number
}

/** 负荷时段分布数据 */
export interface LoadPeriodData {
  date: string
  hourly_data: HourlyLoadPoint[]
  period_summary: Record<string, PeriodSummary>
  shiftable_power: number
}

/** 功率因数趋势数据点 */
export interface PowerFactorPoint {
  date: string
  power_factor: number
  status: 'good' | 'warning' | 'bad'
}

/** 功率因数趋势数据 */
export interface PowerFactorTrendData {
  data: PowerFactorPoint[]
  statistics: {
    avg_power_factor: number
    min_power_factor: number
    max_power_factor: number
    below_baseline_days: number
    baseline: number
  }
  financial_impact: {
    monthly_adjustment: number
    annual_adjustment: number
    is_penalty: boolean
  }
}


// ==================== API 函数 ====================

/**
 * 获取需量配置对比数据
 */
export function getDemandComparison(meterPointId?: number) {
  return request.get<ResponseModel<DemandComparisonData>>('/v1/demand/comparison', {
    params: { meter_point_id: meterPointId }
  })
}

/**
 * 获取迷你需量曲线数据
 */
export function getDemandCurveMini(params?: {
  meterPointId?: number
  months?: number
}) {
  return request.get<ResponseModel<DemandCurveMiniData>>('/v1/demand/curve-mini', {
    params: {
      meter_point_id: params?.meterPointId,
      months: params?.months || 12
    }
  })
}

/**
 * 获取负荷时段分布数据
 */
export function getLoadPeriodDistribution(params?: {
  meterPointId?: number
  date?: string
}) {
  return request.get<ResponseModel<LoadPeriodData>>('/v1/demand/load-period', {
    params: {
      meter_point_id: params?.meterPointId,
      target_date: params?.date
    }
  })
}

/**
 * 获取功率因数趋势数据
 */
export function getPowerFactorTrend(params?: {
  meterPointId?: number
  days?: number
}) {
  return request.get<ResponseModel<PowerFactorTrendData>>('/v1/demand/power-factor-trend', {
    params: {
      meter_point_id: params?.meterPointId,
      days: params?.days || 30
    }
  })
}
