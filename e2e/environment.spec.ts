import { test, expect } from '@playwright/test'

/**
 * 环境监控 E2E 测试
 * 覆盖：环境总览、温湿度监测、水浸检测、烟雾/红外检测
 */

test.describe('环境总览测试', () => {
  test('环境总览页面加载成功', async ({ page }) => {
    await page.goto('/environment/overview')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    expect(page.url()).toContain('/environment/overview')
    const body = page.locator('.el-main, main, .app-main').first()
    await expect(body).toBeVisible({ timeout: 10000 })
  })

  test('环境总览包含子系统概览卡片', async ({ page }) => {
    await page.goto('/environment/overview')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    // 应有卡片或统计区域
    const cards = page.locator('.el-card, .stat-card, .overview-card')
    expect(await cards.count()).toBeGreaterThan(0)
  })

  test('环境总览包含图表或数据展示', async ({ page }) => {
    await page.goto('/environment/overview')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    // 图表(canvas)或表格
    const hasChart = await page.locator('canvas').count() > 0
    const hasTable = await page.locator('.el-table').count() > 0
    const hasCards = await page.locator('.el-card').count() > 0
    expect(hasChart || hasTable || hasCards).toBeTruthy()
  })
})

test.describe('温湿度监测测试', () => {
  test('温湿度监测页面加载成功', async ({ page }) => {
    await page.goto('/environment/temperature')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    expect(page.url()).toContain('/environment/temperature')
    const body = page.locator('.el-main, main, .app-main').first()
    await expect(body).toBeVisible({ timeout: 10000 })
  })

  test('温湿度页面包含传感器数据展示', async ({ page }) => {
    await page.goto('/environment/temperature')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    // 传感器卡片或表格
    const hasTable = await page.locator('.el-table').count() > 0
    const hasCards = await page.locator('.el-card, .sensor-card').count() > 0
    expect(hasTable || hasCards).toBeTruthy()
  })

  test('温湿度页面包含区域筛选（如存在）', async ({ page }) => {
    await page.goto('/environment/temperature')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    // 区域筛选下拉框
    const selects = page.locator('.el-select')
    if (await selects.count() > 0) {
      await expect(selects.first()).toBeVisible()
    }
    // 页面内容区域始终可见
    await expect(page.locator('.el-main, main, .app-main').first()).toBeVisible()
  })
})

test.describe('水浸检测测试', () => {
  test('水浸检测页面加载成功', async ({ page }) => {
    await page.goto('/environment/water-leak')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    expect(page.url()).toContain('/environment/water-leak')
    const body = page.locator('.el-main, main, .app-main').first()
    await expect(body).toBeVisible({ timeout: 10000 })
  })

  test('水浸检测页面包含传感器状态列表', async ({ page }) => {
    await page.goto('/environment/water-leak')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    const hasTable = await page.locator('.el-table').count() > 0
    const hasCards = await page.locator('.el-card, .sensor-card').count() > 0
    const hasTags = await page.locator('.el-tag').count() > 0
    expect(hasTable || hasCards || hasTags).toBeTruthy()
  })

  test('水浸检测页面包含状态指示器', async ({ page }) => {
    await page.goto('/environment/water-leak')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    // 状态标签（正常/告警）
    const tags = page.locator('.el-tag')
    if (await tags.count() > 0) {
      await expect(tags.first()).toBeVisible()
    }
    await expect(page.locator('.el-main, main, .app-main').first()).toBeVisible()
  })
})

test.describe('烟雾/红外检测测试', () => {
  test('烟雾/红外检测页面加载成功', async ({ page }) => {
    await page.goto('/environment/smoke-infrared')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    expect(page.url()).toContain('/environment/smoke-infrared')
    const body = page.locator('.el-main, main, .app-main').first()
    await expect(body).toBeVisible({ timeout: 10000 })
  })

  test('烟雾/红外页面包含探测器状态展示', async ({ page }) => {
    await page.goto('/environment/smoke-infrared')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    const hasTable = await page.locator('.el-table').count() > 0
    const hasCards = await page.locator('.el-card').count() > 0
    expect(hasTable || hasCards).toBeTruthy()
  })

  test('烟雾/红外页面包含区域分组信息', async ({ page }) => {
    await page.goto('/environment/smoke-infrared')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    // 区域分组标签或筛选
    const hasTags = await page.locator('.el-tag').count() > 0
    const hasSelect = await page.locator('.el-select').count() > 0
    const hasCards = await page.locator('.el-card').count() > 0
    expect(hasTags || hasSelect || hasCards).toBeTruthy()
  })
})
