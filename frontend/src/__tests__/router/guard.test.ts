/**
 * 路由守卫单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createRouter, createWebHistory, createMemoryHistory } from 'vue-router'
import { setActivePinia, createPinia } from 'pinia'
import { useUserStore } from '@/stores/user'

// Mock auth API (user store 依赖)
vi.mock('@/api/modules/auth', () => ({
  login: vi.fn().mockResolvedValue({ access_token: 'tok', token_type: 'bearer', expires_in: 3600 }),
  logout: vi.fn().mockResolvedValue(undefined),
  getCurrentUser: vi.fn().mockResolvedValue({
    id: 1, username: 'admin', real_name: '管理员', email: '', phone: '',
    role: 'admin', department: '', avatar: '', is_active: true,
    last_login_at: '', permissions: []
  }),
  getPermissions: vi.fn().mockResolvedValue([])
}))

function createTestRouter(userStore: ReturnType<typeof useUserStore>) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', name: 'Login', component: { template: '<div>Login</div>' }, meta: { requiresAuth: false } },
      { path: '/bigscreen', name: 'Bigscreen', component: { template: '<div>Bigscreen</div>' }, meta: { requiresAuth: false } },
      { path: '/', name: 'Home', component: { template: '<div>Home</div>' } },
      { path: '/dashboard', name: 'Dashboard', component: { template: '<div>Dashboard</div>' } }
    ]
  })

  // 复制项目中的路由守卫逻辑
  router.beforeEach((to, _from, next) => {
    if (to.meta.requiresAuth !== false && !userStore.token) {
      next('/login')
    } else {
      next()
    }
  })

  return router
}

describe('路由守卫', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('未登录访问受保护路由 → 跳转 /login', async () => {
    const userStore = useUserStore()
    const router = createTestRouter(userStore)

    await router.push('/dashboard')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('已登录访问受保护路由 → 正常放行', async () => {
    const userStore = useUserStore()
    userStore.token = 'valid-token'
    const router = createTestRouter(userStore)

    await router.push('/dashboard')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('未登录访问 requiresAuth=false 路由 → 正常放行', async () => {
    const userStore = useUserStore()
    const router = createTestRouter(userStore)

    await router.push('/login')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('未登录访问 /bigscreen → 正常放行', async () => {
    const userStore = useUserStore()
    const router = createTestRouter(userStore)

    await router.push('/bigscreen')
    await router.isReady()

    expect(router.currentRoute.value.path).toBe('/bigscreen')
  })
})
