# 算力中心智能监控系统 (DCIM)

数据中心基础设施管理系统，提供多协议设备采集、实时监控、智能告警、能源管理、资产运维、联动引擎、视频监控、3D 数字孪生、多站点管理等全栈功能。

## 功能特性

### 采集与通信
- **多协议适配**: Modbus TCP/RTU、SNMP v2c/v3、MQTT、HTTP/REST、BACnet/IP、OPC-UA 插件化框架
- **网关管理**: 自动注册、状态监控、远程配置下发、离线缓存与断点续传
- **数据源管理**: 可视化配置、点位批量导入、设备模板复用、连接测试

### 实时监控
- **六大子系统仪表盘**: 供配电、制冷、环境、安防消防、智能基础设施、能效
- **设备状态看板**: 按区域/类型分组，在线/离线/告警实时展示
- **通信中断检测**: 自动识别故障范围，数据质量标记
- **优雅降级**: Redis/WebSocket/MQTT 故障时自动降级，不影响核心功能

### 告警管理
- **4 级告警**: 提示/次要/重要/紧急，阈值可按设备类型批量配置
- **实时触发**: 1 秒内告警，WebSocket 推送 + 声光提醒
- **闭环处理**: 确认→处理→解除全流程，支持批量操作
- **智能防护**: 数据质量标记防误报、告警风暴抑制、升级规则自动通知

### 能源管理
- **PUE 监控**: 实时 PUE 计算与趋势分析，配电拓扑可视化
- **能耗统计**: 五时段电价管理，日/月统计，同比/环比分析
- **节能优化**: 6 种分析插件（峰谷套利、需量优化、PUE 优化等），执行效果追踪
- **能效报告**: Excel/PDF 导出

### 资产与容量
- **资产台账**: 全生命周期管理（入库→上架→维修→报废），批量导入
- **机柜 U 位可视化**: 42U 占用图，拖拽调整
- **四维容量监控**: 空间/电力/制冷/承重使用率，阈值预警
- **智能上架推荐**: 多维度评分，候选机柜排序
- **容量趋势预测**: 线性回归预测 3/6/12 个月，自动扩容建议

### 物理拓扑与智能选址
- **三合一拓扑**: 空间 + 配电 + 制冷拓扑配置
- **多维智能选址**: 综合空间/电力/制冷/承重/三相平衡/温度环境评分
- **故障影响分析**: PDU/配电柜故障影响范围可视化

### 联动引擎
- **规则引擎**: 条件→动作联动框架，支持消防分级联动策略
- **智能诊断**: 故障自动诊断与恢复流程
- **事件时间线**: 联动事件全链路追溯
- **安全控制**: 控制命令分级确认，传感器数据漂移检测

### 视频监控
- **摄像头管理**: 元数据管理、区域关联
- **告警联动**: 告警自动关联视频检索、录像回放
- **PTZ 控制**: 云台控制与区域联动录像

### 运维管理
- **工单系统**: 创建→分配→处理→验收闭环，审批流程
- **巡检管理**: 巡检计划与任务执行
- **知识库**: 运维知识沉淀与检索
- **告警自动派单**: 告警触发自动创建工单

### 报表与决策
- **自动运维报告**: 定期生成运维报告
- **智能摘要面板**: 关键指标汇总展示
- **PDF 报告导出**: 专业格式报告
- **设备健康评估**: 设备运行状态综合评分

### 用户与系统
- **用户管理**: RBAC 权限控制，JWT 认证
- **会话管理**: 并发会话限制，Token 刷新
- **操作审计**: 全操作日志记录
- **密码策略**: 可配置密码复杂度与过期策略
- **多站点隔离**: 站点级数据隔离

### 多站点管理
- **站点管理**: 多站点注册与配置
- **统一视图**: 跨站点切换与汇总展示
- **网关接入**: 多站点网关统一管理

### 2.5D 视觉增强
- **SCSS Mixin 基础设施**: 统一 2.5D 样式体系
- **仪表盘增强**: 概览页面 2.5D 视觉效果
- **列表/表单增强**: 数据展示页面 2.5D 风格
- **特殊页面增强**: 大屏等特殊场景 2.5D 效果

## 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                     前端 (Vue 3)                        │
│  Vue 3 + TypeScript + Element Plus + ECharts + Pinia    │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    后端 (FastAPI)                       │
│  FastAPI + SQLAlchemy + Pydantic + WebSocket            │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   数据库 (SQLite)                       │
│              异步支持 (aiosqlite)                       │
└─────────────────────────────────────────────────────────┘
```

## 快速开始

### 环境要求
- Python 3.9+
- Node.js 18+
- npm 或 yarn

### 方式一: 一键启动

**Windows:**
```bash
start.bat
```

**Linux/Mac:**
```bash
chmod +x start.sh
./start.sh
```

### 方式二: 手动启动

**后端服务:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

**前端服务:**
```bash
cd frontend
npm install
npm run dev
```

### 方式三: Docker 部署

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```
## 演示模式
系统内置完整的 4 层楼数据中心模拟环境，支持按需加载、日期刷新、完整卸载。
| 特征 | 说明 |
|------|------|
| 空间拓扑 | 1 站点、4 楼层、8 房间、16 列 |
| 设备数量 | 628 台（UPS 8、配电柜 40、PDU 320、空调 80、传感器 180） |
| 采集点数 | 2830 点（AI 2650、DI 180） |
| 数据来源 | 虚拟网关 `demo-gateway` |
| 更新频率 | 每 5 秒 |
### 启用演示模式
```env
# .env 文件
DEMO_ENABLED=true
SIMULATION_ENABLED=true
SIMULATION_INTERVAL=5
```
### 加载演示数据
```bash
# 加载当前日期数据
curl -X POST "http://localhost:8080/api/v1/demo/load" \
  -H "Authorization: Bearer <token>"
# 加载 30 天前数据（演示历史场景）
curl -X POST "http://localhost:8080/api/v1/demo/load?date_offset_days=-30" \
  -H "Authorization: Bearer <token>"
```
### 卸载演示数据
```bash
# 清理所有演示数据（72 张表 + Redis 缓存）
curl -X DELETE "http://localhost:8080/api/v1/demo/unload" \
  -H "Authorization: Bearer <token>"
```
详细说明参见 [docs/demo-architecture.md](docs/demo-architecture.md)。

## 访问地址

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:3000 |
| 后端 API | http://localhost:8080 |
| API 文档 | http://localhost:8080/docs |

## 默认账户

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | admin123 | 管理员 |

## 项目结构

```
dcim/
├── backend/                 # 后端代码
│   ├── app/
│   │   ├── api/            # API 路由
│   │   │   └── v1/         # v1 版本 API
│   │   ├── core/           # 核心配置
│   │   ├── models/         # 数据模型
│   │   ├── schemas/        # Pydantic 模型
│   │   └── services/       # 业务服务
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/               # 前端代码
│   ├── src/
│   │   ├── api/           # API 模块
│   │   ├── components/    # 组件
│   │   ├── composables/   # 组合式函数
│   │   ├── layouts/       # 布局
│   │   ├── router/        # 路由
│   │   ├── stores/        # 状态管理
│   │   └── views/         # 页面
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml      # Docker 编排
├── start.bat              # Windows 启动脚本
├── start.sh               # Linux/Mac 启动脚本
└── README.md
```

## API 模块

| 模块 | 路径 | 说明 |
|------|------|------|
| 认证 | /api/v1/auth | 登录/登出/刷新令牌 |
| 用户 | /api/v1/users | 用户管理 |
| 设备 | /api/v1/devices | 设备管理 |
| 点位 | /api/v1/points | 点位管理 |
| 实时数据 | /api/v1/realtime | 实时数据 |
| 告警 | /api/v1/alarms | 告警管理 |
| 阈值 | /api/v1/thresholds | 阈值配置 |
| 历史 | /api/v1/history | 历史数据 |
| 报表 | /api/v1/reports | 报表管理 |
| 日志 | /api/v1/logs | 系统日志 |
| 统计 | /api/v1/statistics | 统计分析 |
| 配置 | /api/v1/configs | 系统配置 |
| 用电 | /api/v1/energy | 用电管理 |

## 用电管理 API (30+ 端点)

| 功能 | 端点 | 说明 |
|------|------|------|
| 设备管理 | GET/POST/PUT/DELETE /energy/devices | 用电设备 CRUD |
| 设备树 | GET /energy/devices/tree | 配电层级树 |
| 实时电力 | GET /energy/realtime | 实时功率数据 |
| 电力汇总 | GET /energy/realtime/summary | PUE/今日/本月 |
| PUE监测 | GET /energy/pue | 当前 PUE |
| PUE趋势 | GET /energy/pue/trend | PUE 历史趋势 |
| 日统计 | GET /energy/statistics/daily | 日能耗统计 |
| 月统计 | GET /energy/statistics/monthly | 月能耗统计 |
| 能耗汇总 | GET /energy/statistics/summary | 能耗汇总 |
| 能耗趋势 | GET /energy/statistics/trend | 能耗趋势 |
| 同环比 | GET /energy/statistics/comparison | 同比/环比 |
| 电价配置 | GET/POST/PUT/DELETE /energy/pricing | 电价 CRUD |
| 节能建议 | GET /energy/suggestions | 建议列表 |
| 接受建议 | PUT /energy/suggestions/{id}/accept | 接受 |
| 拒绝建议 | PUT /energy/suggestions/{id}/reject | 拒绝 |
| 完成建议 | PUT /energy/suggestions/{id}/complete | 完成 |
| 节能潜力 | GET /energy/saving/potential | 潜力分析 |
| 配电图 | GET /energy/distribution | 配电拓扑 |
| 导出日报 | GET /energy/export/daily | Excel/CSV |
| 导出月报 | GET /energy/export/monthly | Excel/CSV |

## 开发说明

### 后端开发
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

### 前端开发
```bash
cd frontend
npm run dev
```

### 生产构建
```bash
cd frontend
npm run build
```

## 配置说明

### 后端配置 (.env)
```env
APP_NAME=算力中心智能监控系统
DEBUG=false
DATABASE_URL=sqlite+aiosqlite:///./dcim.db
SECRET_KEY=your-secret-key
MAX_POINTS=100
```

### 前端配置 (.env)
```env
VITE_API_BASE_URL=http://localhost:8080/api/v1
VITE_WS_URL=ws://localhost:8080/ws
```

## 许可证

MIT License

## 更新日志

### V3.0.0 (2026-02-20)
- 全部 17 个 Epic 完成，系统功能全面覆盖 PRD 88 条需求
- 新增采集网关框架：Modbus TCP/RTU、SNMP v2c/v3、MQTT、HTTP/REST、BACnet/IP、OPC-UA
- 新增网关管理：自动注册、状态监控、远程配置、离线缓存
- 新增数据源管理 UI：可视化配置、点位批量导入、设备模板
- 实时监控适配真实采集数据，六大子系统仪表盘
- 告警管理增强：升级规则、数据质量标记、误告警防护
- 能源管理完善：节能优化 6 种插件、执行效果追踪、能效报告
- 新增资产与容量管理：台账、U 位可视化、四维容量、智能上架、趋势预测
- 新增物理拓扑与智能选址：三合一拓扑、多维评分、故障影响分析
- 新增联动引擎：规则引擎、消防联动、智能诊断、事件时间线
- 新增视频监控集成：摄像头管理、告警联动视频、PTZ 控制
- 新增运维管理：工单、巡检、知识库、告警自动派单
- 新增报表与决策：自动报告、智能摘要、PDF 导出、设备健康评估
- 用户与系统管理增强：密码策略、站点隔离、操作审计
- 新增多站点集中管理：站点切换、统一视图
- 新增 2.5D 视觉增强：全局 SCSS Mixin、仪表盘/列表/特殊页面增强
- 新增协议扩展：MQTT/HTTP/BACnet/OPC-UA 适配器、OTA 网关升级
- 前端单元测试 1182 个用例全通过，后端测试 1350+ 通过
- CI/CD 流水线完善，Docker 一键部署

### V2.1.0 (2026-01-13)
- 新增用电管理模块（用电监控/能耗统计/节能建议）
- 完善历史数据查询页面
- 完善系统设置页面
- 优化前端组件和样式

### V2.0.0
- 重构后端架构（FastAPI + SQLAlchemy）
- 重构前端架构（Vue 3 + TypeScript）
- 新增 WebSocket 实时推送
- 新增数据模拟器
