# 系统架构文档

生成时间: 2026-03-10
项目版本: V4.2.0

## 整体架构

```
浏览器 <--HTTP/WS--> Vite Dev(3000) 或 Express Proxy(3000) <--HTTP/WS--> FastAPI(8080) <--SQL--> SQLite/PostgreSQL
```

## 前端架构

技术栈: Vue 3.4 + TypeScript 5.9 + Vite 5.0 + Element Plus 2.5 + Pinia 2.1 + ECharts 5.6 + Three.js

分层结构:
- 视图层 (views/): 页面组件
- 组件层 (components/): 可复用组件
- 状态层 (stores/): Pinia 状态管理
- API 层 (api/): HTTP 请求封装
- 工具层 (utils/): 工具函数

特性:
- 组合式 API
- TypeScript 类型安全
- 自动导入 (unplugin-auto-import)
- WebSocket 实时推送
- 2.5D 视觉效果

## 后端架构

技术栈: Python 3.11 + FastAPI 0.109 + SQLAlchemy 2.0 (async) + Pydantic 2.5

分层结构:
- API 层 (api/v1/): REST API 端点
- 服务层 (services/): 业务逻辑
- 模型层 (models/): ORM 模型
- Schema 层 (schemas/): 数据验证
- 核心层 (core/): 配置/数据库/安全

特性:
- 异步数据库操作
- JWT 认证
- RBAC 权限控制
- WebSocket 推送
- 数据模拟器

## 集成架构

认证: JWT Token (Bearer)  
实时通信: WebSocket (3 个通道)  
数据采集: 多协议网关 (Modbus/SNMP/MQTT/HTTP/BACnet/OPC-UA)  
缓存: Redis (可选)  
消息队列: MQTT (可选)

## 更新记录

2026-03-10: V4.2.0 - 预冷 TCL 模型架构
  - 新增一阶 RC 热动力学模型，替代固定比例 0.4 制冷可转移功率算法
  - 温度裕度法（THM）安全兜底、7 项自动回退保护
  - VPP 可调容量接口、分阶段实施路径
  - 3 个新数据模型、11 个新 API 端点
  - 详见 architecture.md Section 21

2026-03-10: V4.1.0 - P1 问题修复（7/26+ 完成）
  - Epic 6: PUE 历史写入并发冲突、UPS 效率异常处理
  - Epic 24-26: 条件解析器递归限制、误诊报告并发冲突、断路器恢复失败、Redis 降级存储、动态去重窗口
  - 详见 architecture-v4.1.0-changelog.md

2026-03-01: V3.2.1 - 初始版本
