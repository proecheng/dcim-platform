# Story 19.2: 消防联动可视化页

## Story 描述

**As a** 运维工程师,
**I want to** 在消防联动页面查看所有联动策略的配置状态和历史执行记录，并通过可视化时间线回顾联动事件的完整处理过程,
**So that** 我可以确认联动策略配置正确，并在事后高效回顾火灾事件的完整处置链路。

## 状态: 就绪

## 验收标准 (AC)

### AC-1: 页面路由
- 页面路由: `/security/fire-linkage`（已注册，当前为 PlaceholderView）
- 替换 PlaceholderView 为完整实现
- 不修改 `router/index.ts`

### AC-2: 顶部统计卡片
- 显示 4 个统计卡片: 联动策略总数、已启用数、最近30天触发次数、平均响应时间(ms)
- 数据来源:
  - 策略总数/已启用数: `getLinkagePolicies()` 返回的 total 和 is_enabled 过滤
  - 30天触发次数: `getLinkageExecutions({ start_time: 30天前 })` 返回的 total
  - 平均响应时间: 从执行记录的 `total_duration_ms` 计算平均值
- 使用 `stat-card` 模式（与 access-control.vue 一致）
- 2.5D 弧形倾斜效果

### AC-3: 策略配置区域 — 策略列表
- 消防联动策略列表，使用 `el-collapse` 或自定义可展开卡片
- 每个策略显示:
  - 名称
  - 触发条件: 根据 `trigger_type` 显示（单传感器预警 / 多传感器联动）
  - 联动动作数: `actions.length`
  - 启用状态: `el-switch` 或 `el-tag`
- 分级联动颜色区分:
  - 预警级（priority === 'low' 或 trigger_type 含 'warning'）: 黄色边框/标签
  - 联动级（priority === 'high' 或 trigger_type 含 'alarm'）: 红色边框/标签
- 数据来源: `getLinkagePolicies()` API

### AC-4: 联动动作链可视化（水平流程图）
- 点击策略展开后显示水平流程图
- 流程: 触发条件 → 动作1 → 动作2 → ... → 通知
- 每个动作节点显示:
  - 动作类型图标（关空调/开门禁/切电源/启排烟/开照明/启视频/通知）
  - 目标设备（从 `action_config` 提取）
  - 预期响应时间（`timeout_seconds`）
- 节点间用箭头连线（CSS 实现）
- 预警级策略: 仅显示通知+视频节点（黄色主题）
- 联动级策略: 显示全部动作节点（红色主题）
- 纯 CSS/HTML 实现，不依赖第三方图表库

### AC-5: 执行历史区域 — 历史列表
- 联动执行历史列表，使用 `el-table` 展示
- 每条记录显示:
  - 触发时间: `started_at`
  - 触发源: `trigger_source`（传感器名）
  - 联动级别: 根据关联策略的 priority 判断（预警/联动）
  - 执行结果: `status`（completed=全部成功 / partial_failure=部分失败 / failed=失败）
  - 持续时间: `total_duration_ms` 格式化
- 支持分页
- 数据来源: `getLinkageExecutions()` API

### AC-6: 事件时间线（纵向）
- 点击历史记录展开事件时间线
- 使用 `el-timeline` 纵向展示从检测到恢复的完整链路
- 每个节点显示:
  - 时间戳（精确到毫秒）
  - 动作描述（action_type 中文映射）
  - 执行结果: 成功 ✓ / 失败 ✗
  - 耗时: `duration_ms`
- 失败动作节点: 红色高亮 + 显示 `error_message`
- 数据来源: `getLinkageExecution(id)` 返回的 logs 数组
- 时间线底部显示恢复状态:
  - 查询 `getRecoveries({ execution_id })` 获取恢复记录
  - 显示: 已恢复/待恢复/恢复中
  - 各恢复步骤进度（从 recovery.logs 获取）

### AC-7: 2.5D 视觉增强
- 使用 `@use '@/styles/mixins-25d' as *` 引入 2.5D mixin
- `page-dashboard` preset 应用于页面容器（4 个统计卡片用 `$card-count: 4`）
- 策略配置区和执行历史区使用景深差效果
- 与安防模块其他页面视觉风格一致

### AC-8: 数据刷新
- 页面加载时自动获取策略列表和执行历史
- 10 秒轮询刷新统计数据
- 组件卸载时清理定时器

## 技术任务

### Task 1: 创建 composable — `useFireLinkageData.ts` [AC-2, AC-3, AC-5, AC-8]
- 路径: `frontend/src/composables/useFireLinkageData.ts`
- 封装:
  - 策略列表获取与统计计算
  - 执行历史获取与分页
  - 执行详情（含日志）获取
  - 恢复记录获取
  - 轮询刷新逻辑
- 使用已有 API: `getLinkagePolicies`, `getLinkageExecutions`, `getLinkageExecution`, `getRecoveries`
- 导出类型和辅助函数

### Task 2: 实现 `fire-linkage.vue` 页面 [AC-1 ~ AC-7]
- 路径: `frontend/src/views/security/fire-linkage.vue`
- 替换当前 PlaceholderView
- 布局:
  - 顶部: 4 个统计卡片（el-row + el-col）
  - 中部: 策略配置区（可展开卡片列表 + 动作链流程图）
  - 底部: 执行历史区（el-table + 可展开时间线）
- 动作链流程图: 纯 CSS flex 布局 + 伪元素箭头连线
- 事件时间线: el-timeline 组件
- 2.5D 样式: `@use '@/styles/mixins-25d' as *`

### Task 3: 验证 [全部 AC]
- `lsp_diagnostics` 无新增错误
- 页面正确渲染，无控制台错误

## 动作类型中文映射

| action_type | 中文 | 图标建议 |
|-------------|------|----------|
| ALARM_NOTIFY | 告警通知 | Bell |
| WEBHOOK | Webhook回调 | Connection |
| MQTT_COMMAND | 设备控制 | Setting |
| VIDEO_RECORD | 视频录制 | VideoCamera |
| VIDEO_POPUP | 视频弹窗 | Monitor |
| close_hvac | 关闭空调 | WindPower (自定义) |
| open_door | 开启门禁 | Unlock |
| cut_power | 切断电源 | SwitchButton |
| start_exhaust | 启动排烟 | Promotion |
| turn_on_lights | 开启照明 | Sunny |
| start_video | 启动视频 | VideoCamera |

## 依赖

- 已有 API 模块: `frontend/src/api/modules/linkage.ts`（无需修改）
- 已有类型: `LinkagePolicy`, `LinkageAction`, `LinkageExecution`, `LinkageLog`, `LinkageRecovery`
- 已有 2.5D mixin: `frontend/src/styles/_mixins-25d.scss`
- 参考页面: `frontend/src/views/security/access-control.vue`

## 不做的事

- 不修改后端代码
- 不修改 `router/index.ts`
- 不修改 `sprint-status.yaml`
- 不修改已有页面
- 不使用 `as any` 或 `@ts-ignore`
