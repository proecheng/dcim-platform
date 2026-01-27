/**
 * VPP (虚拟电厂) 方案分析 API
 */
import request from '@/utils/request'

export interface AnalysisRequest {
  months: string[]
  start_date: string
  end_date: string
}

export interface MetricValue {
  value: number
  unit: string
  formula: string
  data_source?: any
  typical_range?: string
  description?: string
  parameters?: any
  breakdown?: any
}

export interface AnalysisResponse {
  analysis_period: {
    months: string[]
    load_data_range: string
  }
  electricity_usage: {
    average_price: MetricValue
    fluctuation_rate: MetricValue
    peak_ratio: MetricValue
    valley_ratio: MetricValue
  }
  load_characteristics: {
    P_max: MetricValue
    P_avg: MetricValue
    P_min: MetricValue
    load_rate: MetricValue
    peak_valley_diff: MetricValue
    load_std: MetricValue
    data_source: any
  }
  cost_structure: {
    market_ratio: MetricValue
    transmission_ratio: MetricValue
    basic_fee_ratio: MetricValue
    system_operation_ratio: MetricValue
    government_fund_ratio: MetricValue
    data_source: any
  }
  transfer_potential: {
    transferable_load: MetricValue
    price_spread: MetricValue
    annual_transfer_benefit: MetricValue
    data_source: any
  }
  demand_optimization: {
    peak_reduction_potential: MetricValue
    demand_optimization_benefit: MetricValue
    parameters: any
  }
  vpp_revenue: {
    demand_response_revenue: MetricValue
    ancillary_service_revenue: MetricValue
    spot_arbitrage_revenue: MetricValue
    total_vpp_revenue: MetricValue
  }
  investment_return: {
    total_investment: MetricValue
    annual_total_benefit: MetricValue
    payback_period: MetricValue
    roi: MetricValue
  }
  summary: {
    annual_total_benefit: MetricValue
    payback_period: MetricValue
    roi: MetricValue
  }
}

export const vppApi = {
  /**
   * 生成完整的VPP方案分析
   */
  generateAnalysis(data: AnalysisRequest): Promise<{ code: number; message: string; data: AnalysisResponse }> {
    return request.post('/v1/vpp/analysis', data)
  },

  /**
   * 获取负荷特性指标
   */
  getLoadMetrics(startDate: string, endDate: string): Promise<any> {
    return request.get('/v1/vpp/load-metrics', {
      params: { start_date: startDate, end_date: endDate }
    })
  },

  /**
   * 获取电费结构分析
   */
  getCostStructure(month: string): Promise<any> {
    return request.get(`/v1/vpp/cost-structure/${month}`)
  },

  /**
   * 获取峰谷转移潜力
   */
  getTransferPotential(): Promise<any> {
    return request.get('/v1/vpp/transfer-potential')
  },

  /**
   * 获取VPP收益测算
   */
  getVPPRevenue(adjustableCapacity: number): Promise<any> {
    return request.get('/v1/vpp/vpp-revenue', {
      params: { adjustable_capacity: adjustableCapacity }
    })
  },

  /**
   * 获取投资回报分析
   */
  getROI(annualBenefit: number): Promise<any> {
    return request.get('/v1/vpp/roi', {
      params: { annual_benefit: annualBenefit }
    })
  },

  /**
   * 获取所有计算公式参考
   */
  getFormulaReference(): Promise<any> {
    return request.get('/v1/vpp/formula-reference')
  }
}
