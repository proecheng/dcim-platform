import { test, expect, type Page } from '@playwright/test'

/**
 * 资产运维 + 系统管理 + 采集配置 E2E 测试
 * 覆盖：资产台账、机柜管理、容量管理、空间拓扑、工单、巡检、知识库、
 *       报表、历史数据、站点管理、操作审计、系统设置、智能选址、
 *       设备管理、数据源、设备模板、网关管理
 */

/** 通用页面加载验证 */
async function verifyPageLoad(page: Page, path: string) {
  await page.goto(path)
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(1000)
  expect(page.url()).toContain(path)
  const body = page.locator('.el-main, main, .app-main').first()
  await expect(body).toBeVisible({ timeout: 10000 })
}

// ══════ 资产与容量 ══════

test.describe('资产与容量测试', () => {
  test('资产台账页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/asset/list')
  })

  test('资产台账包含资产表格', async ({ page }) => {
    await page.goto('/asset/list')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    const hasTable = await page.locator('.el-table').count() > 0
    const hasCards = await page.locator('.el-card').count() > 0
    expect(hasTable || hasCards).toBeTruthy()
  })

  test('机柜管理页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/asset/cabinet')
  })

  test('容量管理页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/asset/capacity')
  })

  test('空间拓扑页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/asset/spatial')
  })
})

// ══════ 运维管理 ══════

test.describe('运维管理测试', () => {
  test('工单管理页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/operation/workorder')
  })

  test('工单管理包含工单表格和操作按钮', async ({ page }) => {
    await page.goto('/operation/workorder')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    const hasTable = await page.locator('.el-table').count() > 0
    const hasCards = await page.locator('.el-card').count() > 0
    expect(hasTable || hasCards).toBeTruthy()

    // 新建工单按钮
    const addBtn = page.locator('.el-button').filter({ hasText: /新增|新建|创建/ })
    if (await addBtn.count() > 0) {
      await expect(addBtn.first()).toBeVisible()
    }
  })

  test('巡检管理页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/operation/inspection')
  })

  test('知识库页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/operation/knowledge')
  })

  test('报表分析页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/operation/reports')
  })

  test('历史数据页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/operation/history')
  })
})

// ══════ 系统管理 ══════

test.describe('系统管理测试', () => {
  // 注意：用户管理详细测试在 user-management.spec.ts 中，这里只做基础加载
  test('用户管理页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/system/users')
  })

  test('站点管理页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/system/sites')
  })

  test('站点管理包含站点列表', async ({ page }) => {
    await page.goto('/system/sites')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    const hasTable = await page.locator('.el-table').count() > 0
    const hasCards = await page.locator('.el-card').count() > 0
    expect(hasTable || hasCards).toBeTruthy()
  })

  test('操作审计页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/system/audit-log')
  })

  test('操作审计包含日志表格', async ({ page }) => {
    await page.goto('/system/audit-log')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    const hasTable = await page.locator('.el-table').count() > 0
    expect(hasTable).toBeTruthy()
  })

  test('系统设置页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/system/settings')
  })

  test('智能选址页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/system/site-selection')
  })
})

// ══════ 采集配置 ══════

test.describe('采集配置测试', () => {
  test('设备管理页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/collection/device-manage')
  })

  test('设备管理包含设备表格', async ({ page }) => {
    await page.goto('/collection/device-manage')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    const hasTable = await page.locator('.el-table').count() > 0
    const hasCards = await page.locator('.el-card').count() > 0
    expect(hasTable || hasCards).toBeTruthy()
  })

  test('数据源管理页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/collection/datasources')
  })

  test('设备模板页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/collection/device-templates')
  })

  test('网关管理页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/collection/gateway')
  })

  test('网关管理包含网关列表', async ({ page }) => {
    await page.goto('/collection/gateway')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    const hasTable = await page.locator('.el-table').count() > 0
    const hasCards = await page.locator('.el-card').count() > 0
    expect(hasTable || hasCards).toBeTruthy()
  })
})
