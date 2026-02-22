# 算力中心智能监控系统 (DCIM) — 数据血缘追溯文档

> 版本: v2.0 | 最后更新: 2026-02-21

---

## 目录

1. [文档概述](#1-文档概述)
2. [数据源分类](#2-数据源分类)
3. [定时任务与后台服务](#3-定时任务与后台服务)
4. [按域分页面数据追溯](#4-按域分页面数据追溯)
   - 4.1 监控域
   - 4.2 管理域
   - 4.3 配置域
   - 4.4 系统管理
   - 4.5 其他页面
   - 4.6 补充: 未在页面追溯中直接引用的后端路由
5. [数据库表清单与写入源](#5-数据库表清单与写入源)
6. [前端 Mock/Fallback 数据说明](#6-前端-mockfallback-数据说明)
7. [数据生命周期](#7-数据生命周期)

---

## 1. 文档概述

### 1.1 追溯方法论

本文档对 DCIM 系统中所有前端页面展示的数据进行全链路追溯，从浏览器渲染层一直回溯到最终数据源头。追溯路径为：

```
前端页面 → Pinia Store / localStorage → API / WebSocket → 后端路由处理器 → 服务层 → 数据库表 → 最终数据源
```

系统共涉及 73 个 Vue 页面、38 个 API 模块、30+ 个后端路由文件、100+ 个数据库模型。本文档按导航域组织，逐页面追溯每个展示字段的数据来源。

### 1.2 系统架构概览

```
浏览器 ──HTTP/WS──> Vite Dev(3000) 或 Express Proxy(3000) ──> FastAPI(8080) ──> SQLite/PostgreSQL
```

| 层级 | 技术栈 | 说明 |
|------|--------|------|
| 前端 | Vue 3 + TypeScript + Vite + Element Plus | ECharts 图表, Three.js 3D |
| 代理 | Vite proxy (开发) / Express (生产) | 静态文件 + API/WS 转发 |
| 后端 | FastAPI + SQLAlchemy 2.0 (异步) | JWT 认证, RBAC 权限, WebSocket |
| 数据库 | SQLite (aiosqlite) / PostgreSQL | 异步 ORM |

### 1.3 双模式运行

系统有两种运行模式，数据来源因模式而异：

| 模式 | 配置 | 实时数据来源 | 聚合数据来源 |
|------|------|-------------|-------------|
| 模拟模式 (默认) | SIMULATION_ENABLED=true | DataSimulator 每5秒写入 | 由 DemoDataService 预填充历史数据 |
| 生产模式 | SIMULATION_ENABLED=false | 采集网关 (MQTT/Modbus/SNMP) | 定时聚合任务计算 |

### 1.4 前端数据中间层

前端页面并非全部直接调用 API，部分数据经过 Pinia Store 或 localStorage 中转：

**Pinia Stores:**

| Store | 文件 | 缓存内容 | 消费页面 |
|-------|------|---------|---------|
| useUserStore | stores/user.ts | 用户信息、Token、权限列表 | 全局 (路由守卫、请求拦截器) |
| useAppStore | stores/app.ts | 侧边栏状态、主题、站点选择 | 布局组件 |
| useAlarmStore | stores/alarm.ts | 活跃告警列表、告警计数 | Dashboard、告警中心、顶部通知栏 |
| useRealtimeStore | stores/realtime.ts | WebSocket 实时数据缓存 | Dashboard、环境监控、设备状态 |
| useEnergyStore | stores/energy.ts | 能耗统计缓存、PUE 数据 | 能效管理各页面 |
| useOpportunityStore | stores/opportunity.ts | 节能机会列表 | 能耗分析、执行追踪 |
| useBigscreenStore | stores/bigscreen.ts | 大屏布局、组件配置 | 大屏展示 |

**localStorage 持久化项:**

| Key | 内容 | 用途 |
|-----|------|------|
| token | JWT access token | API 请求认证 |
| refreshToken | JWT refresh token | Token 刷新 |
| userInfo | 用户基本信息 (JSON) | 页面刷新后恢复用户状态 |
| sidebarStatus | 侧边栏展开/折叠 | 布局偏好持久化 |
| currentSite | 当前选中站点 ID | 多站点切换持久化 |

---

## 2. 数据源分类

系统中所有数据的最终源头可归为以下八类：

### 2.1 数据源总览

| 编号 | 数据源类型 | 标识 | 说明 | 典型写入表 |
|------|-----------|------|------|-----------|
| S1 | 数据模拟器 | DataSimulator | 每5秒生成模拟采集数据 (仅模拟模式) | PointRealtime, PointHistory, Alarm |
| S2 | 采集网关 | Gateway | 生产环境通过 MQTT/Modbus/SNMP 采集真实设备数据 | PointRealtime, PointHistory |
| S3 | 用户录入/配置 | UserInput | 管理员通过前端界面手动创建或修改的配置数据 | Device, Point, PowerDevice, AlarmThreshold 等 |
| S4 | 定时聚合任务 | ScheduledTask | 后台定时任务对原始数据进行聚合计算 | EnergyHourly, EnergyDaily, EnergyMonthly, PUEHistory |
| S5 | 引擎/服务自动生成 | Engine | 事件驱动的后台引擎自动产生的衍生数据 | Alarm, DiagnosisResult, LinkageExecution, EnergySuggestion, DriftDetectionResult |
| S6 | 确定性模拟/硬编码 | Hardcoded | 基于配置参数的确定性计算或硬编码常量 | 无持久化 (实时计算返回) |
| S7 | 用户操作产生 | UserAction | 用户执行业务操作时自动记录的日志和状态变更 | OperationLog, CommandAuditLog, WorkOrderLog, RegulationHistory |
| S8 | 演示数据服务 | DemoDataService | 系统首次启动时预填充演示/历史数据 (仅模拟模式) | EnergyHourly, EnergyDaily, EnergyMonthly, PUEHistory, Demand15MinData |

### 2.2 数据源详细说明

**S1 - 数据模拟器 (DataSimulator)**

- 位置: backend/app/services/simulator.py
- 触发: 系统启动时自动运行 (simulation_enabled=true)
- 行为: 每5秒遍历所有 Point，AI 点位在量程范围内 ±2% 波动，DI 点位有 0.5% 概率触发告警
- 写入: PointRealtime (value, status, quality, updated_at), PointHistory, Alarm

**S2 - 采集网关 (Gateway)**

- 生产模式下，网关设备通过协议采集真实设备数据
- 支持协议: MQTT, Modbus TCP/RTU, SNMP, BACnet, OPC-UA
- 写入: PointRealtime, PointHistory (与模拟器写入相同表)

**S3 - 用户录入/配置**

- 所有 CRUD 操作产生的配置数据
- 包括: 设备管理、测点配置、阈值设置、告警规则、联动策略、资产台账、用户管理等

**S4 - 定时聚合任务**

- 生产模式下由定时任务自动运行；模拟模式下由 DemoDataService 预填充
- 从 PointHistory/PointRealtime 聚合计算能耗和 PUE 数据

**S5 - 引擎/服务自动生成**

- 告警引擎: 基于阈值规则自动生成告警记录
- 诊断引擎: 订阅告警事件，自动生成诊断结果
- 联动引擎: 订阅事件，自动执行联动策略并记录
- 建议引擎: 分析能耗数据，自动生成节能建议

**S6 - 确定性模拟/硬编码**

- energy/realtime 端点: 基于 PowerDevice.rated_power 乘以确定性系数生成电压/电流/功率
- 能源仪表盘: 电费使用硬编码 0.8 元/kWh
- 峰谷比例: peak_ratio=45%, valley_ratio=25% 硬编码

**S7 - 用户操作产生**

- 操作审计日志: 用户每次操作自动记录
- 工单日志: 工单流转过程自动记录
- 命令审计: 高风险命令审批记录

**S8 - 演示数据服务 (DemoDataService)**

- 位置: backend/app/services/demo_data_service.py
- 触发: 系统首次启动且 simulation_enabled=true 时自动运行
- 行为: 预填充历史能耗数据 (EnergyHourly/Daily/Monthly)、PUE 历史、需量数据等，确保模拟模式下图表和统计页面有数据可展示
- 写入: EnergyHourly, EnergyDaily, EnergyMonthly, PUEHistory, Demand15MinData, DemandHistory

---

## 3. 定时任务与后台服务

### 3.1 定时任务清单

| 任务名称 | 执行间隔 | 运行条件 | 读取数据 | 写入数据 | 说明 |
|---------|---------|---------|---------|---------|------|
| DataSimulator | 5秒 | `simulation_enabled=true` | Point (全部) | PointRealtime, PointHistory, Alarm | 模拟采集数据生成 |
| AlarmEngine 刷新 | 30秒 | 始终运行 | AlarmThreshold (版本号) | 内存缓存 | 检查阈值版本，热加载新规则 |
| 通信状态监测 | 30秒 | 始终运行 | Device, PointRealtime | Device.comm_status | 检测设备通信超时 |
| 告警升级引擎 | 60秒 | 始终运行 | Alarm, AlarmEscalation | Alarm (升级处理) | 检查未处理告警的升级条件 |
| PUE 历史记录 | 15分钟 | `simulation_enabled=false` | PowerDevice, PointRealtime | PUEHistory | 计算并记录 PUE 值 |
| 能耗小时聚合 | 每小时 | `simulation_enabled=false` | PointHistory, MeterPoint | EnergyHourly | 按小时聚合电表数据 |
| 能耗日聚合 | 每天一次 | `simulation_enabled=false` | EnergyHourly | EnergyDaily | 按天汇总小时数据 |
| 能耗月聚合 | 每月一次 | `simulation_enabled=false` | EnergyDaily | EnergyMonthly | 按月汇总日数据 |

### 3.2 事件驱动服务

| 服务名称 | 触发条件 | 读取数据 | 写入数据 | 说明 |
|---------|---------|---------|---------|------|
| DiagnosisEngine | 告警事件 | Alarm, DiagnosisRule | DiagnosisResult | 订阅告警，匹配诊断规则 |
| LinkageEngine | 告警/设备事件 | LinkagePolicy, LinkageAction | LinkageExecution, LinkageLog | 订阅事件，执行联动策略 |
| SuggestionEngine | 手动触发/定时 | EnergyDaily, PowerDevice | EnergySuggestion | 分析能耗，生成节能建议 |

### 3.3 PUE 计算器数据流

PUE 计算器 (`backend/app/services/pue_calculator.py`) 的数据流如下：

```
PowerDevice (enabled) -> power_point_id -> PointRealtime.value -> 按 device_type 分类汇总 -> PUE = total / IT
```

分类规则:

| device_type | 分类 | 说明 |
|-------------|------|------|
| IT | IT 负载 | 服务器、存储、网络设备 |
| AC, CHILLER, CT, PUMP | 制冷负载 | 空调、冷机、冷却塔、水泵 |
| UPS | UPS 负载 | 不间断电源 |

数据质量控制: quality==2 的数据点跳过, quality==1 或数据超过300秒标记为不可靠。

### 3.4 WebSocket 推送通道

| 通道 | URL | 推送源 | 推送内容 | 频率 | 消费页面 |
|------|-----|--------|---------|------|---------|
| realtime | `/ws/realtime?token=xxx` | DataSimulator / Gateway | PointRealtime 变更数据 | 每5秒 | dashboard/index.vue, environment/overview.vue, power/overview.vue, cooling/overview.vue, bigscreen/index.vue |
| alarms | `/ws/alarms?token=xxx` | AlarmEngine | 新告警、告警状态变更 | 事件驱动 | alarm/index.vue, dashboard/index.vue, 顶部通知栏组件 |
| system | `/ws/system?token=xxx` | 通信监测 | 设备通信状态、系统状态 | 事件驱动 | device-status/index.vue, dashboard/index.vue |

### 3.5 ML 模型数据流 (条件加载)

ML 模块在 `torch` 已安装时条件加载 (`backend/app/api/v1/__init__.py` 中 try/except 控制)，未安装时跳过，不影响系统核心功能。

| 功能 | API 端点 | 后端处理器 | 读取数据 | 输出 | 说明 |
|------|---------|-----------|---------|------|------|
| 异常检测 | `/ml/anomaly-detect` | `api/v1/ml.py` | PointHistory | 异常评分 | 基于时序数据的异常检测模型 |
| 负荷预测 | `/ml/load-forecast` | `api/v1/ml.py` | EnergyHourly, EnergyDaily | 未来负荷预测值 | 基于历史能耗的负荷预测 |
| PUE 预测 | `/ml/pue-predict` | `api/v1/ml.py` | PUEHistory, PointRealtime | PUE 预测值 | 基于环境参数的 PUE 预测 |

> **注意**: ML 模块为可选功能，`torch` 未安装时所有 `/ml/*` 端点不可用，前端对应功能隐藏。

---

## 4. 按域分页面数据追溯

> **表格列说明:**
> - **页面**: 前端 Vue 文件路径
> - **展示数据**: 页面上显示的主要数据字段
> - **API 端点**: 调用的后端 API (省略 `/api/v1` 前缀)
> - **后端处理器**: 对应的后端路由文件 (均位于 `backend/app/api/v1/` 目录下)
> - **数据库表**: 涉及的主要数据库模型
> - **最终数据源**: 参见第2节数据源编号 (S1-S8)

> **域分类说明**: 监控域 = 只读展示实时/历史数据的页面；管理域 = 涉及业务操作和数据分析的页面；配置域 = 系统配置和策略管理页面。部分页面 (如 energy/monitor.vue) 同时具有监控和管理属性，按主要用途归类。

### 4.1 监控域

#### 4.1.1 综合概览 (Dashboard)

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| dashboard/index.vue | 实时采集数据总览、设备状态统计 | `/realtime/all`, `/realtime/summary` | `api/v1/realtime.py` | Point, PointRealtime, Device | S1/S2 (模拟器或网关) |
| dashboard/index.vue | 活跃告警列表、告警数量 | `/alarms/active` | `api/v1/alarm.py` | Alarm, Point | S5 (告警引擎) |
| dashboard/index.vue | 能耗仪表盘 (PUE、用电量、电费) | `/energy/dashboard` | `api/v1/realtime.py` | PUEHistory, EnergyDaily, PowerDevice | S4/S8 (聚合/预填充) + S6 (电费硬编码 0.8元/kWh, peak_ratio=45%, valley_ratio=25%, 位于 realtime.py 第417-425行) |

#### 4.1.2 供配电监控

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| power/overview.vue | 供配电系统总览、功率分布 | `/power/overview` | `api/v1/power.py` | UPSDevice, BatteryGroup, Device, Point, PointRealtime | S1/S2 |
| power/ups.vue | UPS 设备列表、运行状态、负载率 | `/power/ups`, `/power/ups/{id}` | `api/v1/power.py` | UPSDevice, Device, Point, PointRealtime | S1/S2 (实时值) + S3 (设备配置) |
| power/battery.vue | 电池组列表、电压、温度、健康度 | `/power/battery`, `/power/battery/{id}` | `api/v1/power.py` | BatteryGroup, Device, Point, PointRealtime | S1/S2 (实时值) + S3 (设备配置) |
| power/cabinet.vue | 机柜配电列表、功率分配 | `/power/cabinet` | `api/v1/power.py` | Device, Point, PointRealtime | S1/S2 |
| power/pdu.vue | PDU 列表、相电流、负载率 | `/power/pdu` | `api/v1/power.py` | Device, Point, PointRealtime | S1/S2 |

#### 4.1.3 制冷监控

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| cooling/overview.vue | 制冷系统总览、COP、冷量分布 | `/cooling/overview` | `api/v1/cooling.py` | CoolingGroup, CoolingUnit, ColdAisle, Device, Point, PointRealtime | S1/S2 + S3 |
| cooling/indoor.vue | 室内机组列表、送回风温度、运行状态 | `/cooling/units`, `/cooling/units/{id}` | `api/v1/cooling.py` | CoolingUnit, Device, Point, PointRealtime | S1/S2 (实时值) + S3 (机组配置) |
| cooling/outdoor.vue | 室外机组列表、冷凝温度、风机状态 | `/cooling/units`, `/cooling/units/{id}` | `api/v1/cooling.py` | CoolingUnit, Device, Point, PointRealtime | S1/S2 (实时值) + S3 (机组配置) |
| cooling/cold-aisle.vue | 冷通道列表、温湿度、气流组织 | `/cooling/cold-aisles`, `/cooling/cold-aisles/{id}` | `api/v1/cooling.py` | ColdAisle, Device, Point, PointRealtime | S1/S2 (实时值) + S3 (通道配置) |
| cooling/group-control.vue | 群控策略、机组联动状态 | `/cooling/groups`, `/cooling/units` | `api/v1/cooling.py` | CoolingGroup, CoolingUnit | S3 (群控配置) + S1/S2 (运行状态) |

#### 4.1.4 环境监控

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| environment/overview.vue | 环境参数总览 (温湿度、气流) | `/realtime/all` | `api/v1/realtime.py` | Point, PointRealtime, Device | S1/S2 |
| environment/temperature.vue | 温度分布、超限告警、历史趋势 | `/alarms/active`, `/history/trend` | `api/v1/alarm.py`, `api/v1/history.py` | Alarm, Point, PointHistory | S5 (告警) + S1/S2 (历史数据) |
| environment/smoke-infrared.vue | 烟感/红外传感器告警列表 | `/alarms` | `api/v1/alarm.py` | Alarm, Point | S5 (告警引擎) |
| environment/water-leak.vue | 漏水检测告警列表 | `/alarms` | `api/v1/alarm.py` | Alarm, Point | S5 (告警引擎) |

#### 4.1.5 安防消防

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| security/overview.vue | 安防系统总览、传感器状态 | `/realtime/all` | `api/v1/realtime.py` | Point, PointRealtime, Device | S1/S2 |
| security/access-control.vue | 门禁管理、出入记录 | `/security/access` | `api/v1/security.py` | AccessRecord, Device | S2 (门禁设备) + S3 (配置) |
| security/fire-linkage.vue | 消防联动策略管理 | `/linkage/fire-protection/*` | `api/v1/linkage.py` | LinkagePolicy, LinkageAction | S3 (用户配置) |
| video/index.vue | NVR/摄像头管理列表 | `/video/nvr`, `/video/cameras` | `api/v1/video.py` | NVR, Camera | S3 (用户配置) |
| video/control.vue | 实时视频、云台控制、预置位 | `/video/cameras`, `/video/ptz`, `/video/preset`, `/video/recording` | `api/v1/video.py` | Camera, CameraPreset, VideoEvent | S3 (配置) + S2 (视频流) |
| video/playback.vue | 录像回放、录像片段列表 | `/video/playback`, `/video/segments` | `api/v1/video.py` | Camera, VideoEvent | S2 (录像存储) |

#### 4.1.6 告警中心

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| alarm/index.vue | 告警列表、告警统计、告警处理 | `/alarms`, `/alarms/count`, `/alarms/acknowledge`, `/alarms/resolve` | `api/v1/alarm.py` | Alarm, Point | S5 (告警引擎生成) + S7 (用户确认/处理) |
| alarm/index.vue | 告警规则管理 | `/alarms/rules` (CRUD) | `api/v1/alarm.py` | AlarmRule, Point | S3 (用户配置) |
| alarm/index.vue | 告警屏蔽管理 | `/alarms/shields` (CRUD) | `api/v1/alarm.py` | AlarmShield | S3 (用户配置) |
| alarm/index.vue | 告警升级管理 | `/alarms/escalations` (CRUD) | `api/v1/alarm.py` | AlarmEscalation | S3 (用户配置) |
| alarm/thresholds.vue | 阈值列表、四级阈值设置、批量设置 | `/thresholds` (CRUD), `/thresholds/four-level`, `/thresholds/batch` | `api/v1/threshold.py` | AlarmThreshold, Point | S3 (用户配置) |
| alarm/thresholds.vue | 测点历史趋势 (阈值参考) | `/history/trend` | `api/v1/history.py` | PointHistory | S1/S2 |
| alarm/compound.vue | 复合告警规则管理 | `/alarms/rules` (CRUD) | `api/v1/alarm.py` | AlarmRule, Point | S3 (用户配置) |
| alarm/shield.vue | 告警屏蔽策略管理 | `/alarms/shields` (CRUD) | `api/v1/alarm.py` | AlarmShield, Device, Point | S3 (用户配置) |
| alarm/escalation.vue | 告警升级策略管理 | `/alarms/escalations` (CRUD) | `api/v1/alarm.py` | AlarmEscalation, User | S3 (用户配置) |

### 4.2 管理域

#### 4.2.1 能效管理 - 用电监控

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| energy/monitor.vue | 实时功率数据 (电压、电流、功率) | `/energy/realtime` | `api/v1/energy.py` | PowerDevice | S6 (基于 rated_power 确定性模拟计算) |
| energy/monitor.vue | 功率汇总 (总功率、IT功率) | `/energy/realtime/summary` | `api/v1/energy.py` | PowerDevice, PointRealtime | S6 (模拟) + S1/S2 (实时值) |
| energy/monitor.vue | 当前 PUE 值 | `/energy/pue` | `api/v1/energy.py` (pue_calculator) | PowerDevice, PointRealtime | S1/S2 → pue_calculator 实时计算 |
| energy/monitor.vue | PUE 历史趋势 | `/energy/pue/trend` | `api/v1/energy.py` | PUEHistory | S4/S8 (定时聚合/预填充) |
| energy/monitor.vue | 能耗仪表盘 (含 Mock 降级) | `/energy/dashboard` | `api/v1/realtime.py` | PUEHistory, EnergyDaily, EnergySuggestion, MeterPoint | S4/S8 + S5 + S6 (含前端 Mock 降级) |

> **重要说明**: `energy/realtime` 端点当前所有电气参数 (电压、电流、功率) 均由 PowerDevice.rated_power 乘以确定性系数生成，并非来自 PointRealtime 真实采集值。`/energy/dashboard` 端点的硬编码值 (0.8 元/kWh, peak_ratio=45%, valley_ratio=25%) 位于 `api/v1/realtime.py` 第417-425行。

#### 4.2.2 能效管理 - 能耗统计

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| energy/statistics.vue | 日能耗统计 | `/energy/statistics/daily` | `api/v1/energy.py` | EnergyDaily | S4/S8 (日聚合/预填充) |
| energy/statistics.vue | 月能耗统计 | `/energy/statistics/monthly` | `api/v1/energy.py` | EnergyMonthly | S4/S8 (月聚合/预填充) |
| energy/statistics.vue | 能耗汇总 (总量、均值) | `/energy/statistics/summary` | `api/v1/energy.py` | EnergyDaily, EnergyMonthly | S4/S8 |
| energy/statistics.vue | 能耗趋势图 | `/energy/statistics/trend` | `api/v1/energy.py` | EnergyDaily | S4/S8 |
| energy/statistics.vue | 同比/环比分析 | `/energy/statistics/comparison` | `api/v1/energy.py` | EnergyDaily, EnergyMonthly | S4/S8 |
| energy/statistics.vue | 日/月数据导出 (Excel/CSV) | `/energy/export/daily`, `/energy/export/monthly` | `api/v1/energy.py` | EnergyDaily, EnergyMonthly | S4/S8 |

#### 4.2.3 能效管理 - 能耗分析

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| energy/analysis.vue | 需量配置分析 | `/energy/demand/config/analyze` | `api/v1/energy.py` | DemandHistory, Demand15MinData | S4/S8 (聚合) + S3 (配置) |
| energy/analysis.vue | 设备移峰填谷分析 | `/energy/shift/analyze` | `api/v1/energy.py` | DeviceShiftConfig, DeviceLoadProfile | S3 (配置) + S4 (负载数据) |
| energy/analysis.vue | 15分钟需量曲线 | `/energy/demand/15min-curve` | `api/v1/energy.py` | Demand15MinData | S4/S8 (聚合) |
| energy/analysis.vue | 需量峰值分析 | `/energy/demand/peak-analysis` | `api/v1/energy.py` | DemandHistory | S4/S8 |
| energy/analysis.vue | 需量优化方案 | `/energy/demand/optimization-plan` | `api/v1/energy.py` | DemandHistory, Demand15MinData | S5 (引擎计算) |
| energy/analysis.vue | 需量聚合曲线 | `/energy/demand/aggregated-curve` | `api/v1/energy.py` | Demand15MinData | S4/S8 |
| energy/analysis.vue | 电表点位列表 | `/energy/meters` | `api/v1/energy.py` | MeterPoint | S3 (用户配置) |
| energy/analysis.vue | 负荷时段分布 | `/demand/load-period-distribution` | `api/v1/demand.py` | Demand15MinData | S4/S8 |
| energy/analysis.vue | 节能机会创建 | `/opportunities` (POST) | `api/v1/opportunities.py` | EnergyOpportunity, OpportunityMeasure | S3 (用户创建) |
| energy/analysis.vue | 执行计划详情 | `/execution/plans/{id}` | `api/v1/execution.py` | ExecutionPlan, ExecutionTask | S3 + S7 |

#### 4.2.4 能效管理 - 负荷调控

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| energy/regulation.vue | 调控配置列表 | `/regulation/configs` (CRUD) | `api/v1/regulation.py` | LoadRegulationConfig | S3 (用户配置) |
| energy/regulation.vue | 调控历史记录 | `/regulation/history` | `api/v1/regulation.py` | RegulationHistory | S7 (用户操作产生) |
| energy/regulation.vue | 调控推荐方案 | `/regulation/recommendations` | `api/v1/regulation.py` | LoadRegulationConfig, PointRealtime | S5 (引擎推荐) |
| energy/regulation.vue | 调控模拟 | `/regulation/simulate` | `api/v1/regulation.py` | LoadRegulationConfig, PointRealtime | S5 (实时计算) |
| energy/regulation.vue | 执行调控 | `/regulation/apply` | `api/v1/regulation.py` | RegulationHistory | S7 (用户操作) |
| energy/regulation.vue | 用电设备列表 | `/energy/devices` | `api/v1/energy.py` | PowerDevice | S3 (用户配置) |

#### 4.2.5 能效管理 - 执行追踪

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| energy/execution.vue | 执行计划列表 | `/opportunities/execution-plans` | `api/v1/opportunities.py` | ExecutionPlan | S3 (用户创建) |
| energy/execution.vue | 执行计划详情 | `/opportunities/execution-plans/{id}` | `api/v1/opportunities.py` | ExecutionPlan, ExecutionTask, ExecutionResult | S3 + S7 |
| energy/execution.vue | 更新计划状态 | `/opportunities/execution-plans/{id}/status` | `api/v1/opportunities.py` | ExecutionPlan | S7 (用户操作) |
| energy/execution.vue | 自动任务执行 | `/opportunities/tasks/{id}/auto-execute` | `api/v1/opportunities.py` | ExecutionTask, ExecutionResult | S5 (自动执行) |
| energy/execution.vue | 手动任务完成 | `/opportunities/tasks/{id}/manual-complete` | `api/v1/opportunities.py` | ExecutionTask, ExecutionResult | S7 (用户操作) |
| energy/execution.vue | 执行统计 | `/opportunities/execution-stats` | `api/v1/opportunities.py` | ExecutionPlan, ExecutionResult | S4 (统计聚合) |
| energy/execution.vue | 追踪数据 | `/opportunities/tracking` | `api/v1/opportunities.py` | ExecutionResult | S7 |

#### 4.2.6 能效管理 - 能效报告与节能建议

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| energy/report.vue | 能效报告预览 | `/energy/report/preview` | `api/v1/energy.py` (energy_report_service) | EnergyDaily, PUEHistory, PowerDevice, Alarm | S4 + S5 (聚合+计算) |
| energy/report.vue | 能效报告导出 (Excel/PDF) | `/energy/report/export` | `api/v1/energy.py` | 同上 | S4 + S5 |
| energy/suggestions.vue | 节能建议列表 | `/energy/suggestions` | `api/v1/energy.py` | EnergySuggestion | S5 (建议引擎生成) |
| energy/suggestions.vue | 节能潜力分析 | `/energy/saving/potential` | `api/v1/energy.py` | EnergySuggestion, PowerDevice | S5 |
| energy/suggestions.vue | 接受/拒绝/完成建议 | `/energy/suggestions/{id}/accept`, `reject`, `complete` | `api/v1/energy.py` | EnergySuggestion | S7 (用户操作) |
| energy/suggestions.vue | 建议模板 | `/energy/suggestions/templates` | `api/v1/energy.py` | 内存常量 | S6 (硬编码) |
| energy/suggestions.vue | 触发建议分析 | `/energy/suggestions/trigger-analysis` | `api/v1/energy.py` (suggestion_engine) | EnergySuggestion | S5 (引擎生成) |
| energy/suggestions.vue | 建议汇总统计 | `/energy/suggestions/summary` | `api/v1/energy.py` | EnergySuggestion | S5 |

#### 4.2.7 资产与容量管理

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| asset/index.vue | 资产列表、资产统计 | `/assets` (CRUD), `/assets/statistics` | `api/v1/asset.py` | Asset, AssetLifecycle | S3 (用户录入) |
| asset/index.vue | 维保记录 | `/assets/{id}/maintenance` (CRUD) | `api/v1/asset.py` | MaintenanceRecord | S3 (用户录入) |
| asset/index.vue | 保修到期预警 | `/assets/warranty-alerts` | `api/v1/asset.py` | Asset | S3 (基于录入的保修日期计算) |
| asset/index.vue | 资产导入/导出/模板 | `/assets/import`, `/assets/export`, `/assets/template` | `api/v1/asset.py` | Asset | S3 |
| asset/cabinet.vue | 机柜列表、U位使用率 | `/cabinets` (CRUD), `/cabinets/{id}/usage` | `api/v1/asset.py` | Cabinet, Asset | S3 (用户录入) |
| asset/cabinet.vue | 机柜内资产移动 | `/cabinets/{id}/move-asset` | `api/v1/asset.py` | Asset, Cabinet | S7 (用户操作) |
| capacity/index.vue | 空间容量 | `/capacity/space` (CRUD) | `api/v1/capacity.py` | SpaceCapacity | S3 (用户配置) |
| capacity/index.vue | 电力容量 | `/capacity/power` (CRUD) | `api/v1/capacity.py` | PowerCapacity | S3 |
| capacity/index.vue | 制冷容量 | `/capacity/cooling` (CRUD) | `api/v1/capacity.py` | CoolingCapacity | S3 |
| capacity/index.vue | 承重容量 | `/capacity/weight` (CRUD) | `api/v1/capacity.py` | WeightCapacity | S3 |
| capacity/index.vue | 容量规划 | `/capacity/plans` (CRUD) | `api/v1/capacity.py` | CapacityPlan | S3 |
| capacity/index.vue | 容量统计/告警/趋势/预测 | `/capacity/statistics`, `/capacity/alerts`, `/capacity/trend`, `/capacity/forecast` | `api/v1/capacity.py` | SpaceCapacity, PowerCapacity, CoolingCapacity, WeightCapacity, CapacityHistory | S3 + S4 (趋势计算) |
| capacity/index.vue | 智能上架推荐 | `/capacity/racking-recommendation` | `api/v1/capacity.py` | Cabinet, Asset, SpaceCapacity, PowerCapacity, CoolingCapacity, WeightCapacity | S3 (基于配置数据计算) |
| topology/spatial.vue | 空间拓扑树 (站点/楼层/房间/列) | `/spatial/tree` (CRUD) | `api/v1/spatial.py` | Site, Floor, Room, Row, Cabinet | S3 (用户配置) |
| topology/spatial.vue | 机柜位置更新 | `/spatial/cabinet-position` | `api/v1/spatial.py` | Cabinet | S7 (用户操作) |
| topology/spatial.vue | 空间数据导入/导出 | `/spatial/import`, `/spatial/export` | `api/v1/spatial.py` | Site, Floor, Room, Row | S3 |
| topology/spatial.vue | 布局模板 | `/spatial/templates` | `api/v1/spatial.py` | LayoutTemplate | S3 |

#### 4.2.8 运维管理

> **注意**: history/index.vue 归入运维管理域，因其主要用于运维排障场景。

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| operation/workorder.vue | 工单列表 | `/operations/workorders` (CRUD) | `api/v1/operation.py` | WorkOrder | S3 (用户创建) + S5 (告警自动派单) |
| operation/workorder.vue | 工单流转 (开始/完成) | `/operations/workorders/{id}/start`, `complete` | `api/v1/operation.py` | WorkOrder, WorkOrderLog | S7 (用户操作) |
| operation/workorder.vue | 工单日志 | `/operations/workorders/{id}/logs` | `api/v1/operation.py` | WorkOrderLog | S7 |
| operation/workorder.vue | 运维统计 | `/operations/statistics` | `api/v1/operation.py` | WorkOrder, InspectionTask | S7 (统计聚合) |
| operation/inspection.vue | 巡检计划列表 | `/operations/inspection-plans` (CRUD) | `api/v1/operation.py` | InspectionPlan | S3 (用户配置) |
| operation/inspection.vue | 巡检任务生成/执行 | `/operations/inspection-tasks/generate`, `.../{id}/start`, `complete` | `api/v1/operation.py` | InspectionTask | S3 (生成) + S7 (执行) |
| operation/knowledge.vue | 知识库列表 | `/operations/knowledge` (CRUD) | `api/v1/operation.py` | KnowledgeBase | S3 (用户录入) |
| report/index.vue | 日报/周报/月报 | `/reports/daily`, `/reports/weekly`, `/reports/monthly` | `api/v1/report.py` | ReportRecord, Alarm, Device, EnergyDaily, PUEHistory, WorkOrder | S4 + S5 (聚合计算) |
| report/index.vue | 报告记录列表 | `/reports/records` | `api/v1/report.py` | ReportRecord | S4 |
| report/index.vue | 生成/下载报告 | `/reports/generate`, `/reports/download` | `api/v1/report.py` | ReportRecord, ReportTemplate, ReportSchedule, DeviceHealthScore | S4 + S5 |
| history/index.vue | 测点历史数据查询 | `/history`, `/history/trend`, `/history/statistics` | `api/v1/history.py` | PointHistory, PointHistoryArchive | S1/S2 (原始采集数据) |
| history/index.vue | 历史数据导出 | `/history/export` | `api/v1/history.py` | PointHistory | S1/S2 |
| history/index.vue | 测点列表 (选择器) | `/points` | `api/v1/point.py` | Point | S3 (用户配置) |

#### 4.2.9 虚拟电厂

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| vpp/VPPAnalysis.vue | 虚拟电厂分析 (电费、负荷曲线、电价、可调负荷、VPP配置) | `/vpp/*` | `api/v1/vpp.py` | ElectricityBill, LoadCurve, ElectricityPrice, AdjustableLoad, VPPConfig | S3 (用户配置/导入) |

### 4.3 配置域

#### 4.3.1 采集配置 - 设备管理

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| device-manage/index.vue | 设备列表、设备状态统计 | `/devices` (CRUD), `/devices/status-summary` | `api/v1/device.py` | Device, Point, PointRealtime, Alarm | S3 (设备配置) + S1/S2 (状态) |
| device-manage/detail.vue | 设备详情、关联测点 | `/devices/{id}` | `api/v1/device.py` | Device, Point, PointRealtime | S3 + S1/S2 |
| device-manage/detail.vue | 测点历史趋势 | `/history/trend` | `api/v1/history.py` | PointHistory | S1/S2 |
| device-status/index.vue | 设备状态看板 (按区域/类型分组) | `/devices/status-board` | `api/v1/device.py` | Device, Point, PointRealtime | S1/S2 (实时状态) + S3 (设备配置) |
| device/index.vue | 用电设备列表 | `/energy/devices` | `api/v1/energy.py` | PowerDevice | S3 (用户配置) |

#### 4.3.2 采集配置 - 模板与数据源

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| device-template/index.vue | 设备模板列表 | `/device-templates` (CRUD) | `api/v1/device_templates.py` | DeviceTemplate | S3 (用户配置) |
| datasource/index.vue | 数据源列表 | `/datasources` (CRUD) | `api/v1/datasources.py` | DataSource, DataSourcePoint | S3 (用户配置) |

#### 4.3.3 采集配置 - 网关管理

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| gateway/index.vue | 网关列表、网关状态统计 | `/gateways`, `/gateways/summary` | `api/v1/gateways.py` | Gateway | S3 (用户配置) + S2 (网关自动注册) |
| gateway/index.vue | 网关详情 | `/gateways/{id}` | `api/v1/gateways.py` | Gateway, DataSource | S3 + S2 |
| gateway/index.vue | 网关事件日志 | `/gateways/{id}/events` | `api/v1/gateways.py` | GatewayEvent | S2 (网关上报) + S7 (操作记录) |
| gateway/index.vue | 配置下发 | `/gateways/{id}/push-config` | `api/v1/gateways.py` | ConfigPushRecord | S7 (用户操作) |

#### 4.3.4 采集配置 - 能源配置

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| energy/config.vue | 变压器列表 | `/energy/transformers` (CRUD) | `api/v1/energy.py` | Transformer | S3 (用户配置) |
| energy/config.vue | 电表点位列表 | `/energy/meters` (CRUD) | `api/v1/energy.py` | MeterPoint | S3 |
| energy/config.vue | 配电柜列表 | `/energy/panels` (CRUD) | `api/v1/energy.py` | DistributionPanel | S3 |
| energy/config.vue | 配电回路列表 | `/energy/circuits` (CRUD) | `api/v1/energy.py` | DistributionCircuit | S3 |
| energy/config.vue | 电价配置 | `/energy/pricing` (CRUD) | `api/v1/energy.py` | ElectricityPricing, PricingConfig | S3 |
| energy/config.vue | 移峰比例推荐 | `/energy/shift/recommendations` | `api/v1/energy.py` | DeviceShiftConfig, DeviceLoadProfile | S5 (引擎推荐) |
| energy/config.vue | 更新设备移峰比例 | `/energy/shift/ratio` | `api/v1/energy.py` | DeviceShiftConfig | S7 (用户操作) |
| energy/config.vue | 变压器与电表关联视图 | `/energy/transformers-with-meters` | `api/v1/energy.py` | Transformer, MeterPoint | S3 |
| energy/config.vue | 电费账单 OCR 上传 | `/energy/bill/ocr` | `api/v1/energy.py` | — | S3 (用户上传) |

#### 4.3.5 采集配置 - 配电拓扑

> **注意**: 本节追溯 energy/topology.vue，与 Section 4.3.10 中 topology/power.vue 不同。前者为能源模块的配电拓扑可视化，后者为拓扑配置模块的相位映射管理。

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| energy/topology.vue | 配电拓扑图 | `/energy/distribution/topology` | `api/v1/energy.py` (EnergyTopologyService) | PowerDevice, DistributionPanel, DistributionCircuit, Point, PointRealtime | S3 (拓扑配置) + S1/S2 (实时值) |
| energy/topology.vue | 拓扑节点管理 | `/energy/distribution/topology/node` (CRUD) | `api/v1/energy.py` | PowerDevice | S3 |
| energy/topology.vue | 设备关联测点 | `/energy/distribution/device-points` | `api/v1/energy.py` | Point, PointRealtime | S3 + S1/S2 |
| energy/topology.vue | 拓扑导入/导出 | `/energy/distribution/topology/export`, `import` | `api/v1/energy.py` | PowerDevice, DistributionPanel | S3 |

#### 4.3.6 策略引擎 - 联动策略

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| linkage/policy.vue | 联动策略列表 | `/linkage/policies` (CRUD) | `api/v1/linkage.py` | LinkagePolicy, LinkageAction | S3 (用户配置) |
| linkage/policy.vue | 策略启停 | `/linkage/policies/{id}/toggle` | `api/v1/linkage.py` | LinkagePolicy | S7 (用户操作) |
| linkage/policy.vue | 策略测试 | `/linkage/policies/{id}/test` | `api/v1/linkage.py` | LinkagePolicy | S5 (引擎测试执行) |
| linkage/policy.vue | 动作类型列表 | `/linkage/action-types` | `api/v1/linkage.py` | 内存常量 | S6 (硬编码) |
| linkage/policy.vue | 消防联动重载 | `/linkage/fire-protection/reload` | `api/v1/linkage.py` (fire_protection) | LinkagePolicy | S5 |

#### 4.3.7 策略引擎 - 联动执行与恢复

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| linkage/execution.vue | 联动执行记录列表 | `/linkage/executions` | `api/v1/linkage.py` | LinkageExecution | S5 (联动引擎自动生成) |
| linkage/execution.vue | 执行详情 | `/linkage/executions/{id}` | `api/v1/linkage.py` | LinkageExecution, LinkageLog | S5 |
| linkage/recovery.vue | 可恢复执行列表 | `/linkage/recoverable-executions` | `api/v1/linkage.py` | LinkageExecution | S5 |
| linkage/recovery.vue | 创建恢复流程 | `/linkage/recoveries` (POST) | `api/v1/linkage.py` | LinkageRecovery | S7 (用户操作) |
| linkage/recovery.vue | 恢复记录列表/详情 | `/linkage/recoveries`, `/linkage/recoveries/{id}` | `api/v1/linkage.py` | LinkageRecovery, LinkageRecoveryLog | S7 |
| linkage/recovery.vue | 执行/跳过恢复步骤 | `/linkage/recoveries/{id}/steps/{step}/execute`, `skip` | `api/v1/linkage.py` | LinkageRecoveryLog | S7 |

#### 4.3.8 策略引擎 - 事件时间线与命令审计

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| linkage/timeline.vue | 联动执行时间线 | `/linkage/executions`, `/linkage/timeline` | `api/v1/linkage.py` (timeline_report) | LinkageExecution, LinkageLog | S5 (引擎生成) |
| linkage/timeline.vue | 事件时间线导出 | `/linkage/timeline/export` | `api/v1/linkage.py` | LinkageExecution | S5 |
| linkage/command.vue | 命令审批列表 | `/command/approvals` | `api/v1/command.py` | CommandApproval | S5 (联动引擎触发) + S3 (手动提交) |
| linkage/command.vue | 审批/拒绝命令 | `/command/approvals/{id}/approve`, `reject` | `api/v1/command.py` | CommandApproval, CommandAuditLog | S7 (用户操作) |
| linkage/command.vue | 命令审计日志 | `/command/audit-logs` | `api/v1/command.py` | CommandAuditLog | S7 |
| linkage/command.vue | 风险配置 | `/command/risk-configs` (GET/PUT) | `api/v1/command.py` | SystemConfig | S3 (用户配置) |

#### 4.3.9 策略引擎 - 漂移检测与智能诊断

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| linkage/drift.vue | 漂移检测结果 | `/drift/results` | `api/v1/drift.py` | DriftDetectionResult | S5 (漂移检测引擎) |
| linkage/drift.vue | 触发漂移检测 | `/drift/trigger` | `api/v1/drift.py` | DriftDetectionResult | S5 |
| linkage/drift.vue | 解决漂移 | `/drift/results/{id}/resolve` | `api/v1/drift.py` | DriftDetectionResult | S7 (用户操作) |
| linkage/drift.vue | 漂移汇总统计 | `/drift/summary` | `api/v1/drift.py` | DriftDetectionResult | S5 |
| diagnosis/rules.vue | 诊断规则列表 | `/diagnosis/rules` (CRUD) | `api/v1/diagnosis.py` | DiagnosisRule | S3 (用户配置) |
| diagnosis/rules.vue | 规则启停 | `/diagnosis/rules/{id}/toggle` | `api/v1/diagnosis.py` | DiagnosisRule | S7 |
| diagnosis/rules.vue | 重载诊断规则 | `/diagnosis/rules/reload` | `api/v1/diagnosis.py` | DiagnosisRule | S5 |
| diagnosis/results.vue | 诊断结果列表 | `/diagnosis/results` | `api/v1/diagnosis.py` | DiagnosisResult | S5 (诊断引擎自动生成) |

#### 4.3.10 拓扑配置 - 配电拓扑

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| topology/power.vue | 配电相位映射列表 | `/topology-config/power-phase-mappings` (CRUD) | `api/v1/topology_config.py` | PowerPhaseMapping, PowerDevice, DistributionPanel, DistributionCircuit | S3 (用户配置) |
| topology/power.vue | PDU 三相平衡分析 | `/topology-config/pdu-phase-balance` | `api/v1/topology_config.py` | PowerPhaseMapping, Device, Point, PointRealtime | S3 (配置) + S1/S2 (实时值) |
| topology/power.vue | PDU 列表 | `/power/pdu` | `api/v1/power.py` | Device, Point, PointRealtime | S1/S2 |
| topology/power.vue | 机柜列表 | `/cabinets` | `api/v1/asset.py` | Cabinet | S3 |

#### 4.3.11 拓扑配置 - 制冷拓扑

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| topology/cooling.vue | 制冷区域列表 | `/topology-config/cooling-zones` (CRUD) | `api/v1/topology_config.py` | CoolingZone, CoolingZoneCabinet, CoolingZoneUnit | S3 (用户配置) |
| topology/cooling.vue | 制冷区域容量分析 | `/topology-config/cooling-zone-capacity` | `api/v1/topology_config.py` | CoolingZone, CoolingUnit, Cabinet, Asset | S3 (配置数据计算) |
| topology/cooling.vue | 制冷机组列表 | `/cooling/units` | `api/v1/cooling.py` | CoolingUnit | S3 |
| topology/cooling.vue | 机柜列表 | `/cabinets` | `api/v1/asset.py` | Cabinet | S3 |
| topology/cooling.vue | 房间列表 | `/spatial/rooms` | `api/v1/spatial.py` | Room | S3 |

#### 4.3.12 拓扑配置 - 故障影响与智能选址

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| topology/fault-impact.vue | 故障影响分析 | `/topology-config/fault-impact-analysis` | `api/v1/topology_config.py` | PowerDevice, DistributionPanel, DistributionCircuit, Cabinet, Asset, Alarm | S3 (拓扑配置) + S5 (告警数据) |
| topology/fault-impact.vue | PDU 列表 | `/power/pdu` | `api/v1/power.py` | Device, Point | S3 + S1/S2 |
| topology/site-selection.vue | 智能选址推荐 | `/topology-config/smart-site-selection` | `api/v1/topology_config.py` | Cabinet, Asset, SpaceCapacity, PowerCapacity, CoolingCapacity, WeightCapacity, PowerPhaseMapping, CoolingZone, Device, Point, Floor, Room, Row, Site, Alarm | S3 (多维配置数据综合评分) |

### 4.4 系统管理

#### 4.4.1 用户管理

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| system/user.vue | 用户列表 | `/users` (CRUD) | `api/v1/user.py` | User | S3 (管理员配置) |
| system/user.vue | 用户启停 | `/users/{id}/toggle-status` | `api/v1/user.py` | User | S7 (管理员操作) |
| system/user.vue | 重置密码 | `/users/{id}/reset-password` | `api/v1/user.py` | User, PasswordHistory | S7 |
| system/user.vue | 批量删除 | `/users/batch-delete` | `api/v1/user.py` | User | S7 |

#### 4.4.2 站点管理

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| system/sites.vue | 站点列表、站点汇总 | `/spatial/sites` (CRUD), `/spatial/sites/summary` | `api/v1/spatial.py` | Site | S3 (管理员配置) |

#### 4.4.3 审计日志

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| system/audit-log.vue | 操作日志列表 | `/logs/operation` | `api/v1/log.py` | OperationLog | S7 (用户操作自动记录) |
| system/audit-log.vue | 系统日志列表 | `/logs/system` | `api/v1/log.py` | SystemLog | S5 (系统自动生成) |
| system/audit-log.vue | 通信日志列表 | `/logs/communication` | `api/v1/log.py` | CommunicationLog | S2 (网关通信记录) |
| system/audit-log.vue | 日志导出 | `/logs/export` | `api/v1/log.py` | OperationLog, SystemLog, CommunicationLog | S7 + S5 + S2 |

#### 4.4.4 系统设置

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| settings/index.vue | 阈值配置列表 | `/thresholds` (CRUD), `/thresholds/point-thresholds`, `/thresholds/four-level`, `/thresholds/batch` | `api/v1/threshold.py` | AlarmThreshold, Point | S3 (用户配置) |
| settings/index.vue | 操作日志 | `/logs/operation` | `api/v1/log.py` | OperationLog | S7 |
| settings/index.vue | 系统日志 | `/logs/system` | `api/v1/log.py` | SystemLog | S5 |
| settings/index.vue | 日志导出 | `/logs/export` | `api/v1/log.py` | OperationLog, SystemLog | S7 + S5 |
| settings/index.vue | 测点列表 (选择器) | `/points` | `api/v1/point.py` | Point | S3 |

### 4.5 其他页面

#### 4.5.1 登录页

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| login/index.vue | 登录表单 | `/auth/login` (via Pinia store) | `api/v1/auth.py` | User, UserLoginHistory, UserSession, PasswordHistory | S3 (用户凭证) + S7 (登录记录) |

#### 4.5.2 大屏展示

| 页面 | 展示数据 | API 端点 | 后端处理器 | 数据库表 | 最终数据源 |
|------|---------|---------|-----------|---------|-----------|
| bigscreen/index.vue | 大屏默认布局 | `/bigscreen/default-layout` | (bigscreen store) | — | S3 (布局配置) + S6 (默认布局硬编码) |

> **说明**: 大屏页面通常聚合多个数据源，通过 WebSocket 实时推送更新，底层数据来源与 Dashboard 一致 (S1/S2 实时数据 + S4 聚合数据 + S5 告警数据)。

### 4.6 补充: 未在页面追溯中直接引用的后端路由

以下 17 个后端路由文件未在 Section 4.1-4.5 的页面追溯表格中直接出现，但属于系统 API 层的组成部分：

| 路由文件 | 路径前缀 | 说明 |
|---------|---------|------|
| `api/v1/data_quality.py` | `/data-quality` | 数据质量评估与统计 |
| `api/v1/demo.py` | `/demo` | 演示数据管理 (重置/初始化演示环境) |
| `api/v1/dispatch.py` | `/dispatch` | 调度管理 (可调度设备、调度计划) |
| `api/v1/escalation.py` | `/escalation` | 告警升级独立端点 (与 alarm.py 中升级功能互补) |
| `api/v1/execution.py` | `/execution` | 执行计划独立端点 (被 energy/analysis.vue 引用) |
| `api/v1/floor_map.py` | `/floor-map` | 楼层平面图上传与管理 |
| `api/v1/ml.py` | `/ml` | 机器学习模型端点 (条件加载，需 torch) |
| `api/v1/monitoring.py` | `/monitoring` | 监控数据端点 (双模式: simulation_enabled 条件分支) |
| `api/v1/optimization.py` | `/optimization` | 优化算法端点 (调度优化、储能优化) |
| `api/v1/ota.py` | `/ota` | OTA 固件升级管理 |
| `api/v1/point.py` | `/points` | 测点 CRUD (被多个页面的测点选择器引用) |
| `api/v1/pricing.py` | `/pricing` | 电价独立端点 (与 energy.py 中电价功能互补) |
| `api/v1/proposal.py` | `/proposals` | 节能提案管理 |
| `api/v1/statistics.py` | `/statistics` | 统计分析独立端点 |
| `api/v1/system_health.py` | `/system-health` | 系统健康检查与状态监控 |
| `api/v1/topology.py` | `/topology` | 配电拓扑独立端点 (与 energy.py 中拓扑功能互补) |
| `api/v1/trace.py` | `/trace` | 数据追溯与链路查询 |

---

## 5. 数据库表清单与写入源

> **说明**: 本节补充 Section 4 未覆盖的维度：模型文件位置和写入源归属。Section 4 按页面追溯数据流向，本节按数据库模型维度汇总所有表的写入来源。

### 5.1 采集与实时数据

| 数据库表 | 模型文件 | 主要写入源 | 说明 |
|---------|---------|-----------|------|
| Point | point.py | S3 (用户配置) | 测点定义 (名称、类型、量程、所属设备) |
| PointRealtime | point.py | S1 (模拟器) / S2 (网关) | 测点实时值 (value, status, quality, updated_at) |
| PointGroup | point.py | S3 | 测点分组 |
| PointGroupMember | point.py | S3 | 测点分组成员 |
| PointHistory | history.py | S1 / S2 | 测点历史数据 (时序存储) |
| PointHistoryArchive | history.py | S4 (归档任务) | 历史数据归档 |
| PointChangeLog | history.py | S7 (自动记录) | 测点配置变更日志 |

### 5.2 设备管理

| 数据库表 | 模型文件 | 主要写入源 | 说明 |
|---------|---------|-----------|------|
| Device | device.py | S3 (用户配置) | 设备定义 (名称、类型、通信参数) |
| Gateway | gateway.py | S3 + S2 (自动注册) | 采集网关 |
| DataSource | gateway.py | S3 | 数据源配置 |
| DataSourcePoint | gateway.py | S3 | 数据源关联测点 |
| GatewayEvent | gateway.py | S2 (网关上报) + S7 | 网关事件日志 |
| ConfigPushRecord | gateway.py | S7 | 配置下发记录 |
| PointDataLatest | gateway.py | S2 | 网关最新数据缓存 |
| FirmwarePackage | gateway.py | S3 | 固件包管理 |
| OtaTask | gateway.py | S3 | OTA 升级任务 |
| OtaTaskGateway | gateway.py | S7 | OTA 任务执行记录 |
| DeviceTemplate | gateway.py | S3 | 设备模板 |
| MqttAclRule | gateway.py | S3 | MQTT ACL 规则 |

### 5.3 告警管理

| 数据库表 | 模型文件 | 主要写入源 | 说明 |
|---------|---------|-----------|------|
| Alarm | alarm.py | S1 (模拟器触发) / S5 (告警引擎) | 告警记录 |
| AlarmThreshold | alarm.py | S3 (用户配置) | 告警阈值 |
| AlarmRule | alarm.py | S3 | 复合告警规则 |
| AlarmShield | alarm.py | S3 | 告警屏蔽策略 |
| AlarmDailyStats | alarm.py | S4 (定时统计) | 告警日统计 |
| AlarmEscalation | alarm.py | S3 | 告警升级规则 |

### 5.4 能源管理

| 数据库表 | 模型文件 | 主要写入源 | 说明 |
|---------|---------|-----------|------|
| PowerDevice | energy.py | S3 (用户配置) | 用电设备 (rated_power, device_type) |
| Transformer | energy.py | S3 | 变压器 |
| MeterPoint | energy.py | S3 | 电表点位 |
| DistributionPanel | energy.py | S3 | 配电柜 |
| DistributionCircuit | energy.py | S3 | 配电回路 |
| PowerCurveData | energy.py | S1/S2 + S4 | 功率曲线数据 |
| EnergyHourly | energy.py | S4 (小时聚合) / S8 (预填充) | 小时能耗 |
| EnergyDaily | energy.py | S4 (日聚合) / S8 (预填充) | 日能耗 |
| EnergyMonthly | energy.py | S4 (月聚合) / S8 (预填充) | 月能耗 |
| PUEHistory | energy.py | S4 (15分钟聚合) / S8 (预填充) | PUE 历史记录 |
| ElectricityPricing | energy.py | S3 | 电价配置 |
| PricingConfig | energy.py | S3 | 电价方案 |
| EnergySuggestion | energy.py | S5 (建议引擎) | 节能建议 |
| DemandHistory | energy.py | S4 / S8 | 需量历史 |
| OverDemandEvent | energy.py | S5 | 超需量事件 |
| DeviceLoadProfile | energy.py | S4 | 设备负荷曲线 |
| DeviceShiftConfig | energy.py | S3 | 设备移峰配置 |
| Demand15MinData | energy.py | S4 / S8 | 15分钟需量数据 |
| DemandAnalysisRecord | energy.py | S5 | 需量分析记录 |
| LoadRegulationConfig | energy.py | S3 | 负荷调控配置 |
| RegulationHistory | energy.py | S7 (用户操作) | 调控历史 |

### 5.5 节能优化与执行

| 数据库表 | 模型文件 | 主要写入源 | 说明 |
|---------|---------|-----------|------|
| EnergySavingProposal | energy.py | S5 | 节能提案 |
| ProposalMeasure | energy.py | S5 | 提案措施 |
| MeasureExecutionLog | energy.py | S7 | 措施执行日志 |
| MeasureBaseline | energy.py | S4 | 措施基线数据 |
| MonitoringRecord | energy.py | S5 | 监测记录 |
| EffectReport | energy.py | S5 | 效果报告 |
| MonitoringSession | energy.py | S5 | 监测会话 |
| EnergyOpportunity | energy.py | S3 (用户创建) | 节能机会 |
| OpportunityMeasure | energy.py | S3 | 机会措施 |
| ExecutionPlan | energy.py | S3 | 执行计划 |
| ExecutionTask | energy.py | S3 + S5 | 执行任务 |
| ExecutionResult | energy.py | S5 + S7 | 执行结果 |

### 5.6 虚拟电厂与调度

| 数据库表 | 模型文件 | 主要写入源 | 说明 |
|---------|---------|-----------|------|
| DispatchableDevice | energy.py | S3 | 可调度设备 |
| StorageSystemConfig | energy.py | S3 | 储能系统配置 |
| PVSystemConfig | energy.py | S3 | 光伏系统配置 |
| DispatchSchedule | energy.py | S5 (调度引擎) | 调度计划 |
| RealtimeMonitoring | energy.py | S1/S2 | 实时监测 |
| MonthlyStatistics | energy.py | S4 | 月度统计 |
| OptimizationResult | energy.py | S5 | 优化结果 |
| ElectricityBill | vpp_data.py | S3 (用户导入) | 电费账单 |
| LoadCurve | vpp_data.py | S3 | 负荷曲线 |
| ElectricityPrice | vpp_data.py | S3 | 电价数据 |
| AdjustableLoad | vpp_data.py | S3 | 可调负荷 |
| VPPConfig | vpp_data.py | S3 | VPP 配置 |

### 5.7 资产与容量

| 数据库表 | 模型文件 | 主要写入源 | 说明 |
|---------|---------|-----------|------|
| Cabinet | asset.py | S3 | 机柜 |
| Asset | asset.py | S3 | 资产台账 |
| AssetLifecycle | asset.py | S7 (状态变更自动记录) | 资产生命周期 |
| MaintenanceRecord | asset.py | S3 | 维保记录 |
| AssetInventory | asset.py | S3 | 资产盘点 |
| AssetInventoryItem | asset.py | S3 | 盘点明细 |
| SpaceCapacity | capacity.py | S3 | 空间容量 |
| PowerCapacity | capacity.py | S3 | 电力容量 |
| CoolingCapacity | capacity.py | S3 | 制冷容量 |
| WeightCapacity | capacity.py | S3 | 承重容量 |
| CapacityPlan | capacity.py | S3 | 容量规划 |
| CapacityHistory | capacity.py | S4 (定时快照) | 容量历史 |

### 5.8 空间与拓扑

| 数据库表 | 模型文件 | 主要写入源 | 说明 |
|---------|---------|-----------|------|
| Site | spatial.py | S3 | 站点 |
| Floor | spatial.py | S3 | 楼层 |
| Room | spatial.py | S3 | 房间 |
| Row | spatial.py | S3 | 列 |
| LayoutTemplate | spatial.py | S3 | 布局模板 |
| FloorMap | floor_map.py | S3 | 楼层平面图 |
| PowerPhaseMapping | topology_config.py | S3 | 配电相位映射 |
| CoolingZone | topology_config.py | S3 | 制冷区域 |
| CoolingZoneCabinet | topology_config.py | S3 | 制冷区域-机柜关联 |
| CoolingZoneUnit | topology_config.py | S3 | 制冷区域-机组关联 |

### 5.9 制冷与供配电

| 数据库表 | 模型文件 | 主要写入源 | 说明 |
|---------|---------|-----------|------|
| CoolingGroup | cooling.py | S3 | 制冷群组 |
| CoolingUnit | cooling.py | S3 | 制冷机组 |
| ColdAisle | cooling.py | S3 | 冷通道 |
| UPSDevice | power.py | S3 | UPS 设备 |
| BatteryGroup | power.py | S3 | 电池组 |

### 5.10 联动与诊断

| 数据库表 | 模型文件 | 主要写入源 | 说明 |
|---------|---------|-----------|------|
| LinkagePolicy | linkage.py | S3 | 联动策略 |
| LinkageAction | linkage.py | S3 | 联动动作 |
| LinkageExecution | linkage.py | S5 (联动引擎) | 联动执行记录 |
| LinkageLog | linkage.py | S5 | 联动日志 |
| LinkageRecovery | linkage.py | S7 (用户操作) | 联动恢复 |
| LinkageRecoveryLog | linkage.py | S7 | 恢复日志 |
| DiagnosisRule | diagnosis.py | S3 | 诊断规则 |
| DiagnosisResult | diagnosis.py | S5 (诊断引擎) | 诊断结果 |
| DriftDetectionResult | drift.py | S5 (漂移检测) | 漂移检测结果 |
| CommandApproval | command.py | S5 + S3 | 命令审批 |
| CommandAuditLog | command.py | S7 | 命令审计日志 |

### 5.11 运维管理

| 数据库表 | 模型文件 | 主要写入源 | 说明 |
|---------|---------|-----------|------|
| WorkOrder | operation.py | S3 + S5 (告警自动派单) | 工单 |
| WorkOrderLog | operation.py | S7 (流转自动记录) | 工单日志 |
| InspectionPlan | operation.py | S3 | 巡检计划 |
| InspectionTask | operation.py | S3 (生成) + S7 (执行) | 巡检任务 |
| KnowledgeBase | operation.py | S3 | 知识库 |
| AlarmWorkOrderRule | operation.py | S3 | 告警自动派单规则 |
| WorkOrderApproval | operation.py | S7 | 工单审批 |

### 5.12 报表

| 数据库表 | 模型文件 | 主要写入源 | 说明 |
|---------|---------|-----------|------|
| ReportTemplate | report.py | S3 | 报表模板 |
| ReportRecord | report.py | S4 (定时生成) + S7 (手动生成) | 报表记录 |
| ReportSchedule | report.py | S3 | 报表调度 |
| DeviceHealthScore | report.py | S5 (健康评估引擎) | 设备健康评分 |

### 5.13 视频监控

| 数据库表 | 模型文件 | 主要写入源 | 说明 |
|---------|---------|-----------|------|
| NVR | video.py | S3 | 网络录像机 |
| Camera | video.py | S3 | 摄像头 |
| CameraPreset | video.py | S3 | 摄像头预置位 |
| VideoEvent | video.py | S5 (告警联动) + S2 (录像) | 视频事件 |

### 5.14 用户与系统

| 数据库表 | 模型文件 | 主要写入源 | 说明 |
|---------|---------|-----------|------|
| User | user.py | S3 (管理员配置) | 用户 |
| RolePermission | user.py | S3 | 角色权限 |
| UserLoginHistory | user.py | S7 (登录自动记录) | 登录历史 |
| UserSession | user.py | S7 (登录自动创建) | 用户会话 |
| UserSite | user.py | S3 | 用户-站点关联 |
| PasswordHistory | user.py | S7 (密码变更自动记录) | 密码历史 |
| OperationLog | log.py | S7 (操作自动记录) | 操作日志 |
| SystemLog | log.py | S5 (系统自动生成) | 系统日志 |
| CommunicationLog | log.py | S2 (通信自动记录) | 通信日志 |
| SystemConfig | config.py | S3 | 系统配置 |
| Dictionary | config.py | S3 | 数据字典 |
| License | config.py | S3 | 许可证 |

---

## 6. 前端 Mock/Fallback 数据说明

### 6.1 已知的 Mock 与 Fallback 机制

| 位置 | 类型 | 触发条件 | Mock 内容 | 说明 |
|------|------|---------|----------|------|
| energy/monitor.vue | 前端 Fallback | API 调用失败时 | `generateMockDashboardData()` 生成完整仪表盘数据 (PUE、功率、能耗、电费、建议) | 确保页面在后端不可用时仍可展示 |
| `/energy/realtime` 端点 | 后端确定性模拟 | 始终 (当前实现) | 基于 PowerDevice.rated_power 乘以确定性系数生成电压/电流/功率 | 非真实采集值，所有电气参数均为计算值 |
| `/energy/dashboard` 端点 | 后端硬编码 | 始终 | 电费 = 能耗 * 0.8 元/kWh; peak_ratio=45%, valley_ratio=25% (位于 `api/v1/realtime.py` 第417-425行) | 未接入真实电价计算 |
| 建议模板 | 后端内存常量 | 始终 | `/energy/suggestions/templates` 返回预定义的建议模板列表 | 非数据库存储 |
| 联动动作类型 | 后端内存常量 | 始终 | `/linkage/action-types` 返回预定义的动作类型列表 | 非数据库存储 |
| 大屏布局 | 前端/Store | 无自定义布局时 | bigscreen store 提供默认布局配置 | 降级到默认布局 |
| cooling/overview.vue | 前端 Fallback | API 失败或关键字段缺失 | mockData 对象 (CoolingOverviewSummary) | 制冷总览降级数据 |
| cooling/indoor.vue | 前端 Fallback | API 未就绪 | 模拟精密空调列表和详情 | 室内机组降级数据 |
| cooling/outdoor.vue | 前端 Fallback | API 未就绪 | 模拟室外机列表和详情 | 室外机组降级数据 |
| cooling/cold-aisle.vue | 前端 Fallback | API 未就绪 | 模拟冷通道列表和详情 | 冷通道降级数据 |
| cooling/group-control.vue | 前端 Fallback | API 未就绪 | 模拟群控组列表和详情 | 群控降级数据 |
| power/overview.vue | 前端 Fallback | API 失败或关键字段缺失 | mockData 对象 (PowerOverviewSummary) | 供配电总览降级数据 |
| power/ups.vue | 前端 Fallback | API 未就绪 | 模拟 UPS 列表和详情 | UPS 降级数据 |
| power/battery.vue | 前端 Fallback | API 未就绪 | 模拟电池组列表和详情 | 电池组降级数据 |
| power/cabinet.vue | 前端 Fallback | API 未就绪 | 模拟配电柜列表 | 配电柜降级数据 |
| power/pdu.vue | 前端 Fallback | API 未就绪 | `generateMockOutlets()` 生成模拟 PDU 插座数据 | PDU 降级数据 |
| energy/analysis.vue | 前端 Fallback | API 失败 | `generateMockHourlyData()`, `generateMockCurveData()`, `generateMockAggregatedData()` | 能耗分析降级数据 |
| components/energy/LoadComparisonChart.vue | 前端 Fallback | API 失败 | `generateMockLoadData()` | 负荷对比图降级数据 |
| components/energy/DevicePowerCurveChart.vue | 前端 Fallback | 始终 | `generateMockPowerData()` | 设备功率曲线始终使用模拟数据 |
| components/demand/LoadPeriodChart.vue | 前端 Fallback | API 失败 | `applyMockDataFallback()` + `generateMockData()` | 负荷时段图降级数据 |
| components/bigscreen/BigscreenFloor3D.vue | 前端 Fallback | WebGL 不可用 | 降级到 2D 平面图模式 | 3D 渲染降级 |
| components/bigscreen/BigscreenHistoryDialog.vue | 前端 Fallback | 数据缺失 | 使用 store 中的数据作为 fallback | 历史对话框降级 |
| components/bigscreen/FloorSelector.vue | 前端 Fallback | 数据缺失 | 使用默认数据 | 楼层选择器降级 |
| `api/v1/monitoring.py` 端点 | 后端双模式 | `simulation_enabled` 条件 | `demo_data_provider` 提供模拟数据 (is_demo_data=true) | 监控端点模拟模式分支 |

### 6.2 模拟模式 vs 生产模式数据差异

| 数据类别 | 模拟模式 (`SIMULATION_ENABLED=true`) | 生产模式 (`SIMULATION_ENABLED=false`) |
|---------|--------------------------------------|---------------------------------------|
| PointRealtime | DataSimulator 每5秒写入，AI点位 ±2% 波动 | 采集网关通过协议写入真实值 |
| PointHistory | DataSimulator 同步写入 | 网关采集同步写入 |
| Alarm | DataSimulator DI点位 0.5% 概率触发 + 告警引擎 | 告警引擎基于真实数据触发 |
| EnergyHourly/Daily/Monthly | 由 DemoDataService (`demo_data_service.py`) 预填充历史数据 | 定时聚合任务从 PointHistory 计算 |
| PUEHistory | 由 DemoDataService (`demo_data_service.py`) 预填充历史数据 | 每15分钟由 pue_calculator 从 PointRealtime 计算 |
| energy/realtime 电气参数 | 确定性模拟 (两种模式均相同) | 确定性模拟 (两种模式均相同) |

### 6.3 数据可靠性标注

| 可靠性等级 | 说明 | 涉及数据 |
|-----------|------|---------|
| 高 | 来自真实采集或用户明确录入 | 生产模式下的 PointRealtime, 所有用户配置数据 |
| 中 | 基于真实数据的聚合计算 | EnergyHourly/Daily/Monthly, PUEHistory (生产模式) |
| 低 | 模拟数据或硬编码 | 模拟模式下所有采集数据, energy/realtime 电气参数, 硬编码电费/峰谷比 |
| 降级 | 前端 Mock 数据 | generateMockDashboardData() 等 fallback 函数输出 |

---

## 7. 数据生命周期

系统中部分数据具有生命周期管理机制，包括归档、聚合和清理：

| 机制 | 涉及表 | 触发方式 | 行为 | 说明 |
|------|--------|---------|------|------|
| 历史数据归档 | PointHistory → PointHistoryArchive | 定时任务 | 将超过保留期的 PointHistory 记录迁移到 PointHistoryArchive 表 | 减少主表数据量，提升查询性能 |
| 告警日统计 | Alarm → AlarmDailyStats | 每日定时任务 | 按天统计告警数量、级别分布、处理率，写入 AlarmDailyStats | 为报表和趋势分析提供预聚合数据 |
| 容量历史快照 | SpaceCapacity, PowerCapacity, CoolingCapacity, WeightCapacity → CapacityHistory | 定时快照 | 定期记录各维度容量使用率快照 | 为容量趋势预测提供历史数据 |
| 演示数据初始化 | EnergyHourly, EnergyDaily, EnergyMonthly, PUEHistory, Demand15MinData | DemoDataService (S8) | 系统首次启动时预填充历史数据 | 仅模拟模式，确保图表和统计页面有数据展示 |
| 报表定时生成 | ReportRecord | ReportSchedule 定时触发 | 按配置的调度规则自动生成日报/周报/月报 | 生成的报表记录持久化到 ReportRecord |

---

*本文档基于系统源码分析生成，对应代码版本 V3.0.0 (2026-02-20)。覆盖全部 73 个 Vue 页面、38 个 API 模块、100+ 个数据库模型。数据源编号速查请参见 Section 2.1。如有新增页面或数据流变更，请同步更新本文档。*
