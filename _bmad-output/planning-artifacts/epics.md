---
stepsCompleted: [requirements-inventory, epic-design, story-creation, coverage-map, phase2-supplement]
inputDocuments: [_bmad-output/planning-artifacts/prd.md, _bmad-output/planning-artifacts/architecture.md]
workflowType: epics-and-stories
project_name: DCIM
user_name: proecheng
date: 2026-02-21
phase2_supplement_date: 2026-02-21
phase2_supplement_epics: [18, 19, 20, 21, 22, 23]
---

# DCIM 算力中心智能监控系统 - Epics & Stories

**Author:** proecheng
**Date:** 2026-02-15
**Status:** 完整版 - 基于 PRD 2026-02-15 + Architecture 2026-02-15 全面重建

---

## 概述

本文档将 PRD 中功能需求 FR1-FR99 和非功能需求按业务域组织为 28 个 Epic，每个 Epic 包含 1-10 个用户故事。所有故事按 PRD 分阶段计划标注阶段归属。Epic 24-26 为智能诊断系统（FR34-1~FR34-42），基于架构文档 V4.0.0 Section 18 设计。Epic 27 为前端数据链路统一，基于 `docs/data-flow-audit.md` 审查结果和架构文档 V4.0.0 Section 19 规范。Epic 28 为 Demo 系统解耦与数据隔离，基于 `docs/demo-system-audit.md` 审查结果和架构文档 V4.0.0 Section 20 规范。

### Epic 总览

| # | Epic | 阶段 | FR 覆盖 | 故事数 |
|---|------|------|---------|--------|
| 1 | 采集网关框架 + Modbus/SNMP 适配器 | MVP | FR1,FR2,FR7,FR11,FR12 | 6 |
| 2 | 网关管理 + MQTT 通信链路 | MVP | FR15-FR19 | 6 |
| 3 | 数据源管理 UI + 设备模板 | MVP | FR8-FR10,FR13,FR14 | 5 |
| 4 | 实时监控适配 | MVP | FR21-FR26 | 6 |
| 5 | 告警管理增强 | MVP | FR27-FR33,FR87 | 5 |
| 6 | 能源管理 | MVP+Phase2 | FR45-FR53 | 5 |
| 7 | 资产与容量管理 | Ph1.5+Ph2 | FR54-FR61 | 6 |
| 8 | 机房物理拓扑 + 智能选址 | Phase 2 | FR62-FR66 | 4 |
| 9 | 联动引擎 + 消防联动 | Phase 2 | FR34-FR39 | 7 |
| 10 | 视频监控集成 | Phase 2 | FR40-FR44 | 4 |
| 11 | 运维管理 | Phase 2 | FR67-FR71 | 5 |
| 12 | 报表与决策支持 | Phase 2 | FR72-FR75,FR85 | 4 |
| 13 | 用户与系统管理 | MVP | FR76-FR82,FR84 | 6 |
| 14 | 棕地改进 - 代码质量与测试 | MVP | FR83,FR86,FR88,NFR-E5,NFR-M3 | 6 |
| 15 | 协议扩展 | Ph1.5+Ph2 | FR3-FR6,FR20 | 5 |
| 16 | 多站点集中管理 | 推广阶段 | FR82补充 | 3 |
| 17 | 2.5D 视觉增强 | 全阶段 | FR89-FR92 | 4 |
| 18 | 环境监测子系统详情页 | Phase 2 补充 | FR22 | 3 |
| 19 | 安防消防前端可视化 | Phase 2 补充 | FR37 | 2 |
| 20 | 告警规则增强管理页 | Phase 2 补充 | FR87 | 4 |
| 21 | 网关管理前端 | Phase 2 补充 | FR15-17 | 2 |
| 22 | 站点管理前端 | Phase 2 补充 | FR82 | 2 |
| 23 | 大屏增强与能源OCR | Phase 2 补充 | FR22,FR48 | 3 |
| **24** | **智能诊断核心引擎** | **Phase 2a (月7-8)** | **FR34-1~12, 16~19, 29** | **8** |
| **25** | **智能诊断专业扩展** | **Phase 2b (月9-10)** | **FR34-8, 13~15, 22~26, 30~32** | **8** |
| **26** | **智能诊断高级功能** | **Phase 3 (月11-12+)** | **FR34-3, 20~21, 27~28, 33~42** | **10** |
| **27** | **前端数据链路统一** | **MVP (月1-3)** | **NFR-P1, NFR-M1** | **6** |
| **28** | **Demo 系统解耦与数据隔离** | **MVP (月1-3)** | **NFR-M1, NFR-M3** | **4** |

### Epic 依赖关系

```
Epic 1 --> Epic 2 --> Epic 4 --> Epic 5 --> Epic 9 --> Epic 10
Epic 1 --> Epic 3
Epic 1 --> Epic 15
Epic 4 --> Epic 6
Epic 5 --> Epic 11
Epic 7 --> Epic 8
Epic 5,6,7 --> Epic 12
Epic 2,13 --> Epic 16
Epic 14 --> Epic 17
Epic 13, 14 独立并行
Epic 14 --> Epic 9 (联动引擎需 PostgreSQL+TimescaleDB)
Epic 5 --> Epic 24 --> Epic 25 --> Epic 26
Epic 8 --> Epic 25 (配电拓扑级联依赖物理拓扑)
Epic 14 --> Epic 24 (诊断引擎需 PostgreSQL)
Epic 27 独立并行（棕地前端重构，无外部依赖，但应在 Epic 4/5/6 实施前或同步完成）
Epic 28 独立并行（demo 解耦，应在真实网关接入前完成，即 Epic 1/2 之前或同步）
```

### 阶段规划

| 阶段 | 时间 | Epic |
|------|------|------|
| MVP 月1-3 | 120人天 | 1, 2, 3, 4, 5, 6基础, 13, 14, **27**, **28** |
| Phase 1.5 月4-6 | 试点+补全 | 7基础, 15-MQTT/HTTP |
| Phase 2a 月7-8 | 核心推理 | 6完整, 7完整, 8, 9, 10, 11, 12, 15-BACnet/OPC-UA, **24** |
| Phase 2b 月9-10 | 专业扩展 | **25**, 16 |
| Phase 3 月11-12+ | 高级+灰度 | **26** |

---

## Epic 1: 采集网关框架 + Modbus/SNMP 适配器

**阶段:** MVP (月1-3)
**目标:** 构建协议适配器插件化框架，实现 Modbus TCP/RTU 和 SNMP v2c 适配器，打通设备数据采集链路。
**FR 覆盖:** FR1, FR2, FR7, FR11, FR12
**架构参考:** Architecture 6.1-6.7 协议适配器插件化架构

### Story 1.1: 协议适配器插件化框架

As a 开发者,
I want 一个可扩展的协议适配器框架,
So that 新增协议只需实现标准接口并注册即可，不影响已有适配器。

**Acceptance Criteria:**

- Given 网关代码库已初始化
- When 开发者创建新的协议适配器
- Then 只需继承 BaseProtocolAdapter 抽象基类并实现 connect/disconnect/read_points/write_point/test_connection/get_status 方法
- And 在 ADAPTER_REGISTRY 中注册后即可被采集调度器自动发现和调用
- And 每个数据源独立采集周期（1-60s 可配），asyncio 并发调度互不阻塞

**FR 追溯:** FR11

### Story 1.2: Modbus TCP 适配器

As a 集成工程师,
I want 通过 Modbus TCP 协议采集设备数据,
So that 我可以接入通过网络连接的空调、UPS、PDU 等设备。

**Acceptance Criteria:**

- Given 集成工程师已配置 Modbus TCP 数据源（IP 地址、端口、从站地址、寄存器映射）
- When 采集调度器按配置周期触发采集
- Then 适配器通过 pymodbus 3.x 异步读取指定寄存器数据
- And 支持 Holding Register、Input Register、Coil、Discrete Input 四种寄存器类型
- And 连接失败时按指数退避重试（1s-2s-4s-8s-最大60s）
- And 连续 5 次失败标记数据源为"通信中断"并触发告警
- And 寄存器地址越界时记录错误日志并标记对应点位为"数据质量：异常"
- And 从站无响应时按指数退避重试（1s-2s-4s-8s-最大60s），连续 5 次失败标记数据源为"通信中断"并触发告警
- And 数据类型不匹配（如期望 float 收到 int）时尝试自动转换，无法转换则标记点位质量为"异常"

**FR 追溯:** FR1

### Story 1.3: Modbus RTU 适配器

As a 集成工程师,
I want 通过 Modbus RTU 协议采集串口设备数据,
So that 我可以接入通过 RS-485 连接的精密空调、环境传感器、电池巡检仪。

**Acceptance Criteria:**

- Given 集成工程师已配置 Modbus RTU 数据源（串口号、波特率、数据位、校验位、从站地址）
- When 采集调度器触发采集
- Then 适配器通过 pymodbus 3.x 异步读取串口设备数据
- And TCP 和 RTU 为独立适配器（配置参数、错误处理、重连逻辑差异大）
- And 读取超时立即重试 1 次，仍失败则标记点位质量为"不可靠"
- And 串口被占用时记录错误并标记数据源为"配置错误"，提示用户检查串口分配
- And 波特率不匹配导致 CRC 校验失败时，连续 3 次失败后标记数据源为"通信中断"并建议检查串口参数

**FR 追溯:** FR1

### Story 1.4: SNMP v2c/v3 适配器

As a 集成工程师,
I want 通过 SNMP v2c/v3 协议采集网络设备数据,
So that 我可以接入 UPS、网络交换机等支持 SNMP 的设备。

**Acceptance Criteria:**

- Given 集成工程师已配置 SNMP 数据源（目标地址、团体名、OID 映射）
- When 采集调度器触发采集
- Then 适配器通过 aiosnmp 异步读取指定 OID 的值
- And 支持 GET 和 WALK 操作
- And 原始值经过数据归一化层转换为工程值（缩放、偏移、枚举映射）
- And 支持 SNMP v3 认证模式（用户名、认证协议 MD5/SHA、加密协议 DES/AES）
- And 团体名错误或认证失败时返回明确错误提示"认证失败，请检查团体名/认证参数"
- And OID 不存在时跳过该点位并记录警告日志，不影响其他点位采集
- And SNMP 请求超时（默认 5s）时立即重试 1 次，仍失败则标记点位质量为"不可靠"

**FR 追溯:** FR2

### Story 1.5: 连接测试功能

As a 集成工程师,
I want 对数据源执行连接测试,
So that 我可以在正式采集前验证通信参数是否正确。

**Acceptance Criteria:**

- Given 集成工程师已填写数据源配置参数
- When 点击"测试连接"按钮
- Then 系统尝试建立连接并读取少量数据
- And 返回测试结果：成功（含读取到的样本数据）或失败（含错误原因）
- And 测试超时时间为 10 秒

**FR 追溯:** FR7

### Story 1.6: 干接点信号采集

As a 集成工程师,
I want 通过 Modbus I/O 采集模块读取干接点信号,
So that 消防主机和门禁系统的开关量信号可以接入 DCIM。

**Acceptance Criteria:**

- Given 消防主机/门禁的干接点信号已通过 Modbus I/O 采集模块转换
- When 适配器读取 DI 寄存器
- Then 点位配置层面标记为"干接点类型"
- And 告警引擎对干接点做状态变化触发（非阈值判断）
- And 干接点状态变化事件标记为 FIRE_SIGNAL 优先级（消防信号）

**FR 追溯:** FR12

---

## Epic 2: 网关管理 + MQTT 通信链路

**阶段:** MVP (月1-3)
**目标:** 实现网关注册、状态监控、远程配置下发，打通网关到后端的 MQTT 数据上报链路。
**FR 覆盖:** FR15, FR16, FR17, FR18, FR19（6 个 Story）
**架构参考:** Architecture 2.5-2.6 网关架构, 4.6 MQTT Topic 设计

### Story 2.1: 网关自动注册

As a 运维工程师,
I want 采集网关上线时自动注册到平台,
So that 我不需要手动录入网关信息。

**Acceptance Criteria:**

- Given 网关首次启动并连接到 MQTT Broker
- When 网关发送注册消息到 dcim/{site_id}/gw/{gw_id}/status
- Then 后端自动创建 Gateway 记录（唯一标识、IP、版本、能力列表）
- And 网关每 30 秒发送心跳状态（CPU/内存/磁盘使用率）
- And 心跳超时（Redis TTL 过期）自动标记网关为离线并触发告警

**FR 追溯:** FR15

### Story 2.2: 网关状态监控

As a 运维工程师,
I want 查看所有网关的运行状态,
So that 我可以及时发现网关故障。

**Acceptance Criteria:**

- Given 运维工程师在网关管理页面
- When 查看网关列表
- Then 显示每台网关的在线/离线状态、CPU/内存/磁盘使用率、最后心跳时间
- And 离线网关红色高亮显示
- And 点击网关可查看其负责的数据源和点位数量

**FR 追溯:** FR16

### Story 2.3: 远程配置下发

As a 运维工程师,
I want 通过平台远程向网关下发采集配置,
So that 我不需要到现场修改网关配置。

**Acceptance Criteria:**

- Given 运维工程师在数据源管理页面修改了采集配置
- When 点击"下发配置"
- Then 后端通过 MQTT QoS 2 发送配置到 dcim/{site_id}/gw/{gw_id}/config
- And 网关接收配置后热加载，无需重启
- And 配置下发结果（成功/失败）反馈到前端

**FR 追溯:** FR17

### Story 2.4: 离线缓存与断点续传

As a 运维工程师,
I want 网关在服务器断开时自动缓存数据,
So that 网络恢复后数据不丢失。

**Acceptance Criteria:**

- Given 网关与 MQTT Broker 断开连接
- When 网关继续采集设备数据
- Then 数据自动写入本地 SQLite upload_queue 表
- And 本地缓存容量支持至少 72 小时数据
- And 网络恢复后按时间戳顺序逐批上传（100条/批）
- And Broker ACK 后标记 uploaded=true，定期清理超过 72h 的已上传记录
- And 本地 SQLite 存储空间不足时（剩余 <10%），自动删除最旧的已上传记录腾出空间
- And 如果删除已上传记录后仍不足，覆盖最旧的未上传记录并记录数据丢失告警

**FR 追溯:** FR18, FR19

### Story 2.5: MQTT 数据上报链路

As a 开发者,
I want 后端通过 MQTT 客户端接收网关上报的数据,
So that 采集数据可以进入后端处理流水线。

**Acceptance Criteria:**

- Given FastAPI 启动时内嵌 MQTT 客户端（aiomqtt）
- When 网关通过 dcim/{site_id}/gw/{gw_id}/data 上报点位数据（批量 JSON）
- Then 后端并行执行：更新 Redis 最新值、写入 TimescaleDB（攒批100条或1秒）、告警引擎阈值检测、WebSocket 广播
- And MQTT 数据使用 QoS 1，控制命令使用 QoS 2
- And 支持 EMQX 共享订阅实现多消费者负载均衡

**FR 追溯:** FR15（通信链路部分）

### Story 2.6: Redis 缓存策略实现

As a 开发者,
I want 实现 Redis 缓存策略,
So that 实时数据可以通过缓存快速访问，支撑 WebSocket 推送和仪表盘展示。

**Acceptance Criteria:**

- Given Redis 服务已部署
- When 后端 MQTT 客户端接收到点位数据
- Then 更新 Redis 缓存，Key 模式如下：
  - point:{id}:latest (TTL 60s) — 最新点位值，WebSocket 推送源
  - gateway:{id}:status (TTL 30s) — 网关心跳状态，超时判断离线
  - device:{id}:online (TTL 60s) — 设备在线状态
  - alarm:stats:{level} (实时更新) — 告警统计计数
  - session:{user_id}:tokens (与 JWT 同步) — 并发会话限制
- And 实时数据 API 从 Redis 读取而非直接查库
- And Redis 连接断开时系统降级为直接查库模式

**FR 追溯:** Architecture 3.6, NFR-P4/P5

---

## Epic 3: 数据源管理 UI + 设备模板

**阶段:** MVP (月1-3)
**目标:** 提供数据源配置、点位批量导入、设备模板管理的前端界面，支撑集成工程师完成设备对接。
**FR 覆盖:** FR8, FR9, FR10, FR13, FR14
**架构参考:** Architecture 4.3 数据源管理 API, 4.4 点位批量导入预校验

### Story 3.1: 数据源配置管理

As a 集成工程师,
I want 在前端页面配置和管理数据源,
So that 我可以通过界面完成设备协议对接而不需要编辑配置文件。

**Acceptance Criteria:**

- Given 集成工程师在数据源管理页面
- When 创建新数据源
- Then 根据协议类型动态显示配置表单（Modbus TCP: IP/端口/从站地址; Modbus RTU: 串口/波特率/数据位/校验位; SNMP: 目标地址/团体名）
- And 支持数据源 CRUD 操作
- And 显示每个数据源的连接状态（连接/断开/通信中断）和最后通信时间
- And 支持"测试连接"按钮验证配置正确性

**FR 追溯:** FR8（部分）, FR10（部分）

### Story 3.2: 点位批量导入与预校验

As a 集成工程师,
I want 通过 Excel 批量导入点位配置,
So that 我可以快速完成大量点位的配置工作。

**Acceptance Criteria:**

- Given 集成工程师准备好点位配置 Excel 文件
- When 上传 Excel 文件
- Then 系统自动执行预校验：寄存器地址冲突检测、数据类型匹配验证、量程范围合理性检查
- And 返回校验报告（通过条目数、失败条目数、每条失败的错误原因）
- And 校验通过后可一键导入
- And 同步校验（Excel 通常几百到几千行，计算量不大）
- And Excel 文件格式错误（非 xlsx/xls）时返回明确错误提示
- And 文件大小超过 10MB 时拒绝上传并提示分批导入
- And 文件编码异常导致乱码时提示用户使用 UTF-8 编码

**FR 追溯:** FR8, FR9

### Story 3.3: 只读模式与写入权限管理

As a 集成工程师,
I want 新设备默认以只读模式对接,
So that 首次对接时不会误下发控制命令导致设备异常。

**Acceptance Criteria:**

- Given 新创建的数据源
- When 数据源首次启用
- Then DataSource.write_enabled 默认为 false，仅采集数据不下发控制命令
- And 集成工程师可在确认数据正常后逐台开启写入权限
- And 写入权限变更记录到操作日志

**FR 追溯:** FR10

### Story 3.4: 设备模板管理

As a 集成工程师,
I want 创建和管理设备模板,
So that 同厂商同型号的设备可以复用点位配置，避免重复配置。

**Acceptance Criteria:**

- Given 集成工程师在设备模板管理页面
- When 创建设备模板
- Then 可按厂商、型号分类，预置点位配置（寄存器地址、数据类型、量程、单位）
- And 从模板创建数据源时自动填充点位配置
- And 支持模板的 CRUD 和按厂商/型号查询

**FR 追溯:** FR13

### Story 3.5: 对接报告导出

As a 集成工程师,
I want 导出设备对接报告,
So that 我可以将对接结果交付给客户运维团队。

**Acceptance Criteria:**

- Given 集成工程师完成一批设备的对接
- When 点击"导出对接报告"
- Then 生成包含设备清单、点位映射表、通信参数、连接状态的报告文件
- And 报告格式为 Excel
- And 包含每台设备的对接时间和当前状态

**FR 追溯:** FR14

---

## Epic 4: 实时监控适配

**阶段:** MVP (月1-3)
**目标:** 将现有前端监控页面从模拟数据适配到真实采集数据，通过 Redis 缓存和 WebSocket 实现实时推送。
**FR 覆盖:** FR21, FR22, FR23, FR24, FR25, FR26（6 个 Story: 4.1, 4.1b, 4.2, 4.3, 4.4, 4.5）
**架构参考:** Architecture 10.2 数据流性能路径
**Story 依赖:** Story 4.1b 依赖 Story 4.1 的数据源切换框架

### Story 4.1: 数据源切换框架与供配电/制冷仪表盘适配

As a 运维工程师,
I want 在供配电和制冷仪表盘上查看真实设备的实时数据,
So that 我可以掌握机房核心子系统的实时运行状态。

**Acceptance Criteria:**

- Given 采集网关已接入真实设备并上报数据
- When 运维工程师打开监控仪表盘
- Then 通过环境变量 SIMULATION_ENABLED=true/false 控制模拟器开关：开发环境保留模拟器（true），生产环境关闭（false）
- And 模拟器关闭后，仪表盘数据来源从模拟器切换为 Redis 缓存的真实采集数据
- And 无数据的点位显示"--"
- And 供配电子系统仪表盘适配完成（数据源切换、WebSocket 实时推送）
- And 制冷子系统仪表盘适配完成
- And 数据刷新延迟小于 1 秒（WebSocket 推送）

**FR 追溯:** FR21, FR23

### Story 4.1b: 环境/安防/基础设施/能效仪表盘适配

As a 运维工程师,
I want 在环境、安防消防、智能基础设施、能效仪表盘上查看真实设备数据,
So that 我可以掌握机房所有子系统的实时运行状态。

**Acceptance Criteria:**

- Given Story 4.1 的数据源切换框架已完成
- When 运维工程师打开各子系统仪表盘
- Then 环境子系统仪表盘适配完成（温湿度、漏水、烟感等传感器数据）
- And 安防消防子系统仪表盘适配完成（干接点信号、门禁状态）
- And 智能基础设施子系统仪表盘适配完成
- And 能效子系统仪表盘适配完成（PUE 相关数据）
- And 所有子系统数据刷新延迟小于 1 秒（复用 Story 4.1 的 WebSocket 推送框架）

**FR 追溯:** FR21, FR23

### Story 4.2: 设备详情与历史曲线

As a 运维工程师,
I want 查看单台设备的详细信息和历史数据,
So that 我可以深入分析设备运行状况。

**Acceptance Criteria:**

- Given 运维工程师在设备列表中点击某台设备
- When 进入设备详情页
- Then 显示设备实时参数、关联点位列表、当前告警
- And 显示点位历史曲线（可选时间范围：1小时/6小时/24小时/7天/30天）
- And 历史数据查询 P95 小于 3 秒（TimescaleDB hypertable）

**FR 追溯:** FR22

### Story 4.3: 设备状态看板

As a 运维工程师,
I want 查看按区域和类型分组的设备状态看板,
So that 我可以快速了解哪些设备在线、离线或告警。

**Acceptance Criteria:**

- Given 运维工程师在设备状态看板页面
- When 页面加载
- Then 按区域/类型分组显示设备在线/离线/告警状态统计
- And 支持按区域、设备类型筛选
- And 设备在线状态基于 Redis 缓存（device:{id}:online，TTL 60s）

**FR 追溯:** FR24

### Story 4.4: 通信中断检测与展示

As a 运维工程师,
I want 系统自动检测数据源通信中断并显示影响范围,
So that 我可以快速判断是设备故障还是网络故障。

**Acceptance Criteria:**

- Given 某数据源连续 5 次采集失败
- When 系统标记该数据源为"通信中断"
- Then 前端显示中断时长和影响范围（受影响设备数、点位数）
- And 运维工程师可查看数据源连接状态（连接/断开、最后通信时间）
- And 受影响点位自动标记为"数据质量：不可靠"

**FR 追溯:** FR25, FR26

### Story 4.5: 优雅降级

As a 运维工程师,
I want 系统在部分组件故障时仍能使用,
So that 我不会因为某个服务异常而完全无法查看监控数据。

**Acceptance Criteria:**

- Given 系统正常运行中
- When Redis 连接断开
- Then 实时数据 API 降级为直接查询数据库，页面显示"实时数据可能有延迟"提示
- When WebSocket 连接断开
- Then 前端自动重连（指数退避），页面显示"连接中断，正在重连..."提示，并显示最后已知数据
- When MQTT Broker 不可用
- Then 后端记录错误日志，前端显示"数据采集服务异常"提示，历史数据查询仍可用
- And 所有降级状态在组件恢复后自动解除

**FR 追溯:** NFR-R2

---

## Epic 5: 告警管理增强

**阶段:** MVP (月1-3)
**目标:** 增强现有告警系统以支持真实设备告警，新增告警升级规则、数据质量标记、告警规则前端管理。
**FR 覆盖:** FR27, FR28, FR29, FR30, FR31, FR32, FR33, FR87
**架构参考:** Architecture 10.1 告警触发小于1s

### Story 5.1: 告警阈值配置增强

As a 系统管理员,
I want 为真实设备点位配置 4 级告警阈值,
So that 系统可以根据实际运行数据触发准确的告警。

**Acceptance Criteria:**

- Given 系统管理员在告警阈值配置页面
- When 为点位配置告警阈值
- Then 支持 4 级告警（提示、次要、重要、紧急），每级可设上限和下限
- And 阈值配置支持按设备类型批量设置
- And 配置变更实时生效，无需重启服务

**FR 追溯:** FR27

### Story 5.2: 实时告警触发与通知

As a 运维工程师,
I want 在点位数据超过阈值时立即收到告警通知,
So that 我可以及时响应异常情况。

**Acceptance Criteria:**

- Given 告警引擎在内存中缓存阈值配置
- When MQTT 客户端接收到点位数据且值超过阈值
- Then 在 1 秒内触发告警
- And 通过 WebSocket alarms 通道推送到前端
- And 前端显示声光报警提示（可配置声音开关）
- And 告警记录写入数据库
- And 告警风暴防护：同一点位在 1 分钟内重复越限不重复产生告警（抑制重复告警）
- And 大面积告警（同一数据源 >50% 点位同时越限）时自动标记为"疑似通信异常"，优先检查数据源状态

**FR 追溯:** FR28, FR29

### Story 5.3: 告警处理闭环

As a 运维工程师,
I want 对告警进行确认、处理和解除操作,
So that 告警有完整的处理记录和闭环流程。

**Acceptance Criteria:**

- Given 运维工程师在告警列表页面
- When 选择一条或多条告警
- Then 可执行确认（记录确认人和时间）、处理（记录处理过程）、解除操作
- And 支持批量确认
- And 告警统计支持按级别/区域/设备类型/时间段筛选
- And 告警记录永久保留

**FR 追溯:** FR30, FR31

### Story 5.4: 数据质量标记与误告警防护

As a 运维工程师,
I want 系统在通信中断时自动标记数据质量,
So that 不会基于过期数据产生误告警。

**Acceptance Criteria:**

- Given 某数据源通信中断
- When 系统检测到中断
- Then 受影响点位自动标记为"数据质量：不可靠"
- And 告警引擎跳过"不可靠"点位的阈值检测
- And 通信恢复后自动解除标记并恢复告警检测

**FR 追溯:** FR32

### Story 5.5: 告警升级规则与前端管理

As a 系统管理员,
I want 配置告警升级规则并通过前端管理告警规则,
So that 超时未处理的告警可以自动升级通知上级。

**Acceptance Criteria:**

- Given 系统管理员在告警规则管理页面
- When 创建告警升级规则
- Then 可配置：超时时间、升级后的告警级别、通知对象
- And 告警超时未处理时自动升级级别或通知上级
- And 前端支持告警规则的创建/编辑/删除/启用/禁用

**FR 追溯:** FR33, FR87

---

## Epic 6: 能源管理

**阶段:** MVP (基础) + Phase 2 (完整)
**目标:** 将现有能源管理模块适配真实电表数据，新增节能优化插件和效果追踪。
**FR 覆盖:** FR45, FR46, FR47, FR48, FR49, FR50, FR51, FR52, FR53
**架构参考:** Architecture 2.2 应用服务层 - 节能分析插件

### Story 6.1: PUE 监控与配电拓扑适配 [MVP]

As a 能源管理员,
I want 查看基于真实电表数据的 PUE 值和配电拓扑,
So that 我可以准确掌握数据中心的能效水平。

**Acceptance Criteria:**

- Given 电表设备已通过采集网关接入
- When 能源管理员打开 PUE 监控页面
- Then 显示基于真实电表读数计算的实时 PUE 值及历史趋势
- And 配电拓扑图（变压器-配电柜-PDU-机柜层级）显示真实功率数据
- And PUE 计算公式：总输入功率 / IT 负载功率
- And IT 负载功率为 0 或数据缺失时，PUE 显示为"--"（不可用），不进行除零计算

**FR 追溯:** FR45, FR46

### Story 6.2: 能耗统计与电价管理 [MVP]

As a 能源管理员,
I want 查看能耗统计和管理电价策略,
So that 我可以分析电费构成并优化用电成本。

**Acceptance Criteria:**

- Given 系统已积累能耗数据
- When 能源管理员查看能耗统计页面
- Then 显示日/月能耗统计、尖峰/高峰/平段/低谷/深谷五时段电费分析、同比/环比对比
- And 系统管理员可配置电价策略（尖峰/高峰/平段/低谷/深谷五时段，时段时间可调、电价费率可调）
- And 设备功率监控和负载率分析可用

**FR 追溯:** FR47, FR48, FR53

### Story 6.3: 节能机会自动识别 [Phase 2]

As a 能源管理员,
I want 系统自动识别节能机会,
So that 我可以发现潜在的电费节省空间。

**Acceptance Criteria:**

- Given 系统已积累足够的能耗基线数据
- When 节能分析插件运行
- Then 自动识别 6 种节能机会：峰谷套利、需量优化、PUE 优化、功率因数改善、负荷转移、设备效率提升
- And 每种机会附带预估节省金额和实施建议
- And 插件架构可扩展，新增插件不影响已有分析

**FR 追溯:** FR49

### Story 6.4: 节能方案执行与效果追踪 [Phase 2]

As a 能源管理员,
I want 选择节能方案并追踪执行效果,
So that 我可以验证节能措施的实际收益。

**Acceptance Criteria:**

- Given 能源管理员选择了一个节能方案
- When 设置执行计划并启动
- Then 系统自动生成调度时间表
- And 执行后实时追踪效果（对比电表实际读数与基线）
- And 可导出能效报告（含 PUE 趋势、电费对比、节能成果）

**FR 追溯:** FR50, FR51, FR52

### Story 6.5: 能效报告导出 [Phase 2]

As a 能源管理员,
I want 导出月度能效报告,
So that 我可以向管理层汇报能耗和节能成果。

**Acceptance Criteria:**

- Given 能源管理员在能效报告页面
- When 选择时间范围并点击导出
- Then 生成包含 PUE 趋势、电费对比、节能成果、同比环比分析的报告
- And 支持 Excel 和 PDF 格式导出

**FR 追溯:** FR52

---

## Epic 7: 资产与容量管理

**阶段:** Phase 1.5 (基础) + Phase 2 (完整)
**目标:** 实现设备资产全生命周期管理和四维容量监控，支持机柜上架推荐。
**FR 覆盖:** FR54, FR55, FR56, FR57, FR58, FR59, FR60, FR61（6 个 Story）

### Story 7.1: 资产台账管理 [Phase 1.5]

As a 资产管理员,
I want 录入和管理设备资产信息,
So that 我可以掌握所有设备的基本信息和归属。

**Acceptance Criteria:**

- Given 资产管理员在资产管理页面
- When 录入设备资产
- Then 可填写 SN 码、型号、厂商、保修期、所属机柜、U 位位置等信息
- And 支持批量导入设备资产（Excel）
- And 支持按类型/厂商/状态/机柜筛选和搜索

**FR 追溯:** FR54, FR55

### Story 7.2: 机柜 U 位可视化 [Phase 1.5]

As a 资产管理员,
I want 查看机柜 U 位占用可视化图,
So that 我可以直观了解每个机柜的空间使用情况。

**Acceptance Criteria:**

- Given 资产管理员在机柜详情页面
- When 查看 U 位图
- Then 以可视化方式显示 42U 机柜的每个 U 位占用情况（已用/空闲/预留）
- And 已用 U 位显示设备名称和型号
- And 支持拖拽调整设备位置

**FR 追溯:** FR56

### Story 7.3: 资产生命周期与保修预警 [Phase 2]

As a 资产管理员,
I want 系统自动记录资产生命周期并在保修到期前预警,
So that 我可以及时安排维保和更换。

**Acceptance Criteria:**

- Given 资产已录入系统
- When 资产状态发生变化（入库、上架、维修、下架、报废）
- Then 系统自动记录生命周期事件（时间、操作人、变更内容）
- And 保修到期前 30/60/90 天自动发送预警提醒
- And 资产管理员可查看完整的生命周期时间线

**FR 追溯:** FR57, FR58

### Story 7.4: 四维容量监控 [Phase 2]

As a 资产管理员,
I want 查看空间/电力/制冷/承重容量使用情况,
So that 我可以评估机房的剩余容量。

**Acceptance Criteria:**

- Given 机柜和设备数据已录入
- When 资产管理员查看容量管理页面
- Then 显示空间容量（U 位使用率）、电力容量（功率使用率）、制冷容量（制冷负荷率）、承重容量（重量使用率）
- And 支持按区域/楼层/房间维度聚合查看
- And 容量使用率超过阈值（如 80%）时高亮预警

**FR 追溯:** FR59

### Story 7.5: 智能上架推荐 [Phase 2]

As a 资产管理员,
I want 获取系统推荐的最优上架位置,
So that 新设备可以放置在最合适的机柜中。

**Acceptance Criteria:**

- Given 资产管理员输入新设备需求（U 位数、额定功率、重量）
- When 请求上架推荐
- Then 系统返回至少 3 个候选机柜，每个附带空间/电力/制冷/承重多维度评分
- And 评分基于当前容量数据（简化版，不含三相平衡和温度场）
- And 支持人工覆盖推荐结果

**FR 追溯:** FR60

> 注：FR60 为基于容量数据的简化版推荐（空间+电力+制冷+承重）。FR65 为基于三合一拓扑模型的增强版智能选址（额外加入三相平衡度+温度环境），见 Epic 8 Story 8.3。两者为递进关系。

### Story 7.6: 容量趋势预测 [Phase 2]

As a 运维主管,
I want 查看容量趋势预测和扩容建议,
So that 我可以提前规划机房扩容，避免容量不足影响业务。

**Acceptance Criteria:**

- Given 系统已积累至少 3 个月的容量历史数据
- When 运维主管查看容量预测页面
- Then 显示空间/电力/制冷/承重四维容量的趋势预测（基于历史数据线性回归预测未来 3/6/12 个月）
- And 预测结果附带置信区间
- And 当预测容量将在 N 个月内超过阈值时，自动生成扩容建议
- And 扩容建议包含具体的资源需求量和预估时间点

**FR 追溯:** FR61

---

## Epic 8: 机房物理拓扑 + 智能选址

**阶段:** Phase 2 (月7-9)
**目标:** 构建配电+空间+制冷三合一拓扑模型，实现多维度智能机柜选址推荐（核心创新功能）。
**FR 覆盖:** FR62, FR63, FR64, FR65, FR66
**架构参考:** Architecture 9.1-9.5 机房物理拓扑模型

### Story 8.1: 空间拓扑配置

As a 集成工程师,
I want 配置机柜的物理位置和空间层级,
So that 系统可以建立完整的空间拓扑模型。

**Acceptance Criteria:**

- Given 集成工程师在物理拓扑配置页面
- When 配置机柜物理位置
- Then 可设置行列号、冷热通道归属、楼层/房间/区域层级（Site-Floor-Room-Row-Cabinet）
- And 支持 Excel 批量导入机柜位置
- And 支持可视化拖拽配置
- And 提供常见机房布局模板（2N 冷通道、单排、双排等）

**FR 追溯:** FR62

### Story 8.2: 配电与制冷拓扑配置

As a 集成工程师,
I want 配置 PDU 三相接线关系和空调覆盖范围,
So that 系统可以建立完整的配电和制冷拓扑。

**Acceptance Criteria:**

- Given 集成工程师在拓扑配置页面
- When 配置配电拓扑
- Then 可设置每个机柜接哪个 PDU 的哪一相（A/B/C）
- And 可配置空调覆盖范围（每台空调服务哪些机柜/冷通道分组）
- And 三相不平衡度自动计算：(max-min)/avg x 100%
- And Cabinet 作为三个拓扑的交汇点

**FR 追溯:** FR63, FR64

### Story 8.3: 多维度智能选址推荐

As a 资产管理员,
I want 获取基于三合一拓扑模型的智能选址推荐,
So that 新设备可以放置在空间、电力、温度、制冷综合最优的位置。

**Acceptance Criteria:**

- Given 三合一拓扑模型已配置完成
- When 资产管理员输入新设备需求（U 位数、额定功率、重量）
- Then 系统返回 Top N 候选机柜，每个附带多维度评分卡：空间容量(30%)、电力容量(25%)、三相平衡度(20%)、温度环境(15%)、制冷余量(10%)
- And 机柜平面图上用颜色标注各维度评分（绿/黄/红）
- And 数据不足时降级推荐并标注置信度（高/中/低）
- And 权重默认固定，管理员可通过系统配置调整

**FR 追溯:** FR65

> 注：FR65 为基于三合一拓扑模型的增强版智能选址（空间+电力+三相平衡度+温度环境+制冷余量五维评分）。FR60（Epic 7 Story 7.5）为基于容量数据的简化版推荐。两者为递进关系，FR65 在 FR60 基础上增加三相平衡和温度维度。

### Story 8.4: 故障影响分析

As a 运维工程师,
I want 在配电设备故障时快速定位受影响的设备,
So that 我可以评估故障影响范围并采取应急措施。

**Acceptance Criteria:**

- Given 配电拓扑已配置
- When 配电柜/PDU 发生故障告警
- Then 系统基于拓扑模型自动定位受影响的下游机柜和设备
- And 同时检查制冷拓扑，判断受影响区域空调是否同回路
- And 输出影响报告（设备清单、关联告警、建议操作）

**FR 追溯:** FR66

---

## Epic 9: 联动引擎 + 消防联动

**阶段:** Phase 2 (月7-9)
**目标:** 构建事件驱动的联动引擎，实现消防分级联动策略，支持自动执行和恢复流程。
**FR 覆盖:** FR35, FR36, FR37, FR38, FR39（7 个 Story）（注：FR34 已拆分到 Epic 24-26，Story 9.3 仅保留编号）
**架构参考:** Architecture 7.1-7.7 消防分级联动引擎

### Story 9.1: 联动引擎核心框架

As a 开发者,
I want 一个事件驱动的联动引擎,
So that 系统可以在特定事件触发时自动执行预设动作序列。

**Acceptance Criteria:**

- Given 联动引擎订阅 Redis Pub/Sub 事件总线
- When 告警引擎或 MQTT 客户端产生事件
- Then 联动引擎评估条件并执行匹配的策略
- And 动作执行器通过 asyncio.gather 并行执行所有动作，每个动作独立超时（3s）
- And 单个动作失败不阻塞其他动作
- And 支持动作类型：MQTT_COMMAND、ALARM_NOTIFY、VIDEO_RECORD、VIDEO_POPUP、WEBHOOK

**FR 追溯:** FR36

### Story 9.2: 消防分级联动策略

As a 运维工程师,
I want 系统支持消防分级联动,
So that 火灾信号可以触发自动应急响应，保障人员和设备安全。

**Acceptance Criteria:**

- Given 消防联动策略已通过 YAML 预定义
- When 单一传感器触发（烟雾 OR VESDA）
- Then 执行预警级别：发送预警通知 + 调取区域摄像头 + 等待确认，响应时间小于 5 秒
- When 多传感器交叉确认 或 消防主机干接点信号
- Then 执行联动级别：关空调 + 启排烟 + 切非关键电源 + 解锁门禁 + 应急照明 + 全区录像 + 紧急通知，响应时间小于 3 秒
- And 消防信号（FIRE_SIGNAL）跳过排队立即评估执行
- And 消防联动不需要双重确认（生命安全优先，GB 50116）
- And 联动动作部分失败时（如空调关闭成功但门禁解锁失败），已成功的动作不回滚，失败动作立即重试 1 次
- And 所有动作执行结果（成功/失败/超时）强制记录到联动日志，无论成功与否
- And 联动执行完成后如有失败动作，立即发送告警通知运维工程师人工介入

**FR 追溯:** FR37

### Story 9.3: 智能故障诊断（已拆分）

> **注意**: 此 Story 已被 Epic 24/25/26（智能诊断系统）替代。PRD FR34 已细化为 FR34-1~FR34-42，对应 3 个独立 Epic。此 Story 保留编号以维持连续性，状态标记为"已拆分"。

**FR 追溯:** FR34 → 已拆分为 Epic 24 (FR34-1~12,16~19,29), Epic 25 (FR34-8,13~15,22~26,30~32), Epic 26 (FR34-3,20~21,27~28,33~42)

### Story 9.4: 联动恢复流程

As a 运维工程师,
I want 在事件解除后执行联动恢复,
So that 设备可以安全有序地恢复到正常状态。

**Acceptance Criteria:**

- Given 消防联动已执行，现场确认安全
- When 运维工程师执行"联动恢复"
- Then 支持一键恢复（按预设顺序：门禁-照明-电源-空调-排烟-录像）
- And 支持逐项手动恢复（可跳过某些项或调整顺序）
- And 恢复过程中每步操作记录到事件日志

**FR 追溯:** FR38

### Story 9.5: 事件时间线报告

As a 运维主管,
I want 查看完整的事件时间线报告,
So that 我可以进行事后复盘和合规存档。

**Acceptance Criteria:**

- Given 一次联动事件已完成（含恢复）
- When 查看事件报告
- Then 显示完整时间线：event_id、trigger_time（毫秒精度）、trigger_source、level、每个动作的开始/结束时间和结果、total_duration、recovery_time、operator
- And 报告可导出用于合规存档
- And 联动记录永久保存

**FR 追溯:** FR39

### Story 9.6: 控制命令分级确认

As a 运维工程师,
I want 系统对不同风险等级的控制命令执行不同的确认流程,
So that 高风险操作有足够的安全把关，低风险操作不影响效率。

**Acceptance Criteria:**

- Given 运维工程师在前端发起控制命令（如调整空调温度、切断电源、开关门禁）
- When 命令风险等级为"普通"（如调整空调设定温度、开关照明）
- Then 前端弹出二次确认弹窗，用户确认后直接通过 MQTT QoS 2 下发
- When 命令风险等级为"关键"（如切断回路电源、设备下架断电、UPS 切换）
- Then 前端提交审批请求，后端创建审批工单，审批人确认后才下发命令
- And 审批超时（默认 30 分钟）自动取消并通知发起人
- And 所有控制命令（无论级别）记录到操作审计日志（操作人、命令内容、目标设备、执行结果）
- And 命令风险等级通过系统配置定义，管理员可调整

**FR 追溯:** Architecture 4.5, NFR-S4

### Story 9.7: 传感器数据漂移检测

As a 运维工程师,
I want 系统自动检测传感器数据漂移,
So that 我可以及时发现传感器老化或故障，避免基于错误数据做出误判。

**Acceptance Criteria:**

- Given 系统已积累至少 48 小时的点位历史数据
- When 数据质量检测模块运行
- Then 对每个点位计算 3σ 统计偏差，偏差超过阈值标记为"疑似漂移"
- And 对同区域相邻传感器执行交叉验证，偏差持续扩大时确认漂移
- And 漂移点位在仪表盘上用黄色标记提示"数据可信度：低"
- And 系统生成诊断建议（如"建议现场校验或更换"）
- And 传感器更换后系统自动解除漂移标记

**FR 追溯:** FR35

---

## Epic 10: 视频监控集成

**阶段:** Phase 2 (月7-9)
**目标:** 集成视频监控系统，实现告警联动调取、区域录像、云台控制、告警回放。
**FR 覆盖:** FR40, FR41, FR42, FR43, FR44
**架构参考:** Architecture 8.1-8.6 视频监控集成架构

### Story 10.1: 摄像头元数据管理

As a 系统管理员,
I want 管理摄像头和 NVR 的元数据,
So that 系统知道每个摄像头的位置和关联区域。

**Acceptance Criteria:**

- Given 系统管理员在视频管理页面
- When 录入摄像头信息
- Then 可配置：名称、RTSP URL、ONVIF URL、关联 NVR、位置描述、关联区域/机柜/设备
- And 支持预置位列表配置（联动快速定位）
- And 视频流由前端直接从 NVR 拉取（RTSP/HLS），不经过后端

**FR 追溯:** FR44

### Story 10.2: 告警联动视频调取

As a 运维工程师,
I want 告警触发时自动弹出关联摄像头画面,
So that 我可以远程查看现场情况。

**Acceptance Criteria:**

- Given 告警触发且关联设备有对应摄像头
- When 系统通过 设备-区域-摄像头 关联链找到最近摄像头
- Then 前端自动弹出摄像头实时画面
- And 支持分屏布局（1/4/9 分屏，CSS Grid 实现）
- And 联动触发时自动切换到关联摄像头的 4 分屏布局

**FR 追溯:** FR40

### Story 10.3: 区域联动录像与云台控制

As a 运维工程师,
I want 在特定事件时自动触发录像并远程控制云台,
So that 关键事件有视频记录且可以远程定位到具体设备。

**Acceptance Criteria:**

- Given 消防联动/资产变更/现场调试等事件触发
- When 联动引擎发送 VIDEO_RECORD 动作
- Then 通过 ONVIF 命令触发 NVR 开始区域录像并标记时间戳
- And 运维工程师可远程控制摄像头云台（方向、聚焦），后端转发 PTZ 命令并记录操作日志
- And DCIM 记录 VideoEvent（事件时间、关联告警、摄像头 ID）

**FR 追溯:** FR41, FR42

### Story 10.4: 告警回放

As a 运维工程师,
I want 通过告警时间快速定位历史录像,
So that 我可以回放告警发生时的现场画面进行复盘。

**Acceptance Criteria:**

- Given 运维工程师在告警详情页面
- When 点击"查看录像"
- Then 通过告警时间戳定位到 NVR 录像片段
- And 录像回放由 NVR 负责，DCIM 只提供时间定位
- And 支持前进/后退/倍速播放

**FR 追溯:** FR43

---

## Epic 11: 运维管理

**阶段:** Phase 2 (月7-9)
**目标:** 实现工单管理、巡检管理和知识库，支撑运维工作流自动化。
**FR 覆盖:** FR67, FR68, FR69, FR70, FR71（5 个 Story）

### Story 11.1: 工单管理

As a 运维工程师,
I want 通过系统创建和处理工单,
So that 运维工作有完整的流程记录和跟踪。

**Acceptance Criteria:**

- Given 告警触发或运维工程师手动创建工单
- When 工单创建
- Then 系统按规则自动派发给对应人员（按区域/设备类型/值班表）
- And 工单支持完整生命周期：创建-分配-接单-执行-完成-关闭
- And 工单状态变更自动记录日志
- And 支持按状态/优先级/创建时间筛选工单列表

**FR 追溯:** FR67, FR68

### Story 11.2: 巡检计划与任务

As a 运维主管,
I want 创建巡检计划并自动生成巡检任务,
So that 巡检工作规范化且不会遗漏。

**Acceptance Criteria:**

- Given 运维主管在巡检管理页面
- When 创建巡检计划
- Then 可配置巡检路线、检查项、周期（每日/每周/每月）
- And 系统按计划自动生成巡检任务（APScheduler 定时任务）
- And 运维工程师可在任务中逐项记录巡检结果（正常/异常/备注）

**FR 追溯:** FR69, FR70

### Story 11.3: 知识库

As a 运维工程师,
I want 查阅和维护知识库,
So that 故障处理经验和操作规程可以积累和共享。

**Acceptance Criteria:**

- Given 运维工程师在知识库页面
- When 搜索或浏览知识库
- Then 支持按分类浏览（故障处理、操作规程、设备手册）
- And 支持关键词搜索
- And 支持创建/编辑文章（富文本编辑器）
- And 记录文章浏览量

**FR 追溯:** FR71

### Story 11.4: 告警自动创建工单

As a 运维工程师,
I want 重要告警自动创建工单,
So that 关键问题不会被遗漏。

**Acceptance Criteria:**

- Given 系统管理员配置了告警-工单关联规则
- When 重要或紧急级别告警触发
- Then 系统自动创建工单并派发
- And 工单关联原始告警记录
- And 告警确认后工单自动更新状态

**FR 追溯:** FR67（自动创建部分）

### Story 11.5: 工单审批流程

As a 运维主管,
I want 关键操作工单需要审批才能执行,
So that 高风险操作有管理层把关，降低误操作风险。

**Acceptance Criteria:**

- Given 工单涉及关键操作（如切断电源、设备下架）
- When 工单提交执行
- Then 系统自动触发审批流程，通知审批人
- And 审批人可批准或驳回，驳回需填写原因
- And 审批通过后工单自动流转到执行状态
- And 审批超时自动升级到上级审批人
- And 审批记录完整保存用于审计

**FR 追溯:** FR68（审批部分）

---

## Epic 12: 报表与决策支持

**阶段:** Phase 2 (月7-9)
**目标:** 实现自动报表生成、智能摘要面板、PDF 导出和设备健康度评估。
**FR 覆盖:** FR72, FR73, FR74, FR75, FR85

### Story 12.1: 自动运行报表

As a 运维主管,
I want 系统自动生成运行报表,
So that 我可以定期了解机房运行状况。

**Acceptance Criteria:**

- Given 系统已积累运行数据
- When 到达报表生成时间（日报/周报/月报）
- Then 系统自动生成报表，包含告警趋势、能耗对比、工单统计、设备可用率
- And 报表支持同比/环比分析图表
- And 报表记录保存到 ReportRecord 表

**FR 追溯:** FR72

### Story 12.2: 智能摘要面板

As a 运维主管,
I want 登录后看到需要我决策的事项摘要,
So that 我可以快速了解当前最重要的待办事项。

**Acceptance Criteria:**

- Given 运维主管登录系统
- When 查看摘要面板
- Then 显示按优先级排序的待处理事项：告警升级、设备维保到期、容量预警、工单审批等
- And 每项附带推荐操作和相关数据链接
- And 点击可直接跳转到对应功能页面

**FR 追溯:** FR73

### Story 12.3: PDF 报表导出

As a 运维主管,
I want 将报表导出为 PDF 格式,
So that 我可以打印或分享给不使用系统的人。

**Acceptance Criteria:**

- Given 运维主管在报表页面查看已生成的报表
- When 点击"导出 PDF"
- Then 生成包含统计数据、图表和分析的 PDF 文件
- And PDF 包含报表标题、时间范围、统计表格、趋势图表
- And 后端使用 reportlab 或 weasyprint 生成 PDF

**FR 追溯:** FR74, FR85

### Story 12.4: 设备健康度评估

As a 运维主管,
I want 查看设备健康度评估,
So that 我可以提前规划维保和更换。

**Acceptance Criteria:**

- Given 系统已积累设备运行数据和维保记录
- When 查看设备健康度页面
- Then 显示每台设备的健康度评分（0-100）和状态等级（健康/关注/预警/危险）
- And 评分基于运行数据（如 UPS 电池 SOH）和维保记录
- And 支持按健康度排序，优先关注低分设备

**FR 追溯:** FR75

---

## Epic 13: 用户与系统管理

**阶段:** MVP (月1-3)
**目标:** 完善用户管理前端页面、RBAC 权限体系、操作审计和系统健康监控。
**FR 覆盖:** FR76, FR77, FR78, FR79, FR80, FR81, FR82, FR84（6 个 Story）

### Story 13.1: 用户管理前端页面

As a 系统管理员,
I want 通过前端页面完成用户管理全部操作,
So that 我不需要直接操作数据库来管理用户。

**Acceptance Criteria:**

- Given 系统管理员在用户管理页面
- When 执行用户管理操作
- Then 支持创建、编辑、删除用户账号（支持批量操作）
- And 支持分配用户角色（管理员/操作员/只读）
- And 支持启用/禁用用户
- And 仅 admin 角色可访问此页面

**FR 追溯:** FR76, FR77, FR84

### Story 13.2: 认证与会话管理增强

As a 系统管理员,
I want 完善的认证和会话管理机制,
So that 系统安全性满足等保二级要求。

**Acceptance Criteria:**

- Given 用户登录系统
- When 认证流程执行
- Then JWT Token 过期自动登出
- And 支持并发会话限制（Redis session 集合，超限踢出最早会话）
- And 密码使用 bcrypt 哈希存储
- And 登录限流 5 次/分钟防暴力破解
- And JWT Token 签名验证失败（被篡改）时返回 401 并记录安全告警日志
- And 并发会话超过限制时踢出最早的会话，被踢出用户下次请求返回 401 并提示"会话已在其他设备登录"

**FR 追溯:** FR78

### Story 13.3: 操作审计日志

As a 系统管理员,
I want 查看完整的操作审计日志,
So that 我可以追踪所有用户操作满足合规要求。

**Acceptance Criteria:**

- Given 系统管理员在操作日志页面
- When 查看日志
- Then 显示操作日志列表（时间、用户、操作类型、详情、IP 地址）
- And 支持按时间范围/用户/操作类型筛选
- And 日志保留至少 180 天
- And 审计记录采用追加写入模式，普通管理员无权删除或修改

**FR 追溯:** FR79

### Story 13.4: 数据备份与系统健康

As a 系统管理员,
I want 管理数据备份策略并监控系统健康状态,
So that 数据安全有保障且系统问题可以及时发现。

**Acceptance Criteria:**

- Given 系统管理员在系统管理页面
- When 查看备份和健康状态
- Then 可配置自动备份策略（每日备份时间、保留份数）
- And 支持手动备份和恢复
- And 显示系统健康状态：服务运行状态、数据库连接、Redis 连接、EMQX 连接、存储使用率

**FR 追溯:** FR80, FR81

### Story 13.5: 站点级数据隔离

As a 运维主管,
I want 在统一视图中查看多站点数据,
So that 我可以跨站点对比分析，而运维人员只能看到自己负责的站点。

**Acceptance Criteria:**

- Given 系统已配置多个站点
- When 运维主管登录
- Then 可在统一视图中查看和切换多站点数据
- And 运维人员仅可见其权限范围内的站点数据
- And 数据隔离通过行级 site_id 字段实现，FastAPI 中间件自动注入查询过滤

**FR 追溯:** FR82

### Story 13.6: 密码策略管理

As a 系统管理员,
I want 系统强制执行密码复杂度要求,
So that 用户账号安全性满足等保二级要求。

**Acceptance Criteria:**

- Given 用户创建或修改密码
- When 提交新密码
- Then 系统校验密码复杂度：最少 8 位，包含大写字母、小写字母、数字、特殊字符中至少 3 类
- And 密码不能与最近 5 次历史密码相同
- And 密码超过 90 天未更换时，登录后提示更换（非强制）
- And 系统管理员可在系统配置中调整密码策略参数

**FR 追溯:** NFR-S7

---

## Epic 14: 棕地改进 - 代码质量与测试

**阶段:** MVP (月1-3，与其他 Epic 并行)
**目标:** 提升现有代码质量，补全自动化测试，完善缺失的前端页面。
**FR 覆盖:** FR83, FR86, FR88, NFR-E5, NFR-M3（6 个 Story）

### Story 14.1: 后端自动化测试套件

As a 开发者,
I want 核心模块有完整的自动化测试,
So that 代码变更不会导致功能回归。

**Acceptance Criteria:**

- Given 测试框架已配置（pytest + httpx AsyncClient）
- When 运行 pytest
- Then 核心模块（认证/告警/能源/资产/运维）测试覆盖率达到 80% 以上
- And 覆盖：登录/权限/token 刷新、告警 CRUD/统计、能源 PUE/统计、资产 CRUD/生命周期、工单/巡检
- And 所有测试通过

**FR 追溯:** FR83

### Story 14.2: 独立设备管理页面

As a 运维工程师,
I want 一个独立的设备管理页面,
So that 我可以查看和编辑单台设备的完整信息。

**Acceptance Criteria:**

- Given 运维工程师在设备管理页面
- When 查看设备列表
- Then 显示设备列表（编码、名称、类型、区域、状态、厂商、型号）
- And 点击设备进入详情页，显示基本信息、关联点位、告警规则、历史数据
- And 路由路径与点位管理分离

**FR 追溯:** FR86

### Story 14.3: TypeScript 类型检查零错误

As a 开发者,
I want 前后端类型检查零错误,
So that 类型错误在编译时被捕获，提升代码可维护性。

**Acceptance Criteria:**

- Given 运行类型检查命令
- When 前端执行 npm run typecheck
- Then 零 TypeScript 错误
- When 后端执行 pyright 检查
- Then 零类型错误
- And 所有 API 响应类型与后端 schema 一致

**FR 追溯:** FR88

### Story 14.4: 前端关键组件测试

As a 开发者,
I want 关键前端组件有单元测试,
So that UI 组件的行为和渲染正确。

**Acceptance Criteria:**

- Given 前端测试框架已配置（Vitest + Vue Test Utils）
- When 运行 npm run test
- Then 覆盖：登录表单、仪表盘统计卡片、告警列表、能源图表
- And 覆盖：路由守卫、权限指令、API 拦截器
- And 所有测试通过

**FR 追溯:** FR83（前端部分）

### Story 14.5: 数据库迁移与 TimescaleDB 配置

As a 开发者,
I want 将数据库从 SQLite 迁移到 PostgreSQL + TimescaleDB,
So that 系统可以支撑生产环境的并发和时序数据存储需求。

**Acceptance Criteria:**

- Given 现有系统使用 SQLite (dcim.db)
- When 执行数据库迁移
- Then Alembic 迁移脚本覆盖所有现有表结构
- And point_history 表在初始迁移中即创建为 TimescaleDB hypertable（按 time 列分区，chunk 间隔 1 天）
- And 配置 7 天后自动压缩策略和 90 天原始数据保留策略
- And 开发环境可通过环境变量切换 SQLite/PostgreSQL（DATABASE_URL 配置）
- And 启动时自动创建表和初始数据（admin 用户、默认配置）
- And 现有 Alembic 迁移历史兼容

**FR 追溯:** NFR-E5, Architecture 3.5/3.7

### Story 14.6: Docker Compose 一键部署

As a 运维工程师,
I want 通过 Docker Compose 一键部署整个系统,
So that 部署过程标准化且可重复。

**Acceptance Criteria:**

- Given docker-compose.yml 已配置
- When 执行 docker-compose up -d
- Then 以下服务全部启动：FastAPI app (8080)、Nginx (3000)、PostgreSQL+TimescaleDB (5432)、Redis (6379)、EMQX (1883/8083/18083)
- And Nginx 正确代理前端静态文件和 API/WebSocket 请求
- And 服务间依赖关系正确（app 等待 postgres 和 redis 就绪）
- And 提供 .env.example 文件说明所有可配置环境变量
- And 支持 docker-compose down 完整停止所有服务

**FR 追溯:** NFR-M3, Architecture 5.5

---

## Epic 15: 协议扩展

**阶段:** Phase 1.5 (MQTT/HTTP) + Phase 2 (BACnet/OPC-UA/OTA)
**目标:** 基于 Epic 1 的插件化框架，扩展更多协议适配器，实现 OTA 网关升级。
**FR 覆盖:** FR3, FR4, FR5, FR6, FR20
**架构参考:** Architecture 6.2 适配器注册表

### Story 15.1: MQTT 设备适配器 [Phase 1.5]

As a 集成工程师,
I want 通过 MQTT 协议接入 IoT 传感器,
So that 轻量级传感器可以直接通过 MQTT 上报数据。

**Acceptance Criteria:**

- Given 集成工程师配置 MQTT 数据源（Broker 地址、Topic 订阅、消息解析规则）
- When IoT 传感器发布 MQTT 消息
- Then MqttDeviceAdapter 订阅指定 Topic 并按解析规则提取点位数据
- And 支持 JSON 和自定义格式消息解析
- And 复用网关 MQTT 通信能力

**FR 追溯:** FR5

### Story 15.2: HTTP REST 适配器 [Phase 1.5]

As a 集成工程师,
I want 通过 HTTP REST 协议对接第三方系统,
So that 可以与其他 DCIM 或管理系统交换数据。

**Acceptance Criteria:**

- Given 集成工程师配置 HTTP REST 数据源（URL、请求方式、认证方式、数据解析规则）
- When 采集调度器触发
- Then HttpRestAdapter 发送 HTTP 请求并解析响应数据
- And 支持 GET/POST 请求方式
- And 支持 Basic Auth 和 Bearer Token 认证

**FR 追溯:** FR6

### Story 15.3: BACnet/IP 适配器 [Phase 2]

As a 集成工程师,
I want 通过 BACnet/IP 协议采集楼宇自控设备,
So that 空调、照明等楼宇设备可以接入 DCIM。

**Acceptance Criteria:**

- Given 集成工程师配置 BACnet/IP 数据源（设备实例、对象标识符映射）
- When 采集调度器触发
- Then BacnetIpAdapter 通过 BAC0/bacpypes3 读取 BACnet 对象属性
- And 支持双向通信（读取+控制）
- And 支持设备发现和对象列表浏览

**FR 追溯:** FR3

### Story 15.4: OPC-UA 适配器 [Phase 2]

As a 集成工程师,
I want 通过 OPC-UA 协议采集工业设备数据,
So that 高端工业设备可以接入 DCIM。

**Acceptance Criteria:**

- Given 集成工程师配置 OPC-UA 数据源（端点 URL、节点 ID 映射、证书认证）
- When 采集调度器触发
- Then OpcUaAdapter 通过 asyncua 异步读取指定节点数据
- And 支持证书认证
- And 支持节点浏览和订阅模式

**FR 追溯:** FR4

### Story 15.5: OTA 网关升级 [Phase 2]

As a 运维工程师,
I want 远程升级网关固件,
So that 网关可以获得新功能和安全补丁而不需要到现场。

**Acceptance Criteria:**

- Given 运维工程师在网关管理页面选择目标网关
- When 触发 OTA 升级
- Then 后端通过 MQTT QoS 2 发送升级指令到 dcim/{site_id}/gw/{gw_id}/ota
- And 网关下载升级包到 B 分区，验证后切换启动
- And 升级失败自动回滚到 A 分区
- And 支持分批升级和灰度发布策略

**FR 追溯:** FR20

---

## Epic 16: 多站点集中管理

**阶段:** 推广阶段 (月10-12)
**目标:** 支持多机房统一管理，实现站点切换、跨站点汇总和数据隔离。
**FR 覆盖:** FR82（扩展）
**架构参考:** Architecture 5.4 多站点集中管理

### Story 16.1: 站点管理

As a 系统管理员,
I want 管理多个站点,
So that 不同机房可以在统一平台上管理。

**Acceptance Criteria:**

- Given 系统管理员在站点管理页面
- When 创建新站点
- Then 可配置站点名称、地址、联系人、网络配置
- And 所有业务表通过 site_id 字段实现行级数据隔离
- And EMQX ACL 按 site_id 隔离 Topic 权限

**FR 追溯:** FR82（站点管理部分）

### Story 16.2: 站点切换与统一视图

As a 运维主管,
I want 在统一界面中切换和对比多站点数据,
So that 我可以全局掌握所有机房的运行状况。

**Acceptance Criteria:**

- Given 运维主管有多站点查看权限
- When 在顶部导航栏切换站点
- Then 所有页面数据切换到目标站点
- And 支持"全部站点"视图，汇总显示所有站点的关键指标
- And 支持跨站点报表和对比分析

**FR 追溯:** FR82（统一视图部分）

### Story 16.3: 多站点网关接入

As a 运维工程师,
I want 各机房网关通过 MQTT 连接到中心平台,
So that 远程机房的数据可以汇聚到统一平台。

**Acceptance Criteria:**

- Given 各机房网关通过 VPN/专线连接中心 EMQX Broker
- When 网关上报数据
- Then 数据按 site_id 路由到对应站点的数据空间
- And 网关离线时本地 SQLite 缓存，恢复后断点续传
- And 支持从单站点平滑扩展到 200 台设备

**FR 追溯:** FR82（多站点接入部分）

---

## 需求清单

### 功能需求 (FR1-FR88)

#### 数据采集与协议管理

- FR1: 配置 Modbus TCP/RTU 数据源（IP/串口参数、从站地址、寄存器映射）
- FR2: 配置 SNMP v2c/v3 数据源（目标地址、团体名/认证参数、OID 映射）
- FR3: 配置 BACnet/IP 数据源（设备实例、对象标识符映射）
- FR4: 配置 OPC-UA 数据源（端点 URL、节点 ID 映射、证书认证）
- FR5: 配置 MQTT 数据源（Broker 地址、Topic 订阅、消息解析规则）
- FR6: 配置 HTTP REST 数据源（URL、请求方式、数据解析规则）
- FR7: 对数据源执行连接测试，验证通信参数
- FR8: 通过 Excel 批量导入点位配置表
- FR9: 点位导入时自动预校验（寄存器地址冲突、数据类型匹配、量程范围合理性）
- FR10: 默认只读模式首次对接设备，逐台开启写入权限
- FR11: 按可配置周期（1~60 秒）自动采集设备数据
- FR12: 支持干接点信号通过 Modbus I/O 采集模块转换接入
- FR13: 创建和管理设备模板（按厂商/型号预置点位配置）
- FR14: 导出对接报告（设备清单、点位映射、通信参数）

#### 采集网关管理

- FR15: 采集网关上线时自动注册到平台并分配唯一标识
- FR16: 查看网关运行状态（在线/离线、CPU/内存/磁盘使用率）
- FR17: 远程向网关下发采集配置（数据源参数、点位表）
- FR18: 网关断连时自动本地缓存采集数据（≥ 72 小时）
- FR19: 网关恢复后自动补传缓存数据（断点续传）
- FR20: 远程 OTA 固件升级（A/B 双分区、灰度发布、失败自动回滚）

#### 实时监控

- FR21: 仪表盘查看六大子系统实时数据
- FR22: 查看单台设备详情页面（实时参数、历史曲线、关联告警）
- FR23: 实时推送数据变化到前端（延迟 ≤ 1 秒）
- FR24: 查看设备状态看板（按区域/类型分组）
- FR25: 数据源通信中断时自动检测并显示中断时长和影响范围
- FR26: 查看数据源连接状态（连接/断开、最后通信时间）

#### 告警管理

- FR27: 为点位配置 4 级告警阈值（提示、次要、重要、紧急）
- FR28: 点位数据超过阈值时自动触发告警（延迟 ≤ 1 秒）
- FR29: 接收实时告警通知（系统推送 + 声光报警）
- FR30: 确认、处理、解除告警并记录处理过程
- FR31: 查看告警统计（按级别/区域/设备类型/时间段）
- FR32: 通信中断时标记受影响点位为"数据质量：不可靠"
- FR33: 告警升级规则（超时未处理自动升级告警级别或通知上级）

#### 智能诊断与联动

- FR34: 基于规则和历史数据自动分析告警可能原因（Top 20 高频故障场景）
- FR35: 检测传感器数据漂移（3σ 统计偏差、相邻传感器交叉验证）
- FR36: 配置联动策略（条件→动作链），特定事件触发时自动执行预设动作序列
- FR37: 消防分级联动（单传感器→预警，多传感器交叉确认→全部联动）
- FR38: 执行联动恢复流程（逐项恢复设备到正常状态）
- FR39: 自动生成事件时间线报告（从检测到恢复的完整链路）

#### 视频监控集成

- FR40: 告警触发时自动调取关联摄像头实时画面（分屏 1/4/9）
- FR41: 特定事件触发时自动开始区域录像
- FR42: 远程控制摄像头云台（方向、聚焦）定位到具体设备
- FR43: 通过告警时间快速定位并回放历史录像片段
- FR44: 管理摄像头元数据（位置、关联区域/设备），前端直连 NVR 拉流

#### 能源管理

- FR45: 查看实时 PUE 值及历史趋势
- FR46: 查看配电拓扑图（变压器→配电柜→PDU→机柜层级）
- FR47: 查看能耗统计（日/月能耗、尖峰/高峰/平段/低谷/深谷五时段电费分析、同比/环比对比）
- FR48: 配置电价策略（尖峰/高峰/平段/低谷/深谷五时段，时段时间可调、电价费率可调）
- FR49: 自动识别节能机会（峰谷套利、需量优化、PUE 优化等 6 种）
- FR50: 选择节能方案并设置执行计划
- FR51: 自动追踪节能方案执行效果（对比电表实际读数）
- FR52: 导出能效报告（含 PUE 趋势、电费对比、节能成果）
- FR53: 查看设备功率监控和负载率分析

#### 资产与容量管理

- FR54: 录入和管理设备资产信息（SN 码、型号、厂商、保修期等）
- FR55: 批量导入设备资产
- FR56: 查看机柜 U 位占用可视化图
- FR57: 自动记录资产生命周期事件（入库、上架、维修、下架、报废）
- FR58: 保修到期前自动发送预警提醒
- FR59: 查看空间/电力/制冷/承重容量使用情况
- FR60: 基于容量数据生成机柜上架推荐（≥ 3 个候选位置+多维度评分）
- FR61: 查看容量趋势预测和扩容建议

#### 机房物理拓扑

- FR62: 配置机柜物理位置（行列号、冷热通道归属、楼层/房间/区域层级）
- FR63: 配置 PDU 三相接线关系
- FR64: 配置空调覆盖范围
- FR65: 基于三合一拓扑模型提供多维度智能机柜选址推荐
- FR66: 配电设备故障时基于拓扑模型自动定位受影响的下游机柜和设备

#### 运维管理

- FR67: 自动或手动创建工单，按规则派发给对应人员
- FR68: 处理工单（接单、执行、完成、关闭），支持审批流程
- FR69: 创建和管理巡检计划（巡检路线、检查项、周期）
- FR70: 执行巡检任务并记录巡检结果
- FR71: 查阅和维护知识库（故障处理经验、操作规程、设备手册）

#### 报表与决策支持

- FR72: 自动生成运行报表（日报/周报/月报）
- FR73: 查看摘要面板（按优先级排序的待处理事项+推荐操作）
- FR74: 导出报表为 PDF 格式
- FR75: 设备健康度评估（SOH 评分 0~100 + 状态等级）

#### 用户与系统管理

- FR76: 创建、编辑、删除用户账号（支持批量操作）
- FR77: 分配用户角色和权限（RBAC 三级：管理员/操作员/只读）
- FR78: 基于令牌的认证和会话管理（JWT）
- FR79: 自动记录所有操作日志（保留 ≥ 180 天，审计记录不可篡改）
- FR80: 管理数据备份策略（自动备份、手动备份、恢复）
- FR81: 查看系统健康状态（服务运行状态、数据库状态、存储使用率）
- FR82: 统一视图查看和切换多站点数据，运维人员仅可见权限范围内站点

#### 棕地改进

- FR83: 核心模块自动化测试套件，后端测试覆盖率 ≥ 80%
- FR84: 前端页面完成用户管理全部操作（创建/编辑/删除/角色分配）
- FR85: 报表导出为 PDF 格式（日报/周报/月报）
- FR86: 独立设备管理页面（基本信息、关联点位、告警规则、历史数据）
- FR87: 前端页面管理告警规则（创建/编辑/删除/启用/禁用）
- FR88: 前端 TypeScript 类型检查零错误，后端 pyright 类型检查零错误

### 非功能需求

#### 性能

- NFR-P1: 数据采集周期 ≤ 5 秒（可配置 1~60 秒）
- NFR-P2: 告警触发延迟 ≤ 1 秒
- NFR-P3: 联动执行延迟 ≤ 3 秒（消防联动 GB 50116）
- NFR-P4: API 响应时间 P95 < 500ms（常规）/ P95 < 2s（复杂报表）
- NFR-P5: WebSocket 推送延迟 < 1 秒
- NFR-P6: 首屏加载 ≤ 3 秒
- NFR-P7: 并发采集 ≥ 2,000 点位/网关
- NFR-P8: 平台总容量 200 台设备 / 10,000 点位
- NFR-P9: MQTT Broker 吞吐 ≥ 5,000 msg/s
- NFR-P10: 并发用户 ≥ 50（含 WebSocket 长连接）

#### 安全

- NFR-S1: JWT + bcrypt 认证，密码行业标准单向哈希
- NFR-S2: RBAC 三级权限控制 + 站点级数据隔离
- NFR-S3: 操作审计日志 ≥ 180 天，追加写入模式（等保二级）
- NFR-S4: 远程控制双重确认弹窗，关键操作需审批
- NFR-S5: 新设备默认只读模式
- NFR-S6: 协议安全传输（SNMP v3、OPC-UA 证书、MQTT TLS、Modbus 白名单）
- NFR-S7: 密码复杂度要求、定期更换提醒
- NFR-S8: Token 过期自动登出、并发会话限制

#### 可靠性

- NFR-R1: 系统可用率 ≥ 99.5%
- NFR-R2: 优雅降级（显示最后已知数据 + 状态提示）
- NFR-R3: 网关离线缓存 ≥ 72 小时 + 断点续传
- NFR-R4: 采集数据不丢失
- NFR-R5: 数据一致性 ≥ 99.99%
- NFR-R6: 原始数据 90 天、小时聚合 3 年、告警永久保留
- NFR-R7: 自动每日备份 + 手动备份恢复
- NFR-R8: 消防联动执行成功率 100%
- NFR-R9: 单台网关故障隔离
- NFR-R10: OTA A/B 双分区 + 失败自动回滚

#### 可扩展性

- NFR-E1: 协议适配器插件化架构
- NFR-E2: 节能插件可插拔架构
- NFR-E3: 单站点→多站点集中管理扩展
- NFR-E4: 30 台→200 台设备平滑扩展
- NFR-E5: SQLite→PostgreSQL→TimescaleDB 数据库扩展

#### 可维护性

- NFR-M1: 核心模块测试覆盖率 ≥ 80%
- NFR-M2: API 100% OpenAPI 文档
- NFR-M3: Docker Compose 一键部署
- NFR-M4: 后端 pyright 零错误，前端 typecheck 零错误

---

## FR 覆盖映射表

以下映射表确保 PRD 中所有 88 条基础功能需求（FR1-FR88）均被至少一个 Epic/Story 覆盖。FR34-1~42 智能诊断子需求和 FR89-FR99 的覆盖映射见各 Epic 头部声明。

| FR | 描述 | Epic | Story |
|----|------|------|-------|
| FR1 | Modbus TCP/RTU 数据源配置 | Epic 1 | 1.2, 1.3 |
| FR2 | SNMP v2c/v3 数据源配置 | Epic 1 | 1.4 |
| FR3 | BACnet/IP 数据源配置 | Epic 15 | 15.3 |
| FR4 | OPC-UA 数据源配置 | Epic 15 | 15.4 |
| FR5 | MQTT 数据源配置 | Epic 15 | 15.1 |
| FR6 | HTTP REST 数据源配置 | Epic 15 | 15.2 |
| FR7 | 数据源连接测试 | Epic 1 | 1.5 |
| FR8 | Excel 批量导入点位 | Epic 3 | 3.2 |
| FR9 | 点位导入预校验 | Epic 3 | 3.2 |
| FR10 | 只读模式首次对接 | Epic 3 | 3.3 |
| FR11 | 可配置周期自动采集 | Epic 1 | 1.1 |
| FR12 | 干接点信号采集 | Epic 1 | 1.6 |
| FR13 | 设备模板管理 | Epic 3 | 3.4 |
| FR14 | 对接报告导出 | Epic 3 | 3.5 |
| FR15 | 网关自动注册 | Epic 2 | 2.1 |
| FR16 | 网关状态监控 | Epic 2 | 2.2 |
| FR17 | 远程配置下发 | Epic 2 | 2.3 |
| FR18 | 离线缓存 72h | Epic 2 | 2.4 |
| FR19 | 断点续传 | Epic 2 | 2.4 |
| FR20 | OTA 固件升级 | Epic 15 | 15.5 |
| FR21 | 六大子系统实时数据 | Epic 4 | 4.1 |
| FR22 | 设备详情页 | Epic 4 | 4.2 |
| FR23 | WebSocket 实时推送 | Epic 4 | 4.1 |
| FR24 | 设备状态看板 | Epic 4 | 4.3 |
| FR25 | 通信中断检测 | Epic 4 | 4.4 |
| FR26 | 数据源连接状态 | Epic 4 | 4.4 |
| FR27 | 4 级告警阈值配置 | Epic 5 | 5.1 |
| FR28 | 自动触发告警 | Epic 5 | 5.2 |
| FR29 | 实时告警通知 | Epic 5 | 5.2 |
| FR30 | 告警确认/处理/解除 | Epic 5 | 5.3 |
| FR31 | 告警统计 | Epic 5 | 5.3 |
| FR32 | 数据质量标记防误告警 | Epic 5 | 5.4 |
| FR33 | 告警升级规则 | Epic 5 | 5.5 |
| FR34 | 智能故障诊断 | Epic 9 | 9.3 |
| FR35 | 传感器漂移检测 | Epic 9 | 9.7 |
| FR36 | 联动策略配置 | Epic 9 | 9.1 |
| FR37 | 消防分级联动 | Epic 9 | 9.2 |
| FR38 | 联动恢复流程 | Epic 9 | 9.4 |
| FR39 | 事件时间线报告 | Epic 9 | 9.5 |
| FR40 | 告警联动调取摄像头 | Epic 10 | 10.2 |
| FR41 | 事件触发区域录像 | Epic 10 | 10.3 |
| FR42 | 云台远程控制 | Epic 10 | 10.3 |
| FR43 | 告警回放历史录像 | Epic 10 | 10.4 |
| FR44 | 摄像头元数据管理 | Epic 10 | 10.1 |
| FR45 | PUE 实时监控 | Epic 6 | 6.1 |
| FR46 | 配电拓扑图 | Epic 6 | 6.1 |
| FR47 | 能耗统计 | Epic 6 | 6.2 |
| FR48 | 电价策略配置 | Epic 6 | 6.2 |
| FR49 | 节能机会识别 | Epic 6 | 6.3 |
| FR50 | 节能方案执行 | Epic 6 | 6.4 |
| FR51 | 节能效果追踪 | Epic 6 | 6.4 |
| FR52 | 能效报告导出 | Epic 6 | 6.4, 6.5 |
| FR53 | 设备功率监控 | Epic 6 | 6.2 |
| FR54 | 资产信息管理 | Epic 7 | 7.1 |
| FR55 | 资产批量导入 | Epic 7 | 7.1 |
| FR56 | 机柜 U 位可视化 | Epic 7 | 7.2 |
| FR57 | 资产生命周期 | Epic 7 | 7.3 |
| FR58 | 保修到期预警 | Epic 7 | 7.3 |
| FR59 | 四维容量监控 | Epic 7 | 7.4 |
| FR60 | 机柜上架推荐 | Epic 7 | 7.5 |
| FR61 | 容量趋势预测 | Epic 7 | 7.6 |
| FR62 | 机柜物理位置配置 | Epic 8 | 8.1 |
| FR63 | PDU 三相接线配置 | Epic 8 | 8.2 |
| FR64 | 空调覆盖范围配置 | Epic 8 | 8.2 |
| FR65 | 多维度智能选址 | Epic 8 | 8.3 |
| FR66 | 故障影响分析 | Epic 8 | 8.4 |
| FR67 | 工单创建与派发 | Epic 11 | 11.1, 11.4 |
| FR68 | 工单处理流程 | Epic 11 | 11.1 |
| FR69 | 巡检计划管理 | Epic 11 | 11.2 |
| FR70 | 巡检任务执行 | Epic 11 | 11.2 |
| FR71 | 知识库 | Epic 11 | 11.3 |
| FR72 | 自动运行报表 | Epic 12 | 12.1 |
| FR73 | 智能摘要面板 | Epic 12 | 12.2 |
| FR74 | PDF 报表导出 | Epic 12 | 12.3 |
| FR75 | 设备健康度评估 | Epic 12 | 12.4 |
| FR76 | 用户账号管理 | Epic 13 | 13.1 |
| FR77 | 角色权限分配 | Epic 13 | 13.1 |
| FR78 | 令牌认证与会话 | Epic 13 | 13.2 |
| FR79 | 操作审计日志 | Epic 13 | 13.3 |
| FR80 | 数据备份策略 | Epic 13 | 13.4 |
| FR81 | 系统健康状态 | Epic 13 | 13.4 |
| FR82 | 多站点视图与隔离 | Epic 13, 16 | 13.5, 16.1, 16.2, 16.3 |
| FR83 | 自动化测试覆盖率 | Epic 14 | 14.1, 14.4 |
| FR84 | 用户管理前端页面 | Epic 13 | 13.1 |
| FR85 | PDF 报表导出 | Epic 12 | 12.3 |（与 FR74 为同一需求，保留映射以保持编号连续性）
| FR86 | 独立设备管理页面 | Epic 14 | 14.2 |
| FR87 | 告警规则前端管理 | Epic 5 | 5.5 |
| FR88 | 类型检查零错误 | Epic 14 | 14.3 |
| NFR-S7 | 密码策略 | Epic 13 | 13.6 |
| NFR-R2 | 优雅降级 | Epic 4 | 4.5 |
| NFR-E5 | 数据库扩展 | Epic 14 | 14.5 |
| NFR-M3 | Docker 部署 | Epic 14 | 14.6 |
| NFR-S4 | 控制命令分级确认 | Epic 9 | 9.6 |

### NFR 架构支撑映射

| NFR 类别 | 关键指标 | 支撑 Epic/架构 |
|---------|---------|---------------|
| 性能 - 采集周期 ≤5s | Epic 1 (asyncio 并发调度) |
| 性能 - 告警触发 ≤1s | Epic 5 (MQTT-Redis-内存阈值比对) |
| 性能 - 联动执行 ≤3s | Epic 9 (Redis Pub/Sub + asyncio.gather) |
| 性能 - API P95 <500ms | Epic 4 (Redis 缓存 + PG 索引) |
| 性能 - WebSocket <1s | Epic 4 (MQTT-Redis-WebSocket 直推) |
| 性能 - 历史查询 P95 <3s | Epic 4 (TimescaleDB hypertable) |
| 性能 - 50 并发用户 | Architecture (uvicorn workers + ConnectionManager) |
| 性能 - 5000 msg/s | Epic 2 (EMQX 单节点) |
| 安全 - JWT + RBAC | Epic 13 (三级角色 + 站点隔离) |
| 安全 - 审计日志 180天 | Epic 13 (追加写入 + 行级安全) |
| 安全 - 控制命令安全 | Epic 3 (只读首次对接) + Epic 9 (分级确认: 9.2消防+9.6普通/关键) |
| 安全 - 协议安全 | Epic 15 (SNMP v3/OPC-UA 证书/MQTT TLS) |
| 可靠性 - 可用率 99.5% | Architecture (双机 + PG 主从 + Redis Sentinel) |
| 可靠性 - 离线容错 72h | Epic 2 (SQLite 本地缓存 + 断点续传) |
| 可靠性 - 消防联动 100% | Epic 9 (最高优先级 + 跳过排队) |
| 可靠性 - 网关故障隔离 | Epic 2 (每机房独立网关) |
| 可扩展性 - 协议插件化 | Epic 1 (BaseProtocolAdapter + Registry) |
| 可扩展性 - 多站点 | Epic 16 (行级 site_id 隔离) |
| 可维护性 - 测试覆盖 80% | Epic 14 (pytest + Vitest) |
| 可维护性 - 类型零错误 | Epic 14 (pyright + typecheck) |
| 安全 - 密码策略 | Epic 13 (密码复杂度 + 定期更换) |
| 可靠性 - 优雅降级 | Epic 4 (Redis/WS/MQTT 降级处理) |
| 可维护性 - Docker 部署 | Epic 14 (Docker Compose 一键部署) |
| 可扩展性 - 数据库扩展 | Epic 14 (SQLite->PG+TimescaleDB 迁移) |

## Epic 17: 2.5D 视觉增强

**目标**: 为系统所有页面添加轻度 3D 透视效果，通过 SCSS mixin 系统实现统一的 2.5D 视觉体验。

**覆盖 FR**: FR89, FR90, FR91, FR92

### Story 17.1: 2.5D SCSS Mixin 基础设施 [全阶段]

**作为** 前端开发者，**我想要** 一套可复用的 2.5D SCSS mixin 系统，**以便** 各页面只需 1 行代码即可启用 2.5D 效果。

**验收条件:**
- [ ] 创建 `_mixins-25d.scss`，包含 perspective-container、stat-cards-arc、table-depth、chart-depth-split、form-depth 等 mixin
- [ ] 全局 index.scss 中定义 slideInDepth、fadeInDepthSubtle keyframes
- [ ] 全局 fadeInUp 动画改为 opacity-only，不再包含 transform
- [ ] 提供 page-dashboard、page-list、page-form、page-special 四个页面级 preset
- [ ] 支持 prefers-reduced-motion 媒体查询降级
- [ ] Dashboard 页面重构为使用新 mixin 系统，效果与 POC 一致

**FR 覆盖**: FR89, FR92

### Story 17.2: 仪表盘/概览类页面 2.5D 增强 [全阶段]

**作为** 运维工程师，**我想要** 所有概览页面具有统一的 2.5D 空间层次感，**以便** 快速区分信息层级。

**验收条件:**
- [ ] 以下页面应用 page-dashboard 或 stat-cards-arc + chart-depth-split mixin：
  - dashboard/index.vue、asset/index.vue、capacity/index.vue
  - cooling/overview.vue、power/overview.vue、environment/overview.vue、security/overview.vue
  - device-manage/index.vue、device-status/index.vue
  - energy/monitor.vue、energy/execution.vue、energy/regulation.vue、energy/suggestions.vue
  - operation/workorder.vue、settings/UserManagement.vue
- [ ] 统计卡片弧形倾斜角度在 1-2° 范围
- [ ] hover 效果：浮起 + 发光边框
- [ ] npm run build 通过

**FR 覆盖**: FR89, FR90

### Story 17.3: 列表/表单类页面 2.5D 增强 [全阶段]

**作为** 运维工程师，**我想要** 列表和表单页面也具有微妙的 3D 层次感，**以便** 整个系统视觉风格统一。

**验收条件:**
- [ ] 以下列表类页面应用 page-list mixin：
  - alarm/index.vue、device/index.vue、datasource/index.vue、device-template/index.vue
  - asset/cabinet.vue
  - power/battery.vue、cabinet.vue、pdu.vue、ups.vue
  - cooling/indoor.vue、outdoor.vue、cold-aisle.vue、group-control.vue
  - operation/inspection.vue、knowledge.vue
  - settings/index.vue、energy/config.vue
- [ ] 以下表单/配置类页面应用 page-form mixin：
  - energy/statistics.vue、energy/report.vue
  - history/index.vue、report/index.vue
- [ ] 表格微倾 0.5°，行 hover 浮起 2px
- [ ] npm run build 通过

**FR 覆盖**: FR89, FR91

### Story 17.4: 特殊页面 2.5D 增强 [全阶段]

**作为** 运维工程师，**我想要** 拓扑图、分析等特殊页面也有适当的 3D 效果，**以便** 全系统视觉一致。

**验收条件:**
- [ ] 以下特殊页面应用 page-special 或自定义 mixin 组合：
  - energy/topology.vue、energy/analysis.vue
  - vpp/VPPAnalysis.vue、device-manage/detail.vue
- [ ] login/index.vue 和 bigscreen/index.vue 不做修改（各有独立视觉风格）
- [ ] npm run build 通过
- [ ] 所有页面在 Chrome/Edge 最新版本中效果正常

**FR 覆盖**: FR89

---

---

## Phase 2 补全 — Epic 18-23：待开发页面实现

**背景：** Epic 1-17 已全部实施完毕。以下 Epic 18-23 针对前端仍使用 PlaceholderView 占位组件的页面和代码级 TODO，将其实现为完整功能页面。

**优先级排序：** P0: Epic 21, 22 → P1: Epic 18, 20 → P2: Epic 19 → P3: Epic 23

### 新增 Epic 总览

| # | Epic | 阶段 | FR 覆盖 | 故事数 |
|---|------|------|---------|--------|
| 18 | 环境监控子系统详情页 | Phase 2 补全 | FR21,FR22,FR24,FR35 | 3 |
| 19 | 安防消防前端可视化 | Phase 2 补全 | FR36,FR37,FR44 | 2 |
| 20 | 告警规则增强管理页 | Phase 2 补全 | FR27,FR33,FR87 | 4 |
| 21 | 网关管理前端 | Phase 2 补全 | FR15,FR16,FR17 | 2 |
| 22 | 站点管理前端 | Phase 2 补全 | FR82 | 2 |
| 23 | 大屏增强与能源 OCR | Phase 2 补全 | FR22,FR48,愿景 | 3 |

### 新增 Epic 依赖关系

```
Epic 18 — 独立（后端 API 已就绪）
Epic 19 — 独立（后端联动引擎已就绪）
Epic 20 — 独立（后端告警 API 已就绪）
Epic 21 — 独立（后端网关 API 已就绪）
Epic 22 — 独立（后端站点 API 需验证，Story 自包含）
Epic 23 — Story 23.3 需后端新增 OCR API
所有 Epic 互不依赖，可并行开发。
```

### 新增 FR 覆盖映射

```
FR15: Epic 21 - 网关注册展示
FR16: Epic 21 - 网关状态监控页
FR17: Epic 21 - 远程配置下发 UI
FR21(环境): Epic 18 - 环境子系统详情页
FR22(环境): Epic 18 - 传感器设备详情
FR22(大屏): Epic 23 - 大屏历史弹窗
FR24(环境): Epic 18 - 环境设备状态
FR27: Epic 20 - 阈值配置增强页
FR33: Epic 20 - 升级规则可视化
FR35: Epic 18 - 漂移检测关联展示
FR36: Epic 19 - 消防联动可视化
FR37: Epic 19 - 消防分级联动展示
FR44(门禁): Epic 19 - 门禁时间线视图
FR48(增强): Epic 23 - 电费单 OCR
FR82: Epic 22 - 多站点管理页(22.1 CRUD + 22.2 站点切换器)
FR87: Epic 20 - 告警规则前端管理
```

---


## Epic 21: Gateway Management Frontend

**Phase:** Phase 2 Supplement
**Goal:** Enable operations engineers to view and manage all collection gateways' status and perform remote configuration deployment through the frontend.
**FR Coverage:** FR15, FR16, FR17

### Story 21.1: Gateway List and Status Monitoring

As a operations engineer,
I want to view the running status of all collection gateways on the gateway management page,
So that I can promptly detect gateway failures and understand each gateway's load.

**Acceptance Criteria:**

- **Given** operations engineer enters the gateway management page (`/collection/gateway`)
- **When** the page loads
- **Then** display a gateway list table with: gateway name, unique ID, IP address, online/offline status, CPU usage, memory usage, disk usage, last heartbeat time, associated datasource count
- **And** offline gateways highlighted with red background
- **And** CPU/memory/disk usage displayed as progress bars, orange above 80%, red above 90%
- **And** support filtering by status (online/offline) and searching by name
- **And** clicking a gateway row expands a detail panel showing the datasources and total point count managed by that gateway
- **And** gateway online/offline status pushed in real-time via WebSocket system channel, no REST API polling needed
- **And** gateway offline events triggered by backend Redis TTL expiry, frontend immediately updates list status upon receiving offline event
- **And** page replaces current PlaceholderView component
- **And** page style consistent with `device-manage/index.vue`, includes 2.5D visual enhancement

**FR Trace:** FR15, FR16

### Story 21.2: Gateway Remote Configuration Deployment

As a operations engineer,
I want to remotely deploy collection configurations to gateways through the frontend,
So that I don't need to go on-site to modify gateway configurations.

**Acceptance Criteria:**

- **Given** operations engineer is in the gateway detail panel
- **When** clicking the "Deploy Configuration" button
- **Then** a confirmation dialog appears showing the configuration summary to be deployed (datasource count, point count)
- **And** after confirmation, calls backend API to execute configuration deployment
- **And** button shows loading state during deployment
- **And** successful deployment shows success message, failure shows error reason
- **And** supports viewing gateway configuration deployment history (time, operator, result)
- **And** when gateway is offline, "Deploy Configuration" button is grayed out with tooltip "Gateway offline, cannot deploy"

**FR Trace:** FR17

---

## Epic 22: Site Management Frontend

**Phase:** Phase 2 Supplement
**Goal:** Enable operations supervisors to manage multi-site configurations and switch site data in a unified view.
**FR Coverage:** FR82

### Story 22.1: Site Management Backend API and CRUD Page

> **与 Epic 16 Story 16.1 的关系:** Epic 16 Story 16.1 定义站点管理的后端数据模型和 site_id 行级隔离方案。本 Story 22.1 实现前端 CRUD 页面和后端 API。如果 Epic 16 Story 16.1 在本 Story 之前完成，则复用其 API；若 Epic 16 尚未启动，则本 Story 自行创建后端 API，Epic 16 Story 16.1 在此基础上增加 EMQX ACL 隔离和跨表 site_id 字段。

As a operations supervisor,
I want to create, edit, delete sites on the site management page,
So that I can uniformly manage configurations for multiple data centers.

**Acceptance Criteria:**

- **Given** operations supervisor enters the site management page (`/system/sites`)
- **When** the page loads
- **Then** display a site list table with: site name, site code, address, contact person, device count, gateway count, status (enabled/disabled), creation time
- **And** support adding new site (popup form dialog with name, code, address, contact, description)
- **And** support editing and deleting sites (deletion requires double confirmation, sites with devices cannot be deleted with reason shown)
- **And** before implementation, check if `backend/app/api/v1/` has sites-related route module; if backend CRUD API is missing, this Story scope includes creating backend site management API (`POST/GET/PUT/DELETE /api/v1/sites`) with corresponding SQLAlchemy Model and Pydantic Schema（注：棕地已有 `sites` 表和 `MqttAclRule` 模型引用 `sites.id`，需复用现有表结构）
- **And** page replaces current PlaceholderView component
- **And** page style consistent with `system/user.vue`, includes 2.5D visual enhancement

**FR Trace:** FR82

### Story 22.2: Global Site Switcher and Permission Filtering

As a operations supervisor,
I want a global site switcher in the page header that filters all data by selected site,
So that operations staff only see data within their permission scope.

> **与 Epic 16 Story 16.2 的关系:** 本 Story 实现单站点切换的基础 UI 组件和权限过滤。Epic 16 Story 16.2 在此基础上扩展"全部站点"汇总视图和跨站点对比分析。两者为递进关系，本 Story 先行交付。

**Acceptance Criteria:**

- **Given** site management backend API (Story 22.1) is available
- **When** the page header loads
- **Then** global Header provides a site switcher dropdown component
- **And** switching site filters all global data (devices, alarms, dashboards) by selected site
- **And** operations staff (non-supervisors) only see sites within their permission scope in the switcher
- **And** selected site persists across page navigation (stored in Pinia store + localStorage)
- **And** API calls include `site_id` query parameter when site filter is active

**FR Trace:** FR82

---

## Epic 18: Environment Monitoring Subsystem Detail Pages

**Phase:** Phase 2 Supplement
**Goal:** Enable operations engineers to quickly discover temperature/humidity, water leak, smoke/infrared anomalies through zone-grouped visualization, identifying problem areas at a glance.
**FR Coverage:** FR21 (environment subsystem), FR22 (environment device details), FR24 (environment device status), FR35 (drift correlation display)

### Story 18.1: Temperature and Humidity Monitoring Page

As a operations engineer,
I want to quickly discover temperature/humidity anomalies through zone-grouped cards on the temperature monitoring page and view real-time data and trends for each sensor,
So that I can take action before temperature/humidity exceeds limits.

**Acceptance Criteria:**

- **Given** operations engineer enters the temperature/humidity monitoring page (`/environment/temperature`)
- **When** the page loads
- **Then** top displays stat cards: total sensors, online count, alarm count, average temperature, average humidity, suspected drift count
- **And** core area is a **zone/room grouped card layout**, each zone card shows: zone name, sensor count, average temperature/humidity, max/min values, alarm count. Anomaly zone cards highlighted with red border, suspected drift zones with yellow border
- **And** component architecture reserves heatmap upgrade interface: data layer encapsulated via `composable`, can be replaced with heatmap rendering when sensor location data is ready without refactoring page logic
- **And** clicking a zone card expands sensor list for that zone, clicking a sensor shows detail panel: device name, current temperature/humidity values, last 24-hour trend chart (ECharts), associated alarm list
- **And** bottom auxiliary area is a sensor data table, supports filtering by zone, by status (normal/alarm/offline/suspected drift), and searching by name
- **And** sensors marked as "suspected drift" in data quality have clear identification in both cards and table (yellow icon + tooltip "Data reliability: Low")
- **And** page receives real-time data updates via WebSocket, cards and table auto-refresh
- **And** page replaces current PlaceholderView component
- **And** follows `cooling/overview.vue` "see everything at a glance" design pattern, includes 2.5D visual enhancement

**FR Trace:** FR21, FR22, FR24, FR35

### Story 18.2: Water Leak Detection Page

As a operations engineer,
I want to view all water leak sensors' real-time status and zone distribution on the water leak detection page,
So that I can locate the leak position immediately when a leak occurs.

**Acceptance Criteria:**

- **Given** operations engineer enters the water leak detection page (`/environment/water-leak`)
- **When** the page loads
- **Then** top displays stat cards: total sensors, online count, alarm count (current leaks), last 24-hour alarm count
- **And** core area is **zone/room grouped status cards**, each zone shows: zone name, sensor count, current status summary (all normal / has leak alarm). Leak alarm zone cards with red pulse animation
- **And** clicking a zone card expands sensor list, clicking a sensor shows detail panel: device name, current status (normal/leak/offline), recent alarm records list, installation location description
- **And** bottom auxiliary area is a sensor list table, supports filtering by status and by zone
- **And** water leak sensors are DI type (dry contact), state changes trigger alarms rather than threshold judgment
- **And** page receives real-time status changes via WebSocket
- **And** page replaces current PlaceholderView component, includes 2.5D visual enhancement

**FR Trace:** FR21, FR24

### Story 18.3: Smoke and Infrared Detection Page

As a operations engineer,
I want to view all smoke and infrared sensors' real-time status and zone distribution on the smoke/infrared detection page,
So that I can quickly locate and respond when smoke or intrusion events occur.

**Acceptance Criteria:**

- **Given** operations engineer enters the smoke/infrared detection page (`/environment/smoke-infrared`)
- **When** the page loads
- **Then** top displays stat cards: smoke sensor total/alarm count, infrared sensor total/alarm count, last 24-hour event count
- **And** core area is **zone/room grouped status cards**, each zone shows: zone name, smoke/infrared sensor counts, current status summary. Alarm zone cards highlighted in red
- **And** clicking a zone card expands sensor list, clicking a sensor shows detail panel: device name, type (smoke/infrared), current status, recent event records, associated linkage policy (if any)
- **And** when smoke sensor is in alarm, detail panel shows associated fire linkage policy status (configured/not configured)
- **And** bottom auxiliary area is a sensor list table, supports filtering by type (smoke/infrared) and status
- **And** sensors are DI type, state changes trigger alarms
- **And** page receives real-time status changes via WebSocket
- **And** page replaces current PlaceholderView component, includes 2.5D visual enhancement

**FR Trace:** FR21, FR24

---

## Epic 20: Alarm Rule Enhanced Management Pages

**Phase:** Phase 2 Supplement
**Goal:** Enable system administrators to get more powerful rule management capabilities in independent pages than the alarm center tabs - batch operations, visual editors, rule test preview.
**FR Coverage:** FR27 (threshold configuration), FR33 (escalation rules), FR87 (alarm rule frontend management)

### Story 20.1: Threshold Configuration Enhanced Page

As a system administrator,
I want to batch manage alarm thresholds on an independent threshold configuration page and visually see the relationship between thresholds and real-time data through visual threshold lines,
So that I can efficiently configure reasonable alarm thresholds for large numbers of points, avoiding false alarms and missed alarms.

**Acceptance Criteria:**

- **Given** system administrator enters the threshold configuration page (`/strategy/alarm-rules/thresholds`)
- **When** the page loads
- **Then** display threshold rule list table with: rule name, associated point/device type, 4-level thresholds (info/minor/major/critical), enabled status, last trigger time
- **And** support batch filtering by device type (e.g. "all temperature/humidity sensors", "all UPS")
- **And** support batch operations: batch enable/disable, batch modify thresholds for same device type
- **And** when adding/editing threshold rules, popup configuration dialog includes **visual threshold line preview**: ECharts trend chart showing the point's last 24-hour data, 4-level thresholds overlaid as colored horizontal lines (info-blue, minor-yellow, major-orange, critical-red), dragging threshold lines directly adjusts threshold values
- **And** support single rule CRUD operations (create/edit/delete/enable/disable)
- **And** deletion requires double confirmation
- **And** page replaces current PlaceholderView component, includes 2.5D visual enhancement

**FR Trace:** FR27, FR87

### Story 20.2: Compound Rule Configuration Page

As a system administrator,
I want to configure multi-condition compound alarm rules through a visual editor on an independent compound rule page and preview rule trigger effects,
So that I can create more precise alarm rules, reducing false alarms from single threshold judgment.

**Acceptance Criteria:**

- **Given** system administrator enters the compound rule page (`/strategy/alarm-rules/compound`)
- **When** the page loads
- **Then** display compound rule list table with: rule name, condition count, logic relationship (AND/OR), associated devices, enabled status, last trigger time

**Must Deliver:**
- **And** when adding/editing rules, popup condition editor form: support adding multiple condition rows, each row selects: point -> comparison operator (>, <, =, >=, <=) -> threshold value; conditions support AND/OR logic selection (dropdown); support nested condition groups
- **And** editor bottom provides **rule test preview** function: input simulated point values, **simple conditions (threshold comparison, AND/OR combination) calculated purely in frontend JavaScript with real-time trigger result display**

**Enhancement (non-blocking):**
- **And** visual connection lines between conditions showing logic relationships (enhanced interaction, can iterate later)
- **And** complex conditions (time windows, frequency statistics) reserve backend test API endpoint `POST /api/v1/alarms/rules/test`

- **And** support rule CRUD and enable/disable operations
- **And** page replaces current PlaceholderView component, includes 2.5D visual enhancement

**FR Trace:** FR87

### Story 20.3: Escalation Rule Management Page

As a system administrator,
I want to configure alarm timeout escalation chains through a visual interface on an independent escalation rule page,
So that I can ensure important alarms automatically escalate notification to supervisors when not handled in time.

**Acceptance Criteria:**

- **Given** system administrator enters the escalation rule page (`/strategy/alarm-rules/escalation`)
- **When** the page loads
- **Then** display escalation rule list table with: rule name, applicable alarm level, escalation chain layers, notification person count, enabled status

**Must Deliver:**
- **And** when adding/editing rules, popup configuration panel with **vertical list form** showing escalation chain: each row is an escalation node showing sequence number, timeout input (minutes), notification method selection, notification person selection, alarm level upgrade toggle
- **And** support adding/deleting escalation nodes, up/down arrows to adjust order

**Enhancement (non-blocking):**
- **And** escalation chain displayed as visual flowchart with connection lines and arrows between nodes (enhanced interaction, can iterate later)
- **And** drag to adjust node order

- **And** support configuring different escalation chains for different alarm levels (e.g. minor alarm 30-min escalation, major alarm 10-min escalation)
- **And** support rule CRUD and enable/disable operations
- **And** page replaces current PlaceholderView component, includes 2.5D visual enhancement

**FR Trace:** FR33, FR87

### Story 20.4: Alarm Shield Management Page

As a system administrator,
I want to manage shielding policies through a calendar view on an independent alarm shield page, supporting batch shielding by zone and device type,
So that I can temporarily shield alarms during device maintenance, system upgrades and other scenarios, avoiding large volumes of invalid alarms disturbing operations.

**Acceptance Criteria:**

- **Given** system administrator enters the alarm shield page (`/strategy/alarm-rules/shield`)
- **When** the page loads
- **Then** top displays **calendar view**, showing currently active and planned shielding policies on a timeline, different shielding scopes distinguished by different colors
- **And** bottom displays shielding policy list table with: policy name, shielding scope (global/zone/device type/specific device), shielding period (start-end), shielded alarm levels, status (active/expired/planned), creator
- **And** when adding shielding policy, supports:
  - Batch shield by zone (select zone, shield all device alarms in that zone)
  - Batch shield by device type (e.g. shield all AC alarms)
  - Shield by specific device
  - Configure shielding period (start time, end time, support "take effect immediately" or "scheduled")
  - Select shielded alarm levels (multi-select: info/minor/major/critical)
- **And** expired shielding policies automatically marked as "expired", no longer effective
- **And** support early termination of active shielding policies
- **And** support policy CRUD operations
- **And** page replaces current PlaceholderView component, includes 2.5D visual enhancement

**FR Trace:** FR87

---

## Epic 19: Security and Fire Protection Frontend Visualization

**Phase:** Phase 2 Supplement
**Goal:** Enable operations engineers to view access control entry/exit records and anomaly events through timeline view, and view fire linkage policy visual execution status.
**FR Coverage:** FR36 (linkage policy visualization), FR37 (fire graded linkage display), FR44 (access control association)

### Story 19.1: Access Control Management Page

As a operations engineer,
I want to view all access control device status on the access control management page and browse entry/exit records and anomaly events through a timeline view,
So that I can monitor data center access in real-time and quickly discover security anomalies like unauthorized access.

**Acceptance Criteria:**

- **Given** operations engineer enters the access control management page (`/security/access-control`)
- **When** the page loads
- **Then** top displays stat cards: total access control devices, online count, alarm count (anomaly events), today's total entry/exit count
- **And** left side displays access control device list, each device shows: name, location, current status (normal closed/normal open/anomaly/offline), last event time
- **And** right side core area is a **timeline view**, vertically displaying entry/exit records for the selected access control device along a time axis:
  - Each record shows: time, event type (card swipe open/remote open/anomaly open/fire linkage open), personnel info (if available), result (success/failure)
  - Anomaly events (unauthorized time period access, multiple card swipe failures, forced entry) highlighted in red with warning icon
  - Fire linkage door open events marked in orange showing associated linkage policy name
- **And** timeline supports filtering by date range and by event type
- **And** clicking different access control devices in the device list, right side timeline automatically switches to that device's records
- **And** access control device data sourced from dry contact signals converted through Modbus I/O collection module (DI type), state changes trigger events
- **And** page receives real-time access control events via WebSocket
- **And** page replaces current PlaceholderView component, includes 2.5D visual enhancement

**FR Trace:** FR44

### Story 19.2: Fire Linkage Visualization Page

As a operations engineer,
I want to view all linkage policies' configuration status and historical execution records on the fire linkage page, and review the complete process of linkage events through a visual timeline,
So that I can confirm linkage policies are correctly configured and efficiently review the complete handling chain of fire events after the fact.

**Acceptance Criteria:**

- **Given** operations engineer enters the fire linkage page (`/security/fire-linkage`)
- **When** the page loads
- **Then** top displays stat cards: total linkage policies, enabled count, last 30-day trigger count, average response time

**Policy Configuration Area:**
- **And** display fire linkage policy list, each policy shows: name, trigger condition (single sensor warning/multi-sensor linkage), linkage action count, enabled status
- **And** clicking a policy expands **linkage action chain visualization**: horizontal flowchart showing trigger condition -> action 1 (shut AC) -> action 2 (open access) -> action 3 (cut power) -> action 4 (start exhaust) -> action 5 (open lighting) -> action 6 (activate video) -> notification, each action node shows target device and expected response time
- **And** graded linkage distinguished by different colors: warning level (yellow) notification + video only, linkage level (red) executes all actions

**Execution History Area:**
- **And** display linkage execution history list, each record includes: trigger time, trigger source (sensor name), linkage level (warning/linkage), execution result (all success/partial failure), duration
- **And** clicking a history record expands **event timeline**: vertical time axis showing complete chain from detection to recovery, each node shows: timestamp, action description, execution result (success check/failure X), time taken
- **And** failed action nodes highlighted in red showing failure reason
- **And** timeline bottom shows recovery status: recovered/pending recovery, and each device's recovery progress
- **And** page replaces current PlaceholderView component, includes 2.5D visual enhancement

**FR Trace:** FR36, FR37

---

## Epic 23: Bigscreen Enhancement and Energy OCR

**Phase:** Phase 2 Supplement
**Goal:** Enable operations engineers to view device historical data popups on the bigscreen and 3D floor scenes; enable energy managers to auto-fill electricity pricing configuration through OCR recognition of electricity bills.
**FR Coverage:** FR22 (bigscreen version historical data), FR48 (electricity pricing enhancement), Vision feature (3D floor scene)
**Note:** 3 Stories are independently deliverable with different tech stacks.

### Story 23.1: Bigscreen Device Historical Data Popup

As a operations engineer,
I want to view a device's historical data trend popup when clicking a device on the bigscreen,
So that I can quickly understand device operation trends in the bigscreen monitoring scenario without switching to the management backend.

**Acceptance Criteria:**

- **Given** operations engineer on the bigscreen page (`/bigscreen`) has selected a device
- **When** clicking the "View History" button in the device detail panel
- **Then** popup a historical data dialog (fullscreen modal, dark theme consistent with bigscreen style)
- **And** dialog top shows device name, device type, current status
- **And** core area is an ECharts trend chart, defaulting to show all AI-type points' last 24-hour data curves for that device
- **And** support switching time range: last 1 hour / 6 hours / 24 hours / 7 days
- **And** support checking/unchecking specific points to control which curves display in the trend chart
- **And** trend chart overlays alarm threshold lines (if configured), above-threshold areas marked with semi-transparent red background
- **And** replaces current `handleViewHistory` function's `console.log` placeholder logic
- **And** dialog supports ESC to close, clicking overlay to close

**FR Trace:** FR22

### Story 23.2: Bigscreen 3D Floor Scene Loading

As a operations engineer,
I want to load corresponding 3D scenes by floor when switching to 3D mode on the bigscreen,
So that I can intuitively view the spatial distribution and running status of data center equipment through a three-dimensional perspective.

**Acceptance Criteria:**

- **Given** operations engineer on the bigscreen page, currently in 3D mode
- **When** switching the floor selector to a specific floor
- **Then** **procedurally generate a 3D scene** based on cabinet spatial topology data (row/column numbers, hot/cold aisle assignment): use Three.js BoxGeometry for cabinets (arranged by rows and columns), PlaneGeometry for floor, different colors distinguishing cold aisles (blue semi-transparent) and hot aisles (red semi-transparent)
- **And** scene displays procedurally generated cabinet row/column layout, cabinet dimensions proportional to standard 42U, spacing based on hot/cold aisle width
- **And** if backend has spatial topology data (row/column numbers), fetch from API; if no data, use default 4x10 cabinet layout as demo
- **And** device models colored by real-time status: normal-green, alarm-red pulse, offline-gray
- **And** support mouse/touch interaction: rotate (left-click drag), zoom (scroll wheel), pan (right-click drag)
- **And** clicking a device model triggers device selection event, linking to right-side device detail panel
- **And** 3D scene generation failure or browser not supporting WebGL automatically degrades to 2D floor plan
- **And** if floor has no corresponding spatial topology data, maintain current 2D floor plan mode and log a console message
- **And** replaces current `handleFloorChange` function's 3D mode TODO comment logic

**FR Trace:** Vision feature (Digital Twin Bigscreen)

### Story 23.3: Electricity Bill OCR Recognition

As a energy manager,
I want to upload an electricity bill image and have the system automatically recognize and extract electricity pricing information to fill the configuration form,
So that I don't need to manually input electricity pricing data item by item, reducing input errors and workload.

**Acceptance Criteria:**

- **Given** energy manager on the power distribution configuration page (`/collection/power-config`) in the electricity pricing configuration area
- **When** clicking the "Upload Electricity Bill" button and selecting an image file (supports JPG/PNG/PDF, <=10MB)
- **Then** image uploaded to backend OCR recognition endpoint
- **And** backend calls OCR service (PaddleOCR local deployment preferred to avoid cloud API dependency and costs; if deployment is difficult, can degrade to Baidu Cloud/Alibaba Cloud OCR API requiring API Key configuration) to recognize electricity bill content
- **And** MVP stage supports **1-2 common electricity bill templates** (State Grid, China Southern Power Grid standard formats); for other format bills where overall OCR confidence is below 60%, prompt "This bill format is not yet supported, please input manually"
- **And** backend parses recognition results, extracting key information: electricity rates (peak/high/flat/valley/deep valley), time period divisions, basic electricity fee, power factor adjustment fee
- **And** after recognition, frontend pops up **recognition result confirmation dialog**: left side shows original image, right side shows extracted structured data, each field can be manually corrected
- **And** after user confirmation, auto-fills the electricity pricing configuration form
- **And** fields with recognition confidence below 80% highlighted in yellow, prompting user to verify
- **And** OCR recognition failure shows friendly error message "Recognition failed, please input manually", does not block normal flow
- **And** replaces current `handleBillUpload` function's placeholder logic
- **And** requires new backend API endpoint: `POST /api/v1/energy/ocr/bill` (receives image, returns structured electricity pricing data)

**FR Trace:** FR48

---

---

## Epic 24: 智能诊断核心引擎

**阶段:** Phase 2a (月7-8)
**目标:** 构建分级推理引擎（L1规则/L2故障树），实现故障树建模与版本管理，打通告警→诊断→结果展示闭环。Go/No-Go门槛：准确率≥50% AND L2推理≤10秒（基于 ≥100 条预标注测试集，在 Sprint Review 时由 QA 执行测试套件验证；未达标则延长 2 周调优或仅发布 L1）。
**FR 覆盖:** FR34-1~12, FR34-16~19, FR34-29
**架构参考:** Architecture 18.2~18.4, 18.9~18.10, 18.12, 18.15
**前置依赖:** Epic 5（告警管理，提供告警事件源）, Epic 14（PostgreSQL 迁移完成）, 月6完成故障树专家评审
**棕地迁移注意:** 现有棕地代码中已有 `diagnosis_rules` 表（含 `DiagnosisRule` ORM 模型和 CRUD API），Epic 24 的 Story 24.1 和 24.3 必须在现有表结构基础上通过 Alembic 迁移扩展字段（而非新建表），以避免数据丢失和 API 不兼容。所有新增诊断表（`fault_tree`, `diagnosis_session` 等）使用 Alembic 新建迁移脚本。

### Story 24.1: L1 规则引擎

As a 运维工程师,
I want 系统在告警触发时立即给出常见故障的快速诊断,
So that 我可以在1秒内获得初步故障判断，加快响应速度。

**Acceptance Criteria:**

- Given 管理员已在系统中配置 JSON 格式的诊断规则集（条件→结论，存储在 PostgreSQL `diagnosis_rules` 表——复用棕地已有表名）
- When 告警引擎检测到越限并通过 Redis Pub/Sub 发布 `alarm:new` 事件
- Then 诊断调度器订阅该事件，将告警封装为诊断任务提交到 `asyncio.PriorityQueue`（按告警级别排优先级：紧急=0, 重要=1, 次要=2, 提示=3）
- And L1 引擎从内存中加载的规则集逐条匹配（规则在服务启动时从 DB 加载到内存 dict）
- And 匹配逻辑：先从告警关联的规则中收集所有需要的点位 ID，通过 Redis `MGET` 批量读取最新值（一次网络往返），再逐规则遍历 `conditions` 按 `logic`（AND/OR）组合判断
- And 匹配成功时输出结论（含根因描述、置信度、建议操作列表）
- And 全部匹配过程 < 1秒完成（纯内存操作，无 DB 查询）
- And 无规则匹配时：紧急/重要告警自动升级到 L2 分析（调度器重新入队为 L2 任务）；次要/提示告警记录"L1未匹配"结果，不自动升级（管理员可通过手动触发 API 升级）
- And 初始规则集覆盖 Top 20 高频故障中 ≥12 类（60%），由运维专家协助编写

**技术实现要点:**
- 规则存储: 复用棕地已有 `diagnosis_rules` 表（表名为复数形式，与现有 Alembic 迁移一致），扩展字段: conditions JSON, logic, conclusion, confidence, suggested_actions JSON, enabled, priority
- 内存缓存: 服务启动时 `SELECT * FROM diagnosis_rules WHERE enabled=true ORDER BY priority`，存入 `dict[str, list[DiagnosisRule]]` 按 `(device_type, alarm_type)` 元组索引（一条规则可被多个 key 索引），告警触发时通过告警的 device_type + alarm_type 快速查找候选规则
- 规则热更新: 管理员修改规则后通过 Redis Pub/Sub `diagnosis:rule_update` 通知引擎重新加载

**FR 追溯:** FR34-1

### Story 24.2: 诊断调度器与并发控制

As a 开发者,
I want 一个支持优先级队列和并发控制的诊断调度器,
So that 多个告警同时触发时系统能有序处理，紧急告警优先，不会因过载崩溃。

**Acceptance Criteria:**

- Given 诊断引擎服务已启动
- When 多个告警同时通过 Redis Pub/Sub 触发诊断
- Then 调度器使用自定义 `CancellablePriorityQueue(maxsize=50)`（基于 heapq + `_cancelled` 标记法 + asyncio.Event 通知）排队，按告警级别优先级排序
- And 使用 `asyncio.Semaphore(10)` 限制最多 10 个并发推理任务
- And 队列满时：低优先级新任务直接丢弃并记录日志，同时通过 WebSocket 通知运维人员"诊断队列已满，低优先级任务被跳过"；紧急/重要新任务将队列中最低优先级的未取消任务标记为取消（被取消任务同样通知运维人员），然后插入新任务
- And 每个推理任务设置 `asyncio.wait_for` 超时保护（L1: 2s, L2: 10s, L3: 60s）
- And 超时的任务触发熔断计数器（见 Story 24.7）
- And 调度器支持根据告警级别自动选择推理级别：紧急/重要→L2，次要/提示→L1
- And 运维工程师可通过 API `/api/v1/diagnosis/trigger` 手动触发诊断并指定推理级别（自动/L1/L2/L3），需 operator+ 角色，限流 10 次/分钟/用户、30 次/分钟/全局

**技术实现要点:**
- DiagnosisScheduler 类: 自定义 `CancellablePriorityQueue`（基于 heapq + `_cancelled` 标记法）+ Semaphore + worker 协程；worker 取出任务时跳过已取消项
- 在 FastAPI lifespan 中启动 worker: `asyncio.create_task(scheduler.run())`
- 手动触发 API: `POST /api/v1/diagnosis/trigger {"device_id": ..., "level": "auto"}`（需 operator+ 角色）
- 所有诊断 API 端点 RBAC: trigger(operator+), sessions 列表/详情(operator+), health(admin), chaos/*(admin)，复用 `backend/app/api/deps.py` 的 `require_admin`/`require_operator` 依赖注入

**FR 追溯:** FR34-4, Architecture 18.2（并发控制）

### Story 24.3: 故障树数据模型与CRUD

As a 管理员,
I want 在系统中创建和管理故障树,
So that 诊断引擎可以基于故障树进行因果推理。

**Acceptance Criteria:**

- Given 管理员登录系统
- When 通过 `/api/v1/fault-trees` API 创建故障树
- Then 系统在 `fault_tree` 表创建记录（name, description, status=draft, created_by, created_at）
- And 支持在故障树中添加节点：`fault_tree_node` 表（tree_id, node_type: root/intermediate/leaf, gate_type: AND/OR/NULL, name, description, prior_probability, evidence_point_id）
- And 支持在节点间添加边：`fault_tree_edge` 表（tree_id, parent_node_id, child_node_id）
- And 保存时后端验证 DAG 完整性：
  - 使用 NetworkX 构建 DiGraph 检测是否有循环（`nx.is_directed_acyclic_graph`）
  - 检查无孤立节点: `set(nx.descendants(graph, root_node)) | {root_node}` 必须等于图的全部节点集
  - 检查所有叶节点必须有 `prior_probability > 0` 或关联了 `evidence_point_id`
  - 检查有且仅有一个 root 节点
- And 验证失败时返回具体错误信息（如"节点X形成循环"、"叶节点Y缺少概率值"）
- And 支持故障树的 CRUD 操作（创建/读取/更新/删除），删除仅允许 draft 状态

**技术实现要点:**
- Alembic 迁移: 创建 fault_tree, fault_tree_node, fault_tree_edge, fault_tree_device_mapping 四张表（mapping 表: tree_id, device_type, alarm_type, priority）
- DAG 验证: 从 DB 查出节点和边 → 构建 `nx.DiGraph` → 执行验证 → 返回结果
- API: RESTful CRUD on `/api/v1/fault-trees`, `/api/v1/fault-trees/{id}/nodes`, `/api/v1/fault-trees/{id}/edges`
- **测试策略:** 单元测试须覆盖 DAG 验证器边缘情况: 空图、单节点、合法 DAG、含环图、断开子图、孤立节点

**FR 追溯:** FR34-5, FR34-7

### Story 24.4: 故障树版本管理与HMAC签名

As a 管理员,
I want 对故障树进行版本管理和完整性保护,
So that 故障树变更有迹可循，配置不会被未授权篡改。

**Acceptance Criteria:**

- Given 管理员编辑了一棵故障树
- When 创建新版本时
- Then 系统在 `fault_tree_version` 表创建记录（tree_id, version_number 自增, status=draft, snapshot JSON, hmac_signature=null, created_by）
- And `snapshot` 字段保存完整的节点+边结构的 JSON 快照（`json.dumps(config, sort_keys=True)`）
- When 管理员将版本状态从 draft 改为 reviewed
- Then 需要不同于创建者的管理员审批（`reviewed_by != created_by`）
- When 管理员激活版本时（reviewed → active）
- Then 系统使用 HMAC-SHA-256 对 snapshot 生成签名（密钥从环境变量 `FAULT_TREE_HMAC_KEY` 读取，最短 32 字节，启动时校验长度不足则拒绝启动）
- And 支持密钥轮换: 签名使用当前密钥，验证时同时尝试当前密钥和 `FAULT_TREE_HMAC_KEY_PREVIOUS`（可选），允许平滑过渡
- And 如果 `FAULT_TREE_HMAC_KEY` 环境变量未设置，应用启动时报错退出并记录明确错误信息
- And 签名验证通过后：将该版本标记为 active，将同一 tree 的其他 active 版本改为 archived
- And 诊断引擎收到版本切换事件后，从 DB 加载新版本 snapshot → 构建 NetworkX DiGraph → 替换内存中的旧图
- And 签名验证失败时：拒绝激活，保持旧版本，记录安全告警日志
- And 支持一键回滚到上一个 archived 版本（重新激活）
- And 故障树版本列表 API 返回版本号、状态、创建时间、创建人、激活时间

**技术实现要点:**
- HMAC 签名: `hmac.new(key=secret_key, msg=payload, digestmod=hashlib.sha256).hexdigest()`
- 密钥管理: `settings.FAULT_TREE_HMAC_KEY` + `FAULT_TREE_HMAC_KEY_PREVIOUS`（可选），从环境变量注入，Story 14.6 的 `.env.example` 需增加该变量
- 版本切换通知: Redis Pub/Sub `diagnosis:tree_version_change`，引擎订阅后热加载

**FR 追溯:** FR34-6, FR34-16

### Story 24.5: L2 故障树推理引擎

As a 运维工程师,
I want 系统基于故障树进行因果推理分析中等复杂度故障,
So that 我可以在5秒内获得包含根因路径和置信度的诊断结果。

**Acceptance Criteria:**

- Given 诊断调度器将任务路由到 L2 引擎，当前有活跃版本的故障树已加载到内存（NetworkX DiGraph）
- When L2 引擎接收到诊断任务（含告警设备ID和告警类型）
- Then 引擎执行以下步骤:
  1. **故障树选择与证据收集**: 通过 `fault_tree_device_mapping` 表（tree_id, device_type, alarm_type）匹配告警事件的 device_type + alarm_type 选择适用的故障树（可能匹配多棵，按优先级取第一棵），然后收集所有叶节点证据
     - 从 Redis 读取叶节点关联点位的最新值
     - 从 TimescaleDB 查询时间窗口内（按设备类型差异化：电气5min/温度30min/湿度60min，配置存储在 `system_configs` 表）的历史数据
     - 将点位值与叶节点阈值对比，通过 sigmoid 映射计算叶节点实际概率: `P = prior + (1.0 - prior) × sigmoid(k × (value - threshold))`（k 为斜率参数，默认 2.0，存储在节点配置中），使概率随偏离阈值的程度平滑变化而非二值跳变
  2. **正向概率传播**: 从叶节点向根节点传播
     - OR 门: P = 1 - ∏(1 - P(child_i))
     - AND 门: P = ∏ P(child_i)
  3. **根因路径提取**: 在传播过程中记录每个节点的"贡献度"（子节点概率对父节点概率的偏导），从根节点沿贡献度最大的子节点回溯（OR门→选概率最大的子节点，AND门→选偏离先验最大的子节点），生成根因路径
  4. **结果输出**: 根因节点、置信度（根节点概率）、推理路径（节点链）、证据列表
- And 全部过程 < 5 秒完成
- And 累计覆盖 Top 20 高频故障中 ≥18 类（90%，L1 12类 + L2 额外6类）
- And 推理过程中任何步骤异常（如点位查询超时）不中断推理，该证据标记为"不可用"使用先验概率替代

**技术实现要点:**
- NetworkX 图遍历: `reversed(list(nx.topological_sort(graph)))` 反转拓扑序（原始拓扑序从 root 开始，反转后从叶节点开始），保证从叶到根的传播顺序
- 时间窗口配置: 从 `system_configs` 表读取 `diagnosis_time_windows` JSON
- 证据收集并发: `asyncio.gather` 并行查询 Redis 和 TimescaleDB
- 超时保护: 整体 `asyncio.wait_for(inference(), timeout=10)`
- L2 推理函数返回 `DiagnosisContext` 数据类（包含: 完整节点概率映射 dict[str,float]、NetworkX DiGraph 引用、叶节点概率向量、证据收集结果列表），供 Story 26.2 L3 引擎复用（不仅返回最终结论）
- **测试策略:** 单元测试须覆盖: (1) 概率传播边缘情况（全零先验、全一先验、单子节点门、深层树 ≥10 层）; (2) sigmoid 映射极端输入（value=threshold±1000）; (3) 已知故障树+已知输入→已知输出的集成测试

**FR 追溯:** FR34-2, FR34-9, FR34-10, FR34-29（FR34-29 差异化时间窗口在此 Story 实现，Epic 25 FR 覆盖范围不含 FR34-29）

### Story 24.6: 诊断结果存储与分级推送

As a 运维工程师,
I want 诊断结果按置信度分级处理和推送,
So that 高置信度结果立即告知我，低置信度结果不产生干扰。

**Acceptance Criteria:**

- Given L1 或 L2 引擎完成推理，产生诊断结果
- When 结果置信度 > 80%
- Then 通过 WebSocket `/ws/alarms` 通道推送消息（type: "diagnosis_alert", target_roles: ["operator","admin"]），前端弹窗 + 声音提醒 + 高亮显示
- When 结果置信度 60%-80%
- Then 通过 WebSocket 推送（type: "diagnosis_suggestion"），前端在诊断面板"建议"区域展示，无声音
- When 结果置信度 < 60%
- Then 仅写入日志，诊断面板显示"分析中，暂无高置信度结论，请人工排查"
- And 所有诊断结果写入 `diagnosis_session` 表（trigger_alarm_id, device_id（冗余字段，方便按设备统计）, engine_level, start_time, end_time, inference_time_ms）
- And 诊断结论写入棕地已有 `diagnosis_results` 表（复数形式，通过 Alembic 迁移扩展字段: session_id, root_cause, confidence, reasoning_path JSON, evidence_list JSON, fault_tree_version）
- And 推理审计日志写入 `diagnosis_audit_log` 表（session_id, input_data JSON, output_data JSON, engine_level, inference_time_ms, fault_tree_version）
- And 所有级别的诊断结果均可在"诊断历史"列表中查询
- And 诊断结果报告包含: 根因、置信度、推理路径、证据列表（每条证据含时间戳 timestamp）

**技术实现要点:**
- WebSocket 消息格式: `{"type": "diagnosis_alert", "target_roles": [...], "data": {...}}`
- 前端: alarm Store 新增 `handleDiagnosisMessage` 处理分支，根据 `target_roles` 与当前用户角色匹配
- DB 表: Alembic 迁移创建 diagnosis_session, diagnosis_audit_log（新表），扩展已有 `diagnosis_results` 表增加 session_id/root_cause/confidence/reasoning_path/evidence_list/fault_tree_version 字段
- API: `GET /api/v1/diagnosis/sessions` 列表, `GET /api/v1/diagnosis/sessions/{id}` 详情

**FR 追溯:** FR34-11, FR34-12, FR34-17

### Story 24.7: 熔断降级机制

As a 开发者,
I want 诊断引擎具备熔断降级能力,
So that 推理引擎故障时系统自动回退到L1规则引擎，保证基本诊断能力不中断。

**Acceptance Criteria:**

- Given 诊断引擎正常运行（熔断器状态=CLOSED）
- When L2/L3 推理连续超时（>10秒）或错误率超过 10%（滑动窗口 60 秒内，至少 5 次请求）；低流量时（窗口内请求 < 5 次）切换到绝对计数模式：连续 3 次失败即触发熔断
- Then 熔断器状态切换为 OPEN，所有新诊断请求自动降级到 L1 规则引擎
- And 记录熔断事件到系统告警（"诊断引擎L2/L3熔断，已降级到L1"）
- When 熔断器处于 OPEN 状态 30 秒后
- Then 自动切换到 HALF_OPEN 状态，放行 1 个请求到 L2 试探
- And 试探成功（<10秒且无错误）→ 恢复 CLOSED 状态
- And 试探失败 → 回到 OPEN 状态，继续等待 30 秒
- And PostgreSQL 诊断表不可用时，诊断结果临时写入 Redis（key: `diagnosis:pending:{session_id}`, TTL: 1小时），DB 恢复后由定时任务批量写入
- And 熔断器状态可通过 `/api/v1/diagnosis/health` 查询

**技术实现要点:**
- CircuitBreaker 类: 状态机（CLOSED/OPEN/HALF_OPEN），滑动窗口计数器
- 降级写入: Redis hash 暂存，APScheduler 每分钟检查 pending keys 并尝试写入 DB
- 健康端点: `GET /api/v1/diagnosis/health` 返回 `{state, error_rate, last_trip_time}`

**FR 追溯:** FR34-41, Architecture 18.9

### Story 24.8: 诊断结果标注与RBAC

As a 运维工程师,
I want 对诊断结果进行准确性标注,
So that 系统可以积累反馈数据用于后续优化。

**Acceptance Criteria:**

- Given 运维工程师查看某条诊断结果
- When 点击"标注"按钮
- Then 可以选择"准确"、"不准确"、"未知"三种标注
- And 选择"不准确"时，必须从下拉列表选择或自由填写实际根因（不能为空）
- And 标注写入 `diagnosis_annotation` 表（result_id, annotator_id, annotation: accurate/inaccurate/unknown, actual_root_cause, annotated_at）
- And 系统监控标注偏差：APScheduler 每日统计每个用户的"不准确"标注率，若某用户标注率 > 均值 + 2σ，触发审查告警通知管理员
- And 诊断结果根据用户角色分级展示（复用棕地已有三角色体系 admin/operator/viewer）:
  - viewer（只读用户）: 仅结论 + 建议操作 + 置信度等级（高/中/低）
  - operator（运维）: 完整推理路径 + 概率详情 + 证据列表
  - admin（管理员）: 全部信息 + 审计日志 + 标注管理入口
- And RBAC 权限: 查看诊断结果(viewer+)、标注(operator+)、编辑故障树(admin)、审批故障树变更(admin)

**技术实现要点:**
- 标注 API: `POST /api/v1/diagnosis/sessions/{id}/annotate`
- 分级展示: API 响应中根据 `request.state.user.role` 过滤返回字段
- 偏差检测: APScheduler daily job，SQL 统计每用户不准确率并与全局均值+2σ对比

**FR 追溯:** FR34-18, FR34-19, FR34-36

---

## Epic 25: 智能诊断专业扩展

**阶段:** Phase 2b (月9-10)
**目标:** 扩展诊断引擎的专业能力：配电拓扑级联分析、电气参数集成、暖通增强。Go/No-Go门槛：准确率≥60% AND 误报率<10%（基于 ≥100 条预标注测试集 + 试运行期间标注数据，Sprint Review 验证；未达标则回退 L1+L2 基线版本）。
**FR 覆盖:** FR34-8, FR34-13~15, FR34-22~26, FR34-30~32（注：FR34-29 差异化时间窗口实际在 Epic 24 Story 24.5 实现）
**架构参考:** Architecture 18.5~18.8
**前置依赖:** Epic 24（核心引擎）, Epic 8（机房物理拓扑）

### Story 25.1: 配电拓扑级联分析

As a 运维工程师,
I want 系统在配电设备故障时自动分析受影响的下游设备,
So that 我可以快速评估故障影响范围并优先处理关键设备。

**Acceptance Criteria:**

- Given 配电拓扑数据已配置（Transformer → DistributionPanel → DistributionCircuit → PowerDevice，表名复用棕地已有 `distribution_circuits` 等复数形式表）
- When 诊断引擎启动时
- Then 从 4 张配电拓扑表加载数据，构建 NetworkX DiGraph 配电子图并缓存到内存
- And 设备/拓扑变更时通过 DeviceSyncService 事件触发增量更新子图（采用 copy-on-write：创建新图副本 → 修改副本 → 原子替换引用，避免推理期间的竞态条件）
- When 某配电设备（如 PDU）触发故障告警
- Then 执行向下级联分析: `nx.descendants(graph, fault_node)` 列出所有受影响的下游设备（机柜、服务器等）
- And 执行向上溯源: `nx.ancestors(graph, fault_node)` 追溯上游配电设备链（回路→配电柜→变压器）
- When 运维工程师在某台末端设备（如服务器）上触发诊断
- Then 支持向上溯源，列出供电链路上的所有上游设备及其当前状态
- And 级联分析结果附加到诊断结果的 `impact_analysis` 字段

**技术实现要点:**
- 图构建: `build_power_topology_graph()` 在 FastAPI lifespan 中调用
- 节点命名: `T-{id}`(Transformer), `P-{id}`(DistributionPanel), `C-{id}`(DistributionCircuit), `D-{id}`(PowerDevice) 区分层级
- 增量更新: 监听 DeviceSyncService 的 Redis 事件 `device:topology_change`

**FR 追溯:** FR34-13, FR34-14, FR34-15

### Story 25.2: 电气参数节点集成

As a 运维工程师,
I want 故障树能利用三相不平衡度、THD、功率因数等电气参数作为诊断证据,
So that 诊断引擎能识别电气专业问题（如谐波过高导致UPS异常）。

**Acceptance Criteria:**

- Given 管理员在故障树中创建叶节点，关联了电气参数类型的点位
- When 诊断引擎收集证据时
- Then 支持以下电气参数类型作为故障树叶节点输入:
  - 三相不平衡度: 点位值 > 10% 时作为异常证据（概率→0.9）
  - 谐波畸变率 THD: 点位值 > 5% 时作为异常证据
  - 功率因数: 点位值 < 0.9 时作为异常证据
- And 阈值可在故障树节点配置中自定义（非硬编码）
- And 电气参数概率计算复用 Story 24.5 的 sigmoid 连续映射方式（不再二值化），阈值和斜率参数可在节点配置中自定义

**技术实现要点:**
- 故障树叶节点增加 `threshold_type` 字段 (ABOVE/BELOW)，`threshold_value` 字段，`sigmoid_k` 字段（斜率，默认 2.0）
- 证据收集时复用 L2 引擎统一的 sigmoid 映射函数: `calc_evidence_probability(value, threshold, threshold_type, sigmoid_k, prior)`

**FR 追溯:** FR34-22

### Story 25.3: UPS电池SOH预测

As a 运维工程师,
I want 系统预测UPS电池健康度,
So that 我可以在电池失效前提前更换，避免UPS保护失效。

**Acceptance Criteria:**

- Given UPS 设备已采集内阻和充放电循环次数点位数据
- When APScheduler 每日定时任务执行 SOH 计算
- Then 对每台 UPS 计算 SOH = resistance_factor * w_r + cycle_factor * w_c（权重从 `system_configs` 加载，默认 w_r=0.6, w_c=0.4）
  - resistance_factor = clip(1 - (当前内阻 - 额定内阻) / 额定内阻, 0, 1.0)
  - cycle_factor = clip(1 - 充放电次数 / 额定循环次数, 0, 1.0)
- And 结果写入 `battery_soh_record` 表（device_id, soh_percent, resistance_mohm, cycle_count, weights_version, calculated_at）
- And 如果 `rated_resistance_mohm` 或 `rated_cycle_count` 为 0 或 null，跳过该 UPS 并记录警告日志"Missing rated parameters for device X, SOH calculation skipped"
- And 如果当前内阻或循环次数点位在 Redis 中不可用（null），使用 `battery_soh_record` 表中最近一次 SOH 值，无历史记录则跳过
- And SOH < 80% 触发"关注"级别告警，SOH < 60% 触发"预警"级别告警
- And SOH 结果反馈到故障树: UPS 相关叶节点的先验概率根据 SOH 调整（SOH<60% → 先验概率×1.5，上限0.95）
- And SOH 结果同时反馈到设备健康度评估（FR75）的评分计算
- And UPS 设备模板（`device_templates` 表）的 `point_config` JSON 中需包含 `rated_resistance_mohm` 和 `rated_cycle_count` 字段，Story 实现时通过 Alembic 数据迁移脚本为现有 UPS 模板补充默认额定参数

**技术实现要点:**
- 额定参数: 棕地 `device_templates` 表的 `point_config` JSON 中需扩展 UPS 模板，增加 `rated_resistance_mohm`（额定内阻）和 `rated_cycle_count`（额定循环次数）字段；AC 中应包含"扩展 UPS 设备模板配置"步骤
- 权重管理: `system_configs` 表 `soh_weights` JSON，管理员可通过 API 调整
- 定时任务: APScheduler `cron` trigger, 每日凌晨 3:00

**FR 追溯:** FR34-23

### Story 25.4: N+X冗余拓扑与断路器保护逻辑

As a 运维工程师,
I want 诊断引擎理解冗余供电路径和断路器保护动作,
So that 系统不会将有备用路径的单点故障或正常的保护动作误判为严重故障。

**Acceptance Criteria:**

- Given 管理员在配电拓扑中标记了冗余路径（PowerDevice 表增加 `redundancy_type` 字段: N+1/2N/NULL）
- When 诊断引擎分析某配电设备故障时
- Then 检查该设备是否有活跃的冗余备用路径（查询同一回路或并联回路中 status=normal 的同类设备）
- And 有活跃备用路径 → 降低故障影响等级为"受控故障"，诊断结论标注"已有备用路径自动切换"
- And 无活跃备用路径 → 正常故障告警等级
- And Alembic 迁移脚本创建 `breaker_profile` 表（breaker_device_id, trip_curve_type B/C/D, rated_current, rated_trip_time_ms）和 PowerDevice 表新增 `redundancy_type` 字段
- Given 管理员在 `breaker_profile` 表中录入了断路器特性
- When 出现过流告警且关联断路器动作
- Then 根据实际过载倍数（实际电流/额定电流）查找 `breaker_profile` 中的倍数-时间范围映射表判定:
  - B型: 3倍→3-45s, 5倍→0.04-0.1s
  - C型: 5倍→1.3-15s, 10倍→0.04-0.1s
  - D型: 10倍→1-8s, 50倍→0.04-0.1s
  - 介于映射点之间的倍数使用线性插值
- And 动作时间在映射范围内 → 判定为"保护动作"（非故障），置信度标记为"保护正常动作"
- And 动作时间异常（超出范围）或过流但未动作 → 判定为"设备故障"

**技术实现要点:**
- 冗余查询: 同 circuit_id 或 redundancy_group_id 的设备中查找 status=normal 的
- 断路器判定: 按曲线类型 + 过载倍数查表（`BREAKER_CURVES` dict），介于映射点之间用线性插值计算时间范围
- Alembic 迁移: PowerDevice 加 `redundancy_type` 字段，新建 `breaker_profile` 表

**FR 追溯:** FR34-24, FR34-26

### Story 25.5: 传感器元数据与精度加权

As a 运维工程师,
I want 诊断引擎根据传感器精度调整证据可信度,
So that 高精度传感器的数据在推理中权重更大，过期未校准的传感器数据权重降低。

**Acceptance Criteria:**

- Given 管理员在 `sensor_metadata` 表中录入传感器元数据（point_id, ct_pt_ratio, accuracy_class: 0.2/0.5/1.0, calibration_date, calibration_interval_days 默认365, calibration_result）
- When 诊断引擎收集叶节点证据时
- Then 查询该点位的传感器元数据
- And 根据精度等级调整证据权重: 0.2级→1.0, 0.5级→0.9, 1.0级→0.8
- And 若 `当前日期 - calibration_date > calibration_interval_days`，权重额外降为 0.6，并触发"传感器需校准"提醒告警
- And 无元数据的点位使用默认权重 0.85（不影响现有系统）
- And 证据权重通过收缩公式调整叶节点概率: `P_adj = prior + (P_obs - prior) × weight`（权重越低，观测概率越向先验回归，避免系统性压低所有概率）

**技术实现要点:**
- Alembic 迁移: 新建 `sensor_metadata` 表
- 管理 API: `GET/PUT /api/v1/sensors/metadata`
- 内存缓存: 服务启动时将 sensor_metadata 全量加载到 `dict[int, SensorMeta]`（按 point_id 索引），通过 Redis Pub/Sub `sensor:metadata_update` 热更新（类似规则引擎缓存策略），避免推理时逐条查 DB
- 证据收集: 在 L2 引擎的证据收集阶段从内存缓存读取元数据并计算权重

**FR 追溯:** FR34-25

### Story 25.6: 动态告警阈值

As a 运维工程师,
I want 系统根据环境因素自动调整温湿度告警阈值,
So that 夏季高温高负载时不会产生大量虚假告警。

**Acceptance Criteria:**

- Given 管理员在 `system_configs` 中配置了动态阈值规则（JSON 格式: conditions + adjustments 列表）
- When 告警引擎执行阈值检测时
- Then 先查询当前环境上下文（室外温度点位值、IT总负载百分比、当前季节）
- And 逐条评估规则，累加调整量
- And 最终调整量不超过静态阈值的 ±20%（安全边界）
- And 使用调整后的阈值进行告警判断
- And 每次动态调整记录到日志（原始阈值、调整后阈值、触发的规则、环境上下文）
- And 管理员可通过 `/api/v1/diagnosis/config` 修改规则，无需改代码
- And 动态阈值功能受 `DYNAMIC_THRESHOLDS_ENABLED` 环境变量控制（默认 false），未启用时告警引擎使用静态阈值不受影响
- And `DynamicThresholdService.adjust()` 调用被 try/except 包裹，异常时回退到静态阈值并记录错误日志，确保告警引擎稳定性不受影响
- And Epic 5（MVP 阶段）的告警引擎单元测试在不配置 DynamicThresholdService 的情况下必须继续通过

**技术实现要点:**
- 规则引擎: 简单的条件表达式解析器（支持 >, <, ==, AND/OR），从 JSON 加载
- 集成点: 在 `backend/app/services/alarm_engine.py` 的 `check_threshold()` 方法中，阈值比对前调用 `DynamicThresholdService.adjust(point_id, static_threshold)` 获取调整后阈值。DynamicThresholdService 作为独立服务类，通过 feature flag 控制激活
- 上下文获取: 从 Redis 读取室外温度和负载点位，季节由当前月份推断

**FR 追溯:** FR34-30

### Story 25.7: 趋势分析与多传感器融合

As a 运维工程师,
I want 系统检测缓变型故障趋势和气流异常,
So that 空调效率缓慢下降或冷通道气流不均匀等问题能被提前发现。

**Acceptance Criteria:**

- Given 系统已积累 ≥7 天的温湿度历史数据
- When 历史数据不足 7 天时，趋势分析任务记录日志"Insufficient data for trend analysis on point X (N days available, 7 required)"并跳过该点位，不产生错误
- When APScheduler 每小时执行趋势分析任务
- Then 使用 TimescaleDB 连续聚合视图计算每个温湿度点位的 7 天移动平均
- And 检测连续 3 天移动平均单调递增或递减，且 3 天累计变化量 > 阈值（温度默认 0.5℃，湿度默认 3%RH，阈值存储在 `system_configs` 可配置）→ 触发趋势预警（级别低于阈值告警，不触发声音）
- And 预警信息: "温度点位 T-A01-01 连续3天呈上升趋势（均值从25.2→26.1→27.0），建议检查空调运行状态"
- Given 同区域有多个温度传感器
- When 推理引擎执行多传感器融合时
- Then 计算同区域所有温度传感器值的标准差
- And 标准差 > 5℃ → 作为"气流不均匀"证据（is_evidence=true），概率设为 0.85
- And 标准差 2-5℃ → 标记为"moderate"，不作为证据但记录到诊断附加信息
- And 查询地板下压差传感器值 < 设定值 → 作为"送风系统异常"证据
- And 趋势预警和融合结果可作为 L2/L3 推理的补充证据输入

**技术实现要点:**
- TimescaleDB 连续聚合: `CREATE MATERIALIZED VIEW temp_7d_avg WITH (timescaledb.continuous) AS SELECT time_bucket('1 day', time), point_id, avg(value) ...`，需设置 `ALTER MATERIALIZED VIEW temp_7d_avg SET (timescaledb.materialized_only=false)` 以确保查询包含未物化的最新数据
- 趋势检测: SQL 查询最近 3 天日均值，Python 判断单调性
- 融合计算: `statistics.stdev(temperatures)` 对同 cooling_zone_id 的温度点位

**FR 追溯:** FR34-31, FR34-32

### Story 25.8: 故障树图形化编辑器

As a 管理员,
I want 通过可视化图形界面编辑故障树结构,
So that 我可以直观地创建和修改故障树节点、门、边，而不需要通过 API 或 JSON 手动编辑。

**Acceptance Criteria:**

- Given 管理员进入故障树管理页面 (`/diagnosis/fault-trees/{id}/editor`)
- When 页面加载
- Then 使用 vis-network 渲染当前故障树的 DAG 结构（节点为圆形/矩形，边为有向箭头），根节点在顶部，叶节点在底部
- And 节点颜色区分类型：根节点(红色)、中间门节点(蓝色 AND/橙色 OR)、叶节点(绿色)
- And 支持拖拽添加新节点（从左侧面板拖入画布）：可添加 AND 门、OR 门、叶节点（关联告警类型）
- And 支持拖拽连线创建边（从源节点拖向目标节点）
- And 双击节点弹出属性编辑面板：名称、描述、先验概率（叶节点）、门类型（中间节点）、关联设备类型（叶节点）
- And 支持删除节点和边（选中后按 Delete 键或右键菜单）
- And 每次编辑操作后实时执行 DAG 校验：检测环路、检测孤立节点、验证所有节点可达根节点
- And DAG 校验失败时在画布上高亮问题节点/边并显示错误提示，阻止保存
- And 保存时调用 `/api/v1/fault-trees/{id}/versions` 创建新版本（走 Story 24.4 版本管理流程）
- And 支持撤销/重做（Ctrl+Z / Ctrl+Shift+Z），最多 50 步
- And 画布支持缩放（滚轮）和平移（拖拽空白区域）
- And 大型故障树（>100 节点）支持分层折叠/展开子树

**技术实现要点:**
- 前端: vis-network 库（需确认 package.json 中是否已安装，如无则 `npm install vis-network vis-data`；轻量级图可视化）
- 数据绑定: vis-network DataSet 双向绑定，编辑操作直接更新 DataSet
- DAG 校验: 前端使用拓扑排序检测环路（vis-network 不内置，需自行实现 Kahn 算法）。前端校验为即时反馈（允许中间不完整状态），后端校验（Story 24.3）为权威最终校验，保存时两者都执行
- API: 保存时将 vis-network 的 nodes/edges 转换为后端 `fault_tree_node` / `fault_tree_edge` 格式，调用批量更新 API
- 性能: vis-network 在 1000 节点以内性能良好（NFR-DP6 要求），超过时启用 physics 关闭 + 手动布局

**FR 追溯:** FR34-8

---

## Epic 26: 智能诊断高级功能

**阶段:** Phase 3 (月11-12+)
**目标:** 实现全局因果图、闭环学习自动调参、可解释性增强、L3贝叶斯深度分析。全面上线门槛：准确率≥75%（基于 ≥200 条标注数据）AND 用户满意度≥80%（运维团队 ≥5 人问卷调查"诊断结果对故障处理有帮助"评分 ≥4/5 的比例；未达标则保持 L1+L2 为默认，L3 标记为 Beta）。
**FR 覆盖:** FR34-3, FR34-20~21, FR34-27~28, FR34-33~42（含 FR34-35）
**架构参考:** Architecture 18.2(L3), 18.6, 18.10~18.13
**前置依赖:** Epic 25（专业扩展），累计标注数据≥50次/节点

### Story 26.1: 全局因果图构建

As a 管理员,
I want 构建跨系统全局因果图,
So that 诊断引擎能分析跨配电/暖通/IT/业务的级联故障传播链。

**Acceptance Criteria:**

- Given 各子系统故障树已建立（Epic 24）
- When 管理员通过 `/api/v1/causal-graph` API 定义跨系统传播边
- Then 系统在 `causal_graph` 表创建因果图记录（name, version, status）
- And 在 `causal_edge` 表定义跨系统边（source_node_id 引用故障树节点, target_node_id 引用故障树节点, propagation_type: causes/correlates, propagation_delay_seconds, description）
- And 因果图引用故障树节点 ID（外键），不复制节点数据
- And 运行时加载: 故障树子图 + 跨系统边 → 合并为一个 NetworkX DiGraph
- When 某配电设备故障触发诊断
- Then 执行向下级联预测: `nx.descendants(graph, fault_node)` 列出可能受影响的暖通/IT/业务节点
- When 某末端设备异常触发诊断
- Then 执行向上溯源: `nx.ancestors(graph, symptom_node)` 追溯上游供电/制冷设备
- And 因果图变更纳入故障树版本管理体系（独立版本号），需管理员审批 + HMAC 签名
- And 因果图保存/编辑时验证所有边引用的节点在对应故障树的 active 版本中存在，不存在则拒绝保存并返回错误
- And 故障树版本更新时，系统自动检测因果图中是否存在断裂边（引用了已删除的节点），有则告警

**技术实现要点:**
- 表设计: `causal_graph` (id, name, version, status, hmac_signature), `causal_edge` (graph_id, source_node_id FK→fault_tree_node, target_node_id FK→fault_tree_node, propagation_type, delay_seconds)
- 合并逻辑: 加载所有 active 故障树的 NetworkX 子图 → 添加 causal_edge 定义的跨图边
- 断裂检测: 故障树激活新版本时，查询 causal_edge 中引用了旧版本已删节点的边

**FR 追溯:** FR34-27, FR34-28

### Story 26.2: L3 贝叶斯深度分析 — 正向传播与历史频率校正

As a 运维工程师,
I want 系统能对罕见故障启动深度推理，利用历史数据校正先验概率,
So that L1/L2无法确诊的复杂故障能基于历史频率获得更准确的初步判断。

**Acceptance Criteria:**

- Given 诊断调度器将任务路由到 L3 引擎
- When L3 引擎接收到诊断任务
- Then 执行以下步骤:
  1. **L2 正向传播**（复用 Story 24.5 逻辑）获得初步结果，记录根节点概率 P(effect)
  2. **历史频率校正**: 查询 TimescaleDB 近 90 天同一根节点的故障频率（`SELECT count(*) FROM diagnosis_results WHERE root_cause=X AND created_at > now()-90d`），若样本≥50则用历史频率替代先验概率
  3. 将校正后的先验概率和正向传播结果保存到诊断会话上下文，供 Story 26.2b 使用
- And 历史频率查询使用连续聚合视图加速，单次查询 < 2 秒
- And L3 引擎入口函数 `l3_inference()` 包含整体超时保护: `asyncio.wait_for(l3_inference(), timeout=60)`，涵盖 26.2 和 26.2b 的全部逻辑（两者在代码中是同一函数的上下半段，拆分为两个 Story 仅用于 Sprint 规划粒度控制）

**技术实现要点:**
- 历史频率查询: TimescaleDB 聚合查询，使用连续聚合视图加速
- 会话上下文: 存储在诊断会话内存对象中，供 26.2b 步骤使用
- 超时: 60 秒超时保护在入口函数设置一次，覆盖整个 L3 流程

**FR 追溯:** FR34-3

### Story 26.2b: L3 贝叶斯深度分析 — 逆向贝叶斯推理与排序

As a 运维工程师,
I want 系统通过逆向贝叶斯推理计算各原因的后验概率并排序输出,
So that L1/L2无法确诊的复杂故障也能获得可能的根因判断。

**Acceptance Criteria:**

- Given Story 26.2 的正向传播和历史频率校正已完成
- When L3 引擎执行逆向贝叶斯推理
- Then 执行矩阵化批量传播（避免 N 次独立遍历）：
  - 构建叶节点概率矩阵 P_leaf[N×N]：对角线元素为 1.0（假设该叶节点为真因），其余为先验值
  - 通过 numpy 矩阵运算沿拓扑序批量传播所有 N 种假设，得到 P_root[N] 即 P(effect|cause_i)
  - **AND 门修正**: 当 AND 门的非假设子节点先验概率较低时，P(effect|cause_i) 会被严重压低。对 AND 门的非假设子节点使用 max(先验, 0.5) 作为条件概率下限，避免单一低先验叶节点导致所有假设的后验概率趋近于零
  - P(cause_i): 叶节点 i 的先验概率（经历史频率校正后）
  - P(effect): L2 正向传播得到的根节点概率
  - P(cause_i|effect) = P(effect|cause_i) × P(cause_i) / P(effect)
  - 矩阵化方式: P_leaf 矩阵的每一列代表一种叶节点假设，按反向拓扑序逐层传播，每层根据门类型对整个 numpy 数组执行向量化 OR/AND 运算（N 种假设在数组不同列上并行计算）
  - 性能: 100 个叶节点 × 1000 节点图的矩阵化传播 < 0.5 秒（numpy 向量化），不会成为 30 秒瓶颈
- And **多传感器融合增强**: 聚合同区域多点位数据（复用 Story 25.7 的融合逻辑），作为补充证据
- And **综合排序**: 按后验概率排序输出 Top 5 根因候选，每个附带置信度和证据链
- And 全部过程（含 Story 26.2）< 30 秒（主要耗时在 TimescaleDB 历史查询）
- And 覆盖 Top 20 全部故障场景（100%）
- And L3 不引入额外库（复用 NetworkX + numpy 的基础运算）

**技术实现要点:**
- 贝叶斯计算: numpy 矩阵运算加速叶节点后验概率批量计算
- 融合: 复用 Story 25.7 的 `_calculate_sensor_fusion()` 方法
- 排序: 按 P(cause_i|effect) 降序，取 Top 5

**FR 追溯:** FR34-3

### Story 26.3: 闭环学习自动调参

As a 管理员,
I want 系统基于运维标注数据自动优化故障树概率参数,
So that 诊断准确率随使用时间持续提升。

**Acceptance Criteria:**

- Given 某故障树根因节点（root_cause）在 `diagnosis_results` 中被标注为"准确"或"不准确"的累计次数 ≥ 50 条
- When APScheduler 每周定时任务执行概率调参分析
- Then 统计调参逻辑:
  - 对于根因节点: 计算诊断准确率 = 标注"准确"次数 / 总标注次数。准确率 > 先验概率 → 小幅上调先验（说明该故障比预期更常见），准确率 < 先验概率 → 小幅下调先验（说明该故障被高估）。调整方向由准确率与先验的差值决定，而非直接替换
  - 对于中间/叶节点: 统计该节点参与的所有诊断中，最终结论被标注为"准确"的比例；若与该节点当前先验概率偏差 > 10%，标记为"建议调参"供管理员人工判断
- And 对比当前先验概率，计算调整量 = 实际概率 - 先验概率
- And 若 |调整量| > 先验概率 × 10%，则截断到 ±10% 边界
- And 生成"概率调参审批工单"（probability_adjustment_log 表: node_id, current_probability, proposed_probability, sample_count, adjustment_percent, status=pending）
- And 通知管理员审批（系统告警 + 邮件/WebSocket 推送）
- When 管理员审批确认
- Then 更新故障树节点先验概率，创建新故障树版本（自动走 Story 24.4 的版本管理流程）
- When 管理员拒绝或需要回滚
- Then 支持一键回滚到上一版参数（激活上一个 archived 版本）

**技术实现要点:**
- 统计查询: 按 node_id 分组统计标注结果
- 审批流: 复用现有工单审批机制，或简化为管理员在 API 上 `POST /api/v1/fault-trees/{id}/probability-adjustments/{adj_id}/approve`
- 定时任务: APScheduler weekly job

**FR 追溯:** FR34-20

### Story 26.4: 时间窗口自适应

As a 管理员,
I want 系统自动优化诊断时间窗口参数,
So that 不同类型故障的证据收集窗口更精准。

**Acceptance Criteria:**

- Given 某设备类型的标注数据中"准确"标注的故障持续时间数据 ≥ 30 条
- When APScheduler 月度定时任务执行
- Then 统计该设备类型故障的持续时间 P50（中位数）和 P90
- And 建议时间窗口 = P90 × 1.2（留 20% 裕度）
- And 调整范围限制: 最小 1 分钟，最大 120 分钟
- And 生成调整建议通知管理员（当前值 → 建议值 + 统计依据）
- And 管理员确认后更新 `system_configs` 中的 `diagnosis_time_windows` 配置

**技术实现要点:**
- 持续时间来源: 标注"准确"的诊断对应的源告警的持续时间（`alarm.recovered_at - alarm.created_at`，从 alarm 表 JOIN 获取），仅统计已恢复的告警
- 统计: SQL `percentile_cont(0.5)` 和 `percentile_cont(0.9)`

**FR 追溯:** FR34-21

### Story 26.5: 证据链与可解释性

As a 运维工程师,
I want 诊断结果附带清晰的证据链和敏感性分析,
So that 我能理解诊断逻辑并判断结果是否可信。

**Acceptance Criteria:**

- Given 诊断引擎完成一次推理
- When 生成诊断结果时
- Then 附带结构化证据链 JSON:
  - 每步包含: step序号、规则/门名称、关联点位ID、点位值、阈值/期望值、时间戳(timestamp)
  - 最终步骤包含: 门类型(AND/OR)、计算概率
- And 对 Top 3 关键证据（按"概率偏离先验的绝对值 |P_obs - P_prior|"降序排列，偏离越大=对结论影响越大）执行简化反事实分析:
  - 逐一将每个证据的概率设为先验值（模拟"该证据正常"）
  - 重新执行概率传播
  - 输出: "若点位 T-A01-01 读数正常，根因将变为 X（置信度从 0.82 降至 0.45）"
  - 共执行 3 次额外推理（计算时间可接受）
- And 审计日志满足 ISO 27001/SOC 2 要求: 记录触发源、输入数据、推理路径、输出结果、引擎级别、故障树版本、推理耗时

**技术实现要点:**
- 证据链构建: 在推理过程中逐步记录每个节点的计算过程
- 反事实: 修改叶节点概率 → 重新调用 `propagate_probabilities` → 对比结果
- 性能: 3 次额外传播对 1000 节点图耗时 < 1 秒

**FR 追溯:** FR34-38, FR34-39

### Story 26.6: 误判分析报告

As a 管理员,
I want 系统每月自动生成误判分析报告,
So that 我可以识别诊断系统的薄弱环节并有针对性地优化。

**Acceptance Criteria:**

- Given 系统已运行 ≥ 1 个月且有标注数据
- When APScheduler 月度定时任务触发（每月1日凌晨）
- Then 生成 Markdown 格式误判分析报告，包含:
  - 统计周期: 上月 1 日至末日
  - 总诊断次数、已标注次数、标注覆盖率
  - 误判类型分布: 误报（诊断有结论但标注为不准确）次数/占比、漏报（告警产生后30分钟内诊断引擎无任何结论，但告警最终被人工确认为真实故障——通过工单系统关联告警且工单类型=故障修复来识别）次数/占比
  - 高频误判故障树节点: Top 5 被标注为"不准确"最多的根因节点
  - 设备类型误判分布: 按设备类型统计误判率
  - 改进建议: 根据高频误判节点自动生成（如"节点X误判率32%，建议检查先验概率或增加证据维度"）
- And 报告存储在棕地已有 `report_records` 表（对应 ORM 模型 `ReportRecord`，report_type='diagnosis_monthly'），通过现有报表模板基础设施生成
- And 生成后通知管理员查看

**技术实现要点:**
- SQL 聚合: JOIN diagnosis_results + diagnosis_annotations 按节点/设备类型分组统计
- Markdown 生成: Python f-string 模板
- 存储: 复用棕地已有 `report_records` 表（`ReportRecord` 模型），不新建 `system_report` 表

**FR 追溯:** FR34-40

### Story 26.7: 灾难恢复演练

As a 管理员,
I want 系统定期演练诊断引擎灾难恢复流程,
So that 降级机制经过验证确实有效。

**Acceptance Criteria:**

- Given 管理员在 `/api/v1/diagnosis/chaos/schedule` 配置了演练计划
- When 到达演练窗口（默认: 周日凌晨 02:00-04:00，管理员可调整）且管理员已确认
- Then 按序执行演练场景:
  1. 临时停止 L2/L3 推理能力（设置熔断器为 OPEN）→ 验证 L1 降级是否在 < 30 秒内生效
  2. 模拟 PostgreSQL 诊断表查询超时 → 验证 Redis 暂存是否工作
  3. 记录演练结果: 每个场景的恢复时间、降级成功/失败、数据完整性
- And 演练期间所有真实告警自动走 L1 规则引擎（跳过被注入故障的组件）
- And 演练期间的诊断结果标记 `is_drill=true`，不计入准确率统计
- And 管理员可随时通过 `/api/v1/diagnosis/chaos/stop` 终止演练
- And 演练结束后生成演练报告（降级时间、恢复时间、问题列表），存储到 `report_records` 表（report_type='diagnosis_drill'）
- And 演练后自动恢复所有注入的故障（熔断器→CLOSED，DB连接→正常）

**技术实现要点:**
- 演练调度: APScheduler 季度 cron job，执行前检查 `chaos_confirmed` 标志
- 故障注入: 设置 CircuitBreaker 状态为 OPEN / 在 DiagnosisService 中设置 `_inject_db_fault=True` 标志，仅对诊断相关 DB 查询注入 asyncio.sleep(15) 延迟（不影响其他业务 DB 操作）
- 安全保护: `is_drill_mode` 全局标志，真实告警跳过被注入故障的路径

**FR 追溯:** FR34-42

### Story 26.8: 边缘推理预留与SBOM管理

As a 开发者,
I want 为边缘推理预留接口并建立依赖安全管理,
So that 未来扩展边缘推理时无需重构，且第三方库漏洞能及时发现。

**Acceptance Criteria:**

- Given 网关层代码已存在
- When 开发者在网关代码中预留诊断接口
- Then 在 gateway 模块中定义 `DiagnosisHandler` 抽象接口（connect/receive_rules/execute_l1/report_result），但不实现具体逻辑
- And 中心节点预留 MQTT topic `dcim/diagnosis/rules/{gateway_id}` 用于未来下发规则
- And 在项目 CI 中集成 `pip-audit`（后端）扫描已知漏洞
- And 维护 `SBOM.md` 文件列出关键算法依赖: NetworkX（版本、许可证MIT）、scikit-learn（版本、许可证BSD）、numpy（版本、许可证BSD）
- And 关键库发现高危漏洞（CVSS ≥ 7.0）时触发系统告警

**技术实现要点:**
- 预留接口: 抽象类定义 + NotImplementedError
- SBOM: 手动维护的 Markdown 文件，CI 中 `pip-audit --format json` 自动扫描
- 告警: CI pipeline 失败时通知，或 APScheduler 每周运行 `pip-audit`

**FR 追溯:** FR34-33, FR34-34, FR34-37

### Story 26.9: 训练数据异常检测（对抗样本防护）

As a 管理员,
I want 系统自动检测闭环学习训练数据中的异常和潜在对抗样本,
So that 异常标注数据不会污染故障树概率参数，保障诊断准确率长期稳定。

**Acceptance Criteria:**

- Given 闭环学习（Story 26.3）准备执行概率调参
- When 调参任务启动前执行数据质量检查
- Then 使用 scikit-learn 的 IsolationForest 对训练数据执行异常检测:
  - 特征向量: [诊断耗时, 触发告警数, 证据节点数, 根因概率, 叶节点异常比例, 诊断-标注时间差(秒)]（不包含标注结果本身——将标签作为特征检测标签质量是循环逻辑）
  - 训练集: 最近 180 天全部标注数据（至少 100 条才启用检测，不足则跳过并记录日志）
  - contamination 参数: 0.05（预设 5% 异常率，存储在 `system_configs` 可配置）
  - 异常判定: IsolationForest.predict() 返回 -1 的样本标记为异常
- And 异常样本处理策略:
  - 异常率 ≤ 10%: 降低异常样本权重至 0.1（原始权重 1.0），参与调参但影响被抑制
  - 异常率 > 10% 且 ≤ 30%: 移除全部异常样本，仅用正常样本调参，并通知管理员"异常标注比例偏高，建议检查标注质量"
  - 异常率 > 30%: 中止本次调参，生成告警"训练数据质量严重异常（异常率 {X}%），已中止自动调参，请人工审查标注数据"
- And 检测结果记录到 `training_data_audit` 表（audit_id, run_date, total_samples, anomaly_count, anomaly_rate, action_taken, anomaly_sample_ids JSON）
- And 管理员可在 `/api/v1/diagnosis/training-audit` 查看历史检测报告
- And 管理员可对误判的"异常样本"手动标记为"已确认正常"，下次检测时排除

**技术实现要点:**
- IsolationForest: `from sklearn.ensemble import IsolationForest`，scikit-learn 已在 Epic 24 依赖中（用于未来扩展），无需额外安装
- 特征工程: 从 `diagnosis_results` + `diagnosis_annotations` 表 JOIN 提取特征
- 集成点: 在 Story 26.3 的 `_execute_probability_adjustment()` 方法开头调用 `_check_training_data_quality()` 前置检查
- 性能: IsolationForest 对 1000 条 × 6 特征数据训练 + 预测 < 1 秒

**FR 追溯:** FR34-35

---

## Epic 27: 前端数据链路统一

**阶段:** MVP (月1-3，与 Epic 14 并行)
**目标:** 消除前端数据割裂问题，确保每个数据实体有且仅有一个 Pinia Store 作为事实来源，避免多页面数据不同步。
**实施优先级:** Story 27.1(P0)→27.2(P0)→27.5(P1) 为核心路径，应在 Epic 4/5/6 实施前或同步完成；Story 27.3(P1)、27.4(P1) 可并行；Story 27.6(P2) 可延迟到 Epic 22 就绪后。
**NFR 覆盖:** NFR-P1(性能-减少冗余连接), NFR-M1(可维护性-单一事实来源)
**参考文档:** `docs/data-flow-audit.md`, `architecture.md` Section 19

### Story 27.1: 告警数据链路统一（方案 A）

As a 用户,
I want 所有页面的告警数据来自同一个数据源,
So that 仪表盘、告警列表、大屏、告警铃铛显示的告警计数和列表始终一致。

**Acceptance Criteria:**

- Given AlarmStore 作为告警数据的唯一事实来源
- When 后端通过 WebSocket 推送新告警
- Then AlarmStore 接收并更新 `activeAlarms` 和 `alarmCount`
- And `useAlarm` composable 不再持有自有的 `activeAlarms` ref 和 `alarmCount` ref，改为读取 `alarmStore.activeAlarms` 和 `alarmStore.alarmCount`
- And `useAlarm` composable 的 `addAlarm`/`updateAlarm` 操作直接调用 AlarmStore action
- And BigscreenStore 移除 `activeAlarms` 状态属性，改用 getter 从 `useAlarmStore()` 派生
- And Dashboard (`views/dashboard/index.vue`) 移除局部 `activeAlarms` ref，改为直接读取 `alarmStore.activeAlarms`
- And Dashboard 移除 `dcim_dashboard_cache` 中告警相关的 sessionStorage 缓存
- And 环境监控温度页面（`views/environment/temperature.vue:310`）移除直接调用 `getActiveAlarms()` API 的逻辑，改为从 AlarmStore 读取按 point_id 过滤的告警
- And DemoDataLoader 的 `@loaded`/`@unloaded` 事件处理中，调用 `alarmStore.fetchActiveAlarms()`、`realtimeStore.reload()`、`energyStore.reload()` 刷新全局 Store，确保所有页面数据同步更新
- And 在以下 5 个页面验证告警计数一致性：仪表盘、告警列表页、大屏、Header 告警铃铛、环境监控温度页

**涉及文件:**
- `frontend/src/stores/alarm.ts` — 增加 `fetchActiveAlarms()` action
- `frontend/src/composables/useAlarm.ts` — 移除自有 ref，代理 store
- `frontend/src/stores/bigscreen.ts` — `activeAlarms` 改为 getter
- `frontend/src/views/dashboard/index.vue` — 移除局部告警 ref
- `frontend/src/views/environment/temperature.vue` — 改为从 AlarmStore 读取告警
- Header 告警铃铛组件（`components/` 或 `layouts/` 下）— 确认已从 AlarmStore 读取
- `frontend/src/components/DemoDataLoader.vue` — `@loaded`/`@unloaded` 事件触发全局 Store 刷新

**NFR 追溯:** NFR-P1, NFR-M1

### Story 27.2: 实时数据链路统一（方案 B）

As a 运维工程师,
I want 所有页面的实时点位数据来自同一个数据源,
So that 环境监控页、设备详情页、仪表盘、大屏的实时数据始终一致。

**Acceptance Criteria:**

- Given RealtimeStore 作为实时点位数据的唯一事实来源
- When 后端通过 WebSocket 推送实时数据
- Then RealtimeStore 接收并更新 `dataMap: Map<number, RealtimeData>`
- And `useRealtime` composable 移除自有的 `realtimeData` Map，改为代理 `realtimeStore` 的方法（`getPointData`、`getDataByType`）
- And `useRealtime` composable 不再创建独立的 WebSocket 连接（WS 管理统一由 Story 27.5 的 WebSocketManager 负责）
- And `useBigscreenData` 的 `fetchEnvironmentData()` 从 RealtimeStore 读取数据，而非独立调用 `getAllRealtimeData()` API
- And BigscreenStore 移除 `deviceData` 相关状态，改用 getter 从 RealtimeStore 派生
- And 现有 RealtimeStore 中已定义但未被使用的 `updatePoint`/`setAllData`/`getPointData` 方法被正式启用
- And 在以下页面验证数据一致性：环境监控页、设备详情页、仪表盘实时统计、大屏

**涉及文件:**
- `frontend/src/stores/realtime.ts` — 增加 `handleWsMessage(data)` action（接收来自 WebSocketManager 的数据，不自建 WS 连接）
- `frontend/src/composables/useRealtime.ts` — 移除自有 Map，代理 store
- `frontend/src/composables/bigscreen/useBigscreenData.ts` — 读 RealtimeStore
- `frontend/src/stores/bigscreen.ts` — deviceData 改为 getter

**NFR 追溯:** NFR-P1, NFR-M1

### Story 27.3: 能源数据链路统一（方案 C）

As a 能源管理员,
I want 能源监控页和大屏的 PUE、功率数据来自同一个数据源,
So that 不同页面的 PUE 和功率数值始终一致。

**Acceptance Criteria:**

- Given EnergyStore 作为能源数据的唯一事实来源
- When 能源数据加载完成
- Then BigscreenStore 的 `energy` 对象（pue、totalPower、itPower、coolingPower）改为 getter，读取 `useEnergyStore()` 的 computed 属性
- And `useBigscreenData` 的 `fetchEnergyData()` 调用 `useEnergy.loadAllData()` 而非独立调用 `getEnergyDashboard()` API
- And 统一数据来源：大屏和能源页使用相同的 API 端点获取 PUE
- And 能源监控页（`views/energy/monitor.vue`）如有局部 ref 绕过 EnergyStore 直接调 API 的逻辑，改为从 EnergyStore 读取
- And 在能源监控页和大屏同时验证 PUE 值一致

**涉及文件:**
- `frontend/src/stores/bigscreen.ts` — energy 改为 getter
- `frontend/src/composables/bigscreen/useBigscreenData.ts` — 调用 energyStore
- `frontend/src/stores/energy.ts` — 确认数据加载方法可被外部复用
- `frontend/src/views/energy/monitor.vue` — 移除绕过 EnergyStore 的局部 ref（如存在）

**NFR 追溯:** NFR-M1

### Story 27.4: 告警声音开关统一（方案 D）

As a 用户,
I want 在系统设置中关闭告警声音后全局生效,
So that 不会出现设置页关了声音但告警仍然播放声音的情况。

**Acceptance Criteria:**

- Given AppStore 作为告警声音配置的唯一来源
- When 用户在系统设置中切换告警声音开关
- Then `AppStore.alarmSoundEnabled` 被更新，写入 localStorage key `alarm_sound`
- And `AlarmStore.soundEnabled` 属性被移除
- And `useAlarm` composable 改为读取 `appStore.alarmSoundEnabled` 决定是否播放声音
- And AppStore 初始化时执行一次性迁移：若 localStorage 中存在旧 key `alarm_sound_enabled`，将其值迁移到 `alarm_sound`，然后删除旧 key
- And 迁移后 localStorage 中不再存在 `alarm_sound_enabled` key
- And 系统设置页面的声音开关与实际播放行为完全一致

**涉及文件:**
- `frontend/src/stores/alarm.ts` — 移除 `soundEnabled`
- `frontend/src/stores/app.ts` — 确认 `alarmSoundEnabled` 为唯一来源
- `frontend/src/composables/useAlarm.ts` — 改读 appStore

**NFR 追溯:** NFR-M1

### Story 27.5: WebSocket 单连接管理器（方案 E）

As a 开发者,
I want 每个 WebSocket 通道只维持一个共享连接,
So that 页面切换时不会频繁创建/销毁连接，减少服务器资源浪费。

**Acceptance Criteria:**

- Given 新建 `composables/useWebSocketManager.ts` 单例管理器
- When 多个 Store 或组件需要同一 WS 通道的数据
- Then 管理器确保每个通道（realtime/alarms/system/linkage）最多 1 个 WebSocket 连接
- And 连接生命周期绑定到应用而非组件（在 App.vue 或 MainLayout 中初始化）
- And 各 Store 通过管理器注册消息处理器（`manager.subscribe('alarms', handler)`），而非自行创建连接
- And 管理器负责自动重连（指数退避，最大间隔 30 秒）和心跳保活（30 秒 ping）
- And 组件卸载时调用 `manager.unsubscribe()` 移除处理器，连接本身不断开
- And 所有连接数可在浏览器 DevTools Network/WS 面板中验证（每通道仅 1 个）

**涉及文件:**
- 新建 `frontend/src/composables/useWebSocketManager.ts`
- `frontend/src/stores/alarm.ts` — WebSocket 逻辑改用管理器
- `frontend/src/stores/realtime.ts` — WebSocket 逻辑改用管理器
- `frontend/src/App.vue` 或 `layouts/MainLayout.vue` — 初始化管理器

**NFR 追溯:** NFR-P1

**依赖:** Story 27.1, 27.2（先统一数据归属到 Store，再由本 Story 建立 WebSocketManager 统一管理连接。27.1/27.2 中 Store 的 WS 消息处理 action 需预留 `handleWsMessage(data)` 接口供 Manager 回调）

### Story 27.6: 站点过滤贯穿数据链路（方案 F）

As a 多站点管理员,
I want 切换站点后所有页面数据自动按站点过滤,
So that 不会看到其他站点的混合数据。

**Acceptance Criteria:**

- Given `useSiteStore().currentSiteId` 维护当前站点 ID
- When 管理员切换站点
- Then API 请求拦截器（axios interceptor）自动为所有请求注入 `site_id` 参数
- And `siteStore.switchSite(newSiteId)` action 触发相关 Store（AlarmStore、RealtimeStore、EnergyStore）的 `reload()` 操作，刷新数据
- And WebSocket 连接在切换站点时重新建立（通过 WebSocketManager 断开并携带新 site_id 重连）
- And 各 API 模块层面的 `site_id` 参数（已存在但未使用）被 interceptor 自动注入，调用方无需手动传递
- And 在多站点环境下验证：切换站点后，告警列表、实时数据、能源数据均只显示目标站点数据

**涉及文件:**
- `frontend/src/api/request.ts` — 增加 axios 请求拦截器
- `frontend/src/stores/site.ts` — `switchSite()` 触发相关 store reload
- `frontend/src/composables/useWebSocketManager.ts` — 支持切换站点重连

**NFR 追溯:** NFR-M1

**依赖:** Story 27.5（WebSocket 管理器）
**阶段约束:** 本 Story 依赖 Epic 22（站点管理前端，Phase 2 补充）提供站点切换 UI。MVP 阶段可先实现 API 拦截器和 Store reload 机制，站点切换 UI 集成延迟到 Epic 22 完成后。

### Story 27.7: 数据链路 P0 问题修复

As a 用户,
I want 所有页面的数据完全来自统一的 Store,
So that 不同页面显示的数据始终保持一致，不会出现数据不同步的问题。

**Context:**

对抗性审查（2026-03-10）发现 Epic 27 实施不完整，存在 3 个 P0 级别的严重问题：

1. **P0-1**: 温度监控页面仍直接调用 `getActiveAlarms` API，绕过 AlarmStore
2. **P0-2**: Dashboard 仍维护独立的 `energyData` ref，与 EnergyStore 状态脱节
3. **P0-3**: BigscreenStore 的 `energy` 和 `environment` 仍是独立状态，未改为从对应 Store 派生的 getter

**Acceptance Criteria:**

- Given 温度监控页面点击传感器
- When 加载传感器关联告警
- Then 从 `alarmStore.activeAlarms` 中过滤 `point_id` 匹配的告警，移除直接 API 调用
- And Dashboard 页面完全从 `useEnergyStore()` 读取能源数据，移除局部 `energyData` ref
- And BigscreenStore 的 `energy` 和 `environment` 改为 getter，从 EnergyStore 和 RealtimeStore 派生
- And 移除 Dashboard 的 sessionStorage 缓存机制（`dcim_dashboard_cache`）
- And 所有页面的数据完全同步，无数据割裂问题

**涉及文件:**
- `frontend/src/views/environment/temperature.vue:310`
- `frontend/src/views/dashboard/index.vue`
- `frontend/src/stores/bigscreen.ts`

**优先级:** P0（紧急修复）

**估算工作量:** 8h

**依赖:** Story 27.1, 27.2, 27.3（修复基于已完成的 Store 架构）

---

## Epic 28: Demo 系统解耦与数据隔离

**阶段:** MVP (月1-3)
**目标:** 消除 demo 系统与主系统的数据耦合，实现数据来源全链路可追溯，支持 demo 与真实数据共存。
**实施优先级:** Story 28.2(P0，种子分离)→28.3(P1，编码解耦) 为核心路径，应在真实网关接入（Epic 1/2）前完成；Story 28.1(P1，来源标记) 和 28.4(P1，安全卸载) 可与 Epic 1/2 并行，在真实数据写入前就位即可。
**NFR 覆盖:** NFR-M1(可维护性), NFR-M3(部署灵活性)
**参考文档:** `docs/demo-system-audit.md`, `architecture.md` Section 20

### Story 28.1: 数据来源标记贯穿统一管道（方案 G）

As a 运维工程师,
I want 所有监控数据和告警都标记了数据来源,
So that 我能区分哪些是 demo 模拟数据、哪些是真实网关采集数据，在真实环境中过滤掉 demo 数据。

**Acceptance Criteria:**

- Given `IngestPoint.source` 字段已存在（值为 demo/mqtt/bridge/unknown）
- When 数据通过 `process_payload()` 统一管道入库
- Then Point 表新增 `source: VARCHAR(20)` 列（默认 "manual"），标记点位创建来源（demo/mqtt/manual）
- And PointDataLatest 表新增 `source: VARCHAR(20)` 列（默认 "unknown"），写入时传递 `IngestPoint.source` 值
- And PointHistory 表新增 `source: VARCHAR(20)` 列（默认 "unknown"），写入时传递 `IngestPoint.source` 值
- And Alarm 表新增 `data_source: VARCHAR(20)` 列（默认 "unknown"），告警创建时记录触发数据的来源
- And WebSocket `broadcast_realtime()` 推送消息体增加 `source` 字段
- And Redis 缓存 `point:{id}:latest` 的 JSON 值增加 `source` 字段
- And Alembic 迁移脚本正确添加新列，兼容现有数据（现有行 source 为 "unknown"）
- And 告警列表 API `/api/v1/alarms` 支持 `?data_source=demo` 查询参数过滤
- And 历史数据 API `/api/v1/history` 支持 `?source=mqtt` 查询参数过滤
- And `history_generator.py` 写入 PointHistory 时标记 `source="demo_backfill"`，并在文件头部注释说明绕过 process_payload 的原因（避免触发告警）
- And 确保 history_generator 生成的数据间隔与 ingest_pipeline 的 store_interval 降采样配置一致

**涉及文件:**
- `backend/app/services/ingest_pipeline.py` — Phase 1/2/3 传递 source
- `backend/app/models/alarm.py` — 增加 data_source 列
- `backend/app/models/__init__.py` — Point 增加 source 列, PointHistory 增加 source 列, PointDataLatest 增加 source 列
- `backend/app/api/v1/alarm.py` — 增加 data_source 过滤参数
- `backend/app/api/v1/history.py` — 增加 source 过滤参数
- `backend/app/services/history_generator.py` — 写入 source="demo_backfill"
- Alembic 迁移脚本（与 Story 28.4 的 `is_demo` 列合并为同一个迁移脚本；若在 Epic 14.5 PostgreSQL 迁移前实施，迁移需兼容 SQLite `ALTER TABLE ADD COLUMN` 语法）

**NFR 追溯:** NFR-M1

### Story 28.2: Demo 配置分离与最小化种子（方案 I）

As a 部署工程师,
I want 系统在非 demo 模式下也能正常启动并提供基础功能,
So that 真实环境部署时不依赖 demo 数据，同时有最小化的基础配置。

**Acceptance Criteria:**

- Given 配置项拆分为三个独立开关
- When `.env` 中设置 `SEED_ENABLED=true, DEMO_ENABLED=false, SIMULATION_ENABLED=false`
- Then 系统启动时执行最小化种子（`minimal_seed.py`）：
  - 创建默认 Site（站点名称可配置，默认"默认站点"）
  - 创建基础 Floor/Room 结构（可配置数量，默认 1 层 1 机房）
  - 创建默认电价配置（分时电价模板）
  - 创建默认告警级别配置
  - **不创建设备和点位**
- And 系统页面可正常访问，空间结构页面显示默认站点
- And 设备/点位页面显示为空（引导用户手动添加或接入网关）
- And `DEMO_ENABLED=true` 时在最小种子基础上继续加载完整 demo 数据
- And `SIMULATION_ENABLED=true` 时启动模拟器（可独立于 demo_enabled）
- And 移除 `demo/config.py` 中 `demo_enabled or simulation_enabled` 的合并逻辑
- And `lifecycle.py` 重构为分层启动：seed → demo → simulation

**涉及文件:**
- `backend/app/core/config.py` — 新增 `seed_enabled` 配置项
- `backend/app/main.py` — lifespan 函数适配分层启动（seed→demo→simulation）
- 新建 `backend/app/seeds/minimal_seed.py` — 最小化种子
- `backend/app/demo/lifecycle.py` — 分层启动逻辑
- `backend/app/demo/config.py` — 移除合并逻辑
- `.env.example` — 新增 `SEED_ENABLED` 变量说明

**NFR 追溯:** NFR-M3

### Story 28.3: 主系统代码与 Demo 编码解耦（方案 H）

As a 开发者,
I want 主系统业务服务不硬编码 demo 特定的设备编码和楼层规则,
So that 非 demo 环境中这些服务能正常工作，且新增设备能被正确匹配。

**Acceptance Criteria:**

- Given `point_device_matcher.py` 的 `LEGACY_MAPPING_RULES` 包含 20+ 条硬编码 demo 设备码
- When 重构点位匹配引擎
- Then `LEGACY_MAPPING_RULES` 从 `point_device_matcher.py` 移除，迁移到 `backend/app/demo/data/legacy_mapping.py`
- And 主系统仅保留通用的 `derive_point_prefix()` 和 `identify_point_usage()` 算法
- And demo 模块在初始化时通过注册机制将 legacy 规则注入匹配引擎（可选）
- And `device_sync.py` 的楼层列表从数据库 Floor 表动态查询，移除硬编码 `["F1", "F2", "F3", "F4"]`
- And `device_sync.py` 的回路推断规则参数化，从 DistributionCircuit 表动态匹配，移除硬编码 `"C-CH-01"`, `"C-AC-01"` 等
- And `building_points.py` 移动到 `backend/app/demo/data/` 目录下，主系统不再直接导入
- And 在 demo 禁用状态下运行后端测试，验证主系统服务无 ImportError

**涉及文件:**
- `backend/app/services/point_device_matcher.py` — 移除硬编码
- `backend/app/services/device_sync.py` — 参数化推断规则
- `backend/app/data/building_points.py` → `backend/app/demo/data/building_points.py`
- 新建 `backend/app/demo/data/legacy_mapping.py`

**NFR 追溯:** NFR-M1

### Story 28.4: Demo 数据安全卸载与标记（方案 I 补充）

As a 管理员,
I want 卸载 demo 数据时只删除 demo 创建的记录，保留我自定义的配置,
So that 从 demo 模式过渡到生产模式时不会丢失自定义的告警规则、配电拓扑等。

**Acceptance Criteria:**

- Given 以下表增加 `is_demo: bool = False` 列：Device、Point、Site、Floor、Room、Row、Transformer、MeterPoint、DistributionPanel、DistributionCircuit、PowerDevice、CoolingGroup、CoolingUnit、ColdAisle、AlarmThreshold、FloorMap、ElectricityPricing
- When demo 种子数据创建上述记录时
- Then 所有 demo 创建的记录标记 `is_demo=True`
- And `unload_demo_data()` 重构：按外键依赖顺序删除 `is_demo=True` 的记录（先删子表再删父表：PointHistory→PointRealtime→Point→Device→PowerDevice→DistributionCircuit→DistributionPanel→...→Room→Floor→Site）
- And 用户通过 API 手动创建的记录 `is_demo=False`，卸载时保留
- And 最小种子（Story 28.2）创建的默认 Site/Floor/Room 标记 `is_demo=False`，卸载时保留
- And 卸载前在日志中输出将要删除的记录统计（设备数、点位数、历史数据条数）
- And 前端 DemoDataLoader 卸载确认对话框显示将要删除的记录数量
- And Alembic 迁移脚本添加 `is_demo` 列（与 Story 28.1 的 source 列合并为同一个迁移），现有数据默认为 `True`（假设当前全部是 demo 数据）

**涉及文件:**
- `backend/app/models/device.py` — 增加 is_demo 列
- `backend/app/models/__init__.py` — Point 增加 is_demo 列
- `backend/app/models/spatial.py` — Site/Floor/Room/Row 增加 is_demo 列
- `backend/app/models/energy.py` — Transformer/MeterPoint/DistributionPanel/DistributionCircuit/PowerDevice/ElectricityPricing 增加 is_demo 列
- `backend/app/models/cooling.py` — CoolingGroup/CoolingUnit/ColdAisle 增加 is_demo 列（如存在独立模型文件）
- `backend/app/demo/service.py` — 重构 unload_demo_data()
- `backend/app/demo/seeds/*.py` — 创建时标记 is_demo=True
- `frontend/src/components/DemoDataLoader.vue` — 卸载确认增强
- Alembic 迁移脚本

**NFR 追溯:** NFR-M1, NFR-M3

**依赖:** Story 28.2（配置分离）

---

*文档更新 - 共 28 个 Epic, 138+ 个 Stories, 覆盖 FR1-FR99 全部功能需求 + FR34-1~42 智能诊断子需求（含 FR34-8 图形化编辑器、FR34-35 对抗样本检测）+ 关键 NFR + Phase 2 补充页面 + 前端数据链路统一 + Demo 系统解耦与数据隔离*
