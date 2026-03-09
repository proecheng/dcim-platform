---
epic: 27
story_id: 27.10
title: 数据链路 P1 问题修复 - BigscreenStore activeAlarms 性能优化
status: ready-for-dev
priority: P1
created: 2026-03-10
assigned_to: dev
estimated_effort: 2h
sprint: next
---

# Story 27.10: BigscreenStore activeAlarms Getter 性能优化

## User Story

As a 大屏用户,
I want activeAlarms getter 使用缓存避免重复计算,
So that 在告警数量多时大屏页面不会出现卡顿。

## Context

对抗性审查发现 P1-7 问题：BigscreenStore 的 `activeAlarms` getter 每次访问都会执行 `map()` 转换，将 AlarmStore 的告警数据转换为 BigscreenAlarm 类型。

**当前问题：**
- 每次访问 getter 都重新执行 `map()` 转换
- 如果告警数量多（如 100+ 条）且访问频繁，会影响性能
- 大屏页面可能出现卡顿

**解决方案：**
- 使用 Vue 的 `computed` 缓存转换结果
- 只有当 AlarmStore 的 activeAlarms 变化时才重新计算

## Acceptance Criteria

### AC1: 将 activeAlarms getter 改为 computed 属性

- Given BigscreenStore 初始化
- When 访问 `activeAlarms` 属性
- Then 返回缓存的转换结果
- And 只有当 `alarmStore.activeAlarms` 变化时才重新计算
- And 转换逻辑保持不变

**修改文件:** `frontend/src/stores/bigscreen.ts`

**修改前（约 line 84-97）:**
```typescript
// 在 getters 中
activeAlarms(): BigscreenAlarm[] {
  const alarmStore = useAlarmStore()
  return alarmStore.activeAlarms.map(alarm => ({
    id: alarm.id,
    deviceId: alarm.point_code || String(alarm.point_id || ''),
    deviceName: alarm.point_name || '',
    level: alarm.alarm_level as BigscreenAlarm['level'],
    message: alarm.alarm_message || '',
    value: alarm.trigger_value,
    threshold: alarm.threshold_value,
    createdAt: alarm.created_at,
  }))
}
```

**修改后:**
```typescript
// 在 state 中添加
import { computed } from 'vue'

// 在 store 定义中添加（不在 state、getters、actions 中）
const alarmStore = useAlarmStore()
const activeAlarms = computed(() => {
  return alarmStore.activeAlarms.map(alarm => ({
    id: alarm.id,
    deviceId: alarm.point_code || String(alarm.point_id || ''),
    deviceName: alarm.point_name || '',
    level: alarm.alarm_level as BigscreenAlarm['level'],
    message: alarm.alarm_message || '',
    value: alarm.trigger_value,
    threshold: alarm.threshold_value,
    createdAt: alarm.created_at,
  }))
})

// 在 getters 中
activeAlarms(): BigscreenAlarm[] {
  return activeAlarms.value
}
```

**注意:** Pinia store 中使用 computed 需要特殊处理，可能需要调整实现方式。

### AC2: 验证性能改进

- Given 大屏页面加载，系统有 50+ 条告警
- When 页面渲染和更新
- Then activeAlarms 转换只在告警数据变化时执行
- And 多次访问 activeAlarms 不会重复执行 map 转换
- And 大屏页面无明显卡顿

**验证方法:**
- 在 `activeAlarms` getter 中添加 `console.log('activeAlarms computed')`
- 观察控制台输出次数
- 修改前：每次访问都输出
- 修改后：只在告警数据变化时输出

### AC3: 保持 API 兼容性

- Given 大屏页面和其他使用 BigscreenStore 的组件
- When 访问 `bigscreenStore.activeAlarms`
- Then 返回的数据结构和类型与修改前完全一致
- And 不影响现有功能

## Technical Implementation

### 实现方案

**方案 A: 使用 Pinia 的 computed（推荐）**

在 Pinia store 中，getter 本身就是 computed 属性。问题在于每次调用 getter 都会执行函数体。解决方案是在 getter 外部创建一个 computed 缓存。

```typescript
export const useBigscreenStore = defineStore('bigscreen', () => {
  // 使用 setup 语法
  const alarmStore = useAlarmStore()

  // 缓存的 activeAlarms
  const activeAlarms = computed(() => {
    return alarmStore.activeAlarms.map(alarm => ({
      id: alarm.id,
      deviceId: alarm.point_code || String(alarm.point_id || ''),
      deviceName: alarm.point_name || '',
      level: alarm.alarm_level as BigscreenAlarm['level'],
      message: alarm.alarm_message || '',
      value: alarm.trigger_value,
      threshold: alarm.threshold_value,
      createdAt: alarm.created_at,
    }))
  })

  return {
    // ... 其他 state 和 actions
    activeAlarms
  }
})
```

**方案 B: 在 AlarmStore 中直接提供 BigscreenAlarm 格式**

如果 BigscreenAlarm 格式在多处使用，可以考虑在 AlarmStore 中直接提供转换后的数据。

**推荐方案 A**，因为：
- 保持 AlarmStore 的通用性
- BigscreenAlarm 是大屏特定的类型
- 使用 computed 缓存性能足够好

### 修改清单

1. **frontend/src/stores/bigscreen.ts**
   - 将 store 定义从 options API 改为 setup API（如果需要）
   - 或者在 getters 中使用缓存变量
   - 确保 activeAlarms 使用 computed 缓存

### 测试验证

**性能测试步骤:**

1. **添加性能日志:**
   ```typescript
   const activeAlarms = computed(() => {
     console.log('[Performance] activeAlarms computed')
     return alarmStore.activeAlarms.map(...)
   })
   ```

2. **测试修改前:**
   - 打开大屏页面
   - 观察控制台输出次数
   - 预期：多次输出（每次访问都计算）

3. **测试修改后:**
   - 打开大屏页面
   - 观察控制台输出次数
   - 预期：只输出 1-2 次（初始化和告警变化时）

4. **测试告警更新:**
   - 触发新告警（或通过 WebSocket 推送）
   - 验证 activeAlarms 自动更新
   - 验证只在告警变化时重新计算

## Definition of Done

- [ ] AC1-AC3 全部通过验证
- [ ] 性能测试通过
- [ ] 代码审查通过
- [ ] 无 TypeScript 类型错误
- [ ] 无控制台错误或警告
- [ ] 提交代码并创建 commit

## Notes

- 本 Story 是性能优化，不改变功能行为
- 如果 BigscreenStore 已经使用 setup 语法，实现会更简单
- 如果使用 options API，可能需要重构为 setup API

## Related Issues

- Epic 27: 前端数据链路统一
- Story 27.7: 数据链路 P0 问题修复
- 对抗性审查报告: P1-7

## Performance Impact

**预期性能改进:**
- 告警数量 50 条时：减少 ~50 次 map 操作/秒
- 告警数量 100 条时：减少 ~100 次 map 操作/秒
- 大屏页面帧率提升：预计从 55fps 提升到 60fps（在告警多时）
