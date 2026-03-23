# Backend API Contracts — Exhaustive Inventory

**Generated**: 2026-03-23 | **Scan Level**: Exhaustive | **Source**: `backend/app/api/v1/`

---

## Summary

| Metric | Count |
|--------|-------|
| API 模块 | 60 |
| 总端点数 | 836 |
| 认证方式 | JWT Bearer Token (OAuth2PasswordBearer) |
| 权限模型 | RBAC: admin / operator / viewer |

---

## Endpoints by Module (按端点数排序)

| 模块 | 端点数 | 文件 | 主要功能 |
|------|--------|------|---------|
| energy | 97 | `energy.py` | PUE/用电/配电/需量/分时电价/节能建议/RL优化 |
| diagnosis | 55 | `diagnosis.py` | 智能诊断规则/会话/审计/传感器融合/反事实分析 |
| operation | 41 | `operation.py` | 工单/巡检/知识库/告警转工单 |
| proposal | 33 | `proposal.py` | 节能提案/措施/基线/效果评估 |
| shift | 32 | `shift.py` | 负荷转移计划/执行/约束/制冷联动 |
| capacity | 31 | `capacity.py` | 空间/电力/制冷/承重容量规划 |
| spatial | 25 | `spatial.py` | 站点/楼层/机房/列头柜空间管理 |
| asset | 25 | `asset.py` | 资产台账/机柜/生命周期/盘点 |
| precool | 21 | `precool.py` | 预冷调度/TCL模型/温度约束 |
| alarm | 21 | `alarm.py` | 告警查询/确认/屏蔽/统计/每日统计 |
| video | 20 | `video.py` | 视频监控/NVR/摄像头/预置位/事件 |
| topology | 20 | `topology.py` | 配电拓扑/电路/面板/变压器 |
| report | 20 | `report.py` | 报表模板/生成/调度/健康评分/维护建议 |
| linkage | 20 | `linkage.py` | 告警联动/动作/执行/恢复 |
| dispatch | 17 | `dispatch.py` | 可调度设备/储能/光伏/调度计划 |
| cooling | 16 | `cooling.py` | 制冷组/制冷机组/冷通道 |
| topology_config | 15 | `topology_config.py` | 电力相位映射/制冷区/温度传感器 |
| config | 15 | `config.py` | 系统配置/字典/许可证 |
| power | 14 | `power.py` | UPS/电池组/配电设备 |
| point | 14 | `point.py` | 点位管理/分组/批量操作 |
| optimization | 13 | `optimization.py` | RL优化/训练/模型状态 |
| user | 12 | `user.py` | 用户CRUD/角色/登录历史/站点权限 |
| execution | 12 | `execution.py` | 执行计划/任务/结果跟踪 |
| datasources | 12 | `datasources.py` | 数据源CRUD/连接测试/点位导入/通信状态 |
| trace | 11 | `trace.py` | 数据溯源/映射/溯源树 |
| opportunities | 11 | `opportunities.py` | 节能机会发现/措施推荐 |
| device | 11 | `device.py` | 设备CRUD/拓扑/状态 |
| threshold | 10 | `threshold.py` | 告警阈值管理 |
| ota | 10 | `ota.py` | OTA固件升级/任务管理 |
| gateways | 10 | `gateways.py` | 网关管理/事件/配置推送 |
| notification | 9 | `notification.py` | 系统通知/已读/批量操作 |
| device_templates | 9 | `device_templates.py` | 设备模板/点位模板/实例化 |
| auth | 8 | `auth.py` | 登录/登出/刷新/密码修改 |
| regulation | 8 | `regulation.py` | 负荷调控/历史/配置 |
| statistics | 7 | `statistics.py` | 系统统计/概览/趋势 |
| monitoring | 7 | `monitoring.py` | 监控概览/实时数据/面板 |
| data_quality | 7 | `data_quality.py` | 数据质量检测/评分/趋势 |
| history | 7 | `history.py` | 历史数据/导出/归档 |
| command | 7 | `command.py` | 控制命令/审批/审计日志 |
| log | 6 | `log.py` | 操作日志/系统日志/通信日志 |
| pricing | 6 | `pricing.py` | 分时电价方案/审计 |
| demand | 6 | `demand.py` | 需量分析/15分钟数据/趋势 |
| floor_map | 5 | `floor_map.py` | 楼层地图/布局 |
| ml | 5 | `ml.py` | 机器学习预测（条件加载） |
| realtime | 5 | `realtime.py` | 实时数据推送/WebSocket |
| power_redundancy | 4 | `power_redundancy.py` | 电力冗余检测 |
| drift | 4 | `drift.py` | 数据漂移检测 |
| sensor_metadata | 4 | `sensor_metadata.py` | 传感器元数据管理 |
| ab_testing | 4 | `ab_testing.py` | A/B测试/设备分配/归档 |
| vpp | 4 | `vpp.py` | 虚拟电厂/调度/电费 |
| fault_tree_versions | 3 | `fault_tree_versions.py` | 故障树版本管理 |
| notification_policy | 3 | `notification_policy.py` | 通知策略/通道配置 |
| user_notification_contacts | 3 | `user_notification_contacts.py` | 用户通知联系人 |
| probability_tuning | 3 | `probability_tuning.py` | 概率调优/日志 |
| escalation | 3 | `escalation.py` | 告警升级策略 |
| chaos_drill | 3 | `chaos_drill.py` | 混沌演练/故障注入 |
| predictive_maintenance | 3 | `predictive_maintenance.py` | 预测性维护/仪表盘/设备详情 |
| misdiagnosis_reports | 2 | `misdiagnosis_reports.py` | 误诊报告 |
| system_health | 2 | `system_health.py` | 系统健康度 |
| test_endpoint | 1 | `test_endpoint.py` | 测试端点 |

---

## 认证与权限模式

```
require_viewer   → 只读访问（GET 请求）
require_operator → 操作权限（POST/PUT/DELETE）
require_admin    → 管理员权限（用户管理/系统配置/删除操作）
get_user_site_ids → 站点级数据隔离（多站点 RBAC）
```

## WebSocket 端点

| 通道 | URL | 用途 |
|------|-----|------|
| realtime | `/ws/realtime?token=xxx` | 实时数据推送（5秒间隔） |
| alarms | `/ws/alarms?token=xxx` | 告警通知 + 诊断消息 |
| system | `/ws/system?token=xxx` | 系统状态/数据质量变更 |

## 通用响应模式

- 分页: `PageResponse[T]` — `{items, total, page, page_size}`
- 单项: 直接返回 Pydantic model
- 文件: `StreamingResponse` (Excel/PDF)
- 错误: `HTTPException` with status_code + detail

---

## 功能域分组

### 核心基础设施
- **auth** (8): 登录/登出/JWT刷新/密码管理
- **user** (12): 用户CRUD/角色分配/站点权限/登录历史
- **config** (15): 系统配置/数据字典/许可证
- **log** (6): 操作日志/系统日志/通信日志

### 设备与监控
- **device** (11): 设备CRUD/状态/拓扑关系
- **point** (14): 点位管理/分组/批量配置
- **realtime** (5): 实时数据订阅/WebSocket
- **history** (7): 历史数据查询/导出/归档
- **monitoring** (7): 监控概览/面板数据
- **statistics** (7): 系统统计/概览/趋势
- **device_templates** (9): 设备模板/点位模板/实例化

### 网关与数据采集
- **gateways** (10): 网关注册/心跳/事件日志
- **datasources** (12): 数据源管理/连接测试/点位导入
- **ota** (10): OTA固件升级/批量任务
- **trace** (11): 数据溯源/链路映射/溯源树
- **data_quality** (7): 数据质量检测/评分
- **drift** (4): 数据漂移检测
- **sensor_metadata** (4): 传感器元数据

### 告警与联动
- **alarm** (21): 告警查询/确认/解决/屏蔽/统计
- **threshold** (10): 告警阈值CRUD
- **escalation** (3): 告警升级策略
- **linkage** (20): 告警联动策略/动作/执行/恢复
- **notification** (9): 系统通知管理
- **notification_policy** (3): 通知渠道策略
- **user_notification_contacts** (3): 用户通知联系人

### 能源管理
- **energy** (97): PUE/用电/配电/需量/分时电价/节能建议
- **power** (14): UPS/电池组/配电设备
- **topology** (20): 配电拓扑/电路/面板
- **topology_config** (15): 电力相位/制冷区/温度传感器
- **demand** (6): 需量分析/15分钟数据
- **pricing** (6): 分时电价方案
- **regulation** (8): 负荷调控

### 节能优化
- **proposal** (33): 节能提案/措施/效果评估
- **opportunities** (11): 节能机会发现
- **optimization** (13): RL强化学习优化
- **execution** (12): 执行计划/任务跟踪
- **shift** (32): 负荷转移计划/约束/制冷联动
- **precool** (21): 预冷调度/TCL模型
- **dispatch** (17): 可调度设备/储能/光伏
- **vpp** (4): 虚拟电厂
- **ab_testing** (4): A/B测试

### 空间与资产
- **spatial** (25): 站点/楼层/机房/列管理
- **asset** (25): 资产台账/机柜/生命周期/盘点
- **capacity** (31): 四维容量规划(空间/电力/制冷/承重)
- **floor_map** (5): 楼层地图/布局
- **cooling** (16): 制冷组/机组/冷通道

### 智能诊断
- **diagnosis** (55): 诊断规则/会话/传感器融合/反事实分析
- **fault_tree_versions** (3): 故障树版本管理
- **probability_tuning** (3): 概率调优
- **misdiagnosis_reports** (2): 误诊报告
- **chaos_drill** (3): 混沌演练

### 运维管理
- **operation** (41): 工单/巡检/知识库/告警转工单
- **report** (20): 报表模板/生成/调度/健康评分
- **predictive_maintenance** (3): 预测性维护
- **command** (7): 控制命令/审批/审计
- **video** (20): 视频监控/NVR/摄像头
- **system_health** (2): 系统健康度
- **power_redundancy** (4): 电力冗余检测
- **ml** (5): 机器学习预测（条件加载）
