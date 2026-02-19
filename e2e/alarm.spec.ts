import { test, expect, type Page } from '@playwright/test'

/**
 * 告警管理 E2E 测试
 * 认证状态由 auth.setup.ts 注入，无需重复登录
 */

/** 导航到告警页 */
async function gotoAlarms(page: Page) {
  await page.goto('/alarms')
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(1000)
}

test.describe('告警管理测试', () => {

  test('告警页面加载成功', async ({ page }) => {
    await gotoAlarms(page)

    await expect(page.locator('.alarm-page')).toBeVisible({ timeout: 10000 })
  })

  test('筛选表单可见', async ({ page }) => {
    await gotoAlarms(page)

    // 告警页有多个 tab，每个 tab 都有 .filter-form，定位到第一个（告警记录 tab，默认激活）
    const filterForm = page.locator('.filter-form').first()
    await expect(filterForm).toBeVisible({ timeout: 10000 })

    // 下拉框（告警状态、告警级别、设备类型）
    const selects = filterForm.locator('.el-select')
    expect(await selects.count()).toBeGreaterThanOrEqual(2)

    // 查询和重置按钮
    await expect(filterForm.locator('button, .el-button').filter({ hasText: /查询|搜索/ })).toBeVisible()
    await expect(filterForm.locator('button, .el-button').filter({ hasText: '重置' })).toBeVisible()
  })

  test('告警统计标签可见', async ({ page }) => {
    await gotoAlarms(page)

    const alarmStats = page.locator('.alarm-stats')
    await expect(alarmStats).toBeVisible({ timeout: 10000 })

    for (const level of ['紧急', '重要', '一般', '提示']) {
      await expect(alarmStats.getByText(level).first()).toBeVisible()
    }
  })

  test('告警表格可见，包含正确的列头', async ({ page }) => {
    await gotoAlarms(page)

    const table = page.locator('.alarm-page .el-table').first()
    await expect(table).toBeVisible({ timeout: 10000 })

    for (const col of ['级别', '点位编码', '点位名称', '告警内容', '触发值', '阈值', '状态', '告警时间']) {
      await expect(table.locator('th').filter({ hasText: col }).first()).toBeVisible()
    }
  })

  test('按级别筛选告警', async ({ page }) => {
    await gotoAlarms(page)

    const filterForm = page.locator('.filter-form').first()
    await expect(filterForm).toBeVisible({ timeout: 10000 })

    // 点击告警级别下拉框（第二个 select 通常是级别）
    const levelSelect = filterForm.locator('.el-select').nth(1)
    await levelSelect.click()
    await page.waitForTimeout(500)

    // 选择一个级别选项
    const option = page.locator('.el-select-dropdown__item').first()
    if (await option.isVisible()) {
      await option.click()
      await page.waitForTimeout(300)
    }

    // 点击查询
    await filterForm.locator('button, .el-button').filter({ hasText: /查询|搜索/ }).click()
    await page.waitForTimeout(1000)

    // 表格仍然可见（无论有无数据）
    await expect(page.locator('.alarm-page .el-table').first()).toBeVisible()
  })

  test('重置筛选条件', async ({ page }) => {
    await gotoAlarms(page)

    const filterForm = page.locator('.filter-form').first()
    await expect(filterForm).toBeVisible({ timeout: 10000 })

    // 先设置一个筛选条件
    const firstSelect = filterForm.locator('.el-select').first()
    await firstSelect.click()
    await page.waitForTimeout(500)
    const option = page.locator('.el-select-dropdown__item').first()
    if (await option.isVisible()) {
      await option.click()
      await page.waitForTimeout(300)
    }

    // 点击重置
    await filterForm.locator('button, .el-button').filter({ hasText: '重置' }).click()
    await page.waitForTimeout(1000)

    // 表格仍然可见
    await expect(page.locator('.alarm-page .el-table').first()).toBeVisible()
  })
})
