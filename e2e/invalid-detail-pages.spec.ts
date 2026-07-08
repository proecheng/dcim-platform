import { test, expect, type Page } from '@playwright/test'

function collectUnexpectedConsoleErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') {
      const text = message.text()
      if (text.includes('AxiosError') || text.includes('加载设备详情失败') || text.includes('加载故障树失败')) {
        errors.push(text)
      }
    }
  })
  return errors
}

test.describe('无效详情页友好错误处理', () => {
  test('无效设备 ID 显示友好错误页', async ({ page }) => {
    const consoleErrors = collectUnexpectedConsoleErrors(page)

    await page.goto('/collection/device-manage/detail/999999', { waitUntil: 'domcontentloaded' })

    const result = page.locator('.device-detail-page .el-result')
    await expect(result.getByText('未找到设备')).toBeVisible({ timeout: 15000 })
    await expect(result.getByText('设备 999999 不存在')).toBeVisible()
    await expect(result.getByRole('button', { name: '返回设备管理' })).toBeVisible()
    await expect(result.getByRole('button', { name: '重试' })).toBeVisible()
    expect(consoleErrors).toEqual([])
  })

  test('无效故障树 ID 显示友好错误页', async ({ page }) => {
    const consoleErrors = collectUnexpectedConsoleErrors(page)

    await page.goto('/strategy/diagnosis/fault-trees/999999/editor', { waitUntil: 'domcontentloaded' })

    const result = page.locator('.fault-tree-editor .editor-result')
    await expect(result.getByText('未找到故障树')).toBeVisible({ timeout: 15000 })
    await expect(result.getByText('故障树 999999 不存在')).toBeVisible()
    await expect(result.getByRole('button', { name: '返回诊断规则' })).toBeVisible()
    await expect(result.getByRole('button', { name: '重试' })).toBeVisible()
    await expect(page.locator('.fault-tree-editor .editor-content')).toHaveCount(0)
    expect(consoleErrors).toEqual([])
  })
})
