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
- When 调用 `groupByArea(deviceType?: string)` 方法
- Then 返回按区域分组的数据 `Map<string, RealtimeData[]>`
- And 如果指定 deviceType，只返回该类型的数据
- And 分组逻辑统一：按 `point_code` 的前缀提取区域（如 `A1_TH_001` → `A1`）

**实现位置:** `frontend/src/stores/realtime.ts`

**新增方法:**
```typescript
// 在 RealtimeStore 的 getters 中添加
groupByArea(): (deviceType?: string) => Map<string, RealtimeData[]> {
  return (deviceType?: string) => {
    const map = new Map<string, RealtimeData[]>()
    const filtered = deviceType
      ? Array.from(this.dataMap.values()).filter(d => d.device_type === deviceType)
      : Array.from(this.dataMap.values())

    for (const data of filtered) {
      // 提取区域：A1_TH_001 → A1
      const area = data.point_code.split('_')[0] || 'Unknown'
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
- When 调用 `groupedData` computed
- Then 从 `realtimeStore.groupByArea('TH')` 获取分组数据
- And 移除本地的 `new Map<string, RealtimeData[]>()` 创建逻辑

**修改文件:** `frontend/src/composables/useTemperatureData.ts`

**修改前（约 line 76）:**
```typescript
const map = new Map<string, RealtimeData[]>()
for (const data of thData) {
  const area = data.point_code.split('_')[0] || 'Unknown'
  if (!map.has(area)) {
    map.set(area, [])
  }
  map.get(area)!.push(data)
}
```

**修改后:**
```typescript
const map = realtimeStore.groupByArea('TH')
```

### AC3: useWaterLeakData 使用 Store 分组方法

- Given useWaterLeakData composable 初始化
- When 调用 `groupedData` computed
- Then 从 `realtimeStore.groupByArea('WL')` 获取分组数据
- And 移除本地的分组逻辑

**修改文件:** `frontend/src/composables/useWaterLeakData.ts`

### AC4: useSmokeInfraredData 使用 Store 分组方法

- Given useSmokeInfraredData composable 初始化
- When 调用 `groupedData` computed
- Then 从 `realtimeStore.groupByArea()` 获取所有数据的分组
- And 在 composable 中过滤 `device_type === 'SM' || device_type === 'IR'`
- And 移除本地的分组逻辑

**修改文件:** `frontend/src/composables/useSmokeInfraredData.ts`

## Technical Implementation

### 修改清单

1. **frontend/src/stores/realtime.ts**
   - 在 `getters` 中添加 `groupByArea` 方法
   - 支持可选的 `deviceType` 参数过滤

2. **frontend/src/composables/useTemperatureData.ts**
   - 修改 `groupedData` computed，调用 `realtimeStore.groupByArea('TH')`
   - 移除本地 Map 创建逻辑

3. **frontend/src/composables/useWaterLeakData.ts**
   - 修改 `groupedData` computed，调用 `realtimeStore.groupByArea('WL')`
   - 移除本地 Map 创建逻辑

4. **frontend/src/composables/useSmokeInfraredData.ts**
   - 修改 `groupedData` computed，调用 `realtimeStore.groupByArea()`
   - 在 composable 中过滤烟感和红外类型
   - 移除本地 Map 创建逻辑

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
