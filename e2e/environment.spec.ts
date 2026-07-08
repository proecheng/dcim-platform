import { test, expect, type Page } from '@playwright/test'

/**
 * 环境监控 E2E 测试
 * 覆盖：环境总览、温湿度监测、水浸检测、烟雾/红外检测
 */

function routePattern(routePath: string): RegExp {
  return new RegExp(routePath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
}

async function gotoEnvironmentPage(page: Page, routePath: string) {
  await page.goto(routePath, { waitUntil: 'domcontentloaded' })
  await expect(page).toHaveURL(routePattern(routePath))
  await expect(page.locator('.el-main, main, .app-main').first()).toBeVisible({ timeout: 15000 })
}

async function expectAnySelector(page: Page, selectors: string[]) {
  await expect.poll(async () => {
    for (const selector of selectors) {
      if (await page.locator(selector).count() > 0) {
        return true
      }
    }
    return false
  }, { timeout: 15000 }).toBeTruthy()
}

test.describe('环境总览测试', () => {
  test('环境总览页面加载成功', async ({ page }) => {
    await gotoEnvironmentPage(page, '/environment/overview')

    expect(page.url()).toContain('/environment/overview')
  })

  test('环境总览包含子系统概览卡片', async ({ page }) => {
    await gotoEnvironmentPage(page, '/environment/overview')

    // 应有卡片或统计区域
    await expectAnySelector(page, ['.el-card', '.stat-card', '.overview-card'])
  })

  test('环境总览包含图表或数据展示', async ({ page }) => {
    await gotoEnvironmentPage(page, '/environment/overview')

    // 图表(canvas)或表格
    await expectAnySelector(page, ['canvas', '.el-table', '.el-card'])
  })
})

test.describe('温湿度监测测试', () => {
  test('温湿度监测页面加载成功', async ({ page }) => {
    await gotoEnvironmentPage(page, '/environment/temperature')

    expect(page.url()).toContain('/environment/temperature')
  })

  test('温湿度页面包含传感器数据展示', async ({ page }) => {
    await gotoEnvironmentPage(page, '/environment/temperature')

    // 传感器卡片或表格
    await expectAnySelector(page, ['.el-table', '.el-card', '.sensor-card'])
  })

  test('温湿度页面包含区域筛选（如存在）', async ({ page }) => {
    await gotoEnvironmentPage(page, '/environment/temperature')

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
    await gotoEnvironmentPage(page, '/environment/water-leak')

    expect(page.url()).toContain('/environment/water-leak')
  })

  test('水浸检测页面包含传感器状态列表', async ({ page }) => {
    await gotoEnvironmentPage(page, '/environment/water-leak')

    await expectAnySelector(page, ['.el-table', '.el-card', '.sensor-card', '.el-tag'])
  })

  test('水浸检测页面包含状态指示器', async ({ page }) => {
    await gotoEnvironmentPage(page, '/environment/water-leak')

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
    await gotoEnvironmentPage(page, '/environment/smoke-infrared')

    expect(page.url()).toContain('/environment/smoke-infrared')
  })

  test('烟雾/红外页面包含探测器状态展示', async ({ page }) => {
    await gotoEnvironmentPage(page, '/environment/smoke-infrared')

    await expectAnySelector(page, ['.el-table', '.el-card'])
  })

  test('烟雾/红外页面包含区域分组信息', async ({ page }) => {
    await gotoEnvironmentPage(page, '/environment/smoke-infrared')

    // 区域分组标签或筛选
    await expectAnySelector(page, ['.el-tag', '.el-select', '.el-card'])
  })
})
