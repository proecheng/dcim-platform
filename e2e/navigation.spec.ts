import { test, expect } from '@playwright/test'

/**
 * 全局导航 E2E 测试
 * 认证状态由 auth.setup.ts 注入，无需重复登录
 */

test.describe('全局导航测试', () => {

  test('侧边栏菜单可见', async ({ page }) => {
    await page.goto('/dashboard')
    await page.waitForLoadState('networkidle')

    // 侧边栏导航
    const sidebar = page.locator('.el-aside, .sidebar, .el-menu, .nav-menu').first()
    await expect(sidebar).toBeVisible()
  })

  test('导航到主要页面 - 仪表盘', async ({ page }) => {
    await page.goto('/dashboard')
    await page.waitForLoadState('networkidle')

    await expect(page.locator('.dashboard')).toBeVisible()
    expect(page.url()).toContain('/dashboard')
  })

  test('导航到主要页面 - 点位管理', async ({ page }) => {
    await page.goto('/devices')
    await page.waitForLoadState('networkidle')

    await expect(page.locator('.device-page')).toBeVisible()
    expect(page.url()).toContain('/devices')
  })

  test('导航到主要页面 - 告警管理', async ({ page }) => {
    await page.goto('/alarms')
    await page.waitForLoadState('networkidle')

    await expect(page.locator('.alarm-page')).toBeVisible({ timeout: 10000 })
    expect(page.url()).toContain('/alarms')
  })

  test('导航到主要页面 - 历史数据', async ({ page }) => {
    await page.goto('/history')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    expect(page.url()).toContain('/history')
    // 页面应有内容
    const body = page.locator('.el-main, main, .history-page, .app-main').first()
    await expect(body).toBeVisible()
  })

  test('导航到主要页面 - 系统设置', async ({ page }) => {
    await page.goto('/settings')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    expect(page.url()).toContain('/settings')
    const body = page.locator('.el-main, main, .settings-page, .app-main').first()
    await expect(body).toBeVisible()
  })

  test('导航到供配电总览', async ({ page }) => {
    await page.goto('/power/overview')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    expect(page.url()).toContain('/power/overview')
    const body = page.locator('.el-main, main, .app-main').first()
    await expect(body).toBeVisible()
  })

  test('导航到用电监控', async ({ page }) => {
    await page.goto('/power/monitor')
    await page.waitForLoadState('networkidle')

    expect(page.url()).toContain('/power/monitor')
    await expect(page.locator('.energy-monitor')).toBeVisible()
  })

  test('导航到制冷总览', async ({ page }) => {
    await page.goto('/cooling/overview')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    expect(page.url()).toContain('/cooling/overview')
    const body = page.locator('.el-main, main, .app-main').first()
    await expect(body).toBeVisible()
  })

  test('导航到环境总览', async ({ page }) => {
    await page.goto('/environment/overview')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    expect(page.url()).toContain('/environment/overview')
    const body = page.locator('.el-main, main, .app-main').first()
    await expect(body).toBeVisible()
  })

  test('导航到安防总览', async ({ page }) => {
    await page.goto('/security/overview')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    expect(page.url()).toContain('/security/overview')
    const body = page.locator('.el-main, main, .app-main').first()
    await expect(body).toBeVisible()
  })

  test('导航到资产台账', async ({ page }) => {
    await page.goto('/infrastructure/asset')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    expect(page.url()).toContain('/infrastructure/asset')
    const body = page.locator('.el-main, main, .app-main').first()
    await expect(body).toBeVisible()
  })

  test('导航到节能分析', async ({ page }) => {
    await page.goto('/energy-saving/analysis')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    expect(page.url()).toContain('/energy-saving/analysis')
    const body = page.locator('.el-main, main, .app-main').first()
    await expect(body).toBeVisible()
  })

  test('导航到工单管理', async ({ page }) => {
    await page.goto('/operation/workorder')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    expect(page.url()).toContain('/operation/workorder')
    const body = page.locator('.el-main, main, .app-main').first()
    await expect(body).toBeVisible()
  })

  test('导航到用户管理', async ({ page }) => {
    await page.goto('/system/users')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    // 可能重定向到 /settings 下的用户管理 tab
    expect(page.url()).toMatch(/\/system\/users|\/settings/)
    const body = page.locator('.el-main, main, .app-main').first()
    await expect(body).toBeVisible()
  })
})
