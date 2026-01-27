# 节能机会方案详情页增强计划

## 背景和问题分析

### 用户提出的核心问题

1. **为什么有多个需量控制方案，且年度效益分析结果不同？**
   - 后端可能为同一类别生成多个机会，每个机会有不同的参数配置
   - 每个机会应该是独立的，有自己的 analysis_data 和 potential_saving
   - 需要在UI上清晰展示每个方案的差异点

2. **需量控制方案与需量板块中的需量曲线、需量配置分析、负荷转移分析之间是什么关系？**
   - 理想流程：分析页面(analysis.vue) → 生成机会(opportunities) → 查看详情(OpportunityDetailPanel) → 执行(execution)
   - 当前问题：机会详情页与分析页面缺乏有机联系
   - 解决方案：
     - 详情页应嵌入相关的分析组件（已部分实现）
     - 详情页应提供"查看完整分析"链接跳回分析页面（已实现）
     - 分析页面应能直接生成机会（已实现）

3. **6大方案模板有什么区别？为什么详情页相同？如何区分？**
   - 6大类别：
     1. 电费结构优化 (峰谷套利、需量控制等)
     2. 设备运行优化 (空调、照明、UPS等)
     3. 设备改造升级
     4. 综合优化方案
     5. 其他类别...
   - 当前：所有类别共用同一个 OpportunityDetailPanel，通过 source_plugin 区分
   - 问题：区分不够明显，用户体验不清晰
   - 解决方案：
     - 强化视觉区分（图标、颜色）
     - 不同类别展示不同的嵌入式分析组件
     - 模拟参数区域根据类别动态调整

### 当前已发现的技术问题

#### OptimizationOverview.vue（已修复）
- ✅ 白色背景问题
- ✅ 只支持峰/谷两个时段 → 改为支持5时段（尖峰、峰、平、谷、深谷）
- ✅ 单一转移规则 → 改为每个设备支持多条转移规则
- ✅ 静态年度收益 → 改为实时计算
- ✅ 缺少系统推荐 → 添加推荐计算和"使用推荐值"功能

#### OpportunityDetailPanel.vue（待修复）
- ❌ 源时段只有 sharp/peak/flat，目标时段只有 flat/valley/deep_valley
- ❌ 单一转移规则，不支持多规则配置
- ❌ potential_saving 静态显示，不随参数变化
- ❌ 缺少系统推荐功能
- ❌ 方案类别区分不够明显

## 解决方案

### 方案 A：全面增强 OpportunityDetailPanel（推荐）

**优势**：
- 保持统一的详情页入口
- 通过 source_plugin 和 category 自适应显示内容
- 代码复用性高
- 用户体验一致

**实施内容**：

#### 1. 修复时段选择问题
- 源时段和目标时段都支持全部5个时段：尖峰、峰、平、谷、深谷
- 根据电价配置动态显示可用时段
- 添加时段价格提示

#### 2. 支持多规则转移配置（仅限峰谷套利方案）
- 参考 OptimizationOverview.vue 的实现
- 添加 deviceShiftRules 状态管理
- 支持每个设备配置多条转移规则
- 实时计算总节省金额

#### 3. 实时计算功能
- 将 potential_saving 从静态值改为 computed
- 根据用户调整的模拟参数实时计算
- 不同方案类型有不同的计算逻辑

#### 4. 添加系统推荐功能
- 根据电价时段差异自动计算最优参数
- 提供"使用推荐值"按钮
- 显示推荐理由

#### 5. 强化方案类别视觉区分
- 添加类别图标和颜色标识
- 在标题区域显示方案类型标签
- 不同类别使用不同的主题色

#### 6. 优化嵌入式组件展示
- 确保正确的组件显示逻辑
- 添加加载状态
- 优化布局和间距

### 方案 B：为每个类别创建专门的详情组件

**优势**：
- 每个类别完全独立，灵活性高
- 代码职责清晰

**劣势**：
- 代码重复多
- 维护成本高
- 用户体验不一致

### 推荐方案 A

## 详细设计：增强 OpportunityDetailPanel.vue

### 1. 数据结构调整

```typescript
// 添加多规则支持（仅峰谷套利方案）
interface ShiftRule {
  sourcePeriod: string  // 'sharp' | 'peak' | 'flat' | 'valley' | 'deep_valley'
  targetPeriod: string
  power: number
  hours: number
}

const deviceShiftRules = reactive<Record<number, ShiftRule[]>>({})

// 实时计算的年度节省
const calculatedAnnualSaving = computed(() => {
  if (simulationType.value === 'peak_shift') {
    // 根据 deviceShiftRules 计算总节省
    let total = 0
    for (const [deviceId, rules] of Object.entries(deviceShiftRules)) {
      for (const rule of rules) {
        const sourcePricePrice = getPeriodPrice(rule.sourcePeriod)
        const targetPrice = getPeriodPrice(rule.targetPeriod)
        const priceDiff = sourcePrice - targetPrice
        const dailySaving = rule.power * rule.hours * priceDiff
        total += dailySaving * 250 // 年度工作日
      }
    }
    return total
  } else {
    // 其他方案类型的计算逻辑
    return props.opportunity.potential_saving
  }
})
```

### 2. UI 布局调整

```vue
<template>
  <div class="opportunity-detail-panel">
    <!-- 新增：类别标识区域 -->
    <div class="category-badge">
      <el-icon :size="32" :color="categoryColor">
        <component :is="categoryIcon" />
      </el-icon>
      <div class="category-info">
        <div class="category-name">{{ getCategoryName(opportunity.category) }}</div>
        <div class="source-plugin">{{ getPluginDisplayName(opportunity.source_plugin) }}</div>
      </div>
    </div>

    <!-- 基本信息 - 调整年度节省显示 -->
    <div class="saving-highlight">
      <div class="saving-value">
        <el-icon><Coin /></el-icon>
        {{ formatSaving(calculatedAnnualSaving) }}  <!-- 改为实时计算 -->
      </div>
      <div class="saving-label">
        预计年度节省
        <el-tooltip v-if="isCalculated" content="此金额根据当前参数实时计算">
          <el-icon><InfoFilled /></el-icon>
        </el-tooltip>
      </div>
    </div>

    <!-- 嵌入式分析组件 - 保持现有逻辑 -->
    <div class="section embedded-analysis" v-if="embeddedComponents.length">
      ...
    </div>

    <!-- 模拟区域 - 增强峰谷套利部分 -->
    <div class="section" v-if="showSimulation">
      <h3 class="section-title">
        <span>参数模拟</span>
        <div class="title-actions">
          <el-button
            v-if="simulationType === 'peak_shift'"
            type="info"
            size="small"
            @click="calculateSystemRecommendation"
          >
            生成推荐配置
          </el-button>
          <el-button type="primary" size="small" @click="runSimulation" :loading="simulating">
            运行模拟
          </el-button>
        </div>
      </h3>

      <!-- 峰谷套利优化 - 多规则支持 -->
      <template v-if="simulationType === 'peak_shift'">
        <!-- 系统推荐展示 -->
        <el-alert
          v-if="systemRecommendation"
          type="success"
          :closable="false"
          class="recommendation-alert"
        >
          <template #title>
            <div class="rec-header">
              <span>系统推荐方案</span>
              <el-button type="primary" size="small" @click="applyRecommendation">
                使用推荐值
              </el-button>
            </div>
          </template>
          <div class="rec-summary">
            预计年度节省: <strong>{{ formatSaving(systemRecommendation.annualSaving) }}</strong>
          </div>
          <div class="rec-rules">
            <div v-for="(rule, idx) in systemRecommendation.rules" :key="idx" class="rec-rule">
              {{ rule.deviceNames.join('、') }}:
              {{ rule.power }}kW × {{ rule.hours }}h/天
              从{{ periodNames[rule.sourcePeriod] }}转{{ periodNames[rule.targetPeriod] }}
              (日节省: ¥{{ rule.dailySaving.toFixed(2) }})
            </div>
          </div>
        </el-alert>

        <!-- 设备多规则配置 -->
        <div class="device-shift-config">
          <div v-for="device in availableDevices" :key="device.device_id" class="device-config-card">
            <div class="device-header" @click="toggleDeviceExpand(device.device_id)">
              <el-checkbox
                :model-value="isDeviceSelected(device.device_id)"
                @change="toggleDeviceSelection(device.device_id)"
              />
              <div class="device-info">
                <span class="device-name">{{ device.device_name }}</span>
                <span class="device-power">{{ device.total_adjustable_power }}kW</span>
              </div>
              <el-icon :class="{ rotated: expandedDevices.includes(device.device_id) }">
                <ArrowDown />
              </el-icon>
            </div>

            <!-- 展开后显示规则配置 -->
            <el-collapse-transition>
              <div v-show="expandedDevices.includes(device.device_id)" class="device-rules">
                <div
                  v-for="(rule, ruleIdx) in deviceShiftRules[device.device_id] || []"
                  :key="ruleIdx"
                  class="shift-rule-row"
                >
                  <el-select v-model="rule.sourcePeriod" size="small" style="width: 100px;">
                    <el-option label="尖峰" value="sharp" :disabled="!isPeriodAvailable('sharp')" />
                    <el-option label="峰时" value="peak" :disabled="!isPeriodAvailable('peak')" />
                    <el-option label="平时" value="flat" :disabled="!isPeriodAvailable('flat')" />
                    <el-option label="谷时" value="valley" :disabled="!isPeriodAvailable('valley')" />
                    <el-option label="深谷" value="deep_valley" :disabled="!isPeriodAvailable('deep_valley')" />
                  </el-select>
                  <el-icon><Right /></el-icon>
                  <el-select v-model="rule.targetPeriod" size="small" style="width: 100px;">
                    <el-option label="尖峰" value="sharp" :disabled="!isPeriodAvailable('sharp')" />
                    <el-option label="峰时" value="peak" :disabled="!isPeriodAvailable('peak')" />
                    <el-option label="平时" value="flat" :disabled="!isPeriodAvailable('flat')" />
                    <el-option label="谷时" value="valley" :disabled="!isPeriodAvailable('valley')" />
                    <el-option label="深谷" value="deep_valley" :disabled="!isPeriodAvailable('deep_valley')" />
                  </el-select>
                  <el-input-number v-model="rule.power" size="small" :min="0" :step="5" style="width: 120px;" />
                  <span>kW</span>
                  <el-input-number v-model="rule.hours" size="small" :min="1" :max="8" style="width: 100px;" />
                  <span>小时</span>
                  <el-button
                    type="danger"
                    size="small"
                    :icon="Delete"
                    circle
                    @click="removeShiftRule(device.device_id, ruleIdx)"
                  />
                </div>
                <el-button
                  type="primary"
                  size="small"
                  :icon="Plus"
                  @click="addShiftRule(device.device_id)"
                  style="margin-top: 8px;"
                >
                  添加转移规则
                </el-button>
              </div>
            </el-collapse-transition>
          </div>
        </div>

        <!-- 实时计算结果 -->
        <div class="realtime-calculation">
          <el-card shadow="hover">
            <div class="calc-row">
              <span class="calc-label">日节省</span>
              <span class="calc-value">¥{{ totalDailySaving.toFixed(2) }}</span>
            </div>
            <div class="calc-row">
              <span class="calc-label">月节省</span>
              <span class="calc-value">¥{{ totalMonthlySaving.toFixed(2) }}</span>
            </div>
            <div class="calc-row highlight">
              <span class="calc-label">年度节省</span>
              <span class="calc-value">¥{{ formatSaving(calculatedAnnualSaving) }}</span>
            </div>
          </el-card>
        </div>
      </template>

      <!-- 其他方案类型保持现有逻辑 -->
      <template v-else-if="simulationType === 'demand_adjustment'">
        ...
      </template>
    </div>

    <!-- 操作按钮 -->
    <div class="actions">
      ...
    </div>
  </div>
</template>
```

### 3. 核心方法实现

```typescript
// 类别图标映射
const categoryIcons: Record<number, string> = {
  1: 'TrendCharts',  // 电费结构优化
  2: 'Setting',      // 设备运行优化
  3: 'Upgrade',      // 设备改造升级
  4: 'DataAnalysis'  // 综合优化方案
}

// 类别颜色映射
const categoryColors: Record<number, string> = {
  1: '#1890ff',
  2: '#52c41a',
  3: '#faad14',
  4: '#722ed1'
}

// 获取时段价格（支持5时段）
function getPeriodPrice(period: string): number {
  const priceData = props.opportunity.analysis_data?.pricing_config || {}
  switch (period) {
    case 'sharp': return priceData.sharp_price || 0
    case 'peak': return priceData.peak_price || 0
    case 'flat': return priceData.flat_price || priceData.normal_price || 0
    case 'valley': return priceData.valley_price || 0
    case 'deep_valley': return priceData.deep_valley_price || priceData.valley_price * 0.8 || 0
    default: return 0
  }
}

// 判断时段是否可用（基于电价配置）
function isPeriodAvailable(period: string): boolean {
  return getPeriodPrice(period) > 0
}

// 计算系统推荐配置
function calculateSystemRecommendation() {
  const devices = availableDevices.value
  if (devices.length === 0) return

  // 获取电价最高和最低的时段
  const periods = ['sharp', 'peak', 'flat', 'valley', 'deep_valley']
  const pricesWithPeriod = periods
    .map(p => ({ period: p, price: getPeriodPrice(p) }))
    .filter(p => p.price > 0)
    .sort((a, b) => b.price - a.price)

  if (pricesWithPeriod.length < 2) {
    ElMessage.warning('电价配置不足，无法生成推荐')
    return
  }

  const highestPeriod = pricesWithPeriod[0]
  const lowestPeriod = pricesWithPeriod[pricesWithPeriod.length - 1]
  const priceDiff = highestPeriod.price - lowestPeriod.price

  // 为每个设备生成推荐规则
  const rules: RecommendedRule[] = []
  for (const device of devices) {
    const power = Math.min(device.total_adjustable_power, 50) // 建议每次不超过50kW
    const hours = 4 // 建议每天4小时
    const dailySaving = power * hours * priceDiff

    rules.push({
      deviceIds: [device.device_id],
      deviceNames: [device.device_name],
      sourcePeriod: highestPeriod.period,
      targetPeriod: lowestPeriod.period,
      power,
      hours,
      dailySaving
    })
  }

  const annualSaving = rules.reduce((sum, r) => sum + r.dailySaving, 0) * 250

  systemRecommendation.value = {
    rules,
    annualSaving
  }
}

// 应用系统推荐
function applyRecommendation() {
  if (!systemRecommendation.value) return

  // 清空现有规则
  for (const deviceId of Object.keys(deviceShiftRules)) {
    deviceShiftRules[deviceId] = []
  }

  // 应用推荐规则
  for (const rule of systemRecommendation.value.rules) {
    for (const deviceId of rule.deviceIds) {
      if (!deviceShiftRules[deviceId]) {
        deviceShiftRules[deviceId] = []
      }
      deviceShiftRules[deviceId].push({
        sourcePeriod: rule.sourcePeriod,
        targetPeriod: rule.targetPeriod,
        power: rule.power,
        hours: rule.hours
      })
    }
  }

  // 自动展开所有设备
  expandedDevices.value = rule.deviceIds

  ElMessage.success('已应用推荐配置')
}

// 实时计算总节省
const totalDailySaving = computed(() => {
  let total = 0
  for (const [deviceId, rules] of Object.entries(deviceShiftRules)) {
    for (const rule of rules) {
      const sourcePrice = getPeriodPrice(rule.sourcePeriod)
      const targetPrice = getPeriodPrice(rule.targetPeriod)
      const priceDiff = sourcePrice - targetPrice
      total += rule.power * rule.hours * priceDiff
    }
  }
  return total
})

const totalMonthlySaving = computed(() => totalDailySaving.value * 22)
const totalAnnualSaving = computed(() => totalDailySaving.value * 250)

// 覆盖 calculatedAnnualSaving 的峰谷套利分支
const calculatedAnnualSaving = computed(() => {
  if (simulationType.value === 'peak_shift') {
    return totalAnnualSaving.value
  }
  // 其他方案类型...
  return props.opportunity.potential_saving
})
```

### 4. 样式增强

```scss
.category-badge {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: linear-gradient(135deg, rgba(24, 144, 255, 0.15), rgba(24, 144, 255, 0.05));
  border-radius: 12px;
  margin-bottom: 24px;

  .category-info {
    flex: 1;

    .category-name {
      font-size: 18px;
      font-weight: 600;
      color: var(--text-primary);
    }

    .source-plugin {
      font-size: 12px;
      color: var(--text-secondary);
      margin-top: 4px;
    }
  }
}

.device-shift-config {
  margin-top: 16px;

  .device-config-card {
    background: var(--bg-tertiary);
    border-radius: 8px;
    margin-bottom: 12px;
    overflow: hidden;

    .device-header {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px 16px;
      cursor: pointer;
      transition: background 0.2s;

      &:hover {
        background: var(--bg-hover);
      }

      .device-info {
        flex: 1;
        display: flex;
        justify-content: space-between;

        .device-name {
          font-weight: 500;
          color: var(--text-primary);
        }

        .device-power {
          color: var(--primary-color);
          font-weight: 600;
        }
      }

      .el-icon.rotated {
        transform: rotate(180deg);
      }
    }

    .device-rules {
      padding: 0 16px 16px;
      background: rgba(0, 0, 0, 0.2);

      .shift-rule-row {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;

        span {
          color: var(--text-secondary);
          font-size: 12px;
        }
      }
    }
  }
}

.realtime-calculation {
  margin-top: 16px;

  .calc-row {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid var(--border-color);

    &:last-child {
      border-bottom: none;
    }

    &.highlight {
      padding-top: 12px;
      margin-top: 8px;
      border-top: 2px solid var(--primary-color);

      .calc-label {
        font-size: 16px;
        font-weight: 600;
      }

      .calc-value {
        font-size: 20px;
        color: var(--success-color);
      }
    }

    .calc-label {
      color: var(--text-secondary);
    }

    .calc-value {
      font-weight: 500;
      color: var(--text-primary);
    }
  }
}
```

## 实施步骤

### Step 1: 修复时段选择问题（15%）
- 修改源时段和目标时段的 el-option，支持全部5个时段
- 添加 isPeriodAvailable() 方法根据电价动态禁用
- 添加时段价格提示

### Step 2: 实现多规则转移配置（35%）
- 添加 deviceShiftRules reactive 状态
- 创建设备展开/折叠逻辑
- 实现添加/删除规则功能
- 实时计算总节省

### Step 3: 添加系统推荐功能（25%）
- 实现 calculateSystemRecommendation()
- 实现 applyRecommendation()
- 添加推荐展示 UI

### Step 4: 强化类别视觉区分（15%）
- 添加类别徽章区域
- 实现类别图标和颜色映射
- 优化整体布局

### Step 5: 全面测试（10%）
- 测试各种方案类型
- 测试多规则配置
- 测试实时计算
- 测试推荐功能

## 关键文件

**需要修改的文件**：
- `D:\mytest1\frontend\src\components\energy\OpportunityDetailPanel.vue` - 主要修改

**参考文件**：
- `D:\mytest1\frontend\src\components\energy\OptimizationOverview.vue` - 多规则实现参考
- `D:\mytest1\frontend\src\views\energy\analysis.vue` - 集成方式参考

## 数据流

```
用户在节能中心点击机会
  ↓
OpportunityDetailPanel 打开
  ↓
根据 source_plugin 确定 simulationType
  ↓
根据 category 显示类别徽章和颜色
  ↓
加载嵌入式分析组件（LoadPeriodChart等）
  ↓
如果是峰谷套利：
  - 显示多规则配置界面
  - 用户调整参数
  - 实时计算更新年度节省
  - 可选：点击"生成推荐配置"
  - 可选：点击"使用推荐值"自动填充
  ↓
点击"运行模拟"调用后端API
  ↓
显示模拟结果
  ↓
点击"确认执行"创建执行计划
```

## 验证方法

### 功能验证
1. 测试6大类别机会的详情页显示
2. 验证峰谷套利方案的多规则配置
3. 验证5时段选择和动态禁用
4. 验证实时计算准确性
5. 验证系统推荐功能
6. 验证其他方案类型不受影响

### 视觉验证
1. 检查类别徽章显示正确
2. 检查不同类别的颜色区分
3. 检查深色主题一致性
4. 检查响应式布局

### 集成验证
1. 从分析页面创建机会
2. 在节能中心查看机会
3. 打开详情页验证数据预填充
4. 点击"查看完整分析"跳转正确
5. 修改参数后执行机会

## 预期成果

增强后的 OpportunityDetailPanel 将提供：
1. **更清晰的方案区分**：通过图标、颜色、类别标签明确标识
2. **更强大的峰谷套利配置**：支持每设备多规则、5时段选择、实时计算
3. **智能推荐功能**：系统自动计算最优配置，用户一键应用
4. **更好的用户体验**：视觉区分明确、交互流畅、反馈及时
5. **统一的详情页框架**：所有方案类型共享同一组件，但展示内容自适应

形成完整的 **分析 → 生成机会 → 配置优化 → 执行** 闭环。
