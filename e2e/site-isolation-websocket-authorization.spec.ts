import { expect, test, type APIRequestContext, type Page } from '@playwright/test'
import fs from 'fs'
import path from 'path'

const authFile = process.env.E2E_AUTH_FILE || path.join(__dirname, '.auth', 'admin.json')

type TestUser = {
  id: number
  username: string
  password: string
  token: string
}

type TestSite = {
  id: number
  site_code: string
}

type TestDevice = {
  id: number
  device_code: string
}

type SocketClose = {
  code: number
  reason: string
}

function getAdminTokenFromStorageState(): string {
  const storage = JSON.parse(fs.readFileSync(authFile, 'utf-8')) as {
    origins?: Array<{ localStorage?: Array<{ name: string; value: string }> }>
  }
  const token = storage.origins
    ?.flatMap(item => item.localStorage ?? [])
    .find(item => item.name === 'token')?.value
  if (!token) {
    throw new Error(`未在 ${authFile} 中找到 admin token，请先运行 auth.setup.ts`)
  }
  return token
}

function bearer(token: string) {
  return { Authorization: `Bearer ${token}` }
}

async function login(request: APIRequestContext, username: string, password: string): Promise<string> {
  const response = await request.post('/api/v1/auth/login', {
    form: { username, password },
  })
  expect(response.status(), `登录失败: ${await response.text()}`).toBe(200)
  return (await response.json()).access_token
}

async function refreshToken(request: APIRequestContext, token: string): Promise<string> {
  const response = await request.post('/api/v1/auth/refresh', {
    headers: bearer(token),
  })
  expect(response.status(), `刷新令牌失败: ${await response.text()}`).toBe(200)
  return (await response.json()).access_token
}

async function openAuthenticatedSocket(page: Page, token: string, channel = 'realtime'): Promise<void> {
  await page.goto('/login')
  await page.evaluate(
    ({ accessToken, targetChannel }) => new Promise<void>((resolve, reject) => {
      const state = window as unknown as {
        __authzSocket?: WebSocket
        __authzSocketClose?: SocketClose | null
      }
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const socket = new WebSocket(`${protocol}//${window.location.host}/ws/${targetChannel}`)
      state.__authzSocket = socket
      state.__authzSocketClose = null
      let authenticated = false

      socket.addEventListener('open', () => {
        socket.send(JSON.stringify({ action: 'authenticate', token: accessToken }))
      })
      socket.addEventListener('message', event => {
        const message = JSON.parse(String(event.data))
        if (message.type === 'authenticated') {
          authenticated = true
          resolve()
        }
      })
      socket.addEventListener('close', event => {
        state.__authzSocketClose = { code: event.code, reason: event.reason }
        if (!authenticated) {
          reject(new Error(`WebSocket 认证前关闭: ${event.code}`))
        }
      })
      socket.addEventListener('error', () => reject(new Error('WebSocket 连接失败')), { once: true })
    }),
    { accessToken: token, targetChannel: channel },
  )
}

async function waitForSocketClose(page: Page): Promise<SocketClose> {
  return page.evaluate(() => {
    const state = window as unknown as {
      __authzSocket?: WebSocket
      __authzSocketClose?: SocketClose | null
    }
    if (state.__authzSocketClose) return state.__authzSocketClose
    if (!state.__authzSocket) throw new Error('WebSocket 尚未建立')
    return new Promise<SocketClose>(resolve => {
      state.__authzSocket!.addEventListener(
        'close',
        event => resolve({ code: event.code, reason: event.reason }),
        { once: true },
      )
    })
  })
}

test.describe('Story 39.1 双站点 HTTP 与 WebSocket 授权矩阵', () => {
  test.describe.configure({ mode: 'serial', retries: 0 })

  let adminToken = ''
  let operator: TestUser
  let siteA: TestSite
  let siteB: TestSite
  let deviceA: TestDevice
  let deviceB: TestDevice

  test.beforeAll(async ({ request }) => {
    adminToken = getAdminTokenFromStorageState()
    const suffix = `${Date.now()}_${process.pid}`

    const siteAResponse = await request.post('/api/v1/spatial/sites', {
      headers: bearer(adminToken),
      data: { site_code: `E2E-A-${suffix}`, site_name: 'E2E 授权站点 A' },
    })
    expect(siteAResponse.status(), await siteAResponse.text()).toBe(200)
    siteA = await siteAResponse.json()

    const siteBResponse = await request.post('/api/v1/spatial/sites', {
      headers: bearer(adminToken),
      data: { site_code: `E2E-B-${suffix}`, site_name: 'E2E 隔离站点 B' },
    })
    expect(siteBResponse.status(), await siteBResponse.text()).toBe(200)
    siteB = await siteBResponse.json()

    const userResponse = await request.post('/api/v1/users', {
      headers: bearer(adminToken),
      data: {
        username: `e2e_operator_${suffix}`,
        password: 'Matrix@12345',
        role: 'operator',
        real_name: 'Story 39.1 E2E 操作员',
      },
    })
    expect(userResponse.status(), await userResponse.text()).toBe(200)
    const createdUser = await userResponse.json()
    operator = {
      id: createdUser.id,
      username: createdUser.username,
      password: 'Matrix@12345',
      token: '',
    }

    const siteGrantResponse = await request.put(`/api/v1/users/${operator.id}/sites`, {
      headers: bearer(adminToken),
      data: { site_ids: [siteA.id] },
    })
    expect(siteGrantResponse.status(), await siteGrantResponse.text()).toBe(200)

    const deviceAResponse = await request.post('/api/v1/devices', {
      headers: bearer(adminToken),
      data: {
        device_code: `E2E-DA-${suffix}`,
        device_name: 'E2E A 站设备',
        device_type: 'UPS',
        area_code: 'E2E-A',
        site_id: siteA.id,
      },
    })
    expect(deviceAResponse.status(), await deviceAResponse.text()).toBe(200)
    deviceA = await deviceAResponse.json()

    const deviceBResponse = await request.post('/api/v1/devices', {
      headers: bearer(adminToken),
      data: {
        device_code: `E2E-DB-${suffix}`,
        device_name: 'E2E B 站设备',
        device_type: 'UPS',
        area_code: 'E2E-B',
        site_id: siteB.id,
      },
    })
    expect(deviceBResponse.status(), await deviceBResponse.text()).toBe(200)
    deviceB = await deviceBResponse.json()

    operator.token = await login(request, operator.username, operator.password)
  })

  test.afterAll(async ({ request }) => {
    for (const device of [deviceA, deviceB]) {
      if (!device?.id) continue
      await request.delete(`/api/v1/devices/${device.id}?force=true`, { headers: bearer(adminToken) })
    }
    if (operator?.id) {
      await request.delete(`/api/v1/users/${operator.id}`, { headers: bearer(adminToken) })
    }
    for (const site of [siteA, siteB]) {
      if (!site?.id) continue
      await request.delete(`/api/v1/spatial/sites/${site.id}`, { headers: bearer(adminToken) })
    }
  })

  test('服务端列表仅返回 A 站，B 站详情与猜测 ID 都返回 404', async ({ request }) => {
    const listResponse = await request.get('/api/v1/devices?page_size=100', {
      headers: bearer(operator.token),
    })
    expect(listResponse.status()).toBe(200)
    const ids = (await listResponse.json()).items.map((item: { id: number }) => item.id)
    expect(ids).toContain(deviceA.id)
    expect(ids).not.toContain(deviceB.id)

    const forbiddenDetail = await request.get(`/api/v1/devices/${deviceB.id}`, {
      headers: bearer(operator.token),
    })
    const missingDetail = await request.get('/api/v1/devices/2147483647', {
      headers: bearer(operator.token),
    })
    expect(forbiddenDetail.status()).toBe(404)
    expect(missingDetail.status()).toBe(404)
  })

  test('跨站点创建和改绑在任何写入前返回 403', async ({ request }) => {
    const createResponse = await request.post('/api/v1/devices', {
      headers: bearer(operator.token),
      data: {
        device_code: `E2E-CROSS-${Date.now()}`,
        device_name: '跨站点创建必须失败',
        device_type: 'UPS',
        area_code: 'E2E-B',
        site_id: siteB.id,
      },
    })
    expect(createResponse.status()).toBe(403)

    const rebindResponse = await request.put(`/api/v1/devices/${deviceA.id}`, {
      headers: bearer(operator.token),
      data: { site_id: siteB.id },
    })
    expect(rebindResponse.status()).toBe(403)

    const detailResponse = await request.get(`/api/v1/devices/${deviceA.id}`, {
      headers: bearer(operator.token),
    })
    expect(detailResponse.status()).toBe(200)
    expect((await detailResponse.json()).site_id).toBe(siteA.id)
  })

  test('绕过前端筛选订阅 B 站实时流时由服务端以 4001 关闭', async ({ page }) => {
    await openAuthenticatedSocket(page, operator.token)
    const closePromise = waitForSocketClose(page)
    await page.evaluate(targetSiteId => {
      const state = window as unknown as { __authzSocket?: WebSocket }
      state.__authzSocket!.send(JSON.stringify({
        action: 'subscribe',
        filters: { site_ids: [targetSiteId] },
      }))
    }, siteB.id)

    expect((await closePromise).code).toBe(4001)
  })

  test('登出提交后活动 WebSocket 在下一条业务消息前失效', async ({ page, request }) => {
    const token = await refreshToken(request, operator.token)
    await openAuthenticatedSocket(page, token)
    const closePromise = waitForSocketClose(page)

    const logoutResponse = await request.post('/api/v1/auth/logout', {
      headers: bearer(token),
    })
    expect(logoutResponse.status()).toBe(200)
    expect((await closePromise).code).toBe(4001)
  })

  test('角色降级提交后活动 WebSocket 立即失效', async ({ page, request }) => {
    await openAuthenticatedSocket(page, operator.token)
    const closePromise = waitForSocketClose(page)

    const downgradeResponse = await request.put(`/api/v1/users/${operator.id}`, {
      headers: bearer(adminToken),
      data: { role: 'viewer' },
    })
    expect(downgradeResponse.status(), await downgradeResponse.text()).toBe(200)
    expect((await closePromise).code).toBe(4001)
  })
})
