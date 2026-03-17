# 后端数据模型文档

生成时间: 2026-03-17
项目版本: V4.2.0

## 概览

- 总模型数: 134 个 ORM 模型 + 10 个枚举类
- 数据库: PostgreSQL + TimescaleDB (生产) / SQLite (开发)
- ORM: SQLAlchemy 2.0 (异步)
- 迁移工具: Alembic (54 个版本)
- 模型文件: 34 个 Python 文件 (`backend/app/models/`)

## 枚举定义

| 枚举类 | 文件 | 值 |
|--------|------|-----|
| DataSourceType | enums.py | seed/demo/real |
| PricingPeriodType | enums.py | sharp_peak/peak/flat/valley/deep_valley |
| AssetStatus | asset.py | in_stock/in_use/borrowed/maintenance/scrapped |
| AssetType | asset.py | server/network/storage/ups/pdu/ac/cabinet/sensor/other |
| CapacityType | capacity.py | space/power/cooling/weight/network |
| CapacityStatus | capacity.py | normal/warning/critical/full |
| WorkOrderStatus | operation.py | 待处理/已派单/已接单/处理中/已完成/已关闭/已取消 |
| WorkOrderType | operation.py | 故障报修/日常维护/巡检任务/变更请求/其他 |
| WorkOrderPriority | operation.py | 紧急/高/中/低 |
| ApprovalStatus | operation.py | 待审批/已批准/已驳回/已超时/已升级 |
| InspectionStatus | operation.py | 待巡检/巡检中/已完成/已逾期 |
| TimePeriodType | vpp_data.py | peak/valley/flat |
| MappingType | trace.py | direct/aggregate/composite/ml_prediction |
| AggregationType | trace.py | sum/avg/max/min/count/percentile/stddev |
| MLModelType | trace.py | transformer/gnn/rl |
| CalibrationStatus | diagnosis.py | valid/expired/no_metadata/not_calibrated |
| RollbackTriggerType | rollback.py | temp_over_limit/rate_over_predicted/rate_over_limit/ac_fault/sensor_offline/ups_active/humidity_dew_point |

---

## 1. 用户管理 (user.py)

### 1.1 User — 用户表

表名: `users`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| username | String(50) | NO | - | 用户名 (unique) |
| password_hash | String(255) | NO | - | 密码哈希 |
| real_name | String(50) | YES | - | 真实姓名 |
| email | String(100) | YES | - | 邮箱 |
| phone | String(20) | YES | - | 手机号 |
| role | String(20) | YES | "operator" | 角色: admin/operator/viewer |
| department | String(100) | YES | - | 部门 |
| avatar | String(255) | YES | - | 头像URL |
| is_active | Boolean | YES | True | 是否启用 |
| last_login_at | DateTime | YES | - | 最后登录时间 |
| last_login_ip | String(50) | YES | - | 最后登录IP |
| login_count | Integer | YES | 0 | 登录次数 |
| password_changed_at | DateTime | YES | - | 密码最后修改时间 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 1.2 RolePermission — 角色权限表

表名: `role_permissions`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| role | String(20) | NO | - | 角色 |
| permission | String(100) | NO | - | 权限标识 |
| created_at | DateTime | YES | now | 创建时间 |

### 1.3 UserLoginHistory — 用户登录历史

表名: `user_login_history`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| user_id | Integer | NO | - | 用户ID (FK→users.id) |
| login_at | DateTime | YES | now | 登录时间 |
| login_ip | String(50) | YES | - | 登录IP |
| user_agent | String(255) | YES | - | 用户代理 |
| status | String(20) | YES | - | 状态: success/failed |
| fail_reason | String(100) | YES | - | 失败原因 |

### 1.4 UserSession — 用户会话表

表名: `user_sessions`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| user_id | Integer | NO | - | 用户ID (FK→users.id) |
| token_jti | String(64) | NO | - | JWT ID (unique) |
| created_at | DateTime | YES | now | 创建时间 |
| is_active | Boolean | YES | True | 是否活跃 |
### 1.5 UserSite — 用户-站点关联表

表名: `user_sites` | 约束: UniqueConstraint(user_id, site_id)

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| user_id | Integer | NO | - | 用户ID (FK→users.id) |
| site_id | Integer | NO | - | 站点ID (FK→sites.id) |
| created_at | DateTime | YES | now | 创建时间 |

### 1.6 PasswordHistory — 密码历史记录表

表名: `password_history`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| user_id | Integer | NO | - | 用户ID (FK→users.id) |
| password_hash | String(255) | NO | - | 密码哈希 |
| created_at | DateTime | YES | now | 创建时间 |

---

## 2. 设备与点位 (device.py, point.py)

### 2.1 Device — 设备表

表名: `devices` | 索引: ix_devices_type_area(device_type, area_code), ix_devices_status(status), ix_devices_site_id(site_id)

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| device_code | String(50) | NO | - | 设备编码 (unique) |
| device_name | String(100) | NO | - | 设备名称 |
| device_type | String(20) | NO | - | 设备类型: UPS/AC/PDU/TH/DOOR/SMOKE/WATER |
| area_code | String(10) | NO | - | 区域代码 |
| manufacturer | String(100) | YES | - | 制造商 |
| model | String(100) | YES | - | 型号 |
| serial_number | String(100) | YES | - | 序列号 |
| install_date | Date | YES | - | 安装日期 |
| status | String(20) | YES | "online" | 状态: online/offline/maintenance/alarm |
| location_x | Float | YES | - | 平面图X坐标 |
| location_y | Float | YES | - | 平面图Y坐标 |
| description | Text | YES | - | 描述 |
| site_id | Integer | YES | - | 所属站点ID (FK→sites.id) |
| is_enabled | Boolean | YES | True | 是否启用 |
| is_demo | Boolean | NO | False | 是否为演示数据 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |
### 2.2 Point — 点位表

表名: `points` | 索引: ix_points_device_id, ix_points_type_area(point_type, area_code), ix_points_enabled(is_enabled)

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| point_code | String(50) | NO | - | 点位编码 (unique) |
| point_name | String(100) | NO | - | 点位名称 |
| point_type | String(20) | NO | - | 点位类型: AI/DI/AO/DO/measurement/control/status/alarm |
| device_id | Integer | YES | - | 关联采集设备ID (FK→devices.id) |
| device_type | String(20) | YES | - | 设备类型: TH/UPS/PDU/AC/DOOR/SMOKE/WATER/IR/FAN/LIGHT |
| area_code | String(10) | YES | - | 区域代码: A1/A2/B1/B2 |
| unit | String(20) | YES | - | 单位 |
| data_type | String(10) | YES | "float" | 数据类型: float/int/bool/string |
| min_range | Float | YES | - | 量程最小值 |
| max_range | Float | YES | - | 量程最大值 |
| precision | Integer | YES | 2 | 小数位数 |
| collect_interval | Integer | YES | 10 | 采集周期(秒) |
| store_interval | Integer | YES | 60 | 存储周期(秒) |
| is_enabled | Boolean | YES | True | 是否启用 |
| is_virtual | Boolean | YES | False | 是否虚拟点位 |
| calc_formula | Text | YES | - | 计算公式(虚拟点) |
| description | Text | YES | - | 描述 |
| sort_order | Integer | YES | 0 | 排序 |
| energy_device_id | Integer | YES | - | 关联用能设备ID |
| register_address | String(50) | YES | - | 寄存器地址 |
| function_code | Integer | YES | - | Modbus功能码 |
| scale_factor | Float | YES | 1.0 | 比例因子 |
| offset | Float | YES | 0.0 | 偏移量 |
| source | String(20) | YES | "manual" | 数据来源: demo/mqtt/bridge/manual |
| is_demo | Boolean | NO | False | 是否为演示数据 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 2.3 PointRealtime — 点位实时值表

表名: `point_realtime`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| point_id | Integer | NO | - | 点位ID (PK, FK→points.id) |
| raw_value | Float | YES | - | 原始值 |
| value | Float | YES | - | 工程值 |
| value_text | String(50) | YES | - | 状态文本 |
| quality | Integer | YES | 0 | 数据质量: 0=好 1=不确定 2=坏 |
| status | String(20) | YES | "normal" | 状态: normal/alarm/offline |
| alarm_level | String(20) | YES | - | 当前告警级别 |
| source | String(20) | YES | "unknown" | 数据来源: demo/mqtt/bridge/unknown |
| change_count | Integer | YES | 0 | 变化次数 |
| last_change_at | DateTime | YES | - | 最后变化时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 2.4 PointGroup — 点位分组表

表名: `point_groups`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| group_name | String(100) | NO | - | 分组名称 |
| group_type | String(20) | YES | - | 分组类型: area/device_type/custom |
| parent_id | Integer | YES | - | 父分组ID |
| sort_order | Integer | YES | 0 | 排序 |
| created_at | DateTime | YES | now | 创建时间 |
### 2.5 PointGroupMember — 点位分组关系表

表名: `point_group_members`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| group_id | Integer | NO | - | 分组ID (PK, FK→point_groups.id) |
| point_id | Integer | NO | - | 点位ID (PK, FK→points.id) |

---

## 3. 告警 (alarm.py)

### 3.1 AlarmThreshold — 告警阈值配置表

表名: `alarm_thresholds` | 索引: ix_alarm_thresholds_point_id

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| point_id | Integer | NO | - | 点位ID (FK→points.id) |
| threshold_type | String(20) | NO | - | 阈值类型: high_high/high/low/low_low/equal/change |
| threshold_value | Float | YES | - | 阈值 |
| alarm_level | String(20) | YES | "minor" | 告警级别: critical/major/minor/info |
| alarm_message | String(200) | YES | - | 告警消息 |
| delay_seconds | Integer | YES | 0 | 延迟触发(秒) |
| dead_band | Float | YES | 0 | 死区(回差) |
| is_enabled | Boolean | YES | True | 是否启用 |
| priority | Integer | YES | 0 | 优先级 |
| is_demo | Boolean | NO | False | 是否为演示数据 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 3.2 Alarm — 告警记录表

表名: `alarms` | 索引: ix_alarms_status_level(status, alarm_level), ix_alarms_point_id, ix_alarms_created_at

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| alarm_no | String(50) | NO | - | 告警编号 (unique) |
| point_id | Integer | NO | - | 点位ID (FK→points.id) |
| threshold_id | Integer | YES | - | 阈值配置ID (FK→alarm_thresholds.id) |
| alarm_level | String(20) | NO | - | 告警级别 |
| alarm_type | String(20) | YES | - | 告警类型: threshold/communication/system |
| alarm_message | Text | NO | - | 告警消息 |
| trigger_value | Float | YES | - | 触发值 |
| threshold_value | Float | YES | - | 阈值 |
| status | String(20) | YES | "active" | 状态: active/acknowledged/resolved/ignored |
| acknowledged_by | Integer | YES | - | 确认人 (FK→users.id) |
| acknowledged_at | DateTime | YES | - | 确认时间 |
| ack_remark | Text | YES | - | 确认备注 |
| resolved_by | Integer | YES | - | 解决人 (FK→users.id) |
| resolved_at | DateTime | YES | - | 解决时间 |
| resolve_remark | Text | YES | - | 解决备注 |
| resolve_type | String(20) | YES | - | 解决类型: manual/auto/timeout |
| duration_seconds | Integer | YES | - | 持续时间(秒) |
| process_remark | Text | YES | - | 处理备注 |
| processed_by | Integer | YES | - | 处理人 (FK→users.id) |
| processed_at | DateTime | YES | - | 处理时间 |
| is_notified | Boolean | YES | False | 是否已通知 |
| notify_count | Integer | YES | 0 | 通知次数 |
| escalation_count | Integer | YES | 0 | 升级次数 |
| escalated_from | String(20) | YES | - | 升级前告警级别 |
| escalation_remark | Text | YES | - | 升级备注 |
| last_escalated_at | DateTime | YES | - | 最后升级时间 |
| data_source | String(20) | YES | "unknown" | 触发数据来源: demo/mqtt/bridge/unknown |
| created_at | DateTime | YES | now | 创建时间 |

### 3.3 AlarmRule — 告警规则表（复合告警）

表名: `alarm_rules`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| rule_name | String(100) | NO | - | 规则名称 |
| rule_type | String(20) | YES | - | 规则类型: and/or/sequence |
| condition_expr | Text | YES | - | 条件表达式 |
| alarm_level | String(20) | YES | - | 告警级别 |
| alarm_message | String(200) | YES | - | 告警消息 |
| is_enabled | Boolean | YES | True | 是否启用 |
| created_at | DateTime | YES | now | 创建时间 |

### 3.4 AlarmShield — 告警屏蔽表

表名: `alarm_shields`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| point_id | Integer | YES | - | 点位ID (FK→points.id, 空=全局) |
| alarm_level | String(20) | YES | - | 屏蔽级别(空=全部) |
| start_time | DateTime | NO | - | 开始时间 |
| end_time | DateTime | NO | - | 结束时间 |
| reason | Text | YES | - | 屏蔽原因 |
| created_by | Integer | YES | - | 创建人 (FK→users.id) |
| created_at | DateTime | YES | now | 创建时间 |

### 3.5 AlarmDailyStats — 告警统计表（按天聚合）

表名: `alarm_daily_stats`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| stat_date | Date | NO | - | 统计日期 |
| point_id | Integer | YES | - | 点位ID |
| alarm_level | String(20) | YES | - | 告警级别 |
| total_count | Integer | YES | 0 | 总数 |
| ack_count | Integer | YES | 0 | 已确认数 |
| resolve_count | Integer | YES | 0 | 已解决数 |
| avg_duration_seconds | Integer | YES | - | 平均持续时间 |
| max_duration_seconds | Integer | YES | - | 最大持续时间 |
| created_at | DateTime | YES | now | 创建时间 |
### 3.6 AlarmEscalation — 告警升级规则表

表名: `alarm_escalations`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| rule_name | String(100) | NO | - | 规则名称 |
| source_level | String(20) | NO | - | 源告警级别 |
| timeout_minutes | Integer | NO | - | 超时时间(分钟) |
| target_level | String(20) | NO | - | 升级后告警级别 |
| notify_user_ids | String(500) | YES | "" | 通知对象(逗号分隔用户ID) |
| is_enabled | Boolean | YES | True | 是否启用 |
| description | Text | YES | - | 规则描述 |
| escalation_chain | Text | YES | - | 升级链JSON(节点数组) |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

---

## 4. 历史与日志 (history.py, log.py)

### 4.1 PointHistory — 点位历史数据表

表名: `point_history` | 索引: idx_history_point_time(point_id, recorded_at), idx_history_time(recorded_at)

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| point_id | Integer | NO | - | 点位ID (FK→points.id) |
| value | Float | NO | - | 数值 |
| quality | Integer | YES | 0 | 数据质量: 0=好 1=不确定 2=坏 |
| min_value | Float | YES | - | 周期内最小值 |
| max_value | Float | YES | - | 周期内最大值 |
| avg_value | Float | YES | - | 周期内平均值 |
| source | String(20) | YES | "unknown" | 数据来源: demo/mqtt/bridge/demo_backfill/unknown |
| recorded_at | DateTime | YES | now | 记录时间 |

### 4.2 PointHistoryArchive — 历史数据归档表

表名: `point_history_archive`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| point_id | Integer | NO | - | 点位ID (FK→points.id) |
| archive_type | String(20) | YES | - | 归档类型: hourly/daily/monthly |
| value_min | Float | YES | - | 最小值 |
| value_max | Float | YES | - | 最大值 |
| value_avg | Float | YES | - | 平均值 |
| value_sum | Float | YES | - | 累计值 |
| sample_count | Integer | YES | - | 采样数量 |
| recorded_at | DateTime | YES | - | 记录时间 |
| created_at | DateTime | YES | now | 创建时间 |
### 4.3 PointChangeLog — 点位变化记录表（DI点位）

表名: `point_change_log`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| point_id | Integer | NO | - | 点位ID (FK→points.id) |
| old_value | Float | YES | - | 旧值 |
| new_value | Float | YES | - | 新值 |
| change_type | String(20) | YES | - | 变化类型: normal/alarm/recover |
| changed_at | DateTime | YES | now | 变化时间 |

### 4.4 OperationLog — 操作日志表

表名: `operation_logs` | 索引: ix_operation_logs_user_time(user_id, created_at), ix_operation_logs_module(module)

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| user_id | Integer | YES | - | 用户ID (FK→users.id) |
| username | String(50) | YES | - | 用户名 |
| module | String(50) | NO | - | 模块: user/point/alarm/config/report |
| action | String(50) | NO | - | 操作: create/update/delete/query/export |
| target_type | String(50) | YES | - | 目标类型 |
| target_id | Integer | YES | - | 目标ID |
| target_name | String(100) | YES | - | 目标名称 |
| old_value | Text | YES | - | 旧值(JSON) |
| new_value | Text | YES | - | 新值(JSON) |
| ip_address | String(50) | YES | - | IP地址 |
| user_agent | String(255) | YES | - | 用户代理 |
| request_url | String(255) | YES | - | 请求URL |
| request_method | String(10) | YES | - | 请求方法 |
| request_params | Text | YES | - | 请求参数 |
| response_code | Integer | YES | - | 响应码 |
| response_time_ms | Integer | YES | - | 响应时间(毫秒) |
| remark | Text | YES | - | 备注 |
| created_at | DateTime | YES | now | 创建时间 |

### 4.5 SystemLog — 系统日志表

表名: `system_logs` | 索引: ix_system_logs_level_time(log_level, created_at)

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| log_level | String(20) | NO | - | 日志级别: DEBUG/INFO/WARN/ERROR/FATAL |
| module | String(50) | YES | - | 模块名 |
| message | Text | NO | - | 日志消息 |
| exception | Text | YES | - | 异常信息 |
| stack_trace | Text | YES | - | 堆栈跟踪 |
| created_at | DateTime | YES | now | 创建时间 |

### 4.6 CommunicationLog — 通讯日志表

表名: `communication_logs`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| device_id | Integer | YES | - | 设备ID |
| comm_type | String(20) | YES | - | 通讯类型: request/response/error |
| protocol | String(20) | YES | - | 协议: modbus/snmp/mqtt |
| request_data | Text | YES | - | 请求数据 |
| response_data | Text | YES | - | 响应数据 |
| status | String(20) | YES | - | 状态: success/failed/timeout |
| error_message | Text | YES | - | 错误信息 |
| duration_ms | Integer | YES | - | 耗时(毫秒) |
| created_at | DateTime | YES | now | 创建时间 |
---

## 5. 配置 (config.py)

### 5.1 SystemConfig — 系统配置表

表名: `system_configs`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| config_group | String(50) | NO | - | 配置分组 |
| config_key | String(100) | NO | - | 配置键 |
| config_value | Text | YES | - | 配置值 |
| value_type | String(20) | YES | - | 值类型: string/number/boolean/json |
| description | String(200) | YES | - | 描述 |
| is_editable | Boolean | YES | True | 是否可编辑 |
| updated_by | Integer | YES | - | 更新人 (FK→users.id) |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 5.2 Dictionary — 数据字典表

表名: `dictionaries`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| dict_type | String(50) | NO | - | 字典类型 |
| dict_code | String(50) | NO | - | 字典编码 |
| dict_name | String(100) | NO | - | 字典名称 |
| dict_value | String(200) | YES | - | 字典值 |
| sort_order | Integer | YES | 0 | 排序 |
| is_enabled | Boolean | YES | True | 是否启用 |
| remark | Text | YES | - | 备注 |
| created_at | DateTime | YES | now | 创建时间 |

### 5.3 License — 授权许可表

表名: `licenses`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| license_key | String(100) | NO | - | 许可证密钥 (unique) |
| license_type | String(20) | NO | - | 许可类型: basic/standard/enterprise/unlimited |
| max_points | Integer | NO | - | 最大点位数 |
| features | Text | YES | - | 功能列表(JSON) |
| issue_date | Date | YES | - | 发放日期 |
| expire_date | Date | YES | - | 过期日期 |
| hardware_id | String(100) | YES | - | 硬件ID |
| is_active | Boolean | YES | True | 是否激活 |
| activated_at | DateTime | YES | - | 激活时间 |
| created_at | DateTime | YES | now | 创建时间 |
---

## 6. 能源管理 (energy.py)

### 6.1 Transformer — 变压器配置表

表名: `transformers`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| transformer_code | String(50) | NO | - | 变压器编码 (unique) |
| transformer_name | String(100) | NO | - | 变压器名称 |
| rated_capacity | Float | NO | - | 额定容量 kVA |
| voltage_high | Float | YES | 10.0 | 高压侧电压 kV |
| voltage_low | Float | YES | 0.4 | 低压侧电压 kV |
| connection_type | String(20) | YES | "Dyn11" | 接线组别 |
| efficiency | Float | YES | 98.5 | 效率 % |
| no_load_loss | Float | YES | - | 空载损耗 kW |
| load_loss | Float | YES | - | 负载损耗 kW |
| impedance_voltage | Float | YES | - | 阻抗电压 % |
| install_date | Date | YES | - | 安装日期 |
| location | String(100) | YES | - | 安装位置 |
| status | String(20) | YES | "running" | 状态: running/standby/maintenance/fault |
| is_enabled | Boolean | YES | True | 是否启用 |
| declared_demand | Float | YES | - | 申报需量 kW |
| demand_type | String(10) | YES | "kW" | 需量单位: kW/kVA |
| demand_warning_ratio | Float | YES | 0.9 | 需量预警比例 0-1 |
| is_demo | Boolean | NO | False | 是否为演示数据 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

关系: meter_points (→MeterPoint)

### 6.2 MeterPoint — 计量点配置表

表名: `meter_points`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| meter_code | String(50) | NO | - | 计量点编码 (unique) |
| meter_name | String(100) | NO | - | 计量点名称 |
| meter_no | String(50) | YES | - | 电表号 |
| transformer_id | Integer | YES | - | 关联变压器ID (FK→transformers.id) |
| meter_type | String(20) | YES | "main" | 计量类型: main/sub/check |
| measurement_types | JSON | YES | list | 测量类型列表 |
| ct_ratio | String(20) | YES | - | 电流互感器倍率 |
| pt_ratio | String(20) | YES | - | 电压互感器倍率 |
| multiplier | Float | YES | 1.0 | 综合倍率 |
| declared_demand | Float | YES | - | 申报需量 kW/kVA |
| demand_type | String(10) | YES | "kW" | 需量类型 |
| demand_period | Integer | YES | 15 | 需量计算周期 分钟 |
| customer_no | String(50) | YES | - | 供电局户号 |
| customer_name | String(100) | YES | - | 户名 |
| pricing_config_id | Integer | YES | - | 电价配置ID (FK→electricity_pricing.id) |
| status | String(20) | YES | "normal" | 状态 |
| is_enabled | Boolean | YES | True | 是否启用 |
| is_demo | Boolean | NO | False | 是否为演示数据 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |
### 6.3 DistributionPanel — 配电柜/开关柜表

表名: `distribution_panels`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| panel_code | String(50) | NO | - | 配电柜编码 (unique) |
| panel_name | String(100) | NO | - | 配电柜名称 |
| panel_type | String(20) | NO | - | 类型: main/sub/ups_input/ups_output |
| rated_current | Float | YES | - | 额定电流 A |
| rated_voltage | Float | YES | 380 | 额定电压 V |
| parent_panel_id | Integer | YES | - | 上级配电柜ID (FK→distribution_panels.id) |
| transformer_id | Integer | YES | - | 关联变压器ID (FK→transformers.id) |
| meter_point_id | Integer | YES | - | 关联计量点ID (FK→meter_points.id) |
| location | String(100) | YES | - | 安装位置 |
| area_code | String(10) | YES | - | 区域代码 |
| device_id | Integer | YES | - | 关联动环设备ID (FK→devices.id) |
| status | String(20) | YES | "running" | 状态: running/fault/maintenance |
| is_enabled | Boolean | YES | True | 是否启用 |
| is_demo | Boolean | NO | False | 是否为演示数据 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 6.4 DistributionCircuit — 配电回路表

表名: `distribution_circuits`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| circuit_code | String(50) | NO | - | 回路编码 (unique) |
| circuit_name | String(100) | NO | - | 回路名称 |
| panel_id | Integer | NO | - | 所属配电柜ID (FK→distribution_panels.id) |
| rated_current | Float | YES | - | 额定电流 A |
| breaker_type | String(50) | YES | - | 断路器型号 |
| breaker_rating | Float | YES | - | 断路器额定值 A |
| load_type | String(20) | YES | - | 负载类型: ups/hvac/it_equipment/lighting/general/emergency |
| is_shiftable | Boolean | YES | False | 是否可转移负荷 |
| shift_priority | Integer | YES | 99 | 转移优先级 (1最高) |
| min_runtime_hours | Float | YES | - | 最小运行时长要求 小时 |
| is_enabled | Boolean | YES | True | 是否启用 |
| is_demo | Boolean | NO | False | 是否为演示数据 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 6.5 PowerCurveData — 功率曲线数据表

表名: `power_curve_data` (15分钟粒度)

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| meter_point_id | Integer | YES | - | 计量点ID (FK→meter_points.id) |
| device_id | Integer | YES | - | 设备ID (FK→power_devices.id) |
| timestamp | DateTime | NO | - | 时间戳 |
| active_power | Float | YES | - | 有功功率 kW |
| reactive_power | Float | YES | - | 无功功率 kVar |
| apparent_power | Float | YES | - | 视在功率 kVA |
| power_factor | Float | YES | - | 功率因数 |
| cumulative_energy | Float | YES | - | 累计电量 kWh |
| incremental_energy | Float | YES | - | 增量电量 kWh |
| demand_15min | Float | YES | - | 15分钟需量 kW |
| demand_rolling | Float | YES | - | 滑动窗口需量 kW |
| time_period | String(10) | YES | - | 时段: sharp/peak/flat/valley/deep_valley |
| created_at | DateTime | YES | now | 创建时间 |
### 6.6 DemandHistory — 需量历史记录表（月度）

表名: `demand_history`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| meter_point_id | Integer | NO | - | 计量点ID (FK→meter_points.id) |
| stat_year | Integer | NO | - | 统计年份 |
| stat_month | Integer | NO | - | 统计月份 |
| declared_demand | Float | YES | - | 申报需量 kW |
| max_demand | Float | YES | - | 当月最大需量 kW |
| avg_demand | Float | YES | - | 当月平均需量 kW |
| demand_95th | Float | YES | - | 95%分位数需量 kW |
| max_demand_time | DateTime | YES | - | 最大需量发生时间 |
| over_declared_times | Integer | YES | 0 | 超申报次数 |
| over_declared_max | Float | YES | - | 超申报最大值 kW |
| demand_cost | Float | YES | - | 需量电费 元 |
| over_demand_penalty | Float | YES | 0 | 超需量罚款 元 |
| created_at | DateTime | YES | now | 创建时间 |

### 6.7 OverDemandEvent — 需量超限事件表

表名: `over_demand_events`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| meter_point_id | Integer | NO | - | 计量点ID (FK→meter_points.id) |
| event_time | DateTime | NO | - | 事件时间 |
| demand_value | Float | NO | - | 需量值 kW |
| declared_demand | Float | NO | - | 申报需量 kW |
| over_amount | Float | NO | - | 超出量 kW |
| duration_minutes | Integer | YES | - | 持续时间 分钟 |
| contributing_devices | JSON | YES | - | 贡献设备列表 |
| is_processed | Boolean | YES | False | 是否已处理 |
| process_note | Text | YES | - | 处理备注 |
| created_at | DateTime | YES | now | 创建时间 |

### 6.8 DeviceLoadProfile — 设备负荷曲线配置表

表名: `device_load_profiles`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| device_id | Integer | NO | - | 设备ID (FK→power_devices.id, unique) |
| profile_type | String(20) | YES | "constant" | 类型: constant/variable/scheduled/demand_response |
| hourly_load_factors | JSON | YES | - | 每小时负载系数 [0-1], 长度24 |
| weekday_factor | Float | YES | 1.0 | 工作日系数 |
| weekend_factor | Float | YES | 0.8 | 周末系数 |
| summer_factor | Float | YES | 1.2 | 夏季系数 |
| winter_factor | Float | YES | 1.0 | 冬季系数 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |
### 6.9 DeviceShiftConfig — 设备负荷转移配置表

表名: `device_shift_configs`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| device_id | Integer | NO | - | 设备ID (FK→power_devices.id, unique) |
| is_shiftable | Boolean | YES | False | 是否可转移 |
| shiftable_power_ratio | Float | YES | 0 | 可转移功率比例 0-1 |
| is_critical | Boolean | YES | False | 是否关键负荷 |
| allowed_shift_hours | JSON | YES | - | 允许转移的时段 [0-23] |
| forbidden_shift_hours | JSON | YES | - | 禁止转移的时段 [0-23] |
| min_continuous_runtime | Float | YES | - | 最小连续运行时间 小时 |
| max_shift_duration | Float | YES | - | 最大转移持续时间 小时 |
| min_power | Float | YES | - | 最低运行功率 kW |
| max_ramp_rate | Float | YES | - | 最大爬坡速率 kW/min |
| shift_notice_time | Integer | YES | 30 | 转移提前通知时间 分钟 |
| requires_manual_approval | Boolean | YES | True | 是否需要人工确认 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 6.10 PowerDevice — 用电设备表

表名: `power_devices`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| device_code | String(50) | NO | - | 设备编码 (unique) |
| device_name | String(100) | NO | - | 设备名称 |
| device_type | String(20) | NO | - | 设备类型: UPS/HVAC/IT_SERVER/IT_STORAGE/LIGHTING/PUMP/OTHER |
| rated_power | Float | YES | - | 额定功率 kW |
| rated_voltage | Float | YES | - | 额定电压 V |
| rated_current | Float | YES | - | 额定电流 A |
| power_factor | Float | YES | 0.9 | 额定功率因数 |
| efficiency | Float | YES | 95 | 设备效率 % |
| phase_type | String(10) | YES | "3P" | 相位类型: 1P/3P |
| parent_device_id | Integer | YES | - | 上级设备ID (FK→power_devices.id) |
| circuit_id | Integer | YES | - | 所属回路ID (FK→distribution_circuits.id) |
| circuit_no | String(20) | YES | - | 回路编号 |
| redundancy_type | String(10) | YES | - | 冗余类型: N+1/2N/NULL |
| redundancy_group_id | String(50) | YES | - | 冗余组标识 |
| monitor_device_id | Integer | YES | - | 关联动环设备ID (FK→devices.id) |
| power_point_id | Integer | YES | - | 有功功率点位ID (FK→points.id) |
| energy_point_id | Integer | YES | - | 累计电量点位ID (FK→points.id) |
| voltage_point_id | Integer | YES | - | 电压点位ID (FK→points.id) |
| current_point_id | Integer | YES | - | 电流点位ID (FK→points.id) |
| pf_point_id | Integer | YES | - | 功率因数点位ID (FK→points.id) |
| is_metered | Boolean | YES | True | 是否计量 |
| is_it_load | Boolean | YES | False | 是否IT负载(用于PUE计算) |
| is_critical | Boolean | YES | False | 是否关键负荷 |
| avg_load_rate | Float | YES | - | 平均负载率 % |
| peak_load_rate | Float | YES | - | 峰值负载率 % |
| daily_energy | Float | YES | - | 日均用电量 kWh |
| area_code | String(10) | YES | - | 区域代码 |
| description | Text | YES | - | 描述 |
| is_enabled | Boolean | YES | True | 是否启用 |
| is_demo | Boolean | NO | False | 是否为演示数据 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

关系: circuit(→DistributionCircuit), load_profile(→DeviceLoadProfile), shift_config(→DeviceShiftConfig)
### 6.11 EnergyHourly — 小时能耗表

表名: `energy_hourly`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| device_id | Integer | NO | - | 设备ID (FK→power_devices.id) |
| stat_time | DateTime | NO | - | 统计时间(整点) |
| total_energy | Float | YES | 0 | 总电量 kWh |
| avg_power | Float | YES | 0 | 平均功率 kW |
| max_power | Float | YES | 0 | 最大功率 kW |
| min_power | Float | YES | 0 | 最小功率 kW |
| avg_voltage | Float | YES | - | 平均电压 V |
| avg_current | Float | YES | - | 平均电流 A |
| avg_power_factor | Float | YES | - | 平均功率因数 |
| created_at | DateTime | YES | now | 创建时间 |

### 6.12 EnergyDaily — 日能耗表

表名: `energy_daily`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| device_id | Integer | NO | - | 设备ID (FK→power_devices.id) |
| stat_date | Date | NO | - | 统计日期 |
| total_energy | Float | YES | 0 | 总电量 kWh |
| peak_energy | Float | YES | 0 | 峰时电量 kWh |
| normal_energy | Float | YES | 0 | 平时电量 kWh |
| valley_energy | Float | YES | 0 | 谷时电量 kWh |
| max_power | Float | YES | 0 | 最大功率 kW |
| avg_power | Float | YES | 0 | 平均功率 kW |
| max_power_time | DateTime | YES | - | 最大功率时间 |
| energy_cost | Float | YES | 0 | 电费 元 |
| pue | Float | YES | - | 当日PUE |
| created_at | DateTime | YES | now | 创建时间 |

### 6.13 EnergyMonthly — 月能耗表

表名: `energy_monthly`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| device_id | Integer | NO | - | 设备ID (FK→power_devices.id) |
| stat_year | Integer | NO | - | 统计年份 |
| stat_month | Integer | NO | - | 统计月份 |
| total_energy | Float | YES | 0 | 总电量 kWh |
| peak_energy | Float | YES | 0 | 峰时电量 kWh |
| normal_energy | Float | YES | 0 | 平时电量 kWh |
| valley_energy | Float | YES | 0 | 谷时电量 kWh |
| max_power | Float | YES | 0 | 最大功率 kW |
| avg_power | Float | YES | 0 | 平均功率 kW |
| max_power_date | Date | YES | - | 最大功率日期 |
| total_cost | Float | YES | 0 | 总电费 元 |
| peak_cost | Float | YES | 0 | 峰时电费 元 |
| normal_cost | Float | YES | 0 | 平时电费 元 |
| valley_cost | Float | YES | 0 | 谷时电费 元 |
| avg_pue | Float | YES | - | 月平均PUE |
| created_at | DateTime | YES | now | 创建时间 |
### 6.14 ElectricityPricing — 电价配置表

表名: `electricity_pricing`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| pricing_name | String(50) | NO | - | 电价名称 |
| period_type | String(10) | NO | - | 时段类型: sharp/peak/flat/valley/deep_valley |
| start_time | String(5) | NO | - | 开始时间 HH:MM |
| end_time | String(5) | NO | - | 结束时间 HH:MM |
| price | Float | NO | - | 电价 元/kWh |
| effective_date | Date | NO | - | 生效日期 |
| expire_date | Date | YES | - | 失效日期 |
| is_enabled | Boolean | YES | True | 是否启用 |
| data_source | String(50) | YES | - | 数据来源: seed/demo/real |
| is_demo | Boolean | NO | False | 是否为演示数据 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 6.15 PricingConfig — 电价全局配置表

表名: `pricing_configs`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| config_name | String(100) | NO | "默认配置" | 配置名称 |
| billing_mode | String(20) | YES | "demand" | 计费方式: demand/capacity |
| demand_price | Float | YES | 38.0 | 需量电价 元/kW·月 |
| declared_demand | Float | YES | - | 申报需量 kW |
| over_demand_multiplier | Float | YES | 2.0 | 超需量加价倍数 |
| capacity_price | Float | YES | 28.0 | 容量电价 元/kVA·月 |
| transformer_capacity | Float | YES | - | 变压器容量 kVA |
| power_factor_baseline | Float | YES | 0.90 | 功率因数基准值 |
| power_factor_rules | JSON | YES | - | 功率因数调整规则 |
| transmission_fee | Float | YES | 0.15 | 输配电费 元/kWh |
| government_fund | Float | YES | 0.05 | 政府性基金 元/kWh |
| auxiliary_fee | Float | YES | 0.02 | 辅助服务费 元/kWh |
| other_fee | Float | YES | 0.0 | 其他附加费 元/kWh |
| effective_date | Date | NO | - | 生效日期 |
| expire_date | Date | YES | - | 失效日期 |
| is_enabled | Boolean | YES | True | 是否启用 |
| description | Text | YES | - | 配置说明 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 6.16 PricingScheme — 电价方案表

表名: `pricing_schemes`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| scheme_name | String(100) | NO | - | 方案名称 |
| description | Text | YES | - | 方案说明 |
| is_active | Boolean | NO | False | 是否激活（全局唯一） |
| effective_date | Date | NO | - | 生效日期 |
| expire_date | Date | YES | - | 失效日期 |
| validation_result | JSON | YES | - | 校验结果缓存 |
| validation_time | DateTime | YES | - | 校验时间 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

关系: pricing_relations(→SchemePricingRelation), audit_logs(→PricingSchemeAuditLog)
### 6.17 SchemePricingRelation — 方案-时段关联表

表名: `scheme_pricing_relations`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| scheme_id | Integer | NO | - | 方案ID (FK→pricing_schemes.id, CASCADE) |
| pricing_id | Integer | NO | - | 时段ID (FK→electricity_pricing.id, CASCADE) |
| created_at | DateTime | YES | now | 创建时间 |

### 6.18 PricingSchemeAuditLog — 电价方案审计日志表

表名: `pricing_scheme_audit_logs`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| scheme_id | Integer | NO | - | 方案ID (FK→pricing_schemes.id, CASCADE) |
| action | String(20) | NO | - | 操作: created/updated/activated/deactivated/deleted |
| user_id | Integer | YES | - | 操作用户ID (FK→users.id) |
| changes | JSON | YES | - | 变更内容 |
| timestamp | DateTime | YES | now | 操作时间 |

### 6.19 EnergySuggestion — 节能建议表

表名: `energy_suggestions`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| rule_id | String(50) | NO | - | 规则ID |
| rule_name | String(100) | YES | - | 规则名称 |
| device_id | Integer | YES | - | 相关设备ID (FK→power_devices.id) |
| trigger_value | Float | YES | - | 触发值 |
| threshold_value | Float | YES | - | 阈值 |
| suggestion | Text | NO | - | 建议内容 |
| priority | String(20) | YES | "medium" | 优先级: high/medium/low/urgent |
| potential_saving | Float | YES | - | 预计节省 kWh/月 |
| potential_cost_saving | Float | YES | - | 预计节省费用 元/月 |
| status | String(20) | YES | "pending" | 状态: pending/accepted/rejected/completed |
| accepted_by | Integer | YES | - | 接受人 (FK→users.id) |
| accepted_at | DateTime | YES | - | 接受时间 |
| completed_at | DateTime | YES | - | 完成时间 |
| actual_saving | Float | YES | - | 实际节省 kWh |
| remark | Text | YES | - | 备注 |
| template_id | String(50) | YES | - | 建议模板ID |
| category | String(30) | YES | - | 建议类别: pue/cost/demand/efficiency/maintenance |
| problem_description | Text | YES | - | 问题描述 |
| analysis_detail | Text | YES | - | 分析详情 |
| implementation_steps | JSON | YES | - | 实施步骤 |
| expected_effect | JSON | YES | - | 预期效果 |
| parameters | JSON | YES | - | 模板参数 |
| related_devices | JSON | YES | - | 相关设备列表 |
| difficulty | String(20) | YES | "medium" | 实施难度: easy/medium/hard |
| payback_period | Integer | YES | - | 投资回收期 天 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |
### 6.20 PUEHistory — PUE历史记录表

表名: `pue_history`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| record_time | DateTime | NO | - | 记录时间 |
| total_power | Float | NO | - | 总功率 kW |
| it_power | Float | NO | - | IT负载功率 kW |
| cooling_power | Float | YES | - | 制冷功率 kW |
| ups_loss | Float | YES | - | UPS损耗 kW |
| lighting_power | Float | YES | - | 照明功率 kW |
| other_power | Float | YES | - | 其他功率 kW |
| pue | Float | NO | - | PUE值 |
| created_at | DateTime | YES | now | 创建时间 |

### 6.21 LoadRegulationConfig — 负荷调节配置表

表名: `load_regulation_configs`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| device_id | Integer | NO | - | 关联用电设备ID (FK→power_devices.id) |
| regulation_type | String(20) | NO | - | 调节类型: temperature/brightness/mode/load |
| min_value | Float | NO | - | 最小可调值 |
| max_value | Float | NO | - | 最大可调值 |
| current_value | Float | YES | - | 当前值 |
| default_value | Float | YES | - | 默认值 |
| step_size | Float | YES | 1.0 | 调节步长 |
| unit | String(10) | YES | - | 单位: ℃/%/mode |
| power_factor | Float | YES | - | 功率系数 |
| base_power | Float | YES | - | 基准功率 kW |
| power_curve | JSON | YES | - | 功率曲线 |
| priority | Integer | YES | 5 | 调节优先级 1-10 |
| comfort_impact | String(20) | YES | "low" | 舒适度影响 |
| performance_impact | String(20) | YES | "none" | 性能影响 |
| is_enabled | Boolean | YES | True | 是否启用 |
| is_auto | Boolean | YES | False | 是否自动调节 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 6.22 RegulationHistory — 调节历史记录表

表名: `regulation_history`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| config_id | Integer | NO | - | 调节配置ID (FK→load_regulation_configs.id) |
| device_id | Integer | NO | - | 设备ID (FK→power_devices.id) |
| regulation_type | String(20) | NO | - | 调节类型 |
| old_value | Float | YES | - | 调节前值 |
| new_value | Float | YES | - | 调节后值 |
| power_before | Float | YES | - | 调节前功率 kW |
| power_after | Float | YES | - | 调节后功率 kW |
| power_saved | Float | YES | - | 节省功率 kW |
| trigger_reason | String(50) | YES | - | 触发原因: manual/auto/demand_response/schedule |
| trigger_detail | Text | YES | - | 触发详情 |
| status | String(20) | YES | "pending" | 状态: pending/executing/completed/failed/reverted |
| executed_at | DateTime | YES | - | 执行时间 |
| reverted_at | DateTime | YES | - | 恢复时间 |
| operator_id | Integer | YES | - | 操作人ID (FK→users.id) |
| remark | Text | YES | - | 备注 |
| created_at | DateTime | YES | now | 创建时间 |
### 6.23 DemandAnalysisRecord — 需量分析记录表

表名: `demand_analysis_records`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| meter_point_id | Integer | NO | - | 计量点ID (FK→meter_points.id) |
| analysis_date | Date | NO | - | 分析日期 |
| max_demand | Float | YES | - | 最大需量 kW |
| max_demand_time | DateTime | YES | - | 最大需量发生时间 |
| avg_demand | Float | YES | - | 平均需量 kW |
| min_demand | Float | YES | - | 最小需量 kW |
| demand_95th | Float | YES | - | 95%分位数需量 kW |
| declared_demand | Float | YES | - | 申报需量 kW |
| utilization_rate | Float | YES | - | 需量利用率 % |
| over_demand_count | Integer | YES | 0 | 超需量次数 |
| over_demand_max | Float | YES | - | 超需量最大值 kW |
| over_demand_risk | Float | YES | - | 超需量风险评分 0-100 |
| risk_level | String(20) | YES | - | 风险等级: low/medium/high/critical |
| optimization_potential | Float | YES | - | 优化潜力 kW |
| recommended_demand | Float | YES | - | 建议申报需量 kW |
| potential_saving | Float | YES | - | 潜在节省 元/月 |
| recommended_actions | JSON | YES | - | 推荐措施列表 |
| analysis_type | String(20) | YES | "daily" | 分析类型: daily/monthly/custom |
| created_at | DateTime | YES | now | 创建时间 |

### 6.24 Demand15MinData — 15分钟需量数据表

表名: `demand_15min_data`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| meter_point_id | Integer | NO | - | 计量点ID (FK→meter_points.id) |
| timestamp | DateTime | NO | - | 时间戳(15分钟整点) |
| average_power | Float | NO | - | 15分钟平均功率 kW |
| max_power | Float | YES | - | 15分钟内最大功率 kW |
| min_power | Float | YES | - | 15分钟内最小功率 kW |
| rolling_demand | Float | YES | - | 滑动窗口需量 kW |
| declared_demand | Float | YES | - | 申报需量 kW |
| demand_ratio | Float | YES | - | 需量占比 % |
| is_peak_period | Boolean | YES | False | 是否峰时 |
| time_period | String(10) | YES | - | 时段: sharp/peak/flat/valley/deep_valley |
| is_max_of_day | Boolean | YES | False | 是否当日最大需量 |
| is_max_of_month | Boolean | YES | False | 是否当月最大需量 |
| is_over_declared | Boolean | YES | False | 是否超申报需量 |
| recorded_at | DateTime | YES | now | 记录时间 |

### 6.25 EnergySavingProposal — 节能方案表

表名: `energy_saving_proposals`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| proposal_code | String(50) | NO | - | 方案编号 (unique) |
| proposal_type | String(10) | NO | - | 方案类型: A(无需投资)/B(需要投资) |
| template_id | String(50) | NO | - | 模板ID: A1/A2/A3/A4/A5/B1 |
| template_name | String(200) | NO | - | 模板名称 |
| total_benefit | Numeric(10,2) | YES | - | 总收益 万元/年 |
| total_investment | Numeric(10,2) | YES | 0 | 总投资 万元 |
| current_situation | JSON | YES | - | 当前状况数据 |
| analysis_start_date | Date | YES | - | 分析起始日期 |
| analysis_end_date | Date | YES | - | 分析结束日期 |
| trace_summary | JSON | YES | - | 追溯汇总信息 (专利S1) |
| status | String(20) | YES | "pending" | 状态: pending/accepted/rejected/executing/completed |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

关系: measures(→ProposalMeasure)
### 6.26 ProposalMeasure — 方案措施表

表名: `proposal_measures`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| proposal_id | Integer | NO | - | 方案ID (FK→energy_saving_proposals.id, CASCADE) |
| measure_code | String(50) | NO | - | 措施编号 |
| regulation_object | String(200) | NO | - | 调节对象 |
| regulation_description | Text | YES | - | 调节说明 |
| current_state | JSON | YES | - | 当前状态数据 |
| target_state | JSON | YES | - | 目标状态数据 |
| calculation_formula | Text | YES | - | 计算公式和步骤 |
| calculation_basis | Text | YES | - | 计算依据 |
| annual_benefit | Numeric(10,2) | YES | - | 年收益 万元/年 |
| investment | Numeric(10,2) | YES | 0 | 投资 万元 |
| is_selected | Boolean | YES | False | 用户是否选择该措施 |
| execution_status | String(20) | YES | "pending" | 执行状态 |
| trace_data | JSON | YES | - | 数据追溯链信息 (专利S1) |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 6.27 MeasureExecutionLog — 措施执行日志表

表名: `measure_execution_logs`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| measure_id | Integer | NO | - | 措施ID (FK→proposal_measures.id, CASCADE) |
| execution_time | DateTime | NO | now | 执行时间 |
| power_before | Numeric(10,2) | YES | - | 调节前功率 kW |
| power_after | Numeric(10,2) | YES | - | 调节后功率 kW |
| power_saved | Numeric(10,2) | YES | - | 实际节省功率 kW |
| expected_power_saved | Numeric(10,2) | YES | - | 预期节省功率 kW |
| result | String(20) | YES | - | 执行结果: success/failed/partial |
| result_message | Text | YES | - | 结果描述 |
| execution_data | JSON | YES | - | 执行详细数据 |
| created_at | DateTime | YES | now | 创建时间 |

### 6.28 MeasureBaseline — 措施基准值表 (专利S4a)

表名: `measure_baselines`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| measure_id | Integer | NO | - | 措施ID (FK→proposal_measures.id, CASCADE) |
| captured_at | DateTime | NO | now | 采集时间 |
| capture_duration | Integer | YES | 60 | 采集时长(分钟) |
| power_avg | Numeric(10,2) | YES | - | 平均功率 kW |
| power_max | Numeric(10,2) | YES | - | 最大功率 kW |
| power_min | Numeric(10,2) | YES | - | 最小功率 kW |
| energy_hourly | Numeric(10,2) | YES | - | 小时能耗 kWh |
| energy_daily | Numeric(12,2) | YES | - | 日能耗 kWh |
| device_params | JSON | YES | - | 设备参数快照 |
| data_source | String(50) | YES | - | 数据来源: realtime/history/simulation |
| device_ids | JSON | YES | - | 关联设备ID列表 |
| point_ids | JSON | YES | - | 关联监测点位ID列表 |
| created_at | DateTime | YES | now | 创建时间 |

---

## 7. 资产管理 (asset.py)

### 7.1 Cabinet — 机柜表

表名: `cabinets`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| cabinet_code | String(50) | NO | - | 机柜编码 (unique) |
| cabinet_name | String(100) | NO | - | 机柜名称 |
| location | String(200) | YES | - | 位置 |
| row_number | String(20) | YES | - | 列号 |
| column_number | String(20) | YES | - | 排号 |
| total_u | Integer | YES | 42 | 总U数 |
| max_power | Float | YES | - | 最大功率 kW |
| max_weight | Float | YES | - | 最大承重 kg |
| row_id | Integer | YES | - | 所属行ID (FK→rows.id) |
| aisle_type | String(10) | YES | - | 通道类型: cold/hot/none |
| grid_x | Integer | YES | - | 网格X坐标 |
| grid_y | Integer | YES | - | 网格Y坐标 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

关系: assets(→Asset), row(→Row)

### 7.2 Asset — 资产表

表名: `assets`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| asset_code | String(50) | NO | - | 资产编码 (unique) |
| asset_name | String(100) | NO | - | 资产名称 |
| asset_type | Enum(AssetType) | NO | - | 资产类型 |
| brand | String(100) | YES | - | 品牌 |
| model | String(100) | YES | - | 型号 |
| serial_number | String(100) | YES | - | 序列号 |
| cabinet_id | Integer | YES | - | 机柜ID (FK→cabinets.id) |
| u_position | Integer | YES | - | U位起始位置 |
| u_height | Integer | YES | - | 占用U数 |
| status | Enum(AssetStatus) | YES | in_stock | 资产状态 |
| purchase_date | Date | YES | - | 采购日期 |
| purchase_price | Float | YES | - | 采购价格 |
| supplier | String(200) | YES | - | 供应商 |
| warranty_start | Date | YES | - | 保修开始日期 |
| warranty_end | Date | YES | - | 保修结束日期 |
| maintenance_vendor | String(200) | YES | - | 维保厂商 |
| owner | String(100) | YES | - | 负责人 |
| department | String(100) | YES | - | 所属部门 |
| specifications | Text | YES | - | 规格参数(JSON格式) |
| remark | Text | YES | - | 备注 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

关系: cabinet(→Cabinet), lifecycle_records(→AssetLifecycle), maintenance_records(→MaintenanceRecord)

### 7.3 AssetLifecycle — 资产生命周期记录表

表名: `asset_lifecycles`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| asset_id | Integer | NO | - | 资产ID (FK→assets.id) |
| action | String(50) | NO | - | 操作类型: purchase/deploy/move/maintain/scrap等 |
| action_date | DateTime | NO | - | 操作日期 |
| operator | String(100) | YES | - | 操作人 |
| from_location | String(200) | YES | - | 原位置 |
| to_location | String(200) | YES | - | 新位置 |
| remark | Text | YES | - | 备注 |
| created_at | DateTime | YES | now | 创建时间 |

关系: asset(→Asset)

### 7.4 MaintenanceRecord — 维护记录表

表名: `maintenance_records`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| asset_id | Integer | NO | - | 资产ID (FK→assets.id) |
| maintenance_type | String(50) | NO | - | 维护类型: routine/repair/upgrade等 |
| start_time | DateTime | NO | - | 开始时间 |
| end_time | DateTime | YES | - | 结束时间 |
| technician | String(100) | YES | - | 维护人员 |
| vendor | String(200) | YES | - | 维护厂商 |
| cost | Float | YES | - | 维护费用 |
| description | Text | YES | - | 维护描述 |
| result | Text | YES | - | 维护结果 |
| created_at | DateTime | YES | now | 创建时间 |

关系: asset(→Asset)

### 7.5 AssetInventory — 资产盘点表

表名: `asset_inventories`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| inventory_code | String(50) | NO | - | 盘点编码 (unique) |
| inventory_date | Date | NO | - | 盘点日期 |
| operator | String(100) | YES | - | 盘点人 |
| status | String(20) | YES | "pending" | 盘点状态: pending/in_progress/completed |
| total_count | Integer | YES | 0 | 总数量 |
| checked_count | Integer | YES | 0 | 已盘点数量 |
| matched_count | Integer | YES | 0 | 匹配数量 |
| unmatched_count | Integer | YES | 0 | 不匹配数量 |
| remark | Text | YES | - | 备注 |
| created_at | DateTime | YES | now | 创建时间 |
| completed_at | DateTime | YES | - | 完成时间 |

关系: items(→AssetInventoryItem)

### 7.6 AssetInventoryItem — 资产盘点明细表

表名: `asset_inventory_items`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| inventory_id | Integer | NO | - | 盘点ID (FK→asset_inventories.id) |
| asset_id | Integer | NO | - | 资产ID (FK→assets.id) |
| expected_location | String(200) | YES | - | 预期位置 |
| actual_location | String(200) | YES | - | 实际位置 |
| is_matched | Boolean | YES | False | 是否匹配 |
| check_time | DateTime | YES | - | 盘点时间 |
| remark | Text | YES | - | 备注 |

关系: inventory(→AssetInventory), asset(→Asset)

---

## 8. 容量管理 (capacity.py)

### 8.1 SpaceCapacity — 空间容量表

表名: `space_capacities`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| name | String(100) | NO | - | 名称 |
| location | String(200) | YES | - | 位置 |
| total_area | Float | YES | - | 总面积(平方米) |
| used_area | Float | YES | - | 已用面积(平方米) |
| total_cabinets | Integer | YES | - | 总机柜数 |
| used_cabinets | Integer | YES | - | 已用机柜数 |
| total_u_positions | Integer | YES | - | 总U位数 |
| used_u_positions | Integer | YES | - | 已用U位数 |
| warning_threshold | Float | YES | 80 | 告警阈值(%) |
| critical_threshold | Float | YES | 95 | 严重告警阈值(%) |
| status | Enum(CapacityStatus) | YES | normal | 容量状态 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 8.2 PowerCapacity — 电力容量表

表名: `power_capacities`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| name | String(100) | NO | - | 名称 |
| location | String(200) | YES | - | 位置 |
| capacity_type | String(50) | YES | - | 容量类型 |
| total_capacity_kva | Float | YES | - | 总容量(kVA) |
| used_capacity_kva | Float | YES | - | 已用容量(kVA) |
| total_capacity_kw | Float | YES | - | 总容量(kW) |
| used_capacity_kw | Float | YES | - | 已用容量(kW) |
| redundancy_mode | String(50) | YES | - | 冗余模式 |
| warning_threshold | Float | YES | 70 | 告警阈值(%) |
| critical_threshold | Float | YES | 85 | 严重告警阈值(%) |
| status | Enum(CapacityStatus) | YES | normal | 容量状态 |
| parent_id | Integer | YES | - | 父级ID (FK→power_capacities.id) |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

关系: parent(→PowerCapacity, 自引用), children(→PowerCapacity)

### 8.3 CoolingCapacity — 制冷容量表

表名: `cooling_capacities`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| name | String(100) | NO | - | 名称 |
| location | String(200) | YES | - | 位置 |
| total_cooling_kw | Float | YES | - | 总制冷量(kW) |
| used_cooling_kw | Float | YES | - | 已用制冷量(kW) |
| target_temperature | Float | YES | 24 | 目标温度(℃) |
| current_temperature | Float | YES | - | 当前温度(℃) |
| humidity_target | Float | YES | 50 | 目标湿度(%) |
| current_humidity | Float | YES | - | 当前湿度(%) |
| warning_threshold | Float | YES | 75 | 告警阈值(%) |
| critical_threshold | Float | YES | 90 | 严重告警阈值(%) |
| status | Enum(CapacityStatus) | YES | normal | 容量状态 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 8.4 WeightCapacity — 承重容量表

表名: `weight_capacities`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| name | String(100) | NO | - | 名称 |
| location | String(200) | YES | - | 位置 |
| capacity_type | String(50) | YES | - | 容量类型 |
| total_weight_kg | Float | YES | - | 总承重(kg) |
| used_weight_kg | Float | YES | - | 已用承重(kg) |
| warning_threshold | Float | YES | 80 | 告警阈值(%) |
| critical_threshold | Float | YES | 95 | 严重告警阈值(%) |
| status | Enum(CapacityStatus) | YES | normal | 容量状态 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 8.5 CapacityPlan — 容量规划表

表名: `capacity_plans`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| name | String(100) | NO | - | 规划名称 |
| description | Text | YES | - | 规划描述 |
| device_count | Integer | YES | - | 设备数量 |
| required_u | Integer | YES | - | 所需U位 |
| required_power_kw | Float | YES | - | 所需电力(kW) |
| required_cooling_kw | Float | YES | - | 所需制冷量(kW) |
| required_weight_kg | Float | YES | - | 所需承重(kg) |
| target_cabinet_id | Integer | YES | - | 目标机柜ID (FK→cabinets.id) |
| is_feasible | Boolean | YES | - | 是否可行 |
| feasibility_notes | Text | YES | - | 可行性说明 |
| created_by | String(100) | YES | - | 创建人 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

关系: target_cabinet(→Cabinet)

### 8.6 CapacityHistory — 容量历史记录表

表名: `capacity_histories`

索引: ix_capacity_history_type_time(capacity_type, recorded_at)

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| capacity_type | Enum(CapacityType) | NO | - | 容量类型 |
| reference_id | Integer | NO | - | 关联ID |
| reference_name | String(100) | YES | - | 关联名称 |
| total_value | Float | YES | - | 总量 |
| used_value | Float | YES | - | 已用量 |
| usage_rate | Float | YES | - | 使用率(%) |
| recorded_at | DateTime | YES | now | 记录时间 |

---

## 9. 运维管理 (operation.py)

### 9.1 WorkOrder — 工单表

表名: `work_orders`

索引: ix_work_orders_status(status), ix_work_orders_assignee(assignee), ix_work_orders_created_at(created_at)

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| order_no | String(50) | NO | - | 工单编号 (unique) |
| title | String(200) | NO | - | 工单标题 |
| description | Text | YES | - | 工单描述 |
| order_type | Enum(WorkOrderType) | YES | 其他 | 工单类型 |
| priority | Enum(WorkOrderPriority) | YES | 中 | 优先级 |
| status | Enum(WorkOrderStatus) | YES | 待处理 | 工单状态 |
| device_id | Integer | YES | - | 关联设备ID |
| device_name | String(100) | YES | - | 设备名称 |
| area_code | String(50) | YES | - | 关联区域编码 |
| alarm_id | Integer | YES | - | 关联告警ID |
| location | String(200) | YES | - | 位置 |
| reporter | String(100) | YES | - | 报修人 |
| reporter_phone | String(50) | YES | - | 报修人电话 |
| assignee | String(100) | YES | - | 处理人 |
| created_at | DateTime | YES | now | 创建时间 |
| assigned_at | DateTime | YES | - | 派单时间 |
| accepted_at | DateTime | YES | - | 接单时间 |
| started_at | DateTime | YES | - | 开始处理时间 |
| completed_at | DateTime | YES | - | 完成时间 |
| closed_at | DateTime | YES | - | 关闭时间 |
| deadline | DateTime | YES | - | 截止时间 |
| solution | Text | YES | - | 解决方案 |
| root_cause | Text | YES | - | 根本原因 |
| remarks | Text | YES | - | 备注 |
| satisfaction | Integer | YES | - | 满意度(1-5) |
| feedback | Text | YES | - | 反馈 |

关系: logs(→WorkOrderLog, cascade=all,delete-orphan)

### 9.2 WorkOrderLog — 工单日志表

表名: `work_order_logs`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| order_id | Integer | NO | - | 工单ID (FK→work_orders.id) |
| action | String(50) | YES | - | 操作类型 |
| content | Text | YES | - | 操作内容 |
| operator | String(100) | YES | - | 操作人 |
| created_at | DateTime | YES | now | 创建时间 |

关系: work_order(→WorkOrder)

### 9.3 InspectionPlan — 巡检计划表

表名: `inspection_plans`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| name | String(100) | NO | - | 计划名称 |
| description | Text | YES | - | 计划描述 |
| frequency | String(50) | YES | - | 巡检频率(daily/weekly/monthly) |
| location | String(200) | YES | - | 巡检位置 |
| check_items | Text | YES | - | 检查项目(JSON字符串) |
| assignee | String(100) | YES | - | 负责人 |
| is_active | Boolean | YES | True | 是否启用 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

关系: tasks(→InspectionTask, cascade=all,delete-orphan)

### 9.4 InspectionTask — 巡检任务表

表名: `inspection_tasks`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| plan_id | Integer | YES | - | 巡检计划ID (FK→inspection_plans.id) |
| task_no | String(50) | NO | - | 任务编号 (unique) |
| status | Enum(InspectionStatus) | YES | 待巡检 | 任务状态 |
| assignee | String(100) | YES | - | 执行人 |
| scheduled_date | DateTime | YES | - | 计划执行日期 |
| started_at | DateTime | YES | - | 开始时间 |
| completed_at | DateTime | YES | - | 完成时间 |
| result | Text | YES | - | 巡检结果(JSON) |
| abnormal_count | Integer | YES | 0 | 异常数量 |
| remarks | Text | YES | - | 备注 |
| created_at | DateTime | YES | now | 创建时间 |

关系: plan(→InspectionPlan)

### 9.5 KnowledgeBase — 知识库表

表名: `knowledge_base`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| title | String(200) | NO | - | 标题 |
| category | String(100) | YES | - | 分类 |
| content | Text | YES | - | 内容 |
| tags | String(500) | YES | - | 标签 |
| view_count | Integer | YES | 0 | 查看次数 |
| is_published | Boolean | YES | False | 是否发布 |
| author | String(100) | YES | - | 作者 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 9.6 AlarmWorkOrderRule — 告警自动创建工单规则表

表名: `alarm_workorder_rules`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| name | String(100) | NO | - | 规则名称 |
| alarm_level | String(20) | NO | - | 告警级别(critical/important) |
| alarm_type | String(20) | YES | - | 告警类型过滤(threshold/communication/system, 空=全部) |
| order_type | Enum(WorkOrderType) | YES | 故障报修 | 工单类型 |
| priority | Enum(WorkOrderPriority) | YES | 高 | 工单优先级 |
| assignee | String(100) | YES | - | 自动派单人 |
| is_enabled | Boolean | YES | True | 是否启用 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

## 10. report

源文件: `backend/app/models/report.py`

### 10.1 ReportTemplate — 报表模板表

表名: `report_templates`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| template_name | String(100) | NO | - | 模板名称 |
| template_type | String(20) | YES | - | 模板类型: daily/weekly/monthly/custom |
| template_config | Text | YES | - | 模板配置(JSON) |
| point_ids | Text | YES | - | 包含的点位ID列表(JSON) |
| is_enabled | Boolean | YES | True | 是否启用 |
| created_by | Integer | YES | - | 创建人 (FK → users.id) |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 10.2 ReportRecord — 报表生成记录表

表名: `report_records`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| template_id | Integer | YES | - | 模板ID (FK → report_templates.id) |
| report_name | String(200) | YES | - | 报表名称 |
| report_type | String(20) | YES | - | 报表类型 |
| start_time | DateTime | YES | - | 开始时间 |
| end_time | DateTime | YES | - | 结束时间 |
| file_path | String(255) | YES | - | 文件路径 |
| file_size | Integer | YES | - | 文件大小 |
| status | String(20) | YES | - | 状态: generating/completed/failed |
| error_message | Text | YES | - | 错误信息 |
| report_data | Text | YES | - | 报表数据(JSON) |
| generated_by | Integer | YES | - | 生成人 (FK → users.id) |
| created_at | DateTime | YES | now | 创建时间 |

### 10.3 ReportSchedule — 报表调度配置表

表名: `report_schedules`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| name | String(100) | NO | - | 调度名称 |
| report_type | String(20) | NO | - | 报表类型: daily/weekly/monthly |
| is_enabled | Boolean | YES | True | 是否启用 |
| last_run_at | DateTime | YES | - | 上次运行时间 |
| next_run_at | DateTime | YES | - | 下次运行时间 |
| created_by | Integer | YES | - | 创建人 (FK → users.id) |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 10.4 DeviceHealthScore — 设备健康度评分表

表名: `device_health_scores`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| device_id | Integer | NO | - | 设备ID (FK → devices.id) |
| device_name | String(100) | YES | - | 设备名称 |
| device_type | String(50) | YES | - | 设备类型 |
| score | Float | NO | 100 | 健康度评分 0-100 |
| health_level | String(20) | NO | "健康" | 健康等级: 健康/关注/预警/危险 |
| alarm_count | Integer | YES | 0 | 近期告警数 |
| maintenance_count | Integer | YES | 0 | 维保记录数 |
| last_maintenance_at | DateTime | YES | - | 最近维保时间 |
| calculated_at | DateTime | YES | now | 计算时间 |

## 11. cooling

源文件: `backend/app/models/cooling.py`

### 11.1 CoolingGroup — 空调群控组

表名: `cooling_groups`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| group_name | String(100) | NO | - | 群控组名称 |
| group_mode | String(20) | YES | "independent" | 模式: independent/linked |
| description | Text | YES | - | 描述 |
| is_demo | Boolean | NO | False | 是否为演示数据 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 11.2 CoolingUnit — 精密空调扩展表

表名: `cooling_units`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| device_id | Integer | NO | - | 关联设备ID (FK → devices.id) |
| unit_type | String(20) | YES | "indoor" | 类型: indoor/outdoor |
| cooling_capacity_kw | Float | YES | - | 制冷量(kW) |
| refrigerant_type | String(20) | YES | - | 制冷剂类型 |
| compressor_count | Integer | YES | 1 | 压缩机数量 |
| fan_count | Integer | YES | 2 | 风机数量 |
| group_id | Integer | YES | - | 群控组ID (FK → cooling_groups.id) |
| description | Text | YES | - | 描述 |
| is_demo | Boolean | NO | False | 是否为演示数据 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 11.3 ColdAisle — 冷通道（天窗系统）

表名: `cold_aisles`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| device_id | Integer | NO | - | 关联设备ID (FK → devices.id) |
| aisle_code | String(50) | YES | - | 通道编码 |
| aisle_name | String(100) | YES | - | 通道名称 |
| skylight_count | Integer | YES | 2 | 天窗数量 |
| location | String(100) | YES | - | 位置描述 |
| description | Text | YES | - | 描述 |
| is_demo | Boolean | NO | False | 是否为演示数据 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

## 12. power

源文件: `backend/app/models/power.py`

### 12.1 UPSDevice — UPS设备扩展表

表名: `ups_devices`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| device_id | Integer | NO | - | 关联设备ID (FK → devices.id) |
| ups_type | String(20) | YES | "standalone" | UPS类型: standalone/modular |
| rated_capacity | Float | YES | - | 额定容量(kVA) |
| rated_voltage | Float | YES | - | 额定电压(V) |
| phase_count | Integer | YES | 3 | 相数: 1/3 |
| battery_group_count | Integer | YES | 1 | 电池组数量 |
| bypass_enabled | Boolean | YES | True | 旁路是否启用 |
| description | Text | YES | - | 描述 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 12.2 BatteryGroup — 电池组表

表名: `battery_groups`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| ups_device_id | Integer | YES | - | 关联UPS设备ID (FK → ups_devices.id) |
| group_name | String(100) | YES | - | 电池组名称 |
| battery_type | String(20) | YES | "lead_acid" | 电池类型: lead_acid/lithium |
| rated_capacity | Float | YES | - | 额定容量(Ah) |
| rated_voltage | Float | YES | - | 额定电压(V) |
| cell_count | Integer | YES | - | 电芯数量 |
| install_date | Date | YES | - | 安装日期 |
| description | Text | YES | - | 描述 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

## 13. spatial

源文件: `backend/app/models/spatial.py`

### 13.1 Site — 站点表

表名: `sites`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| site_code | String(50) | NO | - | 站点编码 (unique) |
| site_name | String(100) | NO | - | 站点名称 |
| address | String(200) | YES | - | 地址 |
| contact_person | String(50) | YES | - | 联系人 |
| contact_phone | String(20) | YES | - | 联系电话 |
| contact_email | String(100) | YES | - | 联系邮箱 |
| network_config | JSON | YES | - | 网络配置(VPN/专线信息) |
| status | String(20) | YES | "active" | 状态: active/inactive/maintenance |
| description | Text | YES | - | 描述 |
| data_source | String(50) | YES | - | 数据来源: seed/demo/real |
| is_demo | Boolean | NO | False | 是否为演示数据 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

关系: `floors` → Floor (back_populates="site", lazy="selectin")

### 13.2 Floor — 楼层表

表名: `floors`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| floor_code | String(50) | NO | - | 楼层编码 |
| floor_name | String(100) | NO | - | 楼层名称 |
| site_id | Integer | NO | - | 所属站点ID (FK → sites.id) |
| sort_order | Integer | YES | 0 | 排序 |
| data_source | String(50) | YES | - | 数据来源: seed/demo/real |
| is_demo | Boolean | NO | False | 是否为演示数据 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

约束: UniqueConstraint("site_id", "floor_code", name="uq_floor_site_code")

关系: `site` → Site, `rooms` → Room (lazy="selectin")

### 13.3 Room — 房间表

表名: `rooms`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| room_code | String(50) | NO | - | 房间编码 |
| room_name | String(100) | NO | - | 房间名称 |
| floor_id | Integer | NO | - | 所属楼层ID (FK → floors.id) |
| grid_cols | Integer | YES | 20 | 网格列数 |
| grid_rows | Integer | YES | 20 | 网格行数 |
| area_sqm | Float | YES | - | 面积(平方米) |
| description | Text | YES | - | 描述 |
| data_source | String(50) | YES | - | 数据来源: seed/demo/real |
| is_demo | Boolean | NO | False | 是否为演示数据 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

约束: UniqueConstraint("floor_id", "room_code", name="uq_room_floor_code")

关系: `floor` → Floor, `rows` → Row (lazy="selectin")

### 13.4 Row — 行表（机柜排）

表名: `rows`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| row_code | String(50) | NO | - | 行编码 |
| row_name | String(100) | NO | - | 行名称 |
| room_id | Integer | NO | - | 所属房间ID (FK → rooms.id) |
| aisle_type | String(10) | YES | "none" | 通道类型: cold/hot/none |
| sort_order | Integer | YES | 0 | 排序 |
| is_demo | Boolean | NO | False | 是否为演示数据 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

约束: UniqueConstraint("room_id", "row_code", name="uq_row_room_code")

关系: `room` → Room, `cabinets` → Cabinet (lazy="selectin")

### 13.5 LayoutTemplate — 布局模板表

表名: `layout_templates`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| template_code | String(50) | NO | - | 模板编码 (unique) |
| template_name | String(100) | NO | - | 模板名称 |
| description | Text | YES | - | 描述 |
| template_data | Text | YES | - | JSON格式模板数据 |
| created_at | DateTime | YES | now | 创建时间 |

## 14. topology_config

源文件: `backend/app/models/topology_config.py`

### 14.1 PowerPhaseMapping — 机柜→PDU 三相接线映射

表名: `power_phase_mappings`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| cabinet_id | Integer | NO | - | 机柜ID (FK → cabinets.id, CASCADE) |
| pdu_device_id | Integer | NO | - | PDU设备ID (FK → devices.id, CASCADE) |
| phase | String(1) | NO | - | 相位: A/B/C |
| feed_type | String(10) | NO | - | 馈电类型: primary/backup |
| rated_current | Float | YES | - | 额定电流(A) |
| description | Text | YES | - | 描述 |

约束: UniqueConstraint("cabinet_id", "feed_type", name="uq_cabinet_feed_type")

### 14.2 CoolingZone — 制冷区域

表名: `cooling_zones`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| zone_code | String(50) | NO | - | 区域编码 (unique) |
| zone_name | String(100) | NO | - | 区域名称 |
| room_id | Integer | YES | - | 所属房间ID (FK → rooms.id, SET NULL) |
| site_id | Integer | YES | - | 所属站点 (FK → sites.id, SET NULL) |
| design_capacity_kw | Float | YES | - | 设计制冷量(kW) |
| description | Text | YES | - | 描述 |
| area_m2 | Float | YES | - | 冷通道面积 m²，用于计算热容 |
| height_m | Float | YES | 3.0 | 冷通道层高 m |
| thermal_R | Float | YES | - | 热阻标定值 °C/kW，NULL=未标定 |
| thermal_C | Float | YES | - | 热容标定值 kWh/°C（总热容），NULL=未标定 |
| bypass_beta | Float | YES | 0.1 | 气流短路系数 0~0.3 |
| r_calibrated_at | DateTime | YES | - | R/C 最近标定时间 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 14.3 CoolingZoneCabinet — 制冷区域↔机柜关联

表名: `cooling_zone_cabinets`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| zone_id | Integer | NO | - | 制冷区域ID (FK → cooling_zones.id, CASCADE) |
| cabinet_id | Integer | NO | - | 机柜ID (FK → cabinets.id, CASCADE) |

约束: UniqueConstraint("zone_id", "cabinet_id", name="uq_zone_cabinet")

### 14.4 CoolingZoneUnit — 制冷区域↔空调关联

表名: `cooling_zone_units`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| zone_id | Integer | NO | - | 制冷区域ID (FK → cooling_zones.id, CASCADE) |
| cooling_unit_id | Integer | NO | - | 空调ID (FK → cooling_units.id, CASCADE) |
| is_primary | Integer | YES | 1 | 是否主空调: 1=主, 0=备 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

约束: UniqueConstraint("zone_id", "cooling_unit_id", name="uq_zone_cooling_unit")

### 14.5 CabinetTemperatureSensor — 机柜温度传感器配置

表名: `cabinet_temperature_sensors`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| cabinet_id | Integer | NO | - | 机柜ID (FK → cabinets.id, CASCADE) |
| point_id | Integer | YES | - | 温度点位ID (FK → points.id, SET NULL) |
| sensor_location | String(20) | NO | - | 传感器位置: inlet/outlet/ambient |
| temp_warning_threshold | Float | YES | 27.0 | 温度告警阈值(℃) |
| temp_critical_threshold | Float | YES | 32.0 | 温度严重告警阈值(℃) |
| description | Text | YES | - | 描述 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

约束: UniqueConstraint("cabinet_id", "sensor_location", name="uq_cabinet_sensor_location")

### 14.6 CabinetITLoad — 机柜IT负载监控配置

表名: `cabinet_it_loads`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| cabinet_id | Integer | NO | - | 机柜ID (FK → cabinets.id, CASCADE) |
| power_point_id | Integer | YES | - | 功率点位ID (FK → points.id, SET NULL) |
| rated_power_kw | Float | YES | - | 额定功率(kW) |
| design_load_kw | Float | YES | - | 设计负载(kW) |
| description | Text | YES | - | 描述 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

约束: UniqueConstraint("cabinet_id", name="uq_cabinet_it_load")

## 15. linkage

源文件: `backend/app/models/linkage.py`

### 15.1 LinkagePolicy — 联动策略表

表名: `linkage_policies`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| name | String(100) | NO | - | 策略名称 |
| description | Text | YES | - | 策略描述 |
| trigger_type | String(50) | NO | - | 触发类型: alarm.triggered/alarm.resolved等 |
| trigger_condition | JSON | YES | - | 触发条件 |
| priority | String(20) | YES | "normal" | 优先级: fire_signal/critical/normal |
| is_enabled | Boolean | YES | True | 是否启用 |
| is_system | Boolean | YES | False | 是否系统内置策略 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

关系: `actions` → LinkageAction (cascade="all, delete-orphan")

### 15.2 LinkageAction — 联动动作表

表名: `linkage_actions`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| policy_id | Integer | NO | - | 策略ID (FK → linkage_policies.id) |
| action_type | String(50) | NO | - | 动作类型: ALARM_NOTIFY/WEBHOOK等 |
| action_config | JSON | YES | - | 动作配置 |
| sort_order | Integer | YES | 0 | 执行顺序 |
| timeout_seconds | Integer | YES | 3 | 超时时间(秒) |
| retry_count | Integer | YES | 0 | 重试次数 |
| created_at | DateTime | YES | now | 创建时间 |

### 15.3 LinkageExecution — 联动执行记录表

表名: `linkage_executions`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| policy_id | Integer | NO | - | 策略ID (FK → linkage_policies.id) |
| event_id | String(36) | NO | - | 事件ID |
| trigger_source | String(200) | YES | - | 触发来源 |
| trigger_event | JSON | YES | - | 触发事件快照 |
| status | String(20) | YES | "executing" | 状态: executing/completed/partial_failure/failed |
| started_at | DateTime | YES | now | 开始时间 |
| completed_at | DateTime | YES | - | 完成时间 |
| total_duration_ms | Integer | YES | - | 总耗时(毫秒) |

索引: Index("ix_linkage_exec_policy_status", "policy_id", "status"), Index("ix_linkage_exec_started_at", "started_at")

关系: `logs` → LinkageLog (cascade="all, delete-orphan")

### 15.4 LinkageLog — 联动执行日志表

表名: `linkage_logs`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| execution_id | Integer | NO | - | 执行记录ID (FK → linkage_executions.id) |
| action_id | Integer | YES | - | 动作ID |
| action_type | String(50) | YES | - | 动作类型 |
| action_config | JSON | YES | - | 动作配置快照 |
| status | String(20) | NO | - | 状态: success/failed/timeout/skipped |
| error_message | Text | YES | - | 错误信息 |
| started_at | DateTime | YES | - | 开始时间 |
| completed_at | DateTime | YES | - | 完成时间 |
| duration_ms | Integer | YES | - | 耗时(毫秒) |

### 15.5 LinkageRecovery — 联动恢复记录表

表名: `linkage_recoveries`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| execution_id | Integer | NO | - | 关联执行记录ID (FK → linkage_executions.id) |
| operator | String(50) | NO | - | 操作人 |
| mode | String(20) | YES | "auto" | 恢复模式: auto(一键)/manual(逐项) |
| status | String(20) | YES | "executing" | 状态: executing/completed/partial_recovery/failed |
| started_at | DateTime | YES | now | 开始时间 |
| completed_at | DateTime | YES | - | 完成时间 |
| total_duration_ms | Integer | YES | - | 总耗时(毫秒) |

关系: `logs` → LinkageRecoveryLog (cascade="all, delete-orphan")

### 15.6 LinkageRecoveryLog — 联动恢复步骤日志表

表名: `linkage_recovery_logs`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| recovery_id | Integer | NO | - | 恢复记录ID (FK → linkage_recoveries.id) |
| step_order | Integer | YES | 0 | 恢复步骤顺序 |
| action_type | String(50) | YES | - | 动作类型 |
| target_type | String(50) | YES | - | 目标设备类型 |
| recovery_command | String(50) | YES | - | 恢复命令 |
| action_config | JSON | YES | - | 恢复动作配置 |
| status | String(20) | YES | "pending" | 状态: pending/executing/success/failed/skipped |
| error_message | Text | YES | - | 错误信息 |
| started_at | DateTime | YES | - | 开始时间 |
| completed_at | DateTime | YES | - | 完成时间 |
| duration_ms | Integer | YES | - | 耗时(毫秒) |

## 16. diagnosis

源文件: `backend/app/models/diagnosis.py`

枚举: CalibrationStatus (valid/expired/no_metadata/not_calibrated)

### 16.1 DiagnosisRule — 诊断规则表

表名: `diagnosis_rules`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| rule_code | String(50) | NO | - | 规则编码 (unique) |
| name | String(100) | NO | - | 规则名称 |
| description | Text | YES | - | 规则描述 |
| category | String(30) | NO | - | 分类: temperature/humidity/power/communication/security/cooling/environment/composite |
| trigger_condition | JSON | YES | - | 触发条件 |
| diagnosis_logic | JSON | YES | - | 诊断逻辑(含possible_causes) |
| priority | Integer | YES | 0 | 优先级(高优先匹配) |
| is_enabled | Boolean | YES | True | 是否启用 |
| is_system | Boolean | YES | False | 是否系统内置规则 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 16.2 DiagnosisResult — 诊断结果表

表名: `diagnosis_results`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| alarm_id | Integer | YES | - | 告警ID (FK → alarms.id) |
| alarm_no | String(50) | YES | - | 告警编号(冗余) |
| rule_id | Integer | YES | - | 匹配规则ID (FK → diagnosis_rules.id) |
| rule_code | String(50) | YES | - | 规则编码(冗余) |
| device_type | String(20) | YES | - | 设备类型 |
| zone | String(10) | YES | - | 区域 |
| causes | JSON | YES | - | 诊断原因列表 |
| diagnosis_time_ms | Integer | YES | 0 | 诊断耗时(毫秒) |
| created_at | DateTime | YES | now | 创建时间 |
| device_id | Integer | YES | - | 设备ID (index) |
| diagnosis_level | String(10) | YES | - | 诊断级别 |
| matched | Boolean | YES | 0 | 是否匹配规则 |
| conclusion | Text | YES | - | 诊断结论 |
| confidence | Float | YES | - | 置信度 |
| suggested_actions | JSON | YES | - | 建议操作 |
| evidence | JSON | YES | - | 证据数据 |
| inference_time_ms | Integer | YES | - | 推理耗时(毫秒) |
| error_message | Text | YES | - | 错误信息 |
| session_id | Integer | YES | - | 诊断会话ID (FK → diagnosis_sessions.id) |
| root_cause | String(500) | YES | - | 根因描述 |
| reasoning_path | JSON | YES | - | 推理路径 |
| fault_tree_version | String(50) | YES | - | 故障树版本号 |
| fault_tree_version_id | Integer | YES | - | 故障树版本ID (FK → fault_tree_versions.id) |

### 16.3 DiagnosisSession — 诊断会话表

表名: `diagnosis_sessions`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| trigger_alarm_id | Integer | YES | - | 触发告警ID (FK → alarms.id) |
| device_id | Integer | YES | - | 设备ID (index) |
| engine_level | String(5) | NO | - | 推理级别: L1/L2/L3 |
| status | String(20) | NO | "success" | 会话状态: success/timeout/error/degraded |
| push_status | String(20) | NO | "skipped" | 推送状态: pushed/failed/skipped |
| max_confidence | Float | YES | - | 最高置信度(冗余) |
| start_time | DateTime | NO | - | 推理开始时间 |
| end_time | DateTime | YES | - | 推理结束时间 |
| inference_time_ms | Integer | YES | 0 | 推理耗时(毫秒) |
| created_at | DateTime | YES | now | 创建时间 |

### 16.4 DiagnosisAuditLog — 诊断审计日志表

表名: `diagnosis_audit_logs`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| session_id | Integer | NO | - | 会话ID (FK → diagnosis_sessions.id) |
| input_data | JSON | YES | - | 推理输入数据 |
| output_data | JSON | YES | - | 推理输出数据 |
| engine_level | String(5) | NO | - | 推理级别 |
| inference_time_ms | Integer | YES | 0 | 推理耗时(毫秒) |
| fault_tree_version | String(50) | YES | - | 故障树版本号 |
| created_at | DateTime | YES | now | 创建时间 |

### 16.5 DiagnosisAnnotation — 诊断结果标注表

表名: `diagnosis_annotations`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| session_id | Integer | NO | - | 诊断会话ID (FK → diagnosis_sessions.id, CASCADE) |
| annotator_id | Integer | YES | - | 标注者ID (FK → users.id, SET NULL) |
| annotation | String(20) | NO | - | 标注结果: accurate/inaccurate/unknown |
| actual_root_cause | Text | YES | - | 实际根因 |
| notes | Text | YES | - | 备注 |
| annotated_at | DateTime | NO | now | 标注时间 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 16.6 BatterySOHRecord — UPS电池SOH记录表

表名: `battery_soh_records`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| device_id | Integer | NO | - | 设备ID (FK → devices.id, CASCADE) |
| soh_percent | Float | NO | - | SOH百分比 [0-100] |
| resistance_mohm | Float | YES | - | 当前内阻(毫欧) |
| cycle_count | Integer | YES | - | 充放电循环次数 |
| weights_version | String(50) | YES | - | 权重配置版本 |
| calculated_at | DateTime | NO | - | 计算时间(UTC) |

索引: idx_battery_soh_device_id, idx_battery_soh_calculated_at, idx_battery_soh_device_time

### 16.7 SOHPointUnavailableTracking — SOH点位不可用追踪表

表名: `soh_point_unavailable_tracking`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| device_id | Integer | NO | - | 设备ID (FK → devices.id, CASCADE, unique) |
| consecutive_days | Integer | NO | 0 | 连续不可用天数 |
| last_unavailable_date | DateTime | NO | - | 最后一次不可用日期 |
| alarm_triggered | Boolean | NO | False | 是否已触发告警 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 16.8 BreakerProfile — 断路器配置表

表名: `breaker_profiles`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| breaker_device_id | Integer | NO | - | 断路器设备ID (FK → power_devices.id, CASCADE, unique) |
| trip_curve_type | String(1) | NO | - | 脱扣曲线类型: B/C/D |
| rated_current | Float | NO | - | 额定电流 A |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 16.9 SensorMetadata — 传感器元数据表

表名: `sensor_metadata`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| point_id | Integer | NO | - | 点位ID (FK → points.id, CASCADE, unique) |
| ct_pt_ratio | Float | YES | - | CT/PT变比 |
| accuracy_class | Float | NO | - | 精度等级: 0.2/0.5/1.0 |
| calibration_date | Date | YES | - | 校准日期 |
| calibration_interval_days | Integer | NO | 365 | 校准周期天数 |
| calibration_result | String(500) | YES | - | 校准结果描述 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 16.10 TrendWarning — 趋势预警记录表

表名: `trend_warnings`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| point_id | Integer | NO | - | 点位ID (FK → points.id, CASCADE) |
| trend_type | String(20) | NO | - | 趋势类型: 上升/下降 |
| start_value | Float | NO | - | 起始值 |
| end_value | Float | NO | - | 结束值 |
| total_change | Float | NO | - | 总变化量 |
| message | Text | NO | - | 预警消息 |
| level | String(20) | NO | "info" | 预警级别 |
| detected_at | DateTime | NO | now | 检测时间 |
| acknowledged | Boolean | NO | False | 是否已确认 |
| acknowledged_by | Integer | YES | - | 确认人ID (FK → users.id) |
| acknowledged_at | DateTime | YES | - | 确认时间 |

索引: idx_trend_warnings_point_time, idx_trend_warnings_ack

### 16.11 SensorFusionRecord — 多传感器融合记录表

表名: `sensor_fusion_records`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| zone_id | Integer | NO | - | 区域ID (FK → cooling_zones.id, CASCADE) |
| sensor_count | Integer | NO | - | 传感器数量 |
| std_dev | Float | YES | - | 标准差 |
| evidence_type | String(50) | NO | - | 证据类型 |
| is_evidence | Boolean | NO | False | 是否作为证据 |
| probability | Float | YES | - | 概率 |
| message | Text | YES | - | 融合结果消息 |
| created_at | DateTime | NO | now | 创建时间 |

索引: idx_sensor_fusion_zone_time

### 16.12 CounterfactualAnalysis — 反事实分析表

表名: `counterfactual_analyses`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| session_id | Integer | NO | - | 诊断会话ID (FK, CASCADE, unique) |
| original_root_cause | String(500) | YES | - | 原始根因 |
| original_confidence | Float | YES | - | 原始置信度 |
| top_evidences | JSON | NO | - | Top证据列表 |
| analysis_results | JSON | NO | - | 分析结果 |
| analysis_time_ms | Integer | NO | 0 | 分析耗时(毫秒) |
| fault_tree_version | String(50) | YES | - | 故障树版本号 |
| config_version | String(50) | YES | - | 配置版本号 |
| deleted_at | DateTime | YES | - | 软删除时间 |
| created_at | DateTime | NO | now | 创建时间 |
| updated_at | DateTime | NO | now | 更新时间 |

### 16.13 SystemReport — 系统报告表

表名: `system_reports`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| report_type | String(50) | NO | - | 报告类型 |
| report_period | String(20) | NO | - | 报告周期 YYYY-MM |
| report_version | String(20) | YES | "v1.0" | 报告模板版本 |
| content | Text | NO | - | Markdown 格式报告内容 |
| summary | JSON | YES | - | 报告摘要 |
| generated_at | DateTime | YES | now | 生成时间 |
| generated_by | String(100) | YES | - | 生成者 |
| deleted_at | DateTime | YES | - | 软删除时间戳 |
| updated_at | DateTime | YES | now | 更新时间 |

### 16.14 DiagnosisImprovementRule — 诊断改进建议规则表

表名: `diagnosis_improvement_rules`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| rule_type | String(20) | NO | - | 规则类型: false_positive/false_negative |
| node_id | String(100) | YES | - | 故障树节点ID |
| fault_type | String(100) | YES | - | 故障类型 |
| suggestion_template | Text | NO | - | 建议模板 |
| priority | Integer | YES | 0 | 优先级 |
| is_active | Boolean | YES | True | 是否启用 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 16.15 ProbabilityAdjustmentLog — 概率调参记录表

表名: `probability_adjustment_logs`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| tree_id | Integer | NO | - | 故障树ID (FK → fault_trees.id) |
| node_id | Integer | NO | - | 节点ID (FK → fault_tree_nodes.id) |
| node_name | String(200) | NO | - | 节点名称 |
| node_type | String(20) | NO | - | 节点类型 |
| current_probability | Float | NO | - | 当前先验概率 |
| proposed_probability | Float | NO | - | 建议先验概率 |
| adjustment_percent | Float | NO | - | 调整百分比 |
| sample_count | Integer | NO | - | 样本数 |
| accurate_count | Integer | NO | - | 准确标注次数 |
| inaccurate_count | Integer | NO | - | 不准确标注次数 |
| accuracy_rate | Float | NO | - | 准确率 |
| status | String(20) | NO | "pending" | 状态: pending/approved/rejected |
| reason | Text | YES | - | 审批理由 |
| approved_by | Integer | YES | - | 审批人ID (FK → users.id) |
| approved_at | DateTime | YES | - | 审批时间 |
| version | Integer | NO | 1 | 乐观锁版本号 |
| created_at | DateTime | NO | now | 创建时间 |
| updated_at | DateTime | NO | now | 更新时间 |

### 16.16 AuditLog — 通用审计日志表

表名: `audit_logs`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| user_id | Integer | YES | - | 用户ID (FK → users.id) |
| action | String(100) | NO | - | 操作类型 |
| resource_type | String(50) | NO | - | 资源类型 |
| resource_id | Integer | YES | - | 资源ID |
| details | Text | YES | - | 操作详情 |
| ip_address | String(50) | YES | - | IP地址 |
| user_agent | String(500) | YES | - | User Agent |
| created_at | DateTime | NO | now | 创建时间 |

### 16.17 TimeWindowAdjustmentLog — 时间窗口调参记录表

表名: `time_window_adjustment_logs`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| device_type | String(100) | NO | - | 设备类型 |
| current_window_minutes | Integer | NO | - | 当前时间窗口(分钟) |
| proposed_window_minutes | Integer | NO | - | 建议时间窗口(分钟) |
| adjustment_percent | Float | NO | - | 调整百分比 |
| sample_count | Integer | NO | - | 样本数 |
| p50_duration_seconds | Float | NO | - | P50持续时长(秒) |
| p90_duration_seconds | Float | NO | - | P90持续时长(秒) |
| status | String(20) | NO | "pending" | 状态: pending/approved/rejected |
| reason | Text | YES | - | 审批理由 |
| approved_by | Integer | YES | - | 审批人ID |
| approved_at | DateTime | YES | - | 审批时间 |
| version | Integer | NO | 1 | 乐观锁版本号 |
| created_at | DateTime | NO | now | 创建时间 |
| updated_at | DateTime | NO | now | 更新时间 |

### 16.18 TrainingDataAudit — 训练数据异常检测审计表

表名: `training_data_audits`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| run_date | DateTime | NO | now | 运行日期 |
| total_samples | Integer | NO | - | 总样本数 |
| anomaly_count | Integer | NO | 0 | 异常样本数 |
| anomaly_rate | Float | NO | 0.0 | 异常率 |
| contamination | Float | NO | 0.05 | IsolationForest contamination |
| action_taken | String(50) | NO | - | 执行动作 |
| anomaly_sample_ids | JSON | YES | - | 异常样本 ID 列表 |
| created_at | DateTime | YES | now | 创建时间 |

### 16.19 HMACKeyRotationLog — HMAC 密钥轮换审计日志

表名: `hmac_key_rotation_logs`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| rotated_at | DateTime | NO | now | 轮换时间 |
| rotated_by | Integer | NO | - | 操作者 ID (FK → users.id) |
| versions_resigned | Integer | NO | 0 | 重签名版本数 |
| resigned_version_ids | JSON | YES | - | 重签名的版本 ID 列表 |
| new_key_prefix | String(4) | NO | - | 新密钥前4字符 |
| old_key_prefix | String(4) | YES | - | 旧密钥前4字符 |
| status | String(20) | NO | - | 操作状态: success/failed |
| error_detail | Text | YES | - | 错误详情 |
| created_at | DateTime | YES | now | 创建时间 |

## 17. fault_tree

源文件: `backend/app/models/fault_tree.py`

### 17.1 FaultTree — 故障树元数据

表名: `fault_trees`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| name | String(200) | NO | - | 名称 (unique) |
| description | Text | YES | - | 描述 |
| status | String(20) | NO | "draft" | 状态 |
| created_at | TIMESTAMP | NO | now() | 创建时间 |
| updated_at | TIMESTAMP | NO | now() | 更新时间 |
| created_by | Integer | YES | - | 创建人 (FK → users.id) |
| updated_by | Integer | YES | - | 更新人 (FK → users.id) |

关系: nodes, edges, device_mappings, versions, ab_tests

### 17.2 FaultTreeNode — 故障树节点

表名: `fault_tree_nodes`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| tree_id | Integer | NO | - | 故障树ID (FK, CASCADE) |
| node_type | String(20) | NO | - | 节点类型 (index) |
| gate_type | String(10) | YES | - | 门类型 |
| name | String(200) | NO | - | 节点名称 |
| description | Text | YES | - | 描述 |
| prior_probability | Float | NO | 0.5 | 先验概率 [0-1] |
| evidence_point_id | Integer | YES | - | 证据点位ID (FK → points.id) |
| config | Text | YES | - | 配置JSON |
| threshold_type | String(10) | YES | - | 阈值类型: ABOVE/BELOW |
| threshold_value | Float | YES | - | 阈值 |
| sigmoid_k | Float | YES | 2.0 | Sigmoid K参数 |
| created_at | TIMESTAMP | NO | now() | 创建时间 |

约束: CheckConstraint("prior_probability >= 0.0 AND prior_probability <= 1.0")

### 17.3 FaultTreeEdge — 故障树边

表名: `fault_tree_edges`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| tree_id | Integer | NO | - | 故障树ID (FK, CASCADE) |
| parent_node_id | Integer | NO | - | 父节点ID (FK, CASCADE) |
| child_node_id | Integer | NO | - | 子节点ID (FK, CASCADE) |
| created_at | TIMESTAMP | NO | now() | 创建时间 |

约束: CheckConstraint("parent_node_id != child_node_id")

### 17.4 FaultTreeDeviceMapping — 故障树设备映射

表名: `fault_tree_device_mapping`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| tree_id | Integer | NO | - | 故障树ID (FK, CASCADE) |
| device_type | String(50) | NO | - | 设备类型 (index) |
| alarm_type | String(100) | YES | - | 告警类型 (index) |
| priority | Integer | NO | 0 | 优先级 |
| created_at | TIMESTAMP | NO | now() | 创建时间 |

### 17.5 FaultTreeVersion — 故障树版本

表名: `fault_tree_versions`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| tree_id | Integer | NO | - | 故障树ID (FK, CASCADE) |
| version_number | Integer | NO | - | 版本号 (>0) |
| status | String(20) | NO | "draft" | 状态: draft/reviewed/active/archived |
| snapshot | Text | NO | - | 快照数据 |
| hmac_signature | String(64) | YES | - | HMAC签名 |
| created_by | Integer | NO | - | 创建人 (FK → users.id) |
| created_at | TIMESTAMP | NO | now() | 创建时间 |
| reviewed_by | Integer | YES | - | 审核人 (FK → users.id) |
| reviewed_at | TIMESTAMP | YES | - | 审核时间 |
| activated_at | TIMESTAMP | YES | - | 激活时间 |

## 18. gateway

源文件: `backend/app/models/gateway.py`

### 18.1 Gateway — 采集网关

表名: `gateways`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| gateway_id | String(50) | NO | - | 网关唯一标识 (unique) |
| name | String(100) | NO | - | 网关名称 |
| ip_address | String(45) | YES | - | IP 地址 |
| version | String(50) | YES | - | 固件版本 |
| status | String(20) | YES | "offline" | 状态: online/offline |
| capabilities | JSON | YES | - | 能力列表 |
| cpu_usage | Float | YES | - | CPU 使用率 % |
| memory_usage | Float | YES | - | 内存使用率 % |
| disk_usage | Float | YES | - | 磁盘使用率 % |
| last_heartbeat | DateTime | YES | - | 最后心跳时间 |
| site_id | Integer | YES | None | 站点 ID (FK → sites.id) |
| is_enabled | Boolean | YES | True | 是否启用 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 18.2 DataSource — 数据源

表名: `datasources`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| name | String(100) | NO | - | 数据源名称 |
| protocol_type | String(30) | NO | - | 协议类型 |
| gateway_id | Integer | YES | - | 关联网关 ID |
| connection_config | JSON | NO | - | 连接配置 |
| collection_interval | Integer | YES | 5 | 采集周期（秒） |
| write_enabled | Boolean | YES | False | 是否允许写入 |
| status | String(30) | YES | "disconnected" | 连接状态 |
| last_communication | DateTime | YES | - | 最后通信时间 |
| consecutive_failures | Integer | YES | 0 | 连续失败次数 |
| retry_base_delay | Float | YES | 1.0 | 重试基础延迟（秒） |
| retry_max_delay | Float | YES | 60.0 | 重试最大延迟（秒） |
| retry_max_failures | Integer | YES | 5 | 连续失败阈值 |
| site_id | Integer | YES | None | 站点 ID (FK → sites.id) |
| is_enabled | Boolean | YES | True | 是否启用 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

索引: Index("ix_datasources_gateway_enabled", "gateway_id", "is_enabled")

### 18.3 DataSourcePoint — 数据源点位映射

表名: `datasource_points`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| datasource_id | Integer | NO | - | 数据源 ID |
| point_id | Integer | YES | - | 关联 Point 表 ID |
| address | String(100) | NO | - | 协议地址 |
| data_type | String(30) | YES | - | 数据类型 |
| scale | Float | YES | 1.0 | 缩放系数 |
| offset | Float | YES | 0.0 | 偏移量 |
| enum_mapping | JSON | YES | - | 枚举映射 JSON |
| is_dry_contact | Boolean | YES | False | 是否干接点类型 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

约束: UniqueConstraint("datasource_id", "address")

### 18.4 GatewayEvent — 网关事件记录

表名: `gateway_events`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| gateway_id | String(50) | NO | - | 网关标识 (index) |
| event_type | String(30) | NO | - | 事件类型 |
| old_status | String(20) | YES | - | 旧状态 |
| new_status | String(20) | YES | - | 新状态 |
| detail | JSON | YES | - | 事件详情 |
| created_at | DateTime | YES | now | 创建时间 |

### 18.5 ConfigPushRecord — 配置下发记录

表名: `config_push_records`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| gateway_id | String(50) | NO | - | 网关标识 (index) |
| config_snapshot | JSON | NO | - | 下发的配置快照 |
| status | String(20) | YES | "pending" | 状态: pending/delivered/failed |
| error_message | String(500) | YES | - | 错误信息 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 18.6 PointDataLatest — 点位最新数据

表名: `point_data_latest`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| point_id | String(100) | NO | - | 点位ID (unique) |
| value | String(200) | YES | - | 最新值 |
| quality | Integer | YES | 0 | 质量码: 0=正常, 1=不可靠, 2=异常 |
| timestamp | DateTime | YES | - | 采集时间 |
| gateway_id | String(50) | YES | - | 来源网关 |
| source | String(20) | YES | "unknown" | 数据来源: demo/mqtt/bridge/unknown |
| updated_at | DateTime | YES | now | 更新时间 |

### 18.7 FirmwarePackage — 固件包

表名: `firmware_packages`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| version | String(50) | NO | - | 版本号 (unique, semver) |
| filename | String(200) | NO | - | 文件名 |
| file_size | Integer | NO | - | 文件大小(字节) |
| checksum_sha256 | String(64) | NO | - | SHA-256 校验和 |
| download_url | String(500) | NO | - | 下载地址 |
| release_notes | String(2000) | YES | - | 更新说明 |
| min_version | String(50) | YES | - | 最低兼容版本 |
| is_active | Boolean | YES | True | 是否可用 |
| created_at | DateTime | YES | now | 创建时间 |

### 18.8 OtaTask — OTA 升级任务

表名: `ota_tasks`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| task_id | String(50) | NO | - | 任务唯一标识(UUID, unique) |
| firmware_id | Integer | NO | - | 目标固件包 ID |
| target_version | String(50) | NO | - | 目标版本 |
| strategy | String(20) | YES | "immediate" | 策略: immediate/batch/canary |
| batch_size | Integer | YES | 0 | 分批大小 |
| batch_interval | Integer | YES | 300 | 批次间隔(秒) |
| canary_percent | Integer | YES | 10 | 灰度百分比 |
| status | String(20) | YES | "pending" | 状态 |
| total_gateways | Integer | YES | 0 | 总网关数 |
| success_count | Integer | YES | 0 | 成功数 |
| fail_count | Integer | YES | 0 | 失败数 |
| created_by | String(50) | YES | - | 创建人 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 18.9 OtaTaskGateway — OTA 任务-网关关联

表名: `ota_task_gateways`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| task_id | String(50) | NO | - | 任务 ID (index) |
| gateway_id | String(50) | NO | - | 网关标识 (index) |
| batch_index | Integer | YES | 0 | 所属批次 |
| status | String(20) | YES | "pending" | 状态 |
| old_version | String(50) | YES | - | 升级前版本 |
| progress | Integer | YES | 0 | 进度百分比 |
| error_message | String(500) | YES | - | 错误信息 |
| started_at | DateTime | YES | - | 开始时间 |
| completed_at | DateTime | YES | - | 完成时间 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

约束: UniqueConstraint("task_id", "gateway_id")

### 18.10 DeviceTemplate — 设备模板

表名: `device_templates`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| name | String(100) | NO | - | 模板名称 |
| manufacturer | String(100) | NO | - | 厂商 |
| model | String(100) | NO | - | 型号 |
| protocol_type | String(30) | NO | - | 协议类型 |
| description | String(500) | YES | - | 描述 |
| point_config | JSON | NO | - | 预置点位配置列表 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 18.11 MqttAclRule — MQTT ACL 规则表

表名: `mqtt_acl_rules`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| site_id | Integer | NO | - | 站点ID (FK → sites.id) |
| client_id_pattern | String(200) | YES | - | 客户端ID匹配模式 |
| topic_pattern | String(200) | NO | - | Topic 匹配模式 |
| action | String(10) | YES | "all" | 动作: publish/subscribe/all |
| permission | String(10) | YES | "allow" | 权限: allow/deny |
| description | String(200) | YES | - | 描述 |
| created_at | DateTime | YES | now | 创建时间 |

## 19. trace

源文件: `backend/app/models/trace.py`

枚举: MappingType (direct/aggregate/composite/ml_prediction), AggregationType (sum/avg/max/min/count/percentile/stddev), MLModelType (transformer/gnn/rl)

### 19.1 DataSourceMapping — 数据源映射配置表

表名: `data_source_mappings`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| param_code | String(100) | NO | - | 参数编码 (unique) |
| param_name | String(200) | NO | - | 参数名称 |
| param_unit | String(50) | YES | - | 参数单位 |
| mapping_type | String(20) | NO | - | 映射类型: direct/aggregate/composite |
| source_table | String(100) | YES | - | 源表名称 |
| source_field | String(100) | YES | - | 源字段名称 |
| aggregation_type | String(20) | YES | - | 聚合函数 |
| aggregation_params | JSON | YES | - | 聚合参数 |
| filter_condition | Text | YES | - | 筛选条件 SQL WHERE |
| time_range_type | String(20) | YES | - | 时间范围类型 |
| formula | Text | YES | - | 计算公式 |
| child_params | JSON | YES | - | 子参数列表 |
| template_ids | JSON | YES | - | 适用的模板ID列表 |
| description | Text | YES | - | 参数说明 |
| is_enabled | Boolean | YES | True | 是否启用 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

### 19.2 TraceRecord — 追溯记录表

表名: `trace_records`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| trace_id | String(50) | NO | - | 全局唯一追溯标识 (unique, index) |
| proposal_id | Integer | YES | - | 关联方案ID (FK) |
| measure_id | Integer | YES | - | 关联措施ID (FK) |
| mapping_id | Integer | YES | - | 关联映射配置ID (FK) |
| param_code | String(100) | NO | - | 参数编码 |
| param_name | String(200) | YES | - | 参数名称 |
| mapping_type | String(20) | NO | - | 映射类型 |
| source_table | String(100) | YES | - | 源表名称 |
| source_field | String(100) | YES | - | 源字段名称 |
| filter_condition | Text | YES | - | 筛选条件 |
| aggregation_type | String(20) | YES | - | 聚合函数类型 |
| aggregation_params | JSON | YES | - | 聚合参数 |
| time_range_start | DateTime | YES | - | 时间范围开始 |
| time_range_end | DateTime | YES | - | 时间范围结束 |
| formula | Text | YES | - | 计算公式 |
| formula_display | Text | YES | - | 公式展示形式 |
| raw_value | Numeric(20,6) | YES | - | 原始值 |
| formatted_value | String(100) | YES | - | 格式化后的值 |
| value_unit | String(50) | YES | - | 值单位 |
| parent_trace_id | String(50) | YES | - | 父追溯ID |
| child_trace_ids | JSON | YES | - | 子追溯ID列表 |
| depth | Integer | YES | 0 | 追溯深度 |
| query_sql | Text | YES | - | 实际执行的SQL |
| query_params | JSON | YES | - | 查询参数 |
| query_execution_time | Float | YES | - | 查询执行时间(ms) |
| ml_model_type | String(20) | YES | - | ML模型类型 |
| ml_model_version | String(50) | YES | - | 模型版本号 |
| ml_confidence | Float | YES | - | 预测置信度 0-1 |
| ml_input_features | JSON | YES | - | 模型输入特征摘要 |
| ml_output_raw | JSON | YES | - | 模型原始输出 |
| calculated_at | DateTime | YES | now | 计算时间 |
| created_at | DateTime | YES | now | 创建时间 |

### 19.3 TraceTree — 追溯树索引表

表名: `trace_trees`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| root_trace_id | String(50) | NO | - | 根追溯ID (index) |
| node_trace_id | String(50) | NO | - | 节点追溯ID (index) |
| path | String(500) | YES | - | 从根到此节点的路径 |
| depth | Integer | YES | 0 | 节点深度 |
| proposal_id | Integer | YES | - | 关联方案ID (FK) |
| measure_id | Integer | YES | - | 关联措施ID (FK) |
| created_at | DateTime | YES | now | 创建时间 |

### 19.4 TemplateParameter — 模板参数配置表

表名: `template_parameters`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| template_id | String(50) | NO | - | 模板ID |
| template_name | String(200) | YES | - | 模板名称 |
| param_code | String(100) | NO | - | 参数编码 |
| param_name | String(200) | NO | - | 参数显示名称 |
| param_description | Text | YES | - | 参数说明 |
| mapping_id | Integer | YES | - | 关联映射配置ID (FK) |
| default_value | Numeric(20,6) | YES | - | 默认值 |
| min_value | Numeric(20,6) | YES | - | 最小值 |
| max_value | Numeric(20,6) | YES | - | 最大值 |
| is_required | Boolean | YES | True | 是否必需 |
| sort_order | Integer | YES | 0 | 排序顺序 |
| is_enabled | Boolean | YES | True | 是否启用 |
| created_at | DateTime | YES | now | 创建时间 |
| updated_at | DateTime | YES | now | 更新时间 |

## 20. command

源文件: `backend/app/models/command.py`

### 20.1 CommandApproval — 命令审批工单表

表名: `command_approvals`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| command_type | String(50) | NO | - | 命令类型标识 |
| risk_level | String(20) | NO | - | 风险等级: normal/critical |
| target_device_id | Integer | NO | - | 目标设备ID |
| target_device_name | String(100) | NO | - | 目标设备名称 |
| command_content | JSON | YES | - | 命令内容（参数） |
| requester_id | Integer | NO | - | 发起人ID (FK → users.id) |
| requester_name | String(50) | NO | - | 发起人用户名 |
| approver_id | Integer | YES | - | 审批人ID (FK → users.id) |
| approver_name | String(50) | YES | - | 审批人用户名 |
| status | String(20) | YES | "pending" | 状态: pending/approved/rejected/cancelled/timeout |
| reject_reason | Text | YES | - | 驳回原因 |
| timeout_minutes | Integer | YES | 30 | 超时时间(分钟) |
| created_at | DateTime | YES | now | 创建时间 |
| approved_at | DateTime | YES | - | 审批时间 |
| executed_at | DateTime | YES | - | 执行时间 |
| expired_at | DateTime | NO | - | 过期时间 |

### 20.2 CommandAuditLog — 命令审计日志表

表名: `command_audit_logs`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| command_type | String(50) | NO | - | 命令类型 |
| risk_level | String(20) | NO | - | 风险等级 |
| target_device_id | Integer | NO | - | 目标设备ID |
| target_device_name | String(100) | NO | - | 目标设备名称 |
| command_content | JSON | YES | - | 命令内容 |
| operator_id | Integer | NO | - | 操作人ID (FK → users.id) |
| operator_name | String(50) | NO | - | 操作人用户名 |
| approval_id | Integer | YES | - | 关联审批ID (FK) |
| result | String(20) | NO | - | 结果: success/failed/cancelled/timeout/pending |
| result_message | Text | YES | - | 结果描述 |
| created_at | DateTime | YES | now | 记录时间 |

## 21. floor_map

源文件: `backend/app/models/floor_map.py`

### 21.1 FloorMap — 楼层平面图

表名: `floor_maps`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| floor_code | String(10) | NO | - | 楼层代码 B1/F1/F2/F3 (index) |
| floor_name | String(50) | NO | - | 楼层名称 |
| map_type | String(10) | NO | - | 图类型 2d/3d |
| map_data | Text | NO | - | 图数据 JSON格式 |
| thumbnail | Text | YES | - | 缩略图 Base64 |
| is_default | Boolean | YES | False | 是否默认显示 |
| is_demo | Boolean | NO | False | 是否为演示数据 |
| created_at | DateTime | YES | now() | 创建时间 |
| updated_at | DateTime | YES | now() | 更新时间 |

---

## 22. load_shift.py — 负荷转移系统模型

源文件: `backend/app/models/load_shift.py` (495 行)

包含 8 个 ORM 模型，覆盖负荷转移计划、执行、约束、机会分析、制冷联动、设备寿命影响。

### ShiftPlan — 负荷转移计划表

表名: `shift_plans`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| plan_code | String(50) | NO | - | 计划编号 (unique) |
| plan_name | String(200) | NO | - | 计划名称 |
| shift_from_period | String(20) | NO | - | 转出时段: peak/sharp |
| shift_to_period | String(20) | NO | - | 转入时段: valley/flat |
| shift_date | Date | NO | - | 转移日期 |
| start_time | Time | NO | - | 转移开始时间 |
| end_time | Time | NO | - | 转移结束时间 |
| target_shift_power | Float | NO | - | 目标转移功率 kW |
| selected_devices | JSON | YES | - | 选中设备列表 |
| constraints | JSON | YES | - | 约束配置 |
| expected_cost_saving | Float | YES | - | 预期节省电费 元 |
| expected_energy_saving | Float | YES | - | 预期节省电量 kWh |
| actual_shift_power | Float | YES | - | 实际转移功率 kW |
| actual_cost_saving | Float | YES | - | 实际节省电费 元 |
| actual_energy_saving | Float | YES | - | 实际节省电量 kWh |
| status | String(20) | NO | draft | 状态 |
| approval_status | String(20) | NO | pending | 审批状态 |
| execution_status | String(20) | NO | not_started | 执行状态 |
| description | Text | YES | - | 计划描述 |
| error_message | Text | YES | - | 错误信息 |
| created_by | Integer FK(users.id) | NO | - | 创建人ID |
| approved_by | Integer FK(users.id) | YES | - | 审批人ID |
| approval_comment | Text | YES | - | 审批意见 |
| created_at | DateTime | NO | now() | 创建时间 |
| updated_at | DateTime | YES | now() | 更新时间 |
| approved_at | DateTime | YES | - | 审批时间 |
| executed_at | DateTime | YES | - | 执行时间 |
| completed_at | DateTime | YES | - | 完成时间 |

关系: executions → ShiftExecution (cascade), analysis_records → ShiftAnalysisRecord (cascade)

### ShiftExecution — 负荷转移执行记录表

表名: `shift_executions`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| plan_id | Integer FK(shift_plans.id) | NO | - | 关联计划ID (CASCADE) |
| execution_code | String(50) | NO | - | 执行编号 (unique) |
| start_time | DateTime | NO | - | 开始时间 |
| end_time | DateTime | YES | - | 结束时间 |
| duration_minutes | Integer | YES | - | 执行时长 分钟 |
| before_total_power | Float | YES | - | 执行前总功率 kW |
| before_device_states | JSON | YES | - | 执行前设备状态快照 |
| after_total_power | Float | YES | - | 执行后总功率 kW |
| after_device_states | JSON | YES | - | 执行后设备状态快照 |
| actual_shift_power | Float | YES | - | 实际转移功率 kW |
| actual_cost_saving | Numeric(10,2) | YES | - | 实际节省电费 元 |
| actual_energy_saving | Numeric(10,2) | YES | - | 实际节省电量 kWh |
| status | String(20) | YES | pending | 状态: pending/executing/completed/failed/cancelled/reverted |
| success_rate | Float | YES | - | 成功率 0-1 |
| failure_reason | Text | YES | - | 失败原因 |
| error_details | JSON | YES | - | 错误详情 |
| device_execution_details | JSON | YES | - | 设备执行详情 JSON |
| cooling_linkage_data | JSON | YES | - | 制冷联动数据 JSON |
| executed_by | Integer FK(users.id) | YES | - | 执行人ID |
| created_at | DateTime | YES | now() | 创建时间 |

关系: plan → ShiftPlan

### ShiftConstraint — 负荷转移约束配置表

表名: `shift_constraints`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| constraint_name | String(100) | NO | - | 约束名称 |
| constraint_type | String(30) | NO | - | 约束类型: power/time/device/cooling/safety/electrical |
| constraint_level | String(20) | YES | global | 约束级别: global/device/circuit |
| device_id | Integer FK(power_devices.id) | YES | - | 关联设备ID |
| circuit_id | Integer FK(distribution_circuits.id) | YES | - | 关联回路ID |
| constraint_params | JSON | NO | - | 约束参数 JSON |
| priority | Integer | YES | 5 | 优先级 1-10 (1最高) |
| is_enabled | Boolean | YES | True | 是否启用 |
| is_mandatory | Boolean | YES | False | 是否强制约束 |
| violation_action | String(20) | YES | reject | 违反处理: reject/warn/ignore |
| created_at | DateTime | YES | now() | 创建时间 |
| updated_at | DateTime | YES | now() | 更新时间 |
| remark | Text | YES | - | 备注 |

兼容属性: constraint_config ↔ constraint_params, description ↔ remark, is_active ↔ is_enabled

### ShiftOpportunity — 负荷转移机会分析表

表名: `shift_opportunities`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| opportunity_code | String(50) | NO | - | 机会编号 (unique) |
| opportunity_name | String(200) | NO | - | 机会名称 |
| recommended_date | Date | NO | - | 推荐日期 |
| analysis_period | String(20) | YES | - | 分析时段: peak/sharp |
| recommended_shift_from | String(20) | YES | - | 推荐转出时段 |
| recommended_shift_to | String(20) | YES | - | 推荐转入时段 |
| recommended_shift_power | Float | YES | - | 推荐转移功率 kW |
| recommended_devices | JSON | YES | - | 推荐设备列表 |
| estimated_cost_saving | Numeric(10,2) | YES | - | 预测节省电费 元 |
| estimated_energy_saving | Numeric(10,2) | YES | - | 预测节省电量 kWh |
| confidence_score | Float | YES | - | 置信度评分 0-1 |
| analysis_data | JSON | YES | - | 分析数据 JSON |
| status | String(20) | YES | discovered | 状态: discovered/reviewed/accepted/rejected/converted |
| priority | String(20) | YES | medium | 优先级: high/medium/low |
| converted_to_plan_id | Integer FK(shift_plans.id) | YES | - | 转换为计划ID |
| converted_at | DateTime | YES | - | 转换时间 |
| discovered_at | DateTime | YES | now() | 发现时间 |
| created_at | DateTime | YES | now() | 创建时间 |
| updated_at | DateTime | YES | now() | 更新时间 |

### ShiftAnalysisRecord — 负荷转移分析记录表

表名: `shift_analysis_records`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| plan_id | Integer FK(shift_plans.id) | YES | - | 关联计划ID (CASCADE) |
| analysis_type | String(30) | NO | - | 分析类型: feasibility/constraint/risk/benefit |
| analysis_result | String(20) | YES | - | 分析结果: pass/fail/warning |
| analysis_score | Float | YES | - | 分析评分 0-100 |
| analysis_details | JSON | YES | - | 分析详情 JSON |
| recommendations | JSON | YES | - | 优化建议列表 |
| warnings | JSON | YES | - | 警告信息列表 |
| analyzed_at | DateTime | YES | now() | 分析时间 |

关系: plan → ShiftPlan

### CoolingLinkageConfig — 制冷联动配置表

表名: `cooling_linkage_configs`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| cooling_zone_id | Integer FK(cooling_zones.id) | NO | - | 关联制冷区域 (CASCADE) |
| enabled | Boolean | YES | True | 是否启用制冷联动 |
| lag_time_minutes | Integer | YES | 20 | 制冷滞后时间 分钟 |
| target_cop | Float | YES | 3.0 | 目标 COP |
| cop_lower_threshold | Float | YES | 2.0 | COP 下限阈值 |
| cop_upper_threshold | Float | YES | 4.5 | COP 上限阈值 |
| target_supply_temp | Float | YES | 10.0 | 供水温度目标值 |
| supply_temp_lower | Float | YES | 5.0 | 供水温度下限 |
| supply_temp_upper | Float | YES | 15.0 | 供水温度上限 |
| target_return_temp | Float | YES | 15.0 | 回水温度目标值 |
| return_temp_lower | Float | YES | 10.0 | 回水温度下限 |
| return_temp_upper | Float | YES | 20.0 | 回水温度上限 |
| power_adjust_step | Integer | YES | 20 | 功率调整步长 kW |
| max_adjust_ratio | Float | YES | 0.25 | 最大调整幅度 |
| adjust_interval_minutes | Integer | YES | 10 | 调整间隔时间 分钟 |
| safety_protection_enabled | Boolean | YES | True | 启用安全保护 |
| min_cooling_power | Float | YES | 100 | 最小制冷功率 kW |
| max_cooling_power | Float | YES | 2000 | 最大制冷功率 kW |
| precool_target_temp | Float | YES | - | 预冷目标温度 (Story 29.1) |
| precool_enabled | Boolean | YES | False | 是否启用预冷功能 |
| created_at | DateTime | YES | now() | 创建时间 |
| updated_at | DateTime | YES | now() | 更新时间 |

### CoolingLinkageRecord — 制冷联动记录表

表名: `cooling_linkage_records`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| execution_id | Integer FK(shift_executions.id) | YES | - | 关联执行ID (CASCADE) |
| timestamp | DateTime | NO | now() | 记录时间 |
| event_type | String(20) | YES | - | 事件类型: adjust/alarm/recovery/manual |
| before_power | Float | YES | - | 调整前功率 kW |
| after_power | Float | YES | - | 调整后功率 kW |
| power_change | Float | YES | - | 功率变化 kW |
| cop_before | Float | YES | - | 调整前 COP |
| cop_after | Float | YES | - | 调整后 COP |
| supply_temp_before | Float | YES | - | 调整前供水温度 |
| supply_temp_after | Float | YES | - | 调整后供水温度 |
| return_temp_before | Float | YES | - | 调整前回水温度 |
| return_temp_after | Float | YES | - | 调整后回水温度 |
| reason | Text | YES | - | 调整原因 |
| created_at | DateTime | YES | now() | 创建时间 |

### DeviceLifespanImpact — 设备寿命影响记录表

表名: `device_lifespan_impacts`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| device_id | Integer FK(power_devices.id) | NO | - | 设备ID |
| execution_id | Integer FK(shift_executions.id) | YES | - | 关联执行ID (CASCADE) |
| operation_type | String(20) | YES | - | 操作类型: startup/shutdown/load_change |
| operation_count | Integer | YES | 1 | 操作次数 |
| lifespan_loss_hours | Float | YES | - | 寿命损失 小时 |
| lifespan_loss_percentage | Float | YES | - | 寿命损失百分比 |
| cumulative_startups | Integer | YES | - | 累计启动次数 |
| cumulative_lifespan_loss | Float | YES | - | 累计寿命损失 小时 |
| maintenance_recommended | Boolean | YES | False | 是否建议维护 |
| maintenance_reason | Text | YES | - | 维护原因 |
| next_maintenance_date | Date | YES | - | 建议维护日期 |
| recorded_at | DateTime | YES | now() | 记录时间 |

---

## 23. rollback.py — 回退保护事件模型

源文件: `backend/app/models/rollback.py` (41 行)

包含 1 个 ORM 模型 + 1 个枚举类。

### 枚举: RollbackTriggerType

| 值 | 说明 |
|------|------|
| temp_over_limit | 条件1: T_inlet > 26°C |
| rate_over_predicted | 条件2: 温升超预测 150% |
| rate_over_limit | 条件3: |dT/dt| > 5°C/h |
| ac_fault | 条件4: 空调故障告警 |
| sensor_offline | 条件5: 温度传感器离线 |
| ups_active | 条件6: 市电中断切 UPS |
| humidity_dew_point | 条件7: 湿度接近露点 |

### RollbackEvent — 回退保护事件记录

表名: `rollback_events`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| zone_id | Integer FK(cooling_zones.id) | NO | - | 制冷区域ID |
| trigger_type | String(30) | NO | - | 触发类型 |
| trigger_value | Float | YES | - | 触发时的实际值 |
| threshold | Float | YES | - | 阈值 |
| action | String(100) | NO | - | 执行的回退动作 |
| status | String(20) | YES | active | 状态: active/resolved |
| context_json | Text | YES | - | 附加上下文 JSON |
| created_at | DateTime | YES | now() | 触发时间 |
| resolved_at | DateTime | YES | - | 恢复时间 |

---

## 24. thermal.py — 热动力学数据模型

源文件: `backend/app/models/thermal.py` (206 行)

包含 4 个 ORM 模型，覆盖热参数标定、温度预测、预冷计划、VPP 调控指令。

### ThermalParameter — 热参数标定记录表

表名: `thermal_parameters`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| cooling_zone_id | Integer FK(cooling_zones.id) | NO | - | 关联制冷区域ID (CASCADE) |
| thermal_R | Float | YES | - | 热阻标定值 °C/kW |
| thermal_C | Float | YES | - | 热容标定值 kWh/°C |
| fitting_r_squared | Float | YES | - | 拟合 R² 值 |
| fitting_method | String(20) | YES | manual | 标定方法: auto_fit/manual/default |
| sample_count | Integer | YES | - | 样本数 |
| calibrated_at | DateTime | YES | - | 标定时间 |
| is_active | Boolean | YES | True | 是否为当前生效参数 |
| is_demo | Boolean | YES | False | 是否为 demo 数据 |
| created_at | DateTime | YES | now() | 创建时间 |
| updated_at | DateTime | YES | now() | 更新时间 |

索引: ix_thermal_params_zone_active (cooling_zone_id, is_active)
约束: uq_thermal_params_zone_active (cooling_zone_id, is_active) UNIQUE

### TemperaturePredictionLog — 温度预测记录表

表名: `temperature_prediction_logs`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| cooling_zone_id | Integer FK(cooling_zones.id) | NO | - | 关联制冷区域ID (CASCADE) |
| predicted_temp | Float | NO | - | 预测温度 °C |
| actual_temp | Float | YES | - | 实际温度 °C |
| prediction_horizon_min | Integer | NO | - | 预测时长 分钟 |
| deviation | Float | YES | - | 偏差 = actual - predicted |
| model_version | String(50) | NO | - | 模型参数版本 |
| created_at | DateTime | NO | now() | 记录时间 |

索引: ix_temp_pred_zone_time (cooling_zone_id ASC, created_at DESC)

### PrecoolSchedule — 预冷计划表

表名: `precool_schedules`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| cooling_zone_id | Integer FK(cooling_zones.id) | NO | - | 关联制冷区域ID (CASCADE, index) |
| schedule_date | Date | NO | - | 计划日期 |
| precool_start_time | Time | NO | - | 预冷开始时间（谷时） |
| precool_end_time | Time | NO | - | 预冷结束时间 |
| target_temp | Float | NO | - | 预冷目标温度 °C |
| peak_start_time | Time | NO | - | 峰时削减开始时间 |
| peak_end_time | Time | NO | - | 峰时削减结束时间 |
| planned_savings_kwh | Float | YES | 0.0 | 计划节省电量 kWh |
| actual_savings_kwh | Float | YES | - | 实际节省电量 kWh |
| status | String(20) | YES | pending | 状态: pending/executing/completed/aborted (index) |
| abort_reason | String(500) | YES | - | 中止原因 |
| temperature_trajectory | JSON | YES | - | 预测/实际温度轨迹 JSON |
| is_validated | Boolean | YES | False | 是否通过约束验证 |
| validated_at | DateTime | YES | - | 验证时间 |
| created_at | DateTime | YES | now() | 创建时间 |
| updated_at | DateTime | YES | now() | 更新时间 |

约束: uq_zone_schedule_date (cooling_zone_id, schedule_date) UNIQUE

### VppDispatch — VPP 调控指令记录

表名: `vpp_dispatches`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 (index) |
| dispatch_id | String(64) | NO | - | UUID 外部标识 (unique) |
| command_type | String(20) | NO | - | 调控方向: down_adjust/up_adjust |
| target_power_kw | Float | NO | - | 请求调控功率 kW_e |
| duration_minutes | Integer | NO | - | 持续时间（分钟） |
| priority | Integer | YES | 1 | 优先级 1=普通 2=紧急 |
| status | String(20) | NO | received | 状态: received/accepted/rejected |
| reject_reason | String(500) | YES | - | 拒绝原因 |
| max_adjustable_kw | Float | YES | - | 拒绝时返回的最大可调容量 |
| accepted_power_kw | Float | YES | - | 实际接受的调控功率 |
| aborted_schedule_id | Integer | YES | - | 被中止的预冷计划 ID |
| created_at | DateTime | YES | now() | 创建时间 |

索引: ix_vpp_dispatches_status, ix_vpp_dispatches_created_at

---

## 25. notification.py — 系统通知模型

源文件: `backend/app/models/notification.py` (24 行)

包含 1 个 ORM 模型。

### SystemNotification — 系统内通知表

表名: `system_notifications`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| title | String(200) | NO | - | 通知标题 |
| content | Text | NO | - | 通知内容 |
| notification_type | String(50) | NO | - | 通知类型 |
| target_role | String(20) | NO | - | 目标角色: admin/operator/viewer |
| data | JSON | YES | - | 附加数据 |
| is_read | Boolean | YES | False | 是否已读 |
| created_at | DateTime | YES | now() | 创建时间 |

---

## 26. drift.py — 漂移检测模型

源文件: `backend/app/models/drift.py` (32 行)

包含 1 个 ORM 模型。

### DriftDetectionResult — 漂移检测结果表

表名: `drift_detection_results`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| point_id | Integer FK(points.id) | NO | - | 点位ID |
| point_code | String(50) | NO | - | 点位编码 |
| point_name | String(100) | NO | - | 点位名称 |
| area_code | String(10) | YES | - | 区域代码 |
| status | String(20) | NO | - | 状态: suspected/confirmed/resolved |
| mean_value | Float | NO | - | 检测期间均值 |
| std_value | Float | NO | - | 检测期间标准差 |
| current_value | Float | NO | - | 当前值 |
| deviation_sigma | Float | NO | - | 偏差倍数(σ) |
| cross_validation_result | String(20) | YES | - | 交叉验证结果: pass/fail/skipped |
| diagnosis | Text | NO | - | 诊断建议 |
| detected_at | DateTime | YES | now() | 检测时间 |
| resolved_at | DateTime | YES | - | 解除时间 |
| created_at | DateTime | YES | now() | 记录创建时间 |

---

## 27. video.py — 视频监控模型

源文件: `backend/app/models/video.py` (84 行)

包含 4 个 ORM 模型。

### NVR — NVR 设备表

表名: `nvrs`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| name | String(100) | NO | - | NVR名称 |
| ip_address | String(50) | NO | - | IP地址 |
| port | Integer | YES | 554 | 端口 |
| username | String(100) | YES | - | 登录用户名 |
| password | String(200) | YES | - | 登录密码 |
| manufacturer | String(50) | YES | - | 厂商: hikvision/dahua/other |
| model | String(100) | YES | - | 型号 |
| max_channels | Integer | YES | - | 最大通道数 |
| status | String(20) | YES | offline | 状态: online/offline |
| description | Text | YES | - | 备注 |
| created_at | DateTime | YES | now() | 创建时间 |
| updated_at | DateTime | YES | now() | 更新时间 |

### Camera — 摄像头表

表名: `cameras`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| name | String(100) | NO | - | 摄像头名称 |
| code | String(50) | NO | - | 摄像头编码 (unique) |
| rtsp_url | String(500) | YES | - | RTSP流地址 |
| onvif_url | String(500) | YES | - | ONVIF控制地址 |
| hls_url | String(500) | YES | - | HLS流地址 |
| nvr_id | Integer FK(nvrs.id) | YES | - | 关联NVR |
| channel_no | Integer | YES | - | NVR通道号 |
| area_code | String(10) | YES | - | 关联区域代码 |
| cabinet_id | Integer | YES | - | 关联机柜ID |
| device_id | Integer | YES | - | 关联设备ID |
| location_description | String(200) | YES | - | 位置描述 |
| camera_type | String(20) | YES | dome | 类型: dome/bullet/ptz |
| status | String(20) | YES | unknown | 状态: online/offline/unknown |
| is_enabled | Boolean | YES | True | 是否启用 |
| created_at | DateTime | YES | now() | 创建时间 |
| updated_at | DateTime | YES | now() | 更新时间 |

### CameraPreset — 摄像头预置位表

表名: `camera_presets`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| camera_id | Integer FK(cameras.id) | NO | - | 关联摄像头 |
| preset_index | Integer | NO | - | 预置位编号 |
| name | String(100) | NO | - | 预置位名称 |
| description | String(200) | YES | - | 描述 |

### VideoEvent — 视频事件表

表名: `video_events`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| camera_id | Integer FK(cameras.id) | NO | - | 关联摄像头 |
| event_type | String(30) | NO | - | 事件类型: recording_start/recording_stop/ptz_control/preset_call |
| trigger_source | String(50) | NO | - | 触发来源: linkage/manual |
| alarm_id | Integer | YES | - | 关联告警ID |
| linkage_execution_id | Integer | YES | - | 关联联动执行ID |
| detail | Text | YES | - | 事件详情JSON |
| operator | String(50) | YES | - | 操作人 |
| created_at | DateTime | YES | now() | 事件时间 |

---

## 28. vpp_data.py — 虚拟电厂(VPP)数据模型

源文件: `backend/app/models/vpp_data.py` (111 行)

包含 5 个 ORM 模型 + 1 个枚举类。

### 枚举: TimePeriodType

| 值 | 说明 |
|------|------|
| peak | 峰时 |
| valley | 谷时 |
| flat | 平时 |

### ElectricityBill — 电费清单表

表名: `electricity_bills`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| month | String(7) | NO | - | 月份 YYYY-MM格式 (index) |
| total_consumption | Float | NO | - | 月度总用电量 kWh |
| peak_consumption | Float | YES | - | 峰段用电量 kWh |
| valley_consumption | Float | YES | - | 谷段用电量 kWh |
| flat_consumption | Float | YES | - | 平段用电量 kWh |
| max_demand | Float | YES | - | 最大需量 kW |
| power_factor | Float | YES | - | 功率因数 |
| total_cost | Float | NO | - | 月度总电费 元 |
| basic_fee | Float | YES | - | 基本电费 元 |
| market_purchase_fee | Float | YES | - | 市场化购电电费 元 |
| transmission_fee | Float | YES | - | 输配电费 元 |
| system_operation_fee | Float | YES | - | 系统运行费 元 |
| government_fund | Float | YES | - | 政府性基金及附加 元 |
| created_at | DateTime | YES | func.now() | 创建时间 |
| updated_at | DateTime | YES | func.now() | 更新时间 |

### LoadCurve — 负荷曲线数据表

表名: `load_curves`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| timestamp | DateTime | NO | - | 时间戳 15分钟间隔 (index) |
| load_value | Float | NO | - | 负荷值 kW |
| date | Date | NO | - | 日期 (index) |
| time_period | Enum(TimePeriodType) | YES | - | 时段类型 (峰/平/谷) |
| is_workday | Boolean | YES | True | 是否工作日 |
| created_at | DateTime | YES | func.now() | 创建时间 |

### ElectricityPrice — 电价配置表

表名: `electricity_prices`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| period_type | Enum(TimePeriodType) | NO | - | 时段类型 |
| price | Float | NO | - | 单价 元/kWh |
| start_time | Time | NO | - | 开始时间 HH:MM |
| end_time | Time | NO | - | 结束时间 HH:MM |
| effective_date | Date | YES | - | 生效日期 |
| created_at | DateTime | YES | func.now() | 创建时间 |

### AdjustableLoad — 可调节负荷资源表

表名: `adjustable_loads`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| equipment_name | String(200) | NO | - | 设备名称 |
| equipment_type | String(100) | YES | - | 设备类型 |
| rated_power | Float | NO | - | 额定功率 kW |
| adjustable_ratio | Float | NO | - | 可调节比例 % |
| response_time | Integer | YES | - | 响应时间 分钟 |
| adjustment_cost | Float | YES | - | 调节成本 元/次 |
| is_active | Boolean | YES | True | 是否启用 |
| created_at | DateTime | YES | func.now() | 创建时间 |
| updated_at | DateTime | YES | func.now() | 更新时间 |

### VPPConfig — VPP配置参数表

表名: `vpp_configs`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| config_key | String(100) | NO | - | 配置键 (unique, index) |
| config_value | Float | NO | - | 配置值 |
| config_unit | String(50) | YES | - | 单位 |
| description | String(500) | YES | - | 描述 |
| created_at | DateTime | YES | func.now() | 创建时间 |
| updated_at | DateTime | YES | func.now() | 更新时间 |

---

## 29. ab_test_config.py — A/B 测试模型

源文件: `backend/app/models/ab_test_config.py` (70 行)

包含 3 个 ORM 模型。

### ABTestConfig — A/B 测试配置表

表名: `ab_test_configs`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 (index) |
| name | String(255) | NO | - | 测试名称 |
| fault_tree_id | Integer FK(fault_trees.id) | NO | - | 关联故障树 |
| version_a_id | Integer FK(fault_tree_versions.id) | NO | - | A 版本 |
| version_b_id | Integer FK(fault_tree_versions.id) | NO | - | B 版本 |
| strategy | String(50) | NO | - | 策略: hash/device_type/site/percentage |
| strategy_params | JSON | YES | - | 策略参数 JSON |
| status | String(20) | NO | active | 状态: active/paused/completed |
| version | Integer | NO | 1 | 乐观锁版本号 |
| min_duration_hours | Integer | NO | 168 | 最小运行时长(小时) |
| min_sample_size | Integer | NO | 100 | 最小样本量 |
| created_by | Integer FK(users.id) | YES | - | 创建人 |
| created_at | TIMESTAMP | NO | utcnow | 创建时间 |
| updated_at | TIMESTAMP | NO | utcnow | 更新时间 |
| completed_at | TIMESTAMP | YES | - | 完成时间 |

约束: check_ab_test_status (status IN active/paused/completed), check_version_different (version_a_id != version_b_id)
关系: fault_tree → FaultTree, version_a/version_b → FaultTreeVersion, creator → User

### ABTestDeviceAssignment — A/B 测试设备版本分配记录

表名: `ab_test_device_assignments`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 (index) |
| ab_test_id | Integer FK(ab_test_configs.id) | NO | - | 关联测试 (CASCADE) |
| device_id | String(255) | NO | - | 设备ID |
| assigned_version_id | Integer FK(fault_tree_versions.id) | NO | - | 分配版本 |
| assigned_at | TIMESTAMP | NO | utcnow | 分配时间 |

关系: ab_test → ABTestConfig, assigned_version → FaultTreeVersion

### ABTestArchive — A/B 测试归档数据

表名: `ab_test_archives`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 (index) |
| ab_test_id | Integer FK(ab_test_configs.id) | NO | - | 关联测试 |
| version_a_stats | JSON | NO | - | A 版本统计 |
| version_b_stats | JSON | NO | - | B 版本统计 |
| statistical_test_result | JSON | NO | - | 统计检验结果 |
| decision | String(50) | NO | - | 决策 |
| archived_at | TIMESTAMP | NO | utcnow | 归档时间 |
| archived_by | Integer FK(users.id) | YES | - | 归档人 |

关系: ab_test → ABTestConfig, archiver → User

---

## 30. system.py — 控制与日志模型

源文件: `backend/app/models/system.py` (54 行)

包含 3 个 ORM 模型，使用 Mapped[] 声明式风格。

### ControlCommand — 控制指令表

表名: `control_commands`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| point_id | Integer FK(points.id) | NO | - | 点位ID |
| target_value | Float | NO | - | 目标值 |
| executed_by | Integer FK(users.id) | NO | - | 执行人ID |
| status | String(20) | YES | pending | 状态: pending/executing/success/failed |
| result_message | Text | YES | - | 结果消息 |
| created_at | DateTime | YES | utcnow | 创建时间 |
| executed_at | DateTime | YES | - | 执行时间 |

### License — 系统授权表

表名: `license`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| license_key | String(100) | NO | - | 授权密钥 (unique) |
| license_type | String(20) | NO | - | 类型: basic/standard/enterprise/unlimited |
| max_points | Integer | NO | - | 最大点位数 |
| expire_date | Date | YES | - | 过期日期 |
| is_active | Boolean | YES | True | 是否激活 |
| created_at | DateTime | YES | utcnow | 创建时间 |

### OperationLog — 操作日志表

表名: `operation_logs`

| 列名 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | Integer | NO | autoincrement | 主键 |
| user_id | Integer FK(users.id) | YES | - | 用户ID |
| action | String(100) | NO | - | 操作动作 |
| target_type | String(50) | YES | - | 目标类型: point/alarm/user/threshold |
| target_id | Integer | YES | - | 目标ID |
| old_value | Text | YES | - | 旧值 |
| new_value | Text | YES | - | 新值 |
| ip_address | String(50) | YES | - | IP地址 |
| created_at | DateTime | YES | utcnow | 创建时间 |

---

## 统计汇总

| 指标 | 数量 |
|------|------|
| 模型文件 | 30 |
| ORM 模型 (数据表) | 134 |
| 枚举类 | 8 |
| 总计类定义 | 142 |

### 按模型文件统计

| 序号 | 文件 | ORM 模型数 | 枚举数 |
|------|------|------|------|
| 1 | user.py | 5 | 0 |
| 2 | device.py | 2 | 0 |
| 3 | point.py | 4 | 0 |
| 4 | alarm.py | 7 | 1 |
| 5 | history.py | 2 | 0 |
| 6 | log.py | 3 | 0 |
| 7 | config.py | 3 | 0 |
| 8 | energy.py | 14 | 0 |
| 9 | asset.py | 4 | 0 |
| 10 | capacity.py | 5 | 0 |
| 11 | operation.py | 5 | 1 |
| 12 | report.py | 3 | 0 |
| 13 | cooling.py | 5 | 0 |
| 14 | power.py | 3 | 0 |
| 15 | spatial.py | 5 | 1 |
| 16 | topology_config.py | 5 | 0 |
| 17 | linkage.py | 3 | 0 |
| 18 | diagnosis.py | 5 | 1 |
| 19 | fault_tree.py | 5 | 1 |
| 20 | gateway.py | 2 | 0 |
| 21 | trace.py | 2 | 0 |
| 22 | command.py | 2 | 0 |
| 23 | floor_map.py | 1 | 0 |
| 24 | load_shift.py | 8 | 0 |
| 25 | rollback.py | 1 | 1 |
| 26 | thermal.py | 4 | 0 |
| 27 | notification.py | 1 | 0 |
| 28 | drift.py | 1 | 0 |
| 29 | video.py | 4 | 0 |
| 30 | vpp_data.py | 5 | 1 |
| 31 | ab_test_config.py | 3 | 0 |
| 32 | system.py | 3 | 0 |
| | **合计** | **134** | **8** |

### 按功能域分类

| 功能域 | 模型数 | 包含文件 |
|------|------|------|
| 用户与认证 | 5 | user.py |
| 设备与点位 | 6 | device.py, point.py |
| 告警与阈值 | 7 | alarm.py |
| 历史数据 | 2 | history.py |
| 日志与配置 | 6 | log.py, config.py |
| 能源管理 | 14 | energy.py |
| 资产与容量 | 9 | asset.py, capacity.py |
| 运维管理 | 5 | operation.py |
| 报表系统 | 3 | report.py |
| 制冷系统 | 5 | cooling.py |
| 供配电 | 3 | power.py |
| 空间管理 | 5 | spatial.py |
| 拓扑配置 | 5 | topology_config.py |
| 联动引擎 | 3 | linkage.py |
| 智能诊断 | 10 | diagnosis.py, fault_tree.py |
| 采集与网关 | 2 | gateway.py |
| 数据追溯 | 2 | trace.py |
| 控制指令 | 2 | command.py |
| 楼层图 | 1 | floor_map.py |
| 负荷转移 | 8 | load_shift.py |
| 回退保护 | 1 | rollback.py |
| 热动力学 | 4 | thermal.py |
| 系统通知 | 1 | notification.py |
| 漂移检测 | 1 | drift.py |
| 视频监控 | 4 | video.py |
| VPP 虚拟电厂 | 5 | vpp_data.py |
| A/B 测试 | 3 | ab_test_config.py |
| 控制与授权 | 3 | system.py |

---

*文档生成时间: 2026-03-17 | 项目版本: V4.2.0*
