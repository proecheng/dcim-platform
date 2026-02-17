# Story 4.5: 优雅降级

Status: done

## Story

As a 运维工程师,
I want 系统在部分组件故障时仍能使用,
So that 我不会因为某个服务异常而完全无法查看监控数据。

## Acceptance Criteria (验收标准)

1. **AC-1: 系统健康状态 API** — 新增 `GET /api/v1/system/health` 端点，返回各组件状态：Redis（connected/disconnected）、WebSocket（active connections 数）、MQTT（connected/disconnected，基于配置判断）、Database（connected）
2. **AC-2: Redis 降级提示** — 后端实时数据 API 在 Redis 不可用降级到数据库查询时，在响应 header 中附加 `X-Degraded: true` 和 `X-Degraded-Message: realtime-data-delayed`（不修改响应 body 格式，避免破坏现有前端消费者）；前端 axios 拦截器检测到该 header 时更新 degradation store
3. **AC-3: WebSocket 指数退避重连** — 修改 `WebSocketClient` 的重连逻辑为指数退避（初始 1s，最大 30s，每次翻倍），重连期间前端显示"连接中断，正在重连..."提示条，重连成功后自动消失
4. **AC-4: 前端降级状态全局管理** — 新增 Pinia store `degradation`，管理三种降级状态（redis/websocket/mqtt），各监控页面通过该 store 显示对应的降级提示条
5. **AC-5: 降级提示组件** — 新增全局降级提示组件 `DegradationBanner.vue`，在 layout 中引入，根据 degradation store 的状态显示对应的警告条（黄色=延迟、橙色=重连中、红色=服务异常）
6. **AC-6: 后端测试** — 测试系统健康 API 和降级标志逻辑

## Tasks / Subtasks (任务分解)

- [ ] Task 1: 后端 — 系统健康状态 API (AC: #1)
  - [ ] 1.1 创建 `backend/app/api/v1/system_health.py`，新增 `GET /health` 端点
  - [ ] 1.2 检查 Redis 状态：`redis_service.is_available`
  - [ ] 1.3 检查数据库状态：执行简单查询 `SELECT 1`
  - [ ] 1.4 返回 `{ redis: { status, message }, database: { status }, websocket: { active_connections }, mqtt: { status, message } }`
  - [ ] 1.5 在 `backend/app/api/v1/__init__.py` 注册路由

- [ ] Task 2: 后端 — 实时数据 API 降级标志 (AC: #2)
  - [ ] 2.1 修改 `backend/app/api/v1/realtime.py` 的 `get_all_realtime` 和 `get_realtime_summary`
  - [ ] 2.2 当 Redis 不可用降级到数据库查询时，在 Response header 中设置 `X-Degraded: true` 和 `X-Degraded-Message: realtime-data-delayed`（使用 FastAPI Response 对象）
  - [ ] 2.3 正常情况下不设置该 header（或设置 `X-Degraded: false`）

- [ ] Task 3: 前端 — WebSocket 指数退避重连 (AC: #3)
  - [ ] 3.1 修改 `frontend/src/api/websocket.ts` 的 `scheduleReconnect` 方法
  - [ ] 3.2 实现指数退避：delay = min(initialDelay * 2^attempt, maxDelay)，initialDelay=1000ms，maxDelay=30000ms
  - [ ] 3.3 重连成功后重置 attempt 计数

- [ ] Task 4: 前端 — 降级状态 Pinia Store (AC: #4)
  - [ ] 4.1 创建 `frontend/src/stores/degradation.ts`
  - [ ] 4.2 状态：`redisDown: boolean`、`websocketDown: boolean`、`mqttDown: boolean`、`degradedMessage: string`
  - [ ] 4.3 Actions：`setRedisDown(down, message?)`、`setWebsocketDown(down)`、`setMqttDown(down)`
  - [ ] 4.4 Getter：`hasDegradation` — 任一组件降级时返回 true

- [ ] Task 5: 前端 — 降级提示组件 (AC: #5)
  - [ ] 5.1 创建 `frontend/src/components/common/DegradationBanner.vue`
  - [ ] 5.2 根据 degradation store 状态显示不同颜色的 el-alert：
    - Redis 降级：type=warning，"实时数据可能有延迟"
    - WebSocket 断开：type=warning，"连接中断，正在重连..."
    - MQTT 异常：type=error，"数据采集服务异常"
  - [ ] 5.3 在主布局文件中引入该组件（放在 main content 区域顶部）

- [ ] Task 6: 前端 — 集成降级检测 (AC: #2, #3, #4)
  - [ ] 6.1 在前端 axios 响应拦截器（`frontend/src/utils/request.ts`）中检测 `X-Degraded` header，更新 degradation store
  - [ ] 6.2 在 WebSocket onClose/onError 回调中更新 degradation store 的 websocketDown 状态
  - [ ] 6.3 在 WebSocket onOpen 回调中清除 websocketDown 状态

- [ ] Task 7: 后端测试 (AC: #6)
  - [ ] 7.1 测试系统健康 API — Redis 可用时返回 connected
  - [ ] 7.2 测试系统健康 API — Redis 不可用时返回 disconnected
  - [ ] 7.3 测试实时数据 API — Redis 降级时返回 degraded 标志

- [ ] Task 8: 前端构建验证
  - [ ] 8.1 `npm run build` 构建成功

## Dev Notes (开发指南)

### 1. 文件位置

```
backend/app/api/v1/system_health.py              # 新建 — 系统健康 API
backend/app/api/v1/__init__.py                    # 修改 — 注册路由
backend/app/api/v1/realtime.py                    # 修改 — 添加降级标志
backend/tests/test_graceful_degradation.py        # 新建 — 测试
frontend/src/api/websocket.ts                     # 修改 — 指数退避重连
frontend/src/stores/degradation.ts                # 新建 — 降级状态 store
frontend/src/components/common/DegradationBanner.vue  # 新建 — 降级提示组件
frontend/src/layouts/MainLayout.vue 或类似布局文件  # 修改 — 引入降级提示组件
```

### 2. 系统健康 API

```python
# backend/app/api/v1/system_health.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from ..deps import get_db, require_viewer
from ...models.user import User
from ...core.redis import redis_service
from ...core.config import get_settings

router = APIRouter()

@router.get("/health", summary="系统健康状态")
async def get_system_health(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    settings = get_settings()

    # Redis 状态
    redis_status = "disconnected"
    if redis_service and redis_service.is_available:
        try:
            await redis_service.set("health_check", "ok", ttl=5)
            redis_status = "connected"
        except Exception:
            redis_status = "disconnected"

    # 数据库状态
    db_status = "disconnected"
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    # WebSocket 活跃连接数
    from ...services.websocket import ws_manager
    ws_connections = len(ws_manager.active_connections) if hasattr(ws_manager, 'active_connections') else 0

    return {
        "redis": {"status": redis_status},
        "database": {"status": db_status},
        "websocket": {"active_connections": ws_connections},
        "mqtt": {"status": "not_configured" if not getattr(settings, 'mqtt_enabled', False) else "unknown"},
    }
```

### 3. 实时数据 API 降级标志

在 `realtime.py` 中使用 FastAPI Response header 传递降级状态（不修改响应 body）：

```python
from fastapi import Response

@router.get("", summary="获取所有点位实时数据")
async def get_all_realtime(
    response: Response,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    degraded = False
    # ... 现有 Redis 读取逻辑 ...
    # 如果进入了 except 或 Redis 不可用分支：
    degraded = True

    if degraded:
        response.headers["X-Degraded"] = "true"
        response.headers["X-Degraded-Message"] = "realtime-data-delayed"

    return data  # 返回格式不变
```

前端在 axios 拦截器中检测：

```typescript
// frontend/src/utils/request.ts 的响应拦截器中
import { useDegradationStore } from '@/stores/degradation'

service.interceptors.response.use((response) => {
  const degraded = response.headers['x-degraded']
  if (degraded === 'true') {
    const store = useDegradationStore()
    store.setRedisDown(true, '实时数据可能有延迟')
  } else if (degraded === 'false') {
    const store = useDegradationStore()
    store.setRedisDown(false)
  }
  return response.data
})
```

### 4. WebSocket 指数退避

修改 `frontend/src/api/websocket.ts` 的 `scheduleReconnect`：

```typescript
private scheduleReconnect(): void {
  if (this.reconnectAttempts >= this.maxReconnectAttempts) {
    console.error('WebSocket 重连次数已达上限')
    return
  }

  this.reconnectAttempts++
  // 指数退避：1s, 2s, 4s, 8s, 16s, 30s, 30s, ...
  const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts - 1), 30000)
  console.log(`WebSocket 将在 ${delay}ms 后重连 (${this.reconnectAttempts}/${this.maxReconnectAttempts})`)

  this.reconnectTimer = window.setTimeout(() => {
    this.connect()
  }, delay)
}
```

### 5. 降级状态 Store

```typescript
// frontend/src/stores/degradation.ts
import { defineStore } from 'pinia'

export const useDegradationStore = defineStore('degradation', {
  state: () => ({
    redisDown: false,
    websocketDown: false,
    mqttDown: false,
    degradedMessage: '',
  }),
  getters: {
    hasDegradation: (state) => state.redisDown || state.websocketDown || state.mqttDown,
  },
  actions: {
    setRedisDown(down: boolean, message?: string) {
      this.redisDown = down
      this.degradedMessage = message || ''
    },
    setWebsocketDown(down: boolean) {
      this.websocketDown = down
    },
    setMqttDown(down: boolean) {
      this.mqttDown = down
    },
  },
})
```

### 6. 降级提示组件

```vue
<!-- frontend/src/components/common/DegradationBanner.vue -->
<template>
  <div class="degradation-banners" v-if="store.hasDegradation">
    <el-alert
      v-if="store.redisDown"
      title="实时数据可能有延迟"
      type="warning"
      :closable="false"
      show-icon
    />
    <el-alert
      v-if="store.websocketDown"
      title="连接中断，正在重连..."
      type="warning"
      :closable="false"
      show-icon
    />
    <el-alert
      v-if="store.mqttDown"
      title="数据采集服务异常"
      type="error"
      :closable="false"
      show-icon
    />
  </div>
</template>
```

### 7. 布局集成

找到主布局文件（通常是 `layouts/MainLayout.vue` 或 `layouts/default.vue`），在 main content 区域顶部引入 `DegradationBanner`。

### 8. 关键约束

- **不破坏现有 API 契约**: 使用 Response header（X-Degraded）传递降级状态，不修改响应 body 格式
- **CORS header 暴露**: 如果有 CORS 中间件，需要在 `expose_headers` 中添加 `X-Degraded` 和 `X-Degraded-Message`
- **指数退避**: 初始 1s，最大 30s，公式 `min(1000 * 2^(attempt-1), 30000)`
- **降级自动恢复**: Redis 恢复后下次 API 调用自动返回 degraded=false，WebSocket 重连成功后自动清除提示
- **自动导入**: Vue API 和 Pinia API 无需手动 import
- **测试模式**: 使用 in-memory SQLite + mock Redis

### References

- [Source: api/v1/realtime.py] 实时数据 API（已有 Redis 降级逻辑）
- [Source: api/websocket.ts] WebSocket 客户端（已有重连逻辑）
- [Source: composables/useWebSocket.ts] WebSocket 组合式函数
- [Source: composables/useRealtime.ts] 实时数据组合式函数
- [Source: core/redis.py] Redis 服务（is_available 属性）
- [Source: services/websocket.py] WebSocket 管理器

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

