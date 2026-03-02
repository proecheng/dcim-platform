# 项目概览

生成时间: 2026-03-01  
项目版本: V3.2.1

## 项目信息

项目名称: 算力中心智能监控系统 (DCIM)  
项目类型: 数据中心基础设施管理系统  
开发模式: 前后端分离

## 技术栈

### 前端
- Vue 3.4 + TypeScript 5.9
- Vite 5.0 + Element Plus 2.5
- Pinia 2.1 + Vue Router 4.2
- ECharts 5.6 + Three.js 0.182

### 后端
- Python 3.11 + FastAPI 0.109
- SQLAlchemy 2.0 (async) + Pydantic 2.5
- SQLite (dev) / PostgreSQL (prod)
- WebSocket + JWT 认证

### 测试
- 后端: pytest 9.0 (1350+ 用例)
- 前端: vitest 4.0 (1182 用例)

## 项目规模

- 代码行数: 约 150,000 行
- API 模块: 48 个
- 数据模型: 29 个文件 (100+ 表)
- 前端页面: 28 个目录
- 前端组件: 12 个目录

## 核心功能

1. 多协议设备采集 (Modbus/SNMP/MQTT/HTTP/BACnet/OPC-UA)
2. 实时监控 (六大子系统仪表盘)
3. 智能告警 (4 级告警/闭环处理)
4. 能源管理 (PUE 监控/能耗统计/节能优化)
5. 资产运维 (资产台账/工单/巡检/知识库)
6. 容量管理 (四维容量/趋势预测/智能上架)
7. 联动引擎 (规则引擎/智能诊断)
8. 视频监控 (告警联动/PTZ 控制)
9. 3D 数字孪生 (Three.js 模型/热力图)
10. 多站点管理 (站点隔离/统一视图)

## 最近更新 (V3.2.1)

日期: 2026-03-01

更新内容:
- 重构 device_sync.py 消除重复代码
- 修复回路绑定优先级冲突
- 添加 42 个单元测试
- 所有测试通过 (247/247)

## 访问地址

- 系统入口: http://localhost:3000
- 大屏展示: http://localhost:3000/bigscreen
- API 文档: http://localhost:8080/docs

默认账户: admin / admin123

## 更新记录

2026-03-01: 初始版本，V3.2.1 项目概览
