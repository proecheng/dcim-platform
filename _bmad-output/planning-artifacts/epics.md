---
stepsCompleted: [requirements-inventory, epic-design, story-creation, coverage-map]
inputDocuments: [_bmad-output/planning-artifacts/prd.md, _bmad-output/planning-artifacts/architecture.md]
workflowType: epics-and-stories
project_name: DCIM
user_name: proecheng
date: 2026-02-15
---

# DCIM 算力中心智能监控系统 - Epics & Stories

**Author:** proecheng
**Date:** 2026-02-15
**Status:** 完整版 - 基于 PRD 2026-02-15 + Architecture 2026-02-15 全面重建

---

## 概述

本文档将 PRD 中 88 条功能需求 FR1-FR88 和非功能需求按业务域组织为 16 个 Epic，每个 Epic 包含 3-8 个用户故事。所有故事按 PRD 分阶段计划标注阶段归属。

### Epic 总览

| # | Epic | 阶段 | FR 覆盖 | 故事数 |
|---|------|------|---------|--------|
| 1 | 采集网关框架 + Modbus/SNMP 适配器 | MVP | FR1,FR2,FR7,FR11,FR12 | 6 |
| 2 | 网关管理 + MQTT 通信链路 | MVP | FR15-FR19 | 6 |
| 3 | 数据源管理 UI + 设备模板 | MVP | FR8-FR10,FR13,FR14 | 5 |
| 4 | 实时监控适配 | MVP | FR21-FR26 | 5 |
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
```

### 阶段规划

| 阶段 | 时间 | Epic |
|------|------|------|
| MVP 月1-3 | 120人天 | 1, 2, 3, 4, 5, 6基础, 13, 14 |
| Phase 1.5 月4-6 | 试点+补全 | 7基础, 15-MQTT/HTTP |
| Phase 2 月7-9 | 智能功能 | 6完整, 7完整, 8, 9, 10, 11, 12, 15-BACnet/OPC-UA |
| 推广阶段 月10-12 | 多站点 | 16 |

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
**FR 覆盖:** FR21, FR22, FR23, FR24, FR25, FR26（5 个 Story）
**架构参考:** Architecture 10.2 数据流性能路径

### Story 4.1: 六大子系统仪表盘适配

As a 运维工程师,
I want 在仪表盘上查看真实设备的实时数据,
So that 我可以掌握机房各子系统的实时运行状态。

**Acceptance Criteria:**

- Given 采集网关已接入真实设备并上报数据
- When 运维工程师打开监控仪表盘
- Then 显示六大子系统（供配电、制冷、环境、安防消防、智能基础设施、能效）的实时数据
- And 数据来源从模拟器切换为 Redis 缓存的真实采集数据
- And 通过环境变量 SIMULATION_ENABLED=true/false 控制模拟器开关：开发环境保留模拟器（true），生产环境关闭（false）
- And 模拟器关闭后，仪表盘仅显示真实采集数据，无数据的点位显示"--"
- And 数据刷新延迟小于 1 秒（WebSocket 推送）

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
**FR 覆盖:** FR34, FR35, FR36, FR37, FR38, FR39（7 个 Story）
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

### Story 9.3: 智能故障诊断

As a 运维工程师,
I want 系统自动分析告警的可能原因,
So that 我可以快速定位故障根因。

**Acceptance Criteria:**

- Given 系统已积累足够的历史数据
- When 告警触发
- Then 系统基于规则和历史数据分析给出可能原因列表（覆盖 Top 20 高频故障场景）
- And 每个原因附带置信度和建议操作
- And 诊断规则支持配置和扩展

**FR 追溯:** FR34

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

以下映射表确保 PRD 中所有 88 条功能需求（FR1-FR88）均被至少一个 Epic/Story 覆盖。

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

*文档结束 - 共 17 个 Epic，86 个 Story，覆盖 FR1-FR92 全部 92 条功能需求 + 4 项关键 NFR*
