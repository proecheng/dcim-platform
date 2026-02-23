import { test, expect } from '@playwright/test'

// ------------- 阈值配置测试 -------------
test.describe('阈值配置测试', () => {
  // a. 页面加载与基础结构验证
  test('阈值配置页面加载成功与结构就绪', async ({ page }) => {
    await page.goto('/strategy/alarm-rules/thresholds')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)
    expect(page.url()).toContain('/strategy/alarm-rules/thresholds')
    const body = page.locator('.el-main, main, .app-main').first()
    await expect(body).toBeVisible({ timeout: 10000 })
    // 表格存在
    const table = page.locator('.el-table')
    await expect(table).toBeVisible({ timeout: 10000 })
  })

  // b. 新增按钮可见
  test('阈值配置页面应有新增按钮', async ({ page }) => {
    await page.goto('/strategy/alarm-rules/thresholds')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)
    const addBtn = page.locator('.el-button', { hasText: /新增|添加/ }).first()
    await expect(addBtn).toBeVisible({ timeout: 10000 })
  })

  // c. 表头检查（至少包含阈值相关列）
  test('阈值配置表格列头包含阈值相关字段', async ({ page }) => {
    await page.goto('/strategy/alarm-rules/thresholds')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)
    const headers = await page.locator('.el-table__header th').allTextContents()
    const headerHasThreshold = headers.some(h => /阈值|阈值配置|设备类型|点位类型|告警级别/.test(h))
    expect(headers.length).toBeGreaterThan(0)
    expect(headerHasThreshold).toBeTruthy()
  })
})

// ------------- 复合规则测试 -------------
test.describe('复合规则测试', () => {
  test('复合规则页面加载成功与结构就绪', async ({ page }) => {
    await page.goto('/strategy/alarm-rules/compound')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)
    expect(page.url()).toContain('/strategy/alarm-rules/compound')
    const body = page.locator('.el-main, main, .app-main').first()
    await expect(body).toBeVisible({ timeout: 10000 })
    const table = page.locator('.el-table')
    await expect(table).toBeVisible({ timeout: 10000 })
  })

  test('复合规则页面应有新增按钮', async ({ page }) => {
    await page.goto('/strategy/alarm-rules/compound')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)
    const addBtn = page.locator('.el-button', { hasText: /新增|添加/ }).first()
    await expect(addBtn).toBeVisible({ timeout: 10000 })
  })

  test('复合规则表头包含规则相关字段', async ({ page }) => {
    await page.goto('/strategy/alarm-rules/compound')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)
    const headers = await page.locator('.el-table__header th').allTextContents()
    const headerHasRule = headers.some(h => /规则|表达式|条件|名称/.test(h))
    expect(headers.length).toBeGreaterThan(0)
    expect(headerHasRule).toBeTruthy()
  })
})

// ------------- 升级规则测试 -------------
test.describe('升级规则测试', () => {
  test('升级规则页面加载成功与结构就绪', async ({ page }) => {
    await page.goto('/strategy/alarm-rules/escalation')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)
    expect(page.url()).toContain('/strategy/alarm-rules/escalation')
    const body = page.locator('.el-main, main, .app-main').first()
    await expect(body).toBeVisible({ timeout: 10000 })
    const table = page.locator('.el-table')
    await expect(table).toBeVisible({ timeout: 10000 })
  })

  test('升级规则页面应有新增按钮', async ({ page }) => {
    await page.goto('/strategy/alarm-rules/escalation')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)
    const addBtn = page.locator('.el-button', { hasText: /新增|添加/ }).first()
    await expect(addBtn).toBeVisible({ timeout: 10000 })
  })

  test('升级规则表头包含升级相关字段', async ({ page }) => {
    await page.goto('/strategy/alarm-rules/escalation')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)
    const headers = await page.locator('.el-table__header th').allTextContents()
    const headerHasEscalation = headers.some(h => /升级|级别|通知|名称/.test(h))
    expect(headers.length).toBeGreaterThan(0)
    expect(headerHasEscalation).toBeTruthy()
  })
})

// ------------- 告警屏蔽测试 -------------
test.describe('告警屏蔽测试', () => {
  test('告警屏蔽页面加载成功与结构就绪', async ({ page }) => {
    await page.goto('/strategy/alarm-rules/shield')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)
    expect(page.url()).toContain('/strategy/alarm-rules/shield')
    const body = page.locator('.el-main, main, .app-main').first()
    await expect(body).toBeVisible({ timeout: 10000 })
    const table = page.locator('.el-table')
    await expect(table).toBeVisible({ timeout: 10000 })
  })

  test('告警屏蔽页面应有新增/添加按钮', async ({ page }) => {
    await page.goto('/strategy/alarm-rules/shield')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)
    const addBtn = page.locator('.el-button', { hasText: /新增|添加/ }).first()
    await expect(addBtn).toBeVisible({ timeout: 10000 })
  })

  test('告警屏蔽表头包含屏蔽相关字段', async ({ page }) => {
    await page.goto('/strategy/alarm-rules/shield')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)
    const headers = await page.locator('.el-table__header th').allTextContents()
    const headerHasShield = headers.some(h => /屏蔽|开关|生效|原因/.test(h))
    expect(headers.length).toBeGreaterThan(0)
    expect(headerHasShield).toBeTruthy()
  })
})
