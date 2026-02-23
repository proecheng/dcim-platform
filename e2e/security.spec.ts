import { test, expect } from '@playwright/test'

/**
 * 安防消防 E2E 测试
 * 覆盖：安防总览、门禁管理、消防联动、摄像头管理、视频控制、告警回放
 */

test.describe('安防总览测试', () => {
  test('安防总览页面加载成功', async ({ page }) => {
    await page.goto('/security/overview')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    expect(page.url()).toContain('/security/overview')
    const body = page.locator('.el-main, main, .app-main').first()
    await expect(body).toBeVisible({ timeout: 10000 })
  })

  test('安防总览包含概览卡片或表格', async ({ page }) => {
    await page.goto('/security/overview')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    const hasCards = await page.locator('.el-card').count() > 0
    const hasTable = await page.locator('.el-table').count() > 0
    expect(hasCards || hasTable).toBeTruthy()
  })
})

test.describe('门禁管理测试', () => {
  test('门禁管理页面加载成功', async ({ page }) => {
    await page.goto('/security/access-control')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    expect(page.url()).toContain('/security/access-control')
    const body = page.locator('.el-main, main, .app-main').first()
    await expect(body).toBeVisible({ timeout: 10000 })
  })

  test('门禁管理页面包含门禁表格', async ({ page }) => {
    await page.goto('/security/access-control')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    const hasTable = await page.locator('.el-table').count() > 0
    const hasCards = await page.locator('.el-card').count() > 0
    expect(hasTable || hasCards).toBeTruthy()
  })

  test('门禁管理页面包含状态指示器', async ({ page }) => {
    await page.goto('/security/access-control')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    // 状态标签或开关
    const hasTags = await page.locator('.el-tag').count() > 0
    const hasSwitch = await page.locator('.el-switch').count() > 0
    const hasTable = await page.locator('.el-table').count() > 0
    expect(hasTags || hasSwitch || hasTable).toBeTruthy()
  })
})

test.describe('消防联动测试', () => {
  test('消防联动页面加载成功', async ({ page }) => {
    await page.goto('/security/fire-linkage')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    expect(page.url()).toContain('/security/fire-linkage')
    const body = page.locator('.el-main, main, .app-main').first()
    await expect(body).toBeVisible({ timeout: 10000 })
  })

  test('消防联动页面包含联动规则表格', async ({ page }) => {
    await page.goto('/security/fire-linkage')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    const hasTable = await page.locator('.el-table').count() > 0
    const hasCards = await page.locator('.el-card').count() > 0
    expect(hasTable || hasCards).toBeTruthy()
  })
})

test.describe('摄像头管理测试', () => {
  test('摄像头管理页面加载成功', async ({ page }) => {
    await page.goto('/security/video/cameras')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    expect(page.url()).toContain('/security/video/cameras')
    const body = page.locator('.el-main, main, .app-main').first()
    await expect(body).toBeVisible({ timeout: 10000 })
  })

  test('摄像头管理页面包含摄像头列表', async ({ page }) => {
    await page.goto('/security/video/cameras')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    const hasTable = await page.locator('.el-table').count() > 0
    const hasCards = await page.locator('.el-card').count() > 0
    expect(hasTable || hasCards).toBeTruthy()
  })
})

test.describe('视频控制测试', () => {
  test('视频控制页面加载成功', async ({ page }) => {
    await page.goto('/security/video/control')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    expect(page.url()).toContain('/security/video/control')
    const body = page.locator('.el-main, main, .app-main').first()
    await expect(body).toBeVisible({ timeout: 10000 })
  })

  test('视频控制页面包含控制面板', async ({ page }) => {
    await page.goto('/security/video/control')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    const hasCards = await page.locator('.el-card').count() > 0
    const hasTable = await page.locator('.el-table').count() > 0
    const hasButtons = await page.locator('.el-button').count() > 0
    expect(hasCards || hasTable || hasButtons).toBeTruthy()
  })
})

test.describe('告警回放测试', () => {
  test('告警回放页面加载成功', async ({ page }) => {
    await page.goto('/security/video/playback')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    expect(page.url()).toContain('/security/video/playback')
    const body = page.locator('.el-main, main, .app-main').first()
    await expect(body).toBeVisible({ timeout: 10000 })
  })

  test('告警回放页面包含回放列表或时间线', async ({ page }) => {
    await page.goto('/security/video/playback')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    const hasTable = await page.locator('.el-table').count() > 0
    const hasCards = await page.locator('.el-card').count() > 0
    const hasTimeline = await page.locator('.el-timeline, [class*="timeline"]').count() > 0
    expect(hasTable || hasCards || hasTimeline).toBeTruthy()
  })
})
