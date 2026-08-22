import { test, type Locator, type Page } from '@playwright/test'
import fs from 'fs'
import path from 'path'

type RouteSpec = {
  path: string
  title: string
}

type ActionRecord = {
  route: string
  title: string
  type: string
  label: string
  status: 'clicked' | 'skipped'
  detail?: string
}

type RouteRecord = {
  path: string
  title: string
  screenshot?: string
  actions: ActionRecord[]
}

type IssueRecord = {
  route: string
  type: string
  detail: string
  url?: string
  status?: number
}

const FRONTEND_URL = process.env.FRONTEND_URL ?? 'http://127.0.0.1:3000'
const E2E_ADMIN_USER = process.env.E2E_ADMIN_USER ?? 'admin'
const E2E_ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'admin123'
const VISIBLE_MS = Number(process.env.VISIBLE_MS ?? 5500)
const ACTION_MS = Number(process.env.ACTION_MS ?? 5500)
const CONTROL_TIMEOUT_MS = Number(process.env.CONTROL_TIMEOUT_MS ?? 5000)
const MAX_BUTTONS_PER_PAGE = Number(process.env.MAX_BUTTONS_PER_PAGE ?? 120)
const MAX_EDITABLES_PER_PAGE = Number(process.env.MAX_EDITABLES_PER_PAGE ?? 80)
const MAX_TOGGLES_PER_PAGE = Number(process.env.MAX_TOGGLES_PER_PAGE ?? 80)
const ROUTE_START = Math.max(1, Number(process.env.ROUTE_START ?? 1))
const ROUTE_END = Number(process.env.ROUTE_END ?? 0)
const ARTIFACT_DIR = path.join(process.cwd(), 'artifacts', 'manual-walkthrough')
const PAGE_SCOPE_SELECTOR = '.main'
const RUN_ID = Date.now().toString(36).slice(-6)

const routes: RouteSpec[] = [
  { path: '/bigscreen', title: '数字孪生大屏' },
  { path: '/dashboard', title: '综合概览' },
  { path: '/power/overview', title: '供配电总览' },
  { path: '/power/ups', title: 'UPS监控' },
  { path: '/power/battery', title: '电池组' },
  { path: '/power/cabinet', title: '配电柜' },
  { path: '/power/pdu', title: '机柜PDU' },
  { path: '/power/topology', title: '配电拓扑' },
  { path: '/cooling/overview', title: '制冷总览' },
  { path: '/cooling/indoor', title: '精密空调' },
  { path: '/cooling/outdoor', title: '室外机' },
  { path: '/cooling/cold-aisle', title: '冷通道' },
  { path: '/cooling/group-control', title: '群控状态' },
  { path: '/environment/overview', title: '环境总览' },
  { path: '/environment/temperature', title: '温湿度监测' },
  { path: '/environment/water-leak', title: '水浸检测' },
  { path: '/environment/smoke-infrared', title: '烟雾/红外检测' },
  { path: '/security/overview', title: '安防总览' },
  { path: '/security/access-control', title: '门禁管理' },
  { path: '/security/video/cameras', title: '摄像头管理' },
  { path: '/security/video/control', title: '视频控制' },
  { path: '/security/video/playback', title: '告警回放' },
  { path: '/security/fire-linkage', title: '消防联动' },
  { path: '/alarms', title: '告警中心' },
  { path: '/energy/monitor', title: '用电监控' },
  { path: '/energy/statistics', title: '能耗统计' },
  { path: '/energy/analysis', title: '节能分析' },
  { path: '/energy/regulation', title: '负荷调节' },
  { path: '/energy/execution', title: '执行管理' },
  { path: '/energy/report', title: '能效报告' },
  { path: '/energy/shift/dashboard', title: '转移仪表盘' },
  { path: '/energy/shift/list', title: '计划列表' },
  { path: '/energy/shift/create', title: '新建计划' },
  { path: '/energy/shift/opportunities', title: '转移机会' },
  { path: '/energy/shift/executions', title: '执行记录' },
  { path: '/energy/shift/cooling-config', title: '制冷联动配置' },
  { path: '/energy/shift/cooling-monitor', title: '制冷状态监控' },
  { path: '/energy/shift/constraints', title: '约束管理' },
  { path: '/energy/shift/reports', title: '收益报表' },
  { path: '/energy/shift/precool-schedule', title: '预冷计划' },
  { path: '/energy/shift/deployment', title: '部署管理' },
  { path: '/energy/shift/vpp-monitor', title: 'VPP集成监控' },
  { path: '/asset/list', title: '资产台账' },
  { path: '/asset/cabinet', title: '机柜管理' },
  { path: '/asset/capacity', title: '容量管理' },
  { path: '/asset/spatial', title: '空间拓扑' },
  { path: '/operation/workorder', title: '工单管理' },
  { path: '/operation/inspection', title: '巡检管理' },
  { path: '/operation/knowledge', title: '知识库' },
  { path: '/operation/reports', title: '报表分析' },
  { path: '/operation/history', title: '历史数据' },
  { path: '/operation/predictive', title: '预测性维护' },
  { path: '/vpp/analysis', title: 'VPP方案分析' },
  { path: '/collection/device-manage', title: '设备管理' },
  { path: '/collection/device-status', title: '设备状态看板' },
  { path: '/collection/devices', title: '点位管理' },
  { path: '/collection/datasources', title: '数据源管理' },
  { path: '/collection/device-templates', title: '设备模板' },
  { path: '/collection/power-config', title: '配电配置' },
  { path: '/collection/gateway', title: '网关管理' },
  { path: '/collection/drift', title: '漂移检测' },
  { path: '/strategy/alarm-rules/thresholds', title: '阈值配置' },
  { path: '/strategy/alarm-rules/compound', title: '复合规则' },
  { path: '/strategy/alarm-rules/escalation', title: '升级规则' },
  { path: '/strategy/alarm-rules/shield', title: '告警屏蔽' },
  { path: '/strategy/linkage/policy', title: '联动策略' },
  { path: '/strategy/linkage/execution', title: '执行日志' },
  { path: '/strategy/linkage/recovery', title: '联动恢复' },
  { path: '/strategy/linkage/timeline', title: '事件时间线' },
  { path: '/strategy/linkage/command', title: '命令管理' },
  { path: '/strategy/diagnosis/results', title: '诊断结果' },
  { path: '/strategy/diagnosis/rules', title: '诊断规则' },
  { path: '/strategy/diagnosis/reports', title: '误诊报告' },
  { path: '/strategy/diagnosis/time-window-tuning', title: '时间窗口调参' },
  { path: '/strategy/diagnosis/probability-tuning', title: '概率调参' },
  { path: '/system/users', title: '用户管理' },
  { path: '/system/sites', title: '站点管理' },
  { path: '/system/audit-log', title: '操作审计' },
  { path: '/system/notification', title: '通知管理' },
  { path: '/system/settings', title: '系统设置' },
  { path: '/system/site-selection', title: '智能选址' },
]

const routeSlice = routes.slice(ROUTE_START - 1, ROUTE_END > 0 ? ROUTE_END : routes.length)

const sessionEndingButtonText = /退出登录|登出|注销|返回登录/
const excludedWalkthroughButtonText = /打开数字孪生大屏/
const destructiveActionText = /删除|清空|移除|注销|终止/
const confirmButtonText = /确定|确认|确认删除|删除|保存|提交|应用|完成|启用|禁用|下发|执行|开始分析|触发分析|继续|生成|评估/
const closeButtonText = /取消|关闭|返回/
const expectedBusinessHttpConsoleText = /Failed to load resource: the server responded with a status of (400|409) /

let activeReport: { startedAt: Date; routes: RouteRecord[]; issues: IssueRecord[] } | null = null

test.describe.configure({ mode: 'serial' })
test.use({
  storageState: { cookies: [], origins: [] },
  viewport: null,
  launchOptions: {
    slowMo: 450,
    args: ['--start-maximized'],
  },
})

test('manual headed walkthrough of every routed page and safe functions', async ({ page }) => {
  test.setTimeout(60 * 60 * 1000)
  page.setDefaultTimeout(CONTROL_TIMEOUT_MS)

  fs.mkdirSync(ARTIFACT_DIR, { recursive: true })
  clearPreviousSummary()

  const startedAt = new Date()
  const routeRecords: RouteRecord[] = []
  const issues: IssueRecord[] = []
  activeReport = { startedAt, routes: routeRecords, issues }
  let currentRoute = '启动'

  page.on('console', (message) => {
    if (message.type() === 'error') {
      if (expectedBusinessHttpConsoleText.test(message.text())) {
        return
      }
      issues.push({
        route: currentRoute,
        type: 'console.error',
        detail: message.text().slice(0, 600),
      })
    }
  })

  page.on('pageerror', (error) => {
    issues.push({
      route: currentRoute,
      type: 'pageerror',
      detail: error.message.slice(0, 600),
    })
  })

  page.on('requestfailed', (request) => {
    const errorText = request.failure()?.errorText ?? 'request failed'
    if (errorText === 'net::ERR_ABORTED') {
      return
    }
    issues.push({
      route: currentRoute,
      type: 'requestfailed',
      detail: errorText,
      url: request.url(),
    })
  })

  page.on('response', (response) => {
    const status = response.status()
    const request = response.request()
    if (status >= 500 && ['xhr', 'fetch', 'document'].includes(request.resourceType())) {
      issues.push({
        route: currentRoute,
        type: 'http.5xx',
        detail: response.statusText(),
        status,
        url: response.url(),
      })
    }
    if (
      status >= 400 &&
      status < 500 &&
      ![400, 409].includes(status) &&
      ['xhr', 'fetch', 'document'].includes(request.resourceType())
    ) {
      issues.push({
        route: currentRoute,
        type: `http.${status}`,
        detail: response.statusText(),
        status,
        url: response.url(),
      })
    }
  })

  currentRoute = '登录页'
  await loginVisible(page)
  await screenshot(page, '00-login-complete')

  for (let index = 0; index < routeSlice.length; index += 1) {
    const route = routeSlice[index]
    const absoluteIndex = ROUTE_START + index
    currentRoute = `${route.title} ${route.path}`
    const record: RouteRecord = { path: route.path, title: route.title, actions: [] }
    routeRecords.push(record)

    await ensureAuthenticated(page)
    await page.bringToFront()
    await page.goto(route.path, { waitUntil: 'domcontentloaded', timeout: 30000 })
    await settle(page)
    if (page.url().includes('/login')) {
      issues.push({
        route: currentRoute,
        type: 'auth.redirect',
        detail: '进入页面时被重定向到登录页，已重新认证并重试',
      })
      await loginVisible(page)
      currentRoute = `${route.title} ${route.path}`
      await page.goto(route.path, { waitUntil: 'domcontentloaded', timeout: 30000 })
      await settle(page)
    }
    await holdVisible(page, `${route.title} ${route.path}`)

    const screenshotName = `${String(absoluteIndex).padStart(2, '0')}-${slug(route.path)}.png`
    record.screenshot = await screenshot(page, screenshotName)
    await writeReport({
      startedAt,
      endedAt: new Date(),
      routes: routeRecords,
      issues: dedupeIssues(issues),
    })

    if (route.path === '/bigscreen') {
      record.actions.push({
        route: route.path,
        title: route.title,
        type: '展示型大屏',
        label: '大屏展示与截图',
        status: 'clicked',
      })
      await writeReport({
        startedAt,
        endedAt: new Date(),
        routes: routeRecords,
        issues: dedupeIssues(issues),
      })
      continue
    }

    await explorePage(page, route, record.actions)
    await closeTransientUi(page, `${FRONTEND_URL}${route.path}`, record.actions, route)
    await writeReport({
      startedAt,
      endedAt: new Date(),
      routes: routeRecords,
      issues: dedupeIssues(issues),
    })
  }

  currentRoute = '巡检结束'
  await page.goto('/dashboard', { waitUntil: 'domcontentloaded' })
  await settle(page)
  await holdVisible(page, '巡检结束 - 综合概览')

  const endedAt = new Date()
  const dedupedIssues = dedupeIssues(issues)
  await writeReport({
    startedAt,
    endedAt,
    routes: routeRecords,
    issues: dedupedIssues,
  })

  console.log(
    `[manual-visible-walkthrough] visited=${routeRecords.length} actions=${routeRecords.flatMap((route) => route.actions).filter((action) => action.status === 'clicked').length} issues=${dedupedIssues.length} artifacts=${ARTIFACT_DIR}`,
  )
})

function clearPreviousSummary() {
  const rangeSuffix = `${ROUTE_START}-${ROUTE_END > 0 ? ROUTE_END : routes.length}`
  for (const fileName of ['summary.json', 'summary.md', `summary-${rangeSuffix}.json`, `summary-${rangeSuffix}.md`]) {
    fs.rmSync(path.join(ARTIFACT_DIR, fileName), { force: true })
  }
}

async function loginVisible(page: Page) {
  await page.bringToFront()
  await page.goto('/login', { waitUntil: 'domcontentloaded' })
  await settle(page)
  await holdVisible(page, '登录页')

  if (await ensureAuthenticated(page)) {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' })
    await settle(page)
    await holdVisible(page, '已通过接口认证进入综合概览')
    return
  }

  const username = page.locator('input').first()
  const password = page.locator('input[type="password"]').first()
  if (await username.isVisible().catch(() => false)) {
    await username.fill(E2E_ADMIN_USER)
    await password.fill(E2E_ADMIN_PASSWORD)
    await page.locator('button').filter({ hasText: '登' }).first().click()
    await page.waitForURL('**/dashboard', { timeout: 30000 }).catch(async () => {
      await page.goto('/dashboard', { waitUntil: 'domcontentloaded' })
    })
    await settle(page)
    await holdVisible(page, '登录后综合概览')
  }
}

async function ensureAuthenticated(page: Page) {
  const response = await page.request
    .post(`${FRONTEND_URL}/api/v1/auth/login`, {
      form: {
        username: E2E_ADMIN_USER,
        password: E2E_ADMIN_PASSWORD,
      },
    })
    .catch(() => null)

  if (!response?.ok()) {
    return false
  }

  const body = await response.json().catch(() => null)
  if (!body?.access_token) {
    return false
  }

  await page.evaluate((token) => localStorage.setItem('token', token), body.access_token)
  return true
}

async function explorePage(page: Page, route: RouteSpec, actions: ActionRecord[]) {
  console.log(`[manual-visible-walkthrough] explore: ${route.title} ${route.path}`)
  await editEditableControls(page, route, actions, '页面可编辑内容')
  await clickTabs(page, route, actions)
  await clickSelectLikeControls(page, route, actions)
  await clickPagination(page, route, actions)
  await clickAllVisibleButtons(page, route, actions)
}

async function clickTabs(page: Page, route: RouteSpec, actions: ActionRecord[]) {
  const seen = new Set<string>()
  const tabs = pageScope(page).locator('.el-tabs__item:visible, [role="tab"]:visible')
  const total = await tabs.count().catch(() => 0)
  for (let index = 0; index < Math.min(total, 10); index += 1) {
    const tab = tabs.nth(index)
    const label = normalize(await tab.innerText({ timeout: 500 }).catch(() => ''))
    if (!label || seen.has(label)) {
      continue
    }
    seen.add(label)
    await clickSafely(page, tab, route, actions, '标签页', label)

    const activePane = pageScope(page).locator('.el-tab-pane:visible').last()
    if (await activePane.isVisible().catch(() => false)) {
      await editEditableControls(page, route, actions, `页签“${label}”可编辑内容`, activePane)
      await clickSelectLikeControls(page, route, actions, activePane)
      await clickPagination(page, route, actions, activePane)
      await clickAllVisibleButtons(page, route, actions, activePane)
    }
  }
}

async function clickSelectLikeControls(page: Page, route: RouteSpec, actions: ActionRecord[], scope?: Locator) {
  const controls = (scope ?? pageScope(page)).locator(
    '.el-select:visible, .el-date-editor:visible, .el-dropdown:visible',
  )
  const total = await controls.count().catch(() => 0)
  for (let index = 0; index < total; index += 1) {
    const control = controls.nth(index)
    await clickSafely(page, control, route, actions, '下拉/日期控件', `控件${index + 1}`, {
      closeAfterClick: false,
      exerciseAfterClick: false,
    })
    const label = normalize(
      (await control
        .evaluate((element) => element.closest('.el-form-item')?.querySelector('.el-form-item__label')?.textContent ?? '')
        .catch(() => '')) as string,
    )
    const futureDate = page.locator('.el-picker-panel:visible td.available:not(.disabled):visible').last()
    const sourceLevel = page
      .locator('.el-select-dropdown:visible .el-select-dropdown__item:not(.is-disabled):visible')
      .filter({ hasText: '次要' })
      .first()
    const defaultOption = page
      .locator(
        '.el-select-dropdown:visible .el-select-dropdown__item:not(.is-disabled):visible, .el-dropdown-menu:visible .el-dropdown-menu__item:not(.is-disabled):visible',
      )
      .first()
    const option = (await futureDate.isVisible().catch(() => false))
      ? futureDate
      : /源告警级别/.test(label) && (await sourceLevel.isVisible().catch(() => false))
        ? sourceLevel
        : defaultOption
    if (await option.isVisible().catch(() => false)) {
      await clickSafely(page, option, route, actions, '下拉/日期选项', `控件${index + 1}选项`, {
        closeAfterClick: false,
        exerciseAfterClick: false,
      })
    }
    await page.keyboard.press('Escape').catch(() => {})
    await page.waitForTimeout(ACTION_MS)
  }
}

async function clickPagination(page: Page, route: RouteSpec, actions: ActionRecord[], scope?: Locator) {
  const pagers = (scope ?? pageScope(page)).locator('.el-pagination button:not([disabled]):visible')
  const total = await pagers.count().catch(() => 0)
  for (let index = 0; index < Math.min(total, 2); index += 1) {
    await clickSafely(page, pagers.nth(index), route, actions, '分页', `分页按钮${index + 1}`, {
      exerciseAfterClick: false,
    })
  }
}

async function clickAllVisibleButtons(page: Page, route: RouteSpec, actions: ActionRecord[], scope?: Locator) {
  const seen = new Set<string>()
  const root = scope ?? pageScope(page)

  for (let index = 0; index < MAX_BUTTONS_PER_PAGE; index += 1) {
    const buttons = root.locator('button:visible, [role="button"]:visible')
    const total = await buttons.count().catch(() => 0)
    if (index >= total) {
      break
    }

    const button = buttons.nth(index)
    const label = await buttonLabel(button)
    const key = label || `button-${index}`
    if (seen.has(key)) {
      continue
    }
    seen.add(key)

    if (sessionEndingButtonText.test(label)) {
      actions.push({
        route: route.path,
        title: route.title,
        type: '按钮',
        label,
        status: 'skipped',
        detail: '跳过会中断后续巡检会话的按钮',
      })
      continue
    }

    if (excludedWalkthroughButtonText.test(label)) {
      actions.push({
        route: route.path,
        title: route.title,
        type: '按钮',
        label,
        status: 'skipped',
        detail: '按本轮测试要求跳过数字孪生界面',
      })
      continue
    }

    if (destructiveActionText.test(label)) {
      actions.push({
        route: route.path,
        title: route.title,
        type: '按钮',
        label,
        status: 'skipped',
        detail: '跳过可能没有二次确认的破坏性操作',
      })
      continue
    }

    if (!(await button.isEnabled().catch(() => false))) {
      actions.push({
        route: route.path,
        title: route.title,
        type: '按钮',
        label,
        status: 'skipped',
        detail: '按钮不可用',
      })
      continue
    }

    await clickSafely(page, button, route, actions, '按钮', label || `按钮${index + 1}`)
  }
}

async function clickSafely(
  page: Page,
  locator: Locator,
  route: RouteSpec,
  actions: ActionRecord[],
  type: string,
  label: string,
  options: { closeAfterClick?: boolean; exerciseAfterClick?: boolean } = {},
) {
  const beforeUrl = page.url()
  try {
    await page.bringToFront()
    console.log(`[manual-visible-walkthrough] action: ${route.title} ${type} ${label}`)
    await locator.scrollIntoViewIfNeeded({ timeout: 2500 }).catch(() => {})
    await locator.click({ timeout: 3500, noWaitAfter: true })
    actions.push({ route: route.path, title: route.title, type, label, status: 'clicked' })
    await writeActiveReport()
    await page.waitForTimeout(ACTION_MS)
    if (options.exerciseAfterClick !== false) {
      await exerciseTransientUi(page, route, actions)
    }
    if (options.closeAfterClick !== false) {
      await closeTransientUi(page, beforeUrl, actions, route)
    }
    return true
  } catch (error) {
    actions.push({
      route: route.path,
      title: route.title,
      type,
      label,
      status: 'skipped',
      detail: error instanceof Error ? error.message.slice(0, 260) : String(error).slice(0, 260),
    })
    await writeActiveReport()
    return false
  }
}

async function editEditableControls(
  page: Page,
  route: RouteSpec,
  actions: ActionRecord[],
  type: string,
  scope?: Locator,
) {
  const editableSelector = 'input:not([type="hidden"]):visible, textarea:visible, [contenteditable="true"]:visible'
  const edited = new Set<string>()
  const root = scope ?? pageScope(page)

  for (let index = 0; index < MAX_EDITABLES_PER_PAGE; index += 1) {
    const editables = root.locator(editableSelector)
    const total = await editables.count().catch(() => 0)
    if (index >= total) {
      break
    }

    const editable = editables.nth(index)
    const label = (await editableLabel(editable, index)) || `可编辑内容${index + 1}`
    const key = `${index}:${label}`
    if (edited.has(key)) {
      continue
    }
    edited.add(key)

    if (!(await isEditable(editable))) {
      actions.push({
        route: route.path,
        title: route.title,
        type,
        label,
        status: 'skipped',
        detail: '控件只读或不可用',
      })
      continue
    }

    try {
      await editable.scrollIntoViewIfNeeded({ timeout: 2500 }).catch(() => {})
      const tagName = ((await editable.evaluate((el) => el.tagName).catch(() => '')) as string).toLowerCase()
      const inputType = ((await editable.getAttribute('type').catch(() => '')) ?? '').toLowerCase()
      const value = await valueForEditable(editable, label, inputType, tagName, index)

      if (tagName === 'textarea' || tagName === 'input') {
        console.log(`[manual-visible-walkthrough] edit: ${route.title} ${label}`)
        await editable.fill(value, { timeout: 3500 })
      } else {
        console.log(`[manual-visible-walkthrough] edit: ${route.title} ${label}`)
        await editable.click({ timeout: 3500 })
        await page.keyboard.press(process.platform === 'darwin' ? 'Meta+A' : 'Control+A').catch(() => {})
        await page.keyboard.type(value, { delay: 30 }).catch(() => {})
      }

      actions.push({ route: route.path, title: route.title, type, label, status: 'clicked' })
      await writeActiveReport()
      await page.waitForTimeout(ACTION_MS)
    } catch (error) {
      actions.push({
        route: route.path,
        title: route.title,
        type,
        label,
        status: 'skipped',
        detail: error instanceof Error ? error.message.slice(0, 260) : String(error).slice(0, 260),
      })
      await writeActiveReport()
    }
  }

  await clickToggleControls(page, route, actions, root)
  await clickRadioControls(page, route, actions, root)
}

async function clickToggleControls(page: Page, route: RouteSpec, actions: ActionRecord[], scope?: Locator) {
  const toggles = (scope ?? pageScope(page)).locator(
    '.el-switch:visible, .el-checkbox:visible, [role="switch"]:visible, input[type="checkbox"]:visible',
  )
  const total = await toggles.count().catch(() => 0)
  const seen = new Set<string>()

  const limit = Math.min(total, MAX_TOGGLES_PER_PAGE)
  for (let index = 0; index < limit; index += 1) {
    const toggle = toggles.nth(index)
    const label = (await buttonLabel(toggle)) || `开关/复选${index + 1}`
    const key = `${index}:${label}`
    if (seen.has(key)) {
      continue
    }
    seen.add(key)
    const toggled = await clickSafely(page, toggle, route, actions, '开关/复选', label, {
      closeAfterClick: false,
      exerciseAfterClick: false,
    })
    if (toggled) {
      await clickSafely(page, toggle, route, actions, '开关/复选恢复', `${label}（恢复原状态）`, {
        closeAfterClick: false,
        exerciseAfterClick: false,
      })
    }
  }

  if (total > MAX_TOGGLES_PER_PAGE) {
    actions.push({
      route: route.path,
      title: route.title,
      type: '开关/复选',
      label: `剩余 ${total - MAX_TOGGLES_PER_PAGE} 个动态开关`,
      status: 'skipped',
      detail: '超过单页动态开关巡检上限，避免重复控件导致巡检无法收尾',
    })
  }
}

async function clickRadioControls(page: Page, route: RouteSpec, actions: ActionRecord[], scope?: Locator) {
  const root = scope ?? pageScope(page)
  const groups = root.locator('.el-radio-group:visible, [role="radiogroup"]:visible')
  const groupCount = await groups.count().catch(() => 0)

  for (let groupIndex = 0; groupIndex < groupCount; groupIndex += 1) {
    const radios = groups.nth(groupIndex).locator('.el-radio:visible, [role="radio"]:visible')
    const total = Math.min(await radios.count().catch(() => 0), MAX_TOGGLES_PER_PAGE)
    let originalIndex = -1

    for (let index = 0; index < total; index += 1) {
      const radio = radios.nth(index)
      const checked =
        (await radio.getAttribute('aria-checked').catch(() => null)) === 'true' ||
        (await radio.evaluate((element) => element.classList.contains('is-checked')).catch(() => false)) ||
        (await radio.locator('input[type="radio"]').isChecked().catch(() => false))
      if (checked) originalIndex = index
      await clickSafely(
        page,
        radio,
        route,
        actions,
        '单选项',
        (await buttonLabel(radio)) || `单选组${groupIndex + 1}选项${index + 1}`,
        { closeAfterClick: false, exerciseAfterClick: false },
      )
    }

    if (originalIndex >= 0 && total > 1) {
      const original = radios.nth(originalIndex)
      await clickSafely(
        page,
        original,
        route,
        actions,
        '单选项恢复',
        `${(await buttonLabel(original)) || `单选组${groupIndex + 1}选项${originalIndex + 1}`}（恢复原状态）`,
        { closeAfterClick: false, exerciseAfterClick: false },
      )
    }
  }
}

async function exerciseTransientUi(page: Page, route: RouteSpec, actions: ActionRecord[]) {
  await settle(page)

  const popConfirm = page.locator('.el-popconfirm:visible').last()
  if (await popConfirm.isVisible().catch(() => false)) {
    await page.waitForTimeout(ACTION_MS)
    const popConfirmText = await popConfirm.innerText().catch(() => '')
    if (destructiveActionText.test(popConfirmText)) {
      const cancel = popConfirm.getByRole('button', { name: closeButtonText }).first()
      if (await cancel.isVisible().catch(() => false)) {
        await clickAndRecord(page, cancel, route, actions, '确认气泡', '跳过破坏性操作')
      }
      return
    }
    const confirm = popConfirm.getByRole('button', { name: confirmButtonText }).last()
    if (await confirm.isVisible().catch(() => false)) {
      await clickAndRecord(page, confirm, route, actions, '确认气泡', '确认')
    }
    return
  }

  const messageBox = page.locator('.el-message-box:visible').last()
  if (await messageBox.isVisible().catch(() => false)) {
    await page.waitForTimeout(ACTION_MS)
    const messageBoxText = await messageBox.innerText().catch(() => '')
    if (destructiveActionText.test(messageBoxText)) {
      const cancel = messageBox.getByRole('button', { name: closeButtonText }).first()
      if (await cancel.isVisible().catch(() => false)) {
        await clickAndRecord(page, cancel, route, actions, '确认弹窗', '跳过破坏性操作')
      }
      return
    }
    const confirm = messageBox.getByRole('button', { name: confirmButtonText }).last()
    if (await confirm.isVisible().catch(() => false)) {
      await clickAndRecord(page, confirm, route, actions, '确认弹窗', '确认')
      return
    }
    const cancel = messageBox.getByRole('button', { name: closeButtonText }).first()
    if (await cancel.isVisible().catch(() => false)) {
      await clickAndRecord(page, cancel, route, actions, '确认弹窗', '取消/关闭')
    }
    return
  }

  const dialog = page.locator('.el-dialog:visible, .el-drawer:visible').last()
  if (await dialog.isVisible().catch(() => false)) {
    await editDialogFields(dialog, page, route, actions)
    await clickToggleControls(page, route, actions, dialog)
    await clickRadioControls(page, route, actions, dialog)
    await clickSelectLikeControls(page, route, actions, dialog)
    const dialogText = await dialog.innerText().catch(() => '')
    if (destructiveActionText.test(dialogText)) {
      const cancel = dialog.getByRole('button', { name: closeButtonText }).first()
      if (await cancel.isVisible().catch(() => false)) {
        await clickAndRecord(page, cancel, route, actions, '弹窗/抽屉提交', '跳过破坏性操作')
      }
      return
    }
    const confirm = dialog.getByRole('button', { name: confirmButtonText }).last()
    if (await confirm.isVisible().catch(() => false) && (await confirm.isEnabled().catch(() => false))) {
      await clickAndRecord(page, confirm, route, actions, '弹窗/抽屉提交', await buttonLabel(confirm))
      await page.waitForTimeout(ACTION_MS)
    }
  }
}

async function editDialogFields(dialog: Locator, page: Page, route: RouteSpec, actions: ActionRecord[]) {
  const editables = dialog.locator('input:not([type="hidden"]):visible, textarea:visible, [contenteditable="true"]:visible')
  const total = await editables.count().catch(() => 0)
  for (let index = 0; index < Math.min(total, 4); index += 1) {
    const editable = editables.nth(index)
    const label = (await editableLabel(editable, index)) || `弹窗可编辑内容${index + 1}`
    if (!(await isEditable(editable))) {
      actions.push({
        route: route.path,
        title: route.title,
        type: '弹窗/抽屉可编辑内容',
        label,
        status: 'skipped',
        detail: '控件只读或不可用',
      })
      continue
    }

    try {
      await editable.scrollIntoViewIfNeeded({ timeout: 2500 }).catch(() => {})
      const tagName = ((await editable.evaluate((el) => el.tagName).catch(() => '')) as string).toLowerCase()
      const inputType = ((await editable.getAttribute('type').catch(() => '')) ?? '').toLowerCase()
      const value = await valueForEditable(editable, label, inputType, tagName, index)
      console.log(`[manual-visible-walkthrough] dialog edit: ${route.title} ${label}`)
      if (tagName === 'textarea' || tagName === 'input') {
        await editable.fill(value, { timeout: 3500 })
      } else {
        await editable.click({ timeout: 3500 })
        await page.keyboard.press(process.platform === 'darwin' ? 'Meta+A' : 'Control+A').catch(() => {})
        await page.keyboard.type(value, { delay: 30 }).catch(() => {})
      }
      actions.push({ route: route.path, title: route.title, type: '弹窗/抽屉可编辑内容', label, status: 'clicked' })
      await writeActiveReport()
      await page.waitForTimeout(ACTION_MS)
    } catch (error) {
      actions.push({
        route: route.path,
        title: route.title,
        type: '弹窗/抽屉可编辑内容',
        label,
        status: 'skipped',
        detail: error instanceof Error ? error.message.slice(0, 260) : String(error).slice(0, 260),
      })
      await writeActiveReport()
    }
  }
}

async function clickAndRecord(
  page: Page,
  locator: Locator,
  route: RouteSpec,
  actions: ActionRecord[],
  type: string,
  label: string,
) {
  try {
    console.log(`[manual-visible-walkthrough] action: ${route.title} ${type} ${label || type}`)
    await locator.scrollIntoViewIfNeeded({ timeout: 2500 }).catch(() => {})
    await locator.click({ timeout: 3500, noWaitAfter: true })
    actions.push({ route: route.path, title: route.title, type, label: label || type, status: 'clicked' })
    await writeActiveReport()
    await page.waitForTimeout(ACTION_MS)
  } catch (error) {
    actions.push({
      route: route.path,
      title: route.title,
      type,
      label: label || type,
      status: 'skipped',
      detail: error instanceof Error ? error.message.slice(0, 260) : String(error).slice(0, 260),
    })
    await writeActiveReport()
  }
}

async function closeTransientUi(page: Page, beforeUrl: string, actions: ActionRecord[], route: RouteSpec) {
  await settle(page)

  const dialog = page.locator('.el-dialog:visible, .el-drawer:visible').last()
  if ((await dialog.count().catch(() => 0)) > 0) {
    await page.waitForTimeout(900)
    const cancelButton = dialog.getByRole('button', { name: /取消|关闭|返回/ }).first()
    if (await cancelButton.isVisible().catch(() => false)) {
      await cancelButton.click({ timeout: 2500 }).catch(() => {})
    } else {
      const closeButton = page.locator('.el-dialog__headerbtn:visible, .el-drawer__close-btn:visible').last()
      if (await closeButton.isVisible().catch(() => false)) {
        await closeButton.click({ timeout: 2500 }).catch(() => {})
      } else {
        await page.keyboard.press('Escape').catch(() => {})
      }
    }
    actions.push({
      route: route.path,
      title: route.title,
      type: '弹窗/抽屉',
      label: '关闭或取消',
      status: 'clicked',
    })
    await page.waitForTimeout(ACTION_MS)
  } else {
    await page.keyboard.press('Escape').catch(() => {})
  }

  if (pathname(page.url()) !== pathname(beforeUrl)) {
    await page.goto(beforeUrl, { waitUntil: 'domcontentloaded', timeout: 20000 }).catch(async () => {
      await page.goto(route.path, { waitUntil: 'domcontentloaded', timeout: 20000 })
    })
    await settle(page)
    await page.waitForTimeout(ACTION_MS)
  }
}

async function settle(page: Page) {
  await page.waitForLoadState('domcontentloaded', { timeout: 15000 }).catch(() => {})
  await page.waitForLoadState('networkidle', { timeout: 2500 }).catch(() => {})
  await page.locator('.el-loading-mask:visible').first().waitFor({ state: 'hidden', timeout: 2500 }).catch(() => {})
}

async function holdVisible(page: Page, label: string) {
  await page.bringToFront()
  console.log(`[manual-visible-walkthrough] hold ${VISIBLE_MS}ms: ${label}`)
  await page.waitForTimeout(VISIBLE_MS)
}

async function screenshot(page: Page, name: string) {
  const filePath = path.join(ARTIFACT_DIR, name)
  await page.screenshot({ path: filePath, fullPage: false }).catch(() => undefined)
  return filePath
}

async function buttonLabel(locator: Locator) {
  const text = normalize(await locator.innerText({ timeout: 500 }).catch(() => ''))
  if (text) {
    return text
  }
  const aria = normalize((await locator.getAttribute('aria-label', { timeout: 300 }).catch(() => '')) ?? '')
  if (aria) {
    return aria
  }
  const title = normalize((await locator.getAttribute('title', { timeout: 300 }).catch(() => '')) ?? '')
  if (title) {
    return title
  }
  const placeholder = normalize((await locator.getAttribute('placeholder', { timeout: 300 }).catch(() => '')) ?? '')
  if (placeholder) {
    return placeholder
  }
  const className = normalize((await locator.getAttribute('class', { timeout: 300 }).catch(() => '')) ?? '')
  return className ? `图标按钮:${className.slice(0, 40)}` : ''
}

async function editableLabel(locator: Locator, index: number) {
  const aria = normalize((await locator.getAttribute('aria-label', { timeout: 300 }).catch(() => '')) ?? '')
  if (aria) {
    return aria
  }
  const placeholder = normalize((await locator.getAttribute('placeholder', { timeout: 300 }).catch(() => '')) ?? '')
  if (placeholder) {
    return placeholder
  }
  const formLabel = normalize(
    (await locator
      .evaluate((element) => element.closest('.el-form-item')?.querySelector('.el-form-item__label')?.textContent ?? '')
      .catch(() => '')) as string,
  )
  if (formLabel) {
    return formLabel
  }
  const name = normalize((await locator.getAttribute('name', { timeout: 300 }).catch(() => '')) ?? '')
  if (name) {
    return name
  }
  const type = normalize((await locator.getAttribute('type', { timeout: 300 }).catch(() => '')) ?? '')
  return type ? `${type}输入${index + 1}` : `输入${index + 1}`
}

async function isEditable(locator: Locator) {
  const disabled = await locator.isDisabled({ timeout: CONTROL_TIMEOUT_MS }).catch(() => true)
  if (disabled) {
    return false
  }
  const readonly = await locator.getAttribute('readonly', { timeout: CONTROL_TIMEOUT_MS }).catch(() => null)
  if (readonly !== null) {
    return false
  }
  const inputType = ((await locator.getAttribute('type').catch(() => '')) ?? '').toLowerCase()
  return !['button', 'submit', 'reset', 'file', 'checkbox', 'radio'].includes(inputType)
}

async function valueForEditable(locator: Locator, label: string, inputType: string, tagName: string, index: number) {
  if (/日期|date/i.test(label)) {
    return new Date().toISOString().slice(0, 10)
  }
  const role = (await locator.getAttribute('role', { timeout: CONTROL_TIMEOUT_MS }).catch(() => null)) ?? ''
  if (inputType === 'number' || role === 'spinbutton' || /天数|数量|时长|阈值/.test(label)) {
    const min = parseOptionalNumber(
      (await locator.getAttribute('min').catch(() => null)) ??
        (await locator.getAttribute('aria-valuemin').catch(() => null)),
    )
    const max = parseOptionalNumber(
      (await locator.getAttribute('max').catch(() => null)) ??
        (await locator.getAttribute('aria-valuemax').catch(() => null)),
    )
    const step = parseOptionalNumber(await locator.getAttribute('step').catch(() => null))
    const floor = Number.isFinite(min) ? min : 1
    const ceiling = Number.isFinite(max) ? max : floor + 8
    const increment = Number.isFinite(step) && step > 0 ? step : 1
    const candidate = Math.min(ceiling, Math.max(floor, floor + increment))
    return String(Number.isInteger(candidate) ? candidate : candidate.toFixed(3))
  }
  return testValueFor(label, inputType, tagName, index)
}

function parseOptionalNumber(value: string | null) {
  if (value === null || value.trim() === '') {
    return Number.NaN
  }
  return Number(value)
}

function testValueFor(label: string, inputType: string, tagName: string, index: number) {
  if (/页|page/i.test(label)) {
    return '1'
  }
  if (inputType === 'email' || /邮箱|email/i.test(label)) {
    return `walkthrough-${RUN_ID}-${index}@example.com`
  }
  if (inputType === 'tel' || /电话|手机|phone/i.test(label)) {
    return '13800138000'
  }
  if (inputType === 'url') {
    return 'https://example.com'
  }
  if (inputType === 'password') {
    return 'admin123'
  }
  if (tagName === 'textarea' || /描述|备注|说明|内容|原因/.test(label)) {
    return `自动化可视巡检编辑内容 ${RUN_ID}-${index + 1}`
  }
  if (/编码|编号|code/i.test(label)) {
    return `AUTO-${RUN_ID}-${Date.now().toString(36).slice(-5)}-${index}`
  }
  return `自动化巡检${RUN_ID}-${index + 1}`
}

function normalize(value: string) {
  return value.replace(/\s+/g, ' ').trim()
}

function pageScope(page: Page) {
  return page.locator(PAGE_SCOPE_SELECTOR).first()
}

function pathname(url: string) {
  try {
    return new URL(url).pathname
  } catch {
    return url
  }
}

function slug(value: string) {
  return value.replace(/^\//, '').replace(/[^\w-]+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '') || 'root'
}

function dedupeIssues(issues: IssueRecord[]) {
  const seen = new Set<string>()
  const deduped: IssueRecord[] = []
  for (const issue of issues) {
    const key = `${issue.route}|${issue.type}|${issue.status ?? ''}|${issue.url ?? ''}|${issue.detail}`
    if (seen.has(key)) {
      continue
    }
    seen.add(key)
    deduped.push(issue)
  }
  return deduped
}

async function writeActiveReport() {
  if (!activeReport) {
    return
  }
  await writeReport({
    startedAt: activeReport.startedAt,
    endedAt: new Date(),
    routes: activeReport.routes,
    issues: dedupeIssues(activeReport.issues),
  })
}

async function writeReport(summary: {
  startedAt: Date
  endedAt: Date
  routes: RouteRecord[]
  issues: IssueRecord[]
}) {
  const clickedActions = summary.routes.flatMap((route) => route.actions).filter((action) => action.status === 'clicked')
  const skippedActions = summary.routes.flatMap((route) => route.actions).filter((action) => action.status === 'skipped')
  const rangeSuffix = `${ROUTE_START}-${ROUTE_END > 0 ? ROUTE_END : routes.length}`
  const jsonPath = path.join(ARTIFACT_DIR, `summary-${rangeSuffix}.json`)
  const markdownPath = path.join(ARTIFACT_DIR, `summary-${rangeSuffix}.md`)
  const latestJsonPath = path.join(ARTIFACT_DIR, 'summary.json')
  const latestMarkdownPath = path.join(ARTIFACT_DIR, 'summary.md')

  const jsonContent = JSON.stringify(
    {
      ...summary,
      startedAt: summary.startedAt.toISOString(),
      endedAt: summary.endedAt.toISOString(),
      visibleMsPerPage: VISIBLE_MS,
      routeRange: rangeSuffix,
      clickedActionCount: clickedActions.length,
      skippedActionCount: skippedActions.length,
    },
    null,
    2,
  )
  fs.writeFileSync(jsonPath, jsonContent)
  fs.writeFileSync(latestJsonPath, jsonContent)

  const lines = [
    '# 可视化逐页巡检报告',
    '',
    `- 开始时间: ${summary.startedAt.toISOString()}`,
    `- 结束时间: ${summary.endedAt.toISOString()}`,
    `- 页面停留: 每页 ${VISIBLE_MS}ms`,
    `- 路由范围: ${ROUTE_START}-${ROUTE_END > 0 ? ROUTE_END : routes.length}`,
    `- 覆盖页面: ${summary.routes.length}`,
    `- 已点击安全功能: ${clickedActions.length}`,
    `- 跳过高风险或不可用功能: ${skippedActions.length}`,
    `- 问题数: ${summary.issues.length}`,
    '',
    '## 页面与点击记录',
    '',
    ...summary.routes.map((route, index) => {
      const clicked = route.actions.filter((action) => action.status === 'clicked').length
      const skipped = route.actions.filter((action) => action.status === 'skipped').length
      return `${index + 1}. ${route.title} (${route.path}) - 点击 ${clicked}，跳过 ${skipped}`
    }),
    '',
    '## 问题记录',
    '',
    summary.issues.length === 0
      ? '- 未捕获到 console.error、pageerror、requestfailed 或 5xx 接口响应。'
      : summary.issues
          .slice(0, 120)
          .map((issue) => `- [${issue.route}] ${issue.type}${issue.status ? ` ${issue.status}` : ''}: ${issue.detail}${issue.url ? ` (${issue.url})` : ''}`)
          .join('\n'),
  ]

  const markdownContent = lines.join('\n')
  fs.writeFileSync(markdownPath, markdownContent)
  fs.writeFileSync(latestMarkdownPath, markdownContent)
}
