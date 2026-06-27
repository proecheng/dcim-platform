import { expect, test } from '@playwright/test'
import fs from 'fs'
import path from 'path'

const FRONTEND_URL = process.env.FRONTEND_URL ?? 'http://powerlab.cn:3000'
const HOLD_MS = Number(process.env.VISIBLE_MS ?? 5500)
const ARTIFACT_DIR = path.join(process.cwd(), 'artifacts', 'asset-capacity-visible-check')

const routes = [
  { path: '/asset/list', title: '资产台账', expected: /DEMO-AST|精密空调|资产编码/ },
  { path: '/asset/cabinet', title: '机柜管理', expected: /DEMO-F|机柜|已用U/ },
  { path: '/asset/capacity', title: '容量管理', expected: /空间容量|电力容量|制冷容量|承重容量|DEMO-F/ },
  { path: '/asset/spatial', title: '空间拓扑', expected: /深圳算力中心|机房|空间|楼层/ },
]

test.use({
  viewport: null,
  launchOptions: {
    slowMo: 300,
    args: ['--start-maximized'],
  },
})

test('asset and capacity pages show seeded data in headed browser', async ({ page }) => {
  test.setTimeout(5 * 60 * 1000)
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true })

  page.on('console', (message) => {
    if (message.type() === 'error') {
      console.log(`[console.error] ${message.text()}`)
    }
  })

  await page.goto(`${FRONTEND_URL}/login`, { waitUntil: 'domcontentloaded' })
  await page.waitForLoadState('networkidle').catch(() => {})
  await page.locator('input').first().fill('admin')
  await page.locator('input[type="password"]').first().fill('admin123')
  await page.locator('button').filter({ hasText: '登' }).first().click()
  await page.waitForURL('**/dashboard', { timeout: 30000 }).catch(async () => {
    await page.goto(`${FRONTEND_URL}/dashboard`, { waitUntil: 'domcontentloaded' })
  })
  await page.waitForTimeout(HOLD_MS)

  for (const [index, route] of routes.entries()) {
    await page.goto(`${FRONTEND_URL}${route.path}`, { waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle').catch(() => {})
    await page.waitForTimeout(HOLD_MS)

    const bodyText = await page.locator('body').innerText({ timeout: 5000 })
    expect(bodyText, `${route.title} should render seeded asset/capacity data`).toMatch(route.expected)
    expect(bodyText, `${route.title} should not be empty`).not.toMatch(/暂无数据|无数据|No Data/i)

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, `${String(index + 1).padStart(2, '0')}-${route.title}.png`),
      fullPage: true,
    })
  }
})
