# Story 29.6: 前端温度预测曲线展示

Status: done

## Story

As a 运维人员,
I want 在制冷管理页面查看每个区域的实时温度预测曲线,
So that 我能直观了解温度趋势并做出决策。

## 依赖

- Story 29.4（预测 API）— done
- Story 29.5（精度验证）— done

## Acceptance Criteria

1. Given 后端预冷 API 已就绪（`/api/v1/precool/*`）
   When 前端需要调用预冷相关接口
   Then 创建 `frontend/src/api/modules/precool.ts` 封装以下 API:
   - `predictTemperature(zoneId, data)` → `POST /v1/precool/zones/{zone_id}/predict`（`data` 仅需 `{ hours: number }`，后端自动获取当前温度和功率数据）
   - `getValidationReport(zoneId)` → `GET /v1/precool/zones/{zone_id}/validation`
   - `getThermalParameters(zoneId, params)` → `GET /v1/precool/zones/{zone_id}/parameters`
   - `getDashboard()` → `GET /v1/precool/dashboard`
   - 类型定义: `PredictRequest`, `PredictResponse`, `ValidationReport`, `DashboardZone`, `DashboardResponse`
   - 遵循项目现有 API 模块模式（`import request from '@/utils/request'`）
   - API 响应解包: axios 拦截器已做 `response.data` 解包，前端收到 `{code, message, data}`，需用 `res.data` 获取实际数据

2. Given 预测 API 可正常返回温度轨迹数据
   When 用户访问温度预测图表组件
   Then 创建 `frontend/src/components/energy/TemperaturePredictionChart.vue`:
   - 接收 props: `zoneId: number`, `zoneName?: string`
   - 使用 ECharts 直接渲染（参考项目 `LineChart.vue` 的初始化/销毁/resize 模式）
   - 图表内容:
     - X 轴: 时间步（从 API 返回的 `time_steps` 数组）
     - Y 轴: 温度 °C
     - 当前温度标注: API 返回的 `current_temp` 字段，在 t=0 位置用 `markPoint` 标注（标注为 "当前温度"）
     - 虚线: 预测温度轨迹（`temperature_trajectory`）
     - ASHRAE 参考线: 18°C 下限（蓝色虚线）和 27°C 上限（红色虚线），使用 `markLine`
     - 误差带: 预测曲线 ± 误差范围的半透明区域（使用 ECharts `areaStyle` 的上下界 band）
   - 误差带逻辑:
     - 调用 `getValidationReport(zoneId)` 获取 `mae_1h`
     - `error_band = max(mae_1h ?? 2.0, 1.0)`（无数据时默认 2°C，最小 1°C）
     - 误差带颜色: mae_1h 为 null 时默认黄色（精度未知）, mae_1h < 1.0 绿色, 1.0-2.0 黄色, > 2.0 红色（半透明）
   - 预测范围切换: 顶部按钮组 `0.5h / 1h / 2h`，切换时重新调用预测 API（`hours` 参数）
   - 模型模式标签: 显示 `model_version`（TCL-v1 / THM-fallback）
   - 自动刷新: 每 60 秒自动重新请求预测数据，组件销毁时清除定时器
   - 加载状态: 预测请求期间显示 `v-loading`
   - 错误处理: API 失败时显示 `el-empty` 占位

3. Given 温度预测组件已创建
   When 用户访问制冷状态监控页面
   Then 在 `CoolingLinkageMonitor.vue` 底部新增一行卡片:
   - 标题: "温度预测"
   - 内容: 使用 `<TemperaturePredictionChart>` 组件
   - zone 选择: 如果有多个制冷区域，显示 `el-select` 选择 zone（调用 `getDashboard()` 获取 zone 列表）
   - 默认选中第一个 zone

## 涉及文件

- 新建 `frontend/src/api/modules/precool.ts` — 预冷 API 封装
- 新建 `frontend/src/components/energy/TemperaturePredictionChart.vue` — 温度预测图表组件
- 修改 `frontend/src/views/energy/shift/CoolingLinkageMonitor.vue` — 集成预测图表

## 技术说明

- ECharts 导入: 新组件使用 `import echarts, { type EChartsOption } from '@/utils/echarts'`（项目封装）。注意: 现有 `CoolingLinkageMonitor.vue` 使用全量导入 `import * as echarts from 'echarts'`，集成时保持现有页面导入方式不变
- 请求工具: `import request from '@/utils/request'`（已配置 baseURL + JWT 拦截）
- 组件模式: Vue 3 `<script setup lang="ts">` + `defineProps` + `withDefaults`
- 自动导入: `ref`, `computed`, `onMounted`, `onUnmounted`, `watch` 等无需手动 import
- ECharts resize: 使用 `@vueuse/core` 的 `useDebounceFn` 防抖
- 误差带实现: 使用 stacked area band 技术（项目 `echarts.ts` 未注册 `CustomChart`，禁止使用 `custom` series）:
  - 下界 series: `data = trajectory[i] - error_band`，`areaStyle` 透明，`lineStyle` 透明，`symbol: 'none'`，`stack: 'errorBand'`
  - 上界 series: `data = 2 * error_band`（差值，非绝对值），`areaStyle` 带颜色半透明，`lineStyle` 透明，`symbol: 'none'`，`stack: 'errorBand'`
- ASHRAE markLine 示例: `{ yAxis: 27, name: 'ASHRAE 上限', lineStyle: { type: 'dashed', color: '#f56c6c' } }`
- 项目统一组件: `el-card`, `el-button-group`, `el-select`, `el-empty`, `v-loading` 等 Element Plus 组件

## Tasks

- [x] 1. 创建预冷 API 模块 (`frontend/src/api/modules/precool.ts`)
- [x] 2. 创建温度预测图表组件 (`frontend/src/components/energy/TemperaturePredictionChart.vue`)
- [x] 3. 集成到制冷监控页面 (`CoolingLinkageMonitor.vue`)
- [x] 4. 构建验证 (`npm run build` + `npm run typecheck`) — 通过，无新增错误
