# 节能中心与需量板块集成实现总结

## 实现日期
2026-01-26

## 背景
整合需量板块与节能管理中心，通过嵌入式组件避免界面重复，实现以节能中心为主、需量板块作为数据源的架构。

## 需求分析

### 核心问题
1. **为什么有多个需量控制方案？**
   - 不同 source_plugin 生成不同优化方案（如 demand_optimizer, peak_valley_optimizer）
   - 需要通过方案类型区分，而非仅按 category

2. **需量板块与节能管理如何结合？**
   - 采用嵌入式组件架构
   - 节能中心调用需量板块的图表组件
   - 避免 UI 重复，保持数据一致性

3. **6大方案模板如何区分？**
   - 通过 `source_plugin` 字段映射到 8 种 `SimulationType`
   - 每种类型有独特的参数模板和嵌入式组件

## 架构设计

### 方案选择：方案A - 节能中心为主
- 节能中心：决策与执行入口
- 需量板块：提供数据分析能力
- 嵌入式组件：需量板块的图表可嵌入到节能中心详情页

### 模块职责划分

| 模块 | 职责 |
|------|------|
| 节能中心 | 机会发现、方案模拟、设备选择、执行管理 |
| 需量板块 | 需量曲线分析、峰谷分布、功率因数追踪 |
| 嵌入组件 | DemandComparisonCard, DemandCurveMini, LoadPeriodChart |

## 实现内容

### 后端 (4个文件)

#### 1. `backend/app/api/v1/demand.py` (新建)
- **4个嵌入式 API 端点**：
  - `GET /v1/demand/comparison` - 需量配置对比
  - `GET /v1/demand/curve-mini` - 迷你需量曲线
  - `GET /v1/demand/load-period` - 负荷时段分布
  - `GET /v1/demand/power-factor-trend` - 功率因数趋势
- **Mock数据支持**：无真实数据时返回示例数据

#### 2. `backend/app/api/v1/__init__.py` (修改)
- 注册 demand_router 到 api_router

#### 3. `backend/app/schemas/energy.py` (修改)
- `OpportunitySummary` 新增字段：
  - `source_plugin: Optional[str]` - 来源插件标识
  - `analysis_data: Optional[Dict]` - 分析详情数据
  - `description: Optional[str]` - 机会描述

#### 4. `backend/app/api/v1/opportunities.py` (修改)
- dashboard 端点返回新增字段
- 支持前端根据 source_plugin 区分方案类型

### 前端 (7个文件)

#### 1. `frontend/src/api/modules/demand.ts` (新建)
**类型定义**：
- DemandComparisonData - 需量对比数据
- DemandCurveMiniData - 迷你曲线数据
- LoadPeriodData - 负荷时段数据
- PowerFactorTrendData - 功率因数数据

**API函数**：
```typescript
getDemandComparison(meterPointId?: number)
getDemandCurveMini(params?: {...})
getLoadPeriodDistribution(params?: {...})
getPowerFactorTrend(params?: {...})
```

#### 2. `frontend/src/components/demand/DemandComparisonCard.vue` (新建)
- **功能**：需量配置对比卡片
- **特性**：
  - 显示申报需量 vs 实际最大需量
  - 利用率进度条（颜色编码：低/合理/高）
  - 优化建议和月节省金额
  - 支持 compact 模式
  - "查看完整分析" 链接

#### 3. `frontend/src/components/demand/DemandCurveMini.vue` (新建)
- **功能**：迷你需量曲线图（ECharts）
- **特性**：
  - 近6/12个月需量趋势
  - 最大值高亮（红色）
  - 申报需量阈值线（黄色虚线）
  - 区域渐变填充
  - 响应式调整

#### 4. `frontend/src/components/demand/LoadPeriodChart.vue` (新建)
- **功能**：24小时负荷时段分布（ECharts）
- **特性**：
  - 按电价时段着色（尖峰紫、峰红、平橙、谷绿）
  - 时段汇总（峰/谷平均功率和时长）
  - 可转移功率提示
  - 支持高亮指定时段

#### 5. `frontend/src/components/demand/index.ts` (新建)
- Barrel导出所有嵌入式组件

#### 6. `frontend/src/api/modules/opportunities.ts` (修改)
- **新增类型**：
  ```typescript
  export type SimulationType =
    | 'demand_adjustment'      // 需量调整
    | 'peak_shift'             // 峰谷转移
    | 'power_factor_adjustment' // 功率因数调整
    | 'temperature_adjustment'  // 温度调节
    | 'lighting_control'       // 照明控制
    | 'device_regulation'      // 设备调控
    | 'equipment_upgrade'      // 设备升级
    | 'comprehensive'          // 综合优化
  ```
- **扩展接口**：OpportunitySummary 添加 source_plugin, analysis_data, description

#### 7. `frontend/src/components/energy/OpportunityDetailPanel.vue` (重写)

**核心改造**：

1. **方案类型映射**
```typescript
const pluginTypeMap: Record<string, SimulationType> = {
  'demand_optimizer': 'demand_adjustment',
  'peak_valley_optimizer': 'peak_shift',
  'power_factor_optimizer': 'power_factor_adjustment',
  'hvac_optimizer': 'temperature_adjustment',
  'lighting_optimizer': 'lighting_control',
  'ups_optimizer': 'device_regulation',
  'equipment_upgrade': 'equipment_upgrade',
  'comprehensive_optimizer': 'comprehensive'
}
```

2. **嵌入式组件映射**
```typescript
const pluginComponentMap: Record<string, string[]> = {
  'demand_optimizer': ['DemandComparisonCard', 'DemandCurveMini'],
  'peak_valley_optimizer': ['LoadPeriodChart'],
  'comprehensive_optimizer': ['DemandComparisonCard', 'LoadPeriodChart']
  // ...
}
```

3. **8种模拟参数模板**
- 需量调整：新申报需量
- 峰谷套利：转移功率、转移时长、源时段、目标时段
- 功率因数：目标功率因数
- 温度调节：目标温度
- 照明控制：控制策略、减少时长
- 设备升级：改造方案
- 设备调节：调节类型、目标效率
- 综合方案：多措施组合

4. **参数预填充**
```typescript
function initSimParams() {
  const data = props.opportunity.analysis_data
  if (data?.recommended_declared) {
    simParams.value.new_declared_demand = data.recommended_declared
  }
  // 从 analysis_data 预填充其他参数
}
```

5. **条件渲染嵌入组件**
```vue
<DemandComparisonCard
  v-if="embeddedComponents.includes('DemandComparisonCard')"
  :meter-point-id="opportunity.analysis_data?.meter_point_id"
  :analysis-data="opportunity.analysis_data"
  :compact="true"
/>
```

## 技术特性

### 类型安全
- 前端：TypeScript 严格类型检查通过
- 后端：Python 类型注解，Pydantic 数据验证

### 响应式设计
- ECharts 图表支持 ResizeObserver
- 组件支持 compact 模式

### 数据回退
- API 无数据时提供 Mock 数据
- simulationType 使用 category 作为回退

### 权限控制
- 所有 API 端点使用 `require_viewer` 依赖
- 数据访问需要至少 viewer 权限

## 测试验证

### 后端验证
✅ Python 语法检查通过
✅ 4个 demand API 端点成功注册
✅ 路由加载正确

### 前端验证
✅ TypeScript 编译通过（新增文件无错误）
✅ 生产构建成功（31.69s）
✅ 组件类型定义正确

## API 端点清单

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/demand/comparison` | GET | 需量配置对比 |
| `/v1/demand/curve-mini` | GET | 迷你需量曲线（6/12月）|
| `/v1/demand/load-period` | GET | 24小时负荷时段分布 |
| `/v1/demand/power-factor-trend` | GET | 功率因数趋势（30天）|

## 数据流

```
用户打开节能机会详情
  ↓
根据 source_plugin 确定 simulationType
  ↓
加载对应嵌入式组件
  ↓
组件调用 demand API 获取数据
  ↓
展示分析图表 + 模拟参数表单
  ↓
用户调整参数 → 模拟 → 选择设备 → 确认执行
```

## 部署建议

### 数据库迁移
当前使用 Mock 数据，生产环境需要：
1. 确保 MeterPoint 表有数据
2. PowerCurveData 表有历史曲线
3. PricingConfig 表配置电价
4. DemandHistory 表记录历史需量

### 前端部署
```bash
cd frontend
npm install
npm run build
# 构建产物在 dist/ 目录
```

### 后端部署
```bash
cd backend
# 确保依赖已安装
python -m app.main
# 或使用 uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 后续优化建议

1. **性能优化**
   - 前端 chunk 分割（目前有2.5MB大chunk）
   - API 响应缓存（Redis）
   - 图表懒加载

2. **功能增强**
   - 添加功率因数分析组件
   - HVAC 能耗曲线组件
   - 更多嵌入式组件类型

3. **用户体验**
   - 参数验证提示
   - 模拟结果对比
   - 历史方案回顾

4. **测试覆盖**
   - 单元测试（组件、API）
   - 集成测试（端到端）
   - 性能测试

## 文件清单

### 新建文件 (5个)
- `backend/app/api/v1/demand.py`
- `frontend/src/api/modules/demand.ts`
- `frontend/src/components/demand/DemandComparisonCard.vue`
- `frontend/src/components/demand/DemandCurveMini.vue`
- `frontend/src/components/demand/LoadPeriodChart.vue`
- `frontend/src/components/demand/index.ts`

### 修改文件 (4个)
- `backend/app/api/v1/__init__.py`
- `backend/app/schemas/energy.py`
- `backend/app/api/v1/opportunities.py`
- `frontend/src/api/modules/opportunities.ts`
- `frontend/src/components/energy/OpportunityDetailPanel.vue`

## 总结

本次实现成功整合了需量板块与节能中心，通过：
- **清晰的架构设计**：模块职责明确，避免耦合
- **灵活的类型系统**：8种方案类型，可扩展
- **可复用的组件**：嵌入式图表组件可用于多处
- **完整的数据流**：从分析到执行的闭环

实现遵循了 YAGNI 原则，只实现必需功能，为未来扩展预留了接口。
