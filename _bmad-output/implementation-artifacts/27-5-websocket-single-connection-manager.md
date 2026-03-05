# Story 27.5: WebSocket 单连接管理器

Status: in-progress

## Story

As a 开发者,
I want 每个 WebSocket 通道只维持一个共享连接,
So that 页面切换时不会频繁创建/销毁连接，减少服务器资源浪费。

## 背景分析

当前系统存在 WebSocket 连接管理的分散问题：
- **AlarmStore** — 在 `useAlarm` composable 中创建独立的 `/ws/alarms` 连接
- **RealtimeStore** — 在 `useRealtime` composable 中创建独立的 `/ws/realtime` 连接
- **其他潜在通道** — `/ws/system`, `/ws/linkage` 等

这导致：
1. **连接浪费** — 同一通道在多个组件中被重复创建
2. **生命周期混乱** — 连接绑定到组件，页面切换时频繁断开/重连
3. **重连逻辑重复** — 每个 composable 都实现自己的重连和心跳逻辑
4. **状态不一致** — 多个连接可能收到不同步的消息

### 现有基础设施

`api/websocket.ts` 中的 `WebSocketClient` 类已实现：
- 自动重连（指数退避，最大 10 次）
- 心跳检测（默认 30 秒）
- 消息分发（`on(type, handler)` 注册处理器）
- 订阅机制（`subscribe({ channels, filters })`）
- 降级状态集成

### 解决方案（方案 E）

创建 `useWebSocketManager.ts` 单例管理器，**复用 `WebSocketClient`**：
- **每个通道最多 1 个 WebSocketClient 实例** — 通过通道名（realtime/alarms/system/linkage）管理连接池
- **连接生命周期绑定到应用** — 在 MainLayout 初始化，不随组件卸载而断开
- **复用 WebSocketClient 的重连和心跳** — 管理器只负责池化管理，不重新实现 WS 逻辑
- **代理 API** — 管理器暴露 `on`, `off`, `subscribe`, `send` 等方法，内部委托给对应通道的 WebSocketClient

## Acceptance Criteria (验收标准)

1. **AC-1: WebSocketManager 单例创建** — 新建 `composables/useWebSocketManager.ts`，在模块级别创建单例实例，导出 `useWebSocketManager()` 函数返回该实例。
   - **验证**: 文件存在，模块级别有 `const manager = { ... }` 单例对象，`useWebSocketManager()` 返回该对象。

2. **AC-2: 连接池管理** — 管理器维护 `Map<channel, WebSocketClient>` 连接池，确保每个通道最多 1 个 WebSocketClient 实例。
   - **验证**: `connect(channel)` 方法检查连接池，已存在则复用，不存在则创建新 `WebSocketClient` 实例。

3. **AC-3: 复用 WebSocketClient 功能** — 管理器不重新实现重连/心跳逻辑，直接使用 `WebSocketClient` 的内置功能（指数退避重连、30 秒心跳）。
   - **验证**: 管理器代码中创建 `new WebSocketClient({ url: `/ws/${channel}`, ... })`，不包含自定义重连或心跳逻辑。

4. **AC-4: 代理 API** — 管理器暴露 `on(channel, type, handler)`, `off(channel, type, handler)`, `subscribe(channel, options)`, `send(channel, data)` 方法，内部委托给对应通道的 WebSocketClient。
   - **验证**: 管理器方法体中调用 `clients.get(channel)?.on(type, handler)` 等。

5. **AC-5: AlarmStore 迁移** — `useAlarm` composable 改用 `useWebSocketManager().on('alarms', 'alarm', handler)`，移除自有 `useWebSocket()` 创建逻辑。
   - **验证**: `useAlarm.ts` 中不包含 `useWebSocket()` 调用，改为 `useWebSocketManager().on('alarms', 'alarm', ...)`。

6. **AC-6: RealtimeStore 迁移** — `useRealtime` composable 改用 `useWebSocketManager().on('realtime', 'realtime_data', handler)`，移除自有 `useWebSocket()` 创建逻辑。
   - **验证**: `useRealtime.ts` 中不包含 `useWebSocket()` 调用，改为 `useWebSocketManager().on('realtime', 'realtime_data', ...)`。

7. **AC-7: MainLayout 初始化** — 在 `MainLayout.vue` 的 `onMounted` 中预连接常用通道（`alarms`, `realtime`），确保连接生命周期绑定到 MainLayout（用户登录后才创建连接）。
   - **验证**: `MainLayout.vue` 包含 `wsManager.connect('alarms')` 和 `wsManager.connect('realtime')` 调用。
   - **注意**: MainLayout 卸载（如退出登录）时，连接会自动断开（WebSocketClient 的 onUnmounted 逻辑）。

8. **AC-8: 连接数验证** — 在浏览器 DevTools Network/WS 面板中验证每个通道仅 1 个连接。
   - **验证**: 打开多个页面（Dashboard, 告警列表, 环境监控），DevTools 中 `/ws/alarms` 和 `/ws/realtime` 各只有 1 个连接。

## Tasks / Subtasks (任务分解)

- [ ] Task 1: 创建 WebSocketManager (AC: #1, #2, #3, #4)
  - [ ] 1.1 新建 `frontend/src/composables/useWebSocketManager.ts`
  - [ ] 1.2 在模块级别定义单例对象：
    ```typescript
    const clients = new Map<string, WebSocketClient>()
    const manager = {
      connect(channel: string) { ... },
      disconnect(channel: string) { ... },
      on(channel: string, type: string, handler: Function) { ... },
      off(channel: string, type: string, handler: Function) { ... },
      subscribe(channel: string, options: any) { ... },
      send(channel: string, data: any) { ... }
    }
    export function useWebSocketManager() { return manager }
    ```
  - [ ] 1.3 实现 `connect(channel: string)` 方法：
    - 检查 `clients.has(channel)` 且 `client.ws?.readyState === WebSocket.OPEN`，已连接则直接返回
    - 不存在或已断开则创建 `new WebSocketClient({ url: `/ws/${channel}` })`
    - 调用 `client.connect()` 并存入 `clients` Map
  - [ ] 1.4 实现 `disconnect(channel: string)` 方法：获取 client 并调用 `client.close()`，从 Map 移除
  - [ ] 1.5 实现 `on(channel, type, handler)` 方法：获取 client 并调用 `client.on(type, handler)`
  - [ ] 1.6 实现 `off(channel, type, handler)` 方法：获取 client 并调用 `client.off(type, handler)`
  - [ ] 1.7 实现 `subscribe(channel, options)` 方法：获取 client 并调用 `client.subscribe(options)`
  - [ ] 1.8 实现 `send(channel, data)` 方法：获取 client 并调用 `client.send(data)`

- [ ] Task 2: AlarmStore 迁移 (AC: #5)
  - [ ] 2.1 在 `useAlarm.ts` 顶部新增 `import { useWebSocketManager } from './useWebSocketManager'`
  - [ ] 2.2 移除 `useWebSocket()` 调用及相关变量（`isConnected`, `subscribe`, `on`, `off`, `connect`, `disconnect`）
  - [ ] 2.3 在 `useAlarm` 函数开头新增 `const wsManager = useWebSocketManager()`
  - [ ] 2.4 将 `subscribeAlarms()` 改为：
    ```typescript
    wsManager.on('alarms', 'alarm', handleAlarmMessage)
    wsManager.subscribe('alarms', { channels: ['alarms'] })
    ```
  - [ ] 2.5 移除 `onMounted` 中的 `subscribeAlarms()` 调用（MainLayout 已预连接，composable 只需注册处理器）
  - [ ] 2.6 将 `onUnmounted` 中的 `disconnect()` 改为 `wsManager.off('alarms', 'alarm', handleAlarmMessage)`
  - [ ] 2.7 移除 `isConnected` 相关逻辑（管理器内部处理连接状态）

- [ ] Task 3: RealtimeStore 迁移 (AC: #6)
  - [ ] 3.1 在 `useRealtime.ts` 顶部新增 `import { useWebSocketManager } from './useWebSocketManager'`
  - [ ] 3.2 移除 `useWebSocket()` 调用及相关变量
  - [ ] 3.3 在 `useRealtime` 函数开头新增 `const wsManager = useWebSocketManager()`
  - [ ] 3.4 将 `subscribeRealtime()` 改为：
    ```typescript
    wsManager.on('realtime', 'realtime_data', handleRealtimeMessage)
    wsManager.subscribe('realtime', { channels: ['realtime'] })
    ```
  - [ ] 3.5 移除 `onMounted` 中的 `subscribeRealtime()` 调用（MainLayout 已预连接，composable 只需注册处理器）
  - [ ] 3.6 将 `onUnmounted` 中的 `disconnect()` 改为 `wsManager.off('realtime', 'realtime_data', handleRealtimeMessage)`
  - [ ] 3.7 移除 `isConnected` 相关逻辑和轮询守卫（管理器保证连接可用）

- [ ] Task 4: MainLayout 初始化 (AC: #7)
  - [ ] 4.1 在 `MainLayout.vue` 顶部新增 `import { useWebSocketManager } from '@/composables/useWebSocketManager'`
  - [ ] 4.2 在 `onMounted` 中新增：
    ```typescript
    const wsManager = useWebSocketManager()
    wsManager.connect('alarms')
    wsManager.connect('realtime')
    ```

- [ ] Task 5: 构建与验证 (AC: #1-#8)
  - [ ] 5.1 `npm run build` 无编译错误
  - [ ] 5.2 相关单测通过
  - [ ] 5.3 手动测试：打开 Dashboard → 打开告警列表 → 打开环境监控 → DevTools Network/WS 面板验证每个通道仅 1 个连接
  - [ ] 5.4 手动测试：关闭浏览器标签页 → 重新打开 → 验证连接自动重连
  - [ ] 5.5 手动测试：后端重启 → 验证前端自动重连（指数退避）
  - [ ] 5.6 手动测试：使用 Demo 数据加载器触发 DI 点位告警 → 验证告警声音和通知正常

## Dev Notes (开发指南)

### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                      MainLayout.vue                          │
│  onMounted: wsManager.connect('alarms', 'realtime')         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│         useWebSocketManager (Module-level Singleton)         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ clients: Map<channel, WebSocketClient>              │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │ connect(channel) → 创建/复用 WebSocketClient         │   │
│  │ on(channel, type, handler) → client.on(...)         │   │
│  │ off(channel, type, handler) → client.off(...)       │   │
│  │ subscribe(channel, options) → client.subscribe(...) │   │
│  │ send(channel, data) → client.send(...)              │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
         │                                    │
         ▼                                    ▼
┌──────────────────────┐          ┌──────────────────────┐
│   useAlarm           │          │   useRealtime        │
│  on('alarms', ...)   │          │  on('realtime', ...) │
└──────────────────────┘          └──────────────────────┘
```

### 重连策略

由 `WebSocketClient` 内置实现：
- **指数退避**: 初始 3 秒，每次失败翻倍，最大 10 次尝试
- **重连触发**: `onclose` 事件（非主动关闭）
- **重连取消**: 连接成功或主动调用 `close()`

### 心跳机制

由 `WebSocketClient` 内置实现：
- **间隔**: 30 秒（可配置）
- **格式**: `{ type: 'ping', timestamp: Date.now() }`
- **启动时机**: `onopen` 事件
- **停止时机**: `onclose` 事件或主动 `close()`

### 消息分发

`WebSocketClient` 收到消息后，根据 `message.type` 调用对应的处理器（通过 `on(type, handler)` 注册）。管理器只负责将 `on/off` 调用委托给正确的 client 实例。

### 与其他 Story 的关系

| Story | 关系 |
|-------|------|
| 27.1 | AlarmStore 已统一告警数据，本 Story 统一 WS 连接管理 |
| 27.2 | RealtimeStore 已统一实时数据，本 Story 统一 WS 连接管理 |
| 27.3 | EnergyStore 当前无 WS 推送，未来可扩展 |
| 27.4 | 无直接依赖 |

### 涉及文件

| 文件 | 修改内容 |
|------|---------|
| `frontend/src/composables/useWebSocketManager.ts` | 新建，单例管理器 |
| `frontend/src/composables/useAlarm.ts` | 移除 `useWebSocket()`，改用管理器 |
| `frontend/src/composables/useRealtime.ts` | 移除 `useWebSocket()`，改用管理器 |
| `frontend/src/layouts/MainLayout.vue` | 初始化管理器，预连接通道 |

### 测试要点

1. **单例验证** — 多次调用 `useWebSocketManager()` 返回同一实例
2. **连接复用** — 同一通道多次 `connect()` 不创建新连接
3. **重连验证** — 模拟断开，验证指数退避重连
4. **心跳验证** — 连接成功后，30 秒发送一次 ping
5. **消息分发** — 一个通道多个处理器，消息到达时全部被调用
6. **取消订阅** — `unsubscribe()` 后，处理器不再收到消息
