/**
 * 权限控制组合式函数
 */
import { computed } from 'vue'
import { useUserStore } from '@/stores/user'

export function usePermission() {
  const userStore = useUserStore()

  // 检查是否有指定权限
  const hasPermission = (permission: string): boolean => {
    const permissions = userStore.permissions
    if (!permissions || permissions.length === 0) {
      return false
    }
    return permissions.includes(permission)
  }

  // 检查是否有任意一个权限
  const hasAnyPermission = (permissions: string[]): boolean => {
    return permissions.some(p => hasPermission(p))
  }

  // 检查是否有所有权限
  const hasAllPermissions = (permissions: string[]): boolean => {
    return permissions.every(p => hasPermission(p))
  }

  // 检查角色
  const hasRole = (role: string): boolean => {
    return userStore.role === role
  }

  // 检查是否是管理员
  const isAdmin = computed(() => hasRole('admin'))

  // 检查是否是操作员
  const isOperator = computed(() => hasRole('admin') || hasRole('operator'))

  // 检查是否是查看者
  const isViewer = computed(() => hasRole('admin') || hasRole('operator') || hasRole('viewer'))

  // 权限常量
  const permissions = {
    // 用户管理
    USER_READ: 'user:read',
    USER_WRITE: 'user:write',
    USER_DELETE: 'user:delete',

    // 点位管理
    POINT_READ: 'point:read',
    POINT_WRITE: 'point:write',
    POINT_DELETE: 'point:delete',

    // 告警管理
    ALARM_READ: 'alarm:read',
    ALARM_WRITE: 'alarm:write',
    ALARM_ACK: 'alarm:ack',

    // 配置管理
    CONFIG_READ: 'config:read',
    CONFIG_WRITE: 'config:write',

    // 日志查询
    LOG_READ: 'log:read',

    // 报表管理
    REPORT_READ: 'report:read',
    REPORT_WRITE: 'report:write'
  }

  // 快捷权限检查
  const canReadUsers = computed(() => hasPermission(permissions.USER_READ))
  const canWriteUsers = computed(() => hasPermission(permissions.USER_WRITE))
  const canDeleteUsers = computed(() => hasPermission(permissions.USER_DELETE))

  const canReadPoints = computed(() => hasPermission(permissions.POINT_READ))
  const canWritePoints = computed(() => hasPermission(permissions.POINT_WRITE))
  const canDeletePoints = computed(() => hasPermission(permissions.POINT_DELETE))

  const canReadAlarms = computed(() => hasPermission(permissions.ALARM_READ))
  const canWriteAlarms = computed(() => hasPermission(permissions.ALARM_WRITE))
  const canAckAlarms = computed(() => hasPermission(permissions.ALARM_ACK))

  const canReadConfig = computed(() => hasPermission(permissions.CONFIG_READ))
  const canWriteConfig = computed(() => hasPermission(permissions.CONFIG_WRITE))

  const canReadLogs = computed(() => hasPermission(permissions.LOG_READ))

  const canReadReports = computed(() => hasPermission(permissions.REPORT_READ))
  const canWriteReports = computed(() => hasPermission(permissions.REPORT_WRITE))

  return {
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
    hasRole,
    isAdmin,
    isOperator,
    isViewer,
    permissions,
    canReadUsers,
    canWriteUsers,
    canDeleteUsers,
    canReadPoints,
    canWritePoints,
    canDeletePoints,
    canReadAlarms,
    canWriteAlarms,
    canAckAlarms,
    canReadConfig,
    canWriteConfig,
    canReadLogs,
    canReadReports,
    canWriteReports
  }
}

export default usePermission
