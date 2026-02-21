# Story 23.3: 电费单OCR识别

## Story

**As a** 能源管理员,
**I want to** 上传电费单图片后系统自动识别并提取电价信息填充配置表单,
**So that** 我不需要逐项手动输入电价数据。

## 状态

- **状态**: 开发中
- **优先级**: 高
- **预估工作量**: Medium (4-6小时)

## 验收标准 (AC)

### AC 1: 上传电费单图片
- **Given** 用户在配电配置页面(`/collection/power-config`)的电价配置区域
- **When** 点击"上传电费单识别"按钮，选择图片文件
- **Then** 支持 JPG/PNG/PDF 格式，文件大小 ≤10MB；超限时提示"文件大小不能超过10MB"

### AC 2: 后端OCR识别端点
- **Given** 前端上传图片到 `POST /api/v1/energy/ocr/bill`
- **When** 后端接收到图片
- **Then** 调用 OCR 服务识别电费单内容，返回结构化电价数据（时段名称、时段类型、起止时间、单价、生效日期）

### AC 3: 模板支持与置信度校验
- **Given** 后端 OCR 识别完成
- **When** MVP 阶段支持国家电网、南方电网标准格式
- **Then** 其他格式整体 OCR 置信度低于 60% 时返回错误提示"该电费单格式暂不支持，请手动输入"

### AC 4: 识别结果确认对话框
- **Given** OCR 识别成功返回结构化数据
- **When** 前端收到响应
- **Then** 弹出确认对话框：左侧显示原图预览，右侧显示提取的结构化数据表格，每个字段可手动修正

### AC 5: 低置信度字段高亮
- **Given** 识别结果确认对话框已显示
- **When** 某字段识别置信度低于 80%
- **Then** 该字段黄色高亮，提示用户核实

### AC 6: 确认后自动填充表单
- **Given** 用户在确认对话框中核实/修正数据
- **When** 点击"确认导入"按钮
- **Then** 逐条调用 `createPricing` API 创建电价配置，成功后刷新电价列表

### AC 7: 识别失败友好降级
- **Given** OCR 识别失败（网络错误、服务不可用、格式不支持）
- **When** 后端返回错误
- **Then** 前端显示友好错误信息"识别失败，请手动输入"，不阻塞正常流程

### AC 8: 替换占位逻辑
- **Given** 当前 `handleBillUpload` 函数为占位实现
- **When** 开发完成
- **Then** 替换为完整的上传→OCR→确认→填充流程

## 技术设计

### 架构决策
- 后端新增 OCR 路由在 `backend/app/api/v1/energy.py` 末尾追加
- 后端 OCR 服务层: `backend/app/services/ocr_service.py`（独立服务，MVP 使用模板匹配 + mock 降级）
- 前端修改 `frontend/src/views/energy/config.vue`：替换 `handleBillUpload`，新增确认对话框
- 前端新增 API 函数在 `frontend/src/api/modules/energy.ts`
- 不新增路由、不修改 router/index.ts

### 数据流
```
用户选择图片 → handleBillUpload(file)
  → 校验文件类型/大小
  → POST /api/v1/energy/ocr/bill (FormData)
  → 后端 OCR 识别 → 返回 OcrBillResult
  → 前端弹出确认对话框（左图右数据）
  → 用户确认 → 逐条 createPricing() → 刷新列表
```

### 后端 API 设计
```
POST /api/v1/energy/ocr/bill
Request: multipart/form-data { file: UploadFile }
Response: {
  code: 200,
  data: {
    success: boolean,
    confidence: number,        // 整体置信度 0-100
    provider: string,          // "国家电网" | "南方电网" | "unknown"
    items: [
      {
        pricing_name: string,
        period_type: "sharp"|"peak"|"flat"|"valley"|"deep_valley",
        start_time: string,    // "HH:MM"
        end_time: string,
        price: number,
        confidence: number,    // 字段级置信度 0-100
        effective_date: string // "YYYY-MM-DD"
      }
    ],
    raw_text?: string          // 原始 OCR 文本（调试用）
  }
}
```

### OCR 服务实现策略
- MVP: 创建 `ocr_service.py`，内部实现模板匹配逻辑
- 尝试导入 `paddleocr`，如果不可用则降级为 mock 数据（标注 TODO）
- mock 模式返回国家电网标准五时段电价示例数据，confidence=85
- 生产环境后续集成 PaddleOCR 或云 API

### 前端组件变更
- `config.vue` 新增: `ocrLoading` 状态、`ocrResult` 数据、`ocrDialogVisible` 控制
- `config.vue` 新增: `ocrPreviewUrl` 图片预览 URL
- `config.vue` 新增: 确认对话框模板（el-dialog，左右布局）
- `energy.ts` 新增: `uploadBillForOcr(file: File)` API 函数、`OcrBillResult` 类型

## 任务分解

### Task 1: 后端 OCR 服务层 [后端]
- 创建 `backend/app/services/ocr_service.py`
- 实现 `recognize_bill(file_bytes, filename)` 函数
- 尝试 PaddleOCR，不可用时 mock 降级
- 返回结构化 `OcrBillResult`

### Task 2: 后端 OCR API 端点 [后端]
- 在 `energy.py` 末尾新增 `POST /ocr/bill` 路由
- 在 `schemas/energy.py` 新增 `OcrBillItem`、`OcrBillResult` schema
- 接收 UploadFile，调用 ocr_service，返回结构化数据

### Task 3: 前端 API 函数 [前端]
- 在 `energy.ts` 新增 `OcrBillResult` 类型和 `uploadBillForOcr` 函数

### Task 4: 前端上传+确认对话框 [前端]
- 替换 `handleBillUpload` 占位逻辑
- 新增 OCR 确认对话框（左图右数据）
- 低置信度字段黄色高亮
- 确认后批量创建电价配置

## 审查清单
- [ ] 文件大小/类型校验前后端一致
- [ ] OCR 失败不阻塞正常流程
- [ ] 低置信度字段有视觉提示
- [ ] 不使用 `as any` 或 `@ts-ignore`
- [ ] 不修改 router/index.ts
- [ ] 不重写 config.vue 已有功能
