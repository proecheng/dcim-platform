# DCIM 前端数据链路审查报告

**日期:** 2026-03-05
**审查范围:** frontend/src/stores/, composables/, api/modules/, views/
**审查目的:** 识别数据不同步和割裂问题，制定统一数据流规范

---

## 一、现状架构概览

当前前端数据流存在三层并行数据管理：

```
┌─────────────────────────────────────────────────────┐
│                     Views / Components               │
│  (部分直接调API，部分用composable，部分用store)        │
├─────────────┬─────────────────────┬──────────────────┤
│  Composables │    Pinia Stores     │   Direct API     │
│  (自带状态)   │  (全局状态)          │  (局部ref)       │
├─────────────┴─────────────────────┴──────────────────┤
│                   API Modules                        │
│             (axios → backend REST)                   │
├──────────────────────────────────────────────────────┤
│               WebSocket Channels                     │
│    realtime / alarms / system / linkage              │
└──────────────────────────────────────────────────────┘
```

**问题核心:** 同一数据实体在多个层级被独立维护，缺乏单一事实来源 (Single Source of Truth)。

---

## 二、已识别的数据割裂问题

### P0-1: 告警数据三源割裂 (Critical)

**数据实体:** 活动告警列表 + 告警计数

**割裂现状:**

| 数据源 | 位置 | 状态变量 | 数据来源 |
|--------|------|----------|----------|
| AlarmStore | `stores/alarm.ts` | `activeAlarms`, `alarmCount` | WebSocket push (via useAlarm) |
| useAlarm composable | `composables/useAlarm.ts` | 自有 `activeAlarms` ref, `alarmCount` ref | REST `getActiveAlarms()` + WebSocket |
| BigscreenStore | `stores/bigscreen.ts` | `activeAlarms` (BigscreenAlarm[]) | REST `getActiveAlarms()` (via useBigscreenData) |
| Dashboard View | `views/dashboard/index.vue` | 局部 `activeAlarms` ref | REST `getActiveAlarms()` 直接调用 |

**割裂后果:**
- `useAlarm` composable 维护的 `activeAlarms` 与 `AlarmStore.activeAlarms` 是**独立副本**
- composable 在 WebSocket 消息处理中部分同步到 store（`alarmStore.updateAlarm()`），但 `addAlarm` 动作不同步
- 大屏的告警列表使用不同的类型 `BigscreenAlarm`（字段 `level` vs `alarm_level`），从不同 API 获取
- Dashboard 页面完全独立获取告警，不消费 store 也不用 composable
- **用户在不同页面看到不同的告警计数**

**影响页面:** 仪表盘、告警列表页、大屏、Header告警铃铛

---

### P0-2: 实时点位数据双源割裂 (Critical)

**数据实体:** 实时点位值 (point_id → value)

**割裂现状:**

| 数据源 | 位置 | 状态变量 | 数据来源 |
|--------|------|----------|----------|
| RealtimeStore | `stores/realtime.ts` | `dataMap: Map<number, RealtimeData>` | 未被任何composable写入 |
| useRealtime composable | `composables/useRealtime.ts` | 自有 `realtimeData: Map<number, RealtimeData>` | REST + WebSocket |
| useBigscreenData | `composables/bigscreen/useBigscreenData.ts` | 写入 BigscreenStore | REST `getAllRealtimeData()` |

**割裂后果:**
- `useRealtimeStore` 定义了完整的 API（`updatePoint`, `setAllData`, `getPointData`），但 `useRealtime` composable **完全不使用它**，而是维护自己的 Map
- 每个使用 `useRealtime()` 的组件创建独立的数据副本和 WebSocket 连接
- `RealtimeStore` 实质上是**死代码**——有定义无消费者写入
- 大屏使用独立路径获取相同数据并写入 BigscreenStore

**影响页面:** 环境监控、设备详情、仪表盘实时统计、大屏

---

### P0-3: 能源/PUE 数据双源割裂 (Critical)

**数据实体:** PUE 值、总功率、IT 功率、冷却功率、今日用电量

**割裂现状:**

| 数据源 | 位置 | 状态变量 | API 端点 |
|--------|------|----------|----------|
| EnergyStore | `stores/energy.ts` | `pueData`, `powerSummary`, `realtimePowerData` | `getCurrentPUE()`, `getPowerSummary()` |
| BigscreenStore | `stores/bigscreen.ts` | `energy.pue`, `energy.totalPower`, `energy.itPower` 等 | `getEnergyDashboard()` |

**割裂后果:**
- EnergyStore 的 PUE 来自 `/api/v1/energy/pue/current`
- BigscreenStore 的 PUE 来自 `/api/v1/energy/dashboard` 的 `efficiency.pue` 字段
- 两个端点可能返回**不同的时间点的 PUE 值**（一个是最新实时值，一个是仪表盘汇总值）
- 能源页面和大屏显示的 PUE 可能不一致

**影响页面:** 能源监控页、大屏左右面板

---

### P1-4: 告警声音开关双源冲突 (Major)

**数据实体:** 告警声音启用/禁用

| 数据源 | 位置 | 变量 | localStorage Key |
|--------|------|------|-----------------|
| AppStore | `stores/app.ts` | `alarmSoundEnabled` | `alarm_sound` |
| AlarmStore | `stores/alarm.ts` | `soundEnabled` | `alarm_sound_enabled` |

**割裂后果:**
- 两个 store 使用**不同的 localStorage key** 持久化同一个配置
- `useAlarm` composable 读取 `alarmStore.soundEnabled` 来决定是否播放声音
- AppStore 的 `alarmSoundEnabled` 可能被设置页面修改，但不影响实际播放逻辑
- 用户在"系统设置"页面关闭告警声音，但声音可能仍然播放（因为实际读的是另一个store）

---

### P1-5: WebSocket 多连接浪费 (Major)

**问题:** 每个 `useAlarm()` 或 `useRealtime()` composable 实例都创建独立的 WebSocket 连接

```
MainLayout (useAlarm) ──── ws://host/ws/alarms  ← 连接1
AlarmPage  (useAlarm) ──── ws://host/ws/alarms  ← 连接2
Dashboard  (useAlarm) ──── ws://host/ws/alarms  ← 连接3（如果使用的话）

MainLayout (useRealtime) ── ws://host/ws/realtime ← 连接1
EnvironmentPage (useRealtime) ── ws://host/ws/realtime ← 连接2
```

**后果:**
- 同一通道多个并行 WebSocket 连接，浪费服务器资源
- 同一条消息被多次处理，多次写入不同的状态副本
- 连接/断开生命周期绑定到组件，页面切换时频繁重连

---

### P1-6: 站点过滤未贯穿数据链路 (Major)

**问题:** `useSiteStore` 维护了 `currentSiteId`，但：
- `useAlarm` composable 的 `fetchActiveAlarms()` 不传 `site_id` 参数
- `useRealtime` composable 的 `fetchRealtimeData()` 不传 `site_id` 参数
- `useEnergy` composable 的 `loadRealtimePower()` 不传 `site_id` 参数
- API 模块层面支持 `site_id` 参数，但调用方未使用

**后果:** 多站点部署时，切换站点不会过滤数据，所有页面显示全站数据。

---

### P2-7: 环境监控页面绕过 Store 直接调 API (Minor)

**位置:** `views/environment/temperature.vue:310`

```typescript
const alarms = await getActiveAlarms({ point_id: sensor.point_id })
```

温度监控页面直接调用 `getActiveAlarms` API 而非使用 `useAlarm` composable 或 AlarmStore，获取的告警数据与全局告警状态完全独立。

---

### P2-8: Dashboard 缓存机制与 Store 不一致 (Minor)

**位置:** `views/dashboard/index.vue`

Dashboard 实现了自己的 sessionStorage 缓存机制（`dcim_dashboard_cache`），缓存了 `activeAlarms` 等数据。页面切换后优先显示缓存数据，而非 Store 中的最新数据。如果其他页面通过 WebSocket 更新了告警状态，Dashboard 仍显示旧缓存。

---

## 三、数据链路规范方案

### 3.1 核心原则：单向数据流 + 单一事实来源

```
                    ┌──────────────┐
                    │   Backend    │
                    │  REST + WS   │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  API Module  │  ← 唯一的后端通信层
                    │  (无状态)     │
                    └──────┬───────┘
                           │
              ┌────────────▼────────────┐
              │      Pinia Store        │ ← 单一事实来源
              │  (全局状态 + WebSocket)  │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │      Composable         │ ← 无状态工具层
              │  (格式化 + 业务逻辑)     │  （读 Store，不持有数据）
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │   View / Component      │ ← 纯展示
              └─────────────────────────┘
```

### 3.2 具体整改方案

#### 方案 A: 告警数据链路统一

**目标状态:**

```
Backend WS(alarms) ──► AlarmStore (单一事实来源)
                          │
                          ├── useAlarm composable (无状态，格式化/声音/通知)
                          │     └── 读取 alarmStore.activeAlarms
                          │     └── 写入 alarmStore.addAlarm / updateAlarm
                          │
                          ├── Dashboard 页面 → 直接读 alarmStore
                          ├── 告警列表页 → 直接读 alarmStore
                          └── BigscreenStore.activeAlarms → 从 alarmStore 派生
```

**具体修改:**

1. **AlarmStore** 增加 `fetchActiveAlarms()` action，内部调 API 并更新自身状态
2. **useAlarm composable** 移除自有 `activeAlarms` 和 `alarmCount` ref，改为读取 `alarmStore.activeAlarms` 和 `alarmStore.alarmCount`
3. **WebSocket 连接** 移到 AlarmStore 层级，由 store 的 `init()` action 建立唯一连接
4. **BigscreenStore** 移除 `activeAlarms` 状态，改用 getter 从 `useAlarmStore()` 派生
5. **Dashboard** 移除局部 `activeAlarms` ref，改用 `alarmStore.activeAlarms`

#### 方案 B: 实时数据链路统一

**目标状态:**

```
Backend WS(realtime) ──► RealtimeStore (单一事实来源)
                              │
                              ├── useRealtime composable (无状态工具)
                              │     └── 读取 realtimeStore.dataMap
                              │     └── 提供 getPointData / getDataByType
                              │
                              └── BigscreenStore.deviceData → 从 realtimeStore 派生
```

**具体修改:**

1. **RealtimeStore** 增加 `initWebSocket()` action，建立唯一 WS 连接，收到消息调用 `updatePoint()`
2. **useRealtime composable** 移除自有 `realtimeData` Map，改为代理 `realtimeStore` 的方法
3. **useBigscreenData** 的 `fetchEnvironmentData()` 从 RealtimeStore 读数据而非独立调 API

#### 方案 C: 能源数据链路统一

**目标状态:**

```
Backend REST ──► EnergyStore (单一事实来源)
                     │
                     ├── useEnergy composable (无状态工具)
                     └── BigscreenStore.energy → 从 energyStore 派生 getter
```

**具体修改:**

1. **BigscreenStore** 的 `energy` 对象改为 getter，读取 `useEnergyStore()` 的 computed 属性
2. **useBigscreenData** 的 `fetchEnergyData()` 调用 `useEnergy.loadAllData()` 而非独立调 API
3. 统一 API 端点：大屏和能源页使用相同的数据源

#### 方案 D: 告警声音开关统一

**修改:**
1. 移除 `AlarmStore.soundEnabled`，统一使用 `AppStore.alarmSoundEnabled`
2. `useAlarm` composable 改读 `appStore.alarmSoundEnabled`
3. 统一 localStorage key 为 `alarm_sound`

#### 方案 E: WebSocket 单连接管理

**修改:**
1. 创建 `composables/useWebSocketManager.ts` 单例管理器
2. 所有 Store 的 `initWebSocket()` 通过管理器获取共享连接
3. 管理器负责重连、心跳，Store 只注册消息处理器

#### 方案 F: 站点过滤贯穿

**修改:**
1. 在 API 模块层增加拦截器，自动注入 `site_id` 参数（从 `useSiteStore().currentSiteId` 读取）
2. 或在 axios 请求拦截器中统一添加
3. `siteStore.switchSite()` 触发相关 Store 的 `reload()` 操作

---

## 四、数据实体 → Store 归属映射表

| 数据实体 | 唯一归属 Store | 禁止持有的位置 |
|----------|---------------|---------------|
| 活动告警列表 | AlarmStore | BigscreenStore, useAlarm ref, Dashboard ref |
| 告警计数 | AlarmStore (getter) | useAlarm ref, 各页面局部 ref |
| 实时点位值 | RealtimeStore | useRealtime ref, BigscreenStore.deviceData |
| 实时汇总 | RealtimeStore | useRealtime ref |
| PUE 值 | EnergyStore | BigscreenStore.energy.pue |
| 功率数据 | EnergyStore | BigscreenStore.energy.totalPower 等 |
| 节能建议 | EnergyStore | 无冲突 |
| 节能机会 | OpportunityStore | 无冲突 |
| 设备降级状态 | DegradationStore | 无冲突（degradationFlags 是合理的 pre-Pinia 桥接） |
| 用户信息/权限 | UserStore | 无冲突 |
| 应用设置 | AppStore | AlarmStore.soundEnabled |
| 当前站点 | SiteStore | 无冲突 |
| 大屏场景/布局 | BigscreenStore | 无冲突（仅大屏专属UI状态） |

---

## 五、实施优先级

| 优先级 | 方案 | 涉及文件 | 风险 |
|--------|------|---------|------|
| **P0** | A: 告警统一 | alarm.ts, useAlarm.ts, bigscreen.ts, dashboard/index.vue | 中 — 影响多页面 |
| **P0** | B: 实时数据统一 | realtime.ts, useRealtime.ts, useBigscreenData.ts | 中 — WebSocket 重构 |
| **P1** | C: 能源统一 | energy.ts, bigscreen.ts, useBigscreenData.ts | 低 |
| **P1** | D: 声音开关 | alarm.ts, app.ts, useAlarm.ts | 低 |
| **P1** | E: WebSocket 单例 | 新建 useWebSocketManager.ts | 中 — 全局影响 |
| **P2** | F: 站点过滤 | api/request.ts 拦截器, 各 store | 低 |

---

## 六、与 Epics 的关系

当前 epics.md 中以下 Story 直接涉及数据链路，实施时**必须遵循本规范**：

| Story | 涉及数据链路 | 注意事项 |
|-------|-------------|---------|
| 4.1: 数据切换框架 | 实时数据 WebSocket + REST 双通道 | 必须写入 RealtimeStore，不得新建 ref |
| 5.1-5.5: 告警管理 | 告警全链路 | 必须基于 AlarmStore 单一来源 |
| 22.2: 站点切换器 | site_id 过滤 | 必须实现方案 F |
| 24.6-24.8: 诊断结果展示 | 新数据实体(诊断结果) | 必须新建 DiagnosisStore，不得在 composable 中持有状态 |
| 18.1-18.3: 环境监测 | 实时温湿度数据 | 从 RealtimeStore 读取，不独立调 API |

---

*本报告由数据链路审查生成，建议在 Sprint Planning 前由架构师确认方案并作为实施约束写入故事验收标准。*
