# Epic 27 前端数据链路统一 - 对抗性审查报告

**审查日期:** 2026-03-10
**审查人:** Claude (Adversarial Review Agent)
**审查范围:** Epic 27 的 6 个 Story 实施成果
**审查方法:** 对抗性代码审查（Cynical Review）

---

## 执行摘要

**审查结论:** ❌ **部分实施，存在 14 个问题（3 个 P0，4 个 P1，7 个 P2/P3）**

Epic 27 的核心架构（Store 作为 SSOT）已建立，但仍存在多处绕过 Store 的直接 API 调用和独立数据副本。最严重的问题是：

1. **温度监控页面仍直接调用 `getActiveAlarms` API**（P0-1 未完全解决）
2. **Dashboard 仍维护独立的能源数据副本**（P0-3 未完全解决）
3. **BigscreenStore 的 energy 和 environment 未改为 getter**（P0-3 未完全解决）

**建议:** 立即创建 Story 27.7 修复 P0 问题，然后进行回归测试。

---

## 审查发现（按严重程度排序）

### P0 级别问题（Critical - 必须立即修复）

#### P0-1: 告警数据仍存在绕过 Store 的直接 API 调用

**位置:** `frontend/src/views/environment/temperature.vue:310`

**问题描述:**
```typescript
const alarms = await getActiveAlarms({ point_id: sensor.point_id })
sensorAlarms.value = Array.isArray(alarms) ? alarms : []
```

温度监控页面在点击传感器时，直接调用 `getActiveAlarms` API 获取告警，完全绕过 AlarmStore。

**影响:**
- 温度监控页面显示的告警与全局告警状态不同步
- 用户在不同页面看到不同的告警数据
- 违反了 Story 27.1 的"单一事实来源"原则

**预期实现:**
```typescript
const alarmStore = useAlarmStore()
sensorAlarms.value = alarmStore.activeAlarms.filter(a => a.point_id === sensor.point_id)
```

**修复优先级:** P0 - 立即修复

---

#### P0-2: Dashboard 仍维护独立的能源数据副本

**位置:** `frontend/src/views/dashboard/index.vue:446`

**问题描述:**
```typescript
energyData.value = energyPayload
```

Dashboard 页面维护了独立的 `energyData` ref，并通过 `getEnergyDashboard()` API 获取数据，而非完全依赖 EnergyStore。

**影响:**
- Dashboard 的能源数据与能源管理页面可能不一致
- 存在复杂的回退逻辑（lines 447-475），数据流向不清晰
- 违反了 Story 27.3 的"能源数据 SSOT"原则

**预期实现:**
- 移除 `energyData` ref
- 完全从 `useEnergyStore()` 的 computed 属性读取
- 移除 `getEnergyDashboard()` 调用和回退逻辑

**修复优先级:** P0 - 立即修复

---

#### P0-3: BigscreenStore 的 energy 和 environment 仍是独立状态

**位置:** `frontend/src/stores/bigscreen.ts:44-51, 38-41`

**问题描述:**

`energy` 和 `environment` 仍然是 `state` 中的独立对象，而非从 EnergyStore 和 RealtimeStore 派生的 getter。

```typescript
// state 中的独立对象
energy: {
  totalPower: 0,
  itPower: 0,
  coolingPower: 0,
  pue: 1.5,
  todayEnergy: 0,
  todayCost: 0
}
```

**影响:**
- 大屏的能源数据与能源管理页面使用不同的数据源
- 大屏的环境统计与环境监控页面可能不一致
- 违反了 Story 27.3 的"能源数据统一"原则

**预期实现:**
```typescript
// 在 getters 中
energy(): { ... } {
  const energyStore = useEnergyStore()
  return {
    totalPower: energyStore.totalPower,
    itPower: energyStore.itPower,
    // ...
  }
}
```

**修复优先级:** P0 - 立即修复

---

### P1 级别问题（Major - 应尽快修复）

#### P1-4: Dashboard 的 sessionStorage 缓存机制与 Store 状态脱节

**位置:** `frontend/src/views/dashboard/index.vue` 的 `saveDashboardCache()` 和 `loadDashboardCache()`

**问题描述:**

Dashboard 仍然使用 `sessionStorage` 缓存机制（`dcim_dashboard_cache`），缓存的数据与 Store 状态完全独立。

**影响:**
- 页面刷新后优先显示缓存数据，而非 Store 中的最新数据
- 如果其他页面通过 WebSocket 更新了状态，Dashboard 仍显示旧缓存
- 违反了"单一事实来源"原则

**预期实现:**
- 移除 `saveDashboardCache()` 和 `loadDashboardCache()` 函数
- 移除 `dcim_dashboard_cache` 相关代码
- 完全依赖 Store 的持久化状态

**修复优先级:** P1 - 应尽快修复

---

#### P1-5: 环境监控 composables 仍创建独立的数据分组 Map

**位置:**
- `frontend/src/composables/useTemperatureData.ts:76`
- `frontend/src/composables/useWaterLeakData.ts:40`
- `frontend/src/composables/useSmokeInfraredData.ts:50`

**问题描述:**

```typescript
const map = new Map<string, RealtimeData[]>()
```

虽然数据源来自 RealtimeStore，但分组逻辑在每个 composable 中独立执行。

**影响:**
- 不同页面的分组结果可能不一致（如果分组逻辑有差异）
- 重复的分组计算逻辑，不利于维护

**预期实现:**
- 分组逻辑应该在 RealtimeStore 中统一实现
- composable 只负责调用 Store 的分组方法

**修复优先级:** P1 - 应尽快修复

---

#### P1-6: Dashboard 的 refreshData 逻辑过于复杂

**位置:** `frontend/src/views/dashboard/index.vue:403-486`

**问题描述:**

`refreshData()` 函数同时调用 4 个不同的 API，并且有复杂的回退逻辑。

**影响:**
- 数据流向不清晰，难以追踪数据来源
- 容易出现竞态条件
- 维护困难

**预期实现:**
- 应该只调用各 Store 的 `reload()` 方法
- 由 Store 负责数据获取
- 移除复杂的回退逻辑

**修复优先级:** P1 - 应尽快修复

---

#### P1-7: BigscreenStore 的 activeAlarms getter 进行了数据转换

**位置:** `frontend/src/stores/bigscreen.ts:109-121`

**问题描述:**

每次访问 `activeAlarms` getter 都会执行 `map()` 转换，如果告警数量多且访问频繁，会影响性能。

```typescript
activeAlarms(): BigscreenAlarm[] {
  const alarmStore = useAlarmStore()
  return alarmStore.activeAlarms.map(alarm => ({
    // 数据转换
  }))
}
```

**影响:**
- 大屏页面在告警数量多时可能出现卡顿
- 每次访问都重新计算，浪费性能

**预期实现:**
- 使用 `computed` 缓存转换结果
- 或者在 AlarmStore 中直接使用 BigscreenAlarm 类型

**修复优先级:** P1 - 应尽快修复

---

### P2 级别问题（Minor - 可延迟修复）

#### P2-8: WebSocket 管理器的 reconnectAll 逻辑可能导致消息丢失

**位置:** `frontend/src/composables/useWebSocketManager.ts:129-160`

**问题描述:**

`reconnectAll()` 先关闭所有连接再重连，在关闭和重连之间的时间窗口内，后端推送的消息会丢失。

**影响:**
- 站点切换时可能丢失告警或实时数据更新

**预期实现:**
- 先建立新连接，确认连接成功后再关闭旧连接（无缝切换）

**修复优先级:** P2 - 可延迟修复

---

#### P2-9: site_id 注入逻辑依赖 localStorage

**位置:** `frontend/src/utils/request.ts:46`

**问题描述:**

```typescript
const siteIdStr = localStorage.getItem('current_site_id')
```

直接读取 localStorage，而非从 `useSiteStore()` 读取。

**影响:**
- 如果 SiteStore 的状态与 localStorage 不同步，会导致 API 请求使用错误的 site_id

**预期实现:**
- 从 SiteStore 读取
- 或者确保 SiteStore 的 `switchSite()` 方法同步更新 localStorage

**修复优先级:** P2 - 可延迟修复

---

#### P2-10: AlarmStore 的 fetchVersion 竞态保护不完整

**位置:** `frontend/src/stores/alarm.ts:43-62`

**问题描述:**

虽然使用了版本号模式防竞态，但 `updateCount()` 在 `finally` 块外调用。

**影响:**
- 快速切换站点时，告警计数可能显示错误的值

**预期实现:**
- `updateCount()` 应该在版本号检查通过后才调用

**修复优先级:** P2 - 可延迟修复

---

#### P2-11: useRealtime composable 的轮询逻辑与 WebSocket 状态检查不一致

**位置:** `frontend/src/composables/useRealtime.ts:49`

**问题描述:**

轮询检查 `!wsManager.isConnected('realtime')` 来决定是否轮询，但 WebSocket 可能处于"已连接但未订阅"状态。

**影响:**
- WebSocket 连接正常但未订阅时，轮询会停止，导致数据不更新

**预期实现:**
- 应该检查订阅状态，而非仅检查连接状态

**修复优先级:** P2 - 可延迟修复

---

### P3 级别问题（Trivial - 可选修复）

#### P3-12: AppStore 的 localStorage 迁移逻辑是一次性的

**位置:** `frontend/src/stores/app.ts:137-144`

**问题描述:**

`alarm_sound_enabled → alarm_sound` 的迁移逻辑只在 `initFromStorage()` 时执行一次。

**影响:**
- 部分用户的告警声音开关可能失效

**预期实现:**
- 应该在每次读取时都检查并迁移
- 或者在后端统一处理

**修复优先级:** P3 - 可选修复

---

#### P3-13: RealtimeStore 的 updatePoint 使用原地修改 Map

**位置:** `frontend/src/stores/realtime.ts:85-91`

**问题描述:**

注释说"Vue 3 ref() 对 Map 做深度响应式代理，.set() 能触发依赖更新"，但这依赖于 Vue 3 的内部实现细节。

**影响:**
- 如果 Vue 3 的响应式实现变化，可能导致数据更新不触发视图刷新

**预期实现:**
- 使用 `dataMap.value = new Map(dataMap.value)` 的不可变更新模式

**修复优先级:** P3 - 可选修复

---

#### P3-14: 缺少对 Story 27.1-27.6 实施质量的验证测试

**问题描述:**

虽然 Story 27.1-27.6 标记为 done，但缺少系统性的验证测试来确保实施质量。

**影响:**
- 无法确保所有页面都已迁移到统一的 Store 架构
- 可能存在其他未发现的绕过 Store 的代码

**预期实现:**
- 创建自动化测试验证数据链路统一性
- 或者进行全面的手动回归测试

**修复优先级:** P3 - 可选修复

---

## 修复建议

### 立即行动（本周内）

1. **创建 Story 27.7: 数据链路 P0 问题修复**
   - 修复温度监控页面的告警数据绕过问题（P0-1）
   - 修复 Dashboard 的能源数据副本问题（P0-2）
   - 修复 BigscreenStore 的 energy 和 environment 问题（P0-3）
   - 移除 Dashboard 的 sessionStorage 缓存（P1-4）

2. **回归测试**
   - 验证所有页面的数据同步性
   - 验证 WebSocket 推送是否正常工作
   - 验证站点切换是否正常工作

### 短期改进（下个 Sprint）

3. **重构环境监控 composables**（P1-5）
   - 将分组逻辑移到 RealtimeStore
   - 统一分组算法

4. **简化 Dashboard 的 refreshData 逻辑**（P1-6）
   - 移除复杂的回退逻辑
   - 统一使用 Store 的 reload 方法

5. **优化 BigscreenStore 的 activeAlarms getter**（P1-7）
   - 使用 computed 缓存转换结果

### 长期优化（可选）

6. **改进 WebSocket 重连机制**（P2-8）
7. **统一 site_id 注入逻辑**（P2-9）
8. **完善竞态保护**（P2-10, P2-11）
9. **清理技术债务**（P3-12, P3-13）
10. **增加自动化测试**（P3-14）

---

## 审查方法论

本次审查采用对抗性代码审查（Adversarial Review）方法，以极度怀疑的态度审查代码，假设问题存在并主动寻找。

**审查步骤:**
1. 读取 Epic 27 的 6 个 Story 的验收标准
2. 读取关键文件的实际实现代码
3. 对比验收标准与实际实现，寻找差异
4. 使用 Grep 工具搜索可能绕过 Store 的代码模式
5. 分析数据流向，识别数据割裂点
6. 评估问题的严重程度和影响范围

**审查覆盖范围:**
- ✅ AlarmStore 和 useAlarm composable
- ✅ RealtimeStore 和 useRealtime composable
- ✅ EnergyStore
- ✅ AppStore
- ✅ BigscreenStore
- ✅ WebSocketManager
- ✅ Dashboard 页面
- ✅ 温度监控页面
- ✅ API 请求拦截器

---

## 附录：审查工具使用记录

**使用的工具:**
- Read: 读取关键文件
- Grep: 搜索代码模式
- Glob: 查找文件

**关键搜索模式:**
- `getActiveAlarms` - 查找直接 API 调用
- `ref<.*activeAlarms` - 查找局部告警状态
- `new Map.*RealtimeData` - 查找独立数据结构
- `useAlarmStore|useRealtimeStore|useEnergyStore` - 验证 Store 使用

---

**审查完成时间:** 2026-03-10 15:30
**下一步行动:** 创建 Story 27.7 并开始修复
