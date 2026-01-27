import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login, logout, getCurrentUser, getPermissions } from '@/api/modules/auth'

export interface UserInfo {
  id: number
  username: string
  real_name: string
  email: string
  phone: string
  role: string
  department: string
  avatar: string
  is_active: boolean
  last_login_at: string
  permissions: string[]
}

export const useUserStore = defineStore('user', () => {
  const token = ref<string>(localStorage.getItem('token') || '')
  const userInfo = ref<UserInfo | null>(null)
  const permissions = ref<string[]>([])

  // 计算属性
  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => userInfo.value?.role === 'admin')
  const isOperator = computed(() => ['admin', 'operator'].includes(userInfo.value?.role || ''))
  const role = computed(() => userInfo.value?.role || '')
  const username = computed(() => userInfo.value?.username || '')
  const realName = computed(() => userInfo.value?.real_name || userInfo.value?.username || '')

  // 登录
  async function doLogin(usernameVal: string, password: string) {
    const res = await login({ username: usernameVal, password })
    token.value = res.access_token
    localStorage.setItem('token', res.access_token)
    await fetchUserInfo()
    await fetchPermissions()
  }

  // 获取用户信息
  async function fetchUserInfo() {
    try {
      const res = await getCurrentUser()
      userInfo.value = res
    } catch (e) {
      console.error('获取用户信息失败:', e)
      throw e
    }
  }

  // 获取权限列表
  async function fetchPermissions() {
    try {
      const res = await getPermissions()
      permissions.value = res
    } catch (e) {
      console.error('获取权限失败:', e)
    }
  }

  // 登出
  async function doLogout() {
    try {
      await logout()
    } finally {
      token.value = ''
      userInfo.value = null
      permissions.value = []
      localStorage.removeItem('token')
    }
  }

  // 检查权限
  function hasPermission(permission: string): boolean {
    return permissions.value.includes(permission)
  }

  // 检查任意权限
  function hasAnyPermission(perms: string[]): boolean {
    return perms.some(p => permissions.value.includes(p))
  }

  // 初始化（从 localStorage 恢复）
  async function initFromStorage() {
    if (token.value) {
      try {
        await fetchUserInfo()
        await fetchPermissions()
      } catch (e) {
        // Token 无效，清除
        token.value = ''
        localStorage.removeItem('token')
      }
    }
  }

  return {
    token,
    userInfo,
    permissions,
    isLoggedIn,
    isAdmin,
    isOperator,
    role,
    username,
    realName,
    doLogin,
    fetchUserInfo,
    fetchPermissions,
    doLogout,
    hasPermission,
    hasAnyPermission,
    initFromStorage
  }
})
