import { test, expect, type Page } from '@playwright/test'

/**
 * 供配电 + 制冷 + 策略联动 + 智能诊断 + 虚拟电厂 E2E 测试
 * 覆盖所有子页面的加载验证和基础 UI 元素检查
 */

/** 通用页面加载验证：导航、URL 校验、主容器可见、至少一个 UI 元素 */
async function verifyPageLoad(page: Page, path: string) {
  await page.goto(path)
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(1000)
  expect(page.url()).toContain(path)
  const body = page.locator('.el-main, main, .app-main').first()
  await expect(body).toBeVisible({ timeout: 10000 })
  // 至少存在一个关键 UI 元素
  const hasUI =
    (await page.locator('.el-table').count()) > 0 ||
    (await page.locator('.el-card').count()) > 0 ||
    (await page.locator('canvas').count()) > 0 ||
    (await page.locator('.el-form').count()) > 0
  expect(hasUI).toBeTruthy()
}

// ══════ 供配电监控 ══════

test.describe('供配电子页面测试', () => {
  test('UPS 监控页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/power/ups')
  })

  test('电池组页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/power/battery')
  })

  test('配电柜页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/power/cabinet')
  })

  test('机柜 PDU 页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/power/pdu')
  })

  test('配电拓扑页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/power/topology')
  })
})

// ══════ 制冷监控 ══════

test.describe('制冷子页面测试', () => {
  test('精密空调页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/cooling/indoor')
  })

  test('室外机页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/cooling/outdoor')
  })

  test('冷通道页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/cooling/cold-aisle')
  })

  test('群控状态页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/cooling/group-control')
  })
})

// ══════ 策略联动 ══════

test.describe('策略联动测试', () => {
  test('联动策略页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/strategy/linkage/policy')
  })

  test('联动策略包含规则表格', async ({ page }) => {
    await page.goto('/strategy/linkage/policy')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    const hasTable = await page.locator('.el-table').count() > 0
    const hasCards = await page.locator('.el-card').count() > 0
    expect(hasTable || hasCards).toBeTruthy()
  })

  test('执行日志页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/strategy/linkage/execution')
  })

  test('联动恢复页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/strategy/linkage/recovery')
  })

  test('事件时间线页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/strategy/linkage/timeline')
  })

  test('命令管理页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/strategy/linkage/command')
  })
})

// ══════ 智能诊断 ══════

test.describe('智能诊断测试', () => {
  test('诊断结果页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/strategy/diagnosis/results')
  })

  test('诊断结果包含结果表格', async ({ page }) => {
    await page.goto('/strategy/diagnosis/results')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    const hasTable = await page.locator('.el-table').count() > 0
    const hasCards = await page.locator('.el-card').count() > 0
    expect(hasTable || hasCards).toBeTruthy()
  })

  test('诊断规则页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/strategy/diagnosis/rules')
  })
})

// ══════ 虚拟电厂 ══════

test.describe('虚拟电厂测试', () => {
  test('VPP 方案分析页面加载成功', async ({ page }) => {
    await verifyPageLoad(page, '/vpp/analysis')
  })

  test('VPP 页面包含分析图表或数据', async ({ page }) => {
    await page.goto('/vpp/analysis')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    const hasChart = await page.locator('canvas').count() > 0
    const hasTable = await page.locator('.el-table').count() > 0
    const hasCards = await page.locator('.el-card').count() > 0
    expect(hasChart || hasTable || hasCards).toBeTruthy()
  })
})
