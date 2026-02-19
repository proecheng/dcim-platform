import { test, expect, type Page } from '@playwright/test'

/**
 * Story 1-1: 用户管理页面 E2E 测试
 * 认证状态由 auth.setup.ts 注入，无需重复登录
 */

const ADMIN_USER = 'admin'
const ADMIN_PASS = 'admin123'

async function navigateToUserManagement(page: Page) {
  await page.goto('/settings')
  await page.waitForLoadState('networkidle')
  await page.locator('.el-tabs__item').filter({ hasText: '用户管理' }).click()
  await page.waitForSelector('.user-management', { timeout: 5000 })
  await page.waitForTimeout(1000)
}

// 通过 API 获取 admin token（不走浏览器登录，不触发限流计数）
async function getAdminToken(page: Page): Promise<string> {
  const res = await page.request.post('/api/v1/auth/login', {
    form: { username: ADMIN_USER, password: ADMIN_PASS }
  })
  return (await res.json()).access_token
}

test.describe('Story 1-1: 用户管理页面', () => {

  // AC #1: 显示用户列表
  test('AC1: 管理员导航到用户管理，应显示用户列表', async ({ page }) => {
    await navigateToUserManagement(page)

    // 统计卡片
    await expect(page.locator('.stat-card')).toHaveCount(4)

    // 表格列头
    const table = page.locator('.user-management .el-table')
    await expect(table).toBeVisible()
    for (const col of ['用户名', '姓名', '角色', '部门', '状态', '最后登录', '操作']) {
      await expect(table.locator('th').filter({ hasText: col })).toBeVisible()
    }

    // 搜索 admin 用户（避免被其他测试用户挤出第一页）
    await page.locator('.user-management input[placeholder*="搜索"]').fill('admin')
    await page.locator('.user-management .toolbar button').filter({ hasText: /^搜索$/ }).click()
    await page.waitForTimeout(1000)
    await expect(table.locator('td').filter({ hasText: 'admin' }).first()).toBeVisible()
  })

  // AC #2: 搜索/筛选/分页
  test('AC2: 支持搜索筛选和分页', async ({ page }) => {
    await navigateToUserManagement(page)

    const searchInput = page.locator('.user-management input[placeholder*="搜索"]')
    await expect(searchInput).toBeVisible()
    await expect(page.locator('.user-management .toolbar button').filter({ hasText: /^搜索$/ })).toBeVisible()
    await expect(page.locator('.user-management .toolbar button').filter({ hasText: /^重置$/ })).toBeVisible()
    await expect(page.locator('.user-management .el-pagination')).toBeVisible()

    // 搜索 admin
    await searchInput.fill('admin')
    await page.locator('.user-management .toolbar button').filter({ hasText: /^搜索$/ }).click()
    await page.waitForTimeout(1000)
    expect(await page.locator('.user-management .el-table__body-wrapper .el-table__row').count()).toBeGreaterThanOrEqual(1)

    // 重置
    await page.locator('.user-management .toolbar button').filter({ hasText: /^重置$/ }).click()
    await page.waitForTimeout(1000)
  })

  // AC #3: 新增用户
  test('AC3: 创建新用户', async ({ page }) => {
    await navigateToUserManagement(page)
    const testUsername = `test_${Date.now()}`

    await page.locator('.user-management button').filter({ hasText: '新增用户' }).click()
    await page.waitForTimeout(500)

    const dialog = page.locator('.el-dialog').filter({ hasText: '新增用户' })
    await expect(dialog).toBeVisible()

    await dialog.locator('.el-form-item').filter({ hasText: '用户名' }).locator('input').fill(testUsername)
    await dialog.locator('.el-form-item').filter({ hasText: /^密码$/ }).locator('input').fill('Test@12345')
    await dialog.locator('.el-form-item').filter({ hasText: '确认密码' }).locator('input').fill('Test@12345')
    await dialog.locator('.el-form-item').filter({ hasText: '姓名' }).locator('input').fill('测试用户')

    // 角色选择
    await dialog.locator('.el-form-item').filter({ hasText: '角色' }).locator('.el-select').click()
    await page.waitForTimeout(300)
    await page.getByRole('option', { name: '操作员' }).first().click()

    await dialog.locator('.el-dialog__footer button').filter({ hasText: '确定' }).click()
    await expect(page.locator('.el-message').filter({ hasText: '创建成功' })).toBeVisible({ timeout: 5000 })
  })

  // AC #4: 编辑用户
  test('AC4: 编辑用户信息', async ({ page }) => {
    await navigateToUserManagement(page)

    let apiStatus = 0
    page.on('response', async (resp) => {
      if (resp.url().includes('/api/v1/users/') && resp.request().method() === 'PUT'
        && !resp.url().includes('status') && !resp.url().includes('reset')) {
        apiStatus = resp.status()
      }
    })

    const rows = page.locator('.user-management .el-table__body-wrapper .el-table__row')
    await rows.first().locator('button').filter({ hasText: '编辑' }).click()
    await page.waitForTimeout(500)

    const dialog = page.locator('.el-dialog').filter({ hasText: '编辑用户' })
    await expect(dialog).toBeVisible()
    await expect(dialog.locator('.el-form-item').filter({ hasText: '用户名' }).locator('input')).toBeDisabled()

    const deptInput = dialog.locator('.el-form-item').filter({ hasText: '部门' }).locator('input')
    await deptInput.clear()
    await deptInput.fill('运维部')

    await dialog.locator('.el-dialog__footer button').filter({ hasText: '确定' }).click()
    await page.waitForTimeout(2000)
    expect(apiStatus).toBe(200)
  })

  // AC #5: 重置密码（用临时用户测试，不动 admin 密码）
  test('AC5: 重置用户密码', async ({ page }) => {
    // 通过 API 创建临时用户
    const token = await getAdminToken(page)
    const tempUser = `pwd_test_${Date.now()}`
    await page.request.post('/api/v1/users', {
      headers: { Authorization: `Bearer ${token}` },
      data: { username: tempUser, password: 'Test@12345', role: 'viewer' }
    })

    await navigateToUserManagement(page)

    // 搜索临时用户
    await page.locator('.user-management input[placeholder*="搜索"]').fill(tempUser)
    await page.locator('.user-management .toolbar button').filter({ hasText: /^搜索$/ }).click()
    await page.waitForTimeout(1000)

    let apiStatus = 0
    page.on('response', async (resp) => {
      if (resp.url().includes('reset-password')) apiStatus = resp.status()
    })

    const rows = page.locator('.user-management .el-table__body-wrapper .el-table__row')
    await rows.first().locator('button').filter({ hasText: '重置密码' }).click()
    await page.waitForTimeout(500)

    const dialog = page.locator('.el-dialog').filter({ hasText: '重置密码' })
    await expect(dialog).toBeVisible()
    await dialog.locator('.el-form-item').filter({ hasText: '新密码' }).locator('input').fill('NewPass@123')
    await dialog.locator('.el-form-item').filter({ hasText: '确认密码' }).locator('input').fill('NewPass@123')

    await dialog.locator('.el-dialog__footer button').filter({ hasText: '确定' }).click()
    await page.waitForTimeout(2000)
    expect(apiStatus).toBe(200)
  })

  // AC #6: 不能禁用自己
  test('AC6: admin 的状态开关应被禁用', async ({ page }) => {
    await navigateToUserManagement(page)

    // 搜索 admin（避免被其他测试用户挤出第一页）
    await page.locator('.user-management input[placeholder*="搜索"]').fill('admin')
    await page.locator('.user-management .toolbar button').filter({ hasText: /^搜索$/ }).click()
    await page.waitForTimeout(1000)

    const adminRow = page.locator('.user-management .el-table__body-wrapper .el-table__row').filter({ hasText: 'admin' })
    await expect(adminRow.locator('.el-switch input')).toBeDisabled()
  })

  // AC #7: 不能删除自己
  test('AC7: admin 行不应显示删除按钮', async ({ page }) => {
    await navigateToUserManagement(page)

    // 搜索 admin（避免被其他测试用户挤出第一页）
    await page.locator('.user-management input[placeholder*="搜索"]').fill('admin')
    await page.locator('.user-management .toolbar button').filter({ hasText: /^搜索$/ }).click()
    await page.waitForTimeout(1000)

    const adminRow = page.locator('.user-management .el-table__body-wrapper .el-table__row').filter({ hasText: 'admin' })
    await expect(adminRow.locator('button').filter({ hasText: '删除' })).toHaveCount(0)
  })

  // AC #8: 非 admin 看不到用户管理 tab（通过 API 创建用户 + 新 context 登录）
  test('AC8: 非admin用户看不到用户管理tab', async ({ page, browser }) => {
    // 通过 API 创建 operator 用户
    const token = await getAdminToken(page)
    const testUser = `op_ac8_${Date.now()}`
    await page.request.post('/api/v1/users', {
      headers: { Authorization: `Bearer ${token}` },
      data: { username: testUser, password: 'Test@12345', role: 'operator' }
    })

    // 用全新 context（无 admin 认证状态）登录 operator
    const ctx = await browser.newContext()
    const opPage = await ctx.newPage()
    await opPage.goto('http://localhost:3000/login')
    await opPage.waitForLoadState('networkidle')
    await opPage.locator('input').first().fill(testUser)
    await opPage.locator('input[type="password"]').fill('Test@12345')
    await opPage.locator('button').filter({ hasText: '登' }).click()
    await opPage.waitForURL('**/dashboard', { timeout: 15000 })

    await opPage.goto('http://localhost:3000/settings')
    await opPage.waitForLoadState('networkidle')
    await opPage.waitForTimeout(1000)

    await expect(opPage.locator('.el-tabs__item').filter({ hasText: '用户管理' })).toHaveCount(0)
    await ctx.close()
  })

  // 密码复杂度验证
  test('密码复杂度：弱密码应被拒绝', async ({ page }) => {
    await navigateToUserManagement(page)

    await page.locator('.user-management button').filter({ hasText: '新增用户' }).click()
    await page.waitForTimeout(500)

    const dialog = page.locator('.el-dialog').filter({ hasText: '新增用户' })
    await dialog.locator('.el-form-item').filter({ hasText: '用户名' }).locator('input').fill('weakpwdtest')
    await dialog.locator('.el-form-item').filter({ hasText: /^密码$/ }).locator('input').fill('simple')
    await dialog.locator('.el-form-item').filter({ hasText: '确认密码' }).locator('input').click()
    await page.waitForTimeout(500)

    await expect(dialog.locator('.el-form-item__error').first()).toBeVisible()
    await dialog.locator('.el-dialog__footer button').filter({ hasText: '取消' }).click()
  })
})
