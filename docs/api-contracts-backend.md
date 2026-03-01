# 后端 API 接口契约

> 基于 backend/app/api/v1/ 目录下 47 个路由模块的精确统计。
> 所有 API 均挂载在 `/api/v1` 前缀下。

## API 总览

| 模块 | 前缀 | 标签 | 端点数(估) | 说明 |
|------|------|------|-----------|------|
 | auth | /auth | 认证 | 8 | 登录/登出/刷新/用户信息 |
 | user | /users | 用户管理 | 12 | 用户 CRUD/密码修改 |
 | device | /devices | 设备管理 | 10 | 设备 CRUD |
 | point | /points | 点位管理 | 14 | 点位 CRUD/批量/分组 |
 | realtime | /realtime | 实时数据 | 8 | 实时数据查询/汇总 |
 | alarm | /alarms | 告警管理 | 21 | 告警 CRUD/确认/处理/屏蔽/规则/统计 |
 | threshold | /thresholds | 阈值配置 | 10 | 阈值 CRUD |
 | history | /history | 历史数据 | 7 | 历史查询/导出/统计 |
 | report | /reports | 报表 | 20 | 模板/生成/下载/健康评分 |
 | log | /logs | 日志 | 5 | 操作日志/系统日志 |
 | statistics | /statistics | 统计分析 | 6 | 仪表盘/趋势/分布 |
 | config | /configs | 系统配置 | 7 | 配置 CRUD/字典 |
 | energy | /energy | 用电管理 | 86 | 设备/实时/PUE/统计/建议/配电 |
 | power | /power | 供配电管理 | 13 | UPS/电池/配电柜/PDU |
 | cooling | /cooling | 制冷系统 | 16 | 空调/冷通道/群控 |
 | regulation | /regulation | 负荷调节 | 9 | 调节配置/历史/执行 |
 | asset | (内置) | 资产管理 | 25 | 资产/机柜/生命周期/盘点 |
 | capacity | (内置) | 容量管理 | 31 | 四维容量/规划/历史/趋势 |
 | operation | (内置) | 运维管理 | 41 | 工单/巡检/知识库 |
 | | demo | /demo | 演示数据 | 5 | 演示数据加载/卸载/刷新 |
 | floor_map | /floor-map | 楼层图 | 3 | 楼层图 CRUD |
 | proposal | (内置) | 方案管理 | 33 | 节能方案 CRUD |
 | vpp | /vpp | VPP方案分析 | 7 | VPP 分析/配置 |
 | pricing | /pricing | 电价配置 | 8 | 电价 CRUD/配置 |
 | opportunities | /opportunities | 节能机会 | 11 | 机会检测/措施/仪表盘 |
 | execution | /execution | 执行管理 | 12 | 执行计划/任务/结果 |
 | demand | (内置) | 需量嵌入式API | 4 | 需量分析/15分钟数据 |
 | dispatch | /dispatch | 可调度资源配置 | 18 | 调度设备/储能/光伏 |
 | monitoring | /monitoring | 电费监控 | 10 | 实时监控/月度统计 |
 | topology | /topology | 拓扑编辑 | 16 | 配电拓扑 CRUD |
 | trace | (内置) | 数据追溯链 | 11 | 追溯记录/追溯树 |
 | optimization | /optimization | 日前调度优化 | 13 | 优化执行/结果 |
 | datasources | /datasources | 数据源管理 | 12 | 数据源 CRUD/测试连接 |
 | gateways | /gateways | 网关管理 | 10 | 网关 CRUD/心跳/事件 |
 | device_templates | /device-templates | 设备模板 | 6 | 模板 CRUD |
 | system_health | /system | 系统 | 6 | 健康检查/降级状态 |
 | data_quality | /data-quality | 数据质量 | 2 | 质量标记/统计 |
 | escalation | /escalations | 告警升级 | 6 | 升级规则 CRUD |
 | spatial | (内置) | 空间拓扑 | 25 | 站点/楼层/房间/列 CRUD |
 | topology_config | /topology-config | 拓扑配置 | 15 | PDU相位/制冷区域 |
 | linkage | /linkage | 联动管理 | 20 | 策略/执行/恢复/时间线 |
 | diagnosis | /diagnosis | 智能诊断 | 12 | 规则/结果/触发 |
 | command | /command | 控制命令 | 8 | 命令审批/审计 |
 | drift | /drift | 漂移检测 | 5 | 检测结果/触发 |
 | video | /video | 视频监控 | 20 | NVR/摄像头/预置位/事件 |
 | ml | /ml | 深度学习节能优化 | 9 | ML 模型 (可选, 需 torch) |

## 系统级端点 (main.py 直接注册)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | / | 系统信息 (名称/版本/状态) |
| GET | /api/health | 健康检查 |
| GET | /api/stats | 系统统计 (点位数/授权信息) |
| WS | /ws/realtime?token=xxx | 实时数据 WebSocket |
| WS | /ws/alarms?token=xxx | 告警通知 WebSocket |
| WS | /ws/system?token=xxx | 系统状态 WebSocket |

## 认证模块 (/api/v1/auth)

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | /auth/login | 用户登录 (OAuth2 表单) | 否 |
| POST | /auth/logout | 用户登出 | 是 |
| POST | /auth/refresh | 刷新令牌 | 是 |
| GET | /auth/me | 获取当前用户信息 | 是 |
| PUT | /auth/password | 修改密码 | 是 |

请求格式 (登录):
```
Content-Type: application/x-www-form-urlencoded
username=admin&password=admin123
```

响应格式:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "user": { "id": 1, "username": "admin", "role": "admin", ... }
}
```

## 用户管理 (/api/v1/users)

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | /users | 用户列表 (分页) | admin |
| POST | /users | 创建用户 | admin |
| GET | /users/{id} | 用户详情 | admin |
| PUT | /users/{id} | 更新用户 | admin |
| DELETE | /users/{id} | 删除用户 | admin |
| PUT | /users/{id}/reset-password | 重置密码 | admin |

## 设备管理 (/api/v1/devices)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /devices | 设备列表 (分页/筛选) |
| POST | /devices | 创建设备 |
| GET | /devices/{id} | 设备详情 |
| PUT | /devices/{id} | 更新设备 |
| DELETE | /devices/{id} | 删除设备 |

## 点位管理 (/api/v1/points)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /points | 点位列表 (分页/筛选) |
| POST | /points | 创建点位 |
| GET | /points/{id} | 点位详情 |
| PUT | /points/{id} | 更新点位 |
| DELETE | /points/{id} | 删除点位 |
| POST | /points/batch | 批量创建点位 |
| GET | /points/groups | 点位分组列表 |
| POST | /points/groups | 创建点位分组 |

## 实时数据 (/api/v1/realtime)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /realtime | 所有实时数据 |
| GET | /realtime/{point_id} | 单点实时数据 |
| GET | /realtime/summary | 实时数据汇总 |
| GET | /realtime/by-area | 按区域查询 |

## 告警管理 (/api/v1/alarms)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /alarms | 告警列表 (分页/筛选) |
| GET | /alarms/{id} | 告警详情 |
| PUT | /alarms/{id}/acknowledge | 确认告警 |
| PUT | /alarms/{id}/resolve | 处理告警 |
| PUT | /alarms/{id}/process | 处理备注 |
| GET | /alarms/statistics | 告警统计 |
| GET | /alarms/daily-stats | 每日统计 |
| GET | /alarms/rules | 告警规则列表 |
| POST | /alarms/rules | 创建告警规则 |
| PUT | /alarms/rules/{id} | 更新告警规则 |
| DELETE | /alarms/rules/{id} | 删除告警规则 |
| GET | /alarms/shields | 告警屏蔽列表 |
| POST | /alarms/shields | 创建告警屏蔽 |
| DELETE | /alarms/shields/{id} | 删除告警屏蔽 |

## 阈值配置 (/api/v1/thresholds)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /thresholds | 阈值列表 |
| POST | /thresholds | 创建阈值 |
| PUT | /thresholds/{id} | 更新阈值 |
| DELETE | /thresholds/{id} | 删除阈值 |
| GET | /thresholds/point/{point_id} | 按点位查询阈值 |

## 历史数据 (/api/v1/history)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /history | 历史数据查询 (分页) |
| GET | /history/trend | 趋势数据 |
| GET | /history/export | 导出历史数据 |
| GET | /history/statistics | 历史统计 |
| GET | /history/compare | 数据对比 |

## 用电管理 (/api/v1/energy)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /energy/devices | 用电设备列表 |
| POST | /energy/devices | 创建用电设备 |
| PUT | /energy/devices/{id} | 更新用电设备 |
| DELETE | /energy/devices/{id} | 删除用电设备 |
| GET | /energy/devices/tree | 配电层级树 |
| GET | /energy/realtime | 实时功率数据 |
| GET | /energy/realtime/summary | 功率汇总 (PUE/今日/本月) |
| GET | /energy/pue | 当前 PUE |
| GET | /energy/pue/trend | PUE 历史趋势 |
| GET | /energy/statistics/daily | 日能耗统计 |
| GET | /energy/statistics/monthly | 月能耗统计 |
| GET | /energy/statistics/summary | 能耗汇总 |
| GET | /energy/statistics/trend | 能耗趋势 |
| GET | /energy/statistics/comparison | 同比/环比 |
| GET | /energy/suggestions | 节能建议列表 |
| PUT | /energy/suggestions/{id}/accept | 接受建议 |
| PUT | /energy/suggestions/{id}/reject | 拒绝建议 |
| PUT | /energy/suggestions/{id}/complete | 完成建议 |
| GET | /energy/saving/potential | 节能潜力分析 |
| GET | /energy/distribution | 配电拓扑 |
| GET | /energy/export/daily | 导出日报 |
| GET | /energy/export/monthly | 导出月报 |

## 供配电管理 (/api/v1/power)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /power/overview | 供配电总览 |
| GET | /power/ups | UPS 列表 |
| GET | /power/ups/{id} | UPS 详情 |
| GET | /power/batteries | 电池组列表 |
| GET | /power/batteries/{id} | 电池组详情 |
| GET | /power/cabinets | 配电柜列表 |
| GET | /power/cabinets/{id} | 配电柜详情 |
| GET | /power/pdu | PDU 列表 |
| GET | /power/pdu/{id} | PDU 详情 |

## 制冷系统 (/api/v1/cooling)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /cooling/overview | 制冷总览 |
| GET | /cooling/units | 空调列表 |
| GET | /cooling/units/{id} | 空调详情 |
| GET | /cooling/cold-aisles | 冷通道列表 |
| GET | /cooling/cold-aisles/{id} | 冷通道详情 |
| GET | /cooling/groups | 群控组列表 |
| PUT | /cooling/groups/{id} | 更新群控组 |

## 联动管理 (/api/v1/linkage)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /linkage/policies | 联动策略列表 |
| POST | /linkage/policies | 创建联动策略 |
| PUT | /linkage/policies/{id} | 更新联动策略 |
| DELETE | /linkage/policies/{id} | 删除联动策略 |
| GET | /linkage/executions | 执行记录列表 |
| GET | /linkage/executions/{id} | 执行详情 |
| GET | /linkage/recoveries | 恢复记录列表 |
| POST | /linkage/recoveries | 触发恢复 |
| GET | /linkage/timeline | 事件时间线 |

## 智能诊断 (/api/v1/diagnosis)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /diagnosis/rules | 诊断规则列表 |
| POST | /diagnosis/rules | 创建诊断规则 |
| PUT | /diagnosis/rules/{id} | 更新诊断规则 |
| DELETE | /diagnosis/rules/{id} | 删除诊断规则 |
| GET | /diagnosis/results | 诊断结果列表 |

## 控制命令 (/api/v1/command)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /command/submit | 提交控制命令 |
| GET | /command/approvals | 待审批列表 |
| PUT | /command/approvals/{id}/approve | 审批通过 |
| PUT | /command/approvals/{id}/reject | 审批拒绝 |
| GET | /command/audit-logs | 审计日志 |

## 视频监控 (/api/v1/video)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /video/nvrs | NVR 列表 |
| POST | /video/nvrs | 创建 NVR |
| GET | /video/cameras | 摄像头列表 |
| POST | /video/cameras | 创建摄像头 |
| GET | /video/cameras/{id} | 摄像头详情 |
| GET | /video/cameras/{id}/presets | 预置位列表 |
| GET | /video/events | 视频事件列表 |

## 其他模块

### 节能机会 (/api/v1/opportunities)
- GET /opportunities/dashboard — 节能仪表盘
- GET /opportunities — 机会列表
- GET /opportunities/{id} — 机会详情
- POST /opportunities/detect — 触发检测
- GET /opportunities/{id}/measures — 措施列表

### 执行管理 (/api/v1/execution)
- GET /execution/plans — 执行计划列表
- POST /execution/plans — 创建执行计划
- GET /execution/plans/{id} — 计划详情
- PUT /execution/tasks/{id}/status — 更新任务状态
- GET /execution/stats — 执行统计

### 数据源管理 (/api/v1/datasources)
- GET /datasources — 数据源列表
- POST /datasources — 创建数据源
- PUT /datasources/{id} — 更新数据源
- DELETE /datasources/{id} — 删除数据源
- POST /datasources/{id}/test — 测试连接

### 网关管理 (/api/v1/gateways)
- GET /gateways — 网关列表
- POST /gateways — 注册网关
- PUT /gateways/{id} — 更新网关
- DELETE /gateways/{id} — 删除网关
- POST /gateways/{id}/heartbeat — 心跳上报
- GET /gateways/{id}/events — 网关事件

### 空间拓扑 (内置前缀)
- GET/POST /spatial/sites — 站点 CRUD
- GET/POST /spatial/floors — 楼层 CRUD
- GET/POST /spatial/rooms — 房间 CRUD
- GET/POST /spatial/rows — 列 CRUD
- GET /spatial/tree — 空间层级树

### VPP 方案分析 (/api/v1/vpp)
- POST /vpp/analyze — VPP 方案分析
- GET /vpp/configs — VPP 配置
- GET /vpp/data — VPP 数据

### 电价配置 (/api/v1/pricing)
- GET /pricing — 电价列表
- POST /pricing — 创建电价
- PUT /pricing/{id} — 更新电价
- DELETE /pricing/{id} — 删除电价
- GET /pricing/configs — 电价配置

### 漂移检测 (/api/v1/drift)
- GET /drift/results — 检测结果列表
- POST /drift/detect — 触发检测
- PUT /drift/results/{id}/resolve — 标记已解决

### 数据质量 (/api/v1/data-quality)
- GET /data-quality/stats — 质量统计
- POST /data-quality/mark — 标记数据质量
- GET /data-quality/points — 质量标记列表

### 告警升级 (/api/v1/escalations)
- GET /escalations — 升级规则列表
- POST /escalations — 创建升级规则
- PUT /escalations/{id} — 更新升级规则
- DELETE /escalations/{id} — 删除升级规则

## 通用响应格式

### 分页响应
```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "page_size": 20
}
```

### 错误响应
```json
{
  "detail": "错误描述"
}
```

### 认证头
```
Authorization: Bearer <access_token>
```

## 演示数据管理 (/api/v1/demo)

| 方法 | 路径 | 说明 | 参数 |
|------|------|------|------|
| POST | /demo/load | 加载演示数据 | `date_offset_days` (可选, 日期偏移天数) |
| DELETE | /demo/unload | 卸载演示数据 | 无 |
| POST | /demo/refresh-dates | 刷新日期 | `date_offset_days` (必填, 日期偏移天数) |
| GET | /demo/status | 演示数据状态 | 无 |
| GET | /demo/stats | 演示数据统计 | 无 |

### 加载演示数据

```bash
# 加载当前日期数据
POST /api/v1/demo/load

# 加载 30 天前数据（演示历史场景）
POST /api/v1/demo/load?date_offset_days=-30

# 加载 7 天后数据（演示未来场景）
POST /api/v1/demo/load?date_offset_days=7
```

响应格式:
```json
{
  "status": "success",
  "message": "演示数据加载完成",
  "stats": {
    "sites": 1,
    "floors": 4,
    "rooms": 8,
    "rows": 16,
    "devices": 628,
    "points": 2830,
    "thresholds": 2830,
    "date_offset_days": 0
  }
}
```

### 卸载演示数据

```bash
DELETE /api/v1/demo/unload
```

清理范围（72 张表）:
- 空间拓扑: Site, Floor, Room, Row, Cabinet
- 设备: Device, Point, PointRealtime, PointHistory, PointDataLatest
- 告警: Alarm, AlarmThreshold, AlarmRule, AlarmShield
- 能源: Transformer, MeterPoint, DistributionPanel, PowerDevice, EnergyHourly, EnergyDaily, EnergyMonthly, PUEHistory 等 40+ 张表
- 资产: Asset, AssetLifecycle, MaintenanceRecord
- 运维: WorkOrder, InspectionPlan, KnowledgeBase
- 容量: SpaceCapacity, PowerCapacity, CoolingCapacity, WeightCapacity
- 拓扑: TopologyNode, TopologyEdge, PDUPhaseConfig
- 联动: LinkagePolicy, LinkageExecution, DiagnosisRule
- 视频: NVR, Camera, VideoEvent
- Redis 缓存: `realtime:*`, `alarm:*`, `energy:*`

### 刷新日期

```bash
# 将所有时间戳向前偏移 30 天
POST /api/v1/demo/refresh-dates?date_offset_days=-30
```

影响范围:
- PointHistory.timestamp
- Alarm.alarm_time, resolved_time
- EnergyHourly/Daily/Monthly.timestamp
- PUEHistory.timestamp
- WorkOrder.created_at, updated_at
- 其他所有时间戳字段

### 查询状态

```bash
GET /api/v1/demo/status
```

响应格式:
```json
{
  "demo_enabled": true,
  "simulator_running": true,
  "data_loaded": true,
  "gateway_id": "demo-gateway",
  "last_update": "2026-03-01T12:34:56"
}
```

### 查询统计

```bash
GET /api/v1/demo/stats
```

响应格式:
```json
{
  "sites": 1,
  "floors": 4,
  "rooms": 8,
  "rows": 16,
  "cabinets": 160,
  "devices": 628,
  "points": 2830,
  "ai_points": 2650,
  "di_points": 180,
  "thresholds": 2830,
  "realtime_data": 2830,
  "history_records": 1234567
}
```
