import { chromium } from 'playwright'
import fs from 'node:fs'
import path from 'node:path'

const baseURL = process.env.FRONTEND_URL || 'http://127.0.0.1:3000'
const holdMs = Number(process.env.HOLD_MS || 5500)
const outDir = path.resolve('artifacts', 'cooling-flexibility-visible')
fs.mkdirSync(outDir, { recursive: true })

const issues = []
const steps = []

function record(step, detail = {}) {
  steps.push({ step, at: new Date().toISOString(), ...detail })
  console.log(`[visible-check] ${step}`, detail)
}

async function hold(page, step) {
  record(`hold ${step}`, { ms: holdMs, url: page.url() })
  await page.bringToFront()
  await page.waitForTimeout(holdMs)
}

async function shot(page, name) {
  const filePath = path.join(outDir, name)
  await page.screenshot({ path: filePath, fullPage: false })
  record('screenshot', { filePath })
}

async function login(page) {
  await page.goto(`${baseURL}/login`, { waitUntil: 'domcontentloaded' })
  await page.waitForLoadState('networkidle').catch(() => {})
  await hold(page, '登录页')
  await page.locator('input').first().fill('admin')
  await page.locator('input[type="password"]').first().fill('admin123')
  await page.locator('button').filter({ hasText: /登录|登/ }).first().click()
  await page.waitForURL(/dashboard|collection|energy/, { timeout: 30000 }).catch(async () => {
    await page.goto(`${baseURL}/dashboard`, { waitUntil: 'domcontentloaded' })
  })
  await page.waitForLoadState('networkidle').catch(() => {})
  await hold(page, '登录完成')
  await shot(page, '01-login-dashboard.png')
}

async function verifyPowerConfig(page) {
  await page.goto(`${baseURL}/collection/power-config`, { waitUntil: 'domcontentloaded' })
  await page.waitForLoadState('networkidle').catch(() => {})
  await hold(page, '配电配置页')

  await page.getByRole('tab', { name: '转移配置' }).click()
  await page.waitForLoadState('networkidle').catch(() => {})
  const shiftTable = page.locator('.el-table:visible').filter({ hasText: '推荐比例' }).first()
  await shiftTable.waitFor({ state: 'visible', timeout: 15000 })
  await hold(page, '转移配置表')
  await shot(page, '02-shift-config-table.png')

  for (const text of ['细分负荷', '可控项', '推荐比例']) {
    if (!(await page.getByText(text, { exact: false }).first().isVisible().catch(() => false))) {
      issues.push(`转移配置表缺少 ${text}`)
    }
  }

  const tableText = await shiftTable.innerText()
  const expectedLabels = ['行级/微模块空调', '冷冻水末端', '变频水泵', '大型水冷冷机']
  const presentLabels = expectedLabels.filter((label) => tableText.includes(label))
  record('visible subtype labels', { presentLabels })
  if (presentLabels.length < 2) {
    issues.push(`当前表格可见细分负荷类型不足: ${presentLabels.join(', ')}`)
  }

  const firstDataRow = shiftTable.locator('.el-table__body-wrapper tbody tr').first()
  await firstDataRow.locator('.el-link, a').first().click()
  await page.locator('.el-drawer:visible').waitFor({ state: 'visible', timeout: 10000 })
  await hold(page, '设备用电详情抽屉')
  await shot(page, '03-shift-device-detail-drawer.png')
  if (!(await page.getByText('约束条件分析').first().isVisible().catch(() => false))) {
    issues.push('设备详情抽屉未显示约束条件分析')
  }
  if (!(await page.getByText('水冷/蓄冷执行策略').first().isVisible().catch(() => false))) {
    issues.push('设备详情抽屉未显示水冷/蓄冷执行策略')
  }
  await page.getByRole('button', { name: '关闭' }).click().catch(async () => {
    await page.keyboard.press('Escape')
  })
  await page.waitForTimeout(800)

  await shiftTable.locator('.el-table__body-wrapper tbody tr').first().locator('button', { hasText: '调整' }).click()
  await page.locator('.el-dialog:visible').waitFor({ state: 'visible', timeout: 10000 })
  await hold(page, '调整转移配置弹窗')
  const sliderInput = page.locator('.el-dialog:visible input').last()
  await sliderInput.fill('35').catch(() => {})
  await hold(page, '编辑新比例但不保存')
  await shot(page, '04-shift-ratio-dialog-edited.png')
  await page.getByRole('button', { name: '取消' }).click()
  await page.waitForTimeout(800)
}

async function verifyDeviceTemplates(page) {
  await page.goto(`${baseURL}/collection/device-templates`, { waitUntil: 'domcontentloaded' })
  await page.waitForLoadState('networkidle').catch(() => {})
  await hold(page, '设备模板页')
  await shot(page, '05-device-templates.png')

  await page.getByRole('button', { name: '导入内置协议' }).click()
  await page.locator('.el-dialog:visible').waitFor({ state: 'visible', timeout: 10000 })
  await hold(page, '内置协议模板弹窗')
  await shot(page, '06-builtins-dialog.png')
  if (!(await page.getByText('FusionCol5000-A', { exact: false }).first().isVisible().catch(() => false))) {
    issues.push('内置协议弹窗未显示 FusionCol5000-A')
  }
  await page.getByRole('button', { name: '取消' }).click().catch(async () => {
    await page.keyboard.press('Escape')
  })
  await page.waitForTimeout(800)

  const createButton = page.getByRole('button', { name: '创建数据源' }).first()
  if (await createButton.isVisible().catch(() => false)) {
    await createButton.click()
    await page.locator('.el-dialog:visible').waitFor({ state: 'visible', timeout: 10000 })
    await hold(page, '从模板创建数据源弹窗')
    const createDialog = page.locator('.el-dialog:visible').last()
    await shot(page, '07-create-datasource-dialog.png')
    const dialogText = await createDialog.innerText()
    for (const text of ['业务设备', '细分负荷', '可控项', '资产台账']) {
      if (!dialogText.includes(text)) {
        issues.push(`创建数据源弹窗缺少 ${text}`)
      }
    }

    const subtypeItem = createDialog.locator('.el-form-item').filter({ hasText: '细分负荷' }).first()
    await subtypeItem.locator('.el-select').click()
    await page.locator('.el-select-dropdown:visible').last().getByText('蓄冷系统', { exact: true }).click()
    await hold(page, '选择蓄冷系统后显示蓄冷参数')
    const storageText = await createDialog.innerText()
    for (const text of ['蓄冷容量', '最大放冷', '最大充冷', '等效COP', '放冷效率', '辅机功率', '等效电功率']) {
      if (!storageText.includes(text)) {
        issues.push(`选择蓄冷系统后缺少 ${text}`)
      }
    }
    await shot(page, '08-create-datasource-storage-fields.png')

    await page.locator('.el-dialog:visible input').first().fill(`可视验证-${Date.now().toString().slice(-5)}`).catch(() => {})
    await hold(page, '编辑创建数据源表单但不提交')
    await shot(page, '09-create-datasource-edited.png')
    await page.getByRole('button', { name: '取消' }).click()
  } else {
    issues.push('设备模板表未找到创建数据源按钮，可能尚未安装内置模板')
  }
}

const browser = await chromium.launch({
  headless: false,
  slowMo: 350,
  args: ['--start-maximized'],
})
const context = await browser.newContext({ viewport: null, baseURL })
const page = await context.newPage()

page.on('console', (msg) => {
  if (msg.type() === 'error') issues.push(`console.error: ${msg.text()}`)
})
page.on('pageerror', (err) => issues.push(`pageerror: ${err.message}`))
page.on('response', (resp) => {
  const status = resp.status()
  const resourceType = resp.request().resourceType()
  if (status >= 500 && ['xhr', 'fetch', 'document'].includes(resourceType)) {
    issues.push(`http ${status}: ${resp.url()}`)
  }
})

try {
  await login(page)
  await verifyPowerConfig(page)
  await verifyDeviceTemplates(page)
  await hold(page, '验证结束')
} finally {
  const report = {
    baseURL,
    holdMs,
    issues,
    steps,
    endedAt: new Date().toISOString(),
  }
  fs.writeFileSync(path.join(outDir, 'summary.json'), JSON.stringify(report, null, 2))
  fs.writeFileSync(
    path.join(outDir, 'summary.md'),
    [
      '# Cooling Flexibility Visible Check',
      '',
      `- baseURL: ${baseURL}`,
      `- holdMs: ${holdMs}`,
      `- issues: ${issues.length}`,
      '',
      ...issues.map((issue) => `- ${issue}`),
    ].join('\n'),
  )
  await browser.close()
  if (issues.length) {
    throw new Error(`visible check found ${issues.length} issue(s); see ${path.join(outDir, 'summary.json')}`)
  }
}
