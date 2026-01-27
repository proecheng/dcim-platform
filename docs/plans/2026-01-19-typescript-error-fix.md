# TypeScript 错误修复实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复前端项目中的所有 TypeScript 类型错误，确保 `vue-tsc --noEmit` 通过

**Architecture:** 分类处理错误：1)类型定义文件缺失 2)API响应数据提取错误 3)Element Plus类型问题 4)ECharts类型问题

**Tech Stack:** Vue 3, TypeScript 5.9, Element Plus, ECharts 5

---

## 错误分类汇总

| 类别 | 错误数 | 涉及文件 |
|------|--------|----------|
| Vite 环境类型缺失 | 1 | request.ts |
| API 响应数据提取 | 19 | useEnergy.ts, config.vue, monitor.vue, topology.vue |
| Element Plus Tag 类型 | 15 | StatusTag.vue, alarm/index.vue, device/index.vue, 多个energy页面, settings/index.vue |
| ECharts 类型 | 6 | PieChart.vue, history/index.vue, monitor.vue, suggestions.vue |
| 其他类型错误 | 5 | ExportButton.vue, settings/index.vue, suggestions.vue |

---

## Task 1: 添加 Vite 环境类型定义

**Files:**
- Create: `frontend/src/vite-env.d.ts`

**Step 1: 创建 vite-env.d.ts 文件**

```typescript
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  // 更多环境变量...
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
```

**Step 2: 验证修复**

Run: `npx vue-tsc --noEmit 2>&1 | grep "request.ts" || echo "Fixed"`
Expected: "Fixed"

**Step 3: Commit**

```bash
git add frontend/src/vite-env.d.ts
git commit -m "fix: add Vite environment type definitions"
```

---

## Task 2: 修复 useEnergy.ts API 响应数据提取

**Files:**
- Modify: `frontend/src/composables/useEnergy.ts`

**问题分析:**
响应拦截器返回 `response.data`，因此 API 函数返回的已经是数据本身，不需要再访问 `.data.code` 或 `.data.data`。

**Step 1: 修复所有 API 调用的数据提取**

将所有形如:
```typescript
const res = await getXxx()
if (res.data.code === 0) {
  // use res.data.data
}
```

修改为:
```typescript
const res = await getXxx()
// 直接使用 res，因为拦截器已返回 response.data
energyStore.setXxx(res as XxxType)
```

**Step 2: 完整修复代码**

修改 `loadRealtimePower` 函数 (约第45-48行):
```typescript
async function loadRealtimePower(params?: { device_type?: string; area_code?: string }) {
  try {
    loading.value = true
    error.value = null
    const res = await getRealtimePower(params)
    energyStore.setAllPowerData(res as RealtimePowerData[])
  } catch (e: any) {
    error.value = e.message || '加载实时电力数据失败'
    console.error('加载实时电力数据失败:', e)
  } finally {
    loading.value = false
  }
}
```

修改 `loadPowerSummary` 函数 (约第60-63行):
```typescript
async function loadPowerSummary() {
  try {
    const res = await getPowerSummary()
    energyStore.setPowerSummary(res as RealtimePowerSummary)
  } catch (e: any) {
    console.error('加载电力汇总失败:', e)
  }
}
```

修改 `loadPUE` 函数 (约第72-75行):
```typescript
async function loadPUE() {
  try {
    const res = await getCurrentPUE()
    energyStore.setPUEData(res as PUEData)
  } catch (e: any) {
    console.error('加载PUE数据失败:', e)
  }
}
```

修改 `loadPUETrend` 函数 (约第88-91行):
```typescript
async function loadPUETrend(params?: {
  period?: 'hour' | 'day' | 'week' | 'month'
  start_time?: string
  end_time?: string
}): Promise<PUETrend | null> {
  try {
    const res = await getPUETrend(params)
    return res as PUETrend
  } catch (e: any) {
    console.error('加载PUE趋势失败:', e)
  }
  return null
}
```

修改 `loadEnergySummary` 函数 (约第108-109行):
```typescript
async function loadEnergySummary(params: { ... }): Promise<EnergyStat | null> {
  try {
    const res = await getEnergySummary(params)
    return res as EnergyStat
  } catch (e: any) {
    console.error('加载能耗汇总失败:', e)
  }
  return null
}
```

修改 `loadEnergyTrend` 函数 (约第127-128行):
```typescript
async function loadEnergyTrend(params: { ... }): Promise<EnergyTrend | null> {
  try {
    const res = await getEnergyTrend(params)
    return res as EnergyTrend
  } catch (e: any) {
    console.error('加载能耗趋势失败:', e)
  }
  return null
}
```

修改 `loadEnergyComparison` 函数 (约第144-145行):
```typescript
async function loadEnergyComparison(params: { ... }): Promise<EnergyComparison | null> {
  try {
    const res = await getEnergyComparison(params)
    return res as EnergyComparison
  } catch (e: any) {
    console.error('加载能耗对比失败:', e)
  }
  return null
}
```

修改 `loadSuggestions` 函数 (约第162-163行):
```typescript
async function loadSuggestions(params?: { ... }) {
  try {
    const res = await getSuggestions(params)
    energyStore.setSuggestions(res as EnergySuggestion[])
  } catch (e: any) {
    console.error('加载节能建议失败:', e)
  }
}
```

修改 `handleAcceptSuggestion`, `handleRejectSuggestion`, `handleCompleteSuggestion` 函数:
```typescript
async function handleAcceptSuggestion(id: number) {
  try {
    await acceptSuggestion(id)
    // 刷新列表
    await loadSuggestions()
    return true
  } catch (e: any) {
    console.error('接受建议失败:', e)
    return false
  }
}
```

修改 `loadSavingPotential` 函数 (约第230-231行):
```typescript
async function loadSavingPotential(): Promise<SavingPotential | null> {
  try {
    const res = await getSavingPotential()
    return res as SavingPotential
  } catch (e: any) {
    console.error('加载节能潜力失败:', e)
  }
  return null
}
```

修改 `loadDistributionDiagram` 函数 (约第243-244行):
```typescript
async function loadDistributionDiagram() {
  try {
    const res = await getDistributionDiagram()
    energyStore.setDistributionData(res as DistributionDiagram)
  } catch (e: any) {
    console.error('加载配电图失败:', e)
  }
}
```

**Step 3: 添加缺失的类型导入**

在文件顶部添加:
```typescript
import type {
  RealtimePowerData,
  RealtimePowerSummary,
  PUEData,
  PUETrend,
  EnergyStat,
  EnergyTrend,
  EnergyComparison,
  EnergySuggestion,
  SavingPotential,
  DistributionDiagram
} from '@/api/modules/energy'
```

**Step 4: 验证修复**

Run: `npx vue-tsc --noEmit 2>&1 | grep "useEnergy.ts" | wc -l`
Expected: 0

**Step 5: Commit**

```bash
git add frontend/src/composables/useEnergy.ts
git commit -m "fix: correct API response data extraction in useEnergy"
```

---

## Task 3: 修复 StatusTag.vue 类型问题

**Files:**
- Modify: `frontend/src/components/common/StatusTag.vue`

**问题分析:**
1. `tagType` 返回类型可能为空字符串，但 el-tag 的 type 属性不接受空字符串
2. `statusConfig` 的 fallback 对象缺少 `color` 和 `flash` 属性

**Step 1: 修复类型定义和 fallback 对象**

修改第96行的 fallback 对象:
```typescript
const statusConfig = computed(() => {
  const statusKey = String(props.status)
  const mergedMap = { ...defaultStatusMap, ...props.statusMap }
  return mergedMap[statusKey] || { type: 'info' as StatusType, text: statusKey, color: undefined, flash: false }
})
```

修改第99-101行的 tagType 计算属性:
```typescript
const tagType = computed(() => {
  const type = props.type || statusConfig.value.type
  // 确保返回有效的 tag type，空字符串转为 'info'
  return type || 'info'
})
```

**Step 2: 验证修复**

Run: `npx vue-tsc --noEmit 2>&1 | grep "StatusTag.vue" | wc -l`
Expected: 0

**Step 3: Commit**

```bash
git add frontend/src/components/common/StatusTag.vue
git commit -m "fix: StatusTag type compatibility with Element Plus"
```

---

## Task 4: 修复 ExportButton.vue 事件处理类型

**Files:**
- Modify: `frontend/src/components/common/ExportButton.vue`

**问题分析:**
`@click` 事件处理器接收 `MouseEvent`，但函数签名期望 `string` 参数。

**Step 1: 读取当前文件了解结构**

**Step 2: 修复事件处理**

将按钮的 click 处理修改为箭头函数:
```vue
<el-button @click="() => handleExport('excel')">导出 Excel</el-button>
```

或修改函数签名:
```typescript
const handleExport = async (format: string = 'excel') => {
  // ...
}

// 在模板中使用 @click="() => handleExport('excel')"
```

**Step 3: 验证修复**

Run: `npx vue-tsc --noEmit 2>&1 | grep "ExportButton.vue" | wc -l`
Expected: 0

**Step 4: Commit**

```bash
git add frontend/src/components/common/ExportButton.vue
git commit -m "fix: ExportButton click handler type"
```

---

## Task 5: 修复 PieChart.vue ECharts 类型

**Files:**
- Modify: `frontend/src/components/charts/PieChart.vue`

**问题分析:**
`roseType` 属性类型为 `boolean | 'area' | 'radius'`，但 ECharts 期望 `'area' | 'radius'`。

**Step 1: 修复 roseType 处理**

```typescript
const option = computed(() => ({
  series: [{
    type: 'pie',
    roseType: props.roseType === false ? undefined : props.roseType,
    // ...
  }]
}))
```

**Step 2: 验证修复**

Run: `npx vue-tsc --noEmit 2>&1 | grep "PieChart.vue" | wc -l`
Expected: 0

**Step 3: Commit**

```bash
git add frontend/src/components/charts/PieChart.vue
git commit -m "fix: PieChart roseType property type"
```

---

## Task 6: 修复 energy/config.vue 数据提取和类型

**Files:**
- Modify: `frontend/src/views/energy/config.vue`

**问题分析:**
1. el-tag :type 属性类型问题
2. API 响应数据提取错误 (.data 不存在)

**Step 1: 修复 el-tag 类型 - 使用类型断言或创建辅助函数**

创建辅助函数:
```typescript
type TagType = 'success' | 'warning' | 'info' | 'primary' | 'danger'

const getTagType = (type: string): TagType => {
  const validTypes: TagType[] = ['success', 'warning', 'info', 'primary', 'danger']
  return validTypes.includes(type as TagType) ? (type as TagType) : 'info'
}
```

在模板中使用:
```vue
<el-tag :type="getTagType(row.status === 'enabled' ? 'success' : 'info')">
```

**Step 2: 修复数据提取 (约第472, 482, 492, 502, 512行)**

```typescript
// 修改 loadTransformers
const loadTransformers = async () => {
  const res = await getTransformers()
  transformers.value = res as Transformer[]
}

// 修改 loadMeterPoints
const loadMeterPoints = async () => {
  const res = await getMeterPoints()
  meterPoints.value = res as MeterPoint[]
}

// 修改 loadPanels
const loadPanels = async () => {
  const res = await getPanels()
  panels.value = res as DistributionPanel[]
}

// 修改 loadCircuits
const loadCircuits = async () => {
  const res = await getCircuits()
  circuits.value = res as DistributionCircuit[]
}

// 修改 loadPricings
const loadPricings = async () => {
  const res = await getPricings()
  pricings.value = res as ElectricityPricing[]
}
```

**Step 3: 验证修复**

Run: `npx vue-tsc --noEmit 2>&1 | grep "config.vue" | wc -l`
Expected: 0

**Step 4: Commit**

```bash
git add frontend/src/views/energy/config.vue
git commit -m "fix: energy config page type errors"
```

---

## Task 7: 修复 energy/monitor.vue 类型问题

**Files:**
- Modify: `frontend/src/views/energy/monitor.vue`

**问题分析:**
1. el-tag 类型问题
2. 数据提取 .data 错误
3. ECharts gauge data value 类型错误 (string vs number)

**Step 1: 添加 TagType 辅助函数**

**Step 2: 修复数据提取 (约第445行)**

```typescript
const loadEnergyDashboard = async () => {
  const res = await getEnergyDashboard()
  energyData.value = res as EnergyDashboardData
}
```

**Step 3: 修复 gauge 图表 data.value 类型 (约第458, 531行)**

```typescript
// 将 value: pue.toFixed(2) 改为 value: parseFloat(pue.toFixed(2))
data: [{
  value: parseFloat(energyData.value?.efficiency?.pue?.toFixed(2) || '0'),
  name: 'PUE'
}]
```

**Step 4: 验证修复**

Run: `npx vue-tsc --noEmit 2>&1 | grep "monitor.vue" | wc -l`
Expected: 0

**Step 5: Commit**

```bash
git add frontend/src/views/energy/monitor.vue
git commit -m "fix: energy monitor page type errors"
```

---

## Task 8: 修复 energy/topology.vue 数据提取

**Files:**
- Modify: `frontend/src/views/energy/topology.vue`

**问题分析:**
1. el-tag 类型问题
2. 数据提取 .data 错误 (第115行)

**Step 1: 修复数据提取**

```typescript
const loadTopology = async () => {
  const res = await getTopology()
  topologyData.value = res as DistributionTopology
}
```

**Step 2: 验证修复**

Run: `npx vue-tsc --noEmit 2>&1 | grep "topology.vue" | wc -l`
Expected: 0

**Step 3: Commit**

```bash
git add frontend/src/views/energy/topology.vue
git commit -m "fix: energy topology page type errors"
```

---

## Task 9: 修复 energy/suggestions.vue 类型问题

**Files:**
- Modify: `frontend/src/views/energy/suggestions.vue`

**问题分析:**
1. templates 返回类型不匹配 (第314行)
2. new_suggestions_count 应为 new_suggestions (第334行)
3. by_category 属性不存在 (第349, 351行)
4. ECharts pie data 类型 (第362行)

**Step 1: 修复 templates 类型**

```typescript
const templates = ref<SuggestionTemplate[]>([])

const loadTemplates = async () => {
  const res = await getSuggestionTemplates()
  // 如果返回 { total, templates }，则提取 templates
  if (Array.isArray(res)) {
    templates.value = res
  } else if (res && 'templates' in res) {
    templates.value = (res as { templates: SuggestionTemplate[] }).templates
  }
}
```

**Step 2: 修复 analyze 结果属性名**

```typescript
// 第334行: new_suggestions_count → new_suggestions (检查实际API返回)
const newCount = result.new_suggestions?.length || 0
```

**Step 3: 修复 summary 统计数据**

检查 API 返回的 summary 结构，添加适当的可选链或类型守卫:
```typescript
const categoryData = (summary as any).by_category || {}
```

**Step 4: 修复 ECharts pie data 类型**

```typescript
data: Object.entries(categoryData).map(([name, value]) => ({
  name,
  value: value as number
}))
```

**Step 5: 验证修复**

Run: `npx vue-tsc --noEmit 2>&1 | grep "suggestions.vue" | wc -l`
Expected: 0

**Step 6: Commit**

```bash
git add frontend/src/views/energy/suggestions.vue
git commit -m "fix: energy suggestions page type errors"
```

---

## Task 10: 修复 energy/regulation.vue 类型问题

**Files:**
- Modify: `frontend/src/views/energy/regulation.vue`

**问题分析:**
el-tag 类型问题 (第56行)

**Step 1: 修复 el-tag 类型**

使用类型断言或辅助函数:
```vue
<el-tag :type="(config.type as 'success' | 'warning' | 'info' | 'primary' | 'danger')">
```

**Step 2: 验证修复**

Run: `npx vue-tsc --noEmit 2>&1 | grep "regulation.vue" | wc -l`
Expected: 0

**Step 3: Commit**

```bash
git add frontend/src/views/energy/regulation.vue
git commit -m "fix: energy regulation page tag type"
```

---

## Task 11: 修复 alarm/index.vue 和 device/index.vue 类型

**Files:**
- Modify: `frontend/src/views/alarm/index.vue`
- Modify: `frontend/src/views/device/index.vue`

**问题分析:**
el-tag 类型问题

**Step 1: 在 alarm/index.vue 添加类型辅助函数**

```typescript
type TagType = 'success' | 'warning' | 'info' | 'primary' | 'danger'

const getLevelTagType = (level: string): TagType => {
  const map: Record<string, TagType> = {
    critical: 'danger',
    major: 'warning',
    minor: 'primary',
    info: 'info'
  }
  return map[level] || 'info'
}

const getStatusTagType = (status: string): TagType => {
  const map: Record<string, TagType> = {
    active: 'danger',
    acknowledged: 'warning',
    resolved: 'success'
  }
  return map[status] || 'info'
}
```

在模板中使用:
```vue
<el-tag :type="getLevelTagType(row.alarm_level)">
<el-tag :type="getStatusTagType(row.status)">
```

**Step 2: 在 device/index.vue 添加类似修复**

**Step 3: 验证修复**

Run: `npx vue-tsc --noEmit 2>&1 | grep -E "(alarm|device)/index.vue" | wc -l`
Expected: 0

**Step 4: Commit**

```bash
git add frontend/src/views/alarm/index.vue frontend/src/views/device/index.vue
git commit -m "fix: alarm and device page tag types"
```

---

## Task 12: 修复 settings/index.vue 类型问题

**Files:**
- Modify: `frontend/src/views/settings/index.vue`

**问题分析:**
1. 多处 el-tag 类型问题 (第46, 83, 157, 188行)
2. threshold_type 类型不匹配 (第712行)

**Step 1: 添加 TagType 辅助函数**

**Step 2: 修复 threshold 更新参数类型 (第712行)**

```typescript
type ThresholdType = 'high' | 'low' | 'high_high' | 'low_low' | 'equal' | 'change'

const handleUpdateThreshold = async (row: ThresholdInfo) => {
  await updateThreshold(row.id, {
    point_id: row.point_id,
    threshold_type: row.threshold_type as ThresholdType,
    threshold_value: row.threshold_value,
    alarm_level: row.alarm_level,
    alarm_message: row.alarm_message
  })
}
```

**Step 3: 验证修复**

Run: `npx vue-tsc --noEmit 2>&1 | grep "settings/index.vue" | wc -l`
Expected: 0

**Step 4: Commit**

```bash
git add frontend/src/views/settings/index.vue
git commit -m "fix: settings page type errors"
```

---

## Task 13: 修复 history/index.vue 类型问题

**Files:**
- Modify: `frontend/src/views/history/index.vue`

**问题分析:**
1. ECharts 图表类型错误 (第287行)
2. 导出格式类型错误 (第367行): 'xlsx' 应为 'excel'

**Step 1: 修复图表类型**

确保 chartType 变量使用正确的类型:
```typescript
const chartType = ref<'line' | 'bar'>('line')
```

**Step 2: 修复导出格式**

```typescript
// 将 'xlsx' 改为 'excel'
const exportFormat = ref<'excel' | 'csv' | 'json'>('excel')
```

**Step 3: 验证修复**

Run: `npx vue-tsc --noEmit 2>&1 | grep "history/index.vue" | wc -l`
Expected: 0

**Step 4: Commit**

```bash
git add frontend/src/views/history/index.vue
git commit -m "fix: history page type errors"
```

---

## Task 14: 最终验证

**Step 1: 运行完整类型检查**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: 无错误输出

**Step 2: 运行构建验证**

Run: `cd frontend && npm run build`
Expected: 构建成功

**Step 3: 最终提交**

```bash
git add -A
git commit -m "fix: resolve all TypeScript type errors

- Add Vite environment type definitions
- Fix API response data extraction in useEnergy and vue files
- Fix Element Plus tag type compatibility
- Fix ECharts series data types
- Fix threshold type parameter
- Fix export format type

All vue-tsc checks now pass."
```

---

## 执行检查清单

- [ ] Task 1: vite-env.d.ts 创建
- [ ] Task 2: useEnergy.ts 修复
- [ ] Task 3: StatusTag.vue 修复
- [ ] Task 4: ExportButton.vue 修复
- [ ] Task 5: PieChart.vue 修复
- [ ] Task 6: energy/config.vue 修复
- [ ] Task 7: energy/monitor.vue 修复
- [ ] Task 8: energy/topology.vue 修复
- [ ] Task 9: energy/suggestions.vue 修复
- [ ] Task 10: energy/regulation.vue 修复
- [ ] Task 11: alarm/index.vue + device/index.vue 修复
- [ ] Task 12: settings/index.vue 修复
- [ ] Task 13: history/index.vue 修复
- [ ] Task 14: 最终验证
