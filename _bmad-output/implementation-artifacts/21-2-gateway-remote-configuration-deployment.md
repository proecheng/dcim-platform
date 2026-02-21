# Story 21.2: 网关远程配置下发

## 状态: 就绪

## Story

作为系统管理员，
我希望能够远程向网关推送配置变更，并查看配置下发状态和历史记录，
以便集中管理网关配置，无需物理接触设备。

## 验收标准 (AC)

### AC 21.2.1 — 配置下发操作入口
- 在网关管理页面表格中，每行增加"配置下发"操作按钮
- 按钮仅对在线且启用的网关可用，离线/禁用网关按钮置灰并提示原因
- 支持表格多选 + 批量配置下发按钮

### AC 21.2.2 — 配置下发对话框
- 点击"配置下发"后弹出对话框
- 对话框显示当前网关配置信息（采集周期、协议参数、数据上报间隔等）
- 配置参数可编辑修改
- 提交后调用 `POST /v1/gateways/{id}/push-config` API

### AC 21.2.3 — 配置下发状态展示
- 下发后实时显示状态：下发中(pending) / 已生效(delivered) / 下发失败(failed)
- 状态使用不同颜色标签区分
- 下发失败时显示失败原因和重试按钮

### AC 21.2.4 — 配置下发历史记录
- 对话框内含"历史记录"标签页
- 调用 `GET /v1/gateways/{id}/config-history` 获取历史
- 列表展示：下发时间、配置快照摘要、下发结果、错误信息
- 支持分页

### AC 21.2.5 — 批量配置下发
- 表格支持多选（checkbox）
- 选中多个网关后，顶部出现"批量配置下发"按钮
- 批量下发逐个调用 API，显示整体进度
- 完成后汇总成功/失败数量

### AC 21.2.6 — 2.5D 视觉增强
- 对话框使用项目统一的暗色主题样式
- 配置表单区域应用 `form-depth` mixin 效果
- 状态标签使用项目统一的颜色变量

## 技术方案

### 架构决策
- 创建独立子组件 `GatewayConfigDialog.vue`，通过 props/emits 与父组件通信
- 不修改后端代码，仅消费已有 API
- 不修改路由配置

### 前端变更

#### 新增文件
- `frontend/src/views/gateway/GatewayConfigDialog.vue` — 配置下发对话框组件

#### 修改文件
- `frontend/src/views/gateway/index.vue` — 添加操作列、多选、批量按钮、引入子组件
- `frontend/src/api/modules/gateway.ts` — 添加配置下发和历史记录 API 函数

### API 依赖（已实现）
| 端点 | 方法 | 用途 |
|------|------|------|
| `/v1/gateways/{id}/push-config` | POST | 下发配置 |
| `/v1/gateways/{id}/config-history` | GET | 配置历史 |
| `/v1/gateways/{id}` | GET | 网关详情 |

### 数据模型
```typescript
// ConfigPushResponse — 下发响应
interface ConfigPushResponse {
  id: number
  gateway_id: string
  status: 'pending' | 'delivered' | 'failed'
  error_message: string | null
  created_at: string | null
}

// ConfigPushRecord — 历史记录
interface ConfigPushRecord {
  id: number
  gateway_id: string
  config_snapshot: Record<string, unknown>
  status: string
  error_message: string | null
  created_at: string | null
  updated_at: string | null
}
```

## 任务分解

### Task 1: 扩展 gateway API 模块
- 在 `gateway.ts` 中添加 `pushGatewayConfig` 和 `getConfigHistory` 函数
- 添加 `ConfigPushResponse` 和 `ConfigPushRecord` 类型定义

### Task 2: 创建 GatewayConfigDialog.vue 子组件
- 双标签页：配置下发 / 历史记录
- 配置下发表单（只读展示 + 下发按钮）
- 历史记录表格 + 分页
- 状态标签（pending/delivered/failed）
- 失败重试按钮

### Task 3: 集成到 gateway/index.vue
- 添加操作列（配置下发按钮）
- 添加多选列（el-table-column type="selection"）
- 添加批量配置下发按钮和逻辑
- 引入 GatewayConfigDialog 组件

### Task 4: 2.5D 视觉增强
- 对话框暗色主题样式
- 应用 mixins-25d 效果

### Task 5: 验证
- lsp_diagnostics 无新增错误
- 代码审查

## 对抗性审查记录

### 审查发现
1. **API 契约匹配** — 后端 `push-config` 不接受请求体参数，仅触发配置构建和下发。前端不应提供"修改配置"表单，而是展示当前配置 + 一键下发。
2. **批量下发并发控制** — 需要串行或限制并发，避免同时大量请求导致 MQTT 拥塞。
3. **离线网关处理** — 后端会返回 503（MQTT 未连接），前端需优雅处理。

### 审查结论
Story 可执行。上述发现已纳入实现方案。
