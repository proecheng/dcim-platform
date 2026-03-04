# 源代码目录结构分析

生成时间: 2026-03-01  
项目版本: V3.2.1

## 概述

DCIM (算力中心智能监控系统) 是一个全栈 Web 应用，采用前后端分离架构。项目包含前端 (Vue 3)、后端 (FastAPI)、代理服务器 (Express) 和完整的测试、部署配置。

## 项目根目录结构

```
dcim/
├── backend/                 # 后端服务 (FastAPI + Python)
├── frontend/                # 前端应用 (Vue 3 + TypeScript)
├── proxy/                   # 生产环境代理服务器 (Express)
├── docs/                    # 项目文档
├── tests/                   # E2E 测试
├── deploy/                  # 部署配置
├── scripts/                 # 工具脚本
├── _bmad/                   # BMAD 工作流配置
├── .github/                 # GitHub Actions CI/CD
├── docker-compose.yml       # Docker 编排配置
├── start.bat / start.sh     # 一键启动脚本
├── stop.bat                 # 停止服务脚本
└── README.md                # 项目说明
```

## 后端目录结构 (backend/)

### 核心应用代码 (backend/app/)

```
app/
├── api/                     # API 路由层
│   └── v1/                  # API v1 版本 (48 个模块)
│       ├── auth.py          # 认证 (登录/登出/刷新令牌)
│       ├── user.py          # 用户管理
│       ├── device.py        # 设备管理
│       ├── point.py         # 点位管理
│       ├── realtime.py      # 实时数据
│       ├── alarm.py         # 告警管理
│       ├── threshold.py     # 阈值配置
│       ├── history.py       # 历史数据
│       ├── energy.py        # 能源管理
│       ├── asset.py         # 资产管理
│       ├── capacity.py      # 容量管理
│       ├── topology.py      # 拓扑管理
│       ├── linkage.py       # 联动引擎
│       ├── video.py         # 视频监控
│       ├── operation.py     # 运维管理 (工单/巡检/知识库)
│       ├── report.py        # 报表管理
│       ├── gateways.py      # 网关管理
│       ├── datasources.py   # 数据源管理
│       ├── device_templates.py  # 设备模板
│       ├── cooling.py       # 制冷系统
│       ├── power.py         # 供配电系统
│       ├── monitoring.py    # 监控仪表盘
│       ├── opportunities.py # 节能机会
│       ├── optimization.py  # 节能优化
│       ├── pricing.py       # 电价管理
│       ├── demand.py        # 需量管理
│       ├── proposal.py      # 优化方案
│       ├── execution.py     # 执行追踪
│       ├── regulation.py    # 调节控制
│       ├── diagnosis.py     # 智能诊断
│       ├── trace.py         # 事件追踪
│       ├── escalation.py    # 告警升级
│       ├── data_quality.py  # 数据质量
│       ├── drift.py         # 数据漂移检测
│       ├── command.py       # 控制命令
│       ├── spatial.py       # 空间管理
│       ├── floor_map.py     # 楼层地图
│       ├── topology_config.py  # 拓扑配置
│       ├── system_health.py # 系统健康
│       ├── dispatch.py      # 调度优化
│       ├── vpp.py           # 虚拟电厂
│       ├── ota.py           # OTA 升级
│       ├── ml.py            # 机器学习 (可选)
│       ├── config.py        # 系统配置
│       ├── log.py           # 日志管理
│       └── statistics.py    # 统计分析
│
├── models/                  # 数据模型层 (SQLAlchemy ORM, 29 个文件)
│   ├── user.py              # 用户模型
│   ├── device.py            # 设备模型
│   ├── point.py             # 点位模型
│   ├── history.py           # 历史数据模型
│   ├── alarm.py             # 告警模型
│   ├── energy.py            # 能源模型
│   ├── asset.py             # 资产模型
│   ├── capacity.py          # 容量模型
│   ├── topology_config.py   # 拓扑配置模型
│   ├── linkage.py           # 联动模型
│   ├── video.py             # 视频模型
│   ├── operation.py         # 运维模型
│   ├── report.py            # 报表模型
│   ├── gateway.py           # 网关模型
│   ├── cooling.py           # 制冷模型
│   ├── power.py             # 供配电模型
│   ├── diagnosis.py         # 诊断模型
│   ├── trace.py             # 追踪模型
│   ├── drift.py             # 漂移检测模型
│   ├── command.py           # 命令模型
│   ├── spatial.py           # 空间模型
│   ├── floor_map.py         # 楼层地图模型
│   ├── system.py            # 系统模型
│   ├── vpp_data.py          # 虚拟电厂数据模型
│   ├── config.py            # 配置模型
│   └── log.py               # 日志模型
│
├── schemas/                 # Pydantic Schema (请求/响应验证)
│   ├── user.py
│   ├── device.py
│   ├── point.py
│   ├── alarm.py
│   ├── energy.py
│   └── ...                  # 与 models 对应
│
├── services/                # 业务逻辑层
│   ├── analysis_plugins/    # 节能分析插件 (6 种)
│   │   ├── peak_valley.py   # 峰谷套利
│   │   ├── demand_opt.py    # 需量优化
│   │   ├── pue_opt.py       # PUE 优化
│   │   ├── cooling_opt.py   # 制冷优化
│   │   ├── load_balance.py  # 负载均衡
│   │   └── renewable.py     # 可再生能源
│   ├── device_sync.py       # 设备同步服务
│   ├── alarm_service.py     # 告警服务
│   ├── energy_service.py    # 能源服务
│   ├── capacity_service.py  # 容量服务
│   ├── linkage_service.py   # 联动服务
│   ├── diagnosis_service.py # 诊断服务
│   └── ...
│
├── core/                    # 核心配置
│   ├── config.py            # 配置管理 (Settings)
│   ├── database.py          # 数据库连接 (异步)
│   ├── security.py          # 安全 (JWT/密码哈希)
│   └── deps.py              # 依赖注入
│
├── middleware/              # 中间件
│   ├── auth.py              # 认证中间件
│   └── logging.py           # 日志中间件
│
├── engines/                 # 引擎模块
│   ├── linkage/             # 联动引擎
│   └── diagnosis/           # 诊断引擎
│
├── ml_models/               # 机器学习模型 (可选)
│   ├── load_predictor.py    # 负载预测
│   └── anomaly_detector.py  # 异常检测
│
├── mqtt/                    # MQTT 客户端
│   └── client.py
│
├── utils/                   # 工具函数
│   ├── websocket.py         # WebSocket 管理
│   └── simulator.py         # 数据模拟器
│
└── main.py                  # FastAPI 应用入口
```

### 数据库迁移 (backend/alembic/)

```
alembic/
├── versions/                # 迁移脚本
│   ├── 001_initial.py
│   ├── 002_add_energy.py
│   └── ...
└── env.py                   # Alembic 配置
```

### 测试 (backend/tests/)

```
tests/
├── api/                     # API 测试 (1350+ 用例)
│   ├── test_auth.py
│   ├── test_device.py
│   ├── test_alarm.py
│   ├── test_energy.py
│   └── ...
├── services/                # 服务层测试
│   ├── test_device_sync.py
│   ├── test_alarm_service.py
│   └── ...
├── models/                  # 模型测试
└── conftest.py              # pytest 配置
```

### 网关 (backend/gateway/)

```
gateway/
├── adapters/                # 协议适配器
│   ├── modbus_adapter.py    # Modbus TCP/RTU
│   ├── snmp_adapter.py      # SNMP v2c/v3
│   ├── mqtt_adapter.py      # MQTT
│   ├── http_adapter.py      # HTTP/REST
│   ├── bacnet_adapter.py    # BACnet/IP
│   └── opcua_adapter.py     # OPC-UA
├── core/                    # 网关核心
│   ├── gateway_manager.py   # 网关管理器
│   └── data_buffer.py       # 数据缓冲
└── requirements.txt         # 网关依赖
```

## 前端目录结构 (frontend/)

### 核心应用代码 (frontend/src/)

```
src/
├── api/                     # API 客户端
│   ├── index.ts             # Axios 实例配置
│   └── modules/             # API 模块 (按功能分组)
│       ├── auth.ts
│       ├── device.ts
│       ├── alarm.ts
│       ├── energy.ts
│       ├── asset.ts
│       └── ...
│
├── views/                   # 页面视图 (28 个目录)
│   ├── login/               # 登录页
│   ├── dashboard/           # 仪表盘
│   ├── device/              # 设备管理
│   ├── device-status/       # 设备状态
│   ├── device-manage/       # 设备配置
│   ├── device-template/     # 设备模板
│   ├── alarm/               # 告警管理
│   ├── history/             # 历史数据
│   ├── energy/              # 能源管理
│   ├── asset/               # 资产管理
│   ├── capacity/            # 容量管理
│   ├── topology/            # 拓扑管理
│   ├── linkage/             # 联动引擎
│   ├── video/               # 视频监控
│   ├── operation/           # 运维管理
│   ├── report/              # 报表管理
│   ├── gateway/             # 网关管理
│   ├── datasource/          # 数据源管理
│   ├── cooling/             # 制冷系统
│   ├── power/               # 供配电系统
│   ├── environment/         # 环境监控
│   ├── security/            # 安防消防
│   ├── diagnosis/           # 智能诊断
│   ├── vpp/                 # 虚拟电厂
│   ├── system/              # 系统管理
│   ├── settings/            # 系统设置
│   ├── bigscreen/           # 大屏展示
│   └── common/              # 通用页面 (404/403)
│
├── components/              # 组件库 (12 个目录)
│   ├── common/              # 通用组件
│   │   ├── PageHeader.vue
│   │   ├── DataTable.vue
│   │   ├── SearchForm.vue
│   │   └── ...
│   ├── charts/              # 图表组件
│   │   ├── LineChart.vue
│   │   ├── BarChart.vue
│   │   ├── PieChart.vue
│   │   ├── GaugeChart.vue
│   │   └── ...
│   ├── energy/              # 能源组件
│   │   ├── PUEChart.vue
│   │   ├── PowerTopology.vue
│   │   └── ...
│   ├── bigscreen/           # 大屏组件
│   │   ├── ScreenHeader.vue
│   │   ├── DataPanel.vue
│   │   └── ...
│   ├── asset/               # 资产组件
│   │   ├── CabinetView.vue
│   │   └── ...
│   ├── monitor/             # 监控组件
│   ├── video/               # 视频组件
│   ├── demand/              # 需量组件
│   ├── proposal/            # 方案组件
│   ├── floor-layouts/       # 楼层布局组件
│   ├── DemoDataLoader.vue   # 演示数据加载器
│   └── MetricDisplay.vue    # 指标展示
│
├── stores/                  # Pinia 状态管理
│   ├── user.ts              # 用户状态
│   ├── app.ts               # 应用状态
│   ├── alarm.ts             # 告警状态
│   ├── realtime.ts          # 实时数据状态
│   ├── energy.ts            # 能源状态
│   ├── opportunity.ts       # 节能机会状态
│   └── bigscreen.ts         # 大屏状态
│
├── composables/             # 组合式函数
│   ├── useWebSocket.ts      # WebSocket 连接
│   ├── useAlarm.ts          # 告警处理
│   ├── useChart.ts          # 图表配置
│   └── ...
│
├── router/                  # 路由配置
│   ├── index.ts             # 路由定义
│   └── guards.ts            # 路由守卫
│
├── layouts/                 # 布局组件
│   ├── MainLayout.vue       # 主布局
│   └── BigscreenLayout.vue  # 大屏布局
│
├── styles/                  # 样式文件
│   ├── variables.scss       # SCSS 变量
│   ├── mixins.scss          # SCSS Mixin (2.5D 效果)
│   └── global.scss          # 全局样式
│
├── types/                   # TypeScript 类型定义
│   ├── api.ts
│   ├── device.ts
│   ├── alarm.ts
│   └── ...
│
├── utils/                   # 工具函数
│   ├── request.ts           # HTTP 请求封装
│   ├── format.ts            # 格式化工具
│   └── ...
│
├── config/                  # 配置文件
│   └── constants.ts         # 常量定义
│
├── assets/                  # 静态资源
│   ├── images/
│   ├── icons/
│   └── fonts/
│
├── App.vue                  # 根组件
└── main.ts                  # 应用入口
```

### 测试 (frontend/src/__tests__/)

```
__tests__/
├── components/              # 组件测试 (1182 用例)
│   ├── common/
│   ├── charts/
│   └── ...
├── stores/                  # 状态管理测试
├── composables/             # 组合式函数测试
└── utils/                   # 工具函数测试
```

## 代理服务器 (proxy/)

```
proxy/
├── server.js                # Express 服务器
├── package.json
└── README.md
```

## 文档 (docs/)

```
docs/
├── project-knowledge/       # 项目知识库
│   ├── project-overview.md
│   ├── architecture-frontend.md
│   ├── architecture-backend.md
│   ├── api-contracts-backend.md
│   ├── data-models-backend.md
│   ├── component-inventory-frontend.md
│   ├── development-guide.md
│   └── ...
└── index.md                 # 文档索引
```

## 部署配置 (deploy/)

```
deploy/
├── nginx/                   # Nginx 配置
├── systemd/                 # Systemd 服务配置
└── docker/                  # Docker 配置
```

## 工作流配置 (_bmad/)

```
_bmad/
├── bmm/                     # BMAD 工作流
│   └── workflows/
│       └── document-project/  # 文档生成工作流
└── gds/                     # GDS 工作流
```

## CI/CD (.github/)

```
.github/
└── workflows/
    ├── backend-test.yml     # 后端测试
    ├── frontend-test.yml    # 前端测试
    └── deploy.yml           # 部署流程
```

## 文件统计

### 后端

- API 模块: 48 个
- 数据模型: 29 个
- 测试用例: 1350+ 个
- 协议适配器: 6 个

### 前端

- 页面视图: 28 个目录
- 组件目录: 12 个
- 状态管理: 7 个 Store
- 测试用例: 1182 个

### 总计

- 总代码行数: 约 150,000 行
- Python 文件: 约 300 个
- TypeScript/Vue 文件: 约 400 个
- 配置文件: 约 50 个

## 关键目录说明

### 后端关键目录

1. **app/api/v1/**: REST API 端点定义，每个文件对应一个功能模块
2. **app/models/**: SQLAlchemy ORM 模型，定义数据库表结构
3. **app/services/**: 业务逻辑实现，包含复杂的业务规则
4. **app/core/**: 核心配置和基础设施 (数据库、安全、依赖注入)
5. **backend/gateway/**: 多协议采集网关，支持 6 种工业协议
6. **backend/tests/**: 完整的测试套件，覆盖 API、服务、模型

### 前端关键目录

1. **src/views/**: 页面级组件，对应路由
2. **src/components/**: 可复用组件库
3. **src/stores/**: Pinia 状态管理，管理全局状态
4. **src/api/modules/**: API 客户端，与后端 API 对应
5. **src/composables/**: 组合式函数，封装可复用逻辑
6. **src/styles/**: 全局样式和 2.5D 视觉效果 Mixin

## 代码组织原则

1. **模块化**: 按功能模块组织代码，每个模块独立
2. **分层架构**: 前端 (View/Component/Store/API)，后端 (API/Service/Model/Core)
3. **类型安全**: 前端 TypeScript，后端 Pydantic Schema
4. **测试覆盖**: 前后端都有完整的单元测试和集成测试
5. **配置分离**: 环境配置通过 .env 文件管理
6. **文档完善**: 代码注释、API 文档、项目文档齐全

## 技术债务与改进方向

1. **前端**: 部分组件可以进一步拆分，提高复用性
2. **后端**: 部分服务层逻辑可以进一步抽象
3. **测试**: E2E 测试覆盖可以进一步提升
4. **文档**: API 文档可以自动生成并保持同步

## 更新记录

- 2026-03-01: 初始版本，完成 V3.2.1 代码结构分析
