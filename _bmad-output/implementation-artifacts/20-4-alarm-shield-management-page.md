# Story 20.4: 告警屏蔽管理页

## Story

**As a** 系统管理员,
**I want to** 在独立的告警屏蔽页面通过日历视图管理屏蔽策略，支持按区域和设备类型批量屏蔽,
**So that** 我可以在设备维护、系统升级等场景下临时屏蔽告警。

## 状态: 就绪

## 验收标准 (AC)

### AC 1: 页面路由与布局
- [x] 路由: `/strategy/alarm-rules/shield`
- [x] 替换现有 PlaceholderView 组件
- [x] 顶部: 统计卡片行（总策略数、活跃、计划中、已过期）
- [x] 中部: 日历/时间线视图，显示当前活跃和计划中的屏蔽策略
- [x] 底部: 屏蔽策略列表表格

### AC 2: 日历时间线视图
- [x] 使用 ECharts 自定义图表渲染时间线
- [x] 不同屏蔽范围用不同颜色区分（全局/区域/设备类型/特定设备）
- [x] 显示活跃和计划中的策略
- [x] 已过期策略不在时间线上显示

### AC 3: 屏蔽策略列表
- [x] 列: 策略名、屏蔽范围、屏蔽时段(起止)、屏蔽告警级别、状态、创建者
- [x] 状态: 活跃(绿色)/已过期(灰色)/计划中(蓝色)
- [x] 分页支持
- [x] 筛选: 按状态、屏蔽范围

### AC 4: 添加屏蔽策略
- [x] 屏蔽范围选择: 全局 / 按区域 / 按设备类型 / 按特定设备
- [x] 按区域批量屏蔽（选择区域，屏蔽该区域所有设备告警）
- [x] 按设备类型批量屏蔽（如屏蔽所有空调告警）
- [x] 按特定设备屏蔽
- [x] 配置屏蔽时段（开始时间、结束时间，支持"立即生效"或"定时"）
- [x] 选择屏蔽告警级别（多选: 提示/次要/重要/紧急）
- [x] 屏蔽原因填写

### AC 5: 策略生命周期管理
- [x] 过期屏蔽策略自动标记为"已过期"（前端计算）
- [x] 支持提前终止活跃屏蔽策略
- [x] 支持编辑计划中的策略
- [x] 支持删除策略

### AC 6: 2.5D 视觉增强
- [x] 使用 `@use '@/styles/_mixins-25d' as d25` 引入 mixin
- [x] 页面级使用 `page-list` preset
- [x] 统计卡片弧形倾斜效果

## 技术设计

### 数据模型
现有 API `AlarmShieldInfo` 字段有限（point_id, alarm_level, start_time, end_time, reason, status）。
前端扩展屏蔽范围概念：
- `scope`: 'global' | 'area' | 'device_type' | 'device' — 存储在 reason 字段 JSON 中
- `scope_value`: 具体区域/设备类型/设备ID — 同上

### API 复用
- `getAlarmShields` — 获取屏蔽列表
- `createAlarmShield` — 创建屏蔽
- `deleteAlarmShield` — 删除屏蔽
- `getPointList` — 获取点位（用于设备选择）
- `getDeviceList` — 获取设备列表

### 状态计算（前端）
```typescript
function computeStatus(shield: AlarmShieldInfo): 'active' | 'expired' | 'scheduled' {
  const now = new Date()
  const start = new Date(shield.start_time)
  const end = new Date(shield.end_time)
  if (now > end) return 'expired'
  if (now < start) return 'scheduled'
  return 'active'
}
```

### 文件变更
| 文件 | 操作 |
|------|------|
| `frontend/src/views/alarm/shield.vue` | 替换 PlaceholderView |

## 对抗性审查记录

### 审查发现
1. **API 字段限制**: 现有 `AlarmShieldCreateParams` 只有 `point_id`, `alarm_level`, `start_time`, `end_time`, `reason`。屏蔽范围（全局/区域/设备类型）需要编码到 `reason` 字段中（JSON 格式），前端解析。
2. **批量屏蔽**: 按区域/设备类型批量屏蔽时，需为每个匹配的点位创建独立屏蔽记录，或使用全局屏蔽（point_id=null）+ reason 中标记范围。选择后者以减少 API 调用。
3. **多告警级别**: API 只支持单个 `alarm_level`，多级别屏蔽需创建多条记录或使用 null（屏蔽所有级别）。选择 null + reason 中记录级别列表。

### 审查结论
- 风险可控，通过 reason 字段 JSON 编码扩展信息
- 不修改后端 API，纯前端实现
- 状态计算在前端完成，无需后端支持
