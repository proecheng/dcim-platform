---
epic: 27
story_id: 27.8
title: 数据链路 P1 问题修复 - 环境监控分组统一
status: ready-for-dev
priority: P1
created: 2026-03-10
assigned_to: dev
estimated_effort: 6h
sprint: next
---

# Story 27.8: 环境监控分组逻辑统一到 RealtimeStore

## User Story

As a 开发者,
I want 环境监控的数据分组逻辑统一在 RealtimeStore 中实现,
So that 不同页面使用相同的分组算法，避免重复代码和潜在的不一致。

## Context

对抗性审查发现 P1-5 问题：环境监控的 3 个 composables（useTemperatureData、useWaterLeakData、useSmokeInfraredData）都在各自内部创建独立的 `Map<string, RealtimeData[]>` 进行数据分组。

**当前问题：**
- 分组逻辑重复实现 3 次
- 如果分组算法需要调整，需要修改 3 个文件
- 不同 composable 的分组逻辑可能不一致

**解决方案：**
- 在 RealtimeStore 中添加统一的分组方法
- composables 只负责调用 Store 的分组方法并过滤特定类型

## Acceptance Criteria

### AC1: RealtimeStore 添加通用分组方法

- Given RealtimeStore 已加载实时数据
- When 调用 `groupByArea(deviceType?: string | string[])` 方法
- Then 返回按区域分组的数据 `Map<string, RealtimeData[]>`
- And 如果指定 deviceType（字符串或数组），只返回该类型的数据
- And 分组逻辑统一：按 `area_code` 字段分组，未分区的归为 `'Unknown'`

**实现位置:** `frontend/src/stores/realtime.ts`

**新增方法:**
```typescript
// 在 RealtimeStore 的 getters 中添加
groupByArea(): (deviceType?: string | string[]) => Map<string, RealtimeData[]> {
  return (deviceType?: string | string[]) => {
    const map = new Map<string, RealtimeData[]>()

    // 过滤设备类型
    let filtered = Array.from(this.dataMap.values())
    if (deviceType) {
      const types = Array.isArray(deviceType) ? deviceType : [deviceType]
      filtered = filtered.filter(d => types.includes(d.device_type))
    }

    // 按 area_code 分组
    for (const data of filtered) {
      const area = data.area_code || '未分区'
      if (!map.has(area)) {
        map.set(area, [])
      }
      map.get(area)!.push(data)
    }
    return map
  }
}
```

### AC2: useTemperatureData 使用 Store 分组方法

- Given useTemperatureData composable 初始化
- When 调用 `zoneGroups` computed
- Then 从 `realtimeStore.groupByArea('TH')` 获取基础分组数据
- And 基于分组结果计算统计信息（avgTemp、minTemp、maxTemp、alarmCount 等）
- And 返回类型 `ZoneGroup[]` 保持不变
- And 移除本地的 `new Map<string, RealtimeData[]>()` 创建逻辑

**修改文件:** `frontend/src/composables/useTemperatureData.ts`

**修改前（约 line 76-81）:**
```typescript
const map = new Map<string, RealtimeData[]>()
thSensors.value.forEach(d => {
  const area = d.area_code || '未分区'
  if (!map.has(area)) map.set(area, [])
  map.get(area)!.push(d)
})
```

**修改后:**
```typescript
// 使用 Store 的统一分组方法
const map = realtimeStore.groupByArea('TH')
```

**重要说明:**
- `groupByArea` 只负责基础分组，返回 `Map<string, RealtimeData[]>`
- composable 保留现有的统计计算逻辑（lines 83-106）
- 返回类型 `ZoneGroup[]` 保持不变，不影响页面使用

### AC3: useWaterLeakData 使用 Store 分组方法

- Given useWaterLeakData composable 初始化
- When 调用 `zoneGroups` computed
- Then 从 `realtimeStore.groupByArea('WATER')` 获取基础分组数据
- And 基于分组结果计算统计信息（normalCount、alarmCount、offlineCount 等）
- And 返回类型 `WaterLeakZoneGroup[]` 保持不变
- And 移除本地的分组逻辑

**修改文件:** `frontend/src/composables/useWaterLeakData.ts`

**修改前（约 line 40-45）:**
```typescript
const map = new Map<string, RealtimeData[]>()
wlSensors.value.forEach(d => {
  const area = d.area_code || '未分区'
  if (!map.has(area)) map.set(area, [])
  map.get(area)!.push(d)
})
```

**修改后:**
```typescript
// 使用 Store 的统一分组方法（注意：设备类型是 'WATER' 而非 'WL'）
const map = realtimeStore.groupByArea('WATER')
```

### AC4: useSmokeInfraredData 使用 Store 分组方法

- Given useSmokeInfraredData composable 初始化
- When 调用 `zoneGroups` computed
- Then 从 `realtimeStore.groupByArea(['SMOKE', 'IR'])` 获取基础分组数据（支持多个设备类型）
- And 基于分组结果计算统计信息（smokeCount、irCount、alarmCount 等）
- And 返回类型 `SmokeIRZoneGroup[]` 保持不变
- And 移除本地的分组逻辑

**修改文件:** `frontend/src/composables/useSmokeInfraredData.ts`

**修改前（约 line 50-55）:**
```typescript
const map = new Map<string, RealtimeData[]>()
siSensors.value.forEach(d => {
  const area = d.area_code || '未分区'
  if (!map.has(area)) map.set(area, [])
  map.get(area)!.push(d)
})
```

**修改后:**
```typescript
// 使用 Store 的统一分组方法（支持多个设备类型）
const map = realtimeStore.groupByArea(['SMOKE', 'IR'])
```

## Technical Implementation

### 关键设计决策

**分组逻辑统一，统计逻辑保留:**
- `groupByArea` 只负责基础分组，返回 `Map<string, RealtimeData[]>`
- composables 保留现有的统计计算逻辑（avgTemp、alarmCount、hasDrift 等）
- composables 的返回类型（ZoneGroup、WaterLeakZoneGroup、SmokeIRZoneGroup）保持不变
- 这样既统一了分组逻辑，又不破坏现有 API

**设备类型参数支持:**
- 支持单个类型：`groupByArea('TH')`
- 支持多个类型：`groupByArea(['SMOKE', 'IR'])`
- 支持所有类型：`groupByArea()` 或 `groupByArea(undefined)`

**分组字段:**
- 使用 `area_code` 字段（数据库字段）
- 未分区的数据归为 `'Unknown'`
- 不使用 `point_code.split('_')[0]` 解析（避免假设命名规则）

### 修改清单

1. **frontend/src/stores/realtime.ts**
   - 在 `getters` 中添加 `groupByArea` 方法
   - 支持 `string | string[]` 类型参数
   - 按 `area_code` 分组

2. **frontend/src/composables/useTemperatureData.ts**
   - 修改 `zoneGroups` computed（line 75-107）
   - 将 line 76-81 的分组逻辑替换为 `realtimeStore.groupByArea('TH')`
   - 保留 line 83-106 的统计计算逻辑

3. **frontend/src/composables/useWaterLeakData.ts**
   - 修改 `zoneGroups` computed（line 39-65）
   - 将 line 40-45 的分组逻辑替换为 `realtimeStore.groupByArea('WATER')`
   - 保留 line 47-64 的统计计算逻辑

4. **frontend/src/composables/useSmokeInfraredData.ts**
   - 修改 `zoneGroups` computed（line 49-81）
   - 将 line 50-55 的分组逻辑替换为 `realtimeStore.groupByArea(['SMOKE', 'IR'])`
   - 保留 line 57-80 的统计计算逻辑

### 测试验证

**手动测试步骤:**

1. **验证温度监控分组:**
   - 打开"环境监控 > 温度监控"
   - 检查传感器是否按区域正确分组
   - 验证每个区域的传感器数量正确

2. **验证漏水监控分组:**
   - 打开"环境监控 > 漏水监控"
   - 检查漏水传感器是否按区域正确分组

3. **验证烟感红外分组:**
   - 打开"环境监控 > 烟感红外"
   - 检查烟感和红外传感器是否按区域正确分组

4. **验证数据一致性:**
   - 在不同环境监控页面之间切换
   - 验证相同区域的数据在不同页面显示一致

5. **验证分组逻辑统一:**
   - 在浏览器控制台执行：
     ```javascript
     const store = useRealtimeStore()
     const map = store.groupByArea('TH')
     console.log('分组结果:', Array.from(map.keys()))
     ```
   - 验证分组键是 `area_code` 的值
   - 验证未分区的数据归为 '未分区'
   - 验证多设备类型分组：`store.groupByArea(['SMOKE', 'IR'])`

## Definition of Done

- [ ] AC1-AC4 全部通过验证
- [ ] 手动测试步骤全部通过
- [ ] 代码审查通过
- [ ] 无 TypeScript 类型错误
- [ ] 无控制台错误或警告
- [ ] 提交代码并创建 commit

## Notes

- 本 Story 是对 Epic 27 的持续改进，属于代码重构
- 修改后应进行回归测试，确保环境监控功能正常
- 分组逻辑统一后，未来如需调整只需修改 RealtimeStore 一处

## Related Issues

- Epic 27: 前端数据链路统一
- Story 27.7: 数据链路 P0 问题修复
- 对抗性审查报告: P1-5
