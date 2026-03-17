# 源代码目录结构分析

生成时间: 2026-03-17
项目版本: V4.2.0

## 仓库类型

多部件项目 (Multi-part)，包含 3 个独立服务：

| 部件 | 类型 | 技术栈 | 根目录 |
|------|------|--------|--------|
| backend | FastAPI 后端 | Python 3.11 | `backend/` |
| frontend | Vue 3 前端 | TypeScript 5.9 | `frontend/` |
| proxy | Express 代理 | Node.js | `proxy/` |

## 完整目录树

```
D:\mytest1\
├── backend/                          # FastAPI 后端服务
│   ├── app/                          # 应用主目录
│   │   ├── api/v1/                   # REST API 路由 (57 个模块, 300+ 端点)
│   │   │   ├── __init__.py           # 路由注册中心
│   │   │   ├── auth.py              # 认证 (登录/登出/刷新/密码)
│   │   │   ├── users.py             # 用户管理 (CRUD/批量/站点权限)
│   │   │   ├── devices.py           # 设备管理 (树/状态/详情)
│   │   │   ├── points.py            # 点位管理 (导入导出/分组)
│   │   │   ├── realtime.py          # 实时数据 (按类型/区域/控制)
│   │   │   ├── alarms.py            # 告警管理 (规则/屏蔽/升级)
│   │   │   ├── thresholds.py        # 阈值配置 (4级/批量/复制)
│   │   │   ├── history.py           # 历史数据 (趋势/统计/对比)
│   │   │   ├── energy.py            # 能源管理 (PUE/建议/拓扑)
│   │   │   ├── cooling.py           # 制冷系统 (空调/群控/冷通道)
│   │   │   ├── power.py             # 供配电 (UPS/电池/冗余)
│   │   │   ├── diagnosis.py          # 智能诊断 (规则/结果/注释)
│   │   │   ├── fault_tree.py         # 故障树 (CRUD/版本/图形编辑)
│   │   │   ├── fault_tree_version.py # 故障树版本管理
│   │   │   ├── sensor_metadata.py    # 传感器元数据
│   │   │   ├── probability_tuning.py # 概率调参
│   │   │   ├── ab_testing.py         # A/B 测试
│   │   │   ├── misdiagnosis_reports.py # 误诊分析报告
│   │   │   ├── disaster_recovery.py  # 灾难恢复演练
│   │   │   ├── hmac_key_management.py # HMAC 密钥管理
│   │   │   ├── counterfactual.py     # 反事实分析
│   │   │   ├── time_window.py        # 时间窗口自适应
│   │   │   ├── training_data_audit.py # 训练数据审计
│   │   │   ├── shift.py              # 负荷转移 (计划/机会/分析)
│   │   │   ├── precool.py            # 预冷系统 (配置/执行/历史)
│   │   │   ├── thermal.py            # 热力学 (温度预测/参数)
│   │   │   ├── rollback.py           # 安全回退 (状态/日志)
│   │   │   ├── deployment_phase.py   # 分阶段部署
│   │   │   ├── vpp.py                # VPP 虚拟电厂
│   │   │   ├── regulation.py         # 负荷调节
│   │   │   ├── optimization.py       # 日前调度优化
│   │   │   ├── spatial.py            # 空间管理 (站点/楼层/机房)
│   │   │   ├── topology.py           # 拓扑编辑
│   │   │   ├── topology_config.py    # 拓扑配置
│   │   │   ├── linkage.py            # 联动引擎
│   │   │   ├── reports.py            # 报表 (模板/生成/调度)
│   │   │   ├── logs.py               # 日志 (操作/系统/通讯)
│   │   │   ├── configs.py            # 系统配置
│   │   │   ├── statistics.py         # 统计分析
│   │   │   ├── gateways.py           # 网关管理
│   │   │   ├── datasources.py        # 数据源管理
│   │   │   ├── device_templates.py   # 设备模板
│   │   │   ├── asset.py              # 资产管理
│   │   │   ├── capacity.py           # 容量管理
│   │   │   ├── operation.py          # 运维管理
│   │   │   ├── video.py              # 视频监控
│   │   │   ├── command.py            # 控制命令
│   │   │   ├── drift.py              # 漂移检测
│   │   │   ├── ota.py                # OTA 升级
│   │   │   ├── floor_map.py          # 楼层图
│   │   │   ├── data_quality.py       # 数据质量
│   │   │   ├── trace.py              # 数据追溯
│   │   │   ├── demand.py             # 需量管理
│   │   │   ├── dispatch.py           # 可调度资源
│   │   │   ├── monitoring.py         # 电费监控
│   │   │   ├── pricing.py            # 电价配置
│   │   │   ├── opportunities.py      # 节能机会
│   │   │   ├── execution.py          # 执行管理
│   │   │   └── ml.py                 # 深度学习 (可选, 需 torch)
│   │   ├── models/                   # SQLAlchemy ORM 模型 (34 文件, 120+ 模型)
│   │   │   ├── user.py               # User, RolePermission, UserSession 等
│   │   │   ├── device.py             # Device
│   │   │   ├── point.py              # Point, PointRealtime, PointGroup
│   │   │   ├── alarm.py              # Alarm, AlarmThreshold, AlarmRule 等
│   │   │   ├── history.py            # PointHistory, PointHistoryArchive
│   │   │   ├── log.py                # OperationLog, SystemLog
│   │   │   ├── config.py             # SystemConfig, Dictionary, License
│   │   │   ├── energy.py             # Transformer, EnergyHourly 等 (30+ 模型)
│   │   │   ├── asset.py              # Cabinet, Asset, AssetLifecycle
│   │   │   ├── capacity.py           # SpaceCapacity, PowerCapacity 等
│   │   │   ├── operation.py          # WorkOrder, InspectionPlan, KnowledgeBase
│   │   │   ├── report.py             # ReportTemplate, ReportRecord
│   │   │   ├── cooling.py            # CoolingGroup, CoolingUnit, ColdAisle
│   │   │   ├── power.py              # UPSDevice, BatteryGroup
│   │   │   ├── spatial.py            # Site, Floor, Room, Row
│   │   │   ├── topology_config.py    # CoolingZone, CabinetTemperatureSensor
│   │   │   ├── linkage.py            # LinkagePolicy, LinkageExecution
│   │   │   ├── diagnosis.py          # DiagnosisRule, DiagnosisResult 等
│   │   │   ├── fault_tree.py         # FaultTree, FaultTreeNode, FaultTreeVersion
│   │   │   ├── gateway.py            # Gateway, DataSource
│   │   │   ├── trace.py              # DataSourceMapping, TraceRecord
│   │   │   ├── command.py            # CommandApproval, CommandAuditLog
│   │   │   ├── floor_map.py          # FloorMap
│   │   │   └── enums.py              # 枚举定义
│   │   ├── services/                 # 业务服务层 (147 文件)
│   │   │   ├── auth_service.py       # 认证服务
│   │   │   ├── user_service.py       # 用户服务
│   │   │   ├── device_service.py     # 设备服务
│   │   │   ├── point_service.py      # 点位服务
│   │   │   ├── realtime_service.py   # 实时数据服务
│   │   │   ├── alarm_service.py      # 告警服务
│   │   │   ├── energy_service.py     # 能源服务
│   │   │   ├── cooling_service.py    # 制冷服务
│   │   │   ├── cooling_linkage_service.py # 制冷联动服务
│   │   │   ├── diagnosis_service.py  # 诊断服务
│   │   │   ├── diagnosis_scheduler.py # 诊断调度器
│   │   │   ├── fault_tree_service.py # 故障树服务
│   │   │   ├── l1_rule_engine.py     # L1 规则引擎
│   │   │   ├── l2_fault_tree_engine.py # L2 故障树推理引擎
│   │   │   ├── circuit_breaker.py    # 熔断器
│   │   │   ├── constraint_checker.py # 约束检查器 (RC 热力学)
│   │   │   ├── rc_thermal_model.py   # RC 热力学模型核心
│   │   │   ├── temperature_headroom.py # 温度裕度安全兜底
│   │   │   ├── rollback_protection.py # 7 种自动回退保护
│   │   │   ├── precooling_scheduler.py # 贪心预冷调度
│   │   │   ├── precooling_executor.py # 预冷执行引擎
│   │   │   ├── rc_calibration.py     # RC 参数最小二乘校准
│   │   │   ├── deployment_phase_service.py # 分阶段部署
│   │   │   ├── vpp_capacity_reporter.py # VPP 容量上报
│   │   │   ├── vpp_command_executor.py # VPP 指令执行
│   │   │   ├── datacenter_shift_strategy.py # 负荷转移策略
│   │   │   ├── shift_plan_service.py # 转移计划服务
│   │   │   ├── linkage_engine.py     # 联动引擎
│   │   │   ├── report_service.py     # 报表服务
│   │   │   ├── websocket_manager.py  # WebSocket 管理
│   │   │   ├── data_simulator.py     # 数据模拟器
│   │   │   ├── analysis_plugins/     # 6 种分析插件
│   │   │   └── ...                   # 更多服务
│   │   ├── schemas/                  # Pydantic Schema (请求/响应模型)
│   │   ├── core/                     # 核心模块
│   │   │   ├── config.py             # 配置单例 (@lru_cache)
│   │   │   ├── database.py           # 异步数据库引擎
│   │   │   ├── security.py           # JWT/密码/RBAC
│   │   │   └── deps.py               # 依赖注入
│   │   ├── middleware/               # 中间件
│   │   ├── engines/                  # 数据处理引擎
│   │   ├── demo/                     # Demo 数据生成/种子
│   │   ├── db/                       # 数据库初始化
│   │   ├── ml_models/               # 机器学习模型 (可选)
│   │   └── main.py                   # FastAPI 应用入口
│   ├── alembic/                      # 数据库迁移
│   │   ├── env.py                    # 迁移环境配置
│   │   └── versions/                 # 54 个迁移版本
│   ├── tests/                        # 测试套件 (195 文件)
│   │   ├── api/                      # API 端点测试
│   │   ├── services/                 # 服务层测试
│   │   └── conftest.py               # 测试 fixtures
│   ├── requirements.txt              # Python 依赖 (71 包)
│   ├── Dockerfile                    # 多阶段构建
│   └── alembic.ini                   # Alembic 配置
│
├── frontend/                         # Vue 3 前端服务
│   ├── src/
│   │   ├── api/modules/              # API 模块 (45 个)
│   │   │   ├── auth.ts               # 认证 API
│   │   │   ├── realtime.ts           # 实时数据 API
│   │   │   ├── alarm.ts              # 告警 API
│   │   │   ├── energy.ts             # 能源 API
│   │   │   ├── shift.ts              # 负荷转移 API
│   │   │   ├── precool.ts            # 预冷 API
│   │   │   ├── diagnosis.ts          # 诊断 API
│   │   │   └── ...                   # 更多模块
│   │   ├── views/                    # 页面视图 (97 个)
│   │   │   ├── dashboard/            # 总览仪表盘
│   │   │   ├── energy/               # 能源管理页面
│   │   │   ├── alarm/                # 告警管理页面
│   │   │   ├── asset/                # 资产管理页面
│   │   │   ├── operation/            # 运维管理页面
│   │   │   ├── collection/           # 采集配置页面
│   │   │   ├── strategy/             # 策略配置页面
│   │   │   ├── system/               # 系统管理页面
│   │   │   ├── bigscreen/            # 大屏展示
│   │   │   └── login/                # 登录页
│   │   ├── components/               # 可复用组件 (101 个)
│   │   │   ├── common/               # 通用组件
│   │   │   ├── charts/               # ECharts 图表组件
│   │   │   ├── energy/               # 能源专用组件
│   │   │   ├── bigscreen/            # 大屏专用组件
│   │   │   ├── diagnosis/            # 诊断专用组件
│   │   │   └── asset/                # 资产专用组件
│   │   ├── stores/                   # Pinia 状态管理 (8 个)
│   │   │   ├── user.ts               # 用户状态
│   │   │   ├── app.ts                # 应用状态
│   │   │   ├── alarm.ts              # 告警状态
│   │   │   ├── realtime.ts           # 实时数据状态
│   │   │   ├── energy.ts             # 能源状态
│   │   │   ├── bigscreen.ts          # 大屏状态
│   │   │   ├── opportunity.ts        # 节能机会状态
│   │   │   ├── degradation.ts        # 降级状态
│   │   │   └── site.ts               # 站点状态
│   │   ├── composables/              # 组合式函数
│   │   ├── router/index.ts           # 路由配置 (68 条路由)
│   │   ├── assets/                   # 静态资源
│   │   └── App.vue                   # 根组件
│   ├── public/                       # 公共静态文件
│   ├── dist/                         # 构建输出
│   ├── package.json                  # NPM 依赖 (38 包)
│   ├── vite.config.ts                # Vite 构建配置
│   ├── tsconfig.json                 # TypeScript 配置
│   └── Dockerfile                    # 多阶段构建 (Nginx)
│
├── proxy/                            # Express 代理服务
│   ├── server.js                     # 代理入口
│   └── package.json                  # 3 个核心依赖
│
├── docs/                             # 项目文档 (168+ 文件)
│   ├── index.md                      # 文档索引
│   └── project-knowledge/            # 项目知识库
│
├── deploy/                           # 部署配置
│   └── nginx/                        # Nginx 配置
│
├── docker-compose.yml                # 5 服务编排
├── start.bat                         # Windows 一键启动
├── stop.bat                          # Windows 一键停止
├── CLAUDE.md                         # AI 开发指南
└── README.md                         # 项目说明
```

## 关键目录说明

| 目录 | 文件数 | 说明 |
|------|--------|------|
| `backend/app/api/v1/` | 57 | REST API 路由，每个文件对应一个功能模块 |
| `backend/app/models/` | 34 | ORM 模型定义，120+ 数据表 |
| `backend/app/services/` | 147 | 业务逻辑层，核心算法实现 |
| `backend/app/core/` | 4 | 配置、数据库、安全、依赖注入 |
| `backend/tests/` | 195 | pytest 测试套件 |
| `backend/alembic/versions/` | 54 | 数据库迁移脚本 |
| `frontend/src/views/` | 97 | Vue 页面组件 |
| `frontend/src/components/` | 101 | 可复用 Vue 组件 |
| `frontend/src/stores/` | 8 | Pinia 状态管理 |
| `frontend/src/api/modules/` | 45 | API 调用封装 |

## 入口点

| 入口 | 文件 | 说明 |
|------|------|------|
| 后端应用 | `backend/app/main.py` | FastAPI app 实例，中间件注册，路由挂载 |
| 前端应用 | `frontend/src/main.ts` | Vue app 创建，插件注册 |
| 代理服务 | `proxy/server.js` | Express 静态文件 + API 转发 |
| 数据库迁移 | `backend/alembic/env.py` | Alembic 异步迁移环境 |
