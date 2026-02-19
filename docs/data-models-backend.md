# 后端数据模型

> 基于 backend/app/models/ 目录下 27 个模型文件的穷举式扫描。
> 数据库: SQLite (开发) / PostgreSQL (生产)，ORM: SQLAlchemy 2.0 异步模式。

## 模型总览

共计 27 个模型文件，定义 100+ 个 SQLAlchemy 模型类。

| 文件 | 模型数 | 业务域 |
|------|--------|--------|
| user.py | 6 | 用户与权限 |
| device.py | 1 | 设备管理 |
| point.py | 4 | 点位管理 |
| alarm.py | 6 | 告警管理 |
| history.py | 3 | 历史数据 |
| log.py | 3 | 系统日志 |
| report.py | 4 | 报表管理 |
| config.py | 3 | 系统配置 |
| energy.py | 43 | 用电/能源管理 (最大文件) |
| asset.py | 6 | 资产管理 |
| capacity.py | 6 | 容量管理 |
| operation.py | 7 | 运维管理 |
| floor_map.py | 1 | 楼层图 |
| power.py | 2 | 供配电 |
| cooling.py | 3 | 制冷系统 |
| vpp_data.py | 5 | 虚拟电厂 |
| trace.py | 4 | 数据追溯 |
| gateway.py | 7 | 网关/数据源 |
| spatial.py | 5 | 空间拓扑 |
| topology_config.py | 4 | 拓扑配置 |
| linkage.py | 6 | 联动引擎 |
| diagnosis.py | 2 | 智能诊断 |
| command.py | 2 | 控制命令 |
| drift.py | 1 | 漂移检测 |
| video.py | 4 | 视频监控 |
| system.py | — | 系统级 (部分重复导出) |

---

## 用户与权限 (user.py)

### User — 用户表
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK, 自增 | 主键 |
| username | String(50) | unique, not null | 用户名 |
| password_hash | String(255) | not null | 密码哈希 |
| real_name | String(50) | — | 真实姓名 |
| email | String(100) | — | 邮箱 |
| phone | String(20) | — | 手机号 |
| role | String(20) | default="operator" | 角色: admin/operator/viewer |
| department | String(100) | — | 部门 |
| avatar | String(255) | — | 头像 |
| is_active | Boolean | default=True | 是否启用 |
| last_login_at | DateTime | — | 最后登录时间 |
| last_login_ip | String(50) | — | 最后登录IP |
| login_count | Integer | default=0 | 登录次数 |
| password_changed_at | DateTime | nullable | 密码修改时间 |
| created_at | DateTime | default=now | 创建时间 |
| updated_at | DateTime | auto update | 更新时间 |

### RolePermission — 角色权限表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | PK |
| role | String(20) | 角色名 |
| permission | String(100) | 权限标识 (如 user:read) |
| created_at | DateTime | 创建时间 |

### UserLoginHistory — 登录历史
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | PK |
| user_id | Integer | FK → users.id |
| login_at | DateTime | 登录时间 |
| login_ip | String(50) | 登录IP |
| user_agent | String(255) | 浏览器UA |
| status | String(20) | success/failed |
| fail_reason | String(100) | 失败原因 |

### UserSession — 用户会话
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | PK |
| user_id | Integer | FK → users.id |
| token_jti | String(64) | unique, JWT ID |
| is_active | Boolean | 是否有效 |

### UserSite — 用户站点关联
- UniqueConstraint(user_id, site_id)

### PasswordHistory — 密码历史
- user_id FK → users.id, password_hash

---

## 点位管理 (point.py)

### Point — 点位表 (核心表)
| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | 主键 |
| point_code | String(50) | unique, not null | 点位编码 |
| point_name | String(100) | not null | 点位名称 |
| point_type | String(20) | not null | 类型: AI/DI/AO/DO/measurement/control/status/alarm |
| device_id | Integer | FK → devices.id | 关联设备 |
| device_type | String(20) | — | 设备类型: TH/UPS/PDU/AC/DOOR/SMOKE/WATER |
| area_code | String(10) | — | 区域: A1/A2/B1/B2 |
| unit | String(20) | — | 单位 |
| data_type | String(10) | default="float" | 数据类型 |
| min_range | Float | — | 量程最小值 |
| max_range | Float | — | 量程最大值 |
| precision | Integer | default=2 | 小数位数 |
| collect_interval | Integer | default=10 | 采集周期(秒) |
| store_interval | Integer | default=60 | 存储周期(秒) |
| is_enabled | Boolean | default=True | 是否启用 |
| is_virtual | Boolean | default=False | 是否虚拟点位 |
| calc_formula | Text | — | 计算公式 |
| energy_device_id | Integer | — | 关联用能设备 |
| register_address | String(50) | — | 寄存器地址 |
| function_code | Integer | — | Modbus功能码 |
| scale_factor | Float | default=1.0 | 比例因子 |
| offset | Float | default=0.0 | 偏移量 |

### PointRealtime — 实时值表
| 字段 | 类型 | 说明 |
|------|------|------|
| point_id | Integer | PK, FK → points.id |
| raw_value | Float | 原始值 |
| value | Float | 工程值 |
| value_text | String(50) | 状态文本 |
| quality | Integer | 0=好 1=不确定 2=坏 |
| status | String(20) | normal/alarm/offline |
| alarm_level | String(20) | 当前告警级别 |

### PointGroup — 点位分组
- group_name, group_type (area/device_type/custom), parent_id

### PointGroupMember — 分组关系
- 复合主键: group_id + point_id

---

## 设备管理 (device.py)

### Device — 设备表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | PK |
| device_code | String(50) | unique, 设备编码 |
| device_name | String(100) | 设备名称 |
| device_type | String(20) | 设备类型 |
| area_code | String(10) | 区域代码 |
| manufacturer | String(100) | 制造商 |
| model | String(100) | 型号 |
| serial_number | String(100) | 序列号 |
| install_date | Date | 安装日期 |
| status | String(20) | default="online" |
| site_id | Integer | FK → sites.id |
| is_enabled | Boolean | default=True |

---

## 告警管理 (alarm.py)

### AlarmThreshold — 告警阈值
- point_id FK → points.id, threshold_type, threshold_value, alarm_level, delay_seconds, dead_band, is_enabled

### Alarm — 告警记录
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | PK |
| alarm_no | String(50) | unique, 告警编号 |
| point_id | Integer | FK → points.id |
| threshold_id | Integer | FK → alarm_thresholds.id |
| alarm_level | String(20) | critical/major/minor/info |
| alarm_type | String(20) | 告警类型 |
| alarm_message | Text | 告警消息 |
| trigger_value | Float | 触发值 |
| threshold_value | Float | 阈值 |
| status | String(20) | active/acknowledged/resolved |
| acknowledged_by | Integer | FK → users.id |
| resolved_by | Integer | FK → users.id |
| escalation_count | Integer | 升级次数 |
| escalated_from | String(20) | 原始级别 |

### AlarmRule — 告警规则
- rule_name, rule_type, condition_expr, alarm_level, is_enabled

### AlarmShield — 告警屏蔽
- point_id, alarm_level, start_time, end_time, reason

### AlarmDailyStats — 每日统计
- stat_date, point_id, alarm_level, total_count, ack_count, resolve_count

### AlarmEscalation — 告警升级规则
- rule_name, source_level, timeout_minutes, target_level, notify_user_ids

---

## 历史数据 (history.py)

### PointHistory — 点位历史
- point_id, value, quality, status, recorded_at
- 索引: (point_id, recorded_at)

### PointHistoryArchive — 历史归档
- 与 PointHistory 结构相同，用于归档

### PointChangeLog — 变更日志
- point_id, field_name, old_value, new_value, changed_by

---

## 能源管理 (energy.py) — 43 个模型

### 配电系统拓扑

| 模型 | 表名 | 说明 | 关键关系 |
|------|------|------|----------|
| Transformer | transformers | 变压器 | → MeterPoint |
| MeterPoint | meter_points | 计量点 | → Transformer, → DistributionPanel |
| DistributionPanel | distribution_panels | 配电柜 | → MeterPoint, → DistributionCircuit, 自引用 parent |
| DistributionCircuit | distribution_circuits | 配电回路 | → DistributionPanel, → PowerDevice |

### 需量管理

| 模型 | 表名 | 说明 |
|------|------|------|
| PowerCurveData | power_curve_data | 功率曲线数据 (15分钟粒度) |
| DemandHistory | demand_history | 月度需量统计 |
| OverDemandEvent | over_demand_events | 超需量事件 |
| Demand15MinData | demand_15min_data | 15分钟需量数据 |
| DemandAnalysisRecord | demand_analysis_records | 需量分析记录 |

### 设备负荷

| 模型 | 表名 | 说明 |
|------|------|------|
| DeviceLoadProfile | device_load_profiles | 设备负荷曲线 |
| DeviceShiftConfig | device_shift_configs | 设备转移配置 |
| PowerDevice | power_devices | 用电设备 (核心) |
| LoadRegulationConfig | load_regulation_configs | 负荷调节配置 |
| RegulationHistory | regulation_history | 调节历史 |

### 能耗统计

| 模型 | 表名 | 说明 |
|------|------|------|
| EnergyHourly | energy_hourly | 小时能耗 |
| EnergyDaily | energy_daily | 日能耗 |
| EnergyMonthly | energy_monthly | 月能耗 |
| PUEHistory | pue_history | PUE 历史 |

### 电价与建议

| 模型 | 表名 | 说明 |
|------|------|------|
| ElectricityPricing | electricity_pricing | 电价时段 |
| PricingConfig | pricing_configs | 电价配置 (含需量电价/容量电价) |
| EnergySuggestion | energy_suggestions | 节能建议 |

### 节能方案

| 模型 | 表名 | 说明 |
|------|------|------|
| EnergySavingProposal | energy_saving_proposals | 节能方案 |
| ProposalMeasure | proposal_measures | 方案措施 |
| MeasureExecutionLog | measure_execution_logs | 措施执行日志 |

### 节能机会与执行

| 模型 | 表名 | 说明 |
|------|------|------|
| EnergyOpportunity | energy_opportunities | 节能机会 |
| OpportunityMeasure | opportunity_measures | 机会措施 |
| ExecutionPlan | execution_plans | 执行计划 |
| ExecutionTask | execution_tasks | 执行任务 |
| ExecutionResult | execution_results | 执行结果 |

### V3.0 电费综合优化

| 模型 | 表名 | 说明 |
|------|------|------|
| DispatchableDevice | dispatchable_devices | 可调度设备 |
| StorageSystemConfig | storage_system_configs | 储能系统配置 |
| PVSystemConfig | pv_system_configs | 光伏系统配置 |
| DispatchSchedule | dispatch_schedules | 调度计划 |
| RealtimeMonitoring | realtime_monitoring | 实时监控 |
| MonthlyStatistics | monthly_statistics | 月度统计 |
| OptimizationResult | optimization_results | 优化结果 |

### V3.2 效果监测 (专利 S4)

| 模型 | 表名 | 说明 |
|------|------|------|
| MeasureBaseline | measure_baselines | 措施基线 |
| MonitoringRecord | monitoring_records | 监测记录 |
| EffectReport | effect_reports | 效果报告 |
| MonitoringSession | monitoring_sessions | 监测会话 |

### V3.2 RL 自适应优化 (专利 S5)

| 模型 | 表名 | 说明 |
|------|------|------|
| RLOptimizationHistory | rl_optimization_history | RL 优化历史 |
| RLTrainingLog | rl_training_logs | RL 训练日志 |
| RLModelState | rl_model_states | RL 模型状态 |

---

## 资产管理 (asset.py)

### Cabinet — 机柜
| 字段 | 类型 | 说明 |
|------|------|------|
| cabinet_code | String(50) | unique, 机柜编码 |
| cabinet_name | String(100) | 机柜名称 |
| total_u | Integer | default=42, U位总数 |
| max_power | Float | 最大功率 |
| max_weight | Float | 最大承重 |
| row_id | Integer | FK → rows.id |
| aisle_type | String(10) | 通道类型 |
| grid_x, grid_y | Integer | 网格坐标 |
- 关系: assets, row

### Asset — 资产
- asset_code (unique), asset_name, asset_type (Enum), cabinet_id FK, u_position, u_height, status (Enum)
- 采购信息: purchase_date, purchase_price, supplier, warranty_start/end
- 关系: cabinet, lifecycle_records, maintenance_records

### AssetLifecycle — 生命周期
- asset_id FK, action, action_date, operator, from/to_location

### MaintenanceRecord — 维护记录
- asset_id FK, maintenance_type, technician, vendor, cost

### AssetInventory — 资产盘点
- inventory_code (unique), status, total/checked/matched/unmatched_count
- 关系: items

### AssetInventoryItem — 盘点明细
- inventory_id FK, asset_id FK, expected/actual_location, is_matched

---

## 容量管理 (capacity.py)

| 模型 | 表名 | 说明 |
|------|------|------|
| SpaceCapacity | space_capacities | 空间容量 (面积/机柜/U位) |
| PowerCapacity | power_capacities | 电力容量 (kVA/kW, 自引用层级) |
| CoolingCapacity | cooling_capacities | 制冷容量 (kW, 温湿度) |
| WeightCapacity | weight_capacities | 承重容量 (kg) |
| CapacityPlan | capacity_plans | 容量规划 |
| CapacityHistory | capacity_histories | 容量历史 (索引: type+time) |

---

## 运维管理 (operation.py)

### WorkOrder — 工单
- order_no (unique), title, order_type (Enum), priority (Enum), status (Enum)
- 时间线: created_at → assigned_at → accepted_at → started_at → completed_at → closed_at
- 关系: logs (cascade delete)

### InspectionPlan — 巡检计划
- name, frequency, check_items, assignee
- 关系: tasks (cascade delete)

### InspectionTask — 巡检任务
- plan_id FK, task_no (unique), status (Enum), result, abnormal_count

### KnowledgeBase — 知识库
- title, category, content, tags, view_count, is_published

### AlarmWorkOrderRule — 告警工单规则
- alarm_level, order_type, priority, assignee, is_enabled

### WorkOrderApproval — 工单审批
- order_id FK, approver, status (Enum), timeout_minutes, escalate_to

---

## 空间拓扑 (spatial.py)

层级关系: Site → Floor → Room → Row → Cabinet

| 模型 | 表名 | 说明 | 约束 |
|------|------|------|------|
| Site | sites | 站点 | site_code unique |
| Floor | floors | 楼层 | UniqueConstraint(site_id, floor_code) |
| Room | rooms | 房间 | UniqueConstraint(floor_id, room_code) |
| Row | rows | 列 | — |
| LayoutTemplate | layout_templates | 布局模板 | template_code unique |

---

## 网关与数据源 (gateway.py)

| 模型 | 表名 | 说明 |
|------|------|------|
| Gateway | gateways | 采集网关 (gateway_id unique) |
| DataSource | datasources | 数据源 (协议连接配置) |
| DataSourcePoint | datasource_points | 数据源点位映射 |
| GatewayEvent | gateway_events | 网关事件记录 |
| ConfigPushRecord | config_push_records | 配置下发记录 |
| PointDataLatest | point_data_latest | 最新点位数据 |
| DeviceTemplate | device_templates | 设备模板 |

---

## 联动引擎 (linkage.py)

| 模型 | 表名 | 说明 |
|------|------|------|
| LinkagePolicy | linkage_policies | 联动策略 (trigger_condition JSON) |
| LinkageAction | linkage_actions | 联动动作 (action_config JSON) |
| LinkageExecution | linkage_executions | 执行记录 |
| LinkageLog | linkage_logs | 执行日志 |
| LinkageRecovery | linkage_recoveries | 恢复记录 |
| LinkageRecoveryLog | linkage_recovery_logs | 恢复日志 |

---

## 其他模型

### 拓扑配置 (topology_config.py)
- PowerPhaseMapping: 机柜PDU相位映射, UniqueConstraint(cabinet_id, feed_type)
- CoolingZone: 制冷区域
- CoolingZoneCabinet: 区域-机柜关联
- CoolingZoneUnit: 区域-空调关联

### 供配电 (power.py)
- UPSDevice: UPS设备 (device_id FK, ups_type, rated_capacity)
- BatteryGroup: 电池组 (ups_device_id FK, battery_type, cell_count)

### 制冷系统 (cooling.py)
- CoolingGroup: 群控组
- CoolingUnit: 空调机组 (device_id FK, cooling_capacity_kw)
- ColdAisle: 冷通道 (device_id FK, skylight_count)

### 智能诊断 (diagnosis.py)
- DiagnosisRule: 诊断规则 (rule_code unique, trigger_condition JSON, diagnosis_logic JSON)
- DiagnosisResult: 诊断结果 (alarm_id FK, rule_id FK, causes JSON)

### 控制命令 (command.py)
- CommandApproval: 命令审批 (command_content JSON, risk_level, status)
- CommandAuditLog: 审计日志

### 漂移检测 (drift.py)
- DriftDetectionResult: 检测结果 (point_id FK, deviation_sigma, cross_validation_result)

### 视频监控 (video.py)
- NVR: 录像机 (ip_address, max_channels)
- Camera: 摄像头 (rtsp_url, onvif_url, nvr_id FK)
- CameraPreset: 预置位
- VideoEvent: 视频事件

### VPP 虚拟电厂 (vpp_data.py)
- ElectricityBill: 电费账单
- LoadCurve: 负荷曲线
- ElectricityPrice: 电价
- AdjustableLoad: 可调负荷
- VPPConfig: VPP 配置

### 数据追溯 (trace.py)
- DataSourceMapping: 数据源映射 (mapping_type Enum)
- TraceRecord: 追溯记录
- TraceTree: 追溯树
- TemplateParameter: 模板参数

### 报表 (report.py)
- ReportTemplate: 报表模板
- ReportRecord: 报表记录
- ReportSchedule: 报表调度
- DeviceHealthScore: 设备健康评分

### 系统配置 (config.py)
- SystemConfig: 系统配置 (config_group, config_key, config_value)
- Dictionary: 数据字典 (dict_type, dict_code, dict_name)
- License: 授权信息

### 日志 (log.py)
- OperationLog: 操作日志
- SystemLog: 系统日志
- CommunicationLog: 通信日志

---

## 模型关系图 (核心)

```
Site ──1:N──> Floor ──1:N──> Room ──1:N──> Row ──1:N──> Cabinet ──1:N──> Asset
                                                            │
Device ──1:N──> Point ──1:1──> PointRealtime                │
    │              │                                        │
    │              ├──1:N──> PointHistory                    │
    │              ├──1:N──> AlarmThreshold ──1:N──> Alarm   │
    │              └──1:N──> DriftDetectionResult            │
    │                                                       │
    ├──> UPSDevice ──1:N──> BatteryGroup                    │
    ├──> CoolingUnit                                        │
    └──> ColdAisle                                          │
                                                            │
Transformer ──1:N──> MeterPoint ──1:N──> DistributionPanel  │
                                            │               │
                                    DistributionCircuit     │
                                            │               │
                                        PowerDevice ────────┘

LinkagePolicy ──1:N──> LinkageAction
      │
LinkageExecution ──1:N──> LinkageLog
      │
LinkageRecovery ──1:N──> LinkageRecoveryLog

EnergyOpportunity ──1:N──> OpportunityMeasure
ExecutionPlan ──1:N──> ExecutionTask ──1:N──> ExecutionResult
```
