# Story 27.6: 站点过滤贯穿数据链路

> **Epic**: 27 - 前端数据链路统一
> **Priority**: P2
> **Status**: done
> **依赖**: Epic 22 (站点管理前端), Story 27.1-27.5
> **参考**: docs/data-flow-audit.md Issue P1-6 (Plan F)
> **审查**: 两轮对抗性审查完成，所有修复已应用

---

## 用户故事

**作为** 多站点部署的运维人员，
**我希望** 切换站点后所有页面数据自动过滤为当前站点，
**以便** 我只看到当前关注站点的告警、实时数据和能源信息，不被其他站点数据干扰。

---

## 背景

### 当前问题 (data-flow-audit.md P1-6)

1. `useAlarm` composable 的 `fetchActiveAlarms()` 不传 `site_id` 参数
2. `useRealtime` composable 的 `fetchRealtimeData()` 不传 `site_id` 参数
3. `useEnergy` composable 的 `loadRealtimePower()` 不传 `site_id` 参数
4. API 模块层面支持 `site_id` 参数，但调用方未使用
5. WebSocket subscribe 不支持 `site_id` 过滤
6. `switchSite()` 不触发数据重新加载

### 已有基础设施

| 组件 | 状态 | 位置 |
|------|------|------|
| useSiteStore | 已实现 | stores/site.ts |
| useSiteFilter composable | 已实现 | composables/useSiteFilter.ts（本 Story 完成后标记为 deprecated） |
| SiteSwitcher.vue | 已实现 | components/common/SiteSwitcher.vue |
| 后端 site_id 参数 | 已支持 | 各 API endpoint 的 Query 参数 |
| 后端 RBAC 站点过滤 | 已实现 | api/deps.py get_user_site_ids |
| axios request interceptor | 无 site_id 注入 | utils/request.ts |

---

## 验收标准

### AC-1: axios 请求拦截器自动注入 site_id

- [ ] 修改 `utils/request.ts`，在请求拦截器中自动注入 `site_id`
- [ ] 直接从 `localStorage.getItem('current_site_id')` 读取（避免 Pinia 生命周期问题）
- [ ] 仅当 `currentSiteId` 有值时注入（null 时 localStorage 返回 null，因为使用 `removeItem` 清除）
- [ ] **所有 HTTP 方法**都注入到 `config.params`（URL query string），不注入到 request body
- [ ] 如果请求已手动指定 `site_id`，不覆盖（手动优先）
- [ ] 排除不需要站点过滤的 API 路径（使用精确前缀+斜杠匹配，避免前缀误匹配）

### AC-2: switchSite() 触发全局数据重新加载

- [ ] `siteStore.switchSite(siteId)` 执行后触发以下 Store 重新加载：
  - `alarmStore.fetchActiveAlarms()`
  - `realtimeStore.reload()`
  - `energyStore.reload()`
- [ ] 使用零依赖自定义事件总线（不引入 mitt，项目无此依赖）
- [ ] 事件总线放在独立文件 `utils/siteEvents.ts`
- [ ] 各 Store 在 setup 函数内部使用具名函数订阅事件，避免 HMR 重复注册
- [ ] 重新加载时使用新的 site_id（由拦截器自动注入）
- [ ] 站点切换时使用版本号模式防止竞态条件（旧请求响应不覆盖新数据）

### AC-3: WebSocket 站点切换时重连

- [ ] `useWebSocketManager` 新增 `reconnectAll()` 方法
- [ ] manager 内部维护 `subscriptions` 记录（channel -> subscribe options），disconnect 不丢失
- [ ] `reconnectAll()` 基于 subscriptions 记录重新连接，使用 `WebSocketClient.subscribe()` 方法重新订阅
- [ ] `switchSite()` 触发 WebSocket 全部断开 -> 重连 -> 重新订阅

### AC-4: "全部站点" 模式

- [ ] 当 `currentSiteId` 为 null 时（localStorage 无 `current_site_id` key），不注入 `site_id`，显示所有站点数据
- [ ] 这是默认状态（首次访问或选择"全部站点"时）
- [ ] 后端 RBAC 仍然生效（非 admin 用户只能看到授权站点的数据）

### AC-5: 排除路径配置

- [ ] 定义常量 `SITE_FILTER_EXCLUDED_PATHS`，使用精确前缀+斜杠匹配
- [ ] 包含：`/v1/auth/`, `/v1/spatial/sites`, `/v1/system/`, `/v1/users/`, `/v1/demo/`, `/v1/configs/`, `/v1/logs/`
- [ ] 匹配逻辑：`url === path || url.startsWith(path.endsWith('/') ? path : path + '/')`
- [ ] 后端不支持 `site_id` 的端点额外加入排除列表

### AC-6: useSiteFilter composable 处理

- [ ] 在 `composables/useSiteFilter.ts` 文件顶部添加 `@deprecated` 注释
- [ ] 说明拦截器已自动处理 site_id 注入，不再需要手动调用 `getSiteParams()`
- [ ] 保留 `onSiteChange()` 功能（页面级别仍可能需要监听站点变更来重置 UI 状态）

### AC-7: 测试覆盖

- [ ] 拦截器单元测试：验证 site_id 注入、排除路径、手动指定不覆盖
- [ ] 事件总线测试：验证 on/emit/clear 功能
- [ ] switchSite 集成测试：验证切换后各 Store 重新加载
- [ ] "全部站点"测试：验证 null 时不注入
- [ ] 竞态条件测试：快速切换站点时旧请求不覆盖新数据（版本号模式）

---

## 技术设计

### 1. 请求拦截器修改

```typescript
// utils/request.ts - 请求拦截器

// 不需要站点过滤的 API 路径
const SITE_FILTER_EXCLUDED_PATHS = [
  '/v1/auth/',           // 认证
  '/v1/spatial/sites',   // 站点管理本身不过滤（实际路径，非 /v1/sites）
  '/v1/system/',         // 系统配置
  '/v1/users/',          // 用户管理
  '/v1/demo/',           // Demo 系统
  '/v1/configs/',        // 全局配置
  '/v1/logs/',           // 系统日志
]

function shouldInjectSiteId(url: string): boolean {
  return !SITE_FILTER_EXCLUDED_PATHS.some(
    path => url === path || url.startsWith(path.endsWith('/') ? path : path + '/')
  )
}

service.interceptors.request.use((config) => {
  // 现有 token 注入逻辑保持不变...

  // site_id 自动注入
  // 注意: 直接读 localStorage 而非 useSiteStore()，
  // 避免在 Pinia 未初始化时（app.use(pinia) 之前）调用导致崩溃
  const siteIdStr = localStorage.getItem('current_site_id')
  // siteStore.switchSite(null) 使用 removeItem 清除，所以 null 表示"全部站点"
  if (siteIdStr != null) {
    const siteId = Number(siteIdStr)
    if (!isNaN(siteId) && siteId > 0) {
      const url = config.url || ''
      if (shouldInjectSiteId(url)) {
        if (!config.params) config.params = {}
        // 手动指定优先，不覆盖
        if (config.params.site_id === undefined) {
          config.params.site_id = siteId
        }
      }
    }
  }

  return config
})
```

**设计决策说明:**
- 使用 `localStorage` 直接读取而非 `useSiteStore()` — 避免 Pinia 生命周期问题
- `siteIdStr != null` 检查（`removeItem` 后返回 null） — 与 site.ts 的 `removeItem` 行为一致
- 仅注入到 `config.params`（URL query string） — 后端 FastAPI 使用 `Query` 参数接收 `site_id`
- 精确路径匹配避免 `/v1/auth` 匹配到 `/v1/auth-something` 等误匹配
- `/v1/spatial/sites` 排除（实际 API 路径，非 `/v1/sites`）

### 2. 零依赖事件总线

```typescript
// utils/siteEvents.ts — 零依赖，不引入 mitt
type SiteChangeHandler = (siteId: number | null) => void

class SiteEventBus {
  private handlers = new Set<SiteChangeHandler>()

  on(handler: SiteChangeHandler) {
    this.handlers.add(handler)
    return () => this.handlers.delete(handler)
  }

  emit(siteId: number | null) {
    this.handlers.forEach(handler => {
      try {
        handler(siteId)
      } catch (e) {
        console.error('[SiteEventBus] handler error:', e)
      }
    })
  }

  /** 清除所有处理器（测试隔离用） */
  clear() {
    this.handlers.clear()
  }
}

export const siteEvents = new SiteEventBus()
```

### 3. 站点切换 + Store 重新加载

```typescript
// stores/site.ts — switchSite 方法
import { siteEvents } from '@/utils/siteEvents'

function switchSite(siteId: number | null) {
  currentSiteId.value = siteId
  if (siteId !== null) {
    localStorage.setItem('current_site_id', String(siteId))
  } else {
    localStorage.removeItem('current_site_id')  // 与现有行为一致
  }
  siteEvents.emit(siteId)
}
```

```typescript
// stores/alarm.ts — 版本号模式 + 具名函数订阅
export const useAlarmStore = defineStore('alarm', () => {
  let fetchVersion = 0  // 版本号，防竞态

  async function fetchActiveAlarms() {
    const version = ++fetchVersion
    loading.value = true
    try {
      const alarms = await getActiveAlarms()
      // 版本号检查：如果有更新的请求已发出，丢弃本次结果
      if (version !== fetchVersion) return
      activeAlarms.value = alarms as unknown as Alarm[]
      updateCount()
    } finally {
      if (version === fetchVersion) {
        loading.value = false
      }
    }
  }

  // 具名函数：HMR 重新执行 setup 时，Set.add 同一引用不会重复
  function handleSiteChange() {
    fetchActiveAlarms()
  }
  siteEvents.on(handleSiteChange)
})
```

**关键修改说明:**
- **版本号模式替代 AbortController** — API 函数 `getActiveAlarms()` 不接受 `signal` 参数，无法使用 AbortController。版本号模式在 await 返回后检查版本，丢弃过时响应。
- **移除 `if (loading.value) return` 防重入锁** — 站点切换必须允许重新发请求，否则正在进行的旧请求会阻塞新请求。版本号模式已防竞态。
- **具名函数 `handleSiteChange`** — HMR 重新执行 setup 时创建新函数引用，Set.add 会导致重复。但 Pinia defineStore 的 setup 函数在 HMR 时不会真正重复执行（Pinia 内部处理），实际风险低。

### 4. WebSocket 重连

```typescript
// composables/useWebSocketManager.ts

// 订阅记录：channel -> subscribe options
const subscriptions = new Map<WebSocketChannel, SubscribeOptions>()

// 包装 subscribe：记录订阅信息后调用 client.subscribe()
subscribe(channel, options) {
  subscriptions.set(channel, options)
  const client = clients.get(channel)
  if (client) {
    client.subscribe(options)  // 使用 WebSocketClient.subscribe()，内部发送 { action: 'subscribe', ...options }
  }
}

// 新增：断开所有连接并基于订阅记录重连
reconnectAll() {
  // 1. 关闭所有现有连接
  for (const [channel, client] of clients) {
    client.close()
  }
  clients.clear()

  // 2. 基于订阅记录重新连接
  for (const [channel, options] of subscriptions) {
    // connect() 内部创建新 WebSocketClient，onOpen 回调中重新 subscribe
    const client = new WebSocketClient({
      url: `/ws/${channel}`,
      heartbeatInterval: 30000,
      reconnectInterval: 3000,
      maxReconnectAttempts: 10,
      onOpen: () => {
        client.subscribe(options)
      }
    })
    client.connect()
    clients.set(channel, client)
  }
}
```

**设计决策说明:**
- 使用 `WebSocketClient.subscribe(options)` 而非 `client.send(JSON.stringify({ type: 'subscribe', ... }))` — WebSocketClient 内部使用 `action` 字段而非 `type`
- `onOpen` 回调在构造时传入，确保重连后自动重新订阅
- `clients.clear()` 在关闭后统一清理，避免逐个 delete

### 5. 限制说明

- **多标签页同步**: localStorage 变更不会自动同步到其他标签页的 Pinia state。已知限制，不在本 Story 范围内解决。
- **switchSite 同步执行**: `switchSite()` 内不 await 异步操作（emit 只是通知），各 Store 自行异步处理。

---

## 影响分析

### 修改文件

| 文件 | 修改内容 |
|------|---------|
| `frontend/src/utils/request.ts` | 添加 site_id 拦截器逻辑 |
| `frontend/src/utils/siteEvents.ts` | **新增** 零依赖事件总线 |
| `frontend/src/stores/site.ts` | switchSite 中发射事件 |
| `frontend/src/stores/alarm.ts` | 版本号模式 + setup 内订阅 site-changed |
| `frontend/src/stores/realtime.ts` | 版本号模式 + setup 内订阅 site-changed |
| `frontend/src/stores/energy.ts` | 版本号模式 + setup 内订阅 site-changed |
| `frontend/src/composables/useWebSocketManager.ts` | 添加 subscriptions 记录 + reconnectAll |
| `frontend/src/composables/useSiteFilter.ts` | 添加 @deprecated 注释 |

### 不修改的文件

- 各页面 View 文件 — 通过拦截器自动注入，不需要逐个页面修改
- 后端代码 — 已支持 site_id 参数
- API 模块文件 — 拦截器层面处理

### 风险及缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| Pinia 生命周期 | 拦截器在 Pinia 初始化前被调用 | 使用 localStorage 直接读取，不依赖 Pinia |
| HMR 重复订阅 | 热更新时事件处理器注册多次 | Pinia defineStore 内部处理 HMR，实际风险低 |
| 竞态条件 | 快速切站时旧响应覆盖新数据 | 版本号模式丢弃过时响应 |
| WebSocket 重连 | 断开后丢失订阅信息 | subscriptions Map 持久记录 |
| 排除路径误匹配 | `/v1/auth` 匹配到 `/v1/auth-something` | 精确前缀+斜杠匹配 |
| 多标签页不同步 | localStorage 与 Pinia 状态不一致 | 已知限制，文档记录 |

---

## 测试计划

### 单元测试 (request interceptor)

1. GET 请求自动注入 site_id 到 params
2. POST 请求自动注入 site_id 到 params（不注入到 body）
3. 排除路径不注入（/v1/auth/, /v1/spatial/sites, /v1/system/, /v1/users/, /v1/demo/, /v1/configs/, /v1/logs/）
4. 手动指定 site_id 不被覆盖
5. currentSiteId 为 null 时不注入（localStorage 无 key）
6. currentSiteId 为非数字字符串时不注入

### 事件总线测试

1. on() 注册处理器，emit() 触发
2. 返回的清理函数能移除处理器
3. clear() 清除所有处理器
4. 处理器异常不影响其他处理器

### 集成测试 (site switch)

1. switchSite(1) 后各 Store 重新加载
2. switchSite(null) 清除过滤，显示全部站点数据
3. 快速 switchSite(1) -> switchSite(2)，最终数据为站点 2（版本号模式丢弃旧响应）

### WebSocket 测试

1. subscribe() 记录订阅信息到 subscriptions Map
2. reconnectAll() 断开所有连接并重新连接
3. 重连后 onOpen 自动重新 subscribe
