/**
 * API 模块索引
 */

// 类型导出
export * from './types'

// 认证
export * from './auth'

// 用户管理 - 排除与auth重复的UserInfo
export {
  getUserList,
  getUserById,
  createUser,
  updateUser,
  deleteUser,
  toggleUserStatus,
  resetPassword,
  getLoginHistory as getUserLoginHistory,
  type UserCreateParams,
  type UserUpdateParams,
  type LoginHistory
} from './user'

// 设备管理
export * from './device'

// 点位管理
export * from './point'

// 实时数据
export * from './realtime'

// 告警管理 - 排除与statistics重复的AlarmStatistics和getAlarmStatistics
export {
  getAlarmList as getAlarms,
  getAlarmById,
  getActiveAlarms,
  getAlarmCount,
  acknowledgeAlarm,
  resolveAlarm,
  batchAcknowledgeAlarms as batchAcknowledge,
  getAlarmTrend,
  getTopAlarmPoints,
  exportAlarms,
  type AlarmInfo,
  type AlarmCount,
  type AlarmTrend,
  type AlarmAcknowledgeParams,
  type AlarmResolveParams
} from './alarm'

// 历史数据 - 排除getPointStatistics (与statistics模块冲突)
export {
  getPointHistory,
  getPointTrend,
  getPointStatistics as getHistoryStatistics,
  getPointsCompare as comparePoints,
  getChangeRecords as getPointChanges,
  exportHistory,
  cleanupHistory,
  type HistoryData,
  type TrendData,
  type HistoryStatistics,
  type ChangeRecord,
  type CompareData
} from './history'

// 报表
export * from './report'

// 日志
export * from './log'

// 系统配置
export * from './config'

// 阈值配置
export * from './threshold'

// 统计分析
export * from './statistics'

// 用电管理
export * from './energy'

// 大屏布局
export * from './bigscreen'

// 资产管理
export * from './asset'

// 容量管理
export * from './capacity'

// 运维管理
export * from './operation'

// 演示数据
export * from './demo'

// VPP方案分析
export * from './vpp'

// 节能机会管理
export * from './opportunities'

// 可调度资源配置
export * from './dispatch'

// 电费监控
export * from './monitoring'

// 日前调度优化
export * from './optimization'
