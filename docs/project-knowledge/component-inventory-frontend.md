# 前端组件清单

生成时间: 2026-03-01  
项目版本: V3.2.1  
框架: Vue 3.4 + TypeScript 5.9

## 概述

前端包含 28 个页面视图目录和 12 个组件目录，采用组合式 API 和 TypeScript 类型安全。

## 页面视图 (views/)

| 目录 | 页面数 | 说明 |
|------|-------|------|
| login/ | 1 | 登录页 |
| dashboard/ | 1 | 仪表盘 |
| device/ | 5+ | 设备管理 |
| alarm/ | 3+ | 告警管理 |
| energy/ | 8+ | 能源管理 |
| asset/ | 5+ | 资产管理 |
| operation/ | 6+ | 运维管理 |
| bigscreen/ | 1 | 大屏展示 |

## 组件库 (components/)

| 目录 | 组件数 | 说明 |
|------|-------|------|
| common/ | 15+ | 通用组件 (PageHeader, DataTable, SearchForm) |
| charts/ | 10+ | 图表组件 (LineChart, BarChart, PieChart, GaugeChart) |
| energy/ | 8+ | 能源组件 (PUEChart, PowerTopology) |
| bigscreen/ | 6+ | 大屏组件 (ScreenHeader, DataPanel) |

## 状态管理 (stores/)

| Store | 说明 |
|-------|------|
| user | 用户状态 (登录信息/权限) |
| app | 应用状态 (菜单/主题) |
| alarm | 告警状态 (活动告警/统计) |
| realtime | 实时数据状态 (WebSocket 连接) |
| energy | 能源状态 (PUE/能耗) |
| bigscreen | 大屏状态 (数据刷新) |

## 组合式函数 (composables/)

| 函数 | 说明 |
|------|------|
| useWebSocket | WebSocket 连接管理 |
| useAlarm | 告警处理逻辑 |
| useChart | 图表配置生成 |
| useTable | 表格分页/排序 |

## 更新记录

2026-03-01: 初始版本，涵盖 V3.2.1 所有前端组件
