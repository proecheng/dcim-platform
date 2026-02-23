import { test as setup } from '@playwright/test'
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
  await page.locator('button').filter({ hasText: '登' }).click()
  await page.waitForURL('**/dashboard', { timeout: 60000 })

  // 保存认证状态（cookies + localStorage）
  await page.context().storageState({ path: authFile })
})
