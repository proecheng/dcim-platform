# 源码目录树 - DCIM 算力中心智能监控系统

> 生成时间: 2026-02-04
> 扫描模式: exhaustive (详尽扫描)

---

## 项目根目录结构

```
mytest1/
├── frontend/                    # Vue 3 前端应用
├── backend/                     # FastAPI 后端服务
├── proxy/                       # Express 反向代理
├── docs/                        # 项目文档
├── tests/                       # 测试文件
├── _bmad/                       # BMAD 工作流配置
├── start.bat                    # Windows 一键启动
├── stop.bat                     # 停止服务
├── docker-compose.yml           # Docker 编排
└── CLAUDE.md                    # 开发指导文件
```

---

## Frontend 前端源码 (260 文件)

```
frontend/src/
├── App.vue                      # 根组件
├── main.ts                      # 应用入口
├── vite-env.d.ts               # Vite 类型声明
├── auto-imports.d.ts           # 自动导入类型
├── components.d.ts             # 组件类型声明
│
├── api/                         # API 层 (33 文件)
│   ├── index.ts                # API 统一导出
│   ├── websocket.ts            # WebSocket 客户端
│   └── modules/                # API 模块 (27 个)
│       ├── auth.ts             # 认证 API
│       ├── user.ts             # 用户 API
│       ├── device.ts           # 设备 API
│       ├── point.ts            # 点位 API
│       ├── realtime.ts         # 实时数据 API
│       ├── alarm.ts            # 告警 API
│       ├── history.ts          # 历史数据 API
│       ├── energy.ts           # 能源管理 API
│       ├── demand.ts           # 需量分析 API
│       ├── dispatch.ts         # 调度配置 API
│       ├── monitoring.ts       # 电费监控 API
│       ├── opportunities.ts    # 节能机会 API
│       ├── optimization.ts     # 优化 API
│       ├── vpp.ts              # VPP 方案 API
│       ├── asset.ts            # 资产管理 API
│       ├── capacity.ts         # 容量管理 API
│       ├── operation.ts        # 运维管理 API
│       ├── bigscreen.ts        # 大屏数据 API
│       ├── config.ts           # 配置 API
│       ├── demo.ts             # 演示数据 API
│       ├── floorMap.ts         # 楼层图 API
│       ├── log.ts              # 日志 API
│       ├── report.ts           # 报表 API
│       ├── statistics.ts       # 统计 API
│       ├── threshold.ts        # 阈值 API
│       └── types.ts            # 类型定义
│
├── components/                  # 组件库 (67 组件)
│   ├── common/                 # 通用组件 (6 个)
│   │   ├── DataTable.vue       # 数据表格
│   │   ├── DateRangePicker.vue # 日期范围选择
│   │   ├── ConfirmDialog.vue   # 确认对话框
│   │   ├── ExportButton.vue    # 导出按钮
│   │   ├── SearchForm.vue      # 搜索表单
│   │   └── StatusTag.vue       # 状态标签
│   │
│   ├── charts/                 # 图表组件 (7 个)
│   │   ├── LineChart.vue       # 折线图
│   │   ├── BarChart.vue        # 柱状图
│   │   ├── PieChart.vue        # 饼图
│   │   ├── GaugeChart.vue      # 仪表盘
│   │   ├── RealtimeChart.vue   # 实时图表
│   │   └── Sparkline.vue       # 迷你趋势图
│   │
│   ├── monitor/                # 监控组件 (4 个)
│   │   ├── PointCard.vue       # 点位卡片
│   │   ├── ValueDisplay.vue    # 数值显示
│   │   ├── AlarmBadge.vue      # 告警徽章
│   │   └── StatusPanel.vue     # 状态面板
│   │
│   ├── energy/                 # 能源组件 (24 个)
│   │   ├── PowerCard.vue       # 功率卡片
│   │   ├── PUEGauge.vue        # PUE 仪表
│   │   ├── PUEIndicatorCard.vue # PUE 指标卡片
│   │   ├── InteractivePowerCard.vue # 交互功率卡片
│   │   ├── CostCard.vue        # 成本卡片
│   │   ├── DemandDashboard.vue # 需量仪表盘
│   │   ├── DemandStatusCard.vue # 需量状态卡片
│   │   ├── ScheduleDashboard.vue # 调度仪表盘
│   │   ├── ShiftPlanBuilder.vue  # 负荷转移计划构建器
│   │   ├── DeviceList.vue      # 设备列表
│   │   ├── DevicePowerCurveChart.vue # 设备功率曲线
│   │   ├── DeviceShiftDetailDrawer.vue # 设备转移详情
│   │   ├── DispatchConfig.vue  # 调度配置
│   │   ├── EnergySuggestionCard.vue # 节能建议卡片
│   │   ├── SuggestionDetailDrawer.vue # 建议详情
│   │   ├── SuggestionOverview.vue # 建议概览
│   │   ├── SuggestionsCard.vue # 建议卡片
│   │   ├── ExecutionPlanDialog.vue # 执行计划对话框
│   │   ├── LoadComparisonChart.vue # 负荷对比图
│   │   ├── OptimizationOverview.vue # 优化概览
│   │   ├── OptimizationReport.vue # 优化报告
│   │   ├── ParameterAdjustment.vue # 参数调节
│   │   └── CalculationDetails.vue # 计算详情
│   │
│   ├── bigscreen/              # 大屏组件 (18 个)
│   │   ├── ThreeScene.vue      # Three.js 主场景
│   │   ├── DataCenterModel.vue # 数据中心 3D 模型
│   │   ├── HeatmapOverlay.vue  # 热力图覆盖层
│   │   ├── Floor2DView.vue     # 2D 楼层视图
│   │   ├── FloorSelector.vue   # 楼层选择器
│   │   ├── AlarmBubbles.vue    # 告警气泡效果
│   │   ├── CabinetLabels.vue   # 机柜标签
│   │   ├── DeviceDetailPanel.vue # 设备详情面板
│   │   ├── charts/             # 大屏专用图表
│   │   │   ├── BaseChart.vue
│   │   │   ├── TemperatureTrend.vue
│   │   │   ├── PowerDistribution.vue
│   │   │   ├── PueTrend.vue
│   │   │   └── GaugeChart.vue
│   │   ├── panels/             # 信息面板
│   │   │   ├── LeftPanel.vue
│   │   │   └── RightPanel.vue
│   │   └── ui/                 # UI 控件
│   │       ├── DigitalFlop.vue    # 数字翻牌
│   │       ├── ContextMenu.vue    # 右键菜单
│   │       ├── ThemeSelector.vue  # 主题选择
│   │       └── DraggablePanel.vue # 可拖拽面板
│   │
│   ├── floor-layouts/          # 楼层布局 (6 个)
│   │   ├── FloorLayoutBase.vue # 布局基类
│   │   ├── FloorLayoutSelector.vue # 布局选择器
│   │   ├── FloorB1Layout.vue   # B1 层
│   │   ├── FloorF1Layout.vue   # F1 层
│   │   ├── FloorF2Layout.vue   # F2 层
│   │   └── FloorF3Layout.vue   # F3 层
│   │
│   └── demand/                 # 需量组件 (3 个)
│       ├── DemandCurveMini.vue
│       ├── DemandComparisonCard.vue
│       └── LoadPeriodChart.vue
│
├── composables/                # 组合式函数 (19 个)
│   ├── useWebSocket.ts         # WebSocket 封装
│   ├── useRealtime.ts          # 实时数据订阅
│   ├── useAlarm.ts             # 告警处理
│   ├── useSound.ts             # 声音通知
│   ├── usePermission.ts        # 权限控制
│   ├── useEnergy.ts            # 能源数据
│   └── bigscreen/              # 大屏组合函数 (12 个)
│       ├── useThreeScene.ts    # Three.js 场景管理
│       ├── useBuildingModel.ts # 建筑模型加载
│       ├── useCameraAnimation.ts # 摄像机动画
│       ├── useRaycaster.ts     # 射线检测
│       ├── useAutoTour.ts      # 自动巡游
│       ├── useSceneMode.ts     # 场景模式
│       ├── useBigscreenData.ts # 大屏数据
│       ├── useScreenAdapt.ts   # 屏幕适配
│       ├── useEntranceAnimation.ts # 入场动画
│       ├── useTheme.ts         # 主题切换
│       └── useKeyboardShortcuts.ts # 键盘快捷键
│
├── stores/                     # Pinia 状态管理 (7 个)
│   ├── user.ts                 # 用户认证 & Token
│   ├── app.ts                  # 应用全局状态
│   ├── alarm.ts                # 告警数据
│   ├── realtime.ts             # 实时监控数据
│   ├── energy.ts               # 能源管理数据
│   ├── bigscreen.ts            # 大屏状态
│   └── opportunity.ts          # 节能机会数据
│
├── views/                      # 页面视图 (23 页)
│   ├── login/index.vue         # 登录页
│   ├── dashboard/index.vue     # 监控仪表盘
│   ├── bigscreen/index.vue     # 3D 数字孪生大屏
│   ├── device/index.vue        # 点位管理
│   ├── alarm/index.vue         # 告警管理
│   ├── history/index.vue       # 历史数据
│   ├── report/index.vue        # 报表分析
│   ├── settings/index.vue      # 系统设置
│   ├── capacity/index.vue      # 容量管理
│   ├── energy/                 # 能源管理模块 (8 页)
│   │   ├── monitor.vue         # 用电监控
│   │   ├── statistics.vue      # 能耗统计
│   │   ├── analysis.vue        # 节能中心
│   │   ├── suggestions.vue     # 节能建议
│   │   ├── config.vue          # 配电配置
│   │   ├── topology.vue        # 配电拓扑
│   │   ├── regulation.vue      # 负荷调节
│   │   └── execution.vue       # 执行管理
│   ├── asset/                  # 资产管理 (2 页)
│   │   ├── index.vue           # 资产台账
│   │   └── cabinet.vue         # 机柜管理
│   ├── operation/              # 运维管理 (3 页)
│   │   ├── workorder.vue       # 工单管理
│   │   ├── inspection.vue      # 巡检管理
│   │   └── knowledge.vue       # 知识库
│   └── vpp/                    # VPP 虚拟电厂
│       └── VPPAnalysis.vue     # VPP 方案分析
│
├── router/index.ts             # 路由配置
├── layouts/MainLayout.vue      # 主布局组件
│
├── config/                     # 配置文件
│   ├── echartsTheme.ts         # ECharts 主题
│   └── themes/                 # 大屏主题 (4 套)
│       ├── tech-blue.ts        # 科技蓝
│       ├── night.ts            # 夜间模式
│       ├── realistic.ts        # 写实风格
│       └── wireframe.ts        # 线框模式
│
├── styles/                     # 样式
│   ├── index.scss              # 全局样式
│   ├── element-dark.scss       # Element 暗黑主题
│   └── themes/dark-tech.scss   # 深色科技主题
│
├── utils/                      # 工具函数
│   ├── index.ts                # 通用工具
│   ├── request.ts              # Axios 封装
│   ├── logger.ts               # 日志工具
│   └── three/                  # Three.js 工具 (9 个)
│       ├── sceneSetup.ts       # 场景初始化
│       ├── modelGenerator.ts   # 3D 模型生成
│       ├── heatmapHelper.ts    # 热力图工具
│       ├── labelRenderer.ts    # 标签渲染
│       ├── alarmPulseEffect.ts # 告警脉冲特效
│       ├── powerFlowEffect.ts  # 电力流动特效
│       ├── postProcessing.ts   # 后处理效果
│       └── performanceMonitor.ts # 性能监控
│
└── types/                      # TypeScript 类型
    ├── bigscreen.ts            # 大屏类型
    ├── theme.ts                # 主题类型
    └── element-plus.d.ts       # Element Plus 类型
```

---

## Backend 后端源码 (157 文件)

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 应用入口 (lifespan)
│   │
│   ├── core/                   # 核心模块
│   │   ├── config.py           # Settings (@lru_cache 单例)
│   │   ├── database.py         # 异步数据库 (SQLAlchemy 2.0)
│   │   ├── security.py         # JWT + RBAC 认证
│   │   └── logging.py          # 日志配置
│   │
│   ├── api/v1/                 # REST API (32 路由模块)
│   │   ├── auth.py             # POST /login, /refresh
│   │   ├── user.py             # CRUD /users
│   │   ├── device.py           # CRUD /devices
│   │   ├── point.py            # CRUD /points
│   │   ├── realtime.py         # GET /realtime/current
│   │   ├── alarm.py            # CRUD /alarms + 统计
│   │   ├── threshold.py        # CRUD /thresholds
│   │   ├── history.py          # GET /history + 趋势
│   │   ├── report.py           # 报表生成+导出
│   │   ├── statistics.py       # 统计分析
│   │   ├── energy.py           # 能源管理核心
│   │   ├── demand.py           # 需量分析
│   │   ├── regulation.py       # 负荷调节
│   │   ├── topology.py         # 配电拓扑编辑
│   │   ├── opportunities.py    # 节能机会发现
│   │   ├── execution.py        # 执行计划管理
│   │   ├── dispatch.py         # 可调度资源配置
│   │   ├── monitoring.py       # 电费实时监控
│   │   ├── vpp.py              # VPP 方案分析
│   │   ├── pricing.py          # 电价配置
│   │   ├── asset.py            # 资产台账
│   │   ├── capacity.py         # 容量管理
│   │   ├── operation.py        # 工单/巡检/知识库
│   │   ├── ml.py               # ML 训练+推理 [可选]
│   │   ├── trace.py            # 数据追溯链
│   │   ├── demo.py             # 演示数据
│   │   └── floor_map.py        # 楼层图
│   │
│   ├── models/                 # SQLAlchemy 模型 (70+ 类)
│   │   ├── user.py             # User, RolePermission, UserLoginHistory
│   │   ├── device.py           # Device
│   │   ├── point.py            # Point, PointRealtime, PointGroup
│   │   ├── alarm.py            # Alarm, AlarmThreshold, AlarmRule, AlarmShield
│   │   ├── history.py          # PointHistory, PointHistoryArchive
│   │   ├── log.py              # OperationLog, SystemLog, CommunicationLog
│   │   ├── energy.py           # 20+ 能源相关模型
│   │   ├── asset.py            # 8 资产模型
│   │   ├── capacity.py         # 8 容量模型
│   │   ├── operation.py        # 5 运维模型
│   │   ├── vpp_data.py         # 6 VPP 模型
│   │   └── trace.py            # 6 追溯模型 (专利 S1)
│   │
│   ├── schemas/                # Pydantic 模式 (60+ 类)
│   │   ├── common.py           # PaginatedResponse, StatusResponse
│   │   ├── user.py, device.py, alarm.py ...
│   │   └── (匹配 models 结构)
│   │
│   ├── services/               # 业务服务 (53 文件)
│   │   ├── websocket.py        # WebSocket 连接管理
│   │   ├── simulator.py        # 实时数据模拟 (5s 间隔)
│   │   ├── collector.py        # 数据采集
│   │   ├── forecasting.py      # 负荷预测
│   │   ├── optimizer.py        # 优化引擎
│   │   ├── suggestion_engine.py # 节能建议引擎
│   │   ├── opportunity_engine.py # 机会发现引擎
│   │   ├── execution_service.py # 方案执行
│   │   ├── vpp_calculator.py   # VPP 收益计算
│   │   ├── pricing_service.py  # 电价管理
│   │   ├── formula_calculator.py # 公式计算引擎
│   │   ├── template_generator.py # 方案模板生成
│   │   ├── ml_service.py       # ML 模型服务
│   │   ├── data_trace_service.py # 数据追溯 (专利)
│   │   ├── adaptive_optimization_service.py # RL 自适应 (专利 S5)
│   │   ├── effect_monitoring_service.py # 效果监测 (专利 S4)
│   │   ├── feedback_learning.py # 反馈学习
│   │   ├── realtime_dispatch.py # 实时调度
│   │   └── analysis_plugins/   # 分析插件系统
│   │       ├── base.py         # 插件基类
│   │       ├── registry.py     # 插件注册中心
│   │       ├── manager.py      # 插件管理器
│   │       ├── power_factor.py # 功率因数优化
│   │       ├── peak_valley.py  # 峰谷套利分析
│   │       ├── pue_optimization.py # PUE 优化
│   │       ├── equipment_efficiency.py # 设备能效
│   │       ├── load_shifting.py # 负荷转移
│   │       └── demand_optimization.py # 需量优化
│   │
│   └── ml_models/              # 机器学习 (15 文件)
│       ├── config.py           # 模型配置
│       ├── transformer/        # Transformer 预测
│       │   ├── model.py        # 编码器模型
│       │   ├── dataset.py      # 时序数据集
│       │   └── predictor.py    # 预测器
│       ├── gnn/                # 图神经网络
│       │   ├── model.py        # GNN 模型
│       │   ├── graph_builder.py # 设备关系图构建
│       │   └── predictor.py    # 关联预测
│       └── rl/                 # 强化学习
│           ├── environment.py  # 数据中心环境
│           ├── ppo.py          # PPO 策略优化
│           ├── actor_critic.py # Actor-Critic 网络
│           └── agent.py        # RL 智能体
│
├── alembic/                    # 数据库迁移
├── tests/                      # 测试文件
├── scripts/                    # 脚本工具
├── docs/                       # 后端文档
└── requirements.txt            # Python 依赖
```

---

## Proxy 代理服务

```
proxy/
├── server.js                   # Express 反向代理入口
├── package.json                # 依赖: express, http-proxy-middleware, cors
└── node_modules/
```

---

## 统计摘要

| 部分 | 源文件数 | 代码行数 (估算) | 主要语言 |
|------|----------|-----------------|----------|
| **Frontend** | ~160 (.vue/.ts) | ~55,000 | TypeScript / Vue |
| **Backend** | ~120 (.py) | ~30,000 | Python |
| **Proxy** | 1 (.js) | ~80 | JavaScript |
| **合计** | ~280 | ~85,000 | - |

---

*生成工具: BMAD Document Project Workflow v1.2.0*
*最后更新: 2026-02-04*
