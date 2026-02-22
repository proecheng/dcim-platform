# Epic 23 回顾：大屏增强与能源 OCR

## 完成情况

全部 3 个 Story 完成。本 Epic 涵盖两个不同领域：大屏 3D 可视化增强和能源管理 OCR 功能。

| Story | 标题 | 核心特性 | 涉及层 | 前端构建 |
|-------|------|---------|--------|---------|
| 23-1 | 大屏设备历史数据弹窗 | ECharts 趋势图 + 阈值线 + 时间范围切换 | 纯前端 | ✅ |
| 23-2 | 大屏3D楼层场景加载 | Three.js 程序化生成机柜 + 状态着色 + WebGL 降级 | 纯前端 | ✅ |
| 23-3 | 电费单OCR识别 | 后端 OCR 服务 + 前端确认对话框 + 自动填充 | 前后端 | ✅ |

**优先级：** P3

## 关键经验教训

### 唯一涉及后端改动的 Phase 2 Epic

- 23.3 是 Epic 18-23 中唯一需要修改后端代码的 Story。
- 新增文件：`backend/app/services/ocr_service.py`（OCR 服务层）、`energy.py` 新增 OCR 端点、`schemas/energy.py` 新增类型。
- 其余 14 个 Story 全部是纯前端改动，说明 Epic 1-17 的后端基础设施非常完善。

### Three.js 程序化生成

- 23.2 完全用 Three.js 基础几何体（BoxGeometry、PlaneGeometry）程序化生成机柜场景，不加载外部 3D 模型文件。
- 优点：避免模型文件管理复杂度，机房布局变化时只需修改参数。
- 标准 42U 机柜比例（0.6m×1.2m×2.0m），冷热通道用半透明平面区分。
- 内存管理关键：Three.js 对象必须在 `onUnmounted` 中手动 dispose，否则切换楼层会导致内存泄漏。

### 多层降级策略

- **23.2 WebGL 降级**：浏览器不支持 WebGL 时自动回退到 2D 平面图模式。
- **23.2 数据降级**：无空间拓扑数据时使用默认 4×10 机柜布局作为演示。
- **23.3 OCR 降级**：PaddleOCR 不可用时 mock 返回国家电网标准五时段电价示例数据（confidence=85）。
- **23.3 识别失败降级**：OCR 失败时提示"识别失败，请手动输入"，不阻塞正常流程。
- 降级策略是本 Epic 的设计亮点，确保功能在各种环境下都能使用。

### deviceId 类型不匹配

- 23.1 审查发现大屏模块使用 string 类型 deviceId（如 "A-01"），但标准后端 API 需要 number 类型 id。
- 缓解方案：通过 `getDeviceList({ keyword: deviceId })` 查找对应数字 id，或使用 store 中的设备数据作为 fallback。
- 这反映了大屏模块与标准模块之间的数据模型差异，是历史遗留问题。

### 子组件拆分模式延续

- 23.1 创建 `BigscreenHistoryDialog.vue`，23.2 创建 `BigscreenFloor3D.vue`，均放在 `components/bigscreen/` 目录。
- 最小化修改 `bigscreen/index.vue`，保持主页面代码稳定。
- 与 Epic 21 的 `GatewayConfigDialog.vue` 一致，复杂功能拆为独立子组件是正确的模式。

### OCR 服务 MVP 策略

- 23.3 的 OCR 服务采用渐进式实现：尝试导入 PaddleOCR → 不可用则 mock 降级。
- MVP 阶段支持国家电网、南方电网标准格式，其他格式整体置信度低于 60% 时提示不支持。
- 前端确认对话框（左图右数据）允许用户手动修正识别结果，低置信度字段黄色高亮。

## 待改进项

- **OCR mock 需标注 TODO**：`ocr_service.py` 的 mock 模式需要明确标注，后续集成真实 OCR 引擎（PaddleOCR 或云 API）。
- **deviceId 类型统一**：大屏模块的 string deviceId 与标准 API 的 number id 不一致，长期应统一数据模型。
- **Three.js 内存管理**：确保 `BigscreenFloor3D.vue` 的 `onUnmounted` 正确 dispose 所有 Three.js 对象。

## 行动项

| 行动 | 负责人 | 优先级 |
|------|--------|--------|
| 在 ocr_service.py 中明确标注 mock TODO 和生产集成计划 | Dev Team | 中 |
| 评估大屏 deviceId 类型统一方案 | Dev Team | 低（可选） |
