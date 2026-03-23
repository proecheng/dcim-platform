# Source Tree — Annotated Structure

**Generated**: 2026-03-23 | **Scan Level**: Exhaustive

---

```
D:\mytest1\                            # Project Root — DCIM 算力中心智能监控系统
│
├── CLAUDE.md                          # Claude Code 项目指南
├── README.md                          # 项目说明
├── CHANGELOG.md                       # 变更日志
├── docker-compose.yml                 # Docker 部署配置
├── package.json                       # Root (Playwright E2E)
├── playwright.config.ts               # E2E 测试配置
├── start.bat / stop.bat               # Windows 一键启动/停止
│
├── backend/                           # ═══ FastAPI Backend (Python) ═══
│   ├── requirements.txt               # Python 依赖
│   ├── alembic.ini                    # Alembic 迁移配置
│   ├── alembic/
│   │   └── versions/                  # 58 个数据库迁移文件
│   │
│   ├── app/
│   │   ├── main.py                    # FastAPI 应用入口 (lifespan, 中间件, 定时任务)
│   │   │
│   │   ├── core/                      # 核心基础设施
│   │   │   ├── config.py              # 配置管理 (@lru_cache 单例)
│   │   │   ├── database.py            # SQLAlchemy 2.0 异步引擎
│   │   │   ├── security.py            # JWT 认证/密码哈希
│   │   │   ├── redis.py               # Redis 连接 (可选)
│   │   │   ├── redis_lock.py          # 分布式锁
│   │   │   ├── cache_headers.py       # HTTP 缓存头
│   │   │   └── logging.py             # 日志配置
│   │   │
│   │   ├── api/
│   │   │   ├── deps.py                # 依赖注入 (get_db, require_viewer/operator/admin)
│   │   │   └── v1/                    # ★ 60 个 API 模块, 836 端点
│   │   │       ├── __init__.py        # 路由注册 (条件加载 ML)
│   │   │       ├── auth.py            # 认证 (8 endpoints)
│   │   │       ├── user.py            # 用户管理 (12)
│   │   │       ├── device.py          # 设备 (11)
│   │   │       ├── point.py           # 点位 (14)
│   │   │       ├── alarm.py           # 告警 (21)
│   │   │       ├── energy.py          # 能源 (97) ★ 最大模块
│   │   │       ├── diagnosis.py       # 诊断 (55)
│   │   │       ├── operation.py       # 运维 (41)
│   │   │       ├── shift.py           # 负荷转移 (32)
│   │   │       ├── capacity.py        # 容量规划 (31)
│   │   │       ├── spatial.py         # 空间管理 (25)
│   │   │       ├── asset.py           # 资产 (25)
│   │   │       ├── precool.py         # 预冷 (21)
│   │   │       ├── video.py           # 视频 (20)
│   │   │       ├── topology.py        # 配电拓扑 (20)
│   │   │       ├── report.py          # 报表 (20)
│   │   │       ├── linkage.py         # 联动 (20)
│   │   │       ├── proposal.py        # 节能提案 (33)
│   │   │       ├── dispatch.py        # 调度 (17)
│   │   │       ├── cooling.py         # 制冷 (16)
│   │   │       ├── datasources.py     # 数据源 (12)
│   │   │       ├── gateways.py        # 网关 (10)
│   │   │       └── ... (40+ more)     # 其余模块
│   │   │
│   │   ├── models/                    # ★ 36 文件, 194 个 ORM 模型
│   │   │   ├── user.py                # User/Role/Session/Site (6 models)
│   │   │   ├── device.py              # Device (1)
│   │   │   ├── point.py               # Point/PointRealtime/Group (4)
│   │   │   ├── alarm.py               # Alarm/Threshold/Rule/Shield/Stats/Escalation (6)
│   │   │   ├── gateway.py             # Gateway/DataSource/Point/Event/OTA/Template (12)
│   │   │   ├── energy.py              # ★ 38 models — 最大模型文件
│   │   │   ├── diagnosis.py           # 20 models — 诊断子系统
│   │   │   ├── operation.py           # WorkOrder/Inspection/Knowledge (7)
│   │   │   ├── load_shift.py          # ShiftPlan/Execution/Constraint/Cooling (8)
│   │   │   ├── asset.py               # Asset/Cabinet/Lifecycle/Inventory (6)
│   │   │   ├── spatial.py             # Site/Floor/Room/Row (5)
│   │   │   ├── capacity.py            # Space/Power/Cooling/Weight Capacity (6)
│   │   │   ├── thermal.py             # ThermalParam/Precool/VPP (4)
│   │   │   ├── topology_config.py     # CoolingZone/Phase/Sensor (6)
│   │   │   ├── fault_tree.py          # FaultTree/Node/Edge/Version (5)
│   │   │   ├── linkage.py             # Policy/Action/Execution/Recovery (6)
│   │   │   ├── history.py             # PointHistory/Archive/ChangeLog (3)
│   │   │   ├── trace.py               # DataSourceMapping/TraceRecord/Tree (4)
│   │   │   ├── video.py               # NVR/Camera/Preset/Event (4)
│   │   │   ├── report.py              # Template/Record/Schedule/HealthScore (5)
│   │   │   └── ... (16 more files)
│   │   │
│   │   ├── schemas/                   # 46 个 Pydantic 请求/响应 Schema 文件
│   │   │
│   │   ├── services/                  # ★ 157 个业务服务文件
│   │   │   ├── websocket.py           # WebSocket 管理器 (3通道)
│   │   │   ├── communication_monitor.py # 通信中断检测
│   │   │   ├── gateway_monitor.py     # 网关健康监控
│   │   │   ├── simulation_service.py  # 数据模拟器
│   │   │   ├── pue_calculator.py      # PUE 计算
│   │   │   ├── forecasting.py         # 预测服务
│   │   │   │
│   │   │   ├── analysis_plugins/      # 6 个分析插件
│   │   │   │   ├── base.py            # 插件基类
│   │   │   │   ├── manager.py         # 插件管理器
│   │   │   │   ├── registry.py        # 插件注册
│   │   │   │   ├── demand_optimization.py
│   │   │   │   ├── equipment_efficiency.py
│   │   │   │   ├── load_shifting.py
│   │   │   │   ├── peak_valley.py
│   │   │   │   ├── power_factor.py
│   │   │   │   └── pue_optimization.py
│   │   │   │
│   │   │   ├── diagnosis/             # 33 个诊断子服务
│   │   │   │   ├── l1_engine.py       # L1 规则引擎
│   │   │   │   ├── l2_inference_engine.py # L2 推理引擎
│   │   │   │   ├── fault_tree.py      # 故障树分析
│   │   │   │   ├── sensor_fusion_service.py # 传感器融合
│   │   │   │   ├── counterfactual_service.py # 反事实分析
│   │   │   │   ├── battery_soh_service.py # 电池SOH
│   │   │   │   └── ... (27 more)
│   │   │   │
│   │   │   ├── load_shift/            # 10 个负荷转移服务
│   │   │   │   ├── algorithms/        # 算法 (constraint_checker, benefit_calculator, opportunity_finder)
│   │   │   │   ├── shift_plan_service.py
│   │   │   │   ├── cooling_linkage_service.py
│   │   │   │   └── ... (7 more)
│   │   │   │
│   │   │   ├── precool/               # 10 个预冷服务
│   │   │   │   ├── thermal_model.py   # TCL 热力学模型
│   │   │   │   ├── scheduler.py       # 预冷调度
│   │   │   │   ├── executor.py        # 执行器
│   │   │   │   └── ... (7 more)
│   │   │   │
│   │   │   ├── predictive_maintenance/ # 10 个预测维护服务
│   │   │   │   ├── health_calculator.py # 健康度计算
│   │   │   │   ├── advisor.py         # 维护建议引擎
│   │   │   │   ├── ups_plugin.py      # UPS 劣化分析
│   │   │   │   ├── pdu_plugin.py      # PDU 劣化分析
│   │   │   │   ├── battery_plugin.py  # 电池 劣化分析
│   │   │   │   └── ... (5 more)
│   │   │   │
│   │   │   ├── notification/          # 4 个通知服务
│   │   │   │   ├── dispatcher.py      # 通知分发
│   │   │   │   ├── policy_service.py  # 策略服务
│   │   │   │   ├── adapters.py        # 渠道适配器
│   │   │   │   └── storm.py           # 告警风暴抑制
│   │   │   │
│   │   │   └── ... (60+ more services)
│   │   │
│   │   ├── engines/                   # 引擎
│   │   │   └── alarm_engine.py        # 告警引擎 (内存缓存+批量)
│   │   │
│   │   ├── ml_models/                 # ML 模型 (可选, 需 torch)
│   │   │
│   │   └── data/                      # 种子数据/初始化数据
│   │
│   └── tests/                         # ★ 203 个测试文件
│       ├── api/                        # API 集成测试
│       ├── services/                   # 服务单元测试
│       └── conftest.py                 # 测试夹具
│
├── frontend/                          # ═══ Vue 3 Frontend (TypeScript) ═══
│   ├── package.json                   # NPM 依赖
│   ├── vite.config.ts                 # Vite 构建配置 (代理 /api → 8080)
│   ├── tsconfig.json                  # TypeScript 配置
│   │
│   └── src/                           # ★ 487 个源文件
│       ├── main.ts                    # 应用入口
│       ├── App.vue                    # 根组件
│       │
│       ├── api/
│       │   ├── request.ts             # Axios 实例 (拦截器/Token注入)
│       │   └── modules/               # ★ 46 个 API 模块
│       │       ├── auth.ts            # 认证接口
│       │       ├── alarm.ts           # 告警接口
│       │       ├── energy.ts          # 能源接口 (最大)
│       │       ├── device.ts          # 设备接口
│       │       └── ... (42 more)
│       │
│       ├── views/                     # ★ 98 个页面视图
│       │   ├── login/                 # 登录页
│       │   ├── dashboard/             # 首页仪表盘
│       │   ├── alarm/                 # 告警管理
│       │   ├── energy/                # 能源管理
│       │   ├── environment/           # 环境监控
│       │   ├── device/                # 设备管理
│       │   ├── operation/             # 运维管理
│       │   ├── diagnosis/             # 智能诊断
│       │   ├── bigscreen/             # 大屏展示
│       │   ├── topology/              # 配电拓扑
│       │   ├── capacity/              # 容量规划
│       │   ├── asset/                 # 资产管理
│       │   ├── power/                 # 电力管理
│       │   ├── video/                 # 视频监控
│       │   ├── vpp/                   # 虚拟电厂
│       │   └── ... (14 more dirs)
│       │
│       ├── components/                # ★ 90 个组件
│       │   ├── common/                # 通用组件 (表格/表单/弹窗)
│       │   ├── charts/                # ECharts 图表封装
│       │   ├── bigscreen/             # 大屏组件 (3D/动画)
│       │   ├── energy/                # 能源图表
│       │   ├── diagnosis/             # 诊断可视化 (故障树/DAG)
│       │   ├── monitor/               # 监控面板
│       │   ├── floor-layouts/         # 楼层布局/机房平面
│       │   └── ... (4 more dirs)
│       │
│       ├── stores/                    # ★ 10 个 Pinia Store
│       │   ├── user.ts                # 用户/认证/Token
│       │   ├── app.ts                 # 应用状态/主题/站点
│       │   ├── alarm.ts               # 告警/活跃列表
│       │   ├── realtime.ts            # WebSocket 实时数据
│       │   ├── energy.ts              # 电力/PUE/汇总
│       │   ├── bigscreen.ts           # 大屏数据
│       │   ├── opportunity.ts         # 节能机会
│       │   ├── degradation.ts         # 设备劣化
│       │   └── site.ts                # 站点管理
│       │
│       ├── composables/               # ★ 38 个组合式函数
│       │   ├── useAlarm.ts            # 告警 WS + 声音
│       │   ├── useRealtime.ts         # 实时数据 WS
│       │   ├── useWebSocketManager.ts # WS 统一管理
│       │   ├── useEnergy.ts           # 能源数据轮询
│       │   ├── useThreeScene.ts       # Three.js 场景
│       │   ├── useBuildingModel.ts    # 3D 建筑模型
│       │   ├── useFaultTreeEditor.ts  # 故障树编辑器
│       │   └── ... (31 more)
│       │
│       ├── router/                    # 路由配置
│       ├── layouts/                   # 布局组件
│       ├── config/                    # 前端配置 (主题)
│       ├── styles/                    # 全局样式 (主题)
│       ├── types/                     # TypeScript 类型定义
│       ├── utils/                     # 工具函数
│       │   └── three/                 # Three.js 工具
│       └── assets/                    # 静态资源
│
├── proxy/                             # ═══ Express Proxy ═══
│   ├── server.js                      # 主服务器 (静态文件 + API/WS 转发)
│   ├── server-alt.js                  # 备用端口版本
│   ├── package.json                   # Express 4.18 依赖
│   └── proxy.log                      # 运行日志
│
├── gateway/                           # ═══ 协议适配器 (编译产物) ═══
│   └── adapters/                      # 8 个协议适配器 (.pyc only)
│       ├── base                       # 适配器基类
│       ├── modbus_tcp                 # Modbus TCP
│       ├── modbus_rtu                 # Modbus RTU
│       ├── snmp                       # SNMP v2c/v3
│       ├── mqtt_device                # MQTT
│       ├── http_rest                  # HTTP REST
│       ├── bacnet_ip                  # BACnet/IP
│       ├── opc_ua                     # OPC UA
│       └── registry                   # 适配器注册表
│
├── docs/                              # ═══ 项目文档 (169 files) ═══
│   ├── project-knowledge/             # 项目知识库
│   ├── project-scan-report.json       # BMAD 扫描状态
│   └── ...
│
├── scripts/                           # 构建/部署脚本
├── deploy/                            # 部署配置
├── e2e/                               # E2E 测试
├── _bmad/                             # BMAD Method 配置
└── _bmad-output/                      # BMAD 工作产出
```

---

## 关键指标汇总

| 类别 | 数量 |
|------|------|
| **后端 API 端点** | 836 |
| **后端 ORM 模型** | 194 |
| **后端服务文件** | 157 |
| **后端测试文件** | 203 |
| **后端 Schema** | 46 |
| **Alembic 迁移** | 58 |
| **前端页面** | 98 |
| **前端组件** | 90 |
| **前端 Store** | 10 |
| **前端 API 模块** | 46 |
| **前端 Composable** | 38 |
| **协议适配器** | 8 |
| **总文档文件** | 169 |
