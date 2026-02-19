# 源码目录树分析

> 本文档由自动化扫描生成，基于对项目全部源码文件的穷举式分析。

## 项目总体结构

```
mytest1/
├── backend/                    # 后端服务 (FastAPI + SQLAlchemy)
│   ├── app/                    # 应用主目录
│   │   ├── api/v1/             # REST API 路由 (47 个模块)
│   │   ├── core/               # 核心配置 (6 个文件)
│   │   ├── models/             # ORM 数据模型 (27 个文件)
│   │   ├── schemas/            # Pydantic 验证模型 (31 个文件)
│   │   ├── services/           # 业务服务层 (60+ 个文件)
│   │   │   └── analysis_plugins/ # 分析插件 (8 个文件)
│   │   ├── engines/            # 引擎层 (7 个文件)
│   │   ├── tools/              # 工具类 (3 个文件)
│   │   ├── data/               # 数据初始化 (2 个文件)
│   │   ├── db/                 # 数据库脚本 (1 个文件)
│   │   ├── utils/              # 工具函数 (2 个文件)
│   │   └── main.py             # 应用入口
│   ├── alembic/                # 数据库迁移
│   ├── tests/                  # 测试用例
│   ├── scripts/                # 脚本工具
│   ├── requirements.txt        # Python 依赖
│   └── Dockerfile              # Docker 构建
├── frontend/                   # 前端应用 (Vue 3 + TypeScript)
│   ├── src/
│   │   ├── api/                # API 调用模块
│   │   │   └── modules/        # 按业务分模块 (30+ 个文件)
│   │   ├── components/         # 组件库 (74 个 Vue 组件)
│   │   │   ├── bigscreen/      # 大屏组件
│   │   │   │   ├── charts/     # 图表组件
│   │   │   │   ├── panels/     # 面板组件
│   │   │   │   └── ui/         # UI 基础组件
│   │   │   ├── charts/         # 通用图表组件
│   │   │   ├── common/         # 公共组件
│   │   │   ├── demand/         # 需量管理组件
│   │   │   ├── energy/         # 能源管理组件
│   │   │   ├── floor-layouts/  # 楼层布局组件
│   │   │   ├── monitor/        # 监控组件
│   │   │   ├── asset/          # 资产组件
│   │   │   └── video/          # 视频组件
│   │   ├── composables/        # 组合式函数
│   │   │   └── bigscreen/      # 大屏专用组合式函数
│   │   ├── config/             # 配置文件
│   │   │   └── themes/         # 主题配置
│   │   ├── layouts/            # 布局组件
│   │   ├── router/             # 路由配置
│   │   ├── stores/             # Pinia 状态管理 (8 个 Store)
│   │   ├── styles/             # 样式文件
│   │   ├── types/              # TypeScript 类型定义
│   │   ├── utils/              # 工具函数
│   │   │   └── three/          # Three.js 工具
│   │   ├── views/              # 页面视图 (60 个 Vue 页面)
│   │   ├── App.vue             # 根组件
│   │   └── main.ts             # 应用入口
│   ├── public/                 # 静态资源
│   ├── dist/                   # 构建产物
│   ├── package.json            # 前端依赖
│   ├── vite.config.ts          # Vite 配置
│   ├── tsconfig.json           # TypeScript 配置
│   └── Dockerfile              # Docker 构建
├── proxy/                      # 代理服务 (Express.js)
│   ├── server.js               # 代理入口 (76 行)
│   └── package.json            # 代理依赖
├── start.bat / start.sh        # 一键启动脚本
├── stop.bat                    # 停止脚本
├── docker-compose.yml          # Docker 编排
├── CLAUDE.md                   # 项目开发指南
├── README.md                   # 项目说明
└── DEPLOY.md                   # 部署指南
```

## 后端目录详解

### backend/app/api/v1/ — API 路由层 (47 个文件)

| 文件 | 路由前缀 | 标签 | 说明 |
|------|----------|------|------|
| auth.py | /auth | 认证 | 登录/登出/刷新令牌 |
| user.py | /users | 用户管理 | 用户 CRUD |
| device.py | /devices | 设备管理 | 设备 CRUD |
| point.py | /points | 点位管理 | 点位 CRUD |
| realtime.py | /realtime | 实时数据 | 实时数据查询 |
| alarm.py | /alarms | 告警管理 | 告警 CRUD/确认/处理 |
| threshold.py | /thresholds | 阈值配置 | 告警阈值管理 |
| history.py | /history | 历史数据 | 历史数据查询/导出 |
| report.py | /reports | 报表 | 报表模板/生成 |
| log.py | /logs | 日志 | 系统日志查询 |
| statistics.py | /statistics | 统计分析 | 统计数据 |
| config.py | /configs | 系统配置 | 系统配置管理 |
| energy.py | /energy | 用电管理 | 能源监控/统计 |
| power.py | /power | 供配电管理 | UPS/电池/配电柜 |
| cooling.py | /cooling | 制冷系统 | 空调/冷通道 |
| regulation.py | /regulation | 负荷调节 | 负荷调节配置 |
| asset.py | (内置) | 资产管理 | 资产台账/机柜 |
| capacity.py | (内置) | 容量管理 | 四维容量监控 |
| operation.py | (内置) | 运维管理 | 工单/巡检/知识库 |
| demo.py | (内置) | 演示数据 | 演示数据管理 |
| floor_map.py | /floor-map | 楼层图 | 楼层平面图 |
| proposal.py | (内置) | 方案管理 | 节能方案 |
| vpp.py | /vpp | VPP方案分析 | 虚拟电厂分析 |
| pricing.py | /pricing | 电价配置 | 电价管理 |
| opportunities.py | /opportunities | 节能机会 | 节能机会检测 |
| execution.py | /execution | 执行管理 | 执行计划管理 |
| demand.py | (内置) | 需量嵌入式API | 需量分析 |
| dispatch.py | /dispatch | 可调度资源配置 | 调度资源管理 |
| monitoring.py | /monitoring | 电费监控 | 电费实时监控 |
| topology.py | /topology | 拓扑编辑 | 配电拓扑 |
| trace.py | (内置) | 数据追溯链 | 数据溯源 |
| optimization.py | /optimization | 日前调度优化 | 调度优化 |
| datasources.py | /datasources | 数据源管理 | 数据源 CRUD |
| gateways.py | /gateways | 网关管理 | 网关 CRUD |
| device_templates.py | /device-templates | 设备模板 | 设备模板管理 |
| system_health.py | /system | 系统 | 系统健康检查 |
| data_quality.py | /data-quality | 数据质量 | 数据质量标记 |
| escalation.py | /escalations | 告警升级 | 告警升级规则 |
| spatial.py | (内置) | 空间拓扑 | 空间层级管理 |
| topology_config.py | /topology-config | 拓扑配置 | 拓扑配置管理 |
| linkage.py | /linkage | 联动管理 | 联动策略/执行 |
| diagnosis.py | /diagnosis | 智能诊断 | 故障诊断 |
| command.py | /command | 控制命令 | 分级确认命令 |
| drift.py | /drift | 漂移检测 | 传感器漂移 |
| video.py | /video | 视频监控 | 摄像头/NVR |
| ml.py | /ml | 深度学习节能优化 | ML 模型 (可选) |
| __init__.py | — | — | 路由注册入口 |

### backend/app/core/ — 核心配置层 (6 个文件)

| 文件 | 说明 |
|------|------|
| config.py | 应用配置 (Pydantic Settings, @lru_cache 单例) |
| database.py | 异步数据库引擎 (SQLAlchemy 2.0 async) |
| security.py | JWT 认证、密码哈希、OAuth2 |
| redis.py | Redis 缓存服务 |
| logging.py | 日志配置 |
| __init__.py | 模块初始化 |

### backend/app/models/ — 数据模型层 (27 个文件, 100+ 个模型)

| 文件 | 主要模型 |
|------|----------|
| user.py | User, RolePermission, UserLoginHistory, UserSession, UserSite, PasswordHistory |
| device.py | Device |
| point.py | Point, PointRealtime, PointGroup, PointGroupMember |
| alarm.py | AlarmThreshold, Alarm, AlarmRule, AlarmShield, AlarmDailyStats, AlarmEscalation |
| history.py | PointHistory, PointHistoryArchive, PointChangeLog |
| log.py | OperationLog, SystemLog, CommunicationLog |
| report.py | ReportTemplate, ReportRecord, ReportSchedule, DeviceHealthScore |
| config.py | SystemConfig, Dictionary, License |
| energy.py | PowerDevice, EnergyHourly/Daily/Monthly, ElectricityPricing, PricingConfig, EnergySuggestion, PUEHistory, EnergyOpportunity, OpportunityMeasure, ExecutionPlan/Task/Result, DispatchableDevice, StorageSystemConfig, PVSystemConfig, DispatchSchedule, RealtimeMonitoring, MonthlyStatistics, OptimizationResult, MeasureBaseline, MonitoringRecord, EffectReport, MonitoringSession, RLOptimizationHistory, RLTrainingLog, RLModelState 等 40+ 模型 |
| asset.py | Cabinet, Asset, AssetLifecycle, MaintenanceRecord, AssetInventory, AssetInventoryItem |
| capacity.py | SpaceCapacity, PowerCapacity, CoolingCapacity, WeightCapacity, CapacityPlan, CapacityHistory |
| operation.py | WorkOrder, WorkOrderLog, InspectionPlan, InspectionTask, KnowledgeBase, AlarmWorkOrderRule, WorkOrderApproval |
| floor_map.py | FloorMap |
| power.py | UPSDevice, BatteryGroup |
| cooling.py | CoolingUnit, CoolingGroup, ColdAisle |
| vpp_data.py | ElectricityBill, LoadCurve, ElectricityPrice, AdjustableLoad, VPPConfig |
| trace.py | DataSourceMapping, TraceRecord, TraceTree, TemplateParameter |
| gateway.py | Gateway, DataSource, DataSourcePoint |
| spatial.py | Site, Floor, Room, Row, LayoutTemplate |
| topology_config.py | PowerPhaseMapping, CoolingZone, CoolingZoneCabinet, CoolingZoneUnit |
| linkage.py | LinkagePolicy, LinkageAction, LinkageExecution, LinkageLog, LinkageRecovery, LinkageRecoveryLog |
| diagnosis.py | DiagnosisRule, DiagnosisResult |
| command.py | CommandApproval, CommandAuditLog |
| drift.py | DriftDetectionResult |
| video.py | NVR, Camera, CameraPreset, VideoEvent |
| system.py | 系统级模型 |

### backend/app/engines/ — 引擎层 (7 个文件)

| 文件 | 说明 |
|------|------|
| alarm_engine.py | 告警引擎 — 阈值缓存、告警触发 |
| linkage_engine.py | 联动引擎 — 策略缓存、事件响应 |
| escalation_engine.py | 告警升级引擎 — 定时检查升级 |
| diagnosis_engine.py | 诊断引擎 — 规则加载、故障诊断 |
| event_bus.py | 事件总线 — 发布/订阅模式 |
| cross_confirmation.py | 交叉确认服务 — 消防联动确认 |
| recovery_engine.py | 恢复引擎 — 联动恢复流程 |
| action_handlers.py | 动作处理器 — 联动动作执行 |

### backend/app/services/ — 业务服务层 (60+ 个文件)

主要服务分类：

| 分类 | 文件 | 说明 |
|------|------|------|
| 数据采集 | simulator.py, collector.py | 数据模拟器、采集器 |
| WebSocket | websocket.py | WS 连接管理 |
| 能源分析 | energy_analysis.py, energy_aggregator.py, pue_calculator.py | 能源分析、聚合、PUE 计算 |
| 能源报告 | energy_report_service.py, energy_report_excel.py, energy_report_pdf.py | 报告生成 (Excel/PDF) |
| 节能优化 | opportunity_detector.py, opportunity_engine.py, effect_tracker.py | 节能机会检测、效果追踪 |
| 执行管理 | execution_service.py, proposal_executor.py | 方案执行 |
| 负荷调节 | load_regulation.py, device_regulation_service.py | 负荷调节 |
| 设备管理 | power_device.py, device_control_service.py, device_selector_service.py | 设备控制 |
| 拓扑管理 | energy_topology.py, topology_sync.py | 配电拓扑 |
| 数据追溯 | data_trace_service.py, traced_formula_calculator.py | 数据溯源 |
| 网关管理 | gateway_registration.py, gateway_monitor.py, connection_test.py | 网关注册/监控 |
| 通信监控 | communication_monitor.py | 通信中断检测 |
| 消防策略 | fire_protection.py | 消防联动策略 |
| 诊断加载 | diagnosis_loader.py | 诊断规则加载 |
| 漂移检测 | drift_detection.py | 传感器漂移检测 |
| 视频服务 | video_service.py | 视频监控服务 |
| ML 服务 | ml_service.py, ml_template_generator.py, ml_traced_calculator.py | 机器学习 |
| 其他 | cache_service.py, config_push.py, pricing_service.py, vpp_calculator.py 等 | 缓存/配置/VPP |

### backend/app/services/analysis_plugins/ — 分析插件 (8 个文件)

| 文件 | 说明 |
|------|------|
| base.py | 插件基类 |
| registry.py | 插件注册表 |
| manager.py | 插件管理器 |
| peak_valley.py | 峰谷电价优化 |
| load_shifting.py | 负荷转移 |
| equipment_efficiency.py | 设备效率分析 |
| pue_optimization.py | PUE 优化 |
| power_factor.py | 功率因数优化 |
| demand_optimization.py | 需量优化 |

## 前端目录详解

### frontend/src/stores/ — Pinia 状态管理 (8 个 Store)

| 文件 | Store 名称 | 主要状态 |
|------|-----------|----------|
| user.ts | user | token, userInfo, permissions |
| app.ts | app | sidebarCollapsed, theme, language, alarmSoundEnabled |
| alarm.ts | alarm | activeAlarms, alarmCount, soundEnabled |
| realtime.ts | realtime | dataMap, summary, lastUpdateTime, wsConnected |
| energy.ts | energy | realtimePowerData, powerSummary, pueData, suggestions |
| bigscreen.ts | bigscreen | mode, layout, deviceData, layers, selectedDeviceId |
| opportunity.ts | opportunity | dashboard, opportunities, executionPlans, executionStats |
| degradation.ts | degradation | redisDown, websocketDown, mqttDown, degradedMessage |

### frontend/src/views/ — 页面视图 (60 个 Vue 页面)

按功能域分类：

| 域 | 页面 | 路由 |
|----|------|------|
| 登录 | login/index.vue | /login |
| 仪表盘 | dashboard/index.vue | /dashboard |
| 大屏 | bigscreen/index.vue | /bigscreen |
| 供配电 | power/overview.vue, ups.vue, battery.vue, cabinet.vue, pdu.vue | /power/* |
| 制冷 | cooling/overview.vue, indoor.vue, outdoor.vue, cold-aisle.vue, group-control.vue | /cooling/* |
| 环境 | environment/overview.vue | /environment/overview |
| 安防 | security/overview.vue | /security/overview |
| 能源 | energy/monitor.vue, statistics.vue, config.vue, topology.vue, analysis.vue, regulation.vue, execution.vue, report.vue, suggestions.vue | /power/*, /energy-saving/* |
| 告警 | alarm/index.vue | /alarms |
| 历史 | history/index.vue | /history |
| 报表 | report/index.vue | /reports |
| 设备 | device/index.vue, device-manage/index.vue, device-manage/detail.vue, device-status/index.vue, device-template/index.vue | /devices, /device-manage/*, /device-status, /device-templates |
| 数据源 | datasource/index.vue | /datasources |
| 资产 | asset/index.vue, asset/cabinet.vue | /infrastructure/asset, /infrastructure/cabinet |
| 容量 | capacity/index.vue | /infrastructure/capacity |
| 拓扑 | topology/spatial.vue, power.vue, cooling.vue, site-selection.vue, fault-impact.vue | /infrastructure/* |
| 运维 | operation/workorder.vue, inspection.vue, knowledge.vue | /operation/* |
| VPP | vpp/VPPAnalysis.vue | /vpp/analysis |
| 联动 | linkage/policy.vue, execution.vue, recovery.vue, timeline.vue, command.vue, drift.vue | /linkage/* |
| 诊断 | diagnosis/results.vue, rules.vue | /diagnosis/* |
| 视频 | video/index.vue, control.vue, playback.vue | /video/* |
| 系统 | system/user.vue, audit-log.vue | /system/* |
| 设置 | settings/index.vue, UserManagement.vue | /settings |

### frontend/src/components/ — 组件库 (74 个 Vue 组件)

| 分类 | 组件数 | 主要组件 |
|------|--------|----------|
| common/ | 8 | DataTable, SearchForm, ConfirmDialog, DateRangePicker, ExportButton, StatusTag, AlarmSoundToggle, DataQualityTag, DegradationBanner |
| charts/ | 6 | LineChart, BarChart, PieChart, GaugeChart, RealtimeChart, Sparkline |
| monitor/ | 4 | PointCard, ValueDisplay, StatusPanel, AlarmBadge |
| energy/ | 20 | PUEGauge, PowerCard, CostCard, DeviceList, SuggestionsCard, CalculationDetails, ShiftPlanBuilder, DemandDashboard, ScheduleDashboard, DispatchConfig, OptimizationReport 等 |
| bigscreen/ | 16 | ThreeScene, DataCenterModel, Floor2DView, FloorSelector, HeatmapOverlay, AlarmBubbles, CabinetLabels, DeviceDetailPanel + charts/ + panels/ + ui/ |
| floor-layouts/ | 5 | FloorLayoutBase, FloorLayoutSelector, FloorF1-F3Layout, FloorB1Layout |
| demand/ | 3 | LoadPeriodChart, DemandComparisonCard, DemandCurveMini |
| asset/ | 1 | LifecycleTimeline |
| video/ | 1 | VideoPopup |
| 根级 | 2 | MetricDisplay, DemoDataLoader |

## 代理服务目录

### proxy/ — Express 代理 (3 个文件)

| 文件 | 说明 |
|------|------|
| server.js | 代理服务入口 (76 行) — 静态文件服务 + API/WS 转发 |
| package.json | 依赖: express, http-proxy-middleware, cors |
| pnpm-lock.yaml | 锁定文件 |

## 文件统计

| 部分 | 源码文件数 | 主要语言 |
|------|-----------|----------|
| 后端 (backend/app/) | ~130+ | Python |
| 前端 (frontend/src/) | ~200+ | Vue/TypeScript |
| 代理 (proxy/) | 1 | JavaScript |
| 总计 | ~330+ | — |
