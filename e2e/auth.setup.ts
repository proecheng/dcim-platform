import { expect, test as setup } from '@playwright/test'
import path from 'path'

const ADMIN_USER = process.env.E2E_ADMIN_USER || 'admin'
const ADMIN_PASS = process.env.E2E_ADMIN_PASSWORD || 'admin123'
const authFile = process.env.E2E_AUTH_FILE || path.join(__dirname, '.auth', 'admin.json')

function matchesResponse(responseURL: string, origin: string, pathname: string): boolean {
  const url = new URL(responseURL)
  return url.origin === origin && url.pathname.replace(/\/$/, '') === pathname
}

/**
 * 全局 setup：登录 admin 并保存认证状态
 * 后续所有测试复用此状态，避免重复登录触发限流
 */
setup('authenticate as admin', async ({ page, baseURL }) => {
  if (!baseURL) throw new Error('Playwright baseURL is required')
  const appOrigin = new URL(baseURL).origin

  await page.goto('/login')
  await page.waitForLoadState('networkidle')
  await page.locator('input').first().fill(ADMIN_USER)
  await page.locator('input[type="password"]').fill(ADMIN_PASS)

  const loginResponsePromise = page.waitForResponse(
    response =>
      matchesResponse(response.url(), appOrigin, '/api/v1/auth/login') && response.request().method() === 'POST',
    { timeout: 60000 }
  )
  const currentUserResponsePromise = page.waitForResponse(
    response => matchesResponse(response.url(), appOrigin, '/api/v1/auth/me') && response.request().method() === 'GET',
    { timeout: 60000 }
  )
  await page.locator('button').filter({ hasText: '登' }).click()

  const [loginResponse, currentUserResponse] = await Promise.all([
    loginResponsePromise,
    currentUserResponsePromise
  ])
  expect(loginResponse.ok()).toBe(true)
  expect(currentUserResponse.ok()).toBe(true)
  await expect.poll(
    async () => {
      const token = await page.evaluate(() => localStorage.getItem('token'))
      return token?.split('.').length === 3 && token.split('.').every(Boolean)
    },
    { timeout: 60000 }
  ).toBe(true)

  await expect(page).toHaveURL(/\/dashboard$/, { timeout: 60000 })
  await expect(page.locator('.dashboard')).toBeVisible({ timeout: 60000 })

  // 保存认证状态（cookies + localStorage）
  await page.context().storageState({ path: authFile })
})
