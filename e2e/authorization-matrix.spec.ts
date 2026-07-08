import { test, expect, type APIRequestContext } from '@playwright/test'
import fs from 'fs'
import path from 'path'

const authFile = path.join(__dirname, '.auth', 'admin.json')

type TestUser = {
  id: number
  username: string
  password: string
  token: string
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

async function createUser(request: APIRequestContext, adminToken: string, role: 'operator' | 'viewer'): Promise<TestUser> {
  const suffix = `${Date.now()}_${Math.random().toString(16).slice(2, 8)}`
  const username = `auth_${role}_${suffix}`
  const password = 'Matrix@12345'

  const createResp = await request.post('/api/v1/users', {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: {
      username,
      password,
      role,
      real_name: `权限矩阵${role}`,
      department: '自动化测试'
    }
  })
  expect(createResp.status(), `创建 ${role} 测试用户失败: ${await createResp.text()}`).toBe(200)
  const created = await createResp.json()

  const loginResp = await request.post('/api/v1/auth/login', {
    form: { username, password }
  })
  expect(loginResp.status(), `${role} 测试用户登录失败: ${await loginResp.text()}`).toBe(200)
  const loginBody = await loginResp.json()

  return {
    id: created.id,
    username,
    password,
    token: loginBody.access_token
  }
}

test.describe('权限/越权矩阵', () => {
  test.describe.configure({ mode: 'serial' })

  let adminToken: string
  let operatorUser: TestUser
  let viewerUser: TestUser

  test.beforeAll(async ({ request }) => {
    adminToken = getAdminTokenFromStorageState()
    operatorUser = await createUser(request, adminToken, 'operator')
    viewerUser = await createUser(request, adminToken, 'viewer')
  })

  test.afterAll(async ({ request }) => {
    for (const user of [operatorUser, viewerUser]) {
      if (!user?.id) continue
      await request.delete(`/api/v1/users/${user.id}`, {
        headers: { Authorization: `Bearer ${adminToken}` }
      })
    }
  })

  test('未登录访问受保护接口应返回 401', async ({ request }) => {
    const resp = await request.get('/api/v1/statistics/overview')
    expect(resp.status()).toBe(401)
  })

  test('伪造 token 访问只读接口应返回 401', async ({ request }) => {
    const resp = await request.get('/api/v1/devices?page_size=1', {
      headers: { Authorization: 'Bearer invalid.token.value' }
    })
    expect(resp.status()).toBe(401)
  })

  test('admin 可访问用户管理接口', async ({ request }) => {
    const resp = await request.get('/api/v1/users?page_size=1', {
      headers: { Authorization: `Bearer ${adminToken}` }
    })
    expect(resp.status()).toBe(200)
  })

  test('operator 不可访问 admin-only 用户管理接口', async ({ request }) => {
    const resp = await request.get('/api/v1/users?page_size=1', {
      headers: { Authorization: `Bearer ${operatorUser.token}` }
    })
    expect(resp.status()).toBe(403)
  })

  test('viewer 可访问只读设备列表', async ({ request }) => {
    const resp = await request.get('/api/v1/devices?page_size=1', {
      headers: { Authorization: `Bearer ${viewerUser.token}` }
    })
    expect(resp.status()).toBe(200)
  })

  test('viewer 不可创建设备', async ({ request }) => {
    const resp = await request.post('/api/v1/devices', {
      headers: { Authorization: `Bearer ${viewerUser.token}` },
      data: {
        device_code: `AUTH_MATRIX_${Date.now()}`,
        device_name: '权限矩阵越权设备',
        device_type: 'TEST',
        area_code: 'AUTO'
      }
    })
    expect(resp.status()).toBe(403)
  })
})
