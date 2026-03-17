# 项目概览

生成时间: 2026-03-17
项目版本: V4.2.0

## 项目简介

算力中心智能监控系统 (DCIM - Data Center Infrastructure Management) 是一套完整的数据中心基础设施管理平台，涵盖实时监控、告警管理、能源管理、资产运维、智能诊断、3D 数字孪生、预冷热力学优化、VPP 虚拟电厂集成等功能。

## 技术栈总览

| 层级 | 技术 | 版本 | 说明 |
|------|------|------|------|
| **前端** | Vue 3 + TypeScript | Vue 3.4.15 / TS 5.9.3 | SPA 单页应用 |
| **UI 框架** | Element Plus | 2.5.3 | Material Design 组件库 |
| **图表** | ECharts | 5.6.0 | 数据可视化 |
| **3D** | Three.js | 0.182.0 | 3D 数字孪生 |
| **状态管理** | Pinia | 2.1.7 | 响应式状态管理 |
| **构建工具** | Vite | 5.0.11 | 快速构建 |
| **代理** | Express.js | 4.18.2 | 反向代理 + 静态文件 |
| **后端** | FastAPI | 0.109.0 | 异步 REST API |
| **ORM** | SQLAlchemy 2.0 | 2.0.25 | 异步数据库访问 |
| **数据验证** | Pydantic | 2.5.3 | 请求/响应模型 |
| **数据库** | PostgreSQL + TimescaleDB | PG 16 | 生产环境 |
| **开发数据库** | SQLite | - | 开发环境 |
| **缓存** | Redis | 7 | 分布式缓存/锁 |
| **消息队列** | EMQX (MQTT) | 5 | IoT 数据采集 |
| **认证** | JWT (python-jose) | HS256 | Bearer Token |
| **科学计算** | NumPy / SciPy / scikit-learn | - | 热力学模型/优化 |
| **容器化** | Docker Compose | - | 5 服务编排 |
| **测试** | pytest / vitest | - | 后端/前端测试 |

## 项目规模

| 指标 | 数量 |
|------|------|
| 后端 Python 文件 | 350 |
| API 端点模块 | 57 |
| REST API 端点 | 300+ |
| ORM 数据模型 | 120+ |
| 业务服务 | 147 |
| 数据库迁移 | 54 |
| 前端 Vue/TS 文件 | 483 |
| 页面视图 | 97 |
| 可复用组件 | 101 |
| Pinia Store | 8 |
| 前端 API 模块 | 45 |
| 路由定义 | 68 |
| 后端测试文件 | 195 |
| 文档文件 | 168+ |
| Docker 服务 | 5 |

## 核心功能模块

### 监控域
- **总览仪表盘** — 系统全局状态、关键指标、告警概览
- **供配电监控** — UPS、电池、配电柜、PDU、配电拓扑
- **制冷监控** — 室内/室外空调、冷通道、群控
- **环境监控** — 温湿度、漏水检测、烟感红外
- **安防消防** — 门禁、视频监控、消防联动
- **告警管理** — 4 级告警、声音通知、升级规则、屏蔽

### 能源管理域
- **用电监控** — 实时功率、PUE、配电拓扑图
- **能效统计** — 用电趋势、对比分析、成本核算
- **节能分析** — 6 种分析插件、负荷调度、优化报告
- **负荷转移** — 峰谷转移计划、可行性分析、执行监控
- **需量管理** — 需量监控、告警、趋势分析
- **预冷优化** — RC 热力学模型、温度预测、预冷计划
- **VPP 虚拟电厂** — 可调容量上报、调控指令接收执行

### 资产运维域
- **资产台账** — 资产全生命周期管理、机柜 U 位可视化
- **容量管理** — 空间/电力/制冷/承重四维容量监控
- **工单管理** — 故障/维护/巡检工单、审批流程
- **巡检管理** — 巡检计划、任务、异常记录
- **知识库** — 运维知识沉淀、搜索

### 智能诊断域 (Epic 24-26)
- **L1 规则引擎** — YAML 规则定义、分类管理
- **L2 故障树推理** — 贝叶斯推理、HMAC 签名、版本管理
- **诊断调度器** — 并发控制、熔断降级
- **配电拓扑级联分析** — 电气参数节点、N+X 冗余
- **UPS 电池 SOH 预测** — 健康度评估
- **传感器元数据** — 精度加权、校准管理
- **动态告警阈值** — 趋势分析、多传感器融合
- **故障树图形编辑器** — 可视化编辑
- **反事实分析** — 根因验证
- **误诊反馈** — 闭环学习、概率调参
- **A/B 测试** — 灰度发布
- **灾难恢复演练** — 演练计划、执行、评估
- **HMAC 密钥管理** — 密钥轮换、审计

### 预冷 TCL 模型域 (Epic 29-33)
- **RC 热力学模型** — `C × dT/dt = Q_IT - Q_cool + (T_amb - T)/R`
- **温度裕度安全兜底** — ASHRAE 硬约束、< 2°C 禁止转移
- **7 种自动回退保护** — 温度超限/传感器故障/通信中断等
- **贪心优化预冷调度** — 谷时预冷/峰时释放
- **预冷计划执行引擎** — 状态机驱动
- **RC 参数最小二乘校准** — 自动拟合 R/C 参数
- **分阶段部署控制** — shadow → pilot → production
- **VPP 可调容量上报** — OpenADR 2.0b 兼容接口
- **VPP 调控指令执行** — 指令接收、安全校验、执行反馈

### 系统管理域
- **用户管理** — RBAC 三角色 (admin/operator/viewer)
- **站点管理** — 多站点隔离、全局切换
- **操作审计** — 全操作日志记录
- **系统配置** — 数据字典、许可证管理
- **数据源管理** — 协议适配 (Modbus/SNMP/MQTT/HTTP/BACnet/OPC-UA)
- **网关管理** — 远程配置、OTA 升级
- **Demo 系统** — 独立数据隔离、安全卸载

### 大屏展示
- **3D 数字孪生** — Three.js 楼层场景
- **DataV 大屏** — 实时数据、告警、能源可视化
- **多模式切换** — 指挥/运维/展示三种模式

## 架构概览

```
浏览器 ──HTTP/WS──> Express Proxy(3000) ──> FastAPI(8080) ──> PostgreSQL/SQLite
                     或 Vite Dev(5173)                    ──> Redis
                                                          ──> EMQX (MQTT)
```

### 三层架构

| 层级 | 职责 | 端口 |
|------|------|------|
| **前端** | Vue 3 SPA, ECharts 图表, Three.js 3D | 3000 (prod) / 5173 (dev) |
| **代理** | 静态文件 + API/WS 转发 | 3000 |
| **后端** | REST API, WebSocket, 业务逻辑, 调度器 | 8080 |

### WebSocket 通道

| 通道 | URL | 用途 |
|------|-----|------|
| realtime | `/ws/realtime?token=xxx` | 实时数据推送 |
| alarms | `/ws/alarms?token=xxx` | 告警通知 |
| system | `/ws/system?token=xxx` | 系统状态 |

## 部署方式

### Docker Compose (生产推荐)

5 个服务: PostgreSQL+TimescaleDB, Redis, EMQX, FastAPI Backend, Nginx Frontend

### 本地开发

```bash
# 后端
cd backend && .venv\Scripts\activate && uvicorn app.main:app --reload --port 8080

# 前端 (开发模式)
cd frontend && npm run dev    # http://localhost:5173

# 或一键启动 (生产模式)
start.bat                     # http://localhost:3000
```

### 默认账号

- 管理员: admin / admin123

## 相关文档

- [系统架构](./architecture-overview.md)
- [源代码目录结构](./source-tree-analysis.md)
- [后端 API 接口](./api-contracts-summary.md)
- [后端数据模型](./data-models-summary.md)
- [前端组件清单](./component-inventory-frontend.md)
- [开发指南](./development-guide.md)
