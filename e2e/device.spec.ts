import { test, expect } from '@playwright/test'

/**
 * 点位管理 E2E 测试
 * 认证状态由 auth.setup.ts 注入，无需重复登录
 */

test.describe('点位管理测试', () => {

  test('点位管理页面加载成功', async ({ page }) => {
    await page.goto('/devices')
    await page.waitForLoadState('networkidle')

    await expect(page.locator('.device-page')).toBeVisible()
  })

  test('筛选表单可见', async ({ page }) => {
    await page.goto('/devices')
    await page.waitForLoadState('networkidle')

    const devicePage = page.locator('.device-page')

    // 点位类型下拉框
    const selects = devicePage.locator('.el-select')
    expect(await selects.count()).toBeGreaterThanOrEqual(1)

    // 搜索输入框
    const searchInput = devicePage.locator('input[placeholder*="搜索"], input[placeholder*="关键字"], input[placeholder*="点位"]')
    await expect(searchInput.first()).toBeVisible()
  })

  test('新增点位按钮可见', async ({ page }) => {
    await page.goto('/devices')
    await page.waitForLoadState('networkidle')

    await expect(
      page.locator('.device-page button, .device-page .el-button').filter({ hasText: /新增|添加/ })
    ).toBeVisible()
  })

  test('点位表格可见', async ({ page }) => {
    await page.goto('/devices')
    await page.waitForLoadState('networkidle')

    const table = page.locator('.device-page .el-table')
    await expect(table).toBeVisible()

    // 至少有一些列头
    expect(await table.locator('th').count()).toBeGreaterThanOrEqual(3)
  })

  test('按类型筛选点位', async ({ page }) => {
    await page.goto('/devices')
    await page.waitForLoadState('networkidle')

    const devicePage = page.locator('.device-page')

    // 点击类型下拉框
    const typeSelect = devicePage.locator('.el-select').first()
    await typeSelect.click()
    await page.waitForTimeout(500)

    // 选择 AI 类型
    const aiOption = page.locator('.el-select-dropdown__item').filter({ hasText: 'AI' })
    if (await aiOption.isVisible()) {
      await aiOption.click()
      await page.waitForTimeout(500)
    } else {
      // 选择第一个可用选项
      const firstOption = page.locator('.el-select-dropdown__item').first()
      if (await firstOption.isVisible()) {
        await firstOption.click()
        await page.waitForTimeout(500)
      }
    }

    // 表格仍然可见
    await expect(page.locator('.device-page .el-table')).toBeVisible()
  })

  test('搜索点位', async ({ page }) => {
    await page.goto('/devices')
    await page.waitForLoadState('networkidle')

    const devicePage = page.locator('.device-page')
    const searchInput = devicePage.locator('input[placeholder*="搜索"], input[placeholder*="关键字"], input[placeholder*="点位"]').first()

    await searchInput.fill('温度')
    await page.waitForTimeout(500)

    // 触发搜索（按回车或点击搜索按钮）
    const searchBtn = devicePage.locator('button, .el-button').filter({ hasText: /搜索|查询/ })
    if (await searchBtn.isVisible()) {
      await searchBtn.click()
    } else {
      await searchInput.press('Enter')
    }
    await page.waitForTimeout(1000)

    // 表格仍然可见
    await expect(page.locator('.device-page .el-table')).toBeVisible()
  })
})
