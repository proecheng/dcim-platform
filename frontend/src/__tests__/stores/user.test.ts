/**
 * User Store 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useUserStore } from '@/stores/user'

// Mock auth API
vi.mock('@/api/modules/auth', () => ({
  login: vi.fn().mockResolvedValue({ access_token: 'test-token', token_type: 'bearer', expires_in: 3600 }),
  logout: vi.fn().mockResolvedValue(undefined),
  getCurrentUser: vi.fn().mockResolvedValue({
    id: 1, username: 'admin', real_name: '管理员', email: 'admin@test.com',
    phone: '13800000000', role: 'admin', department: '运维部',
    avatar: '', is_active: true, last_login_at: '2026-01-01', permissions: ['user:read']
  }),
  getPermissions: vi.fn().mockResolvedValue(['user:read', 'user:write', 'alarm:read'])
}))

describe('useUserStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('初始状态 — 未登录', () => {
    const store = useUserStore()
    expect(store.isLoggedIn).toBe(false)
    expect(store.userInfo).toBeNull()
    expect(store.permissions).toEqual([])
  })

  it('doLogin 设置 token 并获取用户信息', async () => {
    const store = useUserStore()
    await store.doLogin('admin', 'admin123')

    expect(store.token).toBe('test-token')
    expect(store.isLoggedIn).toBe(true)
    expect(store.userInfo?.username).toBe('admin')
    expect(store.permissions).toContain('user:read')
    expect(localStorage.setItem).toHaveBeenCalledWith('token', 'test-token')
  })

  it('doLogout 清除所有状态', async () => {
    const store = useUserStore()
    await store.doLogin('admin', 'admin123')
    await store.doLogout()

    expect(store.token).toBe('')
    expect(store.isLoggedIn).toBe(false)
    expect(store.userInfo).toBeNull()
    expect(store.permissions).toEqual([])
    expect(localStorage.removeItem).toHaveBeenCalledWith('token')
  })

  it('isAdmin 计算属性', async () => {
    const store = useUserStore()
    await store.doLogin('admin', 'admin123')
    expect(store.isAdmin).toBe(true)
  })

  it('hasPermission 检查单个权限', async () => {
    const store = useUserStore()
    await store.doLogin('admin', 'admin123')

    expect(store.hasPermission('user:read')).toBe(true)
    expect(store.hasPermission('nonexistent')).toBe(false)
  })

  it('hasAnyPermission 检查任意权限', async () => {
    const store = useUserStore()
    await store.doLogin('admin', 'admin123')

    expect(store.hasAnyPermission(['user:read', 'nonexistent'])).toBe(true)
    expect(store.hasAnyPermission(['nonexistent1', 'nonexistent2'])).toBe(false)
  })

  it('initFromStorage 恢复登录状态', async () => {
    const store = useUserStore()
    // 模拟已有 token
    store.token = 'existing-token'
    await store.initFromStorage()

    expect(store.userInfo).not.toBeNull()
    expect(store.permissions.length).toBeGreaterThan(0)
  })

  it('initFromStorage 无 token 时不请求', async () => {
    const store = useUserStore()
    await store.initFromStorage()
    expect(store.userInfo).toBeNull()
  })
})
