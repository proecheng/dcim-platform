# Story 23.1: 大屏设备历史数据弹窗

## Story

**As a** 运维工程师,
**I want to** 在大屏页面点击设备后查看历史数据趋势弹窗,
**So that** 我可以在大屏监控场景下快速了解设备运行趋势。

## 状态

- **状态**: 开发中
- **优先级**: 高
- **预估工作量**: Medium (4-6小时)

## 验收标准 (AC)

### AC 1: 触发历史数据弹窗
- **Given** 用户在大屏页面 (`/bigscreen`) 已选中一个设备
- **When** 用户点击设备详情面板中的"历史"按钮
- **Then** 弹出全屏历史数据对话框，暗色主题与大屏风格一致

### AC 2: 对话框头部信息
- **Given** 历史数据弹窗已打开
- **When** 弹窗渲染完成
- **Then** 对话框顶部显示：设备名称、设备类型、当前状态指示

### AC 3: ECharts 趋势图
- **Given** 历史数据弹窗已打开
- **When** 数据加载完成
- **Then** 核心区域显示 ECharts 趋势图，默认展示该设备所有 AI 类型点位最近24小时数据曲线

### AC 4: 时间范围切换
- **Given** 趋势图已显示
- **When** 用户点击时间范围按钮（1小时/6小时/24小时/7天）
- **Then** 趋势图重新加载对应时间范围的数据

### AC 5: 点位筛选
- **Given** 趋势图已显示多条曲线
- **When** 用户勾选/取消特定点位复选框
- **Then** 趋势图仅显示已勾选点位的曲线

### AC 6: 告警阈值线
- **Given** 点位已配置告警阈值
- **When** 趋势图渲染
- **Then** 叠加告警阈值线（虚线），超阈值区域标记半透明红色背景

### AC 7: 关闭弹窗
- **Given** 历史数据弹窗已打开
- **When** 用户按 ESC 键或点击遮罩层
- **Then** 弹窗关闭

## 技术设计

### 架构决策
- 创建独立子组件 `BigscreenHistoryDialog.vue` 放在 `components/bigscreen/` 目录
- 最小化修改 `bigscreen/index.vue`：仅替换 `handleViewHistory` + 添加组件引用
- 复用现有 API 模块：`history.ts`、`point.ts`、`threshold.ts`、`device.ts`
- 复用 ECharts 暗色主题（与 BaseChart.vue 一致）

### 数据流
1. `handleViewHistory(deviceId)` → 打开弹窗，传入 deviceId
2. 弹窗内部调用 `getDeviceDetail(deviceId)` 获取设备信息和点位列表
3. 筛选 AI 类型点位，对每个点位调用 `getPointTrend(pointId, { duration })` 获取趋势数据
4. 对每个点位调用 `getPointThresholds(pointId)` 获取阈值配置
5. 组装 ECharts option 渲染趋势图

### 涉及文件
| 文件 | 操作 | 说明 |
|------|------|------|
| `frontend/src/components/bigscreen/BigscreenHistoryDialog.vue` | 新建 | 历史数据弹窗组件 |
| `frontend/src/views/bigscreen/index.vue` | 修改 | 替换 handleViewHistory，引入弹窗 |

### API 依赖
- `GET /v1/devices/{id}/detail` — 设备详情（含点位列表）
- `GET /v1/history/{pointId}/trend` — 趋势数据
- `GET /v1/thresholds/point/{pointId}` — 点位阈值配置

## 任务分解

- [x] Task 1: 创建 BigscreenHistoryDialog.vue 子组件
- [x] Task 2: 修改 bigscreen/index.vue 集成弹窗
- [x] Task 3: lsp_diagnostics 验证
- [x] Task 4: 代码审查

## 对抗性审查记录

### 审查发现
1. **deviceId 类型不匹配**: 大屏使用 string 类型 deviceId（如 "A-01"），但后端 API 需要 number 类型 id。需要在弹窗中处理 deviceId → 数字 id 的映射，或使用设备编码查询。
   - **缓解**: 弹窗接收 string deviceId，通过 `getDeviceList({ keyword: deviceId })` 查找对应数字 id，或直接使用 store 中的设备数据作为 fallback。
2. **API 可能返回空数据**: 新部署环境可能没有历史数据。
   - **缓解**: 添加空状态提示 "暂无历史数据"。
3. **多点位并发请求**: 设备可能有多个 AI 点位，需要并发请求趋势数据。
   - **缓解**: 使用 `Promise.allSettled` 并发请求，部分失败不影响整体。

### 审查结论
需求清晰，技术方案可行。主要风险是 deviceId 类型映射，已有缓解方案。
