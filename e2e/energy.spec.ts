import { test, expect } from '@playwright/test'

/**
 * 用电监控 E2E 测试
 * 认证状态由 auth.setup.ts 注入，无需重复登录
 */

test.describe('用电监控测试', () => {

  test('用电监控页面加载成功', async ({ page }) => {
    await page.goto('/power/monitor')
    await page.waitForLoadState('networkidle')

    await expect(page.locator('.energy-monitor')).toBeVisible()
  })

  test('6 个统计卡片可见', async ({ page }) => {
    await page.goto('/power/monitor')
    await page.waitForLoadState('networkidle')

    const statCards = page.locator('.energy-monitor .stat-cards .stat-card, .energy-monitor .stat-card')
    expect(await statCards.count()).toBeGreaterThanOrEqual(6)

    // 验证关键统计标签
    for (const label of ['总功率', 'IT负载', '制冷功率', 'PUE', '今日用电', '今日电费']) {
      await expect(
        page.locator('.energy-monitor').locator('.stat-card, .el-card').filter({ hasText: label }).first()
      ).toBeVisible()
    }
  })

  test('能耗统计页面加载成功', async ({ page }) => {
    await page.goto('/power/statistics')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    // 页面不应重定向到登录页
    expect(page.url()).toContain('/power/statistics')

    // 页面应有内容（表格、图表或卡片）
    const hasContent = await page.locator('.el-table, .el-card, canvas, .chart-container').first().isVisible().catch(() => false)
    expect(hasContent).toBeTruthy()
  })
})
