# Story 27.4: 告警声音开关统一

Status: in-progress

## Story

As a 用户,
I want 在系统设置中关闭告警声音后全局生效,
So that 不会出现设置页关了声音但告警仍然播放声音的情况。

## 背景分析

当前系统存在告警声音配置的双重来源问题：
- **AppStore.alarmSoundEnabled** — 系统设置页面读写的配置，localStorage key: `alarm_sound`
- **AlarmStore.soundEnabled** — 告警播放逻辑读取的配置，localStorage key: `alarm_sound_enabled`

这导致用户在系统设置页面关闭声音后，告警仍然播放声音（因为 AlarmStore 读取的是不同的 localStorage key）。

### 根本原因

两个 Store 各自管理声音开关状态，没有统一的 SSOT (Single Source of Truth)。

### 解决方案（方案 D）

- **AppStore** 作为告警声音配置的唯一来源
- 移除 `AlarmStore.soundEnabled`
- `useAlarm` composable 改为读取 `appStore.alarmSoundEnabled`
- 统一 localStorage key 为 `alarm_sound`
- 一次性迁移旧 key `alarm_sound_enabled` → `alarm_sound`

## Acceptance Criteria (验收标准)

1. **AC-1: AlarmStore 移除 soundEnabled** — `AlarmStore` 中移除 `soundEnabled` ref 及其相关 getter/setter/toggle 方法。
   - **验证**: `stores/alarm.ts` 中不包含 `soundEnabled` 字段，不包含 `toggleSound` 方法。

2. **AC-2: AppStore 确认为唯一来源** — `AppStore.alarmSoundEnabled` 为告警声音配置的唯一来源，localStorage key 为 `alarm_sound`。`initFromStorage()` 方法负责从 localStorage 读取并初始化。
   - **验证**: `stores/app.ts` 中 `toggleAlarmSound()` 写入 `localStorage.setItem('alarm_sound', ...)`，`initFromStorage()` 读取 `localStorage.getItem('alarm_sound')`。

3. **AC-3: useAlarm 改读 AppStore** — `useAlarm` composable 的 `playAlarmSound()` 方法改为读取 `appStore.alarmSoundEnabled` 决定是否播放声音。
   - **验证**: `composables/useAlarm.ts` 中 `playAlarmSound()` 包含 `const appStore = useAppStore()` 和 `if (!appStore.alarmSoundEnabled) return` 守卫。

4. **AC-4: localStorage 迁移逻辑** — AppStore 初始化时执行一次性迁移：若 localStorage 中存在旧 key `alarm_sound_enabled`，将其值迁移到 `alarm_sound`，然后删除旧 key。
   - **验证**: `stores/app.ts` 的 Store 定义函数体开头包含迁移逻辑（检查 `alarm_sound_enabled` → 写入 `alarm_sound` → 删除旧 key）。

5. **AC-5: 系统设置页面一致性** — 系统设置页面的声音开关与实际播放行为完全一致（都读写 `appStore.alarmSoundEnabled`）。
   - **验证**: 在系统设置页面切换声音开关后，触发新告警时播放行为与开关状态一致。

6. **AC-6: 旧 key 清理** — 迁移后 localStorage 中不再存在 `alarm_sound_enabled` key。
   - **验证**: 浏览器 DevTools → Application → Local Storage 中不包含 `alarm_sound_enabled` key。

## Tasks / Subtasks (任务分解)

- [ ] Task 1: AlarmStore 清理 (AC: #1)
  - [ ] 1.1 移除 `soundEnabled` ref 定义（line 40）
  - [ ] 1.2 移除 `toggleSound()` 方法（line 92-95）
  - [ ] 1.3 移除 return 对象中的 `soundEnabled` 和 `toggleSound` 导出（line 100, 106）

- [ ] Task 2: AppStore 迁移逻辑 (AC: #2, #4)
  - [ ] 2.1 确认 `toggleAlarmSound()` 写入 `localStorage.setItem('alarm_sound', ...)`（已存在，line 82）
  - [ ] 2.2 在 `initFromStorage()` 方法的 `alarm_sound` 读取逻辑之前（line 152 之前）添加迁移逻辑：
    ```typescript
    // 一次性迁移：alarm_sound_enabled → alarm_sound
    const oldKey = 'alarm_sound_enabled'
    const newKey = 'alarm_sound'
    const oldValue = localStorage.getItem(oldKey)
    if (oldValue !== null && localStorage.getItem(newKey) === null) {
      localStorage.setItem(newKey, oldValue)
      localStorage.removeItem(oldKey)
    }
    ```

- [ ] Task 3: useAlarm 改读 AppStore (AC: #3)
  - [ ] 3.1 在 `useAlarm` 函数开头新增 `import { useAppStore } from '@/stores/app'`
  - [ ] 3.2 在 `useAlarm` 函数开头新增 `const appStore = useAppStore()`
  - [ ] 3.3 在 `handleNewAlarm()` 方法中将 `if (alarmStore.soundEnabled)` 改为 `if (appStore.alarmSoundEnabled)`

- [ ] Task 4: 构建与验证 (AC: #1-#6)
  - [ ] 4.1 `npm run build` 无编译错误
  - [ ] 4.2 相关单测通过
  - [ ] 4.3 验证系统设置页面（`/settings`）已正确使用 `appStore.alarmSoundEnabled`（如未使用则修复）
  - [ ] 4.4 手动测试：清空 localStorage → 刷新页面 → 检查 `alarmSoundEnabled` 默认值为 `true`
  - [ ] 4.5 手动测试：设置旧 key `localStorage.setItem('alarm_sound_enabled', 'false')` → 刷新页面 → 打开 DevTools Application → 检查 `alarm_sound=false` 且 `alarm_sound_enabled` 已删除
  - [ ] 4.6 手动测试：在系统设置页面切换声音开关 → 触发新告警（可通过 Demo 数据加载器触发 DI 点位告警）→ 验证播放行为与开关状态一致

## Dev Notes (开发指南)

### 涉及文件

| 文件 | 修改内容 |
|------|---------|
| `frontend/src/stores/alarm.ts` | 移除 `soundEnabled` ref 及相关方法 |
| `frontend/src/stores/app.ts` | 确认 `alarmSoundEnabled` 为唯一来源，添加迁移逻辑 |
| `frontend/src/composables/useAlarm.ts` | 改读 `appStore.alarmSoundEnabled` |

### localStorage Key 统一

| 旧 Key | 新 Key | 说明 |
|--------|--------|------|
| `alarm_sound_enabled` | `alarm_sound` | 迁移后删除旧 key |

### 迁移策略

迁移逻辑在 `AppStore.initFromStorage()` 方法中执行（在读取 `alarm_sound` 之前），确保：
1. 仅在新 key 不存在时才迁移（避免覆盖用户新设置）
2. 迁移后立即删除旧 key（避免混淆）
3. 迁移是幂等的（多次执行不会产生副作用）
4. `initFromStorage()` 需要在应用启动时调用（通常在 `MainLayout.vue` 或 `App.vue` 的 `onMounted` 中）

### 与其他 Story 的关系

| Story | 关系 |
|-------|------|
| 27.1 | AlarmStore 已统一为告警数据 SSOT，本 Story 统一声音配置 SSOT |
| 27.2 | 无直接依赖 |
| 27.3 | 无直接依赖 |

### 测试要点

1. **默认值测试** — 清空 localStorage 后，`alarmSoundEnabled` 应为默认值（通常为 `true`）
2. **迁移测试** — 设置旧 key 后刷新，验证迁移到新 key 且旧 key 被删除
3. **一致性测试** — 系统设置页面切换开关后，告警播放行为应立即生效
4. **幂等性测试** — 多次刷新页面，迁移逻辑不应产生副作用
