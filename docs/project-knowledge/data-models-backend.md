# Backend Data Models — Exhaustive Inventory

**Generated**: 2026-03-23 | **Scan Level**: Exhaustive | **Source**: `backend/app/models/`

---

## Summary

| Metric | Count |
|--------|-------|
| 模型文件 | 36 |
| ORM 模型类 | 194 |
| Schema 文件 | 46 |
| Alembic 迁移 | 58 |
| ORM 基类 | SQLAlchemy 2.0 DeclarativeBase |

---

## Models by Domain

### 用户与认证 — `user.py` (6 models)

| Model | Table | 说明 |
|-------|-------|------|
| User | users | 用户主表 (username, email, role, is_active, hashed_password) |
| RolePermission | role_permissions | 角色权限映射 |
| UserLoginHistory | user_login_histories | 登录历史 |
| UserSession | user_sessions | 会话管理 |
| UserSite | user_sites | 用户-站点多对多 |
| PasswordHistory | password_histories | 密码历史（防重复） |

### 用户通知联系人 — `user_notification_contact.py` (1 model)

| Model | Table | 说明 |
|-------|-------|------|
| UserNotificationContact | user_notification_contacts | 用户通知联系方式 |

### 设备与点位 — `device.py` + `point.py` (5 models)

| Model | Table | 说明 |
|-------|-------|------|
| Device | devices | 设备主表 (name, type, area, status, site_id) |
| Point | points | 点位主表 (code, name, device_id, data_type, unit) |
| PointRealtime | point_realtime | 点位实时值 (value, quality, status) |
| PointGroup | point_groups | 点位分组 |
| PointGroupMember | point_group_members | 分组-点位关联 |

### 告警 — `alarm.py` (6 models)

| Model | Table | 说明 |
|-------|-------|------|
| AlarmThreshold | alarm_thresholds | 告警阈值配置 |
| Alarm | alarms | 告警记录 (alarm_no, level, type, status, source) |
| AlarmRule | alarm_rules | 告警规则 |
| AlarmShield | alarm_shields | 告警屏蔽策略 |
| AlarmDailyStats | alarm_daily_stats | 每日告警统计 |
| AlarmEscalation | alarm_escalations | 告警升级记录 |

### 网关与数据源 — `gateway.py` (12 models)

| Model | Table | 说明 |
|-------|-------|------|
| DataSourceStatus | — | 状态常量类 (connected/disconnected/interrupted/device_offline/gateway_offline) |
| Gateway | gateways | 网关主表 |
| DataSource | datasources | 数据源 (protocol_type, connection_config, status) |
| DataSourcePoint | datasource_points | 数据源-点位映射 |
| GatewayEvent | gateway_events | 网关事件日志 |
| ConfigPushRecord | config_push_records | 配置推送记录 |
| PointDataLatest | point_data_latest | 最新点位数据缓存 |
| FirmwarePackage | firmware_packages | 固件包 |
| OtaTask | ota_tasks | OTA升级任务 |
| OtaTaskGateway | ota_task_gateways | OTA任务-网关关联 |
| DeviceTemplate | device_templates | 设备模板 |
| MqttAclRule | mqtt_acl_rules | MQTT ACL规则 |

### 历史数据 — `history.py` (3 models)

| Model | Table | 说明 |
|-------|-------|------|
| PointHistory | point_history | 点位历史数据 |
| PointHistoryArchive | point_history_archive | 历史数据归档 |
| PointChangeLog | point_change_logs | 点位变更日志 |

### 能源 — `energy.py` (38 models)

| Model | Table | 说明 |
|-------|-------|------|
| Transformer | transformers | 变压器 |
| MeterPoint | meter_points | 计量点 |
| DistributionPanel | distribution_panels | 配电柜 |
| DistributionCircuit | distribution_circuits | 配电回路 |
| PowerCurveData | power_curve_data | 功率曲线 |
| DemandHistory | demand_histories | 需量历史 |
| OverDemandEvent | over_demand_events | 超需量事件 |
| DeviceLoadProfile | device_load_profiles | 设备负荷曲线 |
| DeviceShiftConfig | device_shift_configs | 设备转移配置 |
| PowerDevice | power_devices | 配电设备 |
| EnergyHourly | energy_hourly | 小时用电 |
| EnergyDaily | energy_daily | 日用电 |
| EnergyMonthly | energy_monthly | 月用电 |
| ElectricityPricing | electricity_pricing | 电价 |
| PricingConfig | pricing_configs | 电价配置 |
| EnergySuggestion | energy_suggestions | 节能建议 |
| PUEHistory | pue_history | PUE历史 |
| LoadRegulationConfig | load_regulation_configs | 负荷调控配置 |
| RegulationHistory | regulation_histories | 调控历史 |
| DemandAnalysisRecord | demand_analysis_records | 需量分析 |
| Demand15MinData | demand_15min_data | 15分钟需量 |
| EnergySavingProposal | energy_saving_proposals | 节能提案 |
| ProposalMeasure | proposal_measures | 提案措施 |
| MeasureExecutionLog | measure_execution_logs | 措施执行日志 |
| MeasureBaseline | measure_baselines | 措施基线 |
| MonitoringRecord | monitoring_records | 监控记录 |
| EffectReport | effect_reports | 效果报告 |
| MonitoringSession | monitoring_sessions | 监控会话 |
| RLOptimizationHistory | rl_optimization_histories | RL优化历史 |
| RLTrainingLog | rl_training_logs | RL训练日志 |
| RLModelState | rl_model_states | RL模型状态 |
| EnergyOpportunity | energy_opportunities | 节能机会 |
| OpportunityMeasure | opportunity_measures | 机会措施 |
| ExecutionPlan | execution_plans | 执行计划 |
| ExecutionTask | execution_tasks | 执行任务 |
| ExecutionResult | execution_results | 执行结果 |
| DispatchableDevice | dispatchable_devices | 可调度设备 |
| StorageSystemConfig | storage_system_configs | 储能系统配置 |
| PVSystemConfig | pv_system_configs | 光伏系统配置 |
| DispatchSchedule | dispatch_schedules | 调度计划 |
| RealtimeMonitoring | realtime_monitoring | 实时监控 |
| MonthlyStatistics | monthly_statistics | 月度统计 |
| OptimizationResult | optimization_results | 优化结果 |
| PricingScheme | pricing_schemes | 电价方案 |
| SchemePricingRelation | scheme_pricing_relations | 方案-电价关联 |
| PricingSchemeAuditLog | pricing_scheme_audit_logs | 电价方案审计 |

### 负荷转移 — `load_shift.py` (8 models)

| Model | Table | 说明 |
|-------|-------|------|
| ShiftPlan | shift_plans | 转移计划 |
| ShiftExecution | shift_executions | 转移执行 |
| ShiftConstraint | shift_constraints | 转移约束 |
| ShiftOpportunity | shift_opportunities | 转移机会 |
| ShiftAnalysisRecord | shift_analysis_records | 分析记录 |
| CoolingLinkageConfig | cooling_linkage_configs | 制冷联动配置 |
| CoolingLinkageRecord | cooling_linkage_records | 制冷联动记录 |
| DeviceLifespanImpact | device_lifespan_impacts | 设备寿命影响评估 |

### 制冷 — `cooling.py` (3 models)

| Model | Table | 说明 |
|-------|-------|------|
| CoolingGroup | cooling_groups | 制冷组 |
| CoolingUnit | cooling_units | 制冷机组 |
| ColdAisle | cold_aisles | 冷通道 |

### 热力学 — `thermal.py` (4 models)

| Model | Table | 说明 |
|-------|-------|------|
| ThermalParameter | thermal_parameters | 热力学参数 (R/C/area) |
| TemperaturePredictionLog | temperature_prediction_logs | 温度预测日志 |
| PrecoolSchedule | precool_schedules | 预冷调度 |
| VppDispatch | vpp_dispatches | VPP调度 |

### 拓扑配置 — `topology_config.py` (5 models)

| Model | Table | 说明 |
|-------|-------|------|
| PowerPhaseMapping | power_phase_mappings | 电力相位映射 |
| CoolingZone | cooling_zones | 制冷区 (area_m2, R_value, C_value) |
| CoolingZoneCabinet | cooling_zone_cabinets | 制冷区-机柜 |
| CoolingZoneUnit | cooling_zone_units | 制冷区-机组 |
| CabinetTemperatureSensor | cabinet_temperature_sensors | 机柜温度传感器 |
| CabinetITLoad | cabinet_it_loads | 机柜IT负载 |

### 资产 — `asset.py` (6 models)

| Model | Table | 说明 |
|-------|-------|------|
| Cabinet | cabinets | 机柜 |
| Asset | assets | 资产主表 |
| AssetLifecycle | asset_lifecycles | 资产生命周期 |
| MaintenanceRecord | maintenance_records | 维护记录 |
| AssetInventory | asset_inventories | 资产盘点 |
| AssetInventoryItem | asset_inventory_items | 盘点项目 |

### 空间 — `spatial.py` (5 models)

| Model | Table | 说明 |
|-------|-------|------|
| Site | sites | 站点 |
| Floor | floors | 楼层 |
| Room | rooms | 机房 |
| Row | rows | 列 |
| LayoutTemplate | layout_templates | 布局模板 |

### 容量 — `capacity.py` (6 models)

| Model | Table | 说明 |
|-------|-------|------|
| SpaceCapacity | space_capacities | 空间容量 |
| PowerCapacity | power_capacities | 电力容量 |
| CoolingCapacity | cooling_capacities | 制冷容量 |
| WeightCapacity | weight_capacities | 承重容量 |
| CapacityPlan | capacity_plans | 容量规划 |
| CapacityHistory | capacity_histories | 容量历史 |

### 运维 — `operation.py` (7 models)

| Model | Table | 说明 |
|-------|-------|------|
| WorkOrder | work_orders | 工单 |
| WorkOrderLog | work_order_logs | 工单日志 |
| InspectionPlan | inspection_plans | 巡检计划 |
| InspectionTask | inspection_tasks | 巡检任务 |
| KnowledgeBase | knowledge_base | 知识库 |
| AlarmWorkOrderRule | alarm_work_order_rules | 告警转工单规则 |
| WorkOrderApproval | work_order_approvals | 工单审批 |

### 诊断 — `diagnosis.py` (20 models)

| Model | Table | 说明 |
|-------|-------|------|
| DiagnosisRule | diagnosis_rules | 诊断规则 |
| DiagnosisResult | diagnosis_results | 诊断结果 |
| DiagnosisSession | diagnosis_sessions | 诊断会话 |
| DiagnosisAuditLog | diagnosis_audit_logs | 诊断审计 |
| DiagnosisAnnotation | diagnosis_annotations | 诊断标注 |
| BatterySOHRecord | battery_soh_records | 电池SOH记录 |
| SOHPointUnavailableTracking | soh_point_unavailable_tracking | SOH点位不可用跟踪 |
| BreakerProfile | breaker_profiles | 断路器画像 |
| SensorMetadata | sensor_metadata | 传感器元数据 |
| TrendWarning | trend_warnings | 趋势预警 |
| SensorFusionRecord | sensor_fusion_records | 传感器融合 |
| CounterfactualAnalysis | counterfactual_analyses | 反事实分析 |
| SystemReport | system_reports | 系统报告 |
| DiagnosisImprovementRule | diagnosis_improvement_rules | 诊断改进规则 |
| ProbabilityAdjustmentLog | probability_adjustment_logs | 概率调整日志 |
| AuditLog | audit_logs | 审计日志 |
| TimeWindowAdjustmentLog | time_window_adjustment_logs | 时间窗口调整 |
| TrainingDataAudit | training_data_audits | 训练数据审计 |
| HMACKeyRotationLog | hmac_key_rotation_logs | HMAC密钥轮换 |

### 故障树 — `fault_tree.py` (5 models)

| Model | Table | 说明 |
|-------|-------|------|
| FaultTree | fault_trees | 故障树 |
| FaultTreeNode | fault_tree_nodes | 故障树节点 |
| FaultTreeEdge | fault_tree_edges | 故障树边 |
| FaultTreeDeviceMapping | fault_tree_device_mappings | 故障树-设备映射 |
| FaultTreeVersion | fault_tree_versions | 故障树版本 |

### 联动 — `linkage.py` (6 models)

| Model | Table | 说明 |
|-------|-------|------|
| LinkagePolicy | linkage_policies | 联动策略 |
| LinkageAction | linkage_actions | 联动动作 |
| LinkageExecution | linkage_executions | 联动执行 |
| LinkageLog | linkage_logs | 联动日志 |
| LinkageRecovery | linkage_recoveries | 联动恢复 |
| LinkageRecoveryLog | linkage_recovery_logs | 恢复日志 |

### 溯源 — `trace.py` (4 models)

| Model | Table | 说明 |
|-------|-------|------|
| DataSourceMapping | datasource_mappings | 数据源映射 |
| TraceRecord | trace_records | 溯源记录 |
| TraceTree | trace_trees | 溯源树 |
| TemplateParameter | template_parameters | 模板参数 |

### 通知 — `notification.py` + `notification_policy.py` + `notification_record.py` (3 models)

| Model | Table | 说明 |
|-------|-------|------|
| SystemNotification | system_notifications | 系统通知 |
| NotificationPolicy | notification_policies | 通知策略 |
| NotificationRecord | notification_records | 通知记录 |

### 日志 — `log.py` (3 models)

| Model | Table | 说明 |
|-------|-------|------|
| OperationLog | operation_logs | 操作日志 |
| SystemLog | system_logs | 系统日志 |
| CommunicationLog | communication_logs | 通信日志 |

### 报表 — `report.py` (5 models)

| Model | Table | 说明 |
|-------|-------|------|
| ReportTemplate | report_templates | 报表模板 |
| ReportRecord | report_records | 报表记录 |
| ReportSchedule | report_schedules | 报表调度 |
| DeviceHealthScore | device_health_scores | 设备健康评分 |
| MaintenanceAdvice | maintenance_advices | 维护建议 |

### 电力设备 — `power.py` (2 models)

| Model | Table | 说明 |
|-------|-------|------|
| UPSDevice | ups_devices | UPS设备 |
| BatteryGroup | battery_groups | 电池组 |

### 视频 — `video.py` (4 models)

| Model | Table | 说明 |
|-------|-------|------|
| NVR | nvrs | 网络录像机 |
| Camera | cameras | 摄像头 |
| CameraPreset | camera_presets | 预置位 |
| VideoEvent | video_events | 视频事件 |

### 其他

| Model | File | 说明 |
|-------|------|------|
| SystemConfig | `config.py` | 系统配置 |
| Dictionary | `config.py` | 数据字典 |
| License | `config.py` | 许可证 |
| FloorMap | `floor_map.py` | 楼层地图 |
| CommandApproval | `command.py` | 命令审批 |
| CommandAuditLog | `command.py` | 命令审计 |
| DriftDetectionResult | `drift.py` | 漂移检测结果 |
| ABTestConfig | `ab_test_config.py` | A/B测试配置 |
| ABTestDeviceAssignment | `ab_test_config.py` | A/B测试设备分配 |
| ABTestArchive | `ab_test_config.py` | A/B测试归档 |
| RollbackEvent | `rollback.py` | 回滚事件 |
| VPP models (5) | `vpp_data.py` | 虚拟电厂数据 |

---

## Schema 文件 (46 files)

位于 `backend/app/schemas/`，每个 Pydantic schema 文件对应一个或多个 API 模块的请求/响应模型。

## Alembic 迁移

- 总迁移数: **58**
- 位于: `backend/alembic/versions/`
- 数据库: SQLite (开发) / PostgreSQL (生产)
