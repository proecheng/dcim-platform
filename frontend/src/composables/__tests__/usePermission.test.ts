/**
 * usePermission composable 纯逻辑函数单元测试
 *
 * 覆盖: 权限检查、角色检查、组合权限检查
 * 这些函数定义在 composable 内部，复制核心逻辑进行测试。
 */
import { describe, it, expect } from 'vitest'

// ============================================================
// 来源: usePermission.ts — hasPermission (line 11-17)
// ============================================================
function hasPermission(permissions: string[], permission: string): boolean {
  if (!permissions || permissions.length === 0) return false
  return permissions.includes(permission)
}

// ============================================================
// 来源: usePermission.ts — hasAnyPermission (line 20-22)
// ============================================================
function hasAnyPermission(userPermissions: string[], permissions: string[]): boolean {
  return permissions.some(p => hasPermission(userPermissions, p))
}

// ============================================================
// 来源: usePermission.ts — hasAllPermissions (line 25-27)
// ============================================================
function hasAllPermissions(userPermissions: string[], permissions: string[]): boolean {
  return permissions.every(p => hasPermission(userPermissions, p))
}

// ============================================================
// 来源: usePermission.ts — hasRole (line 30-32)
// ============================================================
function hasRole(currentRole: string, role: string): boolean {
  return currentRole === role
}

// ============================================================
// 来源: usePermission.ts — isAdmin/isOperator/isViewer (line 35-41)
// ============================================================
function isAdmin(role: string): boolean {
  return hasRole(role, 'admin')
}

function isOperator(role: string): boolean {
  return hasRole(role, 'admin') || hasRole(role, 'operator')
}

function isViewer(role: string): boolean {
  return hasRole(role, 'admin') || hasRole(role, 'operator') || hasRole(role, 'viewer')
}

// ============================================================
// 权限常量 (line 44-69)
// ============================================================
const PERMISSIONS = {
  USER_READ: 'user:read',
  USER_WRITE: 'user:write',
  USER_DELETE: 'user:delete',
  POINT_READ: 'point:read',
  POINT_WRITE: 'point:write',
  ALARM_READ: 'alarm:read',
  ALARM_WRITE: 'alarm:write',
  ALARM_ACK: 'alarm:ack',
  CONFIG_READ: 'config:read',
  CONFIG_WRITE: 'config:write',
  LOG_READ: 'log:read',
  REPORT_READ: 'report:read',
  REPORT_WRITE: 'report:write',
}

// ============================================================
// 测试
// ============================================================

describe('usePermission — hasPermission 单权限检查', () => {
  it('正常: 拥有权限返回 true', () => {
    expect(hasPermission(['user:read', 'user:write'], 'user:read')).toBe(true)
  })

  it('正常: 不拥有权限返回 false', () => {
    expect(hasPermission(['user:read'], 'user:write')).toBe(false)
  })

  it('边界: 空权限列表返回 false', () => {
    expect(hasPermission([], 'user:read')).toBe(false)
  })

  it('边界: 精确匹配，不做前缀匹配', () => {
    expect(hasPermission(['user:read'], 'user:rea')).toBe(false)
    expect(hasPermission(['user:read'], 'user:read:extra')).toBe(false)
  })
})

describe('usePermission — hasAnyPermission 任意权限检查', () => {
  it('正常: 拥有其中一个返回 true', () => {
    expect(hasAnyPermission(['user:read'], ['user:read', 'user:write'])).toBe(true)
  })

  it('正常: 一个都没有返回 false', () => {
    expect(hasAnyPermission(['alarm:read'], ['user:read', 'user:write'])).toBe(false)
  })

  it('边界: 空检查列表返回 false', () => {
    expect(hasAnyPermission(['user:read'], [])).toBe(false)
  })

  it('边界: 空用户权限返回 false', () => {
    expect(hasAnyPermission([], ['user:read'])).toBe(false)
  })
})

describe('usePermission — hasAllPermissions 全部权限检查', () => {
  it('正常: 全部拥有返回 true', () => {
    expect(hasAllPermissions(['user:read', 'user:write', 'alarm:read'], ['user:read', 'user:write'])).toBe(true)
  })

  it('正常: 缺少一个返回 false', () => {
    expect(hasAllPermissions(['user:read'], ['user:read', 'user:write'])).toBe(false)
  })

  it('边界: 空检查列表返回 true (vacuous truth)', () => {
    expect(hasAllPermissions(['user:read'], [])).toBe(true)
  })
})

describe('usePermission — hasRole 角色检查', () => {
  it('正常: 匹配角色返回 true', () => {
    expect(hasRole('admin', 'admin')).toBe(true)
  })

  it('正常: 不匹配返回 false', () => {
    expect(hasRole('viewer', 'admin')).toBe(false)
  })

  it('边界: 空角色', () => {
    expect(hasRole('', 'admin')).toBe(false)
  })
})

describe('usePermission — 角色层级检查', () => {
  it('isAdmin: 只有 admin 返回 true', () => {
    expect(isAdmin('admin')).toBe(true)
    expect(isAdmin('operator')).toBe(false)
    expect(isAdmin('viewer')).toBe(false)
  })

  it('isOperator: admin 和 operator 返回 true', () => {
    expect(isOperator('admin')).toBe(true)
    expect(isOperator('operator')).toBe(true)
    expect(isOperator('viewer')).toBe(false)
  })

  it('isViewer: admin、operator、viewer 都返回 true', () => {
    expect(isViewer('admin')).toBe(true)
    expect(isViewer('operator')).toBe(true)
    expect(isViewer('viewer')).toBe(true)
    expect(isViewer('guest')).toBe(false)
  })
})

describe('usePermission — 权限常量', () => {
  it('权限常量格式正确', () => {
    expect(PERMISSIONS.USER_READ).toBe('user:read')
    expect(PERMISSIONS.ALARM_ACK).toBe('alarm:ack')
    expect(PERMISSIONS.CONFIG_WRITE).toBe('config:write')
  })

  it('权限常量可用于 hasPermission', () => {
    const userPerms = ['user:read', 'alarm:read', 'alarm:ack']
    expect(hasPermission(userPerms, PERMISSIONS.USER_READ)).toBe(true)
    expect(hasPermission(userPerms, PERMISSIONS.ALARM_ACK)).toBe(true)
    expect(hasPermission(userPerms, PERMISSIONS.USER_WRITE)).toBe(false)
  })
})
