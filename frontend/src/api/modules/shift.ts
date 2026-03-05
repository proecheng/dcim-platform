import request from '@/utils/request'

// ========== 计划管理 ==========
export function getShiftPlans(params?: any) {
  return request.get('/v1/energy/shift/plans', { params })
}

export function getShiftPlan(id: number) {
  return request.get(`/v1/energy/shift/plans/${id}`)
}

export function createShiftPlan(data: any) {
  return request.post('/v1/energy/shift/plans', data)
}

export function updateShiftPlan(id: number, data: any) {
  return request.put(`/v1/energy/shift/plans/${id}`, data)
}

export function deleteShiftPlan(id: number) {
  return request.delete(`/v1/energy/shift/plans/${id}`)
}

export function submitShiftPlan(id: number) {
  return request.post(`/v1/energy/shift/plans/${id}/submit`)
}

export function approveShiftPlan(id: number, data: any) {
  return request.post(`/v1/energy/shift/plans/${id}/approve`, data)
}

export function executeShiftPlan(id: number) {
  return request.post(`/v1/energy/shift/plans/${id}/execute`)
}

// ========== 分析接口 ==========
export function analyzeFeasibility(data: any) {
  return request.post('/v1/energy/shift/analysis/feasibility', data)
}

export function checkConstraints(data: any) {
  return request.post('/v1/energy/shift/analysis/constraints', data)
}

// ========== 约束管理接口 ==========
export function getShiftConstraints() {
  return request.get('/v1/energy/shift/constraints')
}

export function createShiftConstraint(data: any) {
  return request.post('/v1/energy/shift/constraints', data)
}

export function updateShiftConstraint(id: number, data: any) {
  return request.put(`/v1/energy/shift/constraints/${id}`, data)
}

export function deleteShiftConstraint(id: number) {
  return request.delete(`/v1/energy/shift/constraints/${id}`)
}

export function analyzeBenefit(data: any) {
  return request.post('/v1/energy/shift/analysis/benefit', data)
}

export function assessRisk(data: any) {
  return request.post('/v1/energy/shift/analysis/risk', data)
}
// ========== 机会分析接口 ==========
export function analyzeOpportunities(params?: any) {
  return request.post('/v1/energy/shift/opportunities/analyze', null, { params })
}

export function getOpportunities(params?: any) {
  return request.get('/v1/energy/shift/opportunities', { params })
}

export function getOpportunityDetail(id: number) {
  return request.get(`/v1/energy/shift/opportunities/${id}`)
}

export function convertOpportunityToPlan(id: number) {
  return request.post(`/v1/energy/shift/opportunities/${id}/convert`)
}

// ========== 设备接口 ==========
export function getShiftableDevices() {
  return request.get('/v1/energy/shift/devices/shiftable')
}

export function getDevicePotential(deviceId: number) {
  return request.get(`/v1/energy/shift/devices/${deviceId}/potential`)
}

// ========== 仪表盘接口 ==========
export function getDashboardOverview() {
  return request.get('/v1/energy/shift/dashboard/overview')
}

export function getRealtimeData() {
  return request.get('/v1/energy/shift/dashboard/realtime')
}

export function getTrends(days: number = 7) {
  return request.get('/v1/energy/shift/dashboard/trends', { params: { days } })
}

// ========== 统计接口 ==========
export function getStatisticsSummary(params?: any) {
  return request.get('/v1/energy/shift/statistics/summary', { params })
}

// ========== 执行记录接口 ==========
export function getExecutions(params?: any) {
  return request.get('/v1/energy/shift/executions', { params })
}

export function getExecutionDetail(id: number) {
  return request.get(`/v1/energy/shift/executions/${id}`)
}

export function getExecutionRealtime(id: number) {
  return request.get(`/v1/energy/shift/executions/${id}/realtime`)
}

// ========== 制冷联动接口 ==========
export function getCoolingConfig() {
  return request.get('/v1/energy/shift/cooling/config')
}

export function updateCoolingConfig(data: any) {
  return request.put('/v1/energy/shift/cooling/config', data)
}

export function getCoolingStatus() {
  return request.get('/v1/energy/shift/cooling/status')
}

export function getCoolingHistory(params?: any) {
  return request.get('/v1/energy/shift/cooling/history', { params })
}
// ========== 报表接口 ==========
export function getShiftReport(params: any) {
  return request.get(`/v1/energy/shift/reports/${params.report_type}`, { params })
}
export function exportShiftReport(data: any) {
  return request.post('/v1/energy/shift/reports/export', data.report_data, { params: { format: data.format } })
}
