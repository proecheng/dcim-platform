# Story 20.2: 复合规则配置页

## Story

**As a** 系统管理员,
**I want to** 在独立的复合规则页面通过可视化编辑器配置多条件复合告警规则，并预览规则触发效果,
**So that** 我可以创建更精确的告警规则，减少单一阈值判断带来的误报。

## 状态

- **状态**: 已完成
- **优先级**: 高
- **估算**: 5 Story Points
- **Sprint**: 20 - 告警策略管理

## 验收标准 (AC)

### AC1: 页面路由与基础布局
- **Given** 用户导航到 `/strategy/alarm-rules/compound`
- **When** 页面加载完成
- **Then** 显示复合规则列表页面，包含统计卡片、筛选工具栏、规则表格
- **And** 页面使用 2.5D 视觉增强样式

### AC2: 复合规则列表表格
- **Given** 页面已加载
- **When** 数据加载完成
- **Then** 表格显示列: 规则名、条件数、逻辑关系(AND/OR)、关联设备、启用状态、最后触发时间
- **And** 支持分页、筛选（逻辑关系、启用状态）

### AC3: 条件编辑器 — 添加/编辑规则
- **Given** 用户点击"新增规则"或"编辑"按钮
- **When** 对话框打开
- **Then** 显示条件编辑器表单:
  - 规则基本信息（名称、告警级别、告警消息）
  - 顶层逻辑关系选择（AND/OR 下拉）
  - 条件行列表，每行: 点位选择 → 比较运算符(>, <, =, >=, <=) → 阈值输入
  - 支持添加/删除条件行
  - 支持嵌套条件组（组内可再添加条件行，组有独立的 AND/OR 逻辑）

### AC4: 规则测试预览
- **Given** 用户在条件编辑器中配置了规则
- **When** 用户在底部"规则测试"区域输入模拟点位值
- **Then** 纯前端 JavaScript 实时计算并显示触发结果（触发/未触发）
- **And** 每个条件行显示单独的匹配状态

### AC5: 规则 CRUD 操作
- **Given** 用户在列表页面
- **When** 执行新增/编辑/删除/启用/禁用操作
- **Then** 调用后端 API (`/v1/alarms/rules`) 完成操作
- **And** 操作成功后刷新列表

## 技术设计

### 条件树数据结构

```typescript
// 条件节点 — 叶子节点
interface ConditionItem {
  id: string              // 前端唯一标识 (crypto.randomUUID)
  type: 'condition'
  pointId: number | undefined
  pointName: string
  operator: '>' | '<' | '=' | '>=' | '<='
  threshold: number | undefined
}

// 条件组 — 分支节点
interface ConditionGroup {
  id: string
  type: 'group'
  logic: 'AND' | 'OR'
  children: (ConditionItem | ConditionGroup)[]
}

// 规则表单
interface CompoundRuleForm {
  ruleName: string
  alarmLevel: 'critical' | 'major' | 'minor' | 'info'
  alarmMessage: string
  rootGroup: ConditionGroup   // 顶层条件组
}
```

### 规则测试引擎（纯前端）

```typescript
function evaluateGroup(group: ConditionGroup, values: Record<number, number>): boolean {
  const results = group.children.map(child => {
    if (child.type === 'condition') {
      return evaluateCondition(child, values)
    }
    return evaluateGroup(child, values)
  })
  return group.logic === 'AND'
    ? results.every(Boolean)
    : results.some(Boolean)
}
```

### 序列化 — 与后端 `condition_expr` 字段对接

规则保存时将条件树序列化为 JSON 字符串存入 `condition_expr`，加载时反序列化。

### 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `frontend/src/views/alarm/compound.vue` | 替换 | 完整实现复合规则配置页 |

### 不变更

- 不修改 router/index.ts（路由已存在）
- 不修改后端代码
- 不修改其他已有页面

## 对抗性审查记录

### 审查问题

1. **条件树深度限制**: 嵌套条件组无限递归可能导致 UI 崩溃
   - **缓解**: 限制最大嵌套深度为 3 层，UI 上禁用超深嵌套的"添加子组"按钮

2. **条件编辑器性能**: 大量条件行可能导致渲染卡顿
   - **缓解**: 单个规则条件数限制为 20 条，实际业务场景不会超过 10 条

3. **规则测试引擎边界**: 点位值未填写时的处理
   - **缓解**: 未填写值的条件标记为"未评估"，不参与逻辑运算

4. **condition_expr 兼容性**: 后端 AlarmRuleInfo 的 condition_expr 是 string | null
   - **缓解**: 保存时 JSON.stringify 条件树，加载时 JSON.parse，null 时初始化空条件组

5. **点位选择器数据量**: 点位可能很多
   - **缓解**: 使用 filterable el-select，加载前 100 个点位（与 thresholds.vue 一致）

## 任务分解

- [x] T1: 创建 Story 文件
- [x] T2: 对抗性审查
- [x] T3: 实现 compound.vue — 列表表格 + 统计卡片
- [x] T4: 实现条件编辑器对话框（条件行 + 嵌套组）— CompoundConditionGroup.vue 递归组件
- [x] T5: 实现前端规则测试预览引擎
- [x] T6: lsp_diagnostics 验证 — 两个文件均无错误
