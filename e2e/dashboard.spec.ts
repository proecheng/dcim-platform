import { test, expect } from '@playwright/test'

/**
 * 仪表盘 E2E 测试
 * 认证状态由 auth.setup.ts 注入，无需重复登录
 */

test.describe('仪表盘测试', () => {

  test('仪表盘页面加载成功', async ({ page }) => {
    await page.goto('/dashboard')
    await page.waitForLoadState('networkidle')

    await expect(page.locator('.dashboard')).toBeVisible()
  })

  test('4 个统计卡片可见', async ({ page }) => {
    await page.goto('/dashboard')
    await page.waitForLoadState('networkidle')

    const statCards = page.locator('.stat-cards .stat-card')
    await expect(statCards).toHaveCount(4)

    // 验证卡片标题文字
    for (const label of ['监控点位', '正常点位', '告警点位', '离线点位']) {
      await expect(page.locator('.stat-card').filter({ hasText: label }).first()).toBeVisible()
    }
  })

  test('快捷操作栏可见（3 个按钮）', async ({ page }) => {
    await page.goto('/dashboard')
    await page.waitForLoadState('networkidle')

    const quickActions = page.locator('.quick-actions')
    await expect(quickActions).toBeVisible()

    for (const btnText of ['打开数字孪生大屏', '演示数据', '刷新数据']) {
      await expect(quickActions.locator('button, .el-button').filter({ hasText: btnText })).toBeVisible()
    }
  })

  test('6 大域概览卡片可见', async ({ page }) => {
    await page.goto('/dashboard')
    await page.waitForLoadState('networkidle')

    const domainCards = page.locator('.domain-cards')
    await expect(domainCards).toBeVisible()

    // 6 大域: 供配电、制冷、环境、安防、基础设施、节能
    for (const domain of ['供配电', '制冷', '环境', '安防', '基础设施', '节能']) {
      await expect(domainCards.locator('.el-card, .domain-card').filter({ hasText: domain }).first()).toBeVisible()
    }
  })

  test('点击域卡片跳转到对应页面', async ({ page }) => {
    await page.goto('/dashboard')
    await page.waitForLoadState('networkidle')

    // 点击供配电域卡片
    const powerCard = page.locator('.domain-cards .domain-card').filter({ hasText: '供配电' }).first()
    await expect(powerCard).toBeVisible()
    await powerCard.scrollIntoViewIfNeeded()
    await powerCard.click()

    // 应跳转到供配电相关页面
    await expect(page).toHaveURL(/\/power\/overview/, { timeout: 15000 })
  })

  test('刷新数据按钮可点击', async ({ page }) => {
    await page.goto('/dashboard')
    await page.waitForLoadState('networkidle')

    const refreshBtn = page.locator('.quick-actions').locator('button, .el-button').filter({ hasText: '刷新数据' })
    await expect(refreshBtn).toBeVisible()
    await expect(refreshBtn).toBeEnabled()
    await refreshBtn.click()
    await page.waitForTimeout(1000)

    // 刷新后仪表盘仍然可见
    await expect(page.locator('.dashboard')).toBeVisible()
  })
})
