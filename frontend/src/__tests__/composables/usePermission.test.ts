/**
 * usePermission 组合式函数单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// Mock auth API
vi.mock('@/api/modules/auth', () => ({
  login: vi.fn(),
  logout: vi.fn(),
  getCurrentUser: vi.fn(),
  getPermissions: vi.fn()
}))

describe('usePermission', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  async function setup(role: string, perms: string[]) {
    const { useUserStore } = await import('@/stores/user')
    const { usePermission } = await import('@/composables/usePermission')
    const userStore = useUserStore()
    userStore.permissions = perms
    userStore.userInfo = {
      id: 1, username: 'test', real_name: '测试用户', email: 'test@test.com',
      phone: '13800000000', role, department: '运维部', avatar: '',
      is_active: true, last_login_at: '2026-01-01', permissions: perms
    }
    const perm = usePermission()
    return { userStore, perm }
  }

  it('hasPermission — 有权限时返回 true', async () => {
    const { perm } = await setup('admin', ['user:read', 'alarm:read'])
    expect(perm.hasPermission('user:read')).toBe(true)
  })

  it('hasPermission — 无权限时返回 false', async () => {
    const { perm } = await setup('viewer', ['user:read'])
    expect(perm.hasPermission('user:write')).toBe(false)
  })

  it('hasPermission — 权限列表为空时返回 false', async () => {
    const { perm } = await setup('viewer', [])
    expect(perm.hasPermission('user:read')).toBe(false)
  })

  it('hasAnyPermission — 匹配任一权限返回 true', async () => {
    const { perm } = await setup('operator', ['alarm:read'])
    expect(perm.hasAnyPermission(['user:write', 'alarm:read'])).toBe(true)
  })

  it('hasAnyPermission — 全部不匹配返回 false', async () => {
    const { perm } = await setup('viewer', ['log:read'])
    expect(perm.hasAnyPermission(['user:write', 'alarm:write'])).toBe(false)
  })

  it('hasAllPermissions — 全部匹配返回 true', async () => {
    const { perm } = await setup('admin', ['user:read', 'user:write', 'alarm:read'])
    expect(perm.hasAllPermissions(['user:read', 'user:write'])).toBe(true)
  })

  it('hasAllPermissions — 部分缺失返回 false', async () => {
    const { perm } = await setup('operator', ['user:read'])
    expect(perm.hasAllPermissions(['user:read', 'user:write'])).toBe(false)
  })

  it('hasRole — 角色匹配返回 true', async () => {
    const { perm } = await setup('admin', [])
    expect(perm.hasRole('admin')).toBe(true)
  })

  it('hasRole — 角色不匹配返回 false', async () => {
    const { perm } = await setup('viewer', [])
    expect(perm.hasRole('admin')).toBe(false)
  })

  it('isAdmin — admin 角色为 true', async () => {
    const { perm } = await setup('admin', [])
    expect(perm.isAdmin.value).toBe(true)
    expect(perm.isOperator.value).toBe(true)
    expect(perm.isViewer.value).toBe(true)
  })

  it('isOperator — operator 角色', async () => {
    const { perm } = await setup('operator', [])
    expect(perm.isAdmin.value).toBe(false)
    expect(perm.isOperator.value).toBe(true)
    expect(perm.isViewer.value).toBe(true)
  })

  it('isViewer — viewer 角色', async () => {
    const { perm } = await setup('viewer', [])
    expect(perm.isAdmin.value).toBe(false)
    expect(perm.isOperator.value).toBe(false)
    expect(perm.isViewer.value).toBe(true)
  })

  it('空角色 — 所有角色计算属性为 false', async () => {
    const { perm } = await setup('', [])
    expect(perm.isAdmin.value).toBe(false)
    expect(perm.isOperator.value).toBe(false)
    expect(perm.isViewer.value).toBe(false)
  })

  it('permissions 常量包含所有权限键', async () => {
    const { perm } = await setup('admin', [])
    expect(perm.permissions.USER_READ).toBe('user:read')
    expect(perm.permissions.USER_WRITE).toBe('user:write')
    expect(perm.permissions.USER_DELETE).toBe('user:delete')
    expect(perm.permissions.POINT_READ).toBe('point:read')
    expect(perm.permissions.ALARM_ACK).toBe('alarm:ack')
    expect(perm.permissions.CONFIG_WRITE).toBe('config:write')
    expect(perm.permissions.LOG_READ).toBe('log:read')
    expect(perm.permissions.REPORT_WRITE).toBe('report:write')
  })

  it('canReadUsers / canWriteUsers / canDeleteUsers', async () => {
    const { perm } = await setup('admin', ['user:read', 'user:write', 'user:delete'])
    expect(perm.canReadUsers.value).toBe(true)
    expect(perm.canWriteUsers.value).toBe(true)
    expect(perm.canDeleteUsers.value).toBe(true)
  })

  it('canReadAlarms / canWriteAlarms / canAckAlarms', async () => {
    const { perm } = await setup('operator', ['alarm:read', 'alarm:write', 'alarm:ack'])
    expect(perm.canReadAlarms.value).toBe(true)
    expect(perm.canWriteAlarms.value).toBe(true)
    expect(perm.canAckAlarms.value).toBe(true)
  })

  it('无权限时所有 canXxx 为 false', async () => {
    const { perm } = await setup('viewer', [])
    expect(perm.canReadUsers.value).toBe(false)
    expect(perm.canWriteUsers.value).toBe(false)
    expect(perm.canDeleteUsers.value).toBe(false)
    expect(perm.canReadPoints.value).toBe(false)
    expect(perm.canReadAlarms.value).toBe(false)
    expect(perm.canReadConfig.value).toBe(false)
    expect(perm.canReadLogs.value).toBe(false)
    expect(perm.canReadReports.value).toBe(false)
  })
})
