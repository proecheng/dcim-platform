# 前端架构文档

## 技术栈概览

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue 3 | 3.4.15 | 前端框架 (Composition API) |
| TypeScript | 5.9.3 | 类型安全 |
| Vite | 5.0.11 | 构建工具 + 开发服务器 |
| Element Plus | 2.5.3 | UI 组件库 (中文本地化) |
| Pinia | 2.1.7 | 状态管理 |
| Vue Router | 4.2.5 | 路由管理 |
| ECharts | 5.6.0 | 数据可视化图表 |
| Three.js | 0.182.0 | 3D 数字孪生渲染 |
| Axios | 1.6.5 | HTTP 客户端 |
| GSAP | 3.14.2 | 动画引擎 |
| Day.js | 1.11.10 | 日期处理 |
| SASS | 1.70.0 | CSS 预处理器 |
| DataV Vue3 | 1.7.4 | 大屏数据可视化组件 |
| v-scale-screen | 2.3.0 | 大屏自适应缩放 |

自动化工具:
- unplugin-auto-import: Vue/Pinia API 自动导入，无需手动 import ref/computed/onMounted
- unplugin-vue-components: Element Plus 组件按需自动注册

## 架构模式

### 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    Vue 3 应用 (SPA)                      │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │  Views   │  │Components│  │ Layouts  │  ← 视图层     │
│  │ (60页面) │  │ (74组件) │  │ (主布局) │              │
│  └────┬─────┘  └────┬─────┘  └──────────┘              │
│       │              │                                   │
│  ┌────┴──────────────┴─────┐                            │
│  │    Composables (18个)    │  ← 逻辑复用层             │
│  │  useWebSocket, useAlarm │                            │
│  │  useRealtime, useEnergy │                            │
│  └────────────┬────────────┘                            │
│               │                                          │
│  ┌────────────┴────────────┐                            │
│  │   Pinia Stores (8个)    │  ← 状态管理层             │
│  │  user, app, alarm,      │                            │
│  │  realtime, energy,      │                            │
│  │  bigscreen, opportunity, │                            │
│  │  degradation            │                            │
│  └────────────┬────────────┘                            │
│               │                                          │
│  ┌────────────┴────────────┐                            │
│  │   API 模块 (30+个)      │  ← 数据访问层             │
│  │  Axios 实例 + 拦截器    │                            │
│  └────────────┬────────────┘                            │
│               │                                          │
│  ┌────────────┴────────────┐                            │
│  │   WebSocket 客户端      │  ← 实时通信层             │
│  │  realtime/alarms/system │                            │
│  └─────────────────────────┘                            │
└─────────────────────────────────────────────────────────┘
```

### 设计原则

1. 组合式 API (Composition API): 所有组件使用 `<script setup lang="ts">` 语法
2. 自动导入: Vue/Pinia API 和 Element Plus 组件无需手动 import
3. 暗色主题优先: 默认启用 Element Plus 暗色模式 (`document.documentElement.classList.add('dark')`)
4. 响应式数据流: Pinia Store → 组件响应式更新
5. WebSocket 实时推送: 通过 composable 封装，Store 自动同步

## 目录结构

```
frontend/src/
├── api/                    # API 调用层
│   ├── index.ts            # 统一导出
│   ├── auth.ts             # 认证 API
│   ├── alarm.ts            # 告警 API
│   ├── realtime.ts         # 实时数据 API
│   ├── websocket.ts        # WebSocket 管理
│   ├── datasource.ts       # 数据源 API
│   ├── device-template.ts  # 设备模板 API
│   ├── point.ts            # 点位 API
│   └── modules/            # 业务 API 模块 (25+ 个)
│       ├── user.ts, device.ts, energy.ts, power.ts ...
│       └── types.ts        # 公共类型定义
├── components/             # 组件库 (74 个)
│   ├── common/             # 公共组件 (DataTable, SearchForm, ConfirmDialog 等)
│   ├── charts/             # 图表组件 (LineChart, BarChart, PieChart, GaugeChart 等)
│   ├── monitor/            # 监控组件 (PointCard, ValueDisplay, StatusPanel)
│   ├── energy/             # 能源组件 (PUEGauge, PowerCard, DemandDashboard 等 20个)
│   ├── bigscreen/          # 大屏组件 (ThreeScene, DataCenterModel, HeatmapOverlay 等)
│   │   ├── charts/         # 大屏图表
│   │   ├── panels/         # 大屏面板
│   │   └── ui/             # 大屏 UI 基础
│   ├── floor-layouts/      # 楼层布局 (F1-F3, B1)
│   ├── demand/             # 需量组件
│   ├── asset/              # 资产组件
│   └── video/              # 视频组件
├── composables/            # 组合式函数 (18 个)
│   ├── useWebSocket.ts     # WebSocket 连接管理
│   ├── useRealtime.ts      # 实时数据订阅
│   ├── useAlarm.ts         # 告警处理
│   ├── useEnergy.ts        # 能源数据
│   ├── usePermission.ts    # 权限检查
│   ├── useSound.ts         # 告警声音
│   ├── useDataQuality.ts   # 数据质量
│   └── bigscreen/          # 大屏专用 (11 个)
│       ├── useThreeScene.ts, useBuildingModel.ts, useCameraAnimation.ts
│       ├── useAutoTour.ts, useRaycaster.ts, useSceneMode.ts
│       ├── useEntranceAnimation.ts, useScreenAdapt.ts
│       ├── useBigscreenData.ts, useTheme.ts, useKeyboardShortcuts.ts
│       └── index.ts
├── config/                 # 配置
│   ├── echartsTheme.ts     # ECharts 深色主题注册
│   └── themes/             # 大屏主题 (night, realistic, wireframe, tech-blue)
├── layouts/                # 布局
│   └── MainLayout.vue      # 主布局 (侧边栏 + 顶栏 + 内容区)
├── router/                 # 路由
│   └── index.ts            # 路由配置 (60+ 路由)
├── stores/                 # Pinia 状态管理 (8 个)
│   ├── user.ts, app.ts, alarm.ts, realtime.ts
│   ├── energy.ts, bigscreen.ts, opportunity.ts, degradation.ts
│   └── index.ts
├── styles/                 # 全局样式
│   └── index.scss          # 主样式入口
├── types/                  # TypeScript 类型
│   ├── bigscreen.ts        # 大屏类型
│   ├── theme.ts            # 主题类型
│   └── element-plus.d.ts   # Element Plus 类型扩展
├── utils/                  # 工具函数
│   ├── request.ts          # Axios 实例 (拦截器/认证头/错误处理)
│   ├── logger.ts           # 日志工具
│   ├── index.ts            # 通用工具
│   └── three/              # Three.js 工具
│       ├── sceneSetup.ts, modelGenerator.ts, heatmapHelper.ts
│       ├── labelRenderer.ts, alarmPulseEffect.ts, powerFlowEffect.ts
│       ├── postProcessing.ts, performanceMonitor.ts
│       └── index.ts
├── views/                  # 页面视图 (60 个)
│   ├── login/              # 登录
│   ├── dashboard/          # 仪表盘
│   ├── bigscreen/          # 数字孪生大屏
│   ├── power/              # 供配电 (5 页面)
│   ├── cooling/            # 制冷 (5 页面)
│   ├── environment/        # 环境监控
│   ├── security/           # 安防消防
│   ├── energy/             # 能源管理 (9 页面)
│   ├── alarm/              # 告警管理
│   ├── history/            # 历史数据
│   ├── report/             # 报表
│   ├── device/             # 点位管理
│   ├── device-manage/      # 设备管理
│   ├── device-status/      # 设备状态看板
│   ├── device-template/    # 设备模板
│   ├── datasource/         # 数据源
│   ├── asset/              # 资产管理
│   ├── capacity/           # 容量管理
│   ├── topology/           # 拓扑管理 (5 页面)
│   ├── operation/          # 运维管理 (3 页面)
│   ├── linkage/            # 联动管理 (6 页面)
│   ├── diagnosis/          # 智能诊断 (2 页面)
│   ├── video/              # 视频监控 (3 页面)
│   ├── vpp/                # 虚拟电厂
│   ├── system/             # 系统管理
│   └── settings/           # 系统设置
├── App.vue                 # 根组件
├── main.ts                 # 应用入口
└── vite-env.d.ts           # Vite 环境类型
```

## 路由架构

### 路由层级

```
/ (MainLayout)
├── /dashboard              # 首页仪表盘
├── /devices                # 点位管理
├── /datasources            # 数据源管理
├── /device-templates       # 设备模板
├── /device-manage          # 设备管理
│   └── /detail/:id         # 设备详情
├── /device-status          # 设备状态看板
├── /diagnosis              # 智能诊断
│   ├── /results
│   └── /rules
├── /power                  # 供配电管理 (9 子路由)
├── /cooling                # 制冷系统 (5 子路由)
├── /environment            # 环境监控
├── /security               # 安防消防
├── /infrastructure         # 基础设施 (8 子路由)
├── /energy-saving          # 节能中心 (4 子路由)
├── /alarms                 # 告警管理
├── /history                # 历史数据
├── /reports                # 报表分析
├── /operation              # 运维管理 (3 子路由)
├── /vpp                    # 虚拟电厂
├── /linkage                # 联动管理 (6 子路由)
├── /video                  # 视频监控 (3 子路由)
├── /settings               # 系统设置
└── /system                 # 系统管理 (2 子路由)

/login                      # 登录页 (无需认证)
/bigscreen                  # 数字孪生大屏 (全屏, 无需认证)
```

### 路由守卫

- 全局前置守卫: 检查 `userStore.token`，未登录跳转 `/login`
- `meta.requiresAuth: false` 的路由跳过认证检查 (login, bigscreen)
- 旧路由兼容: `/energy/*` → `/power/*` 或 `/energy-saving/*`

## 状态管理架构

8 个 Pinia Store 按职责划分:

| Store | 职责 | 持久化 | 数据来源 |
|-------|------|--------|----------|
| user | 用户认证/权限 | localStorage (token) | API 登录 |
| app | 全局 UI 状态 | localStorage (设置) | 用户操作 |
| alarm | 活跃告警 | 否 | WebSocket 推送 |
| realtime | 实时点位数据 | 否 | WebSocket 推送 |
| energy | 能源实时数据 | 否 | WebSocket + API |
| bigscreen | 大屏状态/3D场景 | localStorage (面板位置) | API + 用户操作 |
| opportunity | 节能机会/执行计划 | 否 | API |
| degradation | 服务降级状态 | 否 | API 响应头 |

详细的 Store 状态字段、Getters、Actions 参见 [component-inventory-frontend.md](component-inventory-frontend.md)。

## API 调用层架构

### Axios 实例 (utils/request.ts)

```
请求拦截器:
  → 自动添加 Authorization: Bearer <token>
  → 设置 Content-Type

响应拦截器:
  → 401 → 清除 token, 跳转登录
  → 降级标记 → 同步到 degradation store
  → 错误提示 → Element Plus Message
```

### API 模块组织

```
api/
├── 顶层文件 (直接调用)
│   ├── auth.ts      → POST /auth/login, /auth/logout, /auth/refresh
│   ├── alarm.ts     → GET/PUT /alarms/*
│   ├── realtime.ts  → GET /realtime/*
│   └── websocket.ts → WS /ws/realtime, /ws/alarms, /ws/system
└── modules/ (按业务域)
    ├── energy.ts    → GET/POST/PUT/DELETE /energy/*
    ├── power.ts     → GET /power/*
    └── ... (25+ 模块, 与后端 API 一一对应)
```

## 3D 数字孪生架构

### Three.js 渲染管线

```
ThreeScene.vue (容器)
  → useThreeScene (场景/相机/渲染器初始化)
    → useBuildingModel (建筑模型生成)
      → modelGenerator.ts (程序化生成楼层/机柜/设备)
    → useRaycaster (鼠标交互/设备选择)
    → useCameraAnimation (相机平滑过渡)
    → useAutoTour (自动巡游路径)
    → useSceneMode (监控/巡检/热力图模式)
    → useEntranceAnimation (入场动画)
    → postProcessing.ts (后处理效果)
    → performanceMonitor.ts (FPS 监控)

叠加层:
  → HeatmapOverlay (温度热力图)
  → AlarmBubbles (告警气泡动画)
  → CabinetLabels (机柜标签)
  → DeviceDetailPanel (设备详情面板)
  → Floor2DView (2D 楼层平面图)
```

### 主题系统

4 套大屏主题 (config/themes/):
- night: 夜景模式
- realistic: 写实模式
- wireframe: 线框模式
- tech-blue: 科技蓝模式

## 构建和部署

### 开发模式

```bash
npm run dev  # Vite 开发服务器, 端口 3000, HMR 热更新
```

Vite 代理配置:
- `/api/*` → `http://localhost:8080`
- `/ws/*` → `ws://localhost:8080`

### 生产构建

```bash
npm run build      # 输出到 dist/
npm run typecheck   # TypeScript 类型检查
npm run preview     # 预览构建产物
```

构建产物由 Express proxy (proxy/server.js) 或 Nginx 提供静态文件服务。

## 关键设计决策

1. 暗色主题优先: 系统面向机房运维场景，暗色主题减少视觉疲劳，main.ts 中直接启用
2. 自动导入: 减少样板代码，提升开发效率
3. 组合式函数封装 WebSocket: 将实时通信逻辑从组件中解耦
4. 程序化 3D 模型: 使用 Three.js 程序化生成建筑模型，而非加载外部 3D 文件，减少资源依赖
5. 路由兼容重定向: 系统经历多次重构 (energy → power/energy-saving)，保留旧路由兼容
6. Element Plus 运行时样式覆盖: 因按需加载 CSS 顺序问题，main.ts 中通过 JS 动态注入最高优先级暗色样式
7. 大屏独立路由: /bigscreen 不使用 MainLayout，全屏展示，无需认证
