# Story 20.3: 升级规则管理页

## Story

**As a** 系统管理员,
**I want to** 通过可视化界面在独立的升级规则页面配置告警超时升级链,
**So that** 我可以确保重要告警在未及时处理时自动升级通知到上级主管。

## 状态: 就绪开发

## 上下文

本页面属于 Epic 20（告警策略配置 UI）的第三个 Story，与已完成的 `thresholds.vue`（阈值配置）和 `compound.vue`（复合规则）同属告警策略子系统。当前 `escalation.vue` 为 PlaceholderView 占位，需替换为完整功能页面。

### 技术上下文
- 路由已注册: `/strategy/alarm-rules/escalation` → `@/views/alarm/escalation.vue`
- 后端 API 已就绪: `GET/POST/PUT/DELETE /v1/escalations`，含 toggle 端点
- 前端 API 模块已就绪: `@/api/modules/alarm.ts` 中 `getEscalations`、`createEscalation`、`updateEscalation`、`deleteEscalation`、`toggleEscalation`
- 类型定义已就绪: `AlarmEscalationInfo`、`AlarmEscalationCreateParams`、`AlarmEscalationUpdateParams`
- 用户列表 API: `getUserList` from `@/api/modules/user.ts`

### 已有 API 数据结构

```typescript
interface AlarmEscalationInfo {
  id: number
  rule_name: string
  source_level: string        // 源告警级别
  timeout_minutes: number     // 超时分钟数
  target_level: string        // 目标升级级别
  notify_user_ids: number[]   // 通知人 ID 列表
  is_enabled: boolean
  description: string | null
  created_at: string | null
  updated_at: string | null
}
```

### 设计约束
- 遵循 `thresholds.vue` / `compound.vue` 的页面结构模式（统计卡片 → 工具栏 → 表格 → 对话框）
- 使用 `@use '@/styles/_mixins-25d' as d25` + `@include d25.page-list` 实现 2.5D 视觉增强
- Vue 3 `<script setup lang="ts">` + 自动导入（ref/reactive/computed/onMounted/ElMessage/ElMessageBox 无需手动 import）
- Element Plus 组件无需手动 import

## 验收标准

### AC1: 升级规则列表展示
- [ ] 页面顶部显示统计卡片：总规则数、已启用、已禁用、告警级别数
- [ ] 表格列：规则名称、适用告警级别（source_level）、超时时间、目标升级级别、通知人数、启用状态、操作
- [ ] 支持按告警级别筛选、按启用状态筛选
- [ ] 分页组件，支持切换每页条数

### AC2: 升级规则 CRUD
- [ ] 点击「新增升级规则」打开对话框
- [ ] 表单字段：规则名称（必填）、源告警级别（select）、超时时间（分钟，InputNumber）、目标升级级别（select）、通知人（多选）、描述
- [ ] 编辑时回填已有数据
- [ ] 删除前弹出确认框
- [ ] 启用/禁用通过 Switch 切换，调用 toggleEscalation API

### AC3: 升级链编辑器（纵向列表表单）
- [ ] 对话框内以纵向列表展示升级链节点
- [ ] 每个节点显示：序号、超时时间输入（分钟）、通知方式选择（站内信/邮件/短信）、通知人选择（多选用户）、告警级别升级开关
- [ ] 支持「添加节点」按钮在底部追加新节点
- [ ] 支持「删除」按钮移除节点
- [ ] 支持上下箭头调整节点顺序
- [ ] 节点数据序列化为 JSON 存储在 description 字段（升级链配置）

### AC4: 2.5D 视觉增强
- [ ] 使用 `@include d25.page-list` 应用页面级 2.5D 效果
- [ ] 统计卡片使用与 thresholds/compound 一致的样式模式

### AC5: 按告警级别配置不同升级链
- [ ] 源告警级别选择支持：提示/次要/重要/紧急
- [ ] 不同级别可配置不同的超时时间和升级目标

## 技术实现说明

### 文件变更
| 文件 | 操作 | 说明 |
|------|------|------|
| `frontend/src/views/alarm/escalation.vue` | 替换 | PlaceholderView → 完整升级规则管理页 |

### 不可修改文件
- `frontend/src/router/index.ts` — 路由已注册
- `frontend/src/api/modules/alarm.ts` — API 已就绪
- `backend/` — 后端不做修改

### 升级链节点数据结构

```typescript
interface EscalationNode {
  id: string                    // 唯一标识（crypto.randomUUID）
  order: number                 // 序号
  timeout_minutes: number       // 超时分钟数
  notify_method: ('internal' | 'email' | 'sms')[]  // 通知方式
  notify_user_ids: number[]     // 通知人
  upgrade_level: boolean        // 是否升级告警级别
}
```

升级链节点列表序列化为 JSON 字符串，存储在 `description` 字段中。创建/更新时，将第一个节点的 `timeout_minutes` 映射到 `AlarmEscalationCreateParams.timeout_minutes`，将所有节点的 `notify_user_ids` 合并映射到 `AlarmEscalationCreateParams.notify_user_ids`。

### 页面结构

```
统计卡片行（4列）
├── 总规则数
├── 已启用
├── 已禁用
└── 告警级别数

工具栏卡片
├── 筛选表单（告警级别、启用状态）
└── 操作按钮（新增升级规则）

表格卡片
├── 数据表格
└── 分页

编辑对话框
├── 基本信息（规则名、源级别、目标级别、描述）
└── 升级链编辑器（纵向节点列表）
    ├── 节点1: [序号] [超时] [通知方式] [通知人] [升级开关] [↑↓删除]
    ├── 节点2: ...
    └── [+ 添加节点]
```

## 任务分解

### Task 1: 页面骨架与统计卡片
- 替换 PlaceholderView
- 实现统计卡片行
- 实现工具栏（筛选 + 新增按钮）
- 实现数据表格 + 分页
- 接入 getEscalations API

### Task 2: CRUD 对话框与升级链编辑器
- 实现新增/编辑对话框
- 实现升级链纵向列表编辑器
- 节点增删、上下移动
- 表单验证
- 接入 createEscalation / updateEscalation API

### Task 3: 启用/禁用与删除
- Switch 切换调用 toggleEscalation
- 删除确认框 + deleteEscalation
- 2.5D 样式应用

## 测试建议
- 验证列表加载、分页、筛选
- 验证新增/编辑/删除流程
- 验证升级链节点增删、排序
- 验证启用/禁用切换
- 验证表单必填校验
