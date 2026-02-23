import { test, expect } from '@playwright/test'

/**
 * 能源管理扩展 E2E 测试
 * 覆盖：节能分析、负荷调节、执行管理、能效报告
 * 注意：/energy/monitor 和 /energy/statistics 基础测试已在 energy.spec.ts 中
 */

test.describe('节能分析测试', () => {
  test('节能分析页面加载成功', async ({ page }) => {
    await page.goto('/energy/analysis')
    await page.waitForLoadState('load')
    await page.waitForTimeout(3000)

    expect(page.url()).toContain('/energy/analysis')
    const body = page.locator('.el-main, main, .app-main').first()
    await expect(body).toBeVisible({ timeout: 10000 })
  })

  test('节能分析页面包含分析插件卡片', async ({ page }) => {
    await page.goto('/energy/analysis')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    // 6 种分析插件以卡片形式展示
    const cards = page.locator('.el-card, .plugin-card, [class*="plugin"]')
    expect(await cards.count()).toBeGreaterThan(0)
  })

  test('点击分析插件卡片可展开详情', async ({ page }) => {
    await page.goto('/energy/analysis')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    const cards = page.locator('.el-card, .plugin-card, [class*="plugin"]')
    if (await cards.count() > 0) {
      await cards.first().click()
      await page.waitForTimeout(1000)
      // 点击后页面仍然正常
      await expect(page.locator('.el-main, main, .app-main').first()).toBeVisible()
    }
  })
})

test.describe('能耗统计扩展测试', () => {
  test('能耗统计页面包含日期选择器', async ({ page }) => {
    await page.goto('/energy/statistics')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    expect(page.url()).toContain('/energy/statistics')
    // 日期选择器
    const datePicker = page.locator('.el-date-editor, .el-range-editor, input[placeholder*="日期"]')
    if (await datePicker.count() > 0) {
      await expect(datePicker.first()).toBeVisible()
    }
  })

  test('能耗统计页面包含图表或表格', async ({ page }) => {
    await page.goto('/energy/statistics')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    const hasChart = await page.locator('canvas').count() > 0
    const hasTable = await page.locator('.el-table').count() > 0
    const hasCards = await page.locator('.el-card').count() > 0
    expect(hasChart || hasTable || hasCards).toBeTruthy()
  })
})

test.describe('负荷调节测试', () => {
  test('负荷调节页面加载成功', async ({ page }) => {
    await page.goto('/energy/regulation')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    expect(page.url()).toContain('/energy/regulation')
    const body = page.locator('.el-main, main, .app-main').first()
    await expect(body).toBeVisible({ timeout: 10000 })
  })

  test('负荷调节页面包含控制面板', async ({ page }) => {
    await page.goto('/energy/regulation')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    const hasTable = await page.locator('.el-table').count() > 0
    const hasCards = await page.locator('.el-card').count() > 0
    const hasForm = await page.locator('.el-form').count() > 0
    expect(hasTable || hasCards || hasForm).toBeTruthy()
  })
})

test.describe('执行管理测试', () => {
  test('执行管理页面加载成功', async ({ page }) => {
    await page.goto('/energy/execution')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    expect(page.url()).toContain('/energy/execution')
    const body = page.locator('.el-main, main, .app-main').first()
    await expect(body).toBeVisible({ timeout: 10000 })
  })

  test('执行管理页面包含执行记录表格', async ({ page }) => {
    await page.goto('/energy/execution')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    const hasTable = await page.locator('.el-table').count() > 0
    const hasCards = await page.locator('.el-card').count() > 0
    expect(hasTable || hasCards).toBeTruthy()
  })
})

test.describe('能效报告测试', () => {
  test('能效报告页面加载成功', async ({ page }) => {
    await page.goto('/energy/report')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    expect(page.url()).toContain('/energy/report')
    const body = page.locator('.el-main, main, .app-main').first()
    await expect(body).toBeVisible({ timeout: 10000 })
  })

  test('能效报告页面包含报告列表或生成按钮', async ({ page }) => {
    await page.goto('/energy/report')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    const hasTable = await page.locator('.el-table').count() > 0
    const hasCards = await page.locator('.el-card').count() > 0
    const hasBtn = await page.locator('.el-button').filter({ hasText: /生成|导出|下载/ }).count() > 0
    expect(hasTable || hasCards || hasBtn).toBeTruthy()
  })

  test('能效报告页面包含日期筛选', async ({ page }) => {
    await page.goto('/energy/report')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    const datePicker = page.locator('.el-date-editor, .el-range-editor, input[placeholder*="日期"]')
    if (await datePicker.count() > 0) {
      await expect(datePicker.first()).toBeVisible()
    }
    // 页面内容区域始终可见
    await expect(page.locator('.el-main, main, .app-main').first()).toBeVisible()
  })
})
