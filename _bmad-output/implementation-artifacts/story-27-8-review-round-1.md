# Story 27.8 第一轮对抗性审查报告

**审查日期:** 2026-03-10
**审查人:** Claude (Adversarial Review)
**审查方法:** 对比 Story 假设与实际代码实现

---

## 审查结论

❌ **Story 存在 4 个严重问题，必须修改后才能实施**

---

## 发现的问题

### P0-1: 分组逻辑与实际代码不匹配

**问题描述:**
- Story 假设使用 `point_code.split('_')[0]` 提取区域（如 `A1_TH_001` → `A1`）
- 实际代码使用 `d.area_code || '未分区'`
- 这是完全不同的分组逻辑！

**证据:**
```typescript
// useTemperatureData.ts:78
const area = d.area_code || '未分区'

// useWaterLeakData.ts:42
const area = d.area_code || '未分区'

// useSmokeInfraredData.ts:52
const area = d.area_code || '未分区'
```

**影响:**
- 如果按 Story 实施，会破坏现有功能
- `area_code` 是数据库字段，而非从 point_code 解析

**修复方案:**
- Story 应该使用实际的 `area_code` 字段
- AC1 中的示例代码需要修改为 `const area = data.area_code || 'Unknown'`

---

### P0-2: 设备类型不一致

**问题描述:**
- Story AC3 使用 `groupByArea('WL')`
- 实际代码使用 `device_type === 'WATER'`

**证据:**
```typescript
// useWaterLeakData.ts:30
const wlSensors = computed(() =>
  Array.from(allData.value.values()).filter(d => d.device_type === 'WATER')
)
```

**影响:**
- AC3 的实现会导致无法找到漏水传感器

**修复方案:**
- AC3 应该使用 `groupByArea('WATER')`

---

### P1-3: AC4 的过滤逻辑不合理

**问题描述:**
- AC4 要求先调用 `groupByArea()` 获取所有数据，然后在 composable 中过滤
- 这意味着先分组所有设备类型，然后再过滤，效率低下

**证据:**
```typescript
// useSmokeInfraredData.ts:36
const siSensors = computed(() =>
  Array.from(allData.value.values()).filter(d => d.device_type === 'SMOKE' || d.device_type === 'IR')
)
```

**影响:**
- 性能浪费：分组了不需要的数据
- 逻辑不清晰

**修复方案:**
- `groupByArea` 应该支持数组参数：`groupByArea(['SMOKE', 'IR'])`
- 或者在 composable 中先过滤再分组

---

### P1-4: 缺少对现有 ZoneGroup 结构的考虑

**问题描述:**
- useTemperatureData 返回的是 `ZoneGroup[]`，包含复杂的统计信息
- Story 只提到返回 `Map<string, RealtimeData[]>`
- 这会破坏现有的 API

**证据:**
```typescript
// useTemperatureData.ts:12-24
export interface ZoneGroup {
  areaCode: string
  sensors: RealtimeData[]
  tempSensors: RealtimeData[]
  humiditySensors: RealtimeData[]
  avgTemp: number | null
  avgHumidity: number | null
  minTemp: number | null
  maxTemp: number | null
  alarmCount: number
  hasDrift: boolean
  hasAlarm: boolean
}
```

**影响:**
- 温度监控页面依赖 ZoneGroup 的统计字段
- 简单替换会导致页面报错

**修复方案:**
- `groupByArea` 只负责基础分组，返回 `Map<string, RealtimeData[]>`
- composable 保留统计计算逻辑，基于分组结果计算 ZoneGroup
- Story 需要明确说明这一点

---

## 修改建议

### AC1 修改

**修改前:**
```typescript
const area = data.point_code.split('_')[0] || 'Unknown'
```

**修改后:**
```typescript
const area = data.area_code || 'Unknown'
```

### AC2 保持不变

`groupByArea('TH')` 是正确的

### AC3 修改

**修改前:**
```typescript
const map = realtimeStore.groupByArea('WL')
```

**修改后:**
```typescript
const map = realtimeStore.groupByArea('WATER')
```

### AC4 修改

**修改前:**
```typescript
const map = realtimeStore.groupByArea()
// 在 composable 中过滤 device_type === 'SM' || device_type === 'IR'
```

**修改后:**
```typescript
const map = realtimeStore.groupByArea(['SMOKE', 'IR'])
```

**或者:**
```typescript
// 先过滤再分组
const filtered = siSensors.value // 已经过滤了 SMOKE 和 IR
const map = new Map<string, RealtimeData[]>()
filtered.forEach(d => {
  const area = d.area_code || '未分区'
  if (!map.has(area)) map.set(area, [])
  map.get(area)!.push(d)
})
```

### 新增说明

在 Technical Implementation 中添加：

**重要说明:**
- `groupByArea` 只负责基础分组，返回 `Map<string, RealtimeData[]>`
- composables 保留现有的统计计算逻辑（avgTemp、alarmCount 等）
- composables 的返回类型（ZoneGroup、WaterLeakZoneGroup、SmokeIRZoneGroup）保持不变
- 只是将重复的分组逻辑提取到 Store，统计逻辑仍在 composable 中

---

## 审查总结

Story 27.8 的核心思路是正确的（统一分组逻辑），但实施细节与实际代码不匹配。必须修改后才能实施，否则会破坏现有功能。

**必须修改的内容:**
1. AC1: 使用 `area_code` 而非 `point_code.split('_')[0]`
2. AC3: 使用 `'WATER'` 而非 `'WL'`
3. AC4: 支持数组参数或先过滤再分组
4. 添加说明：composables 保留统计逻辑

---

**审查完成时间:** 2026-03-10
**下一步:** 修改 Story 后进行第二轮审查
