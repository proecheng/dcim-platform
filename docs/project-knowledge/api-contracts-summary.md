# 后端 API 接口文档

生成时间: 2026-03-01  
项目版本: V3.2.1  
API 版本: v1

## 概述

DCIM 后端提供 48 个 API 模块，涵盖认证、设备管理、实时监控、告警、能源、资产、运维等全栈功能。所有 API 遵循 RESTful 规范，使用 JWT 认证，支持 RBAC 权限控制。

**基础 URL**: `http://localhost:8080/api/v1`  
**认证方式**: Bearer Token (JWT)  
**权限级别**: viewer (查看), operator (操作), admin (管理员)

## API 模块总览

| 模块 | 路径前缀 | 端点数 | 说明 |
|------|---------|-------|------|
| 认证 | /auth | 8 | 登录/登出/刷新令牌/密码管理 |
| 用户 | /users | 12 | 用户 CRUD/角色/权限/会话管理 |
| 设备 | /devices | 15 | 设备 CRUD/树结构/状态/生命周期 |
| 点位 | /points | 10 | 点位 CRUD/批量导入/模板 |
| 实时数据 | /realtime | 6 | 实时数据查询/WebSocket 推送 |
| 告警 | /alarms | 18 | 告警 CRUD/确认/处理/统计/导出 |
| 阈值 | /thresholds | 8 | 阈值配置/批量设置 |
| 历史数据 | /history | 8 | 历史数据查询/聚合/导出 |
| 能源管理 | /energy | 45+ | 用电设备/PUE/能耗统计/节能建议 |
| 资产管理 | /assets | 20 | 资产台账/机柜/U 位/生命周期 |
| 容量管理 | /capacity | 15 | 四维容量/趋势预测/智能上架 |
| 拓扑管理 | /topology | 12 | 配电拓扑/制冷拓扑/故障影响 |
| 联动引擎 | /linkage | 10 | 联动规则/执行/事件追踪 |
| 视频监控 | /video | 8 | 摄像头管理/告警联动/PTZ 控制 |
| 运维管理 | /operation | 25 | 工单/巡检/知识库 |
| 报表管理 | /reports | 10 | 报表生成/导出/定时任务 |
| 网关管理 | /gateways | 12 | 网关注册/配置/状态监控 |
| 数据源管理 | /datasources | 10 | 数据源配置/连接测试 |
| 设备模板 | /device-templates | 8 | 模板 CRUD/应用 |
| 制冷系统 | /cooling | 10 | 制冷设备/效率监控 |
| 供配电系统 | /power | 12 | 配电设备/负载监控 |
| 监控仪表盘 | /monitoring | 8 | 六大子系统仪表盘数据 |
| 节能机会 | /opportunities | 8 | 节能机会识别/评估 |
| 节能优化 | /optimization | 10 | 优化方案/执行追踪 |
| 电价管理 | /pricing | 8 | 电价配置/时段管理 |
| 需量管理 | /demand | 10 | 需量监控/优化 |
| 优化方案 | /proposals | 8 | 方案管理/审批 |
| 执行追踪 | /execution | 8 | 执行记录/效果评估 |
| 调节控制 | /regulation | 8 | 设备调节/控制命令 |
| 智能诊断 | /diagnosis | 10 | 故障诊断/恢复流程 |
| 事件追踪 | /trace | 8 | 事件时间线/追溯 |
| 告警升级 | /escalation | 8 | 升级规则/通知 |
| 数据质量 | /data-quality | 6 | 数据质量标记/检测 |
| 数据漂移 | /drift | 8 | 传感器漂移检测 |
| 控制命令 | /commands | 10 | 命令管理/分级确认 |
| 空间管理 | /spatial | 10 | 楼层/区域/机柜 |
| 楼层地图 | /floor-maps | 8 | 地图配置/设备定位 |
| 拓扑配置 | /topology-config | 10 | 拓扑配置/验证 |
| 系统健康 | /system-health | 8 | 系统状态/健康检查 |
| 调度优化 | /dispatch | 10 | 负载调度/优化 |
| 虚拟电厂 | /vpp | 12 | VPP 数据/调度 |
| OTA 升级 | /ota | 8 | 网关 OTA 升级 |
| 机器学习 | /ml | 10 | 负载预测/异常检测 (可选) |
| 系统配置 | /configs | 10 | 系统配置 CRUD |
| 日志管理 | /logs | 8 | 操作日志/审计 |
| 统计分析 | /statistics | 12 | 多维度统计分析 |

## 核心 API 模块详解

### 1. 认证模块 (/auth)

#### POST /auth/login
登录获取访问令牌

**请求体**:
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**响应**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1440,
  "user": {
    "id": 1,
    "username": "admin",
    "role": "admin",
    "permissions": ["read", "write", "admin"]
  }
}
```

**特性**:
- 速率限制: 每分钟最多 5 次尝试
- 密码策略验证
- 登录历史记录
- 并发会话限制

#### POST /auth/refresh
刷新访问令牌

**请求头**: `Authorization: Bearer <token>`

**响应**: 新的 access_token

#### POST /auth/logout
登出（撤销令牌）

**请求头**: `Authorization: Bearer <token>`

#### POST /auth/change-password
修改密码

**请求体**:
```json
{
  "old_password": "admin123",
  "new_password": "NewPass123!"
}
```

**密码策略**:
- 最小长度: 8 字符
- 最少类别: 3 种 (大写/小写/数字/特殊字符)
- 历史检查: 不能与最近 5 次密码相同
- 过期时间: 90 天

### 2. 设备管理模块 (/devices)

#### GET /devices
获取设备列表（分页）

**查询参数**:
- `page`: 页码 (默认 1)
- `page_size`: 每页数量 (默认 20, 最大 100)
- `keyword`: 关键词搜索
- `device_type`: 设备类型
- `area_code`: 区域代码
- `status`: 状态 (online/offline/fault)
- `site_id`: 站点 ID

**响应**:
```json
{
  "items": [
    {
      "id": 1,
      "device_code": "UPS-01",
      "device_name": "UPS 1号机",
      "device_type": "UPS",
      "area_code": "A",
      "status": "online",
      "site_id": 1,
      "created_at": "2026-01-01T00:00:00",
      "updated_at": "2026-03-01T10:00:00"
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 20
}
```

#### GET /devices/tree
获取设备树结构（按区域-设备类型-设备）

**响应**:
```json
{
  "A": {
    "label": "A区",
    "children": {
      "UPS": {
        "label": "UPS",
        "children": [
          {"id": 1, "label": "UPS 1号机", "code": "UPS-01", "status": "online"}
        ]
      }
    }
  }
}
```

#### POST /devices
创建设备

**请求体**:
```json
{
  "device_code": "UPS-02",
  "device_name": "UPS 2号机",
  "device_type": "UPS",
  "area_code": "A",
  "site_id": 1,
  "manufacturer": "华为",
  "model": "UPS5000-A",
  "rated_power": 100.0,
  "install_date": "2026-01-01"
}
```

#### PUT /devices/{id}
更新设备

#### DELETE /devices/{id}
删除设备（检查依赖关系）

**响应**:
```json
{
  "can_delete": false,
  "reason": "设备有 15 个关联点位，无法删除",
  "dependencies": {
    "points": 15,
    "alarms": 3
  }
}
```

#### GET /devices/{id}/status
获取设备状态详情

**响应**:
```json
{
  "device_id": 1,
  "status": "online",
  "online_points": 12,
  "offline_points": 3,
  "active_alarms": 2,
  "last_update": "2026-03-01T10:30:00"
}
```

### 3. 告警管理模块 (/alarms)

#### GET /alarms
获取告警列表（多条件筛选）

**查询参数**:
- `page`, `page_size`: 分页
- `status`: active/acknowledged/resolved
- `level`: critical/major/minor/info
- `point_id`: 点位 ID
- `device_type`: 设备类型
- `start_time`, `end_time`: 时间范围
- `keyword`: 关键词

**响应**:
```json
{
  "items": [
    {
      "id": 1,
      "point_id": 10,
      "point_code": "UPS-01-V",
      "point_name": "UPS 1号机电压",
      "alarm_level": "critical",
      "alarm_message": "电压过低: 210V (阈值: 220V)",
      "status": "active",
      "created_at": "2026-03-01T10:00:00",
      "acknowledged_at": null,
      "resolved_at": null
    }
  ],
  "total": 50,
  "page": 1,
  "page_size": 20
}
```

#### GET /alarms/active
获取所有活动告警

#### GET /alarms/statistics
获取告警统计

**响应**:
```json
{
  "total": 150,
  "by_level": {
    "critical": 5,
    "major": 15,
    "minor": 80,
    "info": 50
  },
  "by_status": {
    "active": 20,
    "acknowledged": 30,
    "resolved": 100
  },
  "by_device_type": {
    "UPS": 30,
    "空调": 50,
    "温湿度": 70
  }
}
```

#### POST /alarms/{id}/acknowledge
确认告警

**请求体**:
```json
{
  "note": "已通知运维人员处理"
}
```

#### POST /alarms/{id}/resolve
解除告警

**请求体**:
```json
{
  "resolution": "已更换传感器，问题解决",
  "root_cause": "传感器老化"
}
```

#### POST /alarms/batch-acknowledge
批量确认告警

**请求体**:
```json
{
  "alarm_ids": [1, 2, 3],
  "note": "批量确认"
}
```

#### GET /alarms/export
导出告警记录 (CSV)

### 4. 能源管理模块 (/energy)

能源管理是最复杂的模块，包含 45+ 个端点。

#### 用电设备管理

**GET /energy/devices** - 获取用电设备列表  
**POST /energy/devices** - 创建用电设备  
**PUT /energy/devices/{id}** - 更新用电设备  
**DELETE /energy/devices/{id}** - 删除用电设备  
**GET /energy/devices/tree** - 获取配电层级树

#### 实时电力监控

**GET /energy/realtime** - 获取实时功率数据  
**GET /energy/realtime/summary** - 获取电力汇总 (PUE/今日/本月)

**响应示例**:
```json
{
  "current_power": 1250.5,
  "it_power": 850.3,
  "cooling_power": 300.2,
  "other_power": 100.0,
  "pue": 1.47,
  "today_energy": 28500.0,
  "month_energy": 850000.0,
  "timestamp": "2026-03-01T10:30:00"
}
```

#### PUE 监控

**GET /energy/pue** - 获取当前 PUE  
**GET /energy/pue/trend** - 获取 PUE 历史趋势

**响应示例**:
```json
{
  "current_pue": 1.47,
  "target_pue": 1.40,
  "trend": [
    {"timestamp": "2026-03-01T00:00:00", "pue": 1.45},
    {"timestamp": "2026-03-01T01:00:00", "pue": 1.46},
    {"timestamp": "2026-03-01T02:00:00", "pue": 1.47}
  ]
}
```

#### 能耗统计

**GET /energy/statistics/daily** - 日能耗统计  
**GET /energy/statistics/monthly** - 月能耗统计  
**GET /energy/statistics/summary** - 能耗汇总  
**GET /energy/statistics/trend** - 能耗趋势  
**GET /energy/statistics/comparison** - 同比/环比分析

**日统计响应示例**:
```json
{
  "date": "2026-03-01",
  "total_energy": 28500.0,
  "peak_energy": 5200.0,
  "valley_energy": 8500.0,
  "flat_energy": 14800.0,
  "cost": 18500.0,
  "by_device_type": {
    "IT设备": 18000.0,
    "空调": 8500.0,
    "照明": 2000.0
  }
}
```

#### 电价管理

**GET /energy/pricing** - 获取电价配置  
**POST /energy/pricing** - 创建电价配置  
**PUT /energy/pricing/{id}** - 更新电价配置  
**DELETE /energy/pricing/{id}** - 删除电价配置

**电价配置示例**:
```json
{
  "id": 1,
  "name": "工业电价",
  "peak_price": 1.2,
  "flat_price": 0.8,
  "valley_price": 0.4,
  "peak_hours": "08:00-11:00,18:00-23:00",
  "valley_hours": "23:00-07:00",
  "effective_date": "2026-01-01"
}
```

#### 节能建议

**GET /energy/suggestions** - 获取节能建议列表  
**PUT /energy/suggestions/{id}/accept** - 接受建议  
**PUT /energy/suggestions/{id}/reject** - 拒绝建议  
**PUT /energy/suggestions/{id}/complete** - 完成建议

**建议示例**:
```json
{
  "id": 1,
  "type": "peak_valley_arbitrage",
  "title": "峰谷套利优化",
  "description": "将部分负载从高峰时段转移到低谷时段",
  "potential_saving": 5000.0,
  "status": "pending",
  "created_at": "2026-03-01T08:00:00"
}
```

#### 节能潜力分析

**GET /energy/saving/potential** - 获取节能潜力分析

**响应示例**:
```json
{
  "total_potential": 50000.0,
  "by_category": {
    "peak_valley_arbitrage": 15000.0,
    "demand_optimization": 10000.0,
    "pue_optimization": 12000.0,
    "cooling_optimization": 8000.0,
    "load_balancing": 3000.0,
    "renewable_energy": 2000.0
  }
}
```

#### 配电拓扑

**GET /energy/distribution** - 获取配电拓扑图

**响应示例**:
```json
{
  "nodes": [
    {"id": "T1", "type": "transformer", "name": "变压器1", "capacity": 1000},
    {"id": "M1", "type": "meter", "name": "总表", "parent": "T1"},
    {"id": "P1", "type": "panel", "name": "配电柜1", "parent": "M1"}
  ],
  "edges": [
    {"from": "T1", "to": "M1"},
    {"from": "M1", "to": "P1"}
  ]
}
```

#### 导出功能

**GET /energy/export/daily** - 导出日报 (Excel/CSV)  
**GET /energy/export/monthly** - 导出月报 (Excel/CSV)

### 5. 资产管理模块 (/assets)

#### GET /assets
获取资产列表

**查询参数**:
- `page`, `page_size`: 分页
- `asset_type`: 资产类型
- `status`: 状态 (in_stock/in_use/maintenance/retired)
- `location`: 位置
- `keyword`: 关键词

#### POST /assets
创建资产

**请求体**:
```json
{
  "asset_code": "SRV-001",
  "asset_name": "服务器 Dell R740",
  "asset_type": "服务器",
  "manufacturer": "Dell",
  "model": "PowerEdge R740",
  "serial_number": "SN123456",
  "purchase_date": "2026-01-01",
  "warranty_expire": "2029-01-01",
  "status": "in_stock",
  "location": "仓库A"
}
```

#### GET /assets/{id}/lifecycle
获取资产生命周期记录

**响应**:
```json
{
  "asset_id": 1,
  "events": [
    {"type": "purchase", "date": "2026-01-01", "note": "采购入库"},
    {"type": "deploy", "date": "2026-01-15", "location": "A区机柜01", "note": "上架部署"},
    {"type": "maintenance", "date": "2026-02-01", "note": "定期维护"}
  ]
}
```

#### GET /assets/cabinets/{id}/u-position
获取机柜 U 位占用情况

**响应**:
```json
{
  "cabinet_id": 1,
  "total_u": 42,
  "used_u": 28,
  "available_u": 14,
  "positions": [
    {"u_start": 1, "u_end": 2, "asset_id": 10, "asset_name": "服务器1"},
    {"u_start": 3, "u_end": 4, "asset_id": 11, "asset_name": "服务器2"}
  ]
}
```

### 6. 容量管理模块 (/capacity)

#### GET /capacity/summary
获取四维容量汇总

**响应**:
```json
{
  "space": {"total": 100, "used": 65, "available": 35, "usage_rate": 0.65},
  "power": {"total": 1000, "used": 750, "available": 250, "usage_rate": 0.75},
  "cooling": {"total": 800, "used": 600, "available": 200, "usage_rate": 0.75},
  "weight": {"total": 50000, "used": 35000, "available": 15000, "usage_rate": 0.70}
}
```

#### GET /capacity/trend
获取容量趋势

**查询参数**:
- `dimension`: space/power/cooling/weight
- `period`: 3m/6m/12m

**响应**:
```json
{
  "dimension": "power",
  "historical": [
    {"date": "2026-01-01", "usage_rate": 0.70},
    {"date": "2026-02-01", "usage_rate": 0.72},
    {"date": "2026-03-01", "usage_rate": 0.75}
  ],
  "prediction": [
    {"date": "2026-04-01", "usage_rate": 0.78},
    {"date": "2026-05-01", "usage_rate": 0.81},
    {"date": "2026-06-01", "usage_rate": 0.84}
  ],
  "threshold_warning": 0.80,
  "threshold_critical": 0.90
}
```

#### POST /capacity/recommend-cabinet
智能上架推荐

**请求体**:
```json
{
  "asset_type": "服务器",
  "power_requirement": 5.0,
  "cooling_requirement": 4.0,
  "u_requirement": 2,
  "weight": 50.0
}
```

**响应**:
```json
{
  "recommendations": [
    {
      "cabinet_id": 5,
      "cabinet_name": "A区机柜05",
      "score": 95,
      "reasons": ["电力充足", "制冷充足", "U位充足", "三相平衡"],
      "available_power": 10.0,
      "available_cooling": 8.0,
      "available_u": 14
    }
  ]
}
```

### 7. 运维管理模块 (/operation)

#### 工单管理

**GET /operation/workorders** - 获取工单列表  
**POST /operation/workorders** - 创建工单  
**PUT /operation/workorders/{id}** - 更新工单  
**POST /operation/workorders/{id}/assign** - 分配工单  
**POST /operation/workorders/{id}/complete** - 完成工单

**工单示例**:
```json
{
  "id": 1,
  "title": "UPS 1号机电池更换",
  "type": "maintenance",
  "priority": "high",
  "status": "in_progress",
  "assignee": "张三",
  "created_by": "李四",
  "created_at": "2026-03-01T08:00:00",
  "due_date": "2026-03-03T18:00:00"
}
```

#### 巡检管理

**GET /operation/inspections** - 获取巡检任务列表  
**POST /operation/inspections** - 创建巡检计划  
**POST /operation/inspections/{id}/execute** - 执行巡检  
**POST /operation/inspections/{id}/submit** - 提交巡检结果

#### 知识库

**GET /operation/knowledge** - 获取知识库文章列表  
**POST /operation/knowledge** - 创建知识库文章  
**GET /operation/knowledge/{id}** - 获取文章详情  
**GET /operation/knowledge/search** - 搜索知识库

### 8. 实时数据模块 (/realtime)

#### GET /realtime/points
获取多个点位的实时数据

**查询参数**:
- `point_ids`: 点位 ID 列表 (逗号分隔)

**响应**:
```json
{
  "data": [
    {
      "point_id": 1,
      "point_code": "UPS-01-V",
      "value": 220.5,
      "unit": "V",
      "quality": "good",
      "timestamp": "2026-03-01T10:30:00"
    }
  ]
}
```

#### WebSocket 实时推送

**连接**: `ws://localhost:8080/ws/realtime?token=<jwt_token>`

**推送消息格式**:
```json
{
  "type": "realtime_data",
  "data": {
    "point_id": 1,
    "value": 220.5,
    "timestamp": "2026-03-01T10:30:00"
  }
}
```

## 通用响应格式

### 成功响应

```json
{
  "code": 200,
  "message": "success",
  "data": { ... }
}
```

### 分页响应

```json
{
  "items": [ ... ],
  "total": 100,
  "page": 1,
  "page_size": 20
}
```

### 错误响应

```json
{
  "code": 400,
  "message": "参数错误",
  "detail": "device_code 不能为空"
}
```

## HTTP 状态码

- `200 OK`: 请求成功
- `201 Created`: 创建成功
- `400 Bad Request`: 请求参数错误
- `401 Unauthorized`: 未认证
- `403 Forbidden`: 无权限
- `404 Not Found`: 资源不存在
- `409 Conflict`: 资源冲突
- `422 Unprocessable Entity`: 验证失败
- `429 Too Many Requests`: 请求过于频繁
- `500 Internal Server Error`: 服务器错误

## 认证与权限

### JWT Token 格式

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 权限级别

| 级别 | 说明 | 可访问端点 |
|------|------|----------|
| viewer | 查看者 | GET 端点 |
| operator | 操作员 | GET + POST/PUT (非敏感) |
| admin | 管理员 | 所有端点 |

### 权限装饰器

- `require_viewer`: 需要 viewer 及以上权限
- `require_operator`: 需要 operator 及以上权限
- `require_admin`: 需要 admin 权限

## WebSocket 通道

| 通道 | URL | 用途 |
|------|-----|------|
| realtime | /ws/realtime?token=xxx | 实时数据推送 |
| alarms | /ws/alarms?token=xxx | 告警通知 |
| system | /ws/system?token=xxx | 系统状态 |

## API 文档

完整的 API 文档可通过 Swagger UI 访问:

**URL**: http://localhost:8080/docs

Swagger UI 提供:
- 所有端点的详细说明
- 请求/响应 Schema
- 在线测试功能
- 示例代码生成

## 更新记录

- 2026-03-01: 初始版本，涵盖 V3.2.1 所有 48 个 API 模块
