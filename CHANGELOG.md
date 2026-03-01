# 更新日志

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

## [3.2.0] - 2026-03-01

### 重大重构：演示系统完全解耦

演示系统从核心代码中完全解耦，成为独立可选模块，支持按需加载、日期刷新、完整卸载。

#### 架构改进
- **独立模块化**: 演示代码迁移到 `backend/app/demo/` 独立目录
- **条件加载**: 通过 `DEMO_ENABLED` 环境变量控制，默认关闭
- **统一入库管道**: 演示数据通过 `ingest_pipeline.py` 与 MQTT 共用入库逻辑
- **虚拟 Gateway 模式**: 模拟数据标记 `gateway_id="demo-gateway"`，走真实采集链路
- **双向同步服务**: `DeviceSyncService` 自动同步拓扑节点 ↔ 动环设备

#### 新增功能
- **按需加载 API**: `POST /api/v1/demo/load` 支持日期偏移参数
  - 加载当前日期数据: `POST /api/v1/demo/load`
  - 加载 30 天前数据: `POST /api/v1/demo/load?date_offset_days=-30`
  - 加载未来数据: `POST /api/v1/demo/load?date_offset_days=7`
- **完整卸载 API**: `DELETE /api/v1/demo/unload` 清理 72 张表 + Redis 缓存
- **状态查询 API**: `GET /api/v1/demo/status` 查看演示数据加载状态
- **日期刷新 API**: `POST /api/v1/demo/refresh-date` 更新历史数据时间戳

#### 演示数据规模
- **空间拓扑**: 1 站点、4 楼层、8 房间、16 列
- **设备数量**: 628 台（UPS 8、配电柜 40、PDU 320、空调 80、传感器 180）
- **采集点数**: 2830 点（AI 2650、DI 180）
- **更新频率**: 每 5 秒（可配置）

#### 破坏性变更
- `SIMULATION_ENABLED` 环境变量已弃用，改用 `DEMO_ENABLED`
- 演示数据不再自动加载，需手动调用 API 加载
- 旧版模拟器代码已移除（`app/services/simulation.py`）

#### 升级指南
```bash
# 1. 更新环境变量
# .env 文件
DEMO_ENABLED=true  # 替代 SIMULATION_ENABLED

# 2. 启动服务后加载演示数据
curl -X POST "http://localhost:8080/api/v1/demo/load" \
  -H "Authorization: Bearer <token>"

# 3. 卸载演示数据（可选）
curl -X DELETE "http://localhost:8080/api/v1/demo/unload" \
  -H "Authorization: Bearer <token>"
```

#### 技术债务清理
- 移除 `app/services/simulation.py` 旧模拟器
- 移除 `app/api/v1/simulation.py` 旧 API 路由
- 清理 `main.py` 中的模拟器启动逻辑
- 统一数据入库流程，消除重复代码

### 文档完善
- 新增 [部署指南](docs/deployment-guide.md)
  - 环境要求、依赖安装、配置说明
  - Docker 部署、生产环境最佳实践
  - 常见部署问题排查
- 新增 [故障排查手册](docs/troubleshooting-guide.md)
  - 17 个常见问题分类诊断
  - 日志分析方法、性能调优建议
  - 紧急恢复流程
- 新增 [测试指南](docs/testing-guide.md)
  - 后端 pytest 测试框架（1350+ 用例）
  - 前端 Vitest 测试框架（1182 用例）
  - E2E Playwright 测试、性能测试
- 新增 [贡献指南](docs/contributing-guide.md)
  - 代码规范（Python PEP 8、TypeScript Airbnb）
  - Git 工作流程、提交信息规范
  - Pull Request 流程、代码审查标准
- 更新 [演示系统架构文档](docs/demo-architecture.md)
  - 统一入库管道架构图
  - 演示模块生命周期流程
  - API 使用示例

### 已知问题
- 演示数据加载时间较长（约 30-60 秒），大规模数据场景需优化
- 日期刷新功能仅更新时间戳，不重新生成数据
- 卸载操作不可逆，需谨慎使用

### 性能优化
- 演示数据批量插入优化，减少数据库事务次数
- Redis 缓存策略优化，减少重复查询
- WebSocket 推送频率限制，避免前端卡顿

### 测试覆盖
- 新增演示系统单元测试（`tests/demo/`）
- 新增演示 API 集成测试
- 新增演示数据加载/卸载 E2E 测试


## [3.1.0] - 2026-02-23

全部 23 个 Epic / 101 个 Story 开发完毕。新增 Epic 18-23（Phase 2 补充），替换全部 PlaceholderView 占位页面为完整业务页面；新增监控运维基础设施、全面性能优化、自动化测试补全。

### Epic 18：环境监控子系统详情页
- 温湿度监测页（AI 类型传感器，24h ECharts 趋势图 + 漂移检测标识）
- 水浸检测页（DI 类型传感器，区域分组 + 告警状态卡片）
- 烟雾/红外检测页（双类型传感器，消防联动策略关联）

### Epic 19：安防消防前端可视化
- 门禁管理页（左右分栏布局，设备列表 + 事件时间线）
- 消防联动可视化页（策略卡片 + 纯 CSS 动作链流程图 + 执行历史时间线）

### Epic 20：告警规则增强管理页
- 阈值配置增强页（ECharts markLine 可视化阈值线 + 批量操作）
- 复合规则配置页（递归条件树编辑器 + 纯前端规则测试引擎）
- 升级规则管理页（升级链纵向列表编辑器 + 节点排序）
- 告警屏蔽管理页（ECharts 时间线视图 + 批量屏蔽）

### Epic 21：网关管理前端
- 网关列表与状态监控（统计卡片 + 展开详情 + WebSocket 实时更新）
- 网关远程配置下发（配置对话框子组件 + 批量下发 + 历史记录）

### Epic 22：站点管理前端
- 站点管理 CRUD 与切换（概览卡片 + CRUD 表格 + 站点切换联动）

### Epic 23：大屏增强与能源 OCR
- 大屏设备历史数据弹窗（ECharts 趋势图 + 阈值线 + 时间范围切换）
- 大屏 3D 楼层场景加载（Three.js 程序化生成机柜 + 状态着色 + WebGL 降级）
- 电费单 OCR 识别（PaddleOCR 后端服务 + 前端确认对话框 + 自动填充）

### 基础设施与质量改进
- 监控运维基础设施（健康检查端点、结构化日志、错误追踪、性能指标）
- 全面性能优化（前后端响应速度提升）
- 自动化测试补全（修复坏测试、添加超时保护、补充集成/单元测试、CI 脚本）
- 菜单三区重构（监控域/管理域/配置域分区，RBAC 角色过滤）
- 配电拓扑页面「关联已有设备」功能
- DeviceSyncService 双向同步服务

### 代码审查修复（CR-01 ~ CR-12）
- **CR-01 [HIGH]**: 升级链 JSON 从 description 迁移到专用 escalation_chain 字段
- **CR-02 [HIGH]**: condition_expr 后端 JSON schema 校验 + 前端反序列化错误提示
- **CR-03 [HIGH]**: OCR 文件魔数校验 + API 层 10MB 前置大小检查 (HTTP 413)
- **CR-04 [HIGH]**: WebSocket 单例 onUnmounted 安全清理
- **CR-05 [MEDIUM]**: Three.js GridHelper/Fog 资源清理完善
- **CR-06 [MEDIUM]**: 屏蔽策略编辑改为先创建后删除，防止数据丢失
- **CR-07 [MEDIUM]**: 批量配置下发改为 3 并发控制
- **CR-08 [MEDIUM]**: 24h 告警数按 device_type 过滤，修复全局计数误导
- **CR-09 [MEDIUM]**: 阈值全量加载标记技术债务
- **CR-10 [LOW]**: BigscreenHistoryDialog 非数字 deviceId 显示明确提示
- **CR-11 [LOW]**: 网关页面标签修正（平均负载→平均 CPU，能力标签→协议能力）
- **CR-12 [LOW]**: 条件组深度限制改为 prop + 禁用按钮带 tooltip

### 代码质量
- 后端全量 ruff format + lint 自动修复（270 lint fixes，144 files reformatted）
- 新增 escalation_chain 数据库迁移

## [3.0.0] - 2026-02-20

全部 17 个 Epic / 86 个 Story 开发完毕，项目核心功能 100% 完成。

### Epic 9：联动引擎 + 消防联动
- 联动引擎核心框架（事件总线 + 策略匹配）
- 消防分级联动策略（YAML 预定义 + 多传感器交叉确认）
- 智能故障诊断
- 联动恢复流程
- 事件时间线报告
- 控制指令分级确认
- 传感器数据漂移检测

### Epic 10：视频监控集成
- 摄像头元数据管理
- 告警联动视频调取
- 区域联动录像与云台控制
- 告警回放

### Epic 11：运维管理
- 工单管理
- 巡检计划与任务
- 知识库
- 告警自动创建工单
- 工单审批流程

### Epic 12：报表与决策支持
- 自动运维报告
- 智能摘要面板
- PDF 报告导出
- 设备健康评估

### Epic 13：用户与系统管理
- 用户管理前端页面
- 认证与会话管理增强
- 操作审计日志
- 数据备份与系统健康
- 站点级数据隔离
- 密码策略管理

### Epic 14：代码质量与测试
- 后端自动化测试套件（~80 个测试文件）
- 独立设备管理页面
- TypeScript 类型检查零错误
- 前端关键组件测试（Vitest）
- 数据库迁移与 TimescaleDB 配置
- Docker Compose 一键部署

### Epic 15：协议扩展
- MQTT 设备适配器
- HTTP REST 适配器
- BACnet/IP 适配器
- OPC-UA 适配器（asyncua 异步客户端）
- OTA 网关升级（固件管理、分批/灰度升级）

### Epic 16：多站点集中管理
- 站点管理（多站点 CRUD、EMQX ACL 隔离）
- 站点切换与统一视图（跨站点汇总 API）
- 多站点网关接入（site_id 路由、断点续传去重）

### Epic 17：2.5D 视觉增强
- SCSS Mixin 基础设施（透视深度效果系统）
- 仪表盘概览 2.5D 增强
- 列表/表单 2.5D 增强
- 特殊页面 2.5D 增强（52 个页面改造）

### 基础设施
- GitHub Actions CI/CD 流水线（后端测试 + 前端构建检查 + Docker 镜像推送）
- E2E 测试套件（Playwright，7 个 spec 文件）
- 前端单元测试框架（Vitest，11 个测试文件）

## [2.1.0] - 2026-01-13

### Epic 1-8 全部完成

### Epic 1：采集网关框架 + Modbus/SNMP 适配器
- 协议适配器插件框架
- Modbus TCP/RTU 适配器
- SNMP v2c/v3 适配器
- 连接测试、干接点信号采集

### Epic 2：网关管理 + MQTT 通信链路
- 网关自动注册与状态监控
- 远程配置下发
- 离线缓存与断点续传
- MQTT 数据上报管道、Redis 缓存策略

### Epic 3：数据源管理 UI + 设备模板
- 数据源配置管理
- 点位批量导入与校验
- 只读模式与写权限控制
- 设备模板管理、集成报表导出

### Epic 4：实时监控适配
- 六大子系统仪表盘适配
- 设备详情与历史曲线
- 设备状态看板、通信中断检测、优雅降级

### Epic 5：告警管理增强
- 告警阈值配置增强
- 实时告警触发与通知
- 告警处理闭环
- 数据质量标记与误报防护
- 告警升级规则与前端管理

### Epic 6：能源管理
- PUE 监测与配电拓扑适配
- 能耗统计与电价管理
- 节能机会自动识别
- 节能方案执行与效果跟踪
- 能效报告导出

### Epic 7：资产与容量管理
- 资产台账管理、机柜 U 位可视化
- 资产生命周期与质保预警
- 四维容量监控、智能上架推荐、容量趋势预测

### Epic 8：机房物理拓扑 + 智能选址
- 空间/供配电/制冷拓扑配置
- 多维度智能选址
- 故障影响分析

## [2.0.0] - 2026-01-01

- 重构后端架构（FastAPI + SQLAlchemy 2.0 异步）
- 重构前端架构（Vue 3 + TypeScript + Element Plus）
- 新增 WebSocket 实时推送（realtime/alarms/system 三通道）
- 新增数据模拟器
