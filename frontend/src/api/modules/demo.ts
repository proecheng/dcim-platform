/**
 * 演示数据 API
 */
import request from '@/utils/request'

// 获取演示数据状态
export function getDemoStatus() {
  return request.get('/v1/demo/status')
}

// 加载演示数据
export function loadDemoData(days: number = 30) {
  return request.post('/v1/demo/load', { days })
}

// 获取加载进度
export function getDemoProgress() {
  return request.get('/v1/demo/progress')
}

// 卸载演示数据
export function unloadDemoData() {
  return request.post('/v1/demo/unload')
}

// 刷新历史数据日期
export function refreshDemoDataDates() {
  return request.post('/v1/demo/refresh-dates')
}
