import { expect, test } from '@playwright/test'

const baseURL = process.env.STORY_39_2_BASE_URL

test('actual Nginx artifact loads under the enforced CSP', async ({ page }) => {
  if (!baseURL) throw new Error('STORY_39_2_BASE_URL is required')

  const errors: string[] = []
  page.on('console', message => {
    if (message.type() === 'error') errors.push(message.text())
  })
  page.on('pageerror', error => errors.push(error.message))

  const response = await page.goto(baseURL, { waitUntil: 'networkidle' })
  expect(response?.status()).toBe(200)
  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByRole('button', { name: '登 录' })).toBeVisible()
  await expect(page.getByText('admin123')).toHaveCount(0)

  const csp = response?.headers()['content-security-policy'] || ''
  expect(csp).toContain("script-src 'self'")
  expect(csp).not.toMatch(/script-src[^;]*'unsafe-inline'/)
  expect(response?.headers()['x-content-type-options']).toBe('nosniff')
  expect(response?.headers()['x-frame-options']).toBe('DENY')
  expect(await page.locator('script:not([src])').count()).toBe(0)
  expect(errors).toEqual([])
})
