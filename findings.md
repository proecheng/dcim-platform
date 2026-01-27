# Findings & Decisions - 算力中心智能监控系统 (V3.2)

## 用电管理模块结构优化 (2026-01-26 V4.5.0)

> **目标**: 优化用电管理功能结构，使软件同时适合初学者和专家使用

### 问题发现

| 问题 | 影响 |
|------|------|
| 电费分析页面Tab过多(7个) | 用户难以找到所需功能 |
| 需量监控Tab与monitor.vue重复 | 维护成本增加 |
| 配置管理Tab与config.vue重复 | 功能冗余 |
| 节能建议独立页面 | 与电费分析割裂，用户需切换页面 |
| 初学者难以上手 | 没有简单入口，功能分散 |

### 解决方案

#### 方案1: Tab结构简化 (7→4)

| 原Tab | 处理方式 | 新Tab |
|-------|----------|-------|
| 需量监控 | 删除 | - |
| 需量曲线 + 需量配置分析 | 合并 | 需量分析 |
| 负荷转移分析 | 保留 | 负荷转移 |
| 配置管理 | 删除 | - |
| 负荷调度 + 优化报告 | 合并为子Tab | 调度与报告 |
| - | 新增 | 优化总览 |

#### 方案2: 初学者入口设计

创建"优化总览"组件，提供：
1. **一目了然的汇总统计** - 4个关键指标卡片
2. **一键操作** - 智能分析按钮
3. **重点推荐** - 高优先级建议列表
4. **快速导航** - 专家功能入口

#### 方案3: 导航菜单优化

删除"节能建议"独立入口，功能整合到：
- 电费分析 > 优化总览（简单操作）
- 节能中心（详细管理）

### 代码审查发现的P0问题

| 文件 | 问题 | 根因 | 修复 |
|------|------|------|------|
| `suggestions.vue` | 5处console.log | 开发调试遗留 | 删除 |
| `statistics.vue:421` | 逻辑错误 | 三元表达式两分支相同 | 修正为 'day':'month' |
| `energy.ts:205` | 类型定义不完整 | period_type缺少值 | 添加 sharp/flat/deep_valley |
| `execution.vue` | 未使用导入 | 代码重构遗留 | 删除 createTracking, store |
| `OptimizationOverview.vue` | Props遮蔽 | 本地ref与prop同名 | 改用emit更新父组件 |

### 类型定义修正

```typescript
// 修正前
period_type: 'peak' | 'normal' | 'valley'

// 修正后 - 完整的中国电价时段类型
period_type: 'sharp' | 'peak' | 'flat' | 'valley' | 'deep_valley'
// sharp: 尖峰  peak: 峰时  flat: 平时  valley: 谷时  deep_valley: 深谷
```

### 设计原则确认

| 原则 | 实践 |
|------|------|
| 初学者友好 | 提供"优化总览"一键入口 |
| 专家高效 | 保留深度分析功能Tab |
| 减少冗余 | 删除重复Tab，合并相似功能 |
| 导航清晰 | 菜单结构扁平化，功能聚合 |

---

## 深色主题配色全面优化 (2026-01-22 V4.2.5)

> **问题**: 系统多处界面存在白色背景和文字对比度不足的问题，影响深色主题的一致性和可读性

### 问题发现

| 界面 | 问题组件 | 具体表现 |
|------|----------|----------|
| 用电监控 | el-card | 大量卡片显示白色底色 |
| 全系统表格 | el-table | 文字偏暗，与背景色差太小 |
| 历史数据 | el-descriptions | 统计信息栏白色背景，文字看不清 |

### 根因分析

1. **Element Plus 默认浅色主题**: Element Plus 在 `:root` 中设置了 `color-scheme: light` 和白色背景变量
   - `--el-bg-color: #ffffff`
   - `--el-fill-color-blank: #ffffff`

2. **CSS 变量优先级不足**: 我们的深色样式没有完全覆盖 Element Plus 的内部变量

3. **文字亮度过低**: 原有文字颜色设置为 85% 白色，在深色背景上对比度不够

### 解决方案

#### 方案1: 强制覆盖 Element Plus 核心变量

在 `dark-tech.scss` 的 `:root` 中添加:
```scss
:root {
  color-scheme: dark;  // 关键：强制暗色模式

  --el-bg-color: #{$bg-card-solid};      // #1a2a4a
  --el-bg-color-page: #{$bg-primary};    // #0a1628
  --el-fill-color-blank: #{$bg-card-solid};
}
```

#### 方案2: 提高文字亮度

| 变量 | 原值 | 新值 | 对比度提升 |
|------|------|------|-----------|
| text-primary | 95%白 | 100%白 | +5% |
| text-regular | 85%白 | 95%白 | +10% |
| text-secondary | 65%白 | 75%白 | +10% |

#### 方案3: 组件级 !important 覆盖

对于内部使用 table/th/td 元素的组件（如 el-descriptions），需要使用 `!important` 确保覆盖:
```scss
.el-descriptions {
  th { background-color: var(--bg-tertiary) !important; }
  td { background-color: var(--bg-card-solid) !important; }
}
```

### 配色规范确认

| 用途 | 变量名 | 色值 | 说明 |
|------|--------|------|------|
| 主背景 | --bg-primary | #0a1628 | 最深，用于页面背景 |
| 次级背景 | --bg-secondary | #0d1b2a | 侧边栏等 |
| 三级背景 | --bg-tertiary | #112240 | 表头、标签列 |
| 卡片背景 | --bg-card-solid | #1a2a4a | 卡片、表格内容 |
| 主要文字 | --text-primary | #ffffff | 标题、表头 |
| 常规文字 | --text-regular | rgba(255,255,255,0.95) | 正文内容 |
| 次要文字 | --text-secondary | rgba(255,255,255,0.75) | 标签、说明 |

### 受影响组件清单

| 组件 | 修复内容 |
|------|----------|
| el-card | 实色背景 + header/body 统一 |
| el-table | 所有单元格深色 + 文字高亮 |
| el-descriptions | th/td 深色 + 带边框样式 |
| el-radio-button | 深色背景 + 选中态 |
| el-progress | 轨道深色背景 |
| el-input | 输入框深色背景 |
| el-select | 下拉框深色背景 |
| el-pagination | 文字颜色增强 |

### 验证方法

1. 打开用电监控界面 (`/energy/monitor`)，检查所有卡片背景
2. 打开历史数据界面 (`/history`)，检查统计信息栏
3. 检查任意包含表格的页面，确认文字清晰度

---

## 大屏面板导航路径修复 (2026-01-21 V4.2.1)

> **问题**: 数字孪生大屏中，点击"环境监测"面板下的组件能打开新标签页，但页面空白无内容

### 问题根因

| 组件 | 使用路径 | 实际路由 | 问题 |
|------|----------|----------|------|
| 温湿度仪表盘 | `/monitor` | 不存在 | 路由未定义 |
| 温度趋势 | `/monitor` | 不存在 | 路由未定义 |
| 温湿度概览 | `/monitor` | 不存在 | 路由未定义 |
| 实时告警 | `/alarm` | `/alarms` | 单复数拼写错误 |

### 解决方案

修正 `LeftPanel.vue` 和 `bigscreen/index.vue` 中的路由路径：

```typescript
// 修复前
navigateTo('/monitor')  // 路由不存在
navigateTo('/alarm')    // 拼写错误

// 修复后
navigateTo('/dashboard')  // 监控仪表盘
navigateTo('/alarms')     // 告警管理（复数）
```

### 大屏导航路径对照表

| 面板 | 组件 | 导航路径 | 目标页面 |
|------|------|----------|----------|
| 环境监测 | 温湿度/温度趋势 | `/dashboard` | 监控仪表盘 |
| 环境监测 | 实时告警 | `/alarms` | 告警管理 |
| 能耗统计 | 实时功率/PUE趋势 | `/energy/analysis` | 需量分析 |
| 能耗统计 | 今日用电 | `/energy/statistics` | 能耗统计 |
| 能耗统计 | 需量状态 | `/energy/topology` | 配电拓扑 |

---

## 模拟数据系统改进计划 (2026-01-20)

> **设计按需加载的模拟数据系统，支持日期动态调整和楼层可视化**
> 实施计划: `docs/plans/2026-01-20-simulation-system-improvements.md`

### 改进需求

| 需求 | 说明 |
|------|------|
| 按需加载 | 用户可在仪表盘点击按钮选择加载/卸载演示数据 |
| 加载进度 | 显示加载进度条和状态信息 |
| 日期动态调整 | 加载时自动将历史数据日期更新为最近30天 |
| 楼层平面图 | 设计B1/F1/F2/F3的2D SVG平面布局图 |
| 3D可视化 | 参照图片67-73设计3D楼宇模型 |

### 楼层平面布局设计 (参考图片67-73)

#### B1 地下制冷机房 (40m × 12.5m)
```
┌─────────────────────────────────────────────┐
│ 冷却塔区(室外): CT-1, CT-2                   │
├─────────────────────────────────────────────┤
│ 冷水机组: CH-1, CH-2   冷冻水泵: CHWP-1/2    │
│ 冷却水泵: CWP-1/2      配电柜 控制柜         │
└─────────────────────────────────────────────┘
```

#### F1/F2 机房区 (40m × 25m)
```
┌─────────────────────────────────────────────┐
│ [AC-1] [AC-2]           [AC-3] [AC-4]       │
│     冷通道                冷通道            │
│ ┌──┐┌──┐┌──┐┌──┐┌──┐   ┌──┐┌──┐┌──┐┌──┐┌──┐│
│ │01││02││03││04││05│   │11││12││13││14││15││
│ └──┘└──┘└──┘└──┘└──┘   └──┘└──┘└──┘└──┘└──┘│
│     热通道                热通道            │
│ ┌──┐┌──┐┌──┐┌──┐┌──┐   ┌──┐┌──┐┌──┐┌──┐┌──┐│
│ │06││07││08││09││10│   │16││17││18││19││20││
│ └──┘└──┘└──┘└──┘└──┘   └──┘└──┘└──┘└──┘└──┘│
├─────────────────────────────────────────────┤
│ [UPS-1] [UPS-2] [配电柜] [消防]  [入口][楼梯]│
└─────────────────────────────────────────────┘
```

#### F3 办公监控区 (40m × 25m)
```
┌─────────────────────────────────────────────┐
│ ┌──────────────┐  ┌──────────────┐          │
│ │   监控中心    │  │    会议室    │          │
│ └──────────────┘  └──────────────┘          │
├─────────────────────────────────────────────┤
│ [AC-1]                      [AC-2]          │
│ ┌──┐┌──┐┌──┐┌──┐  ┌──┐┌──┐┌──┐┌──┐[小机房] │
│ │01││02││03││04│  │05││06││07││08│         │
│ └──┘└──┘└──┘└──┘  └──┘└──┘└──┘└──┘         │
├─────────────────────────────────────────────┤
│ [UPS-1] [配电柜] [茶水间] [卫生间] [入口]    │
└─────────────────────────────────────────────┘
```

### 技术方案

| 模块 | 技术 | 说明 |
|------|------|------|
| 后端API | FastAPI + BackgroundTasks | 异步加载，进度回调 |
| 日期刷新 | SQLAlchemy bulk update | 计算偏移量批量更新 |
| 2D布局 | Vue + SVG | 响应式平面布局图 |
| 3D模型 | Three.js | 多楼层可切换3D场景 |

### 计划任务

| Phase | 任务数 | 说明 |
|-------|--------|------|
| Phase 1 | 2 | 后端API - 演示数据服务和端点 |
| Phase 2 | 3 | 前端 - API模块、加载对话框、入口按钮 |
| Phase 3 | 5 | 楼层布局 - SVG基础组件、B1/F1/F2/F3布局 |
| Phase 4 | 2 | 3D模型 - 多楼层支持、楼宇建模 |
| Phase 5 | 2 | 构建验证 |
| **总计** | **14** | - |

---

## 模拟数据系统实现完成 (2026-01-20)

> **实现了完整的3层算力中心大楼模拟数据系统，包含330个监控点位**
> 实施计划: `docs/plans/2026-01-20-simulation-data-system.md`

### 大楼布局结构

| 楼层 | 用途 | 机柜数 | 主要设备 |
|------|------|--------|----------|
| B1 | 地下制冷机房 | - | 冷水机组(2台)、冷却塔(2台)、水泵(4台) |
| F1 | 1楼机房区A | 20台 | UPS(2台)、精密空调(4台)、配电柜、PDU |
| F2 | 2楼机房区B | 15台 | UPS(2台)、精密空调(4台)、配电柜、PDU |
| F3 | 3楼办公监控 | 8台 | UPS(1台)、精密空调(2台)、监控中心、办公区 |

### 点位统计

| 类型 | 数量 | 说明 |
|------|------|------|
| AI (模拟量输入) | 253 | 温度、湿度、电流、功率、电压等 |
| DI (开关量输入) | 57 | 运行状态、故障状态、门禁、烟感等 |
| AO (模拟量输出) | 10 | 空调设定温度等 |
| DO (开关量输出) | 10 | 空调启停控制等 |
| **总计** | **330** | - |

### 文件变更清单

**新建文件:**
- `backend/app/data/__init__.py` - 数据模块初始化
- `backend/app/data/building_points.py` - 大楼点位定义 + 告警阈值配置
- `backend/app/services/history_generator.py` - 历史数据生成器
- `backend/init_building_points.py` - 点位初始化脚本
- `backend/init_history_data.py` - 历史数据初始化入口脚本

**修改文件:**
- `backend/app/services/simulator.py` - 增强AI值生成逻辑，支持设备特定基准值
- `backend/app/core/config.py` - 添加simulation_enabled和simulation_interval配置

### 关键函数

#### 点位定义 (building_points.py)

| 函数 | 功能 |
|------|------|
| `generate_floor_points(floor, cabinet_count)` | 生成楼层点位（温湿度、UPS、空调、配电、PDU） |
| `get_all_points()` | 聚合所有楼层点位 |
| `count_points()` | 统计点位数量 |
| `get_threshold_for_point(point_code, point_name)` | 根据点位获取告警阈值 |

#### 历史数据生成 (history_generator.py)

| 方法 | 功能 |
|------|------|
| `generate_daily_pattern(hour, base_value, variation)` | 日内波动模式 (白天高/夜间低) |
| `generate_seasonal_pattern(day_offset, base_value)` | 季节性波动 (30天周期) |
| `generate_point_history(point, hours)` | 生成单点位历史数据 |
| `generate_all_history(batch_size)` | 批量生成所有点位历史 |
| `generate_energy_history()` | 生成PUE历史数据 |

### 模拟器增强 (simulator.py)

AI值生成根据设备类型设置智能基准值:

| 设备/点位类型 | 基准值 |
|--------------|--------|
| 机房温度 | 24℃ ± 2 |
| 湿度 | 50% ± 5 |
| 负载率 | 45% ± 10 |
| 电池电量 | 85% ± 5 |
| 输入电压 | 380V ± 5 |
| 输出电压 | 220V ± 2 |
| 冷冻水出水温度 | 7℃ ± 1 |
| 冷冻水回水温度 | 12℃ ± 1 |
| 冷却水温度 | 32℃ ± 3 |
| PDU电流 | 8A ± 2 |
| PDU功率 | 3kW ± 1 |

### 配置项 (config.py)

| 配置 | 默认值 | 说明 |
|------|--------|------|
| simulation_enabled | True | 是否启用模拟数据 |
| simulation_interval | 5 | 模拟数据生成间隔(秒) |

### 验证结果

| 验证项 | 结果 |
|--------|------|
| 点位定义验证 | ✅ 330个点位正确生成 |
| 点位初始化 | ✅ 成功创建330个点位+实时数据+告警阈值 |
| 历史数据生成 | ✅ 3天历史数据生成成功 |
| 模拟器导入 | ✅ 增强逻辑正常工作 |
| 配置验证 | ✅ simulation_enabled=True, simulation_interval=5 |
| 前端构建 | ✅ npm run build 成功 (22.39s) |

---

## 数字孪生大屏系统集成完成 (2026-01-20)

> **大屏已完整集成到主系统，实现真实数据对接和便捷导航**
> 实施计划: `docs/plans/2026-01-20-bigscreen-integration.md`

### 集成内容

#### Phase 1: API数据对接 ✅

| 任务 | 实现方式 |
|------|----------|
| useBigscreenData接入真实API | 导入getRealtimeSummary, getAllRealtimeData, getActiveAlarms, getEnergyDashboard |
| fetchEnvironmentData | 从实时数据提取温湿度点位计算最大/平均/最小值 |
| fetchEnergyData | 从能源仪表盘API获取功率/PUE/电费数据 |
| fetchAlarmData | 从活动告警API获取并转换为BigscreenAlarm格式 |
| fetchDeviceData | 从实时数据关联机柜状态和温度/功率数据 |

#### Phase 2: 导航入口集成 ✅

| 入口位置 | 实现方式 |
|----------|----------|
| 侧边栏 | 添加"数字孪生大屏"菜单项，FullScreen图标，新窗口打开 |
| 仪表盘 | 添加"快捷操作"区域，包含"打开数字孪生大屏"按钮 |

#### Phase 3: 大屏页面优化 ✅

| 功能 | 实现方式 |
|------|----------|
| 布局配置加载 | 调用getDefaultLayout()获取默认机房布局 |
| 返回按钮 | 左上角Back图标，支持关闭窗口或返回仪表盘 |
| 模拟数据移除 | 移除onSceneReady中的硬编码模拟数据 |

#### Phase 4: 后端API支持 (已跳过)

使用前端默认布局配置，后端布局API作为可选增强项。

### 文件变更清单

**前端composables:**
- `frontend/src/composables/bigscreen/useBigscreenData.ts` - 接入真实API

**前端API:**
- `frontend/src/api/modules/bigscreen.ts` - 新建大屏API模块
- `frontend/src/api/modules/index.ts` - 添加bigscreen导出

**前端布局:**
- `frontend/src/layouts/MainLayout.vue` - 添加大屏菜单入口

**前端页面:**
- `frontend/src/views/dashboard/index.vue` - 添加快捷操作栏
- `frontend/src/views/bigscreen/index.vue` - 加载布局配置、添加返回按钮

### 数据流架构

```
前端页面组件
    ↓
useBigscreenData.ts
    ↓ 调用
├── getRealtimeSummary()     → /api/v1/realtime/summary
├── getAllRealtimeData()     → /api/v1/realtime
├── getActiveAlarms()        → /api/v1/alarms/active
├── getEnergyDashboard()     → /api/v1/realtime/energy-dashboard
└── getDefaultLayout()       → 前端默认配置 (可切换为后端API)
    ↓ 更新
bigscreenStore (Pinia)
    ↓ 响应式
3D场景 / 面板组件
```

### 验证结果

| 验证项 | 结果 |
|--------|------|
| 构建验证 | ✅ npm run build 成功 |
| 侧边栏入口 | ✅ 新窗口打开大屏 |
| 仪表盘入口 | ✅ 快捷操作按钮可用 |
| 真实数据对接 | ✅ API数据正确显示 |
| 返回功能 | ✅ 支持关闭窗口/返回仪表盘 |

---

## Phase 17 系统品牌更新与UI优化 (2026-01-20)

> **系统重命名为"算力中心智能监控系统"，登录页面深色主题优化**

### 系统名称变更

| 位置 | 旧名称 | 新名称 |
|------|--------|--------|
| 登录页标题 | 泰阳和正 · 动环监测系统 | 算力中心智能监控系统 |
| 侧边栏Logo | 泰阳和正 | 算力监控 |
| 后端配置 | 机房动环监测系统 | 算力中心智能监控系统 |
| 所有文档 | 机房动环监测系统 | 算力中心智能监控系统 |

### 登录页深色主题设计

参考 `相关图片/图片38.png` 的深色科技风配色方案:

| 元素 | 配色 |
|------|------|
| 页面背景 | linear-gradient(135deg, #0a1628 0%, #0d2137 50%, #0a1628 100%) |
| 网格背景 | rgba(0, 212, 255, 0.03) |
| 登录卡片 | rgba(13, 33, 55, 0.9) |
| 卡片边框 | rgba(0, 212, 255, 0.2) |
| 标题颜色 | #00d4ff + 发光效果 |
| 输入框 | rgba(10, 22, 40, 0.8) |
| 按钮 | linear-gradient(135deg, #1890ff 0%, #00d4ff 100%) |

### 修复的问题

| 文件 | 问题 | 修复 |
|------|------|------|
| login/index.vue | 白色背景 (#fff) | 深色主题 |
| cabinet.vue | fallback颜色 #fff | 改为 #1a2a4a |

### 更新的文件列表

**前端代码:**
- `frontend/src/views/login/index.vue` - 登录页面完整重构
- `frontend/src/layouts/MainLayout.vue` - Logo文字更新
- `frontend/src/views/settings/index.vue` - 系统名称
- `frontend/src/views/asset/cabinet.vue` - 背景色修复

**后端代码:**
- `backend/app/main.py` - 注释和默认配置
- `backend/app/core/config.py` - 默认app_name
- `backend/.env`, `.env.example` - 环境变量
- `backend/run.py`, `init_history.py` - 启动脚本

**配置文件:**
- `docker-compose.yml`
- `start.sh`

**文档:**
- `README.md`, `DEPLOY.md`
- `findings.md`, `progress.md`, `task_plan.md`
- `docs/plans/*.md` (4个设计文档)

---

## Phase 15-16 实施完成 (2026-01-20)

> **容量管理和运维管理模块已完成开发**
> 实施计划: `docs/plans/2026-01-20-capacity-operations-implementation.md`

### 容量管理模块 (Phase 15)

#### 功能实现

| 容量类型 | 关键字段 | 状态计算 |
|----------|----------|----------|
| 空间容量 | total_u, used_u | 使用率 >80% 警告, >95% 严重 |
| 电力容量 | rated_power, current_power | 负载率 >80% 警告, >95% 严重 |
| 制冷容量 | rated_cooling, current_load | 负载率 >80% 警告, >95% 严重 |
| 承重容量 | max_weight, current_weight | 使用率 >80% 警告, >95% 严重 |

#### 容量规划功能

- 新设备上架可行性评估
- 自动检查空间/电力/制冷/承重资源
- 返回 feasible 状态和 issues 列表

#### 文件清单

| 层级 | 文件路径 |
|------|----------|
| 模型 | `backend/app/models/capacity.py` |
| Schema | `backend/app/schemas/capacity.py` |
| 服务 | `backend/app/services/capacity.py` |
| API | `backend/app/api/v1/capacity.py` (25端点) |
| 前端API | `frontend/src/api/modules/capacity.ts` |
| 页面 | `frontend/src/views/capacity/index.vue` |

### 运维管理模块 (Phase 16)

#### 工单管理

| 工单状态 | 流程 |
|----------|------|
| pending | 创建待处理 |
| assigned | 已分配处理人 |
| processing | 处理中 |
| completed | 已完成 |
| closed | 已关闭 |

- 工单编号: WO-YYYYMMDD-XXX (自动生成)
- 工单类型: fault/maintenance/change/other
- 优先级: urgent/high/medium/low

#### 巡检管理

| 功能 | 描述 |
|------|------|
| 巡检计划 | 定义巡检项目、频率、负责人 |
| 巡检任务 | 根据计划自动/手动生成任务 |
| 任务执行 | 开始→完成，记录结果/备注 |

- 任务编号: IT-YYYYMMDD-XXX (自动生成)

#### 知识库

- 分类管理: 运维手册/故障案例/应急预案/技术文档
- 浏览计数: 自动统计文章阅读量
- 全文搜索: 支持标题和内容搜索

#### 文件清单

| 层级 | 文件路径 |
|------|----------|
| 模型 | `backend/app/models/operation.py` |
| Schema | `backend/app/schemas/operation.py` |
| 服务 | `backend/app/services/operation.py` |
| API | `backend/app/api/v1/operation.py` (27端点) |
| 前端API | `frontend/src/api/modules/operation.ts` |
| 页面 | `frontend/src/views/operation/workorder.vue` |
| 页面 | `frontend/src/views/operation/inspection.vue` |
| 页面 | `frontend/src/views/operation/knowledge.vue` |

### 技术决策

| 决策 | 原因 |
|------|------|
| 使用枚举类型定义状态 | 代码可读性和类型安全 |
| 自动生成编号 (WO-/IT-) | 业务标识清晰，便于查询 |
| 服务层单例模式 | 统一服务入口，便于依赖注入 |
| 深色主题CSS变量 | 与现有主题系统保持一致 |
| 前后端类型同步 | TypeScript类型定义与Pydantic Schema对应 |

### 构建验证

- Phase 15 构建时间: 20.69s
- Phase 16 构建时间: 21.55s
- 编译错误: 无
- 警告: Sass弃用警告 (不影响功能)

---

## 界面UI深度研究发现 (2026-01-20)

> **基于66张行业DCIM系统界面截图的分析结论**
> 详细报告: `docs/plans/2026-01-20-dcim-ui-research-report.md`

### 分析素材来源

| 类型 | 数量 | 内容 |
|------|------|------|
| 3D可视化大屏 | 15张 | 数字孪生、温度云图、设备状态、逐级下探 |
| PC端管理页面 | 40张 | 告警管理、能效管理、资产管理、工单运维 |
| 移动端APP | 8张 | 个人工作台、实时报警、数据查询 |
| 硬件设备 | 3张 | 网关、机柜、传感器 |

### 核心设计规范发现

#### 1. 配色方案 (深色科技风)

| 类型 | 色值 | 用途 |
|------|------|------|
| 主背景 | #0a1628 ~ #0d1b2a | 页面背景 |
| 卡片背景 | rgba(26, 42, 74, 0.8) | 面板、卡片 |
| 主色 | #1890ff | 主操作、链接 |
| 强调色 | #00d4ff | 数据强调、边框 |
| 成功 | #52c41a | 正常状态 |
| 警告 | #faad14 | 一般告警 |
| 危险 | #f5222d | 紧急告警 |

#### 2. 布局结构

```
标准PC端布局:
┌─────────────────────────────────────────────────────────┐
│  顶部导航 (60px) - Logo + 一级模块菜单 + 用户信息        │
├──────────┬──────────────────────────────────────────────┤
│ 左侧菜单  │  主内容区域                                  │
│ (200px)  │  - 面包屑导航                                │
│ 可折叠    │  - 筛选区/工具栏                             │
│          │  - 数据展示区 (表格/图表/3D)                  │
└──────────┴──────────────────────────────────────────────┘
```

#### 3. 核心组件设计

**统计卡片**: 大字数值 + 图标 + 趋势指示 + 渐变边框
**数据表格**: 深色主题 + 状态标签 + 分页器
**仪表盘**: 半圆/3/4圆 + 渐变填充 + 中心数值
**告警列表**: 左侧等级色条 + 内容 + 时间 + 操作

#### 4. 3D可视化规范

**场景层级** (逐级下探):
```
园区外观 → 建筑/楼层爆炸图 → 机房内部 → 机柜U位 → 设备详情
```

**可视化元素**:
- 温度热力图: 蓝(15℃)→绿(18℃)→黄(22℃)→橙(26℃)→红(30℃+)
- 设备状态: 绿=正常, 黄=告警, 红=故障, 灰=离线
- 电力流向: 粒子动画表示功率流向
- 气流动画: 空调出风→机柜→热通道粒子流

#### 5. 移动端设计

- **主题**: 浅色主题 (与PC端深色形成差异)
- **主色**: 天蓝色 #1890ff
- **布局**: 宫格式功能入口 + 卡片式列表
- **底部**: Tab导航 (首页/任务)

### 与当前系统UI对比

| 方面 | 行业标准 | 当前系统 | 改进建议 |
|------|---------|---------|---------|
| 整体主题 | 深蓝科技风 | 混合主题 | 全面应用深色主题 |
| 顶部导航 | 多模块横向导航 | 简化版 | 增加模块丰富度 |
| 统计卡片 | 带图标、趋势、迷你图 | 基础版 | 升级交互式卡片 |
| 数据表格 | 深色+状态标签 | Element默认 | 定制深色主题 |
| 3D下探 | 园区→楼宇→机房→机柜 | 单层机房 | 增加多层级导航 |
| 电力流向 | 粒子动画 | 无 | 新增功能 |
| 气流可视化 | 粒子系统 | 无 | 新增功能 |

### UI升级实施计划

**实施方案**: `docs/plans/2026-01-20-ui-upgrade-implementation-plan.md`

| 阶段 | 内容 | 预计周期 |
|------|------|---------|
| Phase 12 | 深色主题系统升级 | 1周 |
| Phase 13 | 核心组件库升级 | 1周 |
| Phase 14 | 页面布局重构 | 1周 |
| Phase 15 | 3D可视化深度增强 | 2周 |

### 关键技术实现

**主题变量** (CSS Variables):
```css
--bg-primary: #0a1628;
--bg-card: rgba(26, 42, 74, 0.8);
--primary-color: #1890ff;
--accent-color: #00d4ff;
--accent-glow: rgba(0, 212, 255, 0.3);
```

**ECharts深色主题**: 配置图表背景透明、坐标轴浅色、Tooltip深色背景

**3D粒子系统**: Three.js Points + BufferGeometry实现电力流向和气流动画

### Phase 12 深色主题实施进度 (2026-01-20)

**已完成任务:**

| 任务 | 文件 | 状态 |
|------|------|------|
| Task 1: 主题变量文件 | `frontend/src/styles/themes/dark-tech.scss` | ✅ 完成 |
| Task 2: Element Plus覆盖 | `frontend/src/styles/element-dark.scss` | ✅ 完成 |
| Task 3: 全局样式更新 | `frontend/src/styles/index.scss` | ✅ 完成 |
| Task 4: 主布局组件 | `frontend/src/layouts/MainLayout.vue` | ✅ 完成 |
| Task 5: 仪表盘页面 | `frontend/src/views/dashboard/index.vue` | ✅ 完成 |
| Task 6: ECharts主题 | `frontend/src/config/echartsTheme.ts` | ✅ 完成 |
| Task 7: 构建验证 | `npm run build` | ✅ 通过 |

**创建的新文件:**

1. `frontend/src/styles/themes/dark-tech.scss`
   - SCSS变量定义 (背景色、主色、强调色、状态色、文字色、边框色、阴影、尺寸、圆角、过渡)
   - CSS自定义属性导出 (:root 声明)
   - 图表配色方案

2. `frontend/src/styles/element-dark.scss`
   - 671行Element Plus组件覆盖样式
   - 涵盖: 按钮、输入框、选择器、表格、卡片、标签、菜单、弹窗、抽屉、分页、表单、日期选择器、消息、通知、面包屑、空状态、提示、进度条、徽章、下拉菜单、头像、警告框、标签页、开关、复选框、单选框、加载、弹出框、树形控件

3. `frontend/src/config/echartsTheme.ts`
   - 深色科技风ECharts主题配置
   - 自动注册到echarts
   - 渐变色预设工具函数

**修改的文件:**

1. `frontend/src/styles/index.scss`
   - 导入主题变量和Element覆盖
   - 更新基础样式为深色背景
   - 添加工具类 (.text-primary, .bg-card, .dark-card等)
   - 添加告警闪烁动画

2. `frontend/src/layouts/MainLayout.vue`
   - 移除硬编码颜色 (background-color="#304156")
   - 使用CSS变量 (var(--bg-secondary), var(--border-color)等)
   - 侧边栏、顶栏、主内容区深色主题

3. `frontend/src/views/dashboard/index.vue`
   - 统计卡片深色样式 + 发光效果
   - 告警列表深色背景 + 等级色彩
   - PUE状态色彩 + 文字发光

4. `frontend/src/main.ts`
   - 注册ECharts深色主题

---

## 行业调研发现 (2026-01-20)

### 调研文献清单

| 序号 | 文献名称 | 厂商 | 页数 | 核心特点 |
|------|---------|------|------|---------|
| 1 | DCIM平台技术方案 | 北京盈泽 | 106页 | 最完整的DCIM方案，含3D可视化、资产管理、运维管理 |
| 2 | 智能监控管理平台V7.0技术方案 | 深圳计通(JITON) | 详细版 | 智能化集成应用(机器人/AI/UWB/AR眼镜) |
| 3 | 微模块综合监控系统解决方案 | SHOONIS | 69页 | 微模块专用，强调制冷效率 |
| 4 | DCIM v3r3标准方案技术建议书 | 共济 | 57页 | 标准化DCIM方案，模块化设计 |
| 5 | 机房动力环境监控的组成及必要性 | 郭小平 | 培训PPT | 行业基础知识，发展历程 |

### 行业DCIM系统七大核心模块

1. **动力监控** - UPS/配电/电池/发电机/ATS/列头柜
2. **环境监控** - 温湿度/空调/漏水/新风/消防
3. **安防监控** - 门禁/视频/消防/防盗
4. **资产管理** - 全生命周期管理/盘点/追溯
5. **容量管理** - 空间/电力/制冷/承重/网络
6. **能效管理** - PUE/能耗分项/碳排放/节能
7. **运维管理** - 工单/巡检/维保/变更/值班

### 与当前系统对比

| 功能模块 | 行业标配 | 当前系统 | 差距分析 |
|---------|---------|---------|---------|
| 动力监控 | ✅ | ✅ | 基本具备，可增强发电机/ATS监控 |
| 环境监控 | ✅ | ✅ | 基本具备，需增加温度云图 |
| 安防监控 | ✅ | ⚠️部分 | 仅门禁，需增加视频/消防集成 |
| 资产管理 | ✅ | ❌ | **缺失**，需新增 |
| 容量管理 | ✅ | ❌ | **缺失**，需新增 |
| 能效管理 | ✅ | ✅ | 已实现PUE和能耗统计 |
| 运维管理 | ✅ | ❌ | **缺失**，需新增 |
| 3D可视化 | ✅ | ✅✅ | **优势**，V2.5已有较完整实现 |
| 用电管理 | ⚠️基础 | ✅✅ | **核心优势**，远超行业方案 |

### 当前系统核心优势 (必须保留)

1. **用电管理特色功能**
   - 配电拓扑可视化配置 - 行业方案多为静态配置
   - 15分钟需量分析 - 行业方案无此功能
   - 负荷智能调节 - 行业方案无此功能
   - 峰谷平电费分析 - 行业方案仅总电费统计
   - AI节能建议 - 行业方案多为人工分析

2. **数字孪生3D可视化**
   - Three.js实现，Web端最佳方案
   - 已完成：热力图、设备状态、告警气泡、场景模式、自动巡航
   - 可进一步增强：电力流向、气流动画、逐级导航

### 重构建议

**详细方案**: `docs/plans/2026-01-20-dcim-system-restructure-proposal.md`

**版本规划**:
- V2.6: 3D深度优化 (电力流向、气流动画、逐级导航)
- V3.0: 功能对齐 (安防增强、告警增强、报表增强)
- V3.1: 新增模块 (资产管理、容量管理、运维管理)
- V3.2: 体验优化 (个人工作台、移动端、微信推送)

---

## 需求确认（用户选择）

| 项目 | 选择 | 说明 |
|------|------|------|
| 数据来源 | 模拟数据 | 使用模拟器生成仿真数据，无需硬件 |
| 告警通知 | 网页弹窗 + 声音 | 基础告警，仅在系统内提示 |
| 机房规模 | 单机房 | 管理一个机房的所有设备 |
| 终端支持 | 仅 PC 端 | 桌面浏览器访问，无需移动端适配 |
| 计费模式 | 按点位数收费 | 根据监控点位数量进行授权和计费 |

---

## 一、监控点位设计

### 1.1 点位类型定义

| 类型代码 | 英文名称 | 中文名称 | 说明 | 数据类型 |
|----------|----------|----------|------|----------|
| AI | Analog Input | 模拟量输入 | 采集连续变化的物理量（温度、电压等） | float |
| DI | Digital Input | 开关量输入 | 采集开关状态（门禁、报警器等） | boolean (0/1) |
| AO | Analog Output | 模拟量输出 | 控制输出的连续量（设定温度、风速等） | float |
| DO | Digital Output | 开关量输出 | 控制开关动作（启停设备等） | boolean (0/1) |

### 1.2 点位编码规则

```
点位编码格式: {区域代码}_{设备类型}_{点位类型}_{序号}

示例:
- A1_TH_AI_001  -> A1区-温湿度传感器-模拟量输入-001号（温度）
- A1_UPS_DI_001 -> A1区-UPS-开关量输入-001号（市电状态）
- A1_AC_DO_001  -> A1区-空调-开关量输出-001号（启停控制）

区域代码: A1, A2, B1, B2 等
设备类型: TH(温湿度), UPS, PDU(配电), AC(空调), DOOR(门禁),
         SMOKE(烟感), WATER(漏水), IR(红外), FAN(风机), LIGHT(照明)
```

### 1.3 点位统计汇总

| 点位类型 | 数量 | 说明 |
|----------|------|------|
| AI (模拟量输入) | 36 | 温湿度、电压、电流、功率、电量等 |
| DI (开关量输入) | 22 | 设备状态、告警信号、开关状态等 |
| AO (模拟量输出) | 4 | 温度设定、风速调节等 |
| DO (开关量输出) | 8 | 设备启停控制等 |
| **总计** | **70** | - |

### 1.4 电力监控点位详细清单

#### 1.4.1 配电柜监控点位

| 点位编码 | 点位名称 | 类型 | 单位 | 说明 |
|----------|----------|------|------|------|
| A1_PDU_AI_001 | 总进线电压A | AI | V | A相电压 |
| A1_PDU_AI_002 | 总进线电压B | AI | V | B相电压 |
| A1_PDU_AI_003 | 总进线电压C | AI | V | C相电压 |
| A1_PDU_AI_004 | 总进线电流A | AI | A | A相电流 |
| A1_PDU_AI_005 | 总进线电流B | AI | A | B相电流 |
| A1_PDU_AI_006 | 总进线电流C | AI | A | C相电流 |
| A1_PDU_AI_007 | 总有功功率 | AI | kW | 三相总有功功率 |
| A1_PDU_AI_008 | 总无功功率 | AI | kVar | 三相总无功功率 |
| A1_PDU_AI_009 | 总视在功率 | AI | kVA | 三相总视在功率 |
| A1_PDU_AI_010 | 功率因数 | AI | - | 总功率因数 |
| A1_PDU_AI_011 | 总电能 | AI | kWh | 累计用电量 |
| A1_PDU_AI_012 | 频率 | AI | Hz | 电网频率 |
| A1_PDU_DI_001 | 主开关状态 | DI | - | 0=分/1=合 |
| A1_PDU_DI_002 | 防雷器状态 | DI | - | 0=正常/1=故障 |
| A1_PDU_DI_003 | 过压告警 | DI | - | 0=正常/1=告警 |
| A1_PDU_DI_004 | 欠压告警 | DI | - | 0=正常/1=告警 |

#### 1.4.2 UPS电力监控点位

| 点位编码 | 点位名称 | 类型 | 单位 | 说明 |
|----------|----------|------|------|------|
| A1_UPS_AI_001 | 输入电压 | AI | V | UPS输入电压 |
| A1_UPS_AI_002 | 输出电压 | AI | V | UPS输出电压 |
| A1_UPS_AI_003 | 输出电流 | AI | A | UPS输出电流 |
| A1_UPS_AI_004 | 输出功率 | AI | kW | UPS输出功率 |
| A1_UPS_AI_005 | 负载率 | AI | % | UPS负载百分比 |
| A1_UPS_AI_006 | 电池电压 | AI | V | 电池组电压 |
| A1_UPS_AI_007 | 电池剩余容量 | AI | % | 电池剩余百分比 |
| A1_UPS_AI_008 | 预计后备时间 | AI | min | 当前负载下后备时间 |

#### 1.4.3 空调电力监控点位

| 点位编码 | 点位名称 | 类型 | 单位 | 说明 |
|----------|----------|------|------|------|
| A1_AC_AI_001 | 空调1功率 | AI | kW | 1号空调实时功率 |
| A1_AC_AI_002 | 空调2功率 | AI | kW | 2号空调实时功率 |
| A1_AC_AI_003 | 空调1电量 | AI | kWh | 1号空调累计电量 |
| A1_AC_AI_004 | 空调2电量 | AI | kWh | 2号空调累计电量 |

### 1.5 点位授权与计费

| 版本 | 点位上限 | 适用场景 | 功能限制 |
|------|----------|----------|----------|
| 基础版 | ≤50点 | 小型机房 | 无报表、无数据导出 |
| 标准版 | ≤100点 | 中型机房 | 完整功能 |
| 企业版 | ≤500点 | 大型机房 | 多用户、API对接 |
| 无限版 | 不限 | 数据中心 | 全部功能 + 定制 |

---

## 二、后端架构设计

### 2.1 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           前端 (Vue 3 + TypeScript)                      │
│  ┌─────────┬──────────┬──────────┬──────────┬──────────┬──────────┐    │
│  │ 实时监控 │ 设备管理  │ 告警中心  │ 历史查询  │ 报表分析  │ 系统管理  │    │
│  └────┬────┴────┬─────┴────┬─────┴────┬─────┴────┬─────┴────┬─────┘    │
└───────┼─────────┼──────────┼──────────┼──────────┼──────────┼───────────┘
        │ HTTP    │ WebSocket│          │          │          │
        ▼         ▼          ▼          ▼          ▼          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          API 网关层 (FastAPI)                            │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  认证中间件 │ 权限校验 │ 请求日志 │ 限流控制 │ 异常处理 │ CORS     │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           业务服务层 (Services)                          │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┬──────────┐   │
│  │ 认证服务  │ 点位服务  │ 采集服务  │ 告警服务  │ 报表服务  │ 日志服务  │   │
│  │AuthSvc   │PointSvc  │CollectSvc│AlarmSvc  │ReportSvc │LogSvc    │   │
│  └──────────┴──────────┴──────────┴──────────┴──────────┴──────────┘   │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┬──────────┐   │
│  │ 缓存服务  │ 定时任务  │ WebSocket│ 数据导出  │ 统计分析  │ 系统配置  │   │
│  │CacheSvc  │ScheduleSvc│ WsSvc   │ExportSvc │StatsSvc  │ConfigSvc │   │
│  └──────────┴──────────┴──────────┴──────────┴──────────┴──────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           数据访问层 (Repository)                        │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┬──────────┐   │
│  │UserRepo  │PointRepo │AlarmRepo │HistoryRepo│LogRepo  │ConfigRepo│   │
│  └──────────┴──────────┴──────────┴──────────┴──────────┴──────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                             数据存储层                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐ │
│  │   SQLite/MySQL   │  │   内存缓存       │  │   文件存储               │ │
│  │   (业务数据)      │  │   (实时数据)     │  │   (报表/导出文件)         │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 后端模块划分

```
backend/
├── app/
│   ├── api/                    # API 路由层
│   │   ├── v1/                 # API 版本1
│   │   │   ├── auth.py         # 认证相关 API
│   │   │   ├── user.py         # 用户管理 API
│   │   │   ├── point.py        # 点位管理 API
│   │   │   ├── realtime.py     # 实时数据 API
│   │   │   ├── alarm.py        # 告警管理 API
│   │   │   ├── history.py      # 历史数据 API
│   │   │   ├── report.py       # 报表 API
│   │   │   ├── threshold.py    # 阈值配置 API
│   │   │   ├── log.py          # 日志查询 API
│   │   │   ├── config.py       # 系统配置 API
│   │   │   └── statistics.py   # 统计分析 API
│   │   └── deps.py             # 依赖注入
│   │
│   ├── core/                   # 核心配置
│   │   ├── config.py           # 应用配置
│   │   ├── security.py         # 安全/认证
│   │   ├── database.py         # 数据库连接
│   │   ├── cache.py            # 缓存管理
│   │   ├── exceptions.py       # 自定义异常
│   │   └── middleware.py       # 中间件
│   │
│   ├── models/                 # 数据模型 (ORM)
│   │   ├── user.py             # 用户模型
│   │   ├── point.py            # 点位模型
│   │   ├── alarm.py            # 告警模型
│   │   ├── history.py          # 历史数据模型
│   │   ├── log.py              # 日志模型
│   │   └── config.py           # 配置模型
│   │
│   ├── schemas/                # Pydantic 模型
│   │   ├── user.py
│   │   ├── point.py
│   │   ├── alarm.py
│   │   ├── history.py
│   │   ├── report.py
│   │   └── common.py           # 通用响应模型
│   │
│   ├── services/               # 业务服务层
│   │   ├── auth_service.py     # 认证服务
│   │   ├── user_service.py     # 用户服务
│   │   ├── point_service.py    # 点位服务
│   │   ├── collect_service.py  # 数据采集服务
│   │   ├── alarm_service.py    # 告警服务
│   │   ├── history_service.py  # 历史数据服务
│   │   ├── report_service.py   # 报表服务
│   │   ├── export_service.py   # 数据导出服务
│   │   ├── statistics_service.py# 统计服务
│   │   ├── log_service.py      # 日志服务
│   │   ├── cache_service.py    # 缓存服务
│   │   ├── websocket_service.py# WebSocket服务
│   │   └── scheduler_service.py# 定时任务服务
│   │
│   ├── repositories/           # 数据仓库层
│   │   ├── base.py             # 基础仓库
│   │   ├── user_repo.py
│   │   ├── point_repo.py
│   │   ├── alarm_repo.py
│   │   ├── history_repo.py
│   │   └── log_repo.py
│   │
│   ├── tasks/                  # 定时任务
│   │   ├── data_collect.py     # 数据采集任务
│   │   ├── data_cleanup.py     # 数据清理任务
│   │   ├── alarm_check.py      # 告警检测任务
│   │   ├── report_generate.py  # 报表生成任务
│   │   └── stats_calculate.py  # 统计计算任务
│   │
│   ├── utils/                  # 工具函数
│   │   ├── datetime_utils.py   # 时间处理
│   │   ├── export_utils.py     # 导出工具
│   │   ├── validators.py       # 验证器
│   │   └── helpers.py          # 辅助函数
│   │
│   └── main.py                 # 应用入口
│
├── migrations/                 # 数据库迁移
├── tests/                      # 测试
├── logs/                       # 日志文件
├── exports/                    # 导出文件
├── requirements.txt
└── .env
```

### 2.3 数据库设计

#### 2.3.1 用户与权限

```sql
-- 用户表
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    real_name VARCHAR(50),
    email VARCHAR(100),
    phone VARCHAR(20),
    role VARCHAR(20) DEFAULT 'operator',  -- admin, operator, viewer
    department VARCHAR(100),
    avatar VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    last_login_at TIMESTAMP,
    last_login_ip VARCHAR(50),
    login_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 角色权限表
CREATE TABLE role_permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role VARCHAR(20) NOT NULL,
    permission VARCHAR(100) NOT NULL,  -- point:read, point:write, alarm:ack, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 用户登录历史
CREATE TABLE user_login_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    login_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    login_ip VARCHAR(50),
    user_agent VARCHAR(255),
    status VARCHAR(20),  -- success, failed
    fail_reason VARCHAR(100),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

#### 2.3.2 点位与设备

```sql
-- 设备表（物理设备）
CREATE TABLE devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_code VARCHAR(50) UNIQUE NOT NULL,
    device_name VARCHAR(100) NOT NULL,
    device_type VARCHAR(20) NOT NULL,    -- UPS, AC, PDU, TH, DOOR, SMOKE, WATER
    area_code VARCHAR(10) NOT NULL,
    manufacturer VARCHAR(100),           -- 制造商
    model VARCHAR(100),                  -- 型号
    serial_number VARCHAR(100),          -- 序列号
    install_date DATE,                   -- 安装日期
    status VARCHAR(20) DEFAULT 'online', -- online, offline, maintenance
    location_x REAL,                     -- 平面图X坐标
    location_y REAL,                     -- 平面图Y坐标
    description TEXT,
    is_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 点位表（监控点）
CREATE TABLE points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    point_code VARCHAR(50) UNIQUE NOT NULL,
    point_name VARCHAR(100) NOT NULL,
    point_type VARCHAR(2) NOT NULL,       -- AI, DI, AO, DO
    device_id INTEGER,                    -- 关联设备
    device_type VARCHAR(20) NOT NULL,
    area_code VARCHAR(10) NOT NULL,
    unit VARCHAR(20),
    data_type VARCHAR(10) DEFAULT 'float',
    min_range REAL,
    max_range REAL,
    precision INTEGER DEFAULT 2,          -- 小数位数
    collect_interval INTEGER DEFAULT 10,  -- 采集周期(秒)
    store_interval INTEGER DEFAULT 60,    -- 存储周期(秒)
    is_enabled BOOLEAN DEFAULT TRUE,
    is_virtual BOOLEAN DEFAULT FALSE,     -- 是否虚拟点位(计算点)
    calc_formula TEXT,                    -- 计算公式(虚拟点)
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (device_id) REFERENCES devices(id)
);

-- 点位实时值表（内存表/频繁更新）
CREATE TABLE point_realtime (
    point_id INTEGER PRIMARY KEY,
    raw_value REAL,                       -- 原始值
    value REAL,                           -- 工程值
    value_text VARCHAR(50),               -- 状态文本
    quality INTEGER DEFAULT 0,            -- 0=好 1=不确定 2=坏
    status VARCHAR(20) DEFAULT 'normal',  -- normal, alarm, offline
    alarm_level VARCHAR(20),              -- 当前告警级别
    change_count INTEGER DEFAULT 0,       -- 变化次数
    last_change_at TIMESTAMP,             -- 最后变化时间
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (point_id) REFERENCES points(id)
);

-- 点位分组表
CREATE TABLE point_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_name VARCHAR(100) NOT NULL,
    group_type VARCHAR(20),               -- area, device_type, custom
    parent_id INTEGER,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 点位分组关系
CREATE TABLE point_group_members (
    group_id INTEGER NOT NULL,
    point_id INTEGER NOT NULL,
    PRIMARY KEY (group_id, point_id),
    FOREIGN KEY (group_id) REFERENCES point_groups(id),
    FOREIGN KEY (point_id) REFERENCES points(id)
);
```

#### 2.3.3 告警系统

```sql
-- 告警阈值配置
CREATE TABLE alarm_thresholds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    point_id INTEGER NOT NULL,
    threshold_type VARCHAR(20) NOT NULL,   -- high_high, high, low, low_low, equal, change
    threshold_value REAL,
    alarm_level VARCHAR(20) DEFAULT 'minor',
    alarm_message VARCHAR(200),
    delay_seconds INTEGER DEFAULT 0,       -- 延迟触发(秒)
    dead_band REAL DEFAULT 0,              -- 死区(回差)
    is_enabled BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 0,            -- 优先级
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (point_id) REFERENCES points(id)
);

-- 告警记录表
CREATE TABLE alarms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alarm_no VARCHAR(50) UNIQUE NOT NULL,  -- 告警编号
    point_id INTEGER NOT NULL,
    threshold_id INTEGER,
    alarm_level VARCHAR(20) NOT NULL,
    alarm_type VARCHAR(20),                -- threshold, communication, system
    alarm_message TEXT NOT NULL,
    trigger_value REAL,
    threshold_value REAL,
    status VARCHAR(20) DEFAULT 'active',   -- active, acknowledged, resolved, ignored
    acknowledged_by INTEGER,
    acknowledged_at TIMESTAMP,
    ack_remark TEXT,                       -- 确认备注
    resolved_by INTEGER,
    resolved_at TIMESTAMP,
    resolve_remark TEXT,                   -- 解决备注
    resolve_type VARCHAR(20),              -- manual, auto, timeout
    duration_seconds INTEGER,              -- 持续时间(秒)
    is_notified BOOLEAN DEFAULT FALSE,
    notify_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (point_id) REFERENCES points(id),
    FOREIGN KEY (threshold_id) REFERENCES alarm_thresholds(id),
    FOREIGN KEY (acknowledged_by) REFERENCES users(id),
    FOREIGN KEY (resolved_by) REFERENCES users(id)
);

-- 告警规则表（复合告警）
CREATE TABLE alarm_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name VARCHAR(100) NOT NULL,
    rule_type VARCHAR(20),                 -- and, or, sequence
    condition_expr TEXT,                   -- 条件表达式
    alarm_level VARCHAR(20),
    alarm_message VARCHAR(200),
    is_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 告警屏蔽表
CREATE TABLE alarm_shields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    point_id INTEGER,                      -- 点位(可为空表示全局)
    alarm_level VARCHAR(20),               -- 屏蔽级别(可为空表示全部)
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    reason TEXT,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (point_id) REFERENCES points(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

-- 告警统计表（按天聚合）
CREATE TABLE alarm_daily_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stat_date DATE NOT NULL,
    point_id INTEGER,
    alarm_level VARCHAR(20),
    total_count INTEGER DEFAULT 0,
    ack_count INTEGER DEFAULT 0,
    resolve_count INTEGER DEFAULT 0,
    avg_duration_seconds INTEGER,
    max_duration_seconds INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 2.3.4 历史数据

```sql
-- 历史数据表（分表按月）
CREATE TABLE point_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    point_id INTEGER NOT NULL,
    value REAL NOT NULL,
    quality INTEGER DEFAULT 0,
    min_value REAL,                       -- 周期内最小值
    max_value REAL,                       -- 周期内最大值
    avg_value REAL,                       -- 周期内平均值
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (point_id) REFERENCES points(id)
);

-- 历史数据索引
CREATE INDEX idx_history_point_time ON point_history(point_id, recorded_at);
CREATE INDEX idx_history_time ON point_history(recorded_at);

-- 数据归档表（长期存储，降采样）
CREATE TABLE point_history_archive (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    point_id INTEGER NOT NULL,
    archive_type VARCHAR(20),             -- hourly, daily, monthly
    value_min REAL,
    value_max REAL,
    value_avg REAL,
    value_sum REAL,
    sample_count INTEGER,
    recorded_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 变化记录表（用于DI点位）
CREATE TABLE point_change_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    point_id INTEGER NOT NULL,
    old_value REAL,
    new_value REAL,
    change_type VARCHAR(20),              -- normal, alarm, recover
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (point_id) REFERENCES points(id)
);
```

#### 2.3.5 操作日志

```sql
-- 操作日志表
CREATE TABLE operation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username VARCHAR(50),
    module VARCHAR(50) NOT NULL,          -- user, point, alarm, config, report
    action VARCHAR(50) NOT NULL,          -- create, update, delete, query, export
    target_type VARCHAR(50),              -- point, alarm, threshold, user
    target_id INTEGER,
    target_name VARCHAR(100),
    old_value TEXT,                       -- JSON格式
    new_value TEXT,                       -- JSON格式
    ip_address VARCHAR(50),
    user_agent VARCHAR(255),
    request_url VARCHAR(255),
    request_method VARCHAR(10),
    request_params TEXT,
    response_code INTEGER,
    response_time_ms INTEGER,             -- 响应时间(毫秒)
    remark TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 系统日志表
CREATE TABLE system_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_level VARCHAR(20) NOT NULL,       -- DEBUG, INFO, WARN, ERROR, FATAL
    module VARCHAR(50),
    message TEXT NOT NULL,
    exception TEXT,
    stack_trace TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 通讯日志表
CREATE TABLE communication_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER,
    comm_type VARCHAR(20),                -- request, response, error
    protocol VARCHAR(20),                 -- modbus, snmp, mqtt
    request_data TEXT,
    response_data TEXT,
    status VARCHAR(20),
    error_message TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 2.3.6 报表与配置

```sql
-- 报表模板表
CREATE TABLE report_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_name VARCHAR(100) NOT NULL,
    template_type VARCHAR(20),            -- daily, weekly, monthly, custom
    template_config TEXT,                 -- JSON配置
    point_ids TEXT,                       -- 包含的点位ID列表
    is_enabled BOOLEAN DEFAULT TRUE,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 报表生成记录
CREATE TABLE report_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER,
    report_name VARCHAR(200),
    report_type VARCHAR(20),
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    file_path VARCHAR(255),
    file_size INTEGER,
    status VARCHAR(20),                   -- generating, completed, failed
    error_message TEXT,
    generated_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (template_id) REFERENCES report_templates(id),
    FOREIGN KEY (generated_by) REFERENCES users(id)
);

-- 系统配置表
CREATE TABLE system_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_group VARCHAR(50) NOT NULL,
    config_key VARCHAR(100) NOT NULL,
    config_value TEXT,
    value_type VARCHAR(20),               -- string, number, boolean, json
    description VARCHAR(200),
    is_editable BOOLEAN DEFAULT TRUE,
    updated_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(config_group, config_key)
);

-- 数据字典表
CREATE TABLE dictionaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dict_type VARCHAR(50) NOT NULL,
    dict_code VARCHAR(50) NOT NULL,
    dict_name VARCHAR(100) NOT NULL,
    dict_value VARCHAR(200),
    sort_order INTEGER DEFAULT 0,
    is_enabled BOOLEAN DEFAULT TRUE,
    remark TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 授权许可表
CREATE TABLE licenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    license_key VARCHAR(100) UNIQUE NOT NULL,
    license_type VARCHAR(20) NOT NULL,
    max_points INTEGER NOT NULL,
    features TEXT,                        -- JSON: 功能列表
    issue_date DATE,
    expire_date DATE,
    hardware_id VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    activated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 2.4 API 接口设计

#### 2.4.1 认证接口

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| POST | /api/v1/auth/login | 用户登录 | 公开 |
| POST | /api/v1/auth/logout | 用户登出 | 已认证 |
| POST | /api/v1/auth/refresh | 刷新Token | 已认证 |
| GET | /api/v1/auth/me | 获取当前用户信息 | 已认证 |
| PUT | /api/v1/auth/password | 修改密码 | 已认证 |
| GET | /api/v1/auth/permissions | 获取当前用户权限 | 已认证 |

#### 2.4.2 用户管理接口

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/v1/users | 获取用户列表(分页) | admin |
| GET | /api/v1/users/{id} | 获取用户详情 | admin |
| POST | /api/v1/users | 创建用户 | admin |
| PUT | /api/v1/users/{id} | 更新用户 | admin |
| DELETE | /api/v1/users/{id} | 删除用户 | admin |
| PUT | /api/v1/users/{id}/status | 启用/禁用用户 | admin |
| PUT | /api/v1/users/{id}/reset-password | 重置密码 | admin |
| GET | /api/v1/users/{id}/login-history | 获取登录历史 | admin |

#### 2.4.3 设备管理接口

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/v1/devices | 获取设备列表 | viewer |
| GET | /api/v1/devices/{id} | 获取设备详情 | viewer |
| POST | /api/v1/devices | 创建设备 | operator |
| PUT | /api/v1/devices/{id} | 更新设备 | operator |
| DELETE | /api/v1/devices/{id} | 删除设备 | admin |
| GET | /api/v1/devices/{id}/points | 获取设备下的点位 | viewer |
| GET | /api/v1/devices/tree | 获取设备树结构 | viewer |
| GET | /api/v1/devices/status-summary | 获取设备状态汇总 | viewer |

#### 2.4.4 点位管理接口

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/v1/points | 获取点位列表(支持多条件筛选、分页) | viewer |
| GET | /api/v1/points/{id} | 获取点位详情 | viewer |
| POST | /api/v1/points | 创建点位 | operator |
| PUT | /api/v1/points/{id} | 更新点位 | operator |
| DELETE | /api/v1/points/{id} | 删除点位 | admin |
| PUT | /api/v1/points/{id}/enable | 启用点位 | operator |
| PUT | /api/v1/points/{id}/disable | 禁用点位 | operator |
| POST | /api/v1/points/batch-import | 批量导入点位 | operator |
| GET | /api/v1/points/export | 导出点位配置 | operator |
| GET | /api/v1/points/types-summary | 获取点位类型统计 | viewer |
| GET | /api/v1/points/groups | 获取点位分组 | viewer |
| POST | /api/v1/points/groups | 创建点位分组 | operator |

#### 2.4.5 实时数据接口

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/v1/realtime | 获取所有点位实时数据 | viewer |
| GET | /api/v1/realtime/{point_id} | 获取单个点位实时数据 | viewer |
| GET | /api/v1/realtime/by-type/{type} | 按类型获取实时数据 | viewer |
| GET | /api/v1/realtime/by-area/{area} | 按区域获取实时数据 | viewer |
| GET | /api/v1/realtime/by-device/{device_id} | 按设备获取实时数据 | viewer |
| GET | /api/v1/realtime/by-group/{group_id} | 按分组获取实时数据 | viewer |
| GET | /api/v1/realtime/summary | 获取实时数据汇总 | viewer |
| GET | /api/v1/realtime/dashboard | 获取仪表盘数据 | viewer |
| POST | /api/v1/realtime/control/{point_id} | 下发控制指令(AO/DO) | operator |

#### 2.4.6 历史数据接口

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/v1/history/{point_id} | 获取点位历史数据 | viewer |
| GET | /api/v1/history/{point_id}/trend | 获取趋势数据(图表用) | viewer |
| GET | /api/v1/history/{point_id}/statistics | 获取统计数据 | viewer |
| GET | /api/v1/history/compare | 多点位对比查询 | viewer |
| GET | /api/v1/history/export | 导出历史数据 | operator |
| GET | /api/v1/history/changes/{point_id} | 获取变化记录(DI点) | viewer |
| DELETE | /api/v1/history/cleanup | 清理过期数据 | admin |

#### 2.4.7 告警管理接口

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/v1/alarms | 获取告警列表(多条件筛选、分页) | viewer |
| GET | /api/v1/alarms/active | 获取活动告警 | viewer |
| GET | /api/v1/alarms/{id} | 获取告警详情 | viewer |
| PUT | /api/v1/alarms/{id}/acknowledge | 确认告警 | operator |
| PUT | /api/v1/alarms/{id}/resolve | 解决告警 | operator |
| PUT | /api/v1/alarms/batch-acknowledge | 批量确认告警 | operator |
| GET | /api/v1/alarms/count | 获取各级别告警数量 | viewer |
| GET | /api/v1/alarms/statistics | 获取告警统计 | viewer |
| GET | /api/v1/alarms/trend | 获取告警趋势 | viewer |
| GET | /api/v1/alarms/top-points | 获取高频告警点位 | viewer |
| GET | /api/v1/alarms/export | 导出告警记录 | operator |

#### 2.4.8 阈值配置接口

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/v1/thresholds | 获取阈值配置列表 | viewer |
| GET | /api/v1/thresholds/point/{point_id} | 获取点位阈值配置 | viewer |
| POST | /api/v1/thresholds | 创建阈值配置 | operator |
| PUT | /api/v1/thresholds/{id} | 更新阈值配置 | operator |
| DELETE | /api/v1/thresholds/{id} | 删除阈值配置 | operator |
| POST | /api/v1/thresholds/batch | 批量配置阈值 | operator |
| POST | /api/v1/thresholds/copy | 复制阈值配置到其他点位 | operator |

#### 2.4.9 告警屏蔽接口

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/v1/alarm-shields | 获取屏蔽列表 | viewer |
| POST | /api/v1/alarm-shields | 创建屏蔽规则 | operator |
| DELETE | /api/v1/alarm-shields/{id} | 删除屏蔽规则 | operator |

#### 2.4.10 报表接口

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/v1/reports/templates | 获取报表模板 | viewer |
| POST | /api/v1/reports/templates | 创建报表模板 | operator |
| PUT | /api/v1/reports/templates/{id} | 更新报表模板 | operator |
| DELETE | /api/v1/reports/templates/{id} | 删除报表模板 | operator |
| POST | /api/v1/reports/generate | 生成报表 | operator |
| GET | /api/v1/reports/records | 获取报表记录 | viewer |
| GET | /api/v1/reports/download/{id} | 下载报表 | viewer |
| GET | /api/v1/reports/daily | 获取日报数据 | viewer |
| GET | /api/v1/reports/weekly | 获取周报数据 | viewer |
| GET | /api/v1/reports/monthly | 获取月报数据 | viewer |

#### 2.4.11 日志查询接口

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/v1/logs/operations | 获取操作日志 | admin |
| GET | /api/v1/logs/systems | 获取系统日志 | admin |
| GET | /api/v1/logs/communications | 获取通讯日志 | admin |
| GET | /api/v1/logs/export | 导出日志 | admin |
| GET | /api/v1/logs/statistics | 获取日志统计 | admin |

#### 2.4.12 统计分析接口

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/v1/statistics/overview | 获取系统概览统计 | viewer |
| GET | /api/v1/statistics/points | 获取点位统计 | viewer |
| GET | /api/v1/statistics/alarms | 获取告警统计 | viewer |
| GET | /api/v1/statistics/energy | 获取能耗统计 | viewer |
| GET | /api/v1/statistics/availability | 获取可用性统计 | viewer |
| GET | /api/v1/statistics/comparison | 获取同比/环比数据 | viewer |

#### 2.4.13 系统配置接口

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/v1/configs | 获取系统配置 | admin |
| PUT | /api/v1/configs | 更新系统配置 | admin |
| GET | /api/v1/configs/dictionaries | 获取数据字典 | viewer |
| GET | /api/v1/configs/license | 获取授权信息 | viewer |
| POST | /api/v1/configs/license/activate | 激活授权 | admin |
| GET | /api/v1/configs/backup | 导出系统配置 | admin |
| POST | /api/v1/configs/restore | 导入系统配置 | admin |

#### 2.4.14 WebSocket 接口

| 路径 | 描述 |
|------|------|
| /ws/realtime | 实时数据推送（订阅机制） |
| /ws/alarms | 告警实时推送 |
| /ws/system | 系统状态推送 |

**WebSocket 消息格式**：

```json
// 订阅消息
{
  "action": "subscribe",
  "channels": ["realtime", "alarms"],
  "filters": {
    "point_ids": [1, 2, 3],
    "area_codes": ["A1", "A2"],
    "alarm_levels": ["critical", "major"]
  }
}

// 实时数据推送
{
  "type": "realtime",
  "timestamp": "2026-01-13T10:30:00Z",
  "data": {
    "point_id": 1,
    "point_code": "A1_TH_AI_001",
    "point_name": "A1区温度",
    "value": 24.5,
    "unit": "℃",
    "status": "normal",
    "quality": 0
  }
}

// 告警推送
{
  "type": "alarm",
  "timestamp": "2026-01-13T10:30:00Z",
  "action": "new",  // new, ack, resolve
  "data": {
    "id": 100,
    "alarm_no": "ALM202601130001",
    "point_code": "A1_TH_AI_001",
    "point_name": "A1区温度",
    "level": "major",
    "message": "温度超过上限: 29.5℃ > 28℃",
    "value": 29.5,
    "threshold": 28
  }
}
```

### 2.5 定时任务设计

| 任务名称 | 执行周期 | 说明 |
|----------|----------|------|
| 数据采集 | 每5秒 | 采集所有启用点位的数据 |
| 告警检测 | 每5秒 | 检测阈值触发告警 |
| 实时推送 | 每3秒 | 通过WebSocket推送实时数据 |
| 历史存储 | 每分钟 | 将实时数据存入历史表 |
| 数据聚合 | 每小时 | 计算小时级统计数据 |
| 日统计 | 每天0:05 | 计算日统计数据 |
| 月统计 | 每月1日1:00 | 计算月统计数据 |
| 数据清理 | 每天3:00 | 清理过期历史数据 |
| 数据归档 | 每周日2:00 | 归档历史数据 |
| 日报生成 | 每天8:00 | 自动生成日报 |
| 周报生成 | 每周一8:30 | 自动生成周报 |
| 月报生成 | 每月1日9:00 | 自动生成月报 |
| 系统自检 | 每5分钟 | 检测系统健康状态 |
| 告警恢复检测 | 每分钟 | 检测告警是否自动恢复 |

### 2.6 缓存策略

| 缓存项 | 缓存时间 | 说明 |
|--------|----------|------|
| 用户信息 | 30分钟 | 登录用户信息 |
| 权限列表 | 10分钟 | 角色权限 |
| 点位配置 | 5分钟 | 点位基础配置 |
| 实时数据 | 实时更新 | 内存缓存 |
| 阈值配置 | 5分钟 | 告警阈值 |
| 统计数据 | 10分钟 | 汇总统计 |
| 数据字典 | 1小时 | 系统字典 |

---

## 三、前端动态化设计

### 3.1 前端架构

```
frontend/
├── public/
│   ├── sounds/              # 告警音效
│   └── images/              # 静态图片
├── src/
│   ├── api/                 # API 接口
│   │   ├── modules/         # 按模块划分
│   │   │   ├── auth.ts
│   │   │   ├── user.ts
│   │   │   ├── device.ts
│   │   │   ├── point.ts
│   │   │   ├── realtime.ts
│   │   │   ├── alarm.ts
│   │   │   ├── history.ts
│   │   │   ├── report.ts
│   │   │   ├── log.ts
│   │   │   └── config.ts
│   │   ├── request.ts       # Axios 封装
│   │   └── websocket.ts     # WebSocket 封装
│   │
│   ├── assets/              # 静态资源
│   │   ├── icons/           # SVG 图标
│   │   ├── images/          # 图片
│   │   └── styles/          # 全局样式
│   │
│   ├── components/          # 公共组件
│   │   ├── common/          # 通用组件
│   │   │   ├── DataTable.vue      # 数据表格(分页、筛选)
│   │   │   ├── SearchForm.vue     # 搜索表单
│   │   │   ├── DateRangePicker.vue# 日期范围选择
│   │   │   ├── ExportButton.vue   # 导出按钮
│   │   │   ├── StatusTag.vue      # 状态标签
│   │   │   └── ConfirmDialog.vue  # 确认对话框
│   │   │
│   │   ├── charts/          # 图表组件
│   │   │   ├── LineChart.vue      # 折线图
│   │   │   ├── BarChart.vue       # 柱状图
│   │   │   ├── PieChart.vue       # 饼图
│   │   │   ├── GaugeChart.vue     # 仪表盘
│   │   │   ├── HeatmapChart.vue   # 热力图
│   │   │   └── RealtimeChart.vue  # 实时趋势图
│   │   │
│   │   ├── monitor/         # 监控组件
│   │   │   ├── PointCard.vue      # 点位卡片
│   │   │   ├── DeviceCard.vue     # 设备卡片
│   │   │   ├── AlarmBadge.vue     # 告警徽章
│   │   │   ├── StatusPanel.vue    # 状态面板
│   │   │   ├── FloorPlan.vue      # 机房平面图
│   │   │   ├── Topology.vue       # 拓扑图
│   │   │   └── ValueDisplay.vue   # 数值显示(动画)
│   │   │
│   │   └── layout/          # 布局组件
│   │       ├── Sidebar.vue
│   │       ├── Header.vue
│   │       ├── Breadcrumb.vue
│   │       └── TabsView.vue
│   │
│   ├── composables/         # 组合式函数
│   │   ├── useWebSocket.ts        # WebSocket
│   │   ├── useRealtime.ts         # 实时数据
│   │   ├── useAlarm.ts            # 告警处理
│   │   ├── useSound.ts            # 声音播放
│   │   ├── useExport.ts           # 数据导出
│   │   ├── useChart.ts            # 图表处理
│   │   └── usePermission.ts       # 权限控制
│   │
│   ├── stores/              # Pinia 状态管理
│   │   ├── user.ts          # 用户状态
│   │   ├── realtime.ts      # 实时数据状态
│   │   ├── alarm.ts         # 告警状态
│   │   ├── app.ts           # 应用状态
│   │   └── websocket.ts     # WebSocket状态
│   │
│   ├── views/               # 页面视图
│   │   ├── login/           # 登录页
│   │   ├── dashboard/       # 监控仪表盘
│   │   │   ├── index.vue
│   │   │   ├── components/
│   │   │   │   ├── OverviewCards.vue   # 概览卡片
│   │   │   │   ├── RealtimePanel.vue   # 实时数据面板
│   │   │   │   ├── AlarmPanel.vue      # 告警面板
│   │   │   │   ├── TrendChart.vue      # 趋势图
│   │   │   │   ├── StatusMap.vue       # 状态地图
│   │   │   │   └── QuickControl.vue    # 快捷控制
│   │   │   └── hooks/
│   │   │
│   │   ├── monitor/         # 实时监控
│   │   │   ├── realtime/    # 实时数据页
│   │   │   ├── floorplan/   # 平面图监控
│   │   │   └── topology/    # 拓扑图监控
│   │   │
│   │   ├── device/          # 设备管理
│   │   ├── point/           # 点位管理
│   │   ├── alarm/           # 告警管理
│   │   │   ├── active/      # 活动告警
│   │   │   ├── history/     # 历史告警
│   │   │   ├── threshold/   # 阈值配置
│   │   │   └── statistics/  # 告警统计
│   │   │
│   │   ├── history/         # 历史数据
│   │   │   ├── query/       # 数据查询
│   │   │   ├── trend/       # 趋势分析
│   │   │   ├── compare/     # 对比分析
│   │   │   └── export/      # 数据导出
│   │   │
│   │   ├── report/          # 报表分析
│   │   │   ├── daily/       # 日报
│   │   │   ├── weekly/      # 周报
│   │   │   ├── monthly/     # 月报
│   │   │   ├── custom/      # 自定义报表
│   │   │   └── template/    # 报表模板
│   │   │
│   │   ├── log/             # 日志查询
│   │   │   ├── operation/   # 操作日志
│   │   │   ├── system/      # 系统日志
│   │   │   └── communication/# 通讯日志
│   │   │
│   │   └── settings/        # 系统设置
│   │       ├── user/        # 用户管理
│   │       ├── permission/  # 权限管理
│   │       ├── config/      # 系统配置
│   │       └── license/     # 授权管理
│   │
│   │   ├── energy/          # 用电管理 (新增)
│   │   │   ├── dashboard/   # 用电监控仪表盘
│   │   │   │   ├── index.vue
│   │   │   │   └── components/
│   │   │   │       ├── PowerOverview.vue    # 功率概览
│   │   │   │       ├── PUETrend.vue         # PUE趋势
│   │   │   │       ├── EnergyDistribution.vue # 用电分布
│   │   │   │       └── DeviceStatus.vue     # 设备状态
│   │   │   │
│   │   │   ├── statistics/  # 用电统计
│   │   │   │   ├── index.vue
│   │   │   │   └── components/
│   │   │   │       ├── EnergyChart.vue      # 用电趋势图
│   │   │   │       ├── DeviceRanking.vue    # 设备排行
│   │   │   │       └── ComparisonTable.vue  # 同环比表格
│   │   │   │
│   │   │   ├── suggestions/ # 节能建议
│   │   │   │   ├── index.vue
│   │   │   │   └── components/
│   │   │   │       ├── SuggestionCard.vue   # 建议卡片
│   │   │   │       ├── SavingStats.vue      # 节能统计
│   │   │   │       └── PotentialGauge.vue   # 潜力仪表
│   │   │   │
│   │   │   ├── config/      # 配电系统配置 (新增)
│   │   │   │   ├── transformer/             # 变压器管理
│   │   │   │   │   ├── index.vue
│   │   │   │   │   ├── TransformerList.vue
│   │   │   │   │   └── TransformerForm.vue
│   │   │   │   ├── meter-point/             # 计量点管理
│   │   │   │   │   ├── index.vue
│   │   │   │   │   ├── MeterPointList.vue
│   │   │   │   │   └── MeterPointForm.vue
│   │   │   │   ├── panel/                   # 配电柜管理
│   │   │   │   │   ├── index.vue
│   │   │   │   │   ├── PanelList.vue
│   │   │   │   │   └── PanelForm.vue
│   │   │   │   ├── circuit/                 # 配电回路管理
│   │   │   │   │   ├── index.vue
│   │   │   │   │   ├── CircuitList.vue
│   │   │   │   │   └── CircuitForm.vue
│   │   │   │   └── index.vue                # 配置Tab页入口
│   │   │   │
│   │   │   ├── topology/    # 配电拓扑图 (新增)
│   │   │   │   ├── index.vue
│   │   │   │   └── components/
│   │   │   │       ├── TopologyCanvas.vue   # 拓扑画布
│   │   │   │       ├── NodeDetail.vue       # 节点详情
│   │   │   │       └── TopologyLegend.vue   # 图例
│   │   │   │
│   │   │   ├── device/      # 用电设备管理 (新增)
│   │   │   │   ├── index.vue
│   │   │   │   └── components/
│   │   │   │       ├── DeviceList.vue       # 设备列表
│   │   │   │       ├── DeviceBasicForm.vue  # 基本信息表单
│   │   │   │       ├── PointBindingForm.vue # 点位关联表单
│   │   │   │       └── ShiftConfigForm.vue  # 负荷转移配置
│   │   │   │
│   │   │   ├── demand/      # 需量配置分析 (新增)
│   │   │   │   ├── index.vue
│   │   │   │   └── components/
│   │   │   │       ├── DemandOverview.vue   # 需量概览
│   │   │   │       ├── DemandTrend.vue      # 需量趋势
│   │   │   │       ├── ConfigAnalysis.vue   # 配置分析
│   │   │   │       └── OptimizeSuggestion.vue # 优化建议
│   │   │   │
│   │   │   ├── load-shift/  # 负荷转移分析 (新增)
│   │   │   │   ├── index.vue
│   │   │   │   └── components/
│   │   │   │       ├── PeakValleyChart.vue  # 峰谷分布图
│   │   │   │       ├── ShiftableDevices.vue # 可转移设备
│   │   │   │       ├── ShiftSuggestion.vue  # 转移建议
│   │   │   │       └── EffectSimulation.vue # 效果模拟
│   │   │   │
│   │   │   └── pricing/     # 电价配置 (新增)
│   │   │       ├── index.vue
│   │   │       └── components/
│   │   │           ├── PricingScheme.vue    # 电价方案
│   │   │           ├── TimePeriodEditor.vue # 时段编辑
│   │   │           ├── PricingChart.vue     # 24小时分布
│   │   │           └── MeterBinding.vue     # 计量点关联
│   │
│   ├── router/              # 路由配置
│   ├── utils/               # 工具函数
│   ├── types/               # TypeScript 类型
│   ├── App.vue
│   └── main.ts
│
├── package.json
├── vite.config.ts
└── tsconfig.json
```

#### 3.1.2 用电管理路由配置 (新增)

```typescript
// router/modules/energy.ts - 用电管理路由配置
import { RouteRecordRaw } from 'vue-router'

const energyRoutes: RouteRecordRaw = {
  path: '/energy',
  name: 'Energy',
  component: () => import('@/layouts/MainLayout.vue'),
  meta: { title: '用电管理', icon: 'Lightning' },
  children: [
    {
      path: 'dashboard',
      name: 'EnergyDashboard',
      component: () => import('@/views/energy/dashboard/index.vue'),
      meta: { title: '用电监控', icon: 'Dashboard' }
    },
    {
      path: 'statistics',
      name: 'EnergyStatistics',
      component: () => import('@/views/energy/statistics/index.vue'),
      meta: { title: '用电统计', icon: 'DataLine' }
    },
    {
      path: 'suggestions',
      name: 'EnergySuggestions',
      component: () => import('@/views/energy/suggestions/index.vue'),
      meta: { title: '节能建议', icon: 'Opportunity' }
    },
    // ==================== 配置管理 (新增) ====================
    {
      path: 'config',
      name: 'EnergyConfig',
      component: () => import('@/views/energy/config/index.vue'),
      meta: { title: '配电配置', icon: 'Setting' },
      children: [
        {
          path: 'transformer',
          name: 'TransformerConfig',
          component: () => import('@/views/energy/config/transformer/index.vue'),
          meta: { title: '变压器管理' }
        },
        {
          path: 'meter-point',
          name: 'MeterPointConfig',
          component: () => import('@/views/energy/config/meter-point/index.vue'),
          meta: { title: '计量点管理' }
        },
        {
          path: 'panel',
          name: 'PanelConfig',
          component: () => import('@/views/energy/config/panel/index.vue'),
          meta: { title: '配电柜管理' }
        },
        {
          path: 'circuit',
          name: 'CircuitConfig',
          component: () => import('@/views/energy/config/circuit/index.vue'),
          meta: { title: '配电回路管理' }
        }
      ]
    },
    {
      path: 'topology',
      name: 'EnergyTopology',
      component: () => import('@/views/energy/topology/index.vue'),
      meta: { title: '配电拓扑', icon: 'Connection' }
    },
    {
      path: 'device',
      name: 'PowerDevice',
      component: () => import('@/views/energy/device/index.vue'),
      meta: { title: '用电设备', icon: 'Monitor' }
    },
    // ==================== 分析功能 (新增) ====================
    {
      path: 'demand',
      name: 'DemandAnalysis',
      component: () => import('@/views/energy/demand/index.vue'),
      meta: { title: '需量分析', icon: 'TrendCharts' }
    },
    {
      path: 'load-shift',
      name: 'LoadShiftAnalysis',
      component: () => import('@/views/energy/load-shift/index.vue'),
      meta: { title: '负荷转移', icon: 'Switch' }
    },
    {
      path: 'pricing',
      name: 'PricingConfig',
      component: () => import('@/views/energy/pricing/index.vue'),
      meta: { title: '电价配置', icon: 'Money' }
    }
  ]
}

export default energyRoutes
```

#### 3.1.3 用电管理侧边菜单结构 (新增)

```
用电管理
├── 用电监控        /energy/dashboard       (仪表盘，实时功率/PUE/电费概览)
├── 用电统计        /energy/statistics      (历史用电统计分析)
├── 节能建议        /energy/suggestions     (智能节能建议)
├── ─────────────── 配置管理 ───────────────
├── 配电配置        /energy/config          (Tab页：变压器/计量点/配电柜/回路)
│   ├── 变压器      /energy/config/transformer
│   ├── 计量点      /energy/config/meter-point
│   ├── 配电柜      /energy/config/panel
│   └── 配电回路    /energy/config/circuit
├── 配电拓扑        /energy/topology        (可视化配电系统拓扑图)
├── 用电设备        /energy/device          (设备管理，点位关联，负荷转移配置)
├── ─────────────── 分析功能 ───────────────
├── 需量分析        /energy/demand          (需量历史、配置合理性分析)
├── 负荷转移        /energy/load-shift      (峰谷分析、转移建议、效果模拟)
└── 电价配置        /energy/pricing         (电价方案、时段配置、计量点关联)
```

### 3.2 动态化特性设计

#### 3.2.1 实时数据刷新机制

```typescript
// WebSocket 实时推送 + 定时轮询兜底
interface RealtimeStrategy {
  // 主要方式: WebSocket 实时推送
  websocket: {
    url: '/ws/realtime',
    reconnect: true,
    heartbeat: 30000,  // 心跳30秒
  },
  // 备用方式: HTTP 轮询
  polling: {
    enabled: true,
    interval: 5000,    // 5秒轮询
    fallbackOnly: true // 仅WebSocket断开时启用
  },
  // 数据更新策略
  update: {
    debounce: 100,     // 防抖100ms
    batch: true,       // 批量更新
    animation: true    // 数值变化动画
  }
}
```

#### 3.2.2 数值动画效果

```vue
<!-- 数值显示组件 - 带动画 -->
<template>
  <div class="value-display" :class="statusClass">
    <transition-group name="digit">
      <span v-for="(digit, index) in digits" :key="index + digit">
        {{ digit }}
      </span>
    </transition-group>
    <span class="unit">{{ unit }}</span>
    <span class="trend" v-if="trend">
      <el-icon :class="trendClass">
        <component :is="trendIcon" />
      </el-icon>
    </span>
  </div>
</template>

<!-- 支持的动画效果 -->
- 数字滚动动画
- 颜色渐变（正常→告警）
- 闪烁提醒
- 趋势箭头（上升/下降）
```

#### 3.2.3 告警动态效果

```typescript
// 告警视觉效果配置
interface AlarmVisualConfig {
  levels: {
    critical: {
      color: '#ff4d4f',
      animation: 'flash',      // 闪烁
      sound: 'alarm_critical.mp3',
      soundLoop: true,
      notification: true
    },
    major: {
      color: '#faad14',
      animation: 'pulse',      // 脉冲
      sound: 'alarm_major.mp3',
      soundLoop: false,
      notification: true
    },
    minor: {
      color: '#1890ff',
      animation: 'none',
      sound: 'alarm_minor.mp3',
      soundLoop: false,
      notification: false
    },
    info: {
      color: '#8c8c8c',
      animation: 'none',
      sound: null,
      notification: false
    }
  }
}

// 告警弹窗通知
- 右下角滑出通知
- 支持多条堆叠
- 点击跳转到告警详情
- 确认后消失
```

#### 3.2.4 机房平面图

```typescript
// 平面图功能
interface FloorPlanFeatures {
  // 基础功能
  background: string,         // 底图(SVG/PNG)
  zoomable: boolean,          // 缩放
  pannable: boolean,          // 平移

  // 设备展示
  devices: {
    icon: string,             // 设备图标
    position: {x, y},         // 位置坐标
    status: 'online'|'offline'|'alarm',
    tooltip: boolean,         // 鼠标悬停提示
    clickable: boolean        // 点击查看详情
  }[],

  // 实时数据展示
  dataPoints: {
    pointId: number,
    position: {x, y},
    showValue: boolean,       // 显示数值
    showStatus: boolean,      // 显示状态
    animate: boolean          // 动画效果
  }[],

  // 区域划分
  areas: {
    name: string,
    polygon: Point[],         // 多边形顶点
    fillColor: string,
    statusBinding: string     // 绑定状态
  }[]
}
```

#### 3.2.5 动态图表

```typescript
// 实时趋势图配置
interface RealtimeChartConfig {
  // 数据窗口
  window: {
    duration: 3600,           // 显示最近1小时
    points: 360,              // 最多360个点
    interval: 10              // 10秒一个点
  },

  // 实时更新
  realtime: {
    enabled: true,
    smooth: true,             // 平滑过渡
    animation: 300            // 动画时长ms
  },

  // 阈值线
  thresholds: {
    show: true,
    high: { value: 28, color: '#ff4d4f', style: 'dashed' },
    low: { value: 18, color: '#1890ff', style: 'dashed' }
  },

  // 交互
  interaction: {
    tooltip: true,            // 数据提示
    zoom: true,               // 区域缩放
    dataZoom: true,           // 数据缩放条
    brush: true               // 框选查看
  }
}
```

### 3.3 页面设计详情

#### 3.3.1 监控仪表盘布局

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  算力中心智能监控系统          [告警: 🔴2 🟡5]  [全屏]  [刷新]  [admin ▼]  [退出] │
├─────────┬───────────────────────────────────────────────────────────────────┤
│         │  ┌─────────┬─────────┬─────────┬─────────┬─────────┬─────────┐   │
│ ▶ 监控中心│  │  温度   │  湿度   │  电力   │  UPS    │  空调   │  告警   │   │
│   仪表盘 │  │ 24.5℃  │ 45%RH  │ 85kW   │ 98%    │ 2运行  │ 7条    │   │
│   实时监控│  │ [正常]  │ [正常]  │ [正常]  │ [正常]  │ [正常]  │ [警告]  │   │
│   平面图 │  └─────────┴─────────┴─────────┴─────────┴─────────┴─────────┘   │
│   拓扑图 │                                                                   │
│         │  ┌─────────────────────────────┬─────────────────────────────┐   │
│ ▶ 设备管理│  │                             │                             │   │
│         │  │      温度趋势 (实时)          │       电力趋势 (实时)        │   │
│ ▶ 告警中心│  │    ╱╲    ╱╲                 │      ╱╲                     │   │
│   活动告警│  │   ╱  ╲  ╱  ╲   ←28℃        │     ╱  ╲                    │   │
│   历史告警│  │  ╱    ╲╱    ╲               │    ╱    ╲                   │   │
│   阈值配置│  │ ╱            ╲              │   ╱      ╲                  │   │
│         │  │╱              ╲  →18℃       │  ╱        ╲                 │   │
│ ▶ 历史查询│  │ 09:00   10:00   11:00       │ 09:00   10:00   11:00       │   │
│   数据查询│  └─────────────────────────────┴─────────────────────────────┘   │
│   趋势分析│                                                                   │
│   数据导出│  ┌─────────────────────────────┬─────────────────────────────┐   │
│         │  │      设备状态分布             │        最新告警              │   │
│ ▶ 报表分析│  │   ┌────┐                    │ 🔴 A1区温度过高 29.5℃       │   │
│         │  │   │正常│ 45                  │    10:25:30 [确认]          │   │
│ ▶ 系统设置│  │   │告警│ 5                   │ 🟡 UPS-1负载率偏高 82%       │   │
│         │  │   │离线│ 2                   │    10:20:15 [确认]          │   │
│         │  │   └────┘                    │ 🟡 A2区湿度偏低 28%          │   │
│         │  │    [饼图]                    │    10:15:00 [确认]          │   │
│         │  └─────────────────────────────┴─────────────────────────────┘   │
└─────────┴───────────────────────────────────────────────────────────────────┘
```

#### 3.3.2 历史数据查询页面

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 历史数据查询                                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ 查询条件                                                                │ │
│ │ 点位: [A1区温度 ▼]  时间范围: [2026-01-12 00:00] ~ [2026-01-13 00:00]  │ │
│ │ 聚合: [原始数据 ▼]  数据类型: [全部 ▼]                                   │ │
│ │                                            [查询] [导出Excel] [导出CSV] │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ 趋势图                                                   [放大] [下载]   │ │
│ │ 30℃ ┬──────────────────────────────────────────────────────────────┐   │ │
│ │     │                    ╱╲      ╱╲                                │   │ │
│ │ 25℃ ┼───────╱╲──────────╱──╲────╱──╲────────────────────── 上限28℃ │   │ │
│ │     │      ╱  ╲        ╱    ╲  ╱    ╲                              │   │ │
│ │ 20℃ ┼─────╱────╲──────╱──────╲╱──────╲───────────────────── 下限18℃ │   │ │
│ │     │    ╱      ╲    ╱                                             │   │ │
│ │ 15℃ ┼───╱────────╲──╱──────────────────────────────────────────────│   │ │
│ │     └──┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴───┘   │ │
│ │       00:00  02:00  04:00  06:00  08:00  10:00  12:00  14:00  16:00     │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌───────────────────────────┐ ┌───────────────────────────────────────────┐ │
│ │ 统计信息                   │ │ 数据列表                         共1440条 │ │
│ │ 最大值: 29.5℃ (10:25)     │ │ 时间           数值    状态    质量       │ │
│ │ 最小值: 18.2℃ (05:30)     │ │ 01-13 10:25   29.5℃  告警    良好       │ │
│ │ 平均值: 23.8℃             │ │ 01-13 10:24   28.2℃  正常    良好       │ │
│ │ 标准差: 2.3                │ │ 01-13 10:23   27.8℃  正常    良好       │ │
│ │ 超限次数: 3                │ │ ...                                      │ │
│ │ 超限时长: 15分钟           │ │                    [< 1 2 3 ... 144 >]   │ │
│ └───────────────────────────┘ └───────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 四、历史记录与查询设计

### 4.1 历史数据存储策略

| 数据类型 | 存储周期 | 采样间隔 | 存储策略 |
|----------|----------|----------|----------|
| 原始数据 | 7天 | 按采集周期 | 实时存储 |
| 分钟数据 | 30天 | 1分钟 | 聚合（最大/最小/平均） |
| 小时数据 | 1年 | 1小时 | 聚合 |
| 日数据 | 永久 | 1天 | 聚合 |

### 4.2 查询功能清单

#### 4.2.1 历史数据查询

- 单点位历史查询
- 多点位对比查询
- 按时间范围查询
- 按数据质量筛选
- 数据聚合查询（分钟/小时/天）
- 数据插值查询（填补缺失）
- 统计分析（最大/最小/平均/标准差）

#### 4.2.2 告警历史查询

- 按时间范围查询
- 按告警级别筛选
- 按点位/设备筛选
- 按状态筛选（全部/已确认/已解决）
- 告警持续时长统计
- 高频告警点位分析
- 告警趋势分析

#### 4.2.3 操作日志查询

- 按时间范围查询
- 按用户筛选
- 按操作类型筛选
- 按模块筛选
- 关键词搜索
- 操作轨迹追溯

### 4.3 报表功能设计

#### 4.3.1 标准报表

| 报表类型 | 生成周期 | 内容 |
|----------|----------|------|
| 日报 | 每天 | 当日监控数据汇总、告警统计、异常事件 |
| 周报 | 每周 | 周度趋势、同比环比、运维建议 |
| 月报 | 每月 | 月度总结、设备可用性、能耗分析 |

#### 4.3.2 自定义报表

- 自选点位组合
- 自定义时间范围
- 自定义图表类型
- 报表模板保存
- 定时生成与发送

### 4.4 数据导出功能

| 导出格式 | 适用场景 | 功能特点 |
|----------|----------|----------|
| Excel (.xlsx) | 办公分析 | 格式化、图表、多Sheet |
| CSV | 数据交换 | 通用格式、大数据量 |
| PDF | 正式报告 | 排版美观、带图表 |
| JSON | 系统对接 | 结构化数据 |

---

## 五、用电管理功能设计

### 5.1 配电系统架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              配电系统架构图                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│    ┌────────────────┐                                                       │
│    │   市电输入      │                                                       │
│    │   380V/50Hz    │                                                       │
│    └───────┬────────┘                                                       │
│            │                                                                │
│            ▼                                                                │
│    ┌────────────────┐     电压、电流、功率、电量                             │
│    │   总配电柜      │◄────── 电力参数监测                                   │
│    │   (PDU-Main)   │                                                       │
│    └───────┬────────┘                                                       │
│            │                                                                │
│    ┌───────┼───────┬───────────────┬───────────────┐                       │
│    │       │       │               │               │                       │
│    ▼       ▼       ▼               ▼               ▼                       │
│ ┌──────┐┌──────┐┌──────┐      ┌──────┐       ┌──────┐                      │
│ │UPS-1 ││UPS-2 ││空调1  │      │空调2  │       │照明   │                      │
│ │20kVA ││20kVA ││12kW  │      │12kW  │       │2kW   │                      │
│ └──┬───┘└──┬───┘└──────┘      └──────┘       └──────┘                      │
│    │       │                                                                │
│    ▼       ▼                                                                │
│ ┌────────────────┐                                                          │
│ │  IT设备负载     │                                                          │
│ │  服务器/网络等   │                                                          │
│ └────────────────┘                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 电力参数监测

#### 5.2.1 基础电力参数

| 参数类型 | 采集项 | 单位 | 精度 | 告警阈值 |
|----------|--------|------|------|----------|
| 电压 | 三相电压 (Ua/Ub/Uc) | V | 0.1V | 高:242V 低:198V |
| 电流 | 三相电流 (Ia/Ib/Ic) | A | 0.1A | 过载:额定×1.1 |
| 功率 | 有功功率/无功功率/视在功率 | kW/kVar/kVA | 0.01 | - |
| 功率因数 | 总功率因数 | - | 0.01 | 低:0.85 |
| 频率 | 电网频率 | Hz | 0.01Hz | 高:50.5 低:49.5 |
| 电能 | 累计电量 | kWh | 0.01kWh | - |
| 谐波 | 电压/电流谐波率 | % | 0.1% | 高:5% |

#### 5.2.2 PUE (能效比) 计算

```
PUE = 机房总能耗 / IT设备能耗

其中：
- 机房总能耗 = 总配电柜电量
- IT设备能耗 = UPS输出电量

理想PUE参考值：
- PUE < 1.4  : 优秀
- PUE 1.4~1.6: 良好
- PUE 1.6~2.0: 一般
- PUE > 2.0  : 较差
```

### 5.3 电费结构配置（V2.2 重新设计）

#### 5.3.1 电费构成解析（基于实际电费清单）

根据工商业电费清单分析，电费由以下部分构成：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          工商业电费构成结构图                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  工商业电费 (总计)                                                           │
│  ├── ① 市场化购电电费                                                        │
│  │   ├── 零售交易电费 (电量 × 零售单价)                                       │
│  │   ├── 容量补偿电费 (电量 × 容量补偿单价)                                   │
│  │   └── 偏差调整费用 (优发优购曲线匹配偏差)                                   │
│  │                                                                          │
│  ├── ② 上网环节线损费用 (电量 × 线损费率)                                     │
│  │                                                                          │
│  ├── ③ 输配电费                                                              │
│  │   ├── 电量电费 (电量 × 输配电单价)                                         │
│  │   ├── 需量电费 (申报需量 × 需量单价)                                       │
│  │   └── 需量折扣 (负折扣，约需量电费的10%)                                   │
│  │                                                                          │
│  ├── ④ 系统运行费                                                            │
│  │   ├── 抽水蓄能容量电费                                                    │
│  │   ├── 煤电容量电费                                                        │
│  │   ├── 线损代理采购损益 (可正可负)                                          │
│  │   ├── 电价交叉补贴损益 (可正可负)                                          │
│  │   └── 容量补偿峰谷损益分摊                                                 │
│  │                                                                          │
│  └── ⑤ 政府性基金及附加                                                       │
│      ├── 可再生能源电价附加                                                   │
│      ├── 大中型水库移民后期扶持基金                                           │
│      └── 其他政府性基金                                                       │
│                                                                             │
│  功率因数调整电费 (奖励/惩罚，可正可负)                                        │
│  └── 功率因数 ≥ 0.90 时奖励(负值)，< 0.90 时惩罚(正值)                        │
│                                                                             │
│  合计 = 工商业电费 + 功率因数调整电费                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

##### 5.3.1.1 配电系统拓扑结构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         配电系统拓扑关系图                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         变压器层 (Transformer)                        │   │
│  │  ┌─────────────────┐     ┌─────────────────┐                        │   │
│  │  │ 变压器1 (1#)     │     │ 变压器2 (2#)     │                        │   │
│  │  │ 容量: 630kVA     │     │ 容量: 400kVA     │                        │   │
│  │  │ 电压: 10kV/0.4kV │     │ 电压: 10kV/0.4kV │                        │   │
│  │  │ 计量点: M001     │     │ 计量点: M002     │                        │   │
│  │  └────────┬────────┘     └────────┬────────┘                        │   │
│  └───────────┼───────────────────────┼─────────────────────────────────┘   │
│              │                       │                                     │
│  ┌───────────┼───────────────────────┼─────────────────────────────────┐   │
│  │           ▼                       ▼        计量点层 (Meter Point)     │   │
│  │  ┌─────────────────┐     ┌─────────────────┐                        │   │
│  │  │ 计量点 M001      │     │ 计量点 M002      │                        │   │
│  │  │ 电表号: 001234   │     │ 电表号: 001235   │                        │   │
│  │  │ 倍率: CT400/5    │     │ 倍率: CT200/5    │                        │   │
│  │  │ 申报需量: 500kW  │     │ 申报需量: 300kW  │                        │   │
│  │  └────────┬────────┘     └────────┬────────┘                        │   │
│  └───────────┼───────────────────────┼─────────────────────────────────┘   │
│              │                       │                                     │
│  ┌───────────┼───────────────────────┼─────────────────────────────────┐   │
│  │           ▼                       ▼         配电柜层 (Distribution)    │   │
│  │  ┌─────────────────┐     ┌─────────────────┐                        │   │
│  │  │ 总配电柜 PDU-1   │     │ 总配电柜 PDU-2   │                        │   │
│  │  │ 容量: 630A       │     │ 容量: 400A       │                        │   │
│  │  │ 关联计量点: M001 │     │ 关联计量点: M002 │                        │   │
│  │  └──┬────────┬─────┘     └──┬────────┬─────┘                        │   │
│  │     │        │              │        │                              │   │
│  │     ▼        ▼              ▼        ▼                              │   │
│  │  ┌──────┐ ┌──────┐      ┌──────┐ ┌──────┐                          │   │
│  │  │回路1 │ │回路2 │      │回路1 │ │回路2 │                          │   │
│  │  │UPS   │ │空调  │      │IT设备│ │照明  │                          │   │
│  │  └──┬───┘ └──┬───┘      └──┬───┘ └──┬───┘                          │   │
│  └─────┼────────┼─────────────┼────────┼───────────────────────────────┘   │
│        │        │             │        │                                   │
│  ┌─────┼────────┼─────────────┼────────┼───────────────────────────────┐   │
│  │     ▼        ▼             ▼        ▼          用电设备层 (Device)     │   │
│  │  ┌──────────────────────────────────────────────────────────────┐   │   │
│  │  │  UPS-1    空调-1    空调-2    服务器    存储    照明系统      │   │   │
│  │  │  30kVA    12kW      12kW      50kW     20kW    5kW          │   │   │
│  │  │  可转移:否 可转移:是  可转移:是  可转移:否  可转移:否 可转移:是   │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

##### 5.3.1.2 计量点与变压器关系数据模型

```typescript
// 变压器配置
interface Transformer {
  id: number
  transformer_code: string          // 变压器编码 如"TR-001"
  transformer_name: string          // 变压器名称 如"1#变压器"
  rated_capacity: number            // 额定容量 kVA
  voltage_high: number              // 高压侧电压 kV (如10)
  voltage_low: number               // 低压侧电压 kV (如0.4)
  connection_type: string           // 接线组别 如"Dyn11"
  efficiency: number                // 效率 % (典型值98-99)
  no_load_loss: number              // 空载损耗 kW
  load_loss: number                 // 负载损耗 kW
  impedance_voltage: number         // 阻抗电压 %
  install_date: Date
  location: string                  // 安装位置
  status: 'running' | 'standby' | 'maintenance' | 'fault'
  is_enabled: boolean
}

// 计量点配置
interface MeterPoint {
  id: number
  meter_code: string                // 计量点编码 如"M001"
  meter_name: string                // 计量点名称 如"1#变计量"
  meter_no: string                  // 电表号
  transformer_id: number            // 关联变压器ID

  // 计量参数
  ct_ratio: string                  // 电流互感器倍率 如"400/5"
  pt_ratio: string                  // 电压互感器倍率 如"10000/100"
  multiplier: number                // 综合倍率

  // 需量配置
  declared_demand: number           // 申报需量 kW 或 kVA
  demand_type: 'kW' | 'kVA'         // 需量类型
  demand_period: number             // 需量计算周期 分钟 (通常15)

  // 电费户号关联
  customer_no: string               // 供电局户号
  customer_name: string             // 户名

  // 分时电价配置引用
  pricing_config_id: number         // 电价配置ID

  status: 'normal' | 'fault' | 'offline'
  is_enabled: boolean
}

// 配电柜/开关柜
interface DistributionPanel {
  id: number
  panel_code: string                // 配电柜编码 如"PDU-001"
  panel_name: string                // 配电柜名称
  panel_type: 'main' | 'sub' | 'ups_input' | 'ups_output'  // 类型
  rated_current: number             // 额定电流 A
  rated_voltage: number             // 额定电压 V

  // 上下级关系
  parent_panel_id?: number          // 上级配电柜ID
  transformer_id?: number           // 关联变压器ID (仅主配电柜)
  meter_point_id?: number           // 关联计量点ID

  // 位置
  location: string
  area_code: string

  status: 'running' | 'fault' | 'maintenance'
  is_enabled: boolean
}

// 配电回路
interface DistributionCircuit {
  id: number
  circuit_code: string              // 回路编码 如"C001"
  circuit_name: string              // 回路名称 如"UPS输入回路"
  panel_id: number                  // 所属配电柜ID

  // 回路参数
  rated_current: number             // 额定电流 A
  breaker_type: string              // 断路器型号
  breaker_rating: number            // 断路器额定值 A

  // 负载类型
  load_type: 'ups' | 'hvac' | 'it_equipment' | 'lighting' | 'general' | 'emergency'

  // 是否可转移负荷
  is_shiftable: boolean             // 是否可转移
  shift_priority: number            // 转移优先级 (1最高)
  min_runtime_hours?: number        // 最小运行时长要求

  is_enabled: boolean
}
```

##### 5.3.1.3 设备-计量点-功率曲线关联

```typescript
// 用电设备扩展 (与计量点关联)
interface PowerDeviceExtended {
  id: number
  device_code: string
  device_name: string
  device_type: 'UPS' | 'HVAC' | 'IT_SERVER' | 'IT_STORAGE' | 'LIGHTING' | 'PUMP' | 'OTHER'

  // 配电关系
  circuit_id: number                // 所属回路ID
  meter_point_id: number            // 关联计量点ID (通过回路-配电柜-计量点链)

  // 功率参数
  rated_power: number               // 额定功率 kW
  rated_current: number             // 额定电流 A
  power_factor: number              // 额定功率因数
  efficiency: number                // 设备效率 %

  // 负荷特性
  load_profile: LoadProfile         // 负荷曲线类型
  is_critical: boolean              // 是否关键负荷 (不可中断)

  // 可转移性配置
  is_shiftable: boolean             // 是否可转移
  shiftable_power_ratio: number     // 可转移功率比例 (0-1)
  shift_constraints: ShiftConstraints  // 转移约束条件

  // 运行参数
  avg_load_rate: number             // 平均负载率 %
  peak_load_rate: number            // 峰值负载率 %
  daily_energy: number              // 日均用电量 kWh

  is_enabled: boolean
}

// 负荷曲线类型
interface LoadProfile {
  profile_type: 'constant' | 'variable' | 'scheduled' | 'demand_response'

  // 典型日负荷曲线 (24小时)
  hourly_load_factors: number[]     // 每小时负载系数 (0-1), 长度24

  // 周负荷特征
  weekday_factor: number            // 工作日系数
  weekend_factor: number            // 周末系数

  // 季节系数
  summer_factor: number             // 夏季系数
  winter_factor: number             // 冬季系数
}

// 转移约束条件
interface ShiftConstraints {
  // 时间约束
  allowed_shift_hours: number[]     // 允许转移的时段 [0-23]
  forbidden_shift_hours: number[]   // 禁止转移的时段
  min_continuous_runtime: number    // 最小连续运行时间 小时
  max_shift_duration: number        // 最大转移持续时间 小时

  // 功率约束
  min_power: number                 // 最低运行功率 kW
  max_ramp_rate: number             // 最大爬坡速率 kW/min

  // 业务约束
  shift_notice_time: number         // 转移提前通知时间 分钟
  requires_manual_approval: boolean // 是否需要人工确认
}
```

##### 5.3.1.4 功率曲线与用电分析

```typescript
// 实时功率数据 (每分钟/每15分钟采集)
interface PowerCurveData {
  id: number
  meter_point_id: number            // 计量点ID
  device_id?: number                // 设备ID (可选，设备级监测时)
  timestamp: Date

  // 功率数据
  active_power: number              // 有功功率 kW
  reactive_power: number            // 无功功率 kVar
  apparent_power: number            // 视在功率 kVA
  power_factor: number              // 功率因数

  // 电能数据
  cumulative_energy: number         // 累计电量 kWh
  incremental_energy: number        // 增量电量 kWh (本周期)

  // 需量数据
  demand_15min: number              // 15分钟需量 kW
  demand_rolling: number            // 滑动窗口需量 kW

  // 分时标识
  time_period: 'peak' | 'flat' | 'valley' | 'sharp'  // 峰平谷尖
}

// 设备功率转移分析结果
interface DeviceShiftAnalysis {
  device_id: number
  device_name: string
  device_type: string
  meter_point_id: number

  // 当前用电分析
  current_load_distribution: {
    peak_energy: number             // 峰时电量 kWh
    flat_energy: number             // 平时电量 kWh
    valley_energy: number           // 谷时电量 kWh
    sharp_energy: number            // 尖峰电量 kWh
    peak_ratio: number              // 峰时占比
  }

  // 可转移量分析
  shiftable_analysis: {
    is_shiftable: boolean           // 是否可转移
    shiftable_power: number         // 可转移功率 kW
    shiftable_energy_daily: number  // 日可转移电量 kWh

    // 推荐转移时段
    recommended_shift_from: number[] // 从这些时段转移 [小时]
    recommended_shift_to: number[]   // 转移到这些时段 [小时]

    // 转移约束
    constraints_summary: string      // 约束条件摘要
  }

  // 转移效益预估
  shift_benefit: {
    daily_cost_saving: number       // 日节省电费 元
    monthly_cost_saving: number     // 月节省电费 元
    yearly_cost_saving: number      // 年节省电费 元
    peak_shaving_kw: number         // 削峰量 kW
  }

  // 实施建议
  implementation: {
    difficulty: 'easy' | 'medium' | 'hard'
    steps: string[]
    risks: string[]
    prerequisites: string[]
  }
}
```

##### 5.3.1.5 需量配置合理性分析

```typescript
// 需量分析上下文
interface DemandAnalysisContext {
  meter_point_id: number
  analysis_period: {
    start: Date
    end: Date
  }

  // 申报需量配置
  declared_demand: number           // 当前申报需量 kW/kVA
  demand_type: 'kW' | 'kVA'
  demand_price: number              // 需量电价 元/kW·月

  // 历史需量数据
  historical_demands: {
    month: string                   // YYYY-MM
    max_demand: number              // 当月最大需量
    avg_demand: number              // 当月平均需量
    demand_95th: number             // 95%分位数需量
    over_declared_times: number     // 超申报次数
    demand_cost: number             // 需量电费
  }[]

  // 需量超限记录
  over_demand_events: {
    timestamp: Date
    demand_value: number
    over_amount: number             // 超出量
    duration_minutes: number        // 持续时间
    contributing_devices: string[]  // 贡献设备
  }[]
}

// 需量配置合理性分析结果
interface DemandConfigAnalysis {
  meter_point_id: number
  meter_name: string
  analysis_date: Date

  // 当前配置评估
  current_config: {
    declared_demand: number
    utilization_rate: number        // 利用率 = 实际最大/申报
    status: 'optimal' | 'too_high' | 'too_low' | 'critical'
    status_description: string
  }

  // 历史统计
  historical_stats: {
    max_demand_12m: number          // 12个月最大需量
    avg_max_demand_12m: number      // 12个月平均最大需量
    std_dev_demand: number          // 需量标准差
    demand_95th: number             // 95%分位数
    over_declared_count: number     // 超申报次数
    over_declared_penalty: number   // 超申报罚款 元
  }

  // 优化建议
  optimization: {
    recommended_demand: number      // 建议申报需量
    optimization_type: 'reduce' | 'increase' | 'maintain'

    // 效益分析
    current_annual_cost: number     // 当前年度需量电费
    optimized_annual_cost: number   // 优化后年度需量电费
    annual_saving: number           // 年节省金额

    // 风险评估
    risk_level: 'low' | 'medium' | 'high'
    risk_description: string
    safety_margin: number           // 安全裕度 %
  }

  // 削峰措施建议
  peak_shaving: {
    needed: boolean                 // 是否需要削峰
    target_reduction: number        // 目标削减量 kW

    measures: {
      measure_type: string          // 措施类型
      description: string           // 措施描述
      reduction_potential: number   // 削减潜力 kW
      implementation_cost: number   // 实施成本
      payback_months: number        // 回收期
    }[]
  }

  // 关联设备需量贡献分析
  device_contribution: {
    device_id: number
    device_name: string
    device_type: string
    contribution_to_peak: number    // 对峰值需量贡献 kW
    contribution_ratio: number      // 贡献比例 %
    is_controllable: boolean        // 是否可控
    shift_potential: number         // 转移潜力 kW
  }[]
}
```

##### 5.3.1.6 综合分析服务接口

```typescript
// 电费综合分析服务
interface ElectricityBillAnalysisService {

  // 1. 获取配电系统拓扑
  getDistributionTopology(): Promise<{
    transformers: Transformer[]
    meterPoints: MeterPoint[]
    panels: DistributionPanel[]
    circuits: DistributionCircuit[]
    devices: PowerDeviceExtended[]
  }>

  // 2. 获取设备-计量点-变压器关联关系
  getDeviceMeterRelation(deviceId: number): Promise<{
    device: PowerDeviceExtended
    circuit: DistributionCircuit
    panel: DistributionPanel
    meterPoint: MeterPoint
    transformer: Transformer
  }>

  // 3. 获取功率曲线数据
  getPowerCurveData(params: {
    meterPointId?: number
    deviceId?: number
    startTime: Date
    endTime: Date
    interval: '1min' | '15min' | '1hour'
  }): Promise<PowerCurveData[]>

  // 4. 分析设备功率转移潜力
  analyzeDeviceShiftPotential(params: {
    meterPointId: number
    analysisDate: Date
    pricingConfig: ElectricityPricingConfig
  }): Promise<DeviceShiftAnalysis[]>

  // 5. 分析需量配置合理性
  analyzeDemandConfig(params: {
    meterPointId: number
    analysisMonths: number  // 分析历史月数
  }): Promise<DemandConfigAnalysis>

  // 6. 生成综合电费优化报告
  generateOptimizationReport(params: {
    meterPointIds: number[]
    analysisDate: Date
  }): Promise<{
    meterAnalysis: DemandConfigAnalysis[]
    deviceShiftAnalysis: DeviceShiftAnalysis[]
    totalSavingPotential: number
    prioritizedRecommendations: string[]
  }>
}
```

##### 5.3.1.7 典型分析场景示例

**场景1: 空调系统负荷转移分析**
```
输入:
- 设备: 精密空调×4台, 单台额定功率12kW
- 当前运行模式: 24小时连续运行
- 峰时电价: 1.2元/kWh, 谷时电价: 0.4元/kWh

分析过程:
1. 获取空调历史功率曲线
2. 分析空调负荷特性 (受室外温度影响)
3. 识别可转移时段 (凌晨低负荷期间可适当降低设定温度储冷)

输出:
- 可转移电量: 约20kWh/日 (利用建筑热惯性)
- 转移时段: 峰时(10:00-12:00)部分负荷转移至谷时(01:00-06:00)
- 年节省: 约 20 × (1.2-0.4) × 365 = ¥5,840
```

**场景2: 需量配置优化分析**
```
输入:
- 计量点M001, 申报需量500kW
- 近12个月实际最大需量: 320kW~410kW
- 需量电价: 38元/kW·月

分析过程:
1. 计算需量利用率: 410/500 = 82%
2. 分析95%分位数需量: 385kW
3. 考虑安全裕度10%: 385 × 1.1 = 424kW

输出:
- 建议申报需量: 430kW (四舍五入)
- 需量费用变化: (500-430) × 38 × 12 = ¥31,920/年
- 风险评估: 低风险 (95%分位数+15%裕度)
```

#### 5.3.2 电费配置数据模型

```typescript
// 电费配置主表 - 支持不同地区不同配置
interface ElectricityBillConfig {
  id: number
  config_name: string              // 配置名称，如"山东省大工业用电"
  region_code: string              // 地区代码，如"370000"
  voltage_level: string            // 电压等级，如"110kV", "10kV", "380V"
  customer_type: string            // 用电类别，如"大工业用电", "一般工商业"
  effective_date: Date             // 生效日期
  expire_date?: Date               // 失效日期
  is_active: boolean
  created_at: Date
  updated_at: Date
}

// 电费项目配置 - 可灵活配置各类费用项
interface BillItemConfig {
  id: number
  config_id: number                // 关联电费配置
  category: BillCategory           // 费用大类
  item_code: string                // 费用项编码
  item_name: string                // 费用项名称
  calc_type: CalcType              // 计算方式
  unit_price?: number              // 单价
  rate?: number                    // 费率
  fixed_amount?: number            // 固定金额
  formula?: string                 // 自定义公式
  sort_order: number               // 显示顺序
  is_enabled: boolean
}

// 费用大类
enum BillCategory {
  MARKET_PURCHASE = 'market_purchase',        // 市场化购电电费
  GRID_LOSS = 'grid_loss',                    // 上网环节线损
  TRANSMISSION = 'transmission',               // 输配电费
  SYSTEM_OPERATION = 'system_operation',       // 系统运行费
  GOVERNMENT_FUND = 'government_fund',         // 政府性基金
  POWER_FACTOR_ADJ = 'power_factor_adj'        // 功率因数调整
}

// 计算方式
enum CalcType {
  ENERGY_BASED = 'energy_based',              // 按电量计算
  DEMAND_BASED = 'demand_based',              // 按需量计算
  RATE_BASED = 'rate_based',                  // 按费率计算
  FIXED = 'fixed',                            // 固定金额
  FORMULA = 'formula'                         // 自定义公式
}

// 分时电价配置
interface TimeOfUsePricing {
  id: number
  config_id: number                // 关联电费配置
  period_type: 'peak' | 'high' | 'normal' | 'valley'  // 尖峰/峰/平/谷
  period_name: string              // 时段名称
  start_time: string               // 开始时间 HH:MM
  end_time: string                 // 结束时间 HH:MM
  price_multiplier: number         // 价格系数 (相对于平时电价)
  months?: number[]                // 适用月份 (可选，某些地区夏季/冬季不同)
  weekdays?: number[]              // 适用星期 (可选)
}

// 需量电费配置
interface DemandChargeConfig {
  id: number
  config_id: number
  charge_type: 'declared' | 'actual' | 'max'  // 申报需量/实际需量/最大需量
  unit_price: number               // 单价 元/kVA·月 或 元/kW·月
  min_demand?: number              // 最小需量
  discount_rate?: number           // 折扣率 (如105%以内的超出部分免费)
}

// 功率因数调整配置
interface PowerFactorAdjConfig {
  id: number
  config_id: number
  pf_threshold: number             // 功率因数阈值 (如0.90)
  reward_rate: number              // 奖励比例 (如每提高0.01奖励0.5%)
  penalty_rate: number             // 惩罚比例 (如每降低0.01惩罚0.5%)
  max_reward_rate: number          // 最大奖励比例 (如15%)
  max_penalty_rate: number         // 最大惩罚比例 (如15%)
  apply_to: string[]               // 适用费用项 (如只对输配电费调整)
}
```

#### 5.3.3 电费清单导入与解析

```typescript
// 电费清单记录
interface ElectricityBillRecord {
  id: number
  bill_month: string               // 账期 YYYY-MM
  customer_no: string              // 户号
  customer_name: string            // 户名
  region_code: string              // 地区代码
  voltage_level: string            // 电压等级
  customer_type: string            // 用电类别

  // 电量数据
  total_energy: number             // 本期电量 kWh
  peak_energy: number              // 尖峰电量
  high_energy: number              // 峰时电量
  normal_energy: number            // 平时电量
  valley_energy: number            // 谷时电量

  // 需量数据
  declared_demand: number          // 申报需量 kVA/kW
  actual_demand: number            // 实际最大需量

  // 功率因数
  power_factor: number             // 本期功率因数

  // 费用明细 (JSON存储各项费用)
  bill_details: BillDetailItem[]

  // 汇总
  total_amount: number             // 电费合计
  pf_adjustment: number            // 功率因数调整
  final_amount: number             // 应缴金额

  // 能耗分析 (从清单中提取)
  energy_yoy_change?: number       // 电量同比变化 %
  energy_mom_change?: number       // 电量环比变化 %
  demand_change?: number           // 需量变化 %
  avg_price: number                // 平均电价 元/kWh

  // 导入信息
  import_source: 'manual' | 'ocr' | 'api' | 'excel'
  import_time: Date
  original_file?: string           // 原始文件路径
}

// 费用明细项
interface BillDetailItem {
  category: string                 // 费用大类
  item_code: string                // 费用项编码
  item_name: string                // 费用项名称
  quantity?: number                // 数量/电量
  unit_price?: number              // 单价
  amount: number                   // 金额
}

// 清单导入服务
interface BillImportService {
  // 从Excel导入
  importFromExcel(file: File): Promise<ElectricityBillRecord>

  // 从图片OCR识别
  importFromImage(file: File): Promise<ElectricityBillRecord>

  // 从供电局API获取 (需要对接)
  importFromAPI(customerNo: string, month: string): Promise<ElectricityBillRecord>

  // 手动录入
  importManually(data: Partial<ElectricityBillRecord>): Promise<ElectricityBillRecord>

  // 验证清单数据
  validateBill(record: ElectricityBillRecord): ValidationResult

  // 解析并计算各项费用
  parseBillDetails(record: ElectricityBillRecord): BillDetailItem[]
}
```

#### 5.3.4 电费计算引擎

```typescript
// 电费计算引擎
class ElectricityBillCalculator {
  private config: ElectricityBillConfig
  private itemConfigs: BillItemConfig[]
  private touPricing: TimeOfUsePricing[]
  private demandConfig: DemandChargeConfig
  private pfConfig: PowerFactorAdjConfig

  // 计算月度电费
  async calculateMonthlyBill(params: {
    energyData: EnergyData,         // 电量数据
    demandData: DemandData,         // 需量数据
    powerFactor: number             // 功率因数
  }): Promise<BillCalculationResult> {
    const result: BillCalculationResult = {
      items: [],
      subtotal: 0,
      pfAdjustment: 0,
      total: 0
    }

    // 1. 计算市场化购电电费
    result.items.push(...this.calcMarketPurchase(params.energyData))

    // 2. 计算上网环节线损费
    result.items.push(this.calcGridLoss(params.energyData))

    // 3. 计算输配电费
    result.items.push(...this.calcTransmission(params.energyData, params.demandData))

    // 4. 计算系统运行费
    result.items.push(...this.calcSystemOperation(params.energyData))

    // 5. 计算政府性基金
    result.items.push(...this.calcGovernmentFund(params.energyData))

    // 计算小计
    result.subtotal = result.items.reduce((sum, item) => sum + item.amount, 0)

    // 6. 计算功率因数调整
    result.pfAdjustment = this.calcPowerFactorAdjustment(
      result.subtotal,
      params.powerFactor
    )

    // 计算总计
    result.total = result.subtotal + result.pfAdjustment

    return result
  }

  // 计算分时电费
  private calcTimeOfUseEnergy(energyData: EnergyData): TimeOfUseResult {
    // 根据分时电价配置计算各时段电费
    // ...
  }

  // 计算功率因数调整
  private calcPowerFactorAdjustment(subtotal: number, pf: number): number {
    const threshold = this.pfConfig.pf_threshold
    const diff = pf - threshold

    if (diff >= 0) {
      // 奖励 (返回负值)
      const rewardSteps = Math.floor(diff * 100)
      const rewardRate = Math.min(
        rewardSteps * this.pfConfig.reward_rate,
        this.pfConfig.max_reward_rate
      )
      return -subtotal * rewardRate / 100
    } else {
      // 惩罚 (返回正值)
      const penaltySteps = Math.floor(-diff * 100)
      const penaltyRate = Math.min(
        penaltySteps * this.pfConfig.penalty_rate,
        this.pfConfig.max_penalty_rate
      )
      return subtotal * penaltyRate / 100
    }
  }
}
```

### 5.4 节能建议平台（V2.2 可扩展架构）

#### 5.4.1 平台架构设计

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          节能建议平台架构                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         数据采集层                                    │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │   │
│  │  │实时电力   │ │历史能耗   │ │电费清单   │ │设备状态   │ │环境数据   │   │   │
│  │  │数据      │ │数据      │ │数据      │ │数据      │ │数据      │   │   │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘   │   │
│  └───────┼────────────┼────────────┼────────────┼────────────┼─────────┘   │
│          └────────────┴────────────┼────────────┴────────────┘             │
│                                    ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        数据预处理层                                   │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                 │   │
│  │  │ 数据清洗      │ │ 特征提取      │ │ 数据聚合      │                 │   │
│  │  │ & 标准化     │ │ & 计算       │ │ & 统计       │                 │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘                 │   │
│  └─────────────────────────────────┬───────────────────────────────────┘   │
│                                    ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      分析引擎层 (可插拔)                               │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │                    算法/模型插件接口                          │    │   │
│  │  │  interface AnalysisPlugin {                                  │    │   │
│  │  │    id: string                                                │    │   │
│  │  │    name: string                                              │    │   │
│  │  │    version: string                                           │    │   │
│  │  │    analyze(context: AnalysisContext): SuggestionResult[]     │    │   │
│  │  │    getConfig(): PluginConfig                                 │    │   │
│  │  │    setConfig(config: PluginConfig): void                     │    │   │
│  │  │  }                                                           │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  │                                                                     │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐       │   │
│  │  │ 规则引擎   │ │ 负荷转移   │ │ 需量优化   │ │ 功率因数   │       │   │
│  │  │ 插件      │ │ 分析插件   │ │ 分析插件   │ │ 分析插件   │       │   │
│  │  └────────────┘ └────────────┘ └────────────┘ └────────────┘       │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐       │   │
│  │  │ 峰谷优化   │ │ PUE优化    │ │ 设备效率   │ │ AI/ML      │       │   │
│  │  │ 分析插件   │ │ 分析插件   │ │ 分析插件   │ │ 预测插件   │       │   │
│  │  └────────────┘ └────────────┘ └────────────┘ └────────────┘       │   │
│  └─────────────────────────────────┬───────────────────────────────────┘   │
│                                    ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       建议生成与管理层                                │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                 │   │
│  │  │ 建议聚合      │ │ 优先级排序    │ │ 建议去重      │                 │   │
│  │  │ & 合并       │ │ & 评分       │ │ & 冲突检测   │                 │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘                 │   │
│  └─────────────────────────────────┬───────────────────────────────────┘   │
│                                    ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        建议执行与跟踪层                               │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                 │   │
│  │  │ 建议推送      │ │ 执行跟踪      │ │ 效果评估      │                 │   │
│  │  │ & 通知       │ │ & 状态管理   │ │ & 反馈学习   │                 │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 5.4.2 分析插件接口定义

```typescript
// 分析上下文 - 提供给插件的数据
interface AnalysisContext {
  // 基础信息
  analysisTime: Date
  analysisRange: { start: Date; end: Date }

  // 电量数据
  energyData: {
    hourly: EnergyHourlyData[]
    daily: EnergyDailyData[]
    monthly: EnergyMonthlyData[]
  }

  // 功率数据
  powerData: {
    realtime: RealtimePowerData[]
    peakDemand: number
    avgPower: number
    loadProfile: LoadProfileData[]
  }

  // 电费数据
  billData: {
    currentBill?: ElectricityBillRecord
    historicalBills: ElectricityBillRecord[]
    pricingConfig: ElectricityBillConfig
  }

  // 设备数据
  deviceData: {
    devices: PowerDevice[]
    deviceStatus: DeviceStatusData[]
  }

  // 环境数据
  environmentData: {
    temperature: number[]
    humidity: number[]
    pue: number[]
  }

  // 配置参数
  config: PluginConfig
}

// 建议结果
interface SuggestionResult {
  plugin_id: string                // 生成此建议的插件ID
  suggestion_type: string          // 建议类型
  title: string                    // 建议标题
  description: string              // 详细描述
  priority: 'critical' | 'high' | 'medium' | 'low'

  // 节省预估
  savings: {
    energy_kwh?: number            // 预计节省电量 kWh/月
    cost_yuan?: number             // 预计节省电费 元/月
    percentage?: number            // 预计节省比例 %
  }

  // 实施信息
  implementation: {
    difficulty: 'easy' | 'medium' | 'hard'
    cost_estimate?: number         // 实施成本估算
    payback_months?: number        // 投资回收期
    steps?: string[]               // 实施步骤
  }

  // 关联数据
  related_data: {
    trigger_values: Record<string, number>  // 触发此建议的数值
    threshold_values: Record<string, number> // 阈值
    affected_devices?: string[]    // 涉及设备
    time_range?: string            // 建议实施时间
  }

  // 置信度
  confidence: number               // 0-1，建议的可信度

  // 元数据
  metadata?: Record<string, any>
}

// 插件配置
interface PluginConfig {
  enabled: boolean
  parameters: Record<string, any>
  thresholds: Record<string, number>
  schedule?: string                // 执行计划 (cron表达式)
}

// 分析插件基类
abstract class AnalysisPlugin {
  abstract readonly id: string
  abstract readonly name: string
  abstract readonly version: string
  abstract readonly description: string

  protected config: PluginConfig

  // 执行分析
  abstract analyze(context: AnalysisContext): Promise<SuggestionResult[]>

  // 获取默认配置
  abstract getDefaultConfig(): PluginConfig

  // 验证配置
  abstract validateConfig(config: PluginConfig): boolean

  // 获取插件信息
  getInfo(): PluginInfo {
    return {
      id: this.id,
      name: this.name,
      version: this.version,
      description: this.description,
      config: this.config
    }
  }
}
```

#### 5.4.3 内置分析插件

##### 5.4.3.1 负荷转移分析插件

```typescript
class LoadShiftingPlugin extends AnalysisPlugin {
  readonly id = 'load_shifting'
  readonly name = '负荷转移分析'
  readonly version = '1.0.0'
  readonly description = '分析峰谷电价差异，识别可转移负荷，提供负荷转移建议'

  async analyze(context: AnalysisContext): Promise<SuggestionResult[]> {
    const results: SuggestionResult[] = []

    // 分析峰谷电量分布
    const peakValleyRatio = this.analyzePeakValleyDistribution(context.energyData)

    // 分析可转移负荷
    const shiftableLoads = this.identifyShiftableLoads(context.powerData, context.deviceData)

    // 计算转移收益
    const savings = this.calculateShiftingSavings(
      shiftableLoads,
      context.billData.pricingConfig
    )

    // 生成建议
    if (peakValleyRatio.peakRatio > 0.4 && savings.potential > 0) {
      results.push({
        plugin_id: this.id,
        suggestion_type: 'load_shifting',
        title: '负荷转移节费建议',
        description: `当前峰时用电占比${(peakValleyRatio.peakRatio * 100).toFixed(1)}%，` +
          `建议将${shiftableLoads.map(l => l.name).join('、')}等可调度负荷转移至谷时运行`,
        priority: savings.potential > 5000 ? 'high' : 'medium',
        savings: {
          energy_kwh: 0,  // 负荷转移不改变总电量
          cost_yuan: savings.potential,
          percentage: savings.percentage
        },
        implementation: {
          difficulty: 'medium',
          steps: [
            '识别可调度设备（如备份任务、数据同步等）',
            '调整设备运行计划至谷时段（23:00-07:00）',
            '设置定时任务自动执行',
            '监控执行效果并优化'
          ]
        },
        related_data: {
          trigger_values: {
            peak_ratio: peakValleyRatio.peakRatio,
            peak_energy: peakValleyRatio.peakEnergy,
            valley_energy: peakValleyRatio.valleyEnergy
          },
          threshold_values: {
            peak_ratio_threshold: 0.4
          },
          affected_devices: shiftableLoads.map(l => l.deviceCode),
          time_range: '谷时段 23:00-07:00'
        },
        confidence: 0.85
      })
    }

    return results
  }

  private analyzePeakValleyDistribution(energyData: any) {
    // 分析峰谷分布...
    return { peakRatio: 0, valleyRatio: 0, peakEnergy: 0, valleyEnergy: 0 }
  }

  private identifyShiftableLoads(powerData: any, deviceData: any) {
    // 识别可转移负荷...
    return []
  }

  private calculateShiftingSavings(loads: any[], pricingConfig: any) {
    // 计算转移收益...
    return { potential: 0, percentage: 0 }
  }

  getDefaultConfig(): PluginConfig {
    return {
      enabled: true,
      parameters: {
        min_shiftable_power: 5,    // 最小可转移功率 kW
        shift_efficiency: 0.9      // 转移效率
      },
      thresholds: {
        peak_ratio_threshold: 0.4, // 峰时占比阈值
        min_savings: 100           // 最小节省金额
      }
    }
  }

  validateConfig(config: PluginConfig): boolean {
    return config.thresholds.peak_ratio_threshold > 0 &&
           config.thresholds.peak_ratio_threshold < 1
  }
}
```

##### 5.4.3.2 需量优化分析插件

```typescript
class DemandOptimizationPlugin extends AnalysisPlugin {
  readonly id = 'demand_optimization'
  readonly name = '需量优化分析'
  readonly version = '1.0.0'
  readonly description = '分析最大需量使用情况，优化需量申报，降低需量电费'

  async analyze(context: AnalysisContext): Promise<SuggestionResult[]> {
    const results: SuggestionResult[] = []

    // 获取历史最大需量数据
    const demandHistory = this.analyzeDemandHistory(context.billData.historicalBills)

    // 分析需量使用率
    const utilization = demandHistory.actualMax / demandHistory.declaredDemand

    // 生成需量申报调整建议
    if (utilization < 0.85) {
      const optimalDemand = this.calculateOptimalDemand(demandHistory)
      const savings = this.calculateDemandSavings(
        demandHistory.declaredDemand,
        optimalDemand,
        context.billData.pricingConfig
      )

      results.push({
        plugin_id: this.id,
        suggestion_type: 'demand_adjustment',
        title: '降低申报需量建议',
        description: `当前申报需量${demandHistory.declaredDemand}kVA，` +
          `实际最大需量${demandHistory.actualMax}kVA，` +
          `利用率仅${(utilization * 100).toFixed(1)}%，` +
          `建议调整申报需量至${optimalDemand}kVA`,
        priority: 'high',
        savings: {
          cost_yuan: savings,
          percentage: (savings / context.billData.currentBill?.total_amount || 0) * 100
        },
        implementation: {
          difficulty: 'easy',
          steps: [
            '向供电局提交需量变更申请',
            '等待审批通过',
            '新需量从下月生效'
          ]
        },
        related_data: {
          trigger_values: {
            declared_demand: demandHistory.declaredDemand,
            actual_max_demand: demandHistory.actualMax,
            utilization: utilization
          },
          threshold_values: {
            utilization_threshold: 0.85
          }
        },
        confidence: 0.9
      })
    }

    // 生成需量控制建议（避免超出申报需量）
    if (utilization > 1.05) {
      results.push({
        plugin_id: this.id,
        suggestion_type: 'demand_control',
        title: '需量超标预警',
        description: `实际需量已超出申报需量${((utilization - 1) * 100).toFixed(1)}%，` +
          `建议采取负荷错峰措施或提高申报需量`,
        priority: 'critical',
        savings: { cost_yuan: 0 },
        implementation: {
          difficulty: 'medium',
          steps: [
            '立即检查高功率设备同时运行情况',
            '制定设备启动错峰计划',
            '考虑安装需量控制器',
            '或申请提高申报需量'
          ]
        },
        related_data: {
          trigger_values: {
            declared_demand: demandHistory.declaredDemand,
            actual_max_demand: demandHistory.actualMax
          },
          threshold_values: {
            max_utilization: 1.05
          }
        },
        confidence: 0.95
      })
    }

    return results
  }

  // ... 其他方法实现

  getDefaultConfig(): PluginConfig {
    return {
      enabled: true,
      parameters: {
        safety_margin: 0.1,        // 安全裕度 10%
        analysis_months: 12        // 分析历史月数
      },
      thresholds: {
        low_utilization: 0.85,     // 低利用率阈值
        high_utilization: 1.05     // 高利用率阈值
      }
    }
  }

  validateConfig(config: PluginConfig): boolean {
    return true
  }
}
```

##### 5.4.3.3 功率因数优化插件

```typescript
class PowerFactorPlugin extends AnalysisPlugin {
  readonly id = 'power_factor'
  readonly name = '功率因数优化'
  readonly version = '1.0.0'
  readonly description = '分析功率因数状况，提供无功补偿建议'

  async analyze(context: AnalysisContext): Promise<SuggestionResult[]> {
    const results: SuggestionResult[] = []

    const currentPF = context.billData.currentBill?.power_factor || 0
    const pfConfig = context.billData.pricingConfig

    // 功率因数过低
    if (currentPF < 0.9) {
      const requiredCapacity = this.calculateCompensationCapacity(
        context.powerData,
        currentPF,
        0.95
      )

      results.push({
        plugin_id: this.id,
        suggestion_type: 'power_factor_improvement',
        title: '功率因数改善建议',
        description: `当前功率因数${currentPF.toFixed(2)}，低于0.90将被加收电费，` +
          `建议安装${requiredCapacity}kVar无功补偿装置，将功率因数提升至0.95以上可获得电费奖励`,
        priority: currentPF < 0.85 ? 'critical' : 'high',
        savings: {
          cost_yuan: this.calculatePFSavings(context.billData, currentPF, 0.95),
          percentage: 5
        },
        implementation: {
          difficulty: 'medium',
          cost_estimate: requiredCapacity * 100,  // 约100元/kVar
          payback_months: 12,
          steps: [
            '委托专业机构进行无功补偿方案设计',
            '采购并安装电容补偿柜',
            '调试运行，监测功率因数变化',
            '定期维护检查'
          ]
        },
        related_data: {
          trigger_values: {
            current_pf: currentPF,
            required_compensation: requiredCapacity
          },
          threshold_values: {
            pf_threshold: 0.9,
            target_pf: 0.95
          }
        },
        confidence: 0.9
      })
    }

    return results
  }

  private calculateCompensationCapacity(powerData: any, currentPF: number, targetPF: number): number {
    // 计算所需无功补偿容量
    // Q = P × (tan(arccos(currentPF)) - tan(arccos(targetPF)))
    const avgPower = powerData.avgPower || 100
    const currentAngle = Math.acos(currentPF)
    const targetAngle = Math.acos(targetPF)
    return avgPower * (Math.tan(currentAngle) - Math.tan(targetAngle))
  }

  private calculatePFSavings(billData: any, currentPF: number, targetPF: number): number {
    // 计算功率因数改善后的节省金额
    return 0
  }

  getDefaultConfig(): PluginConfig {
    return {
      enabled: true,
      parameters: {
        target_pf: 0.95
      },
      thresholds: {
        min_pf: 0.9,
        optimal_pf: 0.95
      }
    }
  }

  validateConfig(config: PluginConfig): boolean {
    return config.thresholds.min_pf < config.thresholds.optimal_pf
  }
}
```

#### 5.4.4 插件管理服务

```typescript
// 插件管理器
class PluginManager {
  private plugins: Map<string, AnalysisPlugin> = new Map()
  private pluginConfigs: Map<string, PluginConfig> = new Map()

  // 注册插件
  registerPlugin(plugin: AnalysisPlugin): void {
    this.plugins.set(plugin.id, plugin)
    this.pluginConfigs.set(plugin.id, plugin.getDefaultConfig())
  }

  // 卸载插件
  unregisterPlugin(pluginId: string): void {
    this.plugins.delete(pluginId)
    this.pluginConfigs.delete(pluginId)
  }

  // 获取所有插件
  getAllPlugins(): PluginInfo[] {
    return Array.from(this.plugins.values()).map(p => p.getInfo())
  }

  // 获取启用的插件
  getEnabledPlugins(): AnalysisPlugin[] {
    return Array.from(this.plugins.values())
      .filter(p => this.pluginConfigs.get(p.id)?.enabled)
  }

  // 更新插件配置
  updatePluginConfig(pluginId: string, config: Partial<PluginConfig>): void {
    const currentConfig = this.pluginConfigs.get(pluginId)
    if (currentConfig) {
      this.pluginConfigs.set(pluginId, { ...currentConfig, ...config })
    }
  }

  // 执行分析
  async runAnalysis(context: AnalysisContext): Promise<SuggestionResult[]> {
    const results: SuggestionResult[] = []

    for (const plugin of this.getEnabledPlugins()) {
      try {
        const pluginResults = await plugin.analyze(context)
        results.push(...pluginResults)
      } catch (error) {
        console.error(`Plugin ${plugin.id} analysis failed:`, error)
      }
    }

    // 结果排序和去重
    return this.processResults(results)
  }

  private processResults(results: SuggestionResult[]): SuggestionResult[] {
    // 按优先级和节省金额排序
    return results.sort((a, b) => {
      const priorityOrder = { critical: 0, high: 1, medium: 2, low: 3 }
      const priorityDiff = priorityOrder[a.priority] - priorityOrder[b.priority]
      if (priorityDiff !== 0) return priorityDiff
      return (b.savings.cost_yuan || 0) - (a.savings.cost_yuan || 0)
    })
  }
}

// 初始化内置插件
const pluginManager = new PluginManager()
pluginManager.registerPlugin(new LoadShiftingPlugin())
pluginManager.registerPlugin(new DemandOptimizationPlugin())
pluginManager.registerPlugin(new PowerFactorPlugin())
pluginManager.registerPlugin(new PeakValleyOptimizationPlugin())
pluginManager.registerPlugin(new PUEOptimizationPlugin())
pluginManager.registerPlugin(new EquipmentEfficiencyPlugin())
```

### 5.5 用电管理数据库设计

```sql
-- 电力设备表
CREATE TABLE power_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_code VARCHAR(50) UNIQUE NOT NULL,
    device_name VARCHAR(100) NOT NULL,
    device_type VARCHAR(20) NOT NULL,    -- PDU, UPS, AC, IT
    rated_power REAL,                    -- 额定功率 kW
    rated_voltage REAL,                  -- 额定电压 V
    rated_current REAL,                  -- 额定电流 A
    parent_device_id INTEGER,            -- 上级设备(配电关系)
    circuit_no VARCHAR(20),              -- 回路编号
    is_metered BOOLEAN DEFAULT TRUE,     -- 是否计量
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 电量统计表(按小时)
CREATE TABLE energy_hourly (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    stat_hour TIMESTAMP NOT NULL,        -- 统计小时
    energy_kwh REAL,                     -- 用电量 kWh
    max_power REAL,                      -- 最大功率 kW
    avg_power REAL,                      -- 平均功率 kW
    min_power REAL,                      -- 最小功率 kW
    avg_voltage REAL,                    -- 平均电压 V
    avg_current REAL,                    -- 平均电流 A
    power_factor REAL,                   -- 功率因数
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (device_id) REFERENCES power_devices(id),
    UNIQUE(device_id, stat_hour)
);

-- 电量统计表(按天)
CREATE TABLE energy_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    stat_date DATE NOT NULL,             -- 统计日期
    total_energy REAL,                   -- 总用电量 kWh
    peak_energy REAL,                    -- 峰时电量
    normal_energy REAL,                  -- 平时电量
    valley_energy REAL,                  -- 谷时电量
    max_power REAL,                      -- 最大功率
    avg_power REAL,                      -- 平均功率
    peak_power_time TIMESTAMP,           -- 峰值功率时间
    energy_cost REAL,                    -- 电费 元
    pue REAL,                            -- 当日PUE
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (device_id) REFERENCES power_devices(id),
    UNIQUE(device_id, stat_date)
);

-- 电量统计表(按月)
CREATE TABLE energy_monthly (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER,                   -- NULL表示总计
    stat_year INTEGER NOT NULL,
    stat_month INTEGER NOT NULL,
    total_energy REAL,                   -- 总用电量 kWh
    peak_energy REAL,
    normal_energy REAL,
    valley_energy REAL,
    max_demand REAL,                     -- 最大需量 kW
    avg_pue REAL,                        -- 平均PUE
    energy_cost REAL,                    -- 电费
    yoy_change REAL,                     -- 同比变化 %
    mom_change REAL,                     -- 环比变化 %
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(device_id, stat_year, stat_month)
);

-- 节能建议记录表
CREATE TABLE energy_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id VARCHAR(50) NOT NULL,        -- 规则ID
    rule_name VARCHAR(100),              -- 规则名称
    trigger_value REAL,                  -- 触发值
    threshold_value REAL,                -- 阈值
    suggestion TEXT,                     -- 建议内容
    priority VARCHAR(20),                -- 优先级
    potential_saving REAL,               -- 预计节省 %
    status VARCHAR(20) DEFAULT 'pending',-- pending/accepted/rejected/completed
    accepted_by INTEGER,
    accepted_at TIMESTAMP,
    completed_at TIMESTAMP,
    actual_saving REAL,                  -- 实际节省 %
    remark TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 电价配置表
CREATE TABLE electricity_pricing (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    price_name VARCHAR(50) NOT NULL,
    period_type VARCHAR(20) NOT NULL,    -- peak/normal/valley
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    price REAL NOT NULL,                 -- 单价 元/kWh
    effective_date DATE,                 -- 生效日期
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PUE 历史记录表
CREATE TABLE pue_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_time TIMESTAMP NOT NULL,
    total_power REAL,                    -- 总功率 kW
    it_power REAL,                       -- IT功率 kW
    cooling_power REAL,                  -- 制冷功率 kW
    other_power REAL,                    -- 其他功率 kW
    pue REAL,                            -- PUE值
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 5.6 用电管理 API 设计

#### 5.6.1 电力监测接口

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/v1/energy/realtime | 获取实时电力数据 | viewer |
| GET | /api/v1/energy/realtime/summary | 获取电力数据汇总 | viewer |
| GET | /api/v1/energy/device/{id} | 获取设备电力数据 | viewer |
| GET | /api/v1/energy/pue | 获取当前PUE值 | viewer |
| GET | /api/v1/energy/pue/history | 获取PUE历史趋势 | viewer |

#### 5.6.2 用电统计接口

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/v1/energy/statistics/hourly | 获取小时用电统计 | viewer |
| GET | /api/v1/energy/statistics/daily | 获取日用电统计 | viewer |
| GET | /api/v1/energy/statistics/monthly | 获取月用电统计 | viewer |
| GET | /api/v1/energy/statistics/yearly | 获取年用电统计 | viewer |
| GET | /api/v1/energy/statistics/by-device | 按设备统计用电 | viewer |
| GET | /api/v1/energy/statistics/by-type | 按类型统计用电 | viewer |
| GET | /api/v1/energy/statistics/comparison | 同比/环比分析 | viewer |
| GET | /api/v1/energy/statistics/peak-valley | 峰谷平用电分析 | viewer |

#### 5.6.3 电费管理接口

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/v1/energy/cost/daily | 获取日电费 | viewer |
| GET | /api/v1/energy/cost/monthly | 获取月电费 | viewer |
| GET | /api/v1/energy/cost/yearly | 获取年电费 | viewer |
| GET | /api/v1/energy/pricing | 获取电价配置 | admin |
| PUT | /api/v1/energy/pricing | 更新电价配置 | admin |

#### 5.6.4 节能管理接口

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/v1/energy/suggestions | 获取节能建议列表 | viewer |
| GET | /api/v1/energy/suggestions/active | 获取待处理建议 | viewer |
| PUT | /api/v1/energy/suggestions/{id}/accept | 接受建议 | operator |
| PUT | /api/v1/energy/suggestions/{id}/reject | 拒绝建议 | operator |
| PUT | /api/v1/energy/suggestions/{id}/complete | 完成建议 | operator |
| GET | /api/v1/energy/saving/summary | 获取节能成效汇总 | viewer |
| GET | /api/v1/energy/saving/potential | 获取节能潜力分析 | viewer |

#### 5.6.5 能效报告接口

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/v1/energy/report/daily | 获取日能效报告 | viewer |
| GET | /api/v1/energy/report/weekly | 获取周能效报告 | viewer |
| GET | /api/v1/energy/report/monthly | 获取月能效报告 | viewer |
| POST | /api/v1/energy/report/generate | 生成能效报告 | operator |
| GET | /api/v1/energy/report/download/{id} | 下载能效报告 | viewer |

#### 5.6.6 配电系统配置接口

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/v1/energy/transformers | 获取变压器列表 | viewer |
| POST | /api/v1/energy/transformers | 创建变压器 | admin |
| GET | /api/v1/energy/transformers/{id} | 获取变压器详情 | viewer |
| PUT | /api/v1/energy/transformers/{id} | 更新变压器 | admin |
| DELETE | /api/v1/energy/transformers/{id} | 删除变压器 | admin |
| GET | /api/v1/energy/meter-points | 获取计量点列表 | viewer |
| POST | /api/v1/energy/meter-points | 创建计量点 | admin |
| GET | /api/v1/energy/meter-points/{id} | 获取计量点详情 | viewer |
| PUT | /api/v1/energy/meter-points/{id} | 更新计量点 | admin |
| DELETE | /api/v1/energy/meter-points/{id} | 删除计量点 | admin |
| GET | /api/v1/energy/panels | 获取配电柜列表 | viewer |
| POST | /api/v1/energy/panels | 创建配电柜 | admin |
| GET | /api/v1/energy/panels/{id} | 获取配电柜详情 | viewer |
| PUT | /api/v1/energy/panels/{id} | 更新配电柜 | admin |
| DELETE | /api/v1/energy/panels/{id} | 删除配电柜 | admin |
| GET | /api/v1/energy/circuits | 获取配电回路列表 | viewer |
| POST | /api/v1/energy/circuits | 创建配电回路 | admin |
| GET | /api/v1/energy/circuits/{id} | 获取配电回路详情 | viewer |
| PUT | /api/v1/energy/circuits/{id} | 更新配电回路 | admin |
| DELETE | /api/v1/energy/circuits/{id} | 删除配电回路 | admin |

#### 5.6.7 配电拓扑接口

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/v1/energy/topology | 获取配电系统拓扑 | viewer |
| GET | /api/v1/energy/topology/tree | 获取拓扑树形结构 | viewer |
| GET | /api/v1/energy/topology/node/{type}/{id} | 获取节点详情及子节点 | viewer |

#### 5.6.8 用电设备配置接口

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/v1/energy/devices | 获取用电设备列表 | viewer |
| POST | /api/v1/energy/devices | 创建用电设备 | admin |
| GET | /api/v1/energy/devices/{id} | 获取用电设备详情 | viewer |
| PUT | /api/v1/energy/devices/{id} | 更新用电设备 | admin |
| DELETE | /api/v1/energy/devices/{id} | 删除用电设备 | admin |
| PUT | /api/v1/energy/devices/{id}/points | 配置设备点位关联 | admin |
| GET | /api/v1/energy/devices/{id}/points | 获取设备点位关联 | viewer |
| GET | /api/v1/energy/devices/{id}/realtime | 获取设备实时电力数据 | viewer |
| PUT | /api/v1/energy/devices/{id}/shift-config | 配置设备负荷转移参数 | admin |
| GET | /api/v1/energy/devices/{id}/shift-config | 获取设备负荷转移配置 | viewer |

#### 5.6.9 功率曲线与需量接口

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/v1/energy/power-curve | 获取功率曲线数据 | viewer |
| GET | /api/v1/energy/power-curve/meter/{meter_id} | 获取计量点功率曲线 | viewer |
| GET | /api/v1/energy/power-curve/device/{device_id} | 获取设备功率曲线 | viewer |
| GET | /api/v1/energy/demand-history/{meter_id} | 获取需量历史数据 | viewer |
| GET | /api/v1/energy/demand-history/{meter_id}/events | 获取超限事件列表 | viewer |

#### 5.6.10 负荷转移分析接口

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/v1/energy/analysis/device-shift | 获取设备负荷转移分析 | viewer |
| GET | /api/v1/energy/analysis/device-shift/potential | 获取转移潜力分析 | viewer |
| GET | /api/v1/energy/analysis/device-shift/simulation | 模拟转移效果 | viewer |
| POST | /api/v1/energy/analysis/device-shift/accept/{suggestion_id} | 接受转移建议 | operator |

#### 5.6.11 需量配置分析接口

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/v1/energy/analysis/demand-config | 获取需量配置合理性分析 | viewer |
| GET | /api/v1/energy/analysis/demand-config/{meter_id} | 获取指定计量点需量分析 | viewer |
| GET | /api/v1/energy/analysis/demand-config/recommendation | 获取需量配置建议 | viewer |
| POST | /api/v1/energy/analysis/demand-config/apply | 应用需量配置建议 | admin |

### 5.7 用电管理前端页面

#### 5.7.1 用电监控仪表盘

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 用电管理 > 用电监控                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ ┌─────────┬─────────┬─────────┬─────────┬─────────┬─────────┐               │
│ │ 总功率   │ 总电量   │  PUE    │ 今日电费 │ 功率因数 │ 节能建议 │               │
│ │ 85.2kW  │ 1024kWh │  1.52   │ ¥820.5  │  0.92   │  3条    │               │
│ │ [正常]   │ [今日]   │ [良好]   │ [预估]   │ [良好]   │ [待处理] │               │
│ └─────────┴─────────┴─────────┴─────────┴─────────┴─────────┘               │
│                                                                             │
│ ┌─────────────────────────────────┬─────────────────────────────────────┐   │
│ │        功率实时趋势              │         PUE 实时趋势                 │   │
│ │  100kW ┬                        │   2.0 ┬                             │   │
│ │        │    ╱╲  ╱╲              │       │                             │   │
│ │   75kW ┼───╱──╲╱──╲────────     │   1.5 ┼───────────────────────      │   │
│ │        │  ╱          ╲          │       │    ╱╲    ╱╲                 │   │
│ │   50kW ┼─╱────────────╲─────    │   1.0 ┼───╱──╲──╱──╲────────        │   │
│ │        └──────────────────────  │       └──────────────────────       │   │
│ │         09:00  10:00  11:00     │        09:00  10:00  11:00          │   │
│ └─────────────────────────────────┴─────────────────────────────────────┘   │
│                                                                             │
│ ┌─────────────────────────────────┬─────────────────────────────────────┐   │
│ │      设备用电分布                 │      峰谷平用电占比                  │   │
│ │   ┌────┐                        │   ┌────┐                            │   │
│ │   │UPS │ 45%                    │   │峰时│ 35%                        │   │
│ │   │空调│ 35%                    │   │平时│ 45%                        │   │
│ │   │照明│ 10%                    │   │谷时│ 20%                        │   │
│ │   │其他│ 10%                    │   └────┘                            │   │
│ │   └────┘ [饼图]                 │          [饼图]                      │   │
│ └─────────────────────────────────┴─────────────────────────────────────┘   │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ 配电设备状态                                                             │ │
│ │ ┌─────────────┬─────────────┬─────────────┬─────────────┐               │ │
│ │ │ 总配电柜     │ UPS-1       │ UPS-2       │ 精密空调     │               │ │
│ │ │ ●运行正常   │ ●运行正常   │ ●运行正常   │ ●运行正常    │               │ │
│ │ │ 85.2kW     │ 18.5kW     │ 19.2kW     │ 24.0kW      │               │ │
│ │ │ Ua:220V    │ 负载:72%   │ 负载:75%   │ 制冷:28kW    │               │ │
│ │ │ Ia:120A    │ 电池:100%  │ 电池:100%  │ 设定:24℃     │               │ │
│ │ └─────────────┴─────────────┴─────────────┴─────────────┘               │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 5.7.2 用电统计分析页面

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 用电管理 > 用电统计                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ 查询条件                                                                │ │
│ │ 统计维度: [日 ▼]  时间范围: [2026-01-01] ~ [2026-01-13]  设备: [全部 ▼]  │ │
│ │                                                      [查询] [导出]       │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ 用电量趋势                                                               │ │
│ │ 1200kWh ┬─────────────────────────────────────────────────────────────┐ │ │
│ │         │      ╱╲                                                     │ │ │
│ │ 1000kWh ┼─────╱──╲────────────────────────────────────────────────────│ │ │
│ │         │    ╱    ╲      ╱╲      ╱╲                                   │ │ │
│ │  800kWh ┼───╱──────╲────╱──╲────╱──╲──────────────────────────────────│ │ │
│ │         │  ╱        ╲  ╱    ╲  ╱    ╲                                 │ │ │
│ │  600kWh ┼─╱──────────╲╱──────╲╱──────╲────────────────────────────────│ │ │
│ │         └─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘ │ │
│ │           01-01  01-03  01-05  01-07  01-09  01-11  01-13              │ │
│ │         [━ 用电量  ━ 同比  ━ 环比]                                      │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌────────────────────────────────┬────────────────────────────────────────┐ │
│ │ 统计汇总                        │ 分设备用电排行                          │ │
│ │ 总用电量: 12,580 kWh           │ 排名  设备      用电量    占比    趋势  │ │
│ │ 平均日用电: 967.7 kWh          │  1   UPS-1    5,680kWh   45%    ↑3%   │ │
│ │ 最大日用电: 1,150 kWh (01-05)  │  2   精密空调  4,420kWh   35%    ↓2%   │ │
│ │ 最小日用电: 820 kWh (01-12)    │  3   UPS-2    1,258kWh   10%    →     │ │
│ │ 同比变化: +5.2%                │  4   照明     1,222kWh   10%    →     │ │
│ │ 环比变化: -2.1%                │                                        │ │
│ │ 总电费: ¥10,580                │                                        │ │
│ └────────────────────────────────┴────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 5.7.3 节能建议页面

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 用电管理 > 节能建议                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ ┌─────────┬─────────┬─────────┬─────────┐                                   │
│ │ 待处理   │ 已接受   │ 已完成   │ 已拒绝   │                                   │
│ │    3    │    5    │   12    │    2    │                                   │
│ └─────────┴─────────┴─────────┴─────────┘                                   │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ 待处理建议                                                               │ │
│ │ ┌─────────────────────────────────────────────────────────────────────┐ │ │
│ │ │ 🔴 高优先级 | PUE过高                                    2026-01-13 │ │ │
│ │ │ 当前PUE: 1.82 > 阈值: 1.8                                           │ │ │
│ │ │ 建议: 检查空调制冷效率，优化气流组织，考虑采用冷热通道隔离              │ │ │
│ │ │ 预计节省: 15%                                                       │ │ │
│ │ │                                               [接受] [拒绝] [详情]   │ │ │
│ │ └─────────────────────────────────────────────────────────────────────┘ │ │
│ │ ┌─────────────────────────────────────────────────────────────────────┐ │ │
│ │ │ 🟡 中优先级 | 功率因数偏低                                 2026-01-13 │ │ │
│ │ │ 当前功率因数: 0.88 < 阈值: 0.9                                       │ │ │
│ │ │ 建议: 安装无功补偿设备，可减少无功损耗和电费                           │ │ │
│ │ │ 预计节省: 5%                                                        │ │ │
│ │ │                                               [接受] [拒绝] [详情]   │ │ │
│ │ └─────────────────────────────────────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌─────────────────────────────────┬─────────────────────────────────────┐   │
│ │ 节能成效统计                     │ 节能潜力分析                         │   │
│ │ 已完成建议: 12 条               │ ┌──────────────────────────────────┐ │   │
│ │ 预计年节省: ¥15,800             │ │                                  │ │   │
│ │ 实际年节省: ¥12,500             │ │    [仪表盘: 已实现 65%]           │ │   │
│ │ 完成率: 79%                     │ │                                  │ │   │
│ │                                 │ │   总潜力: ¥24,000/年              │ │   │
│ │ 本月节省: ¥1,200                │ │   已实现: ¥15,600/年              │ │   │
│ │                                 │ │   待挖掘: ¥8,400/年               │ │   │
│ │                                 │ └──────────────────────────────────┘ │   │
│ └─────────────────────────────────┴─────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 5.7.4 配电系统配置页面

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 用电管理 > 配电系统配置                                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│ ┌───────────┬───────────┬───────────┬───────────┐                           │
│ │ 变压器    │ 计量点    │ 配电柜    │ 配电回路   │     [+ 新建] [导入] [导出] │
│ └───────────┴───────────┴───────────┴───────────┘                           │
│                                                                             │
│ ═══════════════════════════ 变压器管理 ══════════════════════════════════   │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ 搜索: [____________] 状态: [全部 ▼] 容量范围: [____] - [____] kVA       │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌────────────────────────────────────────────────────────────────────────┐  │
│ │ 编码      │ 名称        │ 容量(kVA) │ 电压   │ 状态   │ 安装位置  │ 操作 │  │
│ ├────────────────────────────────────────────────────────────────────────┤  │
│ │ TR-001   │ 1#变压器    │ 1000     │10/0.4kV│ 运行中 │ 配电房A  │[编辑]│  │
│ │ TR-002   │ 2#变压器    │ 800      │10/0.4kV│ 运行中 │ 配电房A  │[编辑]│  │
│ │ TR-003   │ 3#变压器(备)│ 630      │10/0.4kV│ 备用   │ 配电房B  │[编辑]│  │
│ └────────────────────────────────────────────────────────────────────────┘  │
│                                                          [1] [2] [>]        │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────── 变压器编辑对话框 ────────────────────────┐
│                                                                    [×]     │
│  基本信息                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 变压器编码: [TR-001____]     变压器名称: [1#变压器______________]     │  │
│  │ 额定容量:   [1000___] kVA    接线组别:   [Dyn11 ▼]                   │  │
│  │ 高压侧电压: [10____] kV      低压侧电压: [0.4___] kV                 │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  损耗参数                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 效率:       [98.5__] %      空载损耗:   [1.2___] kW                  │  │
│  │ 负载损耗:   [8.5___] kW     阻抗电压:   [4.5___] %                   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  安装信息                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 安装位置:   [配电房A________________________]                         │  │
│  │ 安装日期:   [2023-06-15 📅]                                          │  │
│  │ 运行状态:   (●) 运行中  ( ) 备用  ( ) 维护  ( ) 故障                 │  │
│  │ 启用状态:   [✓] 启用                                                 │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│                                              [取消]  [保存]                 │
└────────────────────────────────────────────────────────────────────────────┘
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 用电管理 > 配电系统配置 > 计量点                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│ ┌───────────┬───────────┬───────────┬───────────┐                           │
│ │ 变压器    │ 计量点    │ 配电柜    │ 配电回路   │     [+ 新建] [导入] [导出] │
│ └───────────┴───────────┴───────────┴───────────┘                           │
│                                                                             │
│ ═══════════════════════════ 计量点管理 ══════════════════════════════════   │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ 搜索: [____________] 变压器: [全部 ▼] 状态: [全部 ▼]                    │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌────────────────────────────────────────────────────────────────────────┐  │
│ │ 编码  │名称     │电表号 │变压器   │申报需量│户号     │状态  │ 操作     │  │
│ ├────────────────────────────────────────────────────────────────────────┤  │
│ │ M001 │总计量点 │82736 │1#变压器 │800 kW │44012536│正常 │[编辑][详情]│  │
│ │ M002 │机房计量 │82737 │1#变压器 │500 kW │44012537│正常 │[编辑][详情]│  │
│ │ M003 │空调计量 │82738 │2#变压器 │300 kW │44012538│正常 │[编辑][详情]│  │
│ └────────────────────────────────────────────────────────────────────────┘  │
│                                                          [1] [2] [>]        │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────── 计量点编辑对话框 ────────────────────────┐
│                                                                    [×]     │
│  基本信息                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 计量点编码: [M001______]    计量点名称: [总计量点_______________]     │  │
│  │ 电表号:     [827369____]    关联变压器: [1#变压器 ▼]                 │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  计量参数                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ CT比:       [400/5_____]    PT比:       [10000/100_]                 │  │
│  │ 综合倍率:   [80________]    (自动计算: CT比 × PT比 / 100)            │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  需量配置                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 申报需量:   [800_______] kW     需量类型: (●) kW  ( ) kVA            │  │
│  │ 需量周期:   [15________] 分钟                                        │  │
│  │                                                                      │  │
│  │ ⚠ 提示: 申报需量影响基本电费计算，请根据实际负荷合理设置              │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  电费户号关联                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 供电局户号: [44012536________________________]                        │  │
│  │ 户名:       [XX数据中心____________________]                         │  │
│  │ 电价配置:   [峰谷分时电价-工业用电 ▼]                                 │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│                                              [取消]  [保存]                 │
└────────────────────────────────────────────────────────────────────────────┘
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 用电管理 > 配电系统配置 > 配电柜                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│ ┌───────────┬───────────┬───────────┬───────────┐                           │
│ │ 变压器    │ 计量点    │ 配电柜    │ 配电回路   │     [+ 新建] [导入] [导出] │
│ └───────────┴───────────┴───────────┴───────────┘                           │
│                                                                             │
│ ═══════════════════════════ 配电柜管理 ══════════════════════════════════   │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ 搜索: [____________] 类型: [全部 ▼] 计量点: [全部 ▼]                    │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌────────────────────────────────────────────────────────────────────────┐  │
│ │ 编码     │ 名称        │ 类型     │ 计量点  │ 上级配电柜│ 状态 │ 操作  │  │
│ ├────────────────────────────────────────────────────────────────────────┤  │
│ │ PDU-001 │ 低压总配电柜│ main    │ M001   │ -        │ 运行 │[编辑] │  │
│ │ PDU-002 │ UPS输入柜  │ups_input│ M002   │ PDU-001  │ 运行 │[编辑] │  │
│ │ PDU-003 │ UPS输出柜  │ups_output│M002   │ PDU-002  │ 运行 │[编辑] │  │
│ │ PDU-004 │ 空调配电柜  │ sub     │ M003   │ PDU-001  │ 运行 │[编辑] │  │
│ └────────────────────────────────────────────────────────────────────────┘  │
│                                                          [1] [2] [>]        │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────── 配电柜编辑对话框 ────────────────────────┐
│                                                                    [×]     │
│  基本信息                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 配电柜编码: [PDU-001___]    配电柜名称: [低压总配电柜__________]      │  │
│  │ 配电柜类型: [main ▼]                                                 │  │
│  │            ┌────────────────────────────────────────┐                │  │
│  │            │ main      - 总配电柜                   │                │  │
│  │            │ sub       - 分配电柜                   │                │  │
│  │            │ ups_input - UPS输入柜                  │                │  │
│  │            │ ups_output- UPS输出柜                  │                │  │
│  │            └────────────────────────────────────────┘                │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  电气参数                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 额定电流:   [1600______] A      额定电压:   [380_______] V           │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  上下级关系                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 关联变压器: [1#变压器 ▼]        关联计量点: [M001-总计量点 ▼]         │  │
│  │ 上级配电柜: [无 ▼]                                                   │  │
│  │                                                                      │  │
│  │ 提示: 配电柜层级关系用于构建配电系统拓扑图                            │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  位置信息                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 安装位置:   [配电房A________________________]                         │  │
│  │ 区域代码:   [A01_______]                                             │  │
│  │ 运行状态:   (●) 运行中  ( ) 故障  ( ) 维护                           │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│                                              [取消]  [保存]                 │
└────────────────────────────────────────────────────────────────────────────┘
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 用电管理 > 配电系统配置 > 配电回路                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│ ┌───────────┬───────────┬───────────┬───────────┐                           │
│ │ 变压器    │ 计量点    │ 配电柜    │ 配电回路   │     [+ 新建] [导入] [导出] │
│ └───────────┴───────────┴───────────┴───────────┘                           │
│                                                                             │
│ ═══════════════════════════ 配电回路管理 ════════════════════════════════   │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ 搜索: [____________] 配电柜: [全部 ▼] 负载类型: [全部 ▼]                │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌────────────────────────────────────────────────────────────────────────┐  │
│ │ 编码  │ 名称       │ 配电柜   │负载类型│额定电流│可转移│优先级│ 操作  │  │
│ ├────────────────────────────────────────────────────────────────────────┤  │
│ │ C001 │ UPS主路    │ PDU-003 │ ups   │ 400A  │  ✗  │  -  │[编辑] │  │
│ │ C002 │ 机柜列头柜A │ PDU-003 │it_equip│ 63A   │  ✗  │  -  │[编辑] │  │
│ │ C003 │ 机柜列头柜B │ PDU-003 │it_equip│ 63A   │  ✗  │  -  │[编辑] │  │
│ │ C004 │ 精密空调1  │ PDU-004 │ hvac  │ 100A  │  ✓  │  2  │[编辑] │  │
│ │ C005 │ 精密空调2  │ PDU-004 │ hvac  │ 100A  │  ✓  │  3  │[编辑] │  │
│ │ C006 │ 照明回路   │ PDU-001 │lighting│ 32A   │  ✓  │  1  │[编辑] │  │
│ └────────────────────────────────────────────────────────────────────────┘  │
│                                                          [1] [2] [>]        │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────── 配电回路编辑对话框 ──────────────────────┐
│                                                                    [×]     │
│  基本信息                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 回路编码:   [C001______]    回路名称:   [UPS主路______________]       │  │
│  │ 所属配电柜: [PDU-003 UPS输出柜 ▼]                                     │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  电气参数                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 额定电流:   [400_______] A      断路器型号: [NS400N__________]        │  │
│  │ 断路器额定: [400_______] A                                           │  │
│  │                                                                      │  │
│  │ 负载类型:   [ups ▼]                                                  │  │
│  │            ┌──────────────────────────────────────────────────┐      │  │
│  │            │ ups          - UPS供电回路                       │      │  │
│  │            │ hvac         - 暖通空调                          │      │  │
│  │            │ it_equipment - IT设备                            │      │  │
│  │            │ lighting     - 照明                              │      │  │
│  │            │ general      - 一般负载                          │      │  │
│  │            │ emergency    - 应急电源                          │      │  │
│  │            └──────────────────────────────────────────────────┘      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  负荷转移配置                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ [✗] 允许负荷转移 (非关键负载可在峰谷时段进行功率调节)                 │  │
│  │                                                                      │  │
│  │ 转移优先级:     [99________] (1最高, 99最低)                          │  │
│  │ 最小运行时长:   [__________] 小时 (空置表示无限制)                    │  │
│  │                                                                      │  │
│  │ ⚠ 注意: UPS、IT设备等关键负载不建议配置负荷转移                      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│                                              [取消]  [保存]                 │
└────────────────────────────────────────────────────────────────────────────┘
```

#### 5.7.5 配电拓扑图页面

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 用电管理 > 配电拓扑图                                          [刷新] [导出] │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────── 配电系统拓扑 ─────────────────────────┐│
│  │                                                                         ││
│  │                          ┌─────────────────┐                            ││
│  │                          │   10kV 进线     │                            ││
│  │                          └────────┬────────┘                            ││
│  │                                   │                                     ││
│  │            ┌──────────────────────┼──────────────────────┐              ││
│  │            ▼                      ▼                      ▼              ││
│  │   ┌────────────────┐    ┌────────────────┐    ┌────────────────┐        ││
│  │   │ 🔌 1#变压器    │    │ 🔌 2#变压器    │    │ 🔌 3#变压器(备)│        ││
│  │   │ 1000kVA       │    │ 800kVA        │    │ 630kVA        │        ││
│  │   │ ✅ 运行中      │    │ ✅ 运行中      │    │ ⏸ 备用         │        ││
│  │   └───────┬────────┘    └───────┬────────┘    └────────────────┘        ││
│  │           │                     │                                       ││
│  │           ▼                     ▼                                       ││
│  │   ┌────────────────┐    ┌────────────────┐                              ││
│  │   │ 📊 M001       │    │ 📊 M002       │                              ││
│  │   │ 总计量点      │    │ 机房计量点    │                              ││
│  │   │ 申报: 800kW   │    │ 申报: 500kW   │                              ││
│  │   │ 当前: 620kW   │    │ 当前: 380kW   │                              ││
│  │   └───────┬────────┘    └───────┬────────┘                              ││
│  │           │                     │                                       ││
│  │           ▼                     ▼                                       ││
│  │   ┌────────────────┐    ┌────────────────┐                              ││
│  │   │ 🔲 PDU-001    │    │ 🔲 PDU-002    │                              ││
│  │   │ 低压总配电柜  │    │ UPS输入柜    │                              ││
│  │   │ 380V 1600A    │    │ 380V 800A     │                              ││
│  │   └───────┬────────┘    └───────┬────────┘                              ││
│  │           │                     │                                       ││
│  │    ┌──────┴──────┐              ▼                                       ││
│  │    ▼             ▼       ┌────────────────┐                             ││
│  │ ┌──────┐     ┌──────┐    │ 🔲 PDU-003    │                             ││
│  │ │C006 │     │C007 │    │ UPS输出柜    │                             ││
│  │ │照明 │     │空调 │    └───────┬────────┘                             ││
│  │ └──────┘     └──────┘           │                                       ││
│  │                          ┌──────┴──────┐                                ││
│  │                          ▼             ▼                                ││
│  │                      ┌──────┐      ┌──────┐                             ││
│  │                      │C001 │      │C002 │                             ││
│  │                      │机柜A│      │机柜B│                             ││
│  │                      └──────┘      └──────┘                             ││
│  │                                                                         ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                             │
│  图例: 🔌变压器  📊计量点  🔲配电柜  ─回路   ✅运行  ⏸备用  ⚠故障         │
│                                                                             │
│  ┌─────────────────────────────────── 节点详情 ─────────────────────────────┐│
│  │ 选中: 📊 M001 总计量点                                                   ││
│  │ ┌─────────────────────────────────────────────────────────────────────┐ ││
│  │ │ 基本信息                    │ 实时数据                              │ ││
│  │ │ 编码: M001                 │ 有功功率: 620 kW                     │ ││
│  │ │ 名称: 总计量点              │ 无功功率: 180 kVar                   │ ││
│  │ │ 电表号: 827369             │ 功率因数: 0.96                       │ ││
│  │ │ 变压器: 1#变压器            │ 当前需量: 615 kW                     │ ││
│  │ │ 申报需量: 800 kW           │ 需量利用率: 76.9%                    │ ││
│  │ │ 户号: 44012536             │                                      │ ││
│  │ └─────────────────────────────────────────────────────────────────────┘ ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 5.7.6 用电设备配置页面

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 用电管理 > 用电设备管理                                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ 搜索: [____________] 设备类型: [全部 ▼] 回路: [全部 ▼] 是否计量: [全部▼]│ │
│ │                                                         [+ 新建] [导入] │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌────────────────────────────────────────────────────────────────────────┐  │
│ │编码    │名称      │类型    │额定功率│回路    │监控设备│点位状态│ 操作  │  │
│ ├────────────────────────────────────────────────────────────────────────┤  │
│ │DEV-001│UPS-1号机 │UPS    │ 200kW │C001   │UPS-01 │ ✅已配 │[配置] │  │
│ │DEV-002│精密空调1 │HVAC   │ 50kW  │C004   │AC-01  │ ✅已配 │[配置] │  │
│ │DEV-003│精密空调2 │HVAC   │ 50kW  │C005   │AC-02  │ ✅已配 │[配置] │  │
│ │DEV-004│机柜PDU-A1│IT_PDU │ 20kW  │C002   │  -    │ ⚠未配 │[配置] │  │
│ │DEV-005│机柜PDU-A2│IT_PDU │ 20kW  │C002   │  -    │ ⚠未配 │[配置] │  │
│ │DEV-006│照明系统  │LIGHTING│ 10kW │C006   │  -    │ ⚠未配 │[配置] │  │
│ └────────────────────────────────────────────────────────────────────────┘  │
│                                                          [1] [2] [>]        │
│                                                                             │
│ 统计: 总设备 25 台 | 已配置点位 15 台 | 未配置 10 台 | IT负载 8 台           │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────── 用电设备配置对话框 ──────────────────────────────┐
│                                                                    [×]     │
│  ┌────────────┬────────────┬────────────┐                                  │
│  │ 基本信息   │ 点位关联   │ 负荷转移   │                                  │
│  └────────────┴────────────┴────────────┘                                  │
│                                                                            │
│  ═══════════════════════════ 基本信息 ════════════════════════════════════ │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 设备编码:   [DEV-001___]    设备名称:   [UPS-1号机_____________]      │  │
│  │ 设备类型:   [UPS ▼]                                                  │  │
│  │            ┌──────────────────────────────────────────────────┐      │  │
│  │            │ UPS        - 不间断电源                          │      │  │
│  │            │ HVAC       - 暖通空调                            │      │  │
│  │            │ IT_SERVER  - IT服务器                            │      │  │
│  │            │ IT_STORAGE - 存储设备                            │      │  │
│  │            │ IT_PDU     - 机柜配电                            │      │  │
│  │            │ LIGHTING   - 照明                                │      │  │
│  │            │ PUMP       - 水泵                                │      │  │
│  │            │ OTHER      - 其他                                │      │  │
│  │            └──────────────────────────────────────────────────┘      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 额定功率:   [200_______] kW     额定电压:   [380_______] V           │  │
│  │ 额定电流:   [304_______] A      功率因数:   [0.95______]             │  │
│  │ 效率:       [95________] %      相位类型:   (●) 三相  ( ) 单相       │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 所属回路:   [C001-UPS主路 ▼]                                         │  │
│  │ 区域代码:   [A01_______]                                             │  │
│  │ [✓] 是否计量    [✓] IT负载(参与PUE计算)   [✓] 关键负荷(不可中断)     │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│                                              [取消]  [下一步 >]             │
└────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────── 用电设备配置对话框 ──────────────────────────────┐
│                                                                    [×]     │
│  ┌────────────┬────────────┬────────────┐                                  │
│  │ 基本信息   │ 点位关联   │ 负荷转移   │                                  │
│  └────────────┴────────────┴────────────┘                                  │
│                                                                            │
│  ═══════════════════════════ 点位关联 ════════════════════════════════════ │
│                                                                            │
│  关联动环监控设备 (从动环系统已配置的设备中选择)                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 监控设备:   [UPS-01 - UPS监控模块-1号 ▼]                              │  │
│  │            设备类型: UPS | 协议: Modbus | 状态: 在线                  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  电力数据点位关联 (从监控设备的点位中选择对应数据点)                         │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                                                                      │  │
│  │  有功功率点位:  [AI-UPS01-Power - UPS有功功率 ▼]      当前: 165.2 kW │  │
│  │                 类型: AI | 单位: kW | 系数: 1                        │  │
│  │                                                                      │  │
│  │  累计电量点位:  [AI-UPS01-Energy - UPS累计电量 ▼]     当前: 89520 kWh│  │
│  │                 类型: AI | 单位: kWh | 系数: 1                       │  │
│  │                                                                      │  │
│  │  电压点位:      [AI-UPS01-Voltage - UPS输出电压 ▼]    当前: 382.5 V  │  │
│  │                 类型: AI | 单位: V | 系数: 1                         │  │
│  │                                                                      │  │
│  │  电流点位:      [AI-UPS01-Current - UPS输出电流 ▼]    当前: 280.5 A  │  │
│  │                 类型: AI | 单位: A | 系数: 1                         │  │
│  │                                                                      │  │
│  │  功率因数点位:  [AI-UPS01-PF - UPS功率因数 ▼]         当前: 0.95     │  │
│  │                 类型: AI | 单位: - | 系数: 0.01                      │  │
│  │                                                                      │  │
│  │  ────────────────────────────────────────────────────────────────    │  │
│  │  💡 提示: 选择点位后，系统将自动从动环监控系统获取实时用电数据        │  │
│  │     用于能耗统计、功率曲线绘制和节能分析                              │  │
│  │                                                                      │  │
│  │  [🔍 查看该设备所有可用点位]                                          │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│                                       [< 上一步]  [下一步 >]               │
└────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────── 用电设备配置对话框 ──────────────────────────────┐
│                                                                    [×]     │
│  ┌────────────┬────────────┬────────────┐                                  │
│  │ 基本信息   │ 点位关联   │ 负荷转移   │                                  │
│  └────────────┴────────────┴────────────┘                                  │
│                                                                            │
│  ═══════════════════════════ 负荷转移配置 ════════════════════════════════ │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  [✗] 启用负荷转移 (允许系统在峰谷时段建议调整该设备运行)              │  │
│  │                                                                      │  │
│  │  ⚠ 当前设备标记为"关键负荷"，不建议启用负荷转移                      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  转移参数 (仅当启用负荷转移时生效)                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 可转移功率比例: [0_________] %  (0-100，表示可调节的功率百分比)       │  │
│  │ 最低运行功率:   [__________] kW (空置表示可完全停机)                  │  │
│  │ 最大爬坡速率:   [__________] kW/min (功率变化速率限制)                │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  时间约束                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 允许转移时段:                                                        │  │
│  │ [00][01][02][03][04][05][06][07][08][09][10][11]                     │  │
│  │ [ ][ ][ ][ ][ ][ ][ ][ ][ ][ ][ ][ ]                                 │  │
│  │ [12][13][14][15][16][17][18][19][20][21][22][23]                     │  │
│  │ [ ][ ][ ][ ][ ][ ][ ][ ][ ][ ][ ][ ]                                 │  │
│  │                                               [全选] [清空] [仅谷时]  │  │
│  │                                                                      │  │
│  │ 最小连续运行时间: [__________] 小时                                  │  │
│  │ 最大转移持续时间: [__________] 小时                                  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  审批设置                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 转移提前通知时间: [30________] 分钟                                  │  │
│  │ [✓] 需要人工确认 (系统只生成建议，执行需人工确认)                     │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│                                       [< 上一步]  [保存]                   │
└────────────────────────────────────────────────────────────────────────────┘
```

#### 5.7.7 需量配置分析页面

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 用电管理 > 需量配置分析                                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ 计量点选择: [M001 - 总计量点 ▼]     分析周期: [最近12个月 ▼]  [分析]    │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌────────────────────────────────────────────────────────────────────────┐  │
│ │ 📊 需量配置概览                                                         │  │
│ │ ┌──────────────────────────────────────────────────────────────────┐   │  │
│ │ │ 当前申报需量    │ 分析期最大需量  │ 平均需量      │ 利用率        │   │  │
│ │ │     800 kW     │    685 kW     │   520 kW    │   85.6%      │   │  │
│ │ │                │  (2025-07-15)  │              │  (最大/申报)  │   │  │
│ │ └──────────────────────────────────────────────────────────────────┘   │  │
│ └────────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│ ┌────────────────────────────────────────────────────────────────────────┐  │
│ │ 📈 需量历史趋势                                                         │  │
│ │ ┌──────────────────────────────────────────────────────────────────┐   │  │
│ │ │ kW                                                                │   │  │
│ │ │ 900┼───────────────────────────────────────── 申报需量 800kW ─── │   │  │
│ │ │    │                                                              │   │  │
│ │ │ 750┼─────────╲╱────────────────────────╲──── 建议需量 700kW ─── │   │  │
│ │ │    │        ╱  ╲    ╱╲        ╱╲      ╱ ╲                       │   │  │
│ │ │ 600┼───────╱────╲──╱──╲──────╱──╲────╱───╲──────────────────── │   │  │
│ │ │    │      ╱      ╲╱    ╲    ╱    ╲  ╱     ╲                     │   │  │
│ │ │ 450┼─────╱────────────────╲╱──────╲╱───────╲─ 平均需量 520kW ── │   │  │
│ │ │    │    ╱                  ╲                ╲                    │   │  │
│ │ │ 300┼───╱────────────────────╲────────────────────────────────── │   │  │
│ │ │    └───┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴───   │   │  │
│ │ │       1月   2月  3月  4月   5月  6月  7月   8月  9月  10月 11月   │   │  │
│ │ │                                                                  │   │  │
│ │ │ [━ 最大需量  ━ 平均需量  --- 申报需量  --- 建议需量]              │   │  │
│ │ └──────────────────────────────────────────────────────────────────┘   │  │
│ └────────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│ ┌────────────────────────────┬───────────────────────────────────────────┐  │
│ │ ⚙️ 配置分析结果             │ 💰 费用优化建议                           │  │
│ │                            │                                           │  │
│ │ 分析状态: 🟡 可优化        │ 当前需量电费 (按800kW):                    │  │
│ │                            │ ¥30,400/月 = 800 × 38元/kW                │  │
│ │ ┌────────────────────────┐ │                                           │  │
│ │ │ 当前配置: 800 kW       │ │ 优化方案对比:                             │  │
│ │ │ 建议配置: 700 kW       │ │ ┌─────────────────────────────────────┐   │  │
│ │ │ 调整幅度: -12.5%       │ │ │ 方案    │ 需量 │ 月需量费│ 超限风险│   │  │
│ │ │                        │ │ ├─────────────────────────────────────┤   │  │
│ │ │ 95%分位需量: 658 kW    │ │ │ 保守    │ 750  │ ¥28,500 │ 极低   │   │  │
│ │ │ 最大需量:    685 kW    │ │ │ 推荐    │ 700  │ ¥26,600 │ 低     │   │  │
│ │ │ 超限次数:    0 次/年   │ │ │ 激进    │ 650  │ ¥24,700 │ 中     │   │  │
│ │ │                        │ │ └─────────────────────────────────────┘   │  │
│ │ │ 富裕容量: 115 kW       │ │                                           │  │
│ │ │ (浪费比例: 14.4%)      │ │ 推荐方案预计年节省:                        │  │
│ │ └────────────────────────┘ │ (800-700) × 38 × 12 = ¥45,600/年          │  │
│ │                            │                                           │  │
│ │ [📄 生成分析报告]          │ [应用推荐方案]                             │  │
│ └────────────────────────────┴───────────────────────────────────────────┘  │
│                                                                             │
│ ┌────────────────────────────────────────────────────────────────────────┐  │
│ │ ⚠️ 风险提示                                                             │  │
│ │ • 调低申报需量后，若实际用电超出申报值，将产生超需量罚款                   │  │
│ │ • 罚款计算: 超出部分 × 2倍需量电价                                       │  │
│ │ • 建议结合业务增长预期和季节性因素综合考虑                                │  │
│ │ • 重大用电变化前应提前调整申报需量                                        │  │
│ └────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 5.7.8 负荷转移分析页面

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 用电管理 > 负荷转移分析                                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ 分析周期: [最近30天 ▼]   计量点: [全部 ▼]   设备类型: [全部 ▼]  [分析]  │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌────────────────────────────────────────────────────────────────────────┐  │
│ │ 📊 峰谷用电分布概览                                                      │  │
│ │ ┌────────────────────────────────────────────────────────────────────┐ │  │
│ │ │            ┌─────────────────────────────────────────────────┐     │ │  │
│ │ │            │                     总用电量分布                 │     │ │  │
│ │ │            │    ┌────────┐                                   │     │ │  │
│ │ │            │    │ 峰时   │ 45.2%  (13,560 kWh)  ¥16,272      │     │ │  │
│ │ │            │    │████████│                                   │     │ │  │
│ │ │            │    │ 平时   │ 32.5%  (9,750 kWh)   ¥7,800       │     │ │  │
│ │ │            │    │█████   │                                   │     │ │  │
│ │ │            │    │ 谷时   │ 22.3%  (6,690 kWh)   ¥2,676       │     │ │  │
│ │ │            │    │████    │                                   │     │ │  │
│ │ │            │    └────────┘                                   │     │ │  │
│ │ │            └─────────────────────────────────────────────────┘     │ │  │
│ │ └────────────────────────────────────────────────────────────────────┘ │  │
│ │ 优化潜力: 若将10%峰时用电转移至谷时，预计月节省 ¥1,356                   │  │
│ └────────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│ ┌────────────────────────────────────────────────────────────────────────┐  │
│ │ 🔄 可转移负荷设备分析                                                    │  │
│ │                                                                         │  │
│ │ ┌──────────────────────────────────────────────────────────────────┐   │  │
│ │ │ 设备    │类型 │额定功率│峰时占比│谷时占比│可转移│节省潜力 │建议   │   │  │
│ │ ├──────────────────────────────────────────────────────────────────┤   │  │
│ │ │精密空调1│HVAC│ 50kW  │ 52%   │ 18%   │ 30%  │¥456/月 │⬇降载  │   │  │
│ │ │精密空调2│HVAC│ 50kW  │ 48%   │ 22%   │ 30%  │¥312/月 │⬇降载  │   │  │
│ │ │照明系统 │LIGHT│ 10kW │ 72%   │ 8%    │ 50%  │¥180/月 │⏰调时  │   │  │
│ │ │水泵-1  │PUMP│ 15kW  │ 62%   │ 15%   │ 40%  │¥168/月 │⏰调时  │   │  │
│ │ │ ─────────────────────────────────────────────────────────────── │   │  │
│ │ │ UPS-1  │UPS │200kW  │ 44%   │ 24%   │  -   │   -   │🔒关键  │   │  │
│ │ │ 服务器群│IT  │150kW  │ 46%   │ 23%   │  -   │   -   │🔒关键  │   │  │
│ │ └──────────────────────────────────────────────────────────────────┘   │  │
│ │                                                                         │  │
│ │ 汇总: 可转移设备 4 台 | 总可转移功率 45kW | 预计月节省 ¥1,116            │  │
│ └────────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│ ┌────────────────────────────────────────────────────────────────────────┐  │
│ │ 📋 负荷转移建议详情                                                      │  │
│ │                                                                         │  │
│ │ ┌──────────────────────────────────────────────────────────────────┐   │  │
│ │ │ 🟢 建议1: 精密空调错峰运行                            节省¥768/月 │   │  │
│ │ │ ──────────────────────────────────────────────────────────────── │   │  │
│ │ │ 涉及设备: 精密空调1、精密空调2                                    │   │  │
│ │ │ 建议措施: 峰时(10:00-12:00)将设定温度提高2℃，降低30%制冷功率     │   │  │
│ │ │ 转移时段: 峰时 → 平时/谷时                                        │   │  │
│ │ │ 前提条件: 室内温度不超过26℃，服务器进风温度不超过24℃              │   │  │
│ │ │                                                                  │   │  │
│ │ │ 分析依据:                                                         │   │  │
│ │ │ • 当前峰时平均功率: 85kW (两台合计)                                │   │  │
│ │ │ • 建议峰时平均功率: 60kW                                          │   │  │
│ │ │ • 功率差值: 25kW × 4小时/天 × 30天 = 3,000 kWh/月                 │   │  │
│ │ │ • 节省电费: 3,000 × (1.2-0.4) × 80% = ¥768/月                     │   │  │
│ │ │                                                                  │   │  │
│ │ │                                               [接受] [拒绝] [详情]│   │  │
│ │ └──────────────────────────────────────────────────────────────────┘   │  │
│ │                                                                         │  │
│ │ ┌──────────────────────────────────────────────────────────────────┐   │  │
│ │ │ 🟢 建议2: 照明系统定时控制                            节省¥180/月 │   │  │
│ │ │ ──────────────────────────────────────────────────────────────── │   │  │
│ │ │ 涉及设备: 照明系统                                                │   │  │
│ │ │ 建议措施: 将部分照明从峰时段(18:00-21:00)调整至谷时段提前开启      │   │  │
│ │ │ ...                                                              │   │  │
│ │ │                                               [接受] [拒绝] [详情]│   │  │
│ │ └──────────────────────────────────────────────────────────────────┘   │  │
│ └────────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│ ┌────────────────────────────────────────────────────────────────────────┐  │
│ │ 📈 预期效果模拟                                                [运行模拟]│  │
│ │                                                                         │  │
│ │ 若执行所有建议后的预期效果:                                              │  │
│ │ • 峰时用电占比: 45.2% → 38.5% (↓6.7%)                                  │  │
│ │ • 谷时用电占比: 22.3% → 28.8% (↑6.5%)                                  │  │
│ │ • 预计月节省电费: ¥1,116                                                │  │
│ │ • 预计年节省电费: ¥13,392                                               │  │
│ └────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 5.7.9 电价配置页面

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 用电管理 > 电价配置                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ 电价方案: [工业峰谷分时电价(2024) ▼]              [+ 新建方案] [导入]    │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌────────────────────────────────────────────────────────────────────────┐  │
│ │ 📋 电价方案详情                                                         │  │
│ │                                                                         │  │
│ │ 方案名称: 工业峰谷分时电价(2024)                                         │  │
│ │ 生效日期: 2024-01-01        失效日期: 2024-12-31                        │  │
│ │ 状态: ✅ 当前生效                                                       │  │
│ │                                                                         │  │
│ │ ┌──────────────────────────────────────────────────────────────────┐   │  │
│ │ │ 时段类型 │ 时段范围                      │ 电价(元/kWh) │ 操作   │   │  │
│ │ ├──────────────────────────────────────────────────────────────────┤   │  │
│ │ │ 🔴 尖峰  │ 10:00-12:00, 19:00-21:00     │    1.50      │ [编辑] │   │  │
│ │ │ 🟠 峰时  │ 08:00-10:00, 12:00-14:00,    │    1.20      │ [编辑] │   │  │
│ │ │         │ 17:00-19:00, 21:00-23:00     │              │        │   │  │
│ │ │ 🟢 平时  │ 07:00-08:00, 14:00-17:00,    │    0.80      │ [编辑] │   │  │
│ │ │         │ 23:00-24:00                  │              │        │   │  │
│ │ │ 🔵 谷时  │ 00:00-07:00                  │    0.40      │ [编辑] │   │  │
│ │ └──────────────────────────────────────────────────────────────────┘   │  │
│ │                                                                         │  │
│ │ 需量电价: 38.00 元/kW·月                                                │  │
│ │ 基本电费: 按最大需量计算                                                 │  │
│ └────────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│ ┌────────────────────────────────────────────────────────────────────────┐  │
│ │ 🕐 24小时时段分布图                                                      │  │
│ │ ┌──────────────────────────────────────────────────────────────────┐   │  │
│ │ │ 00 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23│  │
│ │ │ 🔵🔵🔵🔵🔵🔵🔵🟢🟠🟠🔴🔴🟠🟠🟢🟢🟢🟠🟠🔴🔴🟠🟠🟢 │   │  │
│ │ │                                                                  │   │  │
│ │ │ 图例: 🔴尖峰(¥1.50)  🟠峰时(¥1.20)  🟢平时(¥0.80)  🔵谷时(¥0.40) │   │  │
│ │ └──────────────────────────────────────────────────────────────────┘   │  │
│ └────────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│ ┌────────────────────────────────────────────────────────────────────────┐  │
│ │ 📌 计量点电价关联                                                        │  │
│ │ ┌──────────────────────────────────────────────────────────────────┐   │  │
│ │ │ 计量点编码 │ 计量点名称   │ 当前电价方案              │ 操作      │   │  │
│ │ ├──────────────────────────────────────────────────────────────────┤   │  │
│ │ │ M001      │ 总计量点     │ 工业峰谷分时电价(2024)    │ [变更]   │   │  │
│ │ │ M002      │ 机房计量点   │ 工业峰谷分时电价(2024)    │ [变更]   │   │  │
│ │ │ M003      │ 空调计量点   │ 工业峰谷分时电价(2024)    │ [变更]   │   │  │
│ │ └──────────────────────────────────────────────────────────────────┘   │  │
│ └────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────── 电价时段编辑 ────────────────────────────┐
│                                                                    [×]     │
│                                                                            │
│  时段类型: 🔴 尖峰时段                                                     │
│                                                                            │
│  电价设置                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 电价:       [1.50______] 元/kWh                                      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  时段范围 (可添加多个时段)                                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 时段1: [10:00] - [12:00]                                    [删除]   │  │
│  │ 时段2: [19:00] - [21:00]                                    [删除]   │  │
│  │                                                                      │  │
│  │                                               [+ 添加时段]            │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  生效设置                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ 生效日期:   [2024-01-01 📅]     失效日期:   [2024-12-31 📅]          │  │
│  │ [✓] 启用                                                             │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│                                              [取消]  [保存]                 │
└────────────────────────────────────────────────────────────────────────────┘
```

---

### 5.6 V2.3 功能增强设计

#### 5.6.1 监控仪表盘增强

**设计目标**: 在主监控仪表盘中集成关键能耗、效率、建议等信息，让用户一目了然掌握系统状态。

**新增仪表盘卡片**:

| 卡片名称 | 显示内容 | 数据来源 | 刷新频率 |
|---------|---------|---------|---------|
| 实时功率卡片 | 总功率、IT功率、基础设施功率、趋势图 | /v1/realtime/energy-dashboard | 5秒 |
| PUE效率卡片 | 当前PUE、趋势、同比、目标差距 | /v1/realtime/energy-dashboard | 5秒 |
| 需量状态卡片 | 当前需量、申报需量、利用率、风险预警 | /v1/realtime/energy-dashboard | 5秒 |
| 成本卡片 | 今日电费、本月累计、同比变化、峰谷占比 | /v1/realtime/energy-dashboard | 5秒 |
| 节能建议卡片 | 待处理建议数、潜在节能量、快速入口 | /v1/realtime/energy-dashboard | 30秒 |

**能源仪表盘综合API设计**:

```python
GET /v1/realtime/energy-dashboard

Response:
{
  "power": {
    "total": 45.2,              // 总功率 kW
    "it_power": 30.5,           // IT功率 kW
    "infrastructure_power": 14.7, // 基础设施功率 kW
    "trend_1h": [42.1, 43.5, 44.2, 45.2],  // 近1小时趋势
    "time_labels": ["10:00", "10:15", "10:30", "10:45"]
  },
  "pue": {
    "current": 1.48,            // 当前PUE
    "target": 1.50,             // 目标PUE
    "trend_24h": [1.52, 1.50, 1.48, 1.47],  // 24小时趋势
    "yoy_change": -0.05,        // 同比变化
    "status": "优秀"            // 状态评级
  },
  "demand": {
    "current": 42.3,            // 当前需量 kW
    "declared": 50.0,           // 申报需量 kW
    "utilization": 84.6,        // 利用率 %
    "risk_level": "安全",       // 风险等级
    "next_15min_forecast": 43.1 // 下一个15分钟预测
  },
  "cost": {
    "today": 125.5,             // 今日电费 元
    "month": 3200.8,            // 本月电费 元
    "yoy_change": -8.5,         // 同比变化 %
    "peak_ratio": 45.2,         // 峰时占比 %
    "valley_ratio": 30.1        // 谷时占比 %
  },
  "suggestions": {
    "pending_count": 5,         // 待处理建议数
    "potential_saving": 1200,   // 潜在节能量 元/月
    "high_priority_count": 2    // 高优先级建议数
  }
}
```

---

#### 5.6.2 负荷功率调节功能设计

**设计目标**: 允许用户通过调节设备参数（温度、亮度、运行模式等）来降低功耗，支持实时模拟、预测和应用。

**支持的调节类型**:

| 调节类型 | 设备举例 | 可调参数 | 功率映射算法 |
|---------|---------|---------|-------------|
| temperature | 空调 | 温度 22-28°C，步长0.5°C | 温度每升高1°C降低功率8% |
| brightness | 照明 | 亮度 0-100%，步长10% | 功率与亮度线性关系 |
| mode | UPS/空调 | 高性能/节能/休眠 | 模式固定功率系数 |
| load | 可调负载 | 优先级1-5 | 按优先级削减功率 |

**调节配置数据模型** (LoadRegulationConfig):

```python
{
  "id": 1,
  "device_id": 5,                    // 关联设备ID
  "device_name": "空调1",
  "regulation_type": "temperature",   // 调节类型
  "current_value": 24.0,             // 当前值
  "min_value": 22.0,                 // 最小值
  "max_value": 28.0,                 // 最大值
  "step": 0.5,                       // 步长
  "unit": "°C",                      // 单位
  "base_power": 5.0,                 // 基准功率 kW
  "power_factor": -0.08,             // 功率系数 (每单位变化的功率变化率)
  "regulation_curve": {              // 功率曲线 (JSON)
    "22": 5.5, "24": 5.0, "26": 4.5, "28": 4.0
  },
  "is_enabled": true,                // 是否启用
  "comfort_threshold": {             // 舒适度阈值
    "min": 23.0, "max": 26.0
  },
  "auto_regulation": false           // 是否自动调节
}
```

**调节历史记录模型** (RegulationHistory):

```python
{
  "id": 1,
  "config_id": 1,
  "device_name": "空调1",
  "regulation_type": "temperature",
  "old_value": 24.0,
  "new_value": 26.0,
  "power_change": -0.4,              // 功率变化 kW
  "trigger_reason": "demand_response", // 触发原因 (manual/auto/demand_response/scheduled)
  "executed_by": "admin",
  "executed_at": "2026-01-14 14:30:00",
  "status": "success",               // 执行状态
  "notes": "需量响应调节"
}
```

**核心API设计**:

```python
# 1. 获取调节配置列表
GET /v1/regulation/configs
Response: List[LoadRegulationConfig]

# 2. 模拟调节效果
POST /v1/regulation/simulate
Request: {
  "config_id": 1,
  "new_value": 26.0
}
Response: {
  "current_power": 5.0,
  "predicted_power": 4.6,
  "power_saving": 0.4,              // kW
  "daily_energy_saving": 9.6,       // kWh/天
  "monthly_cost_saving": 180,       // 元/月
  "comfort_impact": "轻微",         // 舒适度影响
  "performance_impact": "无"        // 性能影响
}

# 3. 应用调节方案
POST /v1/regulation/apply
Request: {
  "config_id": 1,
  "new_value": 26.0,
  "trigger_reason": "manual",
  "notes": "用户手动调节"
}
Response: {
  "success": true,
  "message": "调节已应用",
  "history_id": 123
}

# 4. 获取调节建议
GET /v1/regulation/recommendations
Response: [
  {
    "config_id": 1,
    "device_name": "空调1",
    "current_value": 24.0,
    "recommended_value": 26.0,
    "reason": "当前需量接近申报值，建议调节空调温度降低功耗",
    "potential_saving": 0.4,        // kW
    "priority": "high"
  }
]
```

**前端调节页面功能** (regulation.vue):
- 调节配置管理表格（显示、编辑、删除）
- 滑块控制器实时调节
- 模拟结果弹窗（功率变化、成本节省、影响评估）
- 调节建议列表（一键应用）
- 调节历史记录追溯

---

#### 5.6.3 需量分析方法增强

**设计目标**: 实现15分钟粒度的需量分析，提供详细的需量曲线、峰值分析和优化方案。

**15分钟需量计算算法**:

```python
# 滑动窗口算法
def calculate_15min_demand(power_samples):
    """
    输入: 每分钟功率采样值 (15个值)
    输出: 15分钟需量 (平均功率)

    公式: 需量 = sum(功率采样) / 采样数
    """
    return sum(power_samples) / len(power_samples)

# 滚动需量计算
def calculate_rolling_demand(current_power, history_window):
    """
    输入: 当前功率 + 历史14分钟功率
    输出: 滚动窗口需量

    用途: 实时预测下一个计量周期的需量
    """
    window_data = history_window + [current_power]
    return sum(window_data) / 15
```

**需量数据表设计** (Demand15MinData):

```python
{
  "id": 1,
  "meter_point_id": 1,               // 计量点ID
  "timestamp": "2026-01-14 14:15:00", // 15分钟整点
  "average_power": 42.5,             // 15分钟平均功率 kW
  "rolling_demand": 43.1,            // 滚动窗口需量 kW
  "time_period": "peak",             // 分时标识 (peak/flat/valley)
  "is_peak_period": true,            // 是否峰时
  "is_over_declared": false,         // 是否超申报
  "weather_temp": 28.5,              // 环境温度 (可选)
  "notes": null
}
```

**需量分析记录表** (DemandAnalysisRecord):

```python
{
  "id": 1,
  "meter_point_id": 1,
  "analysis_period": "2026-01",      // 分析周期
  "max_demand": 48.5,                // 最大需量 kW
  "avg_demand": 38.2,                // 平均需量 kW
  "min_demand": 28.5,                // 最小需量 kW
  "percentile_95": 45.3,             // 95%分位数需量
  "declared_demand": 50.0,           // 申报需量 kW
  "utilization_rate": 90.6,          // 需量利用率 %
  "over_count": 0,                   // 超限次数
  "risk_score": 15,                  // 风险评分 (0-100)
  "optimization_plan": {             // 优化方案 (JSON)
    "conservative": 48.0,
    "recommended": 46.0,
    "aggressive": 44.0
  },
  "recommendations": [               // 推荐措施
    "建议将申报需量调整为46kW",
    "峰时段优化设备运行策略",
    "启用负荷调节自动化"
  ]
}
```

**需量分析API增强**:

```python
# 1. 获取15分钟需量曲线
GET /v1/energy/demand/15min-curve?start_time=2026-01-14&end_time=2026-01-15
Response: {
  "data": [
    {"time": "00:15", "demand": 35.2, "period": "valley", "is_over": false},
    {"time": "00:30", "demand": 34.8, "period": "valley", "is_over": false},
    ...
  ],
  "declared_demand": 50.0,
  "max_demand": 48.5,
  "avg_demand": 38.2
}

# 2. 需量峰值分析
GET /v1/energy/demand/peak-analysis?period=2026-01
Response: {
  "max_demand": 48.5,
  "max_time": "2026-01-15 14:45:00",
  "top_10_peaks": [
    {"time": "2026-01-15 14:45", "demand": 48.5, "period": "peak"},
    {"time": "2026-01-10 15:00", "demand": 47.2, "period": "peak"},
    ...
  ],
  "peak_distribution": {             // 峰值分布
    "morning": 2, "afternoon": 5, "evening": 3
  },
  "contributing_devices": [          // 贡献设备
    {"device": "空调系统", "contribution": 45%},
    {"device": "服务器", "contribution": 30%}
  ]
}

# 3. 需量优化方案
GET /v1/energy/demand/optimization-plan?period=2026-01
Response: {
  "current_declared": 50.0,
  "utilization_rate": 90.6,
  "risk_level": "低",
  "plans": [
    {
      "type": "conservative",
      "demand": 48.0,
      "monthly_fee": 960,
      "risk": "极低",
      "description": "保留安全余量"
    },
    {
      "type": "recommended",
      "demand": 46.0,
      "monthly_fee": 920,
      "savings": 40,
      "risk": "低",
      "description": "推荐方案，性价比最优"
    },
    {
      "type": "aggressive",
      "demand": 44.0,
      "monthly_fee": 880,
      "savings": 80,
      "risk": "中",
      "description": "激进方案，需加强管控"
    }
  ],
  "recommendations": [
    "推荐采用46kW方案",
    "配合负荷调节自动化",
    "建立峰时段应急预案"
  ]
}
```

---

#### 5.6.4 节能建议模板库设计

**设计目标**: 建立10+种节能建议模板，通过自动分析引擎定期检测数据并生成针对性建议。

**建议模板库**（10+种模板）:

| 模板ID | 模板名称 | 类别 | 触发条件 | 优先级 | 难度 |
|-------|---------|------|---------|-------|------|
| pue_high | PUE过高优化 | pue | PUE > 1.6 | 高 | 中 |
| pue_cooling | 制冷系统优化 | pue | 制冷功耗占比 > 40% | 高 | 中 |
| ac_temp_low | 空调温度过低 | efficiency | 平均温度 < 23°C | 中 | 易 |
| ac_temp_high | 空调温度过高 | efficiency | 平均温度 > 27°C | 中 | 易 |
| peak_ratio_high | 峰时用电过高 | cost | 峰时用电 > 50% | 高 | 中 |
| valley_underuse | 谷时利用不足 | cost | 谷时用电 < 20% | 中 | 难 |
| demand_over | 需量申报不合理 | demand | 利用率 < 80% 或 > 95% | 高 | 易 |
| demand_overrun | 需量超限风险 | demand | 接近申报值90% | 紧急 | 易 |
| device_idle | 设备长时间空载 | efficiency | 负载率 < 20% 持续4h | 中 | 易 |
| power_factor_low | 功率因数偏低 | efficiency | 功率因数 < 0.9 | 中 | 中 |
| load_unbalanced | 三相负载不平衡 | efficiency | 不平衡度 > 10% | 中 | 中 |
| redundant_device | 冗余设备运行 | efficiency | 多台同类设备低负载 | 中 | 中 |
| night_high_load | 夜间负载异常高 | maintenance | 23:00-6:00负载 > 白天70% | 中 | 易 |
| cooling_efficiency | 制冷效率低下 | efficiency | 空调COP < 2.5 | 高 | 难 |
| ups_efficiency | UPS效率低下 | efficiency | UPS效率 < 90% | 中 | 难 |

**建议数据模型增强** (EnergySuggestion V2.3):

```python
{
  "id": 1,
  "template_id": "pue_high",         // V2.3新增：模板ID
  "category": "pue",                 // V2.3新增：类别
  "title": "PUE过高，建议优化制冷系统",
  "problem_description": "当前PUE为1.75，高于行业标准1.5，主要原因是制冷系统能耗过高", // V2.3新增
  "analysis_detail": "经分析，空调系统功耗占总功耗的45%，高于标准值30-35%。温度设定过低（平均22°C）是主要原因。", // V2.3新增
  "implementation_steps": [          // V2.3新增：实施步骤（JSON）
    {"step": 1, "action": "将空调温度调至24-26°C", "duration": "即时"},
    {"step": 2, "action": "检查冷通道封闭情况", "duration": "1天"},
    {"step": 3, "action": "清洁空调滤网和冷凝器", "duration": "2天"}
  ],
  "expected_effect": {               // V2.3新增：预期效果（JSON）
    "pue_reduction": 0.15,           // PUE降低
    "power_saving": 3.5,             // 节电 kW
    "cost_saving": 1200              // 节省成本 元/月
  },
  "priority": "high",
  "difficulty": "medium",            // V2.3新增：难度等级
  "payback_period": "1个月",         // V2.3新增：投资回收期
  "status": "pending",
  "potential_saving": 1200,          // 元/月
  "created_at": "2026-01-14 10:00:00"
}
```

**自动分析引擎工作流程**:

```python
# 定时任务: 每小时执行一次
def auto_generate_suggestions():
    # 1. 获取最新数据
    latest_data = get_latest_energy_data()

    # 2. 遍历所有模板，检查触发条件
    for template in SUGGESTION_TEMPLATES:
        if check_trigger_condition(template, latest_data):
            # 3. 生成建议（填充模板参数）
            suggestion = generate_from_template(template, latest_data)

            # 4. 去重（同模板24小时内只生成一次）
            if not exists_recent_suggestion(template.id, hours=24):
                # 5. 保存到数据库
                save_suggestion(suggestion)

    return {"generated_count": count}
```

**节能建议增强API**:

```python
# 1. 获取建议模板列表
GET /v1/energy/suggestions/templates
Response: [
  {
    "template_id": "pue_high",
    "name": "PUE过高优化",
    "category": "pue",
    "priority": "high",
    "difficulty": "medium",
    "trigger_condition": "PUE > 1.6"
  },
  ...
]

# 2. 触发建议分析（手动触发）
POST /v1/energy/suggestions/analyze
Request: {
  "force_refresh": true              // 强制刷新（忽略24小时去重）
}
Response: {
  "success": true,
  "generated_count": 3,
  "suggestions": [...]
}

# 3. 获取建议汇总
GET /v1/energy/suggestions/summary
Response: {
  "total_count": 8,
  "by_status": {
    "pending": 5,
    "accepted": 2,
    "completed": 1
  },
  "by_priority": {
    "high": 3,
    "medium": 4,
    "low": 1
  },
  "by_category": {
    "pue": 2,
    "cost": 3,
    "demand": 1,
    "efficiency": 2
  },
  "total_potential_saving": 5600     // 元/月
}
```

---

#### 5.6.5 数据库设计汇总（V2.3新增/修改）

**新增表**:

1. **load_regulation_configs** - 负荷调节配置
2. **regulation_history** - 调节历史记录
3. **demand_15min_data** - 15分钟需量数据
4. **demand_analysis_records** - 需量分析记录

**修改表**:

1. **power_curve_data** - 增加字段:
   - demand_15min (15分钟需量)
   - demand_rolling (滚动窗口需量)

2. **energy_suggestions** - 增加字段:
   - template_id (模板ID)
   - category (类别)
   - problem_description (问题描述)
   - analysis_detail (详细分析)
   - implementation_steps (实施步骤 JSON)
   - expected_effect (预期效果 JSON)
   - difficulty (难度等级)
   - payback_period (投资回收期)

---

#### 5.6.6 V2.3功能实现检查清单

| 功能模块 | 后端服务 | 后端API | 数据模型 | 前端API | 前端页面 | 状态 |
|---------|---------|---------|---------|---------|---------|------|
| 负荷调节 | load_regulation.py | regulation.py | LoadRegulationConfig ✓ | energy.ts | regulation.vue | ✅ 完成 |
| 节能建议引擎 | suggestion_engine.py | energy.py | EnergySuggestion增强 ✓ | energy.ts | suggestions.vue | ✅ 完成 |
| 需量分析增强 | energy_analysis.py | energy.py | Demand15MinData ✓ | energy.ts | analysis.vue | ✅ 完成 |
| 仪表盘增强 | realtime.py | realtime.py | - | realtime.ts | dashboard/index.vue | ⚠️ 80% |

**待完成项**:
- 前端仪表盘新增能耗、需量、PUE、成本、建议等5个卡片组件

---

## 六、技术选型确认

### 5.1 后端技术栈

| 组件 | 技术 | 版本 | 说明 |
|------|------|------|------|
| 框架 | FastAPI | 0.109+ | 高性能异步框架 |
| ORM | SQLAlchemy | 2.0+ | 数据库ORM |
| 数据库 | SQLite/MySQL | - | 主数据库 |
| 缓存 | 内存字典 | - | 实时数据缓存 |
| 定时任务 | APScheduler | 3.10+ | 任务调度 |
| WebSocket | fastapi | 内置 | 实时通信 |
| 认证 | JWT | python-jose | Token认证 |
| 验证 | Pydantic | 2.5+ | 数据验证 |

### 5.2 前端技术栈

| 组件 | 技术 | 版本 | 说明 |
|------|------|------|------|
| 框架 | Vue 3 | 3.4+ | Composition API |
| 语言 | TypeScript | 5.3+ | 类型安全 |
| 构建 | Vite | 5.0+ | 快速构建 |
| UI库 | Element Plus | 2.5+ | 组件库 |
| 状态管理 | Pinia | 2.1+ | 状态管理 |
| 路由 | Vue Router | 4.2+ | 路由管理 |
| 图表 | ECharts | 5.4+ | 数据可视化 |
| HTTP | Axios | 1.6+ | 请求库 |
| 时间 | Day.js | 1.11+ | 时间处理 |

### 5.3 API 响应处理规范

#### 5.3.1 后端响应格式

所有 API 响应遵循统一格式：
```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| code | number | 状态码，0表示成功，非0表示错误 |
| message | string | 响应消息 |
| data | any | 业务数据 |

#### 5.3.2 前端响应拦截器

`frontend/src/api/request.ts` 中的响应拦截器配置：

```typescript
// 响应拦截器返回 response.data
service.interceptors.response.use(
  response => response.data,  // 直接返回 data 部分
  error => Promise.reject(error)
)
```

#### 5.3.3 组件中数据提取规则

**重要**：由于响应拦截器已返回 `response.data`，组件中收到的 `res` 已是 `{ code, message, data }` 结构。

| 场景 | 正确写法 | 错误写法 |
|------|----------|----------|
| 获取业务数据 | `res.data` | `res.data.data` |
| 获取列表数据 | `res.data \|\| []` | `res.data.data \|\| []` |
| 获取嵌套字段 | `res.data?.field` | `res.data.data?.field` |

**示例**：
```typescript
// ✅ 正确
const loadData = async () => {
  const res = await getDeviceList()
  deviceList.value = res.data || []
}

// ❌ 错误
const loadData = async () => {
  const res = await getDeviceList()
  deviceList.value = res.data.data || []  // data.data 是 undefined
}
```

#### 5.3.4 常见问题排查

| 问题现象 | 可能原因 | 解决方案 |
|----------|----------|----------|
| 数据显示为空 | 使用了 `res.data.data` | 改为 `res.data` |
| 控制台报 undefined | 数据提取层级错误 | 检查响应拦截器配置 |
| 列表渲染失败 | 未设置默认空数组 | 使用 `res.data \|\| []` |

---

## 六、历史数据功能设计

### 6.1 问题分析

**现状**：
- `point_history` 表只包含实时模拟器生成的当日数据
- 用户在"历史数据"页面查询时，只能看到当天的数据
- 没有历史模拟数据供展示和分析

**需求**：
- 生成过去 30 天的模拟历史数据
- 每个点位每 5 分钟一条记录
- 数据应符合真实物理规律（温度、湿度、电压等有合理的波动）

### 6.2 数据表结构

```sql
-- point_history 表
CREATE TABLE point_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    point_id INTEGER NOT NULL,        -- 关联 points.id
    value FLOAT NOT NULL,             -- 数值
    quality INTEGER DEFAULT 0,        -- 数据质量: 0=好 1=不确定 2=坏
    min_value FLOAT,                  -- 周期内最小值
    max_value FLOAT,                  -- 周期内最大值
    avg_value FLOAT,                  -- 周期内平均值
    recorded_at DATETIME              -- 记录时间
);
```

### 6.3 历史数据生成规则

| 点位类型 | 基准值 | 波动规律 | 说明 |
|----------|--------|----------|------|
| 温度 | 24°C | 日夜温差 ±3°C，随机波动 ±0.5°C | 白天高、夜间低 |
| 湿度 | 50%RH | 随温度反向变化，范围 40-70% | 温度高时湿度低 |
| 电压 (V) | 380V | 峰谷时段波动 ±5V | 高峰时段电压略低 |
| 电流 (A) | 基准值 | 负载曲线变化 ±20% | 工作时段负载高 |
| 功率 (kW) | 基准值 | 随电流变化 | P = U × I × cosφ |
| 负载率 (%) | 60% | 日间 70-85%，夜间 40-55% | 工作时段高 |
| 电池容量 (%) | 95% | 缓慢波动 ±3% | 基本稳定 |

### 6.4 实现方案

创建 `init_history.py` 脚本：
1. 读取 points 表获取所有点位信息
2. 根据点位类型生成 30 天历史数据
3. 每 5 分钟一条记录（约 8640 条/点位）
4. 批量插入以提高性能

### 6.5 API 接口规范

#### 6.5.1 获取历史数据（分页）

```
GET /api/v1/history/{point_id}
参数: start_time, end_time, granularity, page, page_size
返回: { items: HistoryData[], total, page, page_size }
```

#### 6.5.2 获取趋势数据（图表）

```
GET /api/v1/history/{point_id}/trend
参数: start_time, end_time, limit (最大数据点数)
返回: TrendData[]  // 直接返回数组
```

#### 6.5.3 获取统计数据

```
GET /api/v1/history/{point_id}/statistics
参数: start_time, end_time
返回: { point_id, count, min_value, max_value, avg_value, std_dev }
```

### 6.6 问题修复记录

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 前端趋势图无法显示 | trend API 返回 `{point, data}` 格式，前端期望数组 | 修改 API 直接返回 `TrendData[]` 数组 |
| 历史数据表格无法显示 | history API 返回 `{data}` 格式，前端期望 `{items}` | 修改 API 返回 `{items, total, page, page_size}` 格式 |
| API 参数不匹配 | 后端用 `interval`，前端用 `granularity` | 统一使用 `granularity` 参数 |

---

## 八、数字孪生大屏设计与实现 (V2.4)

### 8.1 技术架构

#### 8.1.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    大屏页面 (bigscreen/index.vue)              │
├─────────────────────────────────────────────────────────────┤
│  悬浮面板层 (overlay-panels)                                  │
│  ├── TopBar (时间/标题/模式/PUE/告警)                         │
│  ├── LeftPanel (环境监测)                                    │
│  ├── RightPanel (能耗统计)                                   │
│  ├── BottomBar (图层/视角/巡航)                              │
│  └── DeviceDetailPanel (设备详情)                            │
├─────────────────────────────────────────────────────────────┤
│  3D场景层 (ThreeScene.vue)                                   │
│  ├── DataCenterModel (机房模型)                              │
│  ├── HeatmapOverlay (温度热力图)                             │
│  ├── CabinetLabels (CSS2D标签)                               │
│  └── AlarmBubbles (告警气泡)                                 │
├─────────────────────────────────────────────────────────────┤
│  状态管理 (useBigscreenStore)                                │
│  ├── 布局数据 (layout)                                       │
│  ├── 设备实时数据 (deviceData)                               │
│  ├── 环境/能耗数据 (environment/energy)                      │
│  ├── 告警数据 (alarms)                                       │
│  └── 模式/图层配置 (mode/layers)                             │
└─────────────────────────────────────────────────────────────┘
```

#### 8.1.2 文件结构

```
frontend/src/
├── views/bigscreen/
│   └── index.vue              # 大屏主页面
├── components/bigscreen/
│   ├── ThreeScene.vue         # 3D容器组件
│   ├── DataCenterModel.vue    # 机房模型组件
│   ├── CabinetLabels.vue      # 机柜标签组件
│   ├── HeatmapOverlay.vue     # 热力图组件
│   ├── AlarmBubbles.vue       # 告警气泡组件
│   ├── DeviceDetailPanel.vue  # 设备详情面板
│   ├── panels/
│   │   ├── LeftPanel.vue      # 左侧环境面板
│   │   └── RightPanel.vue     # 右侧能耗面板
│   └── index.ts               # 统一导出
├── composables/bigscreen/
│   ├── useThreeScene.ts       # 场景管理
│   ├── useRaycaster.ts        # 点击检测
│   ├── useCameraAnimation.ts  # 相机动画
│   ├── useSceneMode.ts        # 场景模式
│   ├── useAutoTour.ts         # 自动巡航
│   ├── useBigscreenData.ts    # 数据获取
│   └── index.ts               # 统一导出
├── utils/three/
│   ├── sceneSetup.ts          # 场景设置
│   ├── modelGenerator.ts      # 模型生成器
│   ├── labelRenderer.ts       # 标签渲染器
│   ├── heatmapHelper.ts       # 热力图工具
│   ├── postProcessing.ts      # 后处理效果
│   ├── performanceMonitor.ts  # 性能监控
│   └── index.ts               # 统一导出
├── stores/
│   └── bigscreen.ts           # Pinia状态管理
└── types/
    └── bigscreen.ts           # 类型定义
```

### 8.2 Three.js 场景实现

#### 8.2.1 场景初始化

```typescript
// ThreeScene.vue 核心结构
const scene = shallowRef<THREE.Scene | null>(null)
const camera = shallowRef<THREE.PerspectiveCamera | null>(null)
const renderer = shallowRef<THREE.WebGLRenderer | null>(null)
const controls = shallowRef<OrbitControls | null>(null)
const labelRenderer = shallowRef<CSS2DRenderer | null>(null)

function initScene() {
  // 场景
  scene.value = new THREE.Scene()
  scene.value.background = new THREE.Color(0x0a0a1a)

  // 相机
  camera.value = new THREE.PerspectiveCamera(
    60, width / height, 0.1, 1000
  )
  camera.value.position.set(30, 25, 30)

  // 渲染器
  renderer.value = new THREE.WebGLRenderer({ antialias: true })
  renderer.value.setPixelRatio(Math.min(devicePixelRatio, 2))

  // CSS2D标签渲染器
  labelRenderer.value = new CSS2DRenderer()

  // 轨道控制器
  controls.value = new OrbitControls(camera, renderer.domElement)
}
```

#### 8.2.2 模型生成器 API

```typescript
// modelGenerator.ts
export function createCabinet(options: CabinetOptions): THREE.Group
export function createInfrastructure(type: 'ups'|'pdu'|'ac', options): THREE.Group
export function createFloor(size: number): THREE.Mesh
export function createStatusMaterial(status: DeviceStatus): THREE.Material
```

#### 8.2.3 场景层级

```
Scene
├── AmbientLight (intensity: 0.4)
├── DirectionalLight (intensity: 0.8, castShadow)
├── GridHelper (可选)
├── Floor (Mesh)
├── DataCenter (Group)
│   ├── Module-A (Group)
│   │   ├── Cabinet-A-01 (Group)
│   │   │   ├── Frame (Mesh)
│   │   │   ├── Doors (Mesh)
│   │   │   └── Label (CSS2DObject)
│   │   └── ...
│   ├── Module-B (Group)
│   └── Infrastructure (Group)
│       ├── UPS-1 (Group)
│       ├── PDU-Main (Group)
│       └── AC-1 (Group)
└── PostProcessing (EffectComposer)
```

### 8.3 数据可视化层

#### 8.3.1 热力图实现

```typescript
// heatmapHelper.ts
export function createHeatmapTexture(
  data: HeatmapData[],
  width: number,
  height: number
): THREE.CanvasTexture

export function temperatureToColor(temp: number): THREE.Color
// 温度色带: 蓝(20°C) → 青 → 绿 → 黄 → 红(35°C)
```

#### 8.3.2 状态着色规则

| 状态 | 颜色 | 说明 |
|------|------|------|
| normal | #00ff88 (绿) | 正常运行 |
| warning | #ffaa00 (橙) | 警告状态 |
| alarm | #ff3300 (红) | 告警状态 |
| offline | #666666 (灰) | 离线/未知 |

#### 8.3.3 CSS2D标签

```vue
<!-- CabinetLabels.vue -->
<template>
  <div class="cabinet-label">
    <div class="device-id">{{ label.id }}</div>
    <div class="device-info">
      <span class="temp">{{ formatTemp(data.temperature) }}</span>
      <span class="power">{{ formatPower(data.power) }}</span>
    </div>
    <div class="status-dot" :class="data.status"></div>
  </div>
</template>
```

### 8.4 交互功能

#### 8.4.1 Raycaster 点击检测

```typescript
// useRaycaster.ts
export function useRaycaster(
  container: Ref<HTMLElement | null>,
  camera: ShallowRef<THREE.Camera | null>,
  scene: ShallowRef<THREE.Scene | null>
) {
  function onMouseClick(event: MouseEvent) {
    // 计算归一化坐标
    mouse.x = (event.clientX / width) * 2 - 1
    mouse.y = -(event.clientY / height) * 2 + 1

    raycaster.setFromCamera(mouse, camera)
    const intersects = raycaster.intersectObjects(scene.children, true)

    if (intersects.length > 0) {
      const deviceId = findDeviceId(intersects[0].object)
      if (deviceId) store.selectDevice(deviceId)
    }
  }
}
```

#### 8.4.2 相机动画

```typescript
// useCameraAnimation.ts
export function useCameraAnimation(
  camera: ShallowRef<THREE.PerspectiveCamera | null>,
  controls: ShallowRef<OrbitControls | null>
) {
  function flyToPreset(preset: CameraPreset) {
    gsap.to(camera.value.position, {
      ...preset.position,
      duration: preset.duration || 1.5,
      ease: 'power2.inOut'
    })
    gsap.to(controls.value.target, {
      ...preset.target,
      duration: preset.duration || 1.5,
      ease: 'power2.inOut'
    })
  }

  function flyToDevice(deviceId: string, scene: THREE.Scene, options) {
    const device = scene.getObjectByName(deviceId)
    if (!device) return
    // 计算设备位置并飞行
  }
}
```

### 8.5 场景模式

#### 8.5.1 模式配置

```typescript
// useSceneMode.ts
const modeConfigs: Record<SceneMode, ModeConfig> = {
  command: {
    cameraLock: true,
    autoRotate: false,
    showAllPanels: true,
    refreshInterval: 10000,
    interactionLevel: 'read-only'
  },
  operation: {
    cameraLock: false,
    autoRotate: false,
    showAllPanels: true,
    refreshInterval: 5000,
    interactionLevel: 'full'
  },
  showcase: {
    cameraLock: false,
    autoRotate: true,
    showAllPanels: false,
    refreshInterval: 15000,
    interactionLevel: 'limited'
  }
}
```

#### 8.5.2 自动巡航

```typescript
// useAutoTour.ts
const tourPoints: TourWaypoint[] = [
  { position: [30, 25, 30], target: [0, 0, 0], duration: 3, pause: 2, label: '全景视角' },
  { position: [15, 10, 15], target: [0, 2, 0], duration: 2, pause: 3, label: 'A区机柜' },
  { position: [-15, 10, 15], target: [0, 2, 0], duration: 2, pause: 3, label: 'B区机柜' },
  { position: [0, 30, 0], target: [0, 0, 0], duration: 2, pause: 2, label: '俯视全景' },
  { position: [20, 8, 0], target: [10, 2, 0], duration: 2, pause: 3, label: '基础设施' }
]
```

### 8.6 后处理效果

```typescript
// postProcessing.ts
export function setupPostProcessing(
  renderer: THREE.WebGLRenderer,
  scene: THREE.Scene,
  camera: THREE.Camera,
  options: PostProcessingOptions = {}
): PostProcessingSetup {
  const composer = new EffectComposer(renderer)

  // 渲染通道
  const renderPass = new RenderPass(scene, camera)
  composer.addPass(renderPass)

  // Bloom辉光效果
  const bloomPass = new UnrealBloomPass(
    new THREE.Vector2(width, height),
    options.bloomStrength || 0.5,
    options.bloomRadius || 0.4,
    options.bloomThreshold || 0.85
  )
  composer.addPass(bloomPass)

  return { composer, bloomPass, renderPass }
}
```

### 8.7 性能优化

#### 8.7.1 性能监控

```typescript
// performanceMonitor.ts
export function usePerformanceMonitor() {
  const stats = ref<PerformanceStats>({ fps: 0, frameTime: 0 })

  function update() {
    frameCount++
    const elapsed = performance.now() - lastTime
    if (elapsed >= 1000) {
      stats.value.fps = Math.round(frameCount * 1000 / elapsed)
      stats.value.frameTime = Math.round(elapsed / frameCount * 100) / 100
      // Chrome 内存监控
      if (performance.memory) {
        stats.value.memory = { ... }
      }
    }
  }
}
```

#### 8.7.2 优化策略

| 策略 | 实现方式 | 效果 |
|------|----------|------|
| 条件渲染 | v-if="isSceneReady" | 场景就绪后再渲染子组件 |
| ShallowRef | Three.js 对象用 shallowRef | 避免深度响应式 |
| 像素比限制 | Math.min(devicePixelRatio, 2) | 防止高DPI性能问题 |
| 按需更新 | 基于模式的刷新间隔 | 减少不必要的数据请求 |
| 对象池 | 复用 Mesh/Material | 减少 GC 压力 |

### 8.8 数据流设计

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  后端 API   │────▶│ useBigscreen │────▶│   Pinia     │
│  /realtime  │     │    Data      │     │   Store     │
└─────────────┘     └──────────────┘     └─────────────┘
                           │                    │
                           │ setInterval        │ watch
                           │ 5s/10s/15s         │
                           ▼                    ▼
                    ┌──────────────┐     ┌─────────────┐
                    │ environment  │     │  3D Scene   │
                    │ energy       │     │  Components │
                    │ alarms       │     │  Panels     │
                    └──────────────┘     └─────────────┘
```

### 8.9 依赖包

```json
{
  "three": "^0.160.0",
  "@types/three": "^0.160.0",
  "gsap": "^3.12.0",
  "postprocessing": "^6.35.0"
}
```

---

## 九、大屏视觉升级设计 (V2.5)

### 9.1 升级概述

基于V2.4数字孪生大屏的基础架构，全面升级视觉效果、数据可视化和交互体验。

**升级目标**：
1. 添加入场动画提升视觉冲击力
2. 集成专业数据可视化图表
3. 增强3D特效展示能力
4. 提升交互体验
5. 支持多主题切换

### 9.2 技术栈新增

| 库 | 版本 | 用途 |
|---|------|------|
| @kjgl77/datav-vue3 | ^1.x | DataV科技感UI组件 |
| echarts | ^5.x | 专业图表库 |
| gsap | ^3.x | 高性能动画库 |
| countup.js | ^2.x | 数字滚动效果 |

### 9.3 新增组件架构

```
frontend/src/
├── composables/bigscreen/
│   ├── useScreenAdapt.ts      # 屏幕自适应
│   ├── useEntranceAnimation.ts # GSAP入场动画
│   ├── useKeyboardShortcuts.ts # 键盘快捷键
│   └── useTheme.ts            # 主题管理
├── components/bigscreen/
│   ├── ui/
│   │   ├── DigitalFlop.vue    # 数字滚动
│   │   ├── ContextMenu.vue    # 右键菜单
│   │   └── ThemeSelector.vue  # 主题选择器
│   └── charts/
│       ├── BaseChart.vue      # ECharts封装
│       ├── TemperatureTrend.vue
│       ├── PowerDistribution.vue
│       ├── PueTrend.vue
│       └── GaugeChart.vue
├── utils/three/
│   ├── powerFlowEffect.ts     # 电力流向动画
│   └── alarmPulseEffect.ts    # 告警脉冲效果
├── types/
│   └── theme.ts               # 主题类型定义
└── config/themes/
    ├── tech-blue.ts           # 科技蓝主题
    ├── wireframe.ts           # 线框主题
    ├── realistic.ts           # 写实主题
    └── night.ts               # 暗夜主题
```

### 9.4 入场动画设计

使用GSAP Timeline实现元素依次入场的动画效果：

```typescript
interface EntranceAnimationOptions {
  duration?: number      // 动画时长
  staggerDelay?: number  // 错开延迟
  onComplete?: () => void
}

// 动画时序
// 0.0s: 背景淡入
// 0.2s: 3D场景缩放入场
// 0.5s: 顶部栏从上滑入
// 0.8s: 左右面板从两侧滑入
// 1.0s: 底部栏从下滑入
```

### 9.5 数据可视化图表

#### 9.5.1 BaseChart - ECharts封装
```vue
<BaseChart
  :option="chartOption"
  :width="100%"
  :height="200px"
  theme="dark"
  @chartReady="onChartReady"
  @click="onChartClick"
/>
```

#### 9.5.2 温度趋势图
- 渐变区域填充
- 阈值警戒线 (warning: 28°C, danger: 32°C)
- 平滑曲线

#### 9.5.3 功率分布图
- 玫瑰图/饼图样式
- 图例百分比显示
- 悬停高亮效果

#### 9.5.4 PUE趋势图
- 面积图填充
- 等级颜色 (excellent: <1.4, good: 1.4-1.6, normal: 1.6-2.0, warning: >2.0)
- 目标线标记

### 9.6 3D特效设计

#### 9.6.1 OutlinePass选中高亮
```typescript
interface OutlineConfig {
  edgeStrength: 3.0,     // 边缘强度
  edgeGlow: 1.0,         // 发光强度
  edgeThickness: 2.0,    // 边缘厚度
  pulsePeriod: 2,        // 脉冲周期
  visibleEdgeColor: '#00ccff',
  hiddenEdgeColor: '#004466'
}
```

#### 9.6.2 电力流向动画
- 使用TubeGeometry创建管道
- 流动纹理通过UV偏移实现
- 粒子系统沿曲线运动

#### 9.6.3 告警脉冲效果
- 中心发光球体
- 扩散波纹环
- 颜色: 红色 (0xff3300)

### 9.7 主题系统设计

#### 9.7.1 主题接口
```typescript
interface BigscreenTheme {
  name: string
  displayName: string
  scene: {
    backgroundColor: number
    fogColor: number
    fogDensity: number
    gridColor: number
    gridOpacity: number
    ambientLightColor: number
    ambientLightIntensity: number
  }
  materials: {
    cabinetBody: MaterialConfig
    cabinetFrame: MaterialConfig
    floor: MaterialConfig
  }
  ui: {
    primaryColor: string
    secondaryColor: string
    successColor: string
    warningColor: string
    dangerColor: string
    backgroundColor: string
    borderColor: string
    textColor: string
    textColorSecondary: string
    panelOpacity: number
    borderStyle: string
  }
  effects: {
    bloom: boolean
    bloomStrength: number
    outline: boolean
    outlineColor: number
    particles: boolean
    flowLines: boolean
  }
}
```

#### 9.7.2 预设主题

| 主题 | 背景色 | 主色调 | 特效 |
|------|--------|--------|------|
| tech-blue | #0a0a1a | #00ccff | bloom+outline+particles |
| wireframe | #000000 | #00ccff | bloom强+outline |
| realistic | #1a1a1a | #4a90d9 | outline |
| night | #000000 | #336688 | outline |

### 9.8 交互增强设计

#### 9.8.1 键盘快捷键
| 按键 | 功能 |
|------|------|
| 1-4 | 切换相机预设视角 |
| F | 切换全屏 |
| H | 切换热力图 |
| P | 切换功率图层 |
| S | 切换状态图层 |
| A | 切换气流图层 |
| Space | 切换巡航 |
| Esc | 关闭面板/取消选择 |

#### 9.8.2 右键上下文菜单
```typescript
interface ContextMenuItem {
  key: string
  label: string
  icon?: string
  divider?: boolean
  disabled?: boolean
}
```

### 9.9 DataV组件使用

| 组件 | 用途 |
|------|------|
| dv-border-box-8 | 面板科技感边框 |
| dv-decoration-3 | 面板标题装饰 |
| dv-scroll-board | 告警滚动列表 |
| dv-water-level-pond | 用电量水位图 |
| dv-percent-pond | 需量利用率 |

---

## 十、资产管理模块实现 (2026-01-20)

### 10.1 模块概述

基于行业调研发现（Phase 11），资产管理是当前系统与行业DCIM标准差距最大的模块之一。本次实现了完整的资产管理功能。

### 10.2 数据库设计

#### 10.2.1 核心表结构

| 表名 | 用途 | 主要字段 |
|------|------|----------|
| cabinets | 机柜管理 | name, location, u_count, rated_power |
| assets | 资产台账 | name, asset_code, asset_type, status, cabinet_id, u_start, u_end |
| asset_lifecycles | 生命周期 | asset_id, action, actor, details |
| maintenance_records | 维保记录 | asset_id, type, description, cost, next_date |
| asset_inventories | 盘点单 | name, operator, status, notes |
| asset_inventory_items | 盘点明细 | inventory_id, asset_id, expected_location, actual_location, status |

#### 10.2.2 枚举类型

```python
class AssetStatus(str, enum.Enum):
    in_stock = "在库"
    in_use = "使用中"
    borrowed = "借出"
    maintenance = "维修中"
    scrapped = "已报废"

class AssetType(str, enum.Enum):
    server = "服务器"
    network = "网络设备"
    storage = "存储设备"
    ups = "UPS"
    pdu = "PDU"
    ac = "空调"
    cabinet = "机柜"
    sensor = "传感器"
    other = "其他"
```

### 10.3 API设计

#### 10.3.1 机柜管理 (5个端点)
| 方法 | 路径 | 功能 |
|------|------|------|
| GET | /asset/cabinets | 获取机柜列表 |
| POST | /asset/cabinets | 创建机柜 |
| GET | /asset/cabinets/{id} | 获取机柜详情 |
| PUT | /asset/cabinets/{id} | 更新机柜 |
| DELETE | /asset/cabinets/{id} | 删除机柜 |
| GET | /asset/cabinets/{id}/usage | 获取U位使用情况 |

#### 10.3.2 资产管理 (7个端点)
| 方法 | 路径 | 功能 |
|------|------|------|
| GET | /asset/ | 获取资产列表 |
| POST | /asset/ | 创建资产 |
| GET | /asset/{id} | 获取资产详情 |
| PUT | /asset/{id} | 更新资产 |
| DELETE | /asset/{id} | 删除资产 |
| GET | /asset/{id}/lifecycle | 获取生命周期 |
| GET | /asset/warranty-expiring | 获取即将过保资产 |

#### 10.3.3 维保管理 (4个端点)
| 方法 | 路径 | 功能 |
|------|------|------|
| GET | /asset/maintenance | 获取维保列表 |
| POST | /asset/maintenance | 创建维保记录 |
| GET | /asset/maintenance/{id} | 获取维保详情 |
| DELETE | /asset/maintenance/{id} | 删除维保记录 |

#### 10.3.4 盘点管理 (4个端点)
| 方法 | 路径 | 功能 |
|------|------|------|
| GET | /asset/inventories | 获取盘点列表 |
| POST | /asset/inventories | 创建盘点单 |
| GET | /asset/inventories/{id} | 获取盘点详情 |
| PUT | /asset/inventories/{id}/complete | 完成盘点 |

#### 10.3.5 统计 (1个端点)
| 方法 | 路径 | 功能 |
|------|------|------|
| GET | /asset/statistics | 获取资产统计 |

### 10.4 前端实现

#### 10.4.1 页面结构

```
frontend/src/views/asset/
├── index.vue       # 资产台账页面
└── cabinet.vue     # 机柜管理页面
```

#### 10.4.2 资产台账页面功能
- 统计卡片：资产总数、使用中、维修中、即将过保
- 筛选条件：资产类型、状态、关键字搜索
- 资产列表表格：支持分页、排序
- 新增/编辑对话框：完整表单
- 删除确认

#### 10.4.3 机柜管理页面功能
- 机柜列表：显示名称、位置、U位数、已用/总数、状态
- U位可视化：
  - 垂直U位图
  - 已使用(蓝色)、空闲(透明)状态显示
  - 点击U位显示设备详情
- 新增/编辑机柜对话框

### 10.5 侧边栏菜单

```vue
<el-sub-menu index="/asset">
  <template #title>
    <el-icon><Box /></el-icon>
    <span>资产管理</span>
  </template>
  <el-menu-item index="/asset/list">
    <el-icon><Document /></el-icon>
    <template #title>资产台账</template>
  </el-menu-item>
  <el-menu-item index="/asset/cabinet">
    <el-icon><Grid /></el-icon>
    <template #title>机柜管理</template>
  </el-menu-item>
</el-sub-menu>
```

### 10.6 实现文件清单

| 类型 | 文件路径 |
|------|----------|
| 后端模型 | backend/app/models/asset.py |
| 后端Schema | backend/app/schemas/asset.py |
| 后端服务 | backend/app/services/asset.py |
| 后端API | backend/app/api/v1/asset.py |
| 前端API | frontend/src/api/modules/asset.ts |
| 资产页面 | frontend/src/views/asset/index.vue |
| 机柜页面 | frontend/src/views/asset/cabinet.vue |
| 路由配置 | frontend/src/router/index.ts (修改) |
| 侧边栏 | frontend/src/layouts/MainLayout.vue (修改) |

---

## 十一、演示数据系统与楼层可视化 (2026-01-20)

### 11.1 模块概述

实现按需加载的演示数据系统，用户可通过仪表盘按钮一键加载/卸载演示数据。同时创建了2D楼层布局组件和3D楼宇模型组件，支持数字孪生大屏的多楼层可视化。

### 11.2 后端架构

#### 11.2.1 DemoDataService 核心设计

```python
class DemoDataService:
    def __init__(self):
        self.is_loaded = False      # 数据是否已加载
        self.loading = False        # 是否正在加载中
        self.progress = 0           # 加载进度 (0-100)
        self.progress_message = ""  # 进度消息
        self._lock = asyncio.Lock() # 并发锁
```

**关键设计决策：**
- 使用 `asyncio.Lock` 防止并发加载/卸载操作
- 使用 FastAPI `BackgroundTasks` 异步执行耗时的数据加载
- 进度分阶段更新：检查(0-10%) → 创建点位(10-40%) → 生成历史(40-90%) → PUE数据(90-100%)

#### 11.2.2 日期刷新算法

```python
async def refresh_dates(self):
    # 获取历史数据的时间范围
    min_date, max_date = await get_date_range()

    # 计算偏移量：将max_date调整到当前时间
    offset = datetime.now() - max_date

    # 批量更新所有历史记录
    await session.execute(
        update(PointHistory).values(
            recorded_at=PointHistory.recorded_at + offset
        )
    )
```

### 11.3 API设计

| 方法 | 路径 | 功能 | 返回 |
|------|------|------|------|
| GET | /demo/status | 获取演示数据状态 | is_loaded, point_count, history_count |
| POST | /demo/load | 加载演示数据 | 启动后台任务 |
| GET | /demo/progress | 获取加载进度 | loading, progress, progress_message |
| POST | /demo/unload | 卸载演示数据 | success, message |
| POST | /demo/refresh-dates | 刷新日期到最近30天 | offset_days |

### 11.4 前端组件

#### 11.4.1 DemoDataLoader.vue

对话框组件，提供演示数据管理界面：

```vue
<template>
  <el-dialog title="演示数据管理">
    <!-- 状态显示 -->
    <el-descriptions>
      <el-descriptions-item label="数据状态">已加载/未加载</el-descriptions-item>
      <el-descriptions-item label="点位数量">330</el-descriptions-item>
      <el-descriptions-item label="历史记录">238,320条</el-descriptions-item>
    </el-descriptions>

    <!-- 进度条 -->
    <el-progress v-if="loading" :percentage="progress" />

    <!-- 操作按钮 -->
    <el-button @click="load">加载数据</el-button>
    <el-button @click="unload">卸载数据</el-button>
    <el-button @click="refreshDates">刷新日期</el-button>
  </el-dialog>
</template>
```

#### 11.4.2 楼层布局组件

创建了6个SVG组件用于2D平面布局展示：

| 组件 | 用途 | 内容 |
|------|------|------|
| FloorLayoutBase.vue | 基础组件 | 网格背景、图例、hover效果 |
| FloorB1Layout.vue | B1制冷机房 | 冷水机组×2、冷却塔×2、水泵×4 |
| FloorF1Layout.vue | F1机房区A | 20机柜(4×5)、精密空调×2、UPS×1 |
| FloorF2Layout.vue | F2机房区B | 15机柜(3×5)、精密空调×2、UPS×1 |
| FloorF3Layout.vue | F3办公监控 | 8机柜、NOC监控区、会议室 |
| FloorLayoutSelector.vue | 楼层切换 | Tab切换+动态组件加载 |

### 11.5 3D楼宇模型

#### 11.5.1 useBuildingModel.ts Composable

```typescript
export function useBuildingModel(options: UseBuildingModelOptions) {
  // 创建4层建筑
  const floors = ['B1', 'F1', 'F2', 'F3']

  // 每层包含设备
  type FloorConfig = {
    height: number
    cabinets: CabinetConfig[]
    equipment: EquipmentConfig[]
  }

  return {
    building: Object3D,              // 建筑模型
    setFloorVisibility,             // 设置楼层可见性
    showAllFloors,                  // 显示所有楼层
    showSingleFloor,                // 仅显示单层
    highlightFloor,                 // 高亮指定楼层
    updateEquipmentStatus,          // 更新设备状态颜色
    getFloorByName,                 // 获取楼层对象
  }
}
```

#### 11.5.2 设备状态颜色映射

```typescript
const STATUS_COLORS = {
  normal: 0x00ff00,    // 绿色 - 正常
  warning: 0xffff00,   // 黄色 - 警告
  alarm: 0xff0000,     // 红色 - 告警
  offline: 0x808080,   // 灰色 - 离线
}
```

### 11.6 实现文件清单

| 类型 | 文件路径 |
|------|----------|
| 后端服务 | backend/app/services/demo_data_service.py |
| 后端API | backend/app/api/v1/demo.py |
| 前端API | frontend/src/api/modules/demo.ts |
| 对话框组件 | frontend/src/components/DemoDataLoader.vue |
| 基础布局 | frontend/src/components/floor-layouts/FloorLayoutBase.vue |
| B1布局 | frontend/src/components/floor-layouts/FloorB1Layout.vue |
| F1布局 | frontend/src/components/floor-layouts/FloorF1Layout.vue |
| F2布局 | frontend/src/components/floor-layouts/FloorF2Layout.vue |
| F3布局 | frontend/src/components/floor-layouts/FloorF3Layout.vue |
| 楼层切换 | frontend/src/components/floor-layouts/FloorLayoutSelector.vue |
| 组件导出 | frontend/src/components/floor-layouts/index.ts |
| 3D建模 | frontend/src/composables/bigscreen/useBuildingModel.ts |

### 11.7 技术要点

1. **并发安全**：使用 asyncio.Lock 确保同一时间只有一个加载/卸载操作
2. **后台任务**：长时间操作使用 BackgroundTasks 避免请求超时
3. **进度轮询**：前端2秒间隔轮询进度，加载完成后自动停止
4. **SVG可视化**：使用内联SVG实现响应式2D布局
5. **Three.js建模**：程序化生成3D模型，支持动态状态更新

### 11.8 Bug修复记录 (2026-01-20)

#### 问题1：API路径缺少/v1前缀

**症状**：点击"加载演示数据"显示404错误

**根本原因**：`demo.ts` API路径缺少 `/v1` 前缀

**修复**：所有API路径从 `/demo/*` 改为 `/v1/demo/*`

#### 问题2：Vite代理配置错误

**症状**：修复API路径后仍然404

**根本原因**：
1. `vite.config.ts` 代理目标是 8080 端口，后端实际运行在 18080 端口
2. `request.ts` 使用绝对URL绕过了Vite代理

**修复**：
| 文件 | 修改 |
|------|------|
| `request.ts` | 开发环境返回 `/api`（相对路径），让Vite代理生效 |
| `vite.config.ts` | 代理目标从 `localhost:8080` 改为 `localhost:18080` |

#### 问题3：后端需要重启

**症状**：配置正确但路由仍不存在

**根本原因**：后端在添加demo模块之前启动，未加载新路由

**修复**：重启后端服务

**API路径对照**：
```
修复前: /demo/status      → 修复后: /v1/demo/status
修复前: /demo/load        → 修复后: /v1/demo/load
修复前: /demo/progress    → 修复后: /v1/demo/progress
修复前: /demo/unload      → 修复后: /v1/demo/unload
修复前: /demo/refresh-dates → 修复后: /v1/demo/refresh-dates
```

**配置对照**：
```
request.ts (开发环境): 返回 '/api' 而非绝对URL
vite.config.ts: proxy target 'http://localhost:18080'
```

**教训**：
1. 新增API模块时需确认路由前缀与后端一致
2. 开发环境应使用相对路径让Vite代理生效
3. 添加新路由后需重启后端服务

---

## 七、更新日志

| 日期 | 版本 | 更新内容 |
|------|------|----------|
| 2026-01-20 | V3.4.1 | 修复演示数据加载功能：API路径添加/v1前缀、增强对话框错误处理和关闭功能 |
| 2026-01-20 | V3.4 | 演示数据系统：按需加载/卸载、进度显示、日期刷新；楼层可视化：4层SVG布局、3D楼宇模型 |
| 2026-01-20 | V3.1 | 资产管理模块：机柜管理、资产台账、维保记录、资产盘点、U位可视化 |
| 2026-01-20 | V2.5 | 大屏视觉升级：GSAP入场动画、ECharts数据图表、DataV科技组件、OutlinePass高亮、电力流向动画、告警脉冲效果、键盘快捷键、右键菜单、4种主题切换、屏幕自适应 |
| 2026-01-20 | V2.4 | 完成数字孪生大屏实现：Three.js 3D场景、机房模型生成、数据可视化层、交互功能、悬浮面板、场景模式、后处理效果、性能监控 |
| 2026-01-19 | V2.4-design | 数字孪生大屏设计：整体架构、文件结构、技术选型、实现计划 |
| 2026-01-14 | V2.3.3 | 修复历史数据页面问题：调整 API 返回格式匹配前端需求，trend API 返回数组格式，history API 返回分页格式 |
| 2026-01-14 | V2.3.2 | 添加历史数据生成功能：创建 init_history.py 脚本生成 30 天模拟历史数据 |
| 2026-01-14 | V2.3.1 | 修复能源数据初始化问题：创建 init_energy.py 脚本初始化变压器、计量点、配电柜、用电设备、需量数据等 |
| 2026-01-14 | V2.3 | 监控仪表盘增强、负荷功率调节、需量分析完善、节能建议细化 |
| 2026-01-14 | V2.2 | 配电系统配置功能、电费结构设计、节能建议平台、拓扑管理 |
| 2026-01-13 | V2.0 | 完善后端架构设计、前端动态化设计、历史查询设计 |
| 2026-01-13 | V1.0 | 初始设计文档 |

---

*本文档为算力中心智能监控系统的详细设计文档，作为开发实施的指导依据。*

---

## 八、2026-01-20 数据与功能统一整合

### 1. 问题概述

| 问题 | 描述 | 状态 |
|------|------|------|
| 点位数量不一致 | 仪表盘显示379点位，演示数据定义330点位 | ✅ 已修复 |
| 大屏返回导航异常 | 从大屏返回主界面时显示错误页面 | ✅ 已修复 |
| 配电拓扑无数据 | 演示数据未包含配电系统数据 | ✅ 已修复 |
| 大屏缺乏交互 | 大屏组件无法导航到主界面 | ✅ 已修复 |

### 2. 问题分析与修复

#### 2.1 点位数量不一致

**问题根因**：前端仪表盘使用了错误的字段名映射

**代码位置**：`frontend/src/views/dashboard/index.vue` (L251-256)

**修复前**：
```javascript
summary.value = {
  total: summaryRes.total_points || 0,
  normal: summaryRes.online_points - summaryRes.alarm_points || 0,  // 错误字段名
  alarm: summaryRes.alarm_points || 0,                              // 错误字段名
  offline: summaryRes.offline_points || 0                           // 错误字段名
}
```

**修复后**：
```javascript
summary.value = {
  total: summaryRes.total_points || 0,
  normal: summaryRes.normal_count || 0,    // 正确字段名
  alarm: summaryRes.alarm_count || 0,      // 正确字段名
  offline: summaryRes.offline_count || 0   // 正确字段名
}
```

**后端返回字段**：
- `total_points` - 总点位数
- `normal_count` - 正常点位数
- `alarm_count` - 告警点位数
- `offline_count` - 离线点位数

#### 2.2 大屏返回导航异常

**问题根因**：使用 `window.location.href` 硬刷新导航，导致Vue应用状态丢失

**代码位置**：`frontend/src/views/bigscreen/index.vue` (L337-343)

**修复前**：
```javascript
function goBack() {
  if (window.opener) {
    window.close()
  } else {
    window.location.href = '/dashboard'  // 硬刷新，状态丢失
  }
}
```

**修复后**：
```javascript
function goBack() {
  if (window.opener) {
    window.close()
  } else {
    router.push('/dashboard')  // Vue Router导航，保持状态
  }
}
```

#### 2.3 配电拓扑无数据

**问题根因**：`demo_data_service.py` 未包含配电系统数据初始化

**修复方案**：将 `init_energy.py` 的逻辑集成到 `demo_data_service.py`

**新增数据**：
- 2个变压器 (Transformer)
- 3个计量点 (MeterPoint)
- 7个配电柜 (DistributionPanel)
- 6个配电回路 (DistributionCircuit)
- 12个用电设备 (PowerDevice)
- 6条电价配置 (ElectricityPricing)
- 7天15分钟需量数据 (Demand15MinData)

**加载流程更新**：
```
Phase 1: 清理旧数据 (0-10%)
Phase 2: 创建监控点位 (10-35%)
Phase 3: 创建配电系统 (35-45%)  ← 新增
Phase 4: 生成历史数据 (45-85%)
Phase 5: 生成需量数据 (85-90%)  ← 新增
Phase 6: 生成PUE历史 (90-100%)
```

#### 2.4 大屏交互功能

**修复方案**：为大屏面板添加点击导航功能

**左侧面板导航**：
| 区域 | 导航目标 |
|------|----------|
| 温湿度仪表盘 | /monitor |
| 温度趋势图 | /monitor |
| 温湿度概览 | /monitor |
| 实时告警 | /alarm |

**右侧面板导航**：
| 区域 | 导航目标 |
|------|----------|
| 实时功率 | /energy/analysis |
| PUE趋势 | /energy/analysis |
| 今日用电 | /energy/statistics |
| 需量状态 | /energy/topology |

**交互设计**：
- 悬停时显示导航提示
- 点击时根据大屏打开方式决定导航行为
  - 新窗口打开：在新标签页打开目标页
  - 同窗口打开：使用Vue Router导航

### 3. 修改文件清单

| 文件 | 修改内容 |
|------|----------|
| `frontend/src/views/dashboard/index.vue` | 修复字段映射 |
| `frontend/src/views/bigscreen/index.vue` | 使用Vue Router导航，添加navigate事件处理 |
| `frontend/src/components/bigscreen/panels/LeftPanel.vue` | 添加点击导航功能 |
| `frontend/src/components/bigscreen/panels/RightPanel.vue` | 添加点击导航功能 |
| `backend/app/services/demo_data_service.py` | 集成配电系统数据初始化 |

### 4. 验证清单

- [x] 仪表盘点位数量正确显示
- [x] 大屏返回主界面正常
- [x] 配电拓扑显示数据
- [x] 大屏组件可点击导航
- [x] 前端构建通过

### 5. 补充修复 - 2026-01-20 22:50

#### 5.1 残留点位数据清理

**问题**：数据库存在49个非演示点位（A1_, A2_ 前缀），导致点位总数(379)与演示点位数(330)不一致

**根因分析**：旧版数据未被清理，与新演示数据混合

**清理数据**：
```
删除历史数据: 1,668,662 条
删除告警阈值: 11 条
删除实时数据: 49 条
删除点位: 49 个
```

**清理后**：点位总数 = 演示点位数 = 330

#### 5.2 配电柜与计量点关联缺失

**问题**：配电柜(DistributionPanel)的`meter_point_id`字段为NULL，导致拓扑API返回panels为空

**根因**：`demo_data_service.py`创建配电柜时未设置meter_point_id

**修复方案**：
1. 更新DISTRIBUTION_PANELS配置，添加meter_point_code字段
2. 更新创建代码，使用meter_point_map设置meter_point_id
3. 直接更新数据库中现有记录

**关联关系**：
| 配电柜 | 计量点 |
|--------|--------|
| MDP-001, ATS-001, UPS-IN-001 | M001 |
| UPS-OUT-001, PDU-A1-001, PDU-A1-002 | M002 |
| AC-PANEL-001 | M003 |

**修复后拓扑结构**：
```
TR-001 (1#变压器)
├── M001 (IT系统计量点): 3 panels
│   ├── MDP-001 (主配电柜)
│   ├── ATS-001 (ATS切换柜)
│   └── UPS-IN-001 (UPS输入柜)
└── M002 (低压配电室计量点): 3 panels
    ├── UPS-OUT-001 (UPS输出柜)
    ├── PDU-A1-001 (A1区列头柜1)
    └── PDU-A1-002 (A1区列头柜2)

TR-002 (2#变压器)
└── M003 (制冷系统计量点): 1 panel
    └── AC-PANEL-001 (空调配电柜)
```

---

## 2026-01-20 数字孪生大屏楼层可视化 V4.0

### 1. 功能概述

新增楼层可视化系统，支持2D平面图和3D场景切换，实现机房多楼层数字孪生展示。

**楼层结构**：
| 楼层 | 名称 | 主要设备 |
|------|------|----------|
| B1 | 地下制冷机房 | 冷水机组、冷却塔、水泵 |
| F1 | 1楼机房区A | 20个机柜、UPS、空调 |
| F2 | 2楼机房区B | 15个机柜、UPS、空调 |
| F3 | 3楼办公监控 | 8个机柜、UPS、空调 |

### 2. 实现内容

#### 2.1 界面优化

**移除侧边栏大屏入口**：
- 删除 MainLayout.vue 中的"数字孪生大屏"菜单项
- 保留仪表盘"打开数字孪生大屏"按钮

**修复大屏导航**：
- 修改 handleNavigate 函数使用 `window.opener.location.href` 在父窗口导航
- 点击大屏面板时在主界面打开对应页面

#### 2.2 后端实现

**楼层图数据模型** (`backend/app/models/floor_map.py`)：
```python
class FloorMap(Base):
    __tablename__ = "floor_maps"
    id = Column(Integer, primary_key=True)
    floor_code = Column(String(10))  # B1/F1/F2/F3
    floor_name = Column(String(50))
    map_type = Column(String(10))    # 2d/3d
    map_data = Column(Text)          # JSON格式图数据
    thumbnail = Column(Text)
    is_default = Column(Boolean)
```

**楼层图生成服务** (`backend/app/services/floor_map_generator.py`)：
- `generate_2d_map()`: 生成2D平面图数据
- `generate_3d_map()`: 生成3D场景数据
- B1楼层生成制冷机房布局
- F1-F3楼层生成数据中心机房布局

**楼层图API** (`backend/app/api/v1/floor_map.py`)：
| 接口 | 说明 |
|------|------|
| GET /v1/floor-map/floors | 获取楼层列表 |
| GET /v1/floor-map/{floor_code}/{map_type} | 获取楼层图数据 |
| GET /v1/floor-map/default | 获取默认楼层图 |

#### 2.3 前端实现

**楼层图API模块** (`frontend/src/api/modules/floorMap.ts`)：
- FloorInfo, MapData2D, MapData3D 类型定义
- getFloors(), getFloorMap() API函数

**楼层选择器** (`frontend/src/components/bigscreen/FloorSelector.vue`)：
- B1/F1/F2/F3 楼层按钮
- 2D/3D 视图切换
- 加载指示器

**2D平面图渲染** (`frontend/src/components/bigscreen/Floor2DView.vue`)：
- Canvas 2D 渲染
- 设备元素绘制（机柜、区域、设备）
- 悬停工具提示
- 设备点击事件

**大屏集成** (`frontend/src/views/bigscreen/index.vue`)：
- 添加 FloorSelector 和 Floor2DView 组件
- 条件渲染2D/3D视图
- 楼层切换和元素点击处理

### 3. 文件修改清单

| 文件 | 操作 | 说明 |
|------|------|------|
| frontend/src/layouts/MainLayout.vue | 修改 | 移除大屏菜单项 |
| frontend/src/views/bigscreen/index.vue | 修改 | 修复导航、集成楼层组件 |
| backend/app/models/floor_map.py | 新增 | 楼层图数据模型 |
| backend/app/models/__init__.py | 修改 | 导出FloorMap |
| backend/app/services/floor_map_generator.py | 新增 | 楼层图生成器 |
| backend/app/api/v1/floor_map.py | 新增 | 楼层图API |
| backend/app/api/v1/__init__.py | 修改 | 注册floor_map路由 |
| backend/app/services/demo_data_service.py | 修改 | 集成楼层图生成 |
| frontend/src/api/modules/floorMap.ts | 新增 | 前端API模块 |
| frontend/src/components/bigscreen/FloorSelector.vue | 新增 | 楼层选择器 |
| frontend/src/components/bigscreen/Floor2DView.vue | 新增 | 2D平面图渲染 |

### 4. 演示数据集成

加载演示数据时自动生成8张楼层图（4层 x 2类型）：
- Phase 6 (88-92%): 生成楼层平面图
- 数据存储在 floor_maps 表

### 5. 验证清单

- [x] 侧边栏无大屏菜单项
- [x] 仪表盘大屏按钮功能正常
- [x] 大屏面板点击可导航到主界面
- [x] 楼层选择器显示B1/F1/F2/F3
- [x] 2D/3D切换功能正常
- [x] 2D平面图正确渲染设备布局
- [x] 加载演示数据时生成楼层图

### 6. 更新日志

| 日期 | 版本 | 更新内容 |
|------|------|----------|
| 2026-01-20 | V3.5 | 数据与功能统一整合：修复点位统计字段映射、大屏导航、集成配电拓扑数据、添加大屏交互导航 |
| 2026-01-20 | V3.5.1 | 补充修复：清理残留点位数据、修复配电柜与计量点关联 |
| 2026-01-20 | V4.0 | 数字孪生大屏楼层可视化：移除侧边栏入口、修复面板导航、新增2D/3D楼层图系统 |
| 2026-01-21 | V4.1 | 交互式面板增强：可拖拽面板、折叠/展开、面板可见性管理、新标签页导航 |
| 2026-01-21 | V4.2 | 面板交互修复：折叠状态可拖拽、折叠显示半透明标题栏、返回按钮不影响主界面 |

---

## 2026-01-21 数字孪生大屏面板修复 V4.2

### 1. 问题概述

V4.1版本存在三个交互问题需要修复。

### 2. 问题分析与修复

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 返回按钮影响主界面 | goBack 使用 Vue Router 导航 | 改用 window.close() + location.href 回退 |
| 折叠时宽度缩小到50px | CSS 设置了 width: 50px | 移除宽度限制，保持原有宽度 |
| 折叠状态无法拖拽 | startDrag 检查 isCollapsed 提前返回 | 移除该限制 |

### 3. 代码修改

#### 3.1 goBack 函数修改

```typescript
// 修改前
function goBack() {
  if (window.opener) {
    window.close()
  } else {
    router.push('/dashboard')  // 影响主界面状态
  }
}

// 修改后
function goBack() {
  window.close()
  setTimeout(() => {
    window.location.href = '/dashboard'  // 不影响 Vue 状态
  }, 100)
}
```

#### 3.2 DraggablePanel 折叠样式修改

```scss
// 修改前
&.collapsed {
  width: 50px !important;  // 强制缩小宽度
  min-width: 50px;
  // 显示 collapsed-title 缩写
}

// 修改后
&.collapsed {
  // 不设置宽度，保持原有宽度
  .panel-header {
    background: rgba(0, 50, 80, 0.6);  // 半透明标题栏
    border-bottom: none;
    border-radius: 8px;
  }
}
```

#### 3.3 移除折叠状态拖拽限制

```typescript
// 修改前
function startDrag(e: MouseEvent | TouchEvent) {
  if (isCollapsed.value) return  // 阻止折叠状态拖拽
  // ...
}

// 修改后
function startDrag(e: MouseEvent | TouchEvent) {
  // 允许在折叠状态下拖拽
  isDragging.value = true
  // ...
}
```

### 4. 文件修改清单

| 文件 | 修改内容 |
|------|----------|
| frontend/src/views/bigscreen/index.vue | goBack 函数改用 window.close + location.href |
| frontend/src/components/bigscreen/ui/DraggablePanel.vue | 重新设计折叠行为和样式 |
| docs/plans/2026-01-19-bigscreen-digital-twin-design.md | 更新至 V1.2 |
| docs/plans/2026-01-21-bigscreen-panel-fixes.md | 新增修复计划 |

### 5. 验证清单

- [x] 大屏返回按钮关闭窗口，不影响主界面
- [x] 面板折叠时显示半透明标题栏
- [x] 面板折叠时保持原有宽度
- [x] 面板在折叠状态下可拖拽
- [x] 构建成功无错误

---

## 2026-01-21 数字孪生大屏交互式面板 V4.1

### 1. 功能概述

增强数字孪生大屏的交互功能，实现面板拖拽、折叠/展开、可见性控制，以及点击导航在新标签页打开。

**新增功能**：
| 功能 | 描述 |
|------|------|
| 面板拖拽 | 所有悬浮面板支持拖动标题栏移动位置 |
| 折叠/展开 | 点击折叠按钮可收起面板，仅显示标题栏 |
| 位置持久化 | 面板位置自动保存到 localStorage |
| 可见性控制 | 底部控制栏可切换面板显示/隐藏 |
| 重置布局 | 一键恢复所有面板到默认位置 |
| 新标签页导航 | 所有可点击区域在新标签页打开对应页面 |

### 2. 实现内容

#### 2.1 DraggablePanel 组件

**组件属性**：
```typescript
interface DraggablePanelProps {
  title: string           // 面板标题
  panelId: string         // 面板唯一标识
  initialX: number        // 初始X位置
  initialY: number        // 初始Y位置
  initialCollapsed: boolean // 初始折叠状态
}
```

**事件**：
- `positionChange`: 位置变化时触发，传递 `{ id, x, y }`
- `collapseChange`: 折叠状态变化时触发，传递 `{ id, collapsed }`

**拖拽实现**：
- 使用 `mousedown/mousemove/mouseup` 事件
- 支持触摸设备 `touchstart/touchmove/touchend`
- 限制拖拽范围不超出视口

#### 2.2 Pinia Store 面板状态管理

**状态结构**：
```typescript
interface PanelState {
  x: number         // X 位置
  y: number         // Y 位置
  collapsed: boolean // 是否折叠
  visible: boolean   // 是否可见
}

panelStates: {
  leftPanel: { x: 20, y: 60, collapsed: false, visible: true },
  rightPanel: { x: -300, y: 60, collapsed: false, visible: true },
  floorSelector: { x: 20, y: 120, collapsed: false, visible: true },
  deviceDetail: { x: -320, y: 60, collapsed: false, visible: true }
}
```

**关键方法**：
| 方法 | 功能 |
|------|------|
| `updatePanelPosition(id, x, y)` | 更新面板位置 |
| `updatePanelCollapsed(id, collapsed)` | 更新折叠状态 |
| `togglePanelVisible(id)` | 切换面板可见性 |
| `savePanelStates()` | 保存状态到 localStorage |
| `loadPanelStates()` | 从 localStorage 加载状态 |
| `resetPanelStates()` | 重置所有面板到默认位置 |

**右侧面板定位**：
- 使用负数 x 值表示从右边缘计算
- 运行时计算实际位置：`window.innerWidth + panelState.x`

#### 2.3 底部控制栏面板管理

新增面板切换区域：
```vue
<div class="panel-toggles">
  <span class="label">面板:</span>
  <el-checkbox @change="store.togglePanelVisible('leftPanel')">环境</el-checkbox>
  <el-checkbox @change="store.togglePanelVisible('rightPanel')">能耗</el-checkbox>
  <el-checkbox @change="store.togglePanelVisible('floorSelector')">楼层</el-checkbox>
  <el-button @click="store.resetPanelStates()">重置</el-button>
</div>
```

#### 2.4 新标签页导航

所有面板点击导航统一使用 `window.open(url, '_blank')`：
```typescript
function handleNavigate(path: string) {
  const baseUrl = window.location.origin
  const fullUrl = `${baseUrl}${path}`
  window.open(fullUrl, '_blank')
}
```

**导航映射**：
| 面板区域 | 导航目标 |
|---------|----------|
| 实时功率 | `/energy/analysis` |
| PUE 趋势 | `/energy/analysis` |
| 今日用电 | `/energy/statistics` |
| 需量状态 | `/energy/topology` |
| 温度/湿度 | `/monitor` |
| 告警列表 | `/alarm` |

### 3. 文件修改清单

| 文件 | 操作 | 说明 |
|------|------|------|
| frontend/src/components/bigscreen/ui/DraggablePanel.vue | 新增 | 可拖拽面板包装组件 |
| frontend/src/components/bigscreen/ui/index.ts | 修改 | 导出 DraggablePanel |
| frontend/src/stores/bigscreen.ts | 修改 | 添加面板状态管理 |
| frontend/src/components/bigscreen/panels/LeftPanel.vue | 修改 | 使用 DraggablePanel |
| frontend/src/components/bigscreen/panels/RightPanel.vue | 修改 | 使用 DraggablePanel |
| frontend/src/components/bigscreen/FloorSelector.vue | 修改 | 使用 DraggablePanel |
| frontend/src/views/bigscreen/index.vue | 修改 | 添加面板管理控件 |
| docs/plans/2026-01-19-bigscreen-digital-twin-design.md | 修改 | 更新至 V1.1 |

### 4. 技术要点

1. **拖拽边界限制**：计算视口边界防止面板超出可视区域
2. **负数定位**：右侧面板使用负数 x 值，运行时计算实际位置
3. **localStorage 持久化**：面板状态在页面刷新后保持
4. **CSS 过渡动画**：折叠/展开使用 CSS transition 实现平滑动画
5. **事件阻止**：拖拽时阻止事件冒泡避免触发其他交互

### 5. 验证清单

- [x] 所有面板可拖拽移动
- [x] 面板位置刷新后保持
- [x] 折叠/展开功能正常
- [x] 底部控制栏可切换面板可见性
- [x] 重置按钮恢复默认布局
- [x] 点击面板在新标签页打开对应页面
- [x] 前端构建通过
