import { expect, test as setup } from '@playwright/test'
import path from 'path'

const ADMIN_USER = 'admin'
const ADMIN_PASS = 'admin123'
const authFile = path.join(__dirname, '.auth', 'admin.json')

/**
 * 全局 setup：登录 admin 并保存认证状态
 * 后续所有测试复用此状态，避免重复登录触发限流
 */
setup('authenticate as admin', async ({ page }) => {
  await page.goto('/login')
  await page.waitForLoadState('networkidle')
  await page.locator('input').first().fill(ADMIN_USER)
  await page.locator('input[type="password"]').fill(ADMIN_PASS)

  const loginResponsePromise = page.waitForResponse(
    response => response.url().endsWith('/api/v1/auth/login') && response.request().method() === 'POST'
  )
  const currentUserResponsePromise = page.waitForResponse(
    response => response.url().endsWith('/api/v1/auth/me') && response.request().method() === 'GET'
  )
  await page.locator('button').filter({ hasText: '登' }).click()

  const [loginResponse, currentUserResponse] = await Promise.all([
    loginResponsePromise,
    currentUserResponsePromise
  ])
  expect(loginResponse.ok()).toBe(true)
  expect(currentUserResponse.ok()).toBe(true)
  await expect.poll(() => page.evaluate(() => localStorage.getItem('token'))).not.toBeNull()

  // 冷启动 Vite 可能在首次加载 Dashboard 依赖时刷新页面，显式导航可保持已认证路径。
  await page.goto('/dashboard')
  await expect(page).toHaveURL(/\/dashboard$/)

  // 保存认证状态（cookies + localStorage）
  await page.context().storageState({ path: authFile })
})
