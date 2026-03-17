# 前端组件清单

生成时间: 2026-03-17
项目版本: V4.2.0
框架: Vue 3.4 + TypeScript 5.9 + Vite + Element Plus

## 概览

| 类别 | 数量 |
|------|------|
| 页面视图 (.vue in views/) | 96 |
| 可复用组件 (.vue in components/) | 90 |
| Pinia Store | 9 |
| API 模块 | 41 |
| 路由 (含组件) | 88 |
| 路由 (重定向兼容) | 58 |
| Composables | 18 |
| 布局组件 | 1 |

---

## 1. 路由结构 (88 组件路由 + 58 重定向)

文件: `frontend/src/router/index.ts`

路由守卫: `beforeEach` 检查 `meta.requiresAuth !== false && !userStore.token` → 跳转 `/login`

### 1.1 顶层路由

| 路径 | 名称 | 组件 | meta |
|------|------|------|------|
| `/login` | Login | `views/login/index.vue` | requiresAuth: false |
| `/bigscreen` | Bigscreen | `views/bigscreen/index.vue` | title: 数字孪生大屏, fullscreen: true, requiresAuth: false |
| `/` | — | `layouts/MainLayout.vue` | redirect: /dashboard |

### 1.2 监控域

#### 综合概览

| 路径 | 名称 | 组件 | meta.title |
|------|------|------|------------|
| `/dashboard` | Dashboard | `views/dashboard/index.vue` | 综合概览 |

#### 供配电监控 (`/power`, redirect → /power/overview)

| 路径 | 名称 | 组件 | meta.title |
|------|------|------|------------|
| `/power/overview` | PowerOverview | `views/power/overview.vue` | 供配电总览 |
| `/power/ups` | PowerUPS | `views/power/ups.vue` | UPS监控 |
| `/power/battery` | PowerBattery | `views/power/battery.vue` | 电池组 |
| `/power/cabinet` | PowerCabinet | `views/power/cabinet.vue` | 配电柜 |
| `/power/pdu` | PowerPDU | `views/power/pdu.vue` | 机柜PDU |
| `/power/topology` | PowerTopology | `views/energy/topology.vue` | 配电拓扑 |

#### 制冷监控 (`/cooling`, redirect → /cooling/overview)

| 路径 | 名称 | 组件 | meta.title |
|------|------|------|------------|
| `/cooling/overview` | CoolingOverview | `views/cooling/overview.vue` | 制冷总览 |
| `/cooling/indoor` | CoolingIndoor | `views/cooling/indoor.vue` | 精密空调 |
| `/cooling/outdoor` | CoolingOutdoor | `views/cooling/outdoor.vue` | 室外机 |
| `/cooling/cold-aisle` | CoolingColdAisle | `views/cooling/cold-aisle.vue` | 冷通道 |
| `/cooling/group-control` | CoolingGroupControl | `views/cooling/group-control.vue` | 群控状态 |

#### 环境监控 (`/environment`, redirect → /environment/overview)

| 路径 | 名称 | 组件 | meta.title |
|------|------|------|------------|
| `/environment/overview` | EnvironmentOverview | `views/environment/overview.vue` | 环境总览 |
| `/environment/temperature` | EnvironmentTemperature | `views/environment/temperature.vue` | 温湿度监测 |
| `/environment/water-leak` | EnvironmentWaterLeak | `views/environment/water-leak.vue` | 水浸检测 |
| `/environment/smoke-infrared` | EnvironmentSmokeInfrared | `views/environment/smoke-infrared.vue` | 烟雾/红外检测 |

#### 安防消防 (`/security`, redirect → /security/overview)

| 路径 | 名称 | 组件 | meta.title |
|------|------|------|------------|
| `/security/overview` | SecurityOverview | `views/security/overview.vue` | 安防总览 |
| `/security/access-control` | SecurityAccessControl | `views/security/access-control.vue` | 门禁管理 |
| `/security/video/cameras` | VideoCameras | `views/video/index.vue` | 摄像头管理 |
| `/security/video/control` | VideoControl | `views/video/control.vue` | 视频控制 |
| `/security/video/playback` | VideoPlayback | `views/video/playback.vue` | 告警回放 |
| `/security/fire-linkage` | SecurityFireLinkage | `views/security/fire-linkage.vue` | 消防联动 |

#### 告警中心

| 路径 | 名称 | 组件 | meta.title |
|------|------|------|------------|
| `/alarms` | Alarms | `views/alarm/index.vue` | 告警中心 |

### 1.3 管理域

#### 能效管理 (`/energy`, redirect → /energy/monitor)

| 路径 | 名称 | 组件 | meta.title |
|------|------|------|------------|
| `/energy/monitor` | EnergyMonitor | `views/energy/monitor.vue` | 用电监控 |
| `/energy/statistics` | EnergyStatistics | `views/energy/statistics.vue` | 能耗统计 |
| `/energy/analysis` | EnergyAnalysis | `views/energy/analysis.vue` | 节能分析 |
| `/energy/regulation` | EnergyRegulation | `views/energy/regulation.vue` | 负荷调节 |
| `/energy/execution` | EnergyExecution | `views/energy/execution.vue` | 执行管理 |
| `/energy/report` | EnergyReport | `views/energy/report.vue` | 能效报告 |

#### 负荷转移 (`/energy/shift`, redirect → /energy/shift/dashboard)

| 路径 | 名称 | 组件 | meta.title |
|------|------|------|------------|
| `/energy/shift/dashboard` | ShiftDashboard | `views/energy/shift/ShiftDashboard.vue` | 转移仪表盘 |
| `/energy/shift/list` | ShiftPlanList | `views/energy/shift/ShiftPlanList.vue` | 计划列表 |
| `/energy/shift/create` | ShiftPlanCreate | `views/energy/shift/ShiftPlanCreate.vue` | 新建计划 |
| `/energy/shift/edit/:id` | ShiftPlanEdit | `views/energy/shift/ShiftPlanCreate.vue` | 编辑计划 (hidden) |
| `/energy/shift/detail/:id` | ShiftPlanDetail | `views/energy/shift/ShiftPlanDetail.vue` | 计划详情 (hidden) |
| `/energy/shift/opportunities` | ShiftOpportunityList | `views/energy/shift/ShiftOpportunityList.vue` | 转移机会 |
| `/energy/shift/opportunity/:id` | ShiftOpportunityDetail | `views/energy/shift/ShiftOpportunityDetail.vue` | 机会详情 (hidden) |
| `/energy/shift/executions` | ShiftExecutionList | `views/energy/shift/ShiftExecutionList.vue` | 执行记录 |
| `/energy/shift/execution/:id` | ShiftExecutionDetail | `views/energy/shift/ShiftExecutionDetail.vue` | 执行详情 (hidden) |
| `/energy/shift/monitor/:id` | ShiftExecutionMonitor | `views/energy/shift/ShiftExecutionMonitor.vue` | 实时监控 (hidden) |
| `/energy/shift/cooling-config` | CoolingLinkageConfig | `views/energy/shift/CoolingLinkageConfig.vue` | 制冷联动配置 |
| `/energy/shift/cooling-monitor` | CoolingLinkageMonitor | `views/energy/shift/CoolingLinkageMonitor.vue` | 制冷状态监控 |
| `/energy/shift/constraints` | ShiftConstraintConfig | `views/energy/shift/ShiftConstraintConfig.vue` | 约束管理 |
| `/energy/shift/reports` | ShiftReports | `views/energy/shift/ShiftReports.vue` | 收益报表 |
| `/energy/shift/precool-schedule` | PrecoolSchedule | `views/energy/shift/PrecoolScheduleView.vue` | 预冷计划 |
| `/energy/shift/deployment` | DeploymentPhase | `views/energy/shift/DeploymentPhaseView.vue` | 部署管理 |
| `/energy/shift/vpp-monitor` | VppMonitor | `views/energy/shift/VppMonitorView.vue` | VPP 集成监控 |

#### 资产与容量 (`/asset`, redirect → /asset/list)

| 路径 | 名称 | 组件 | meta.title |
|------|------|------|------------|
| `/asset/list` | AssetList | `views/asset/index.vue` | 资产台账 |
| `/asset/cabinet` | AssetCabinet | `views/asset/cabinet.vue` | 机柜管理 |
| `/asset/capacity` | AssetCapacity | `views/capacity/index.vue` | 容量管理 |
| `/asset/spatial` | AssetSpatial | `views/topology/spatial.vue` | 空间拓扑 |

#### 运维管理 (`/operation`, redirect → /operation/workorder)

| 路径 | 名称 | 组件 | meta.title |
|------|------|------|------------|
| `/operation/workorder` | WorkOrder | `views/operation/workorder.vue` | 工单管理 |
| `/operation/inspection` | Inspection | `views/operation/inspection.vue` | 巡检管理 |
| `/operation/knowledge` | Knowledge | `views/operation/knowledge.vue` | 知识库 |
| `/operation/reports` | Reports | `views/report/index.vue` | 报表分析 |
| `/operation/history` | History | `views/history/index.vue` | 历史数据 |

#### 虚拟电厂 (`/vpp`, redirect → /vpp/analysis)

| 路径 | 名称 | 组件 | meta.title |
|------|------|------|------------|
| `/vpp/analysis` | VPPAnalysis | `views/vpp/VPPAnalysis.vue` | VPP方案分析 |

### 1.4 配置域

#### 采集配置 (`/collection`, redirect → /collection/device-manage)

| 路径 | 名称 | 组件 | meta.title |
|------|------|------|------------|
| `/collection/device-manage` | DeviceManage | `views/device-manage/index.vue` | 设备管理 |
| `/collection/device-manage/detail/:id` | DeviceDetail | `views/device-manage/detail.vue` | 设备详情 (hidden) |
| `/collection/device-status` | DeviceStatus | `views/device-status/index.vue` | 设备状态看板 |
| `/collection/devices` | Devices | `views/device/index.vue` | 点位管理 |
| `/collection/datasources` | Datasources | `views/datasource/index.vue` | 数据源管理 |
| `/collection/device-templates` | DeviceTemplates | `views/device-template/index.vue` | 设备模板 |
| `/collection/power-config` | PowerConfig | `views/energy/config.vue` | 配电配置 |
| `/collection/gateway` | Gateway | `views/gateway/index.vue` | 网关管理 |
| `/collection/drift` | CollectionDrift | `views/linkage/drift.vue` | 漂移检测 |

#### 策略引擎 (`/strategy`, redirect → /strategy/linkage/policy)

**告警规则** (`/strategy/alarm-rules`, redirect → thresholds)

| 路径 | 名称 | 组件 | meta.title |
|------|------|------|------------|
| `/strategy/alarm-rules/thresholds` | AlarmThresholds | `views/alarm/thresholds.vue` | 阈值配置 |
| `/strategy/alarm-rules/compound` | AlarmCompound | `views/alarm/compound.vue` | 复合规则 |
| `/strategy/alarm-rules/escalation` | AlarmEscalation | `views/alarm/escalation.vue` | 升级规则 |
| `/strategy/alarm-rules/shield` | AlarmShield | `views/alarm/shield.vue` | 告警屏蔽 |

**联动策略** (`/strategy/linkage`, redirect → policy)

| 路径 | 名称 | 组件 | meta.title |
|------|------|------|------------|
| `/strategy/linkage/policy` | LinkagePolicy | `views/linkage/policy.vue` | 联动策略 |
| `/strategy/linkage/execution` | LinkageExecution | `views/linkage/execution.vue` | 执行日志 |
| `/strategy/linkage/recovery` | LinkageRecovery | `views/linkage/recovery.vue` | 联动恢复 |
| `/strategy/linkage/timeline` | LinkageTimeline | `views/linkage/timeline.vue` | 事件时间线 |
| `/strategy/linkage/command` | LinkageCommand | `views/linkage/command.vue` | 命令管理 |

**智能诊断** (`/strategy/diagnosis`, redirect → results)

| 路径 | 名称 | 组件 | meta.title |
|------|------|------|------------|
| `/strategy/diagnosis/results` | DiagnosisResults | `views/diagnosis/results.vue` | 诊断结果 |
| `/strategy/diagnosis/rules` | DiagnosisRules | `views/diagnosis/rules.vue` | 诊断规则 |
| `/strategy/diagnosis/reports` | DiagnosisReports | `views/diagnosis/Reports.vue` | 误诊报告 |
| `/strategy/diagnosis/time-window-tuning` | TimeWindowTuning | `views/diagnosis/TimeWindowTuning.vue` | 时间窗口调参 |
| `/strategy/diagnosis/probability-tuning` | ProbabilityTuning | `views/diagnosis/ProbabilityTuning.vue` | 概率调参 |
| `/strategy/diagnosis/fault-trees/:id/editor` | FaultTreeEditor | `views/diagnosis/FaultTreeEditor.vue` | 故障树编辑器 (hidden) |

**漂移重定向**: `/strategy/drift` → `/collection/drift`

#### 系统管理 (`/system`, redirect → /system/users)

| 路径 | 名称 | 组件 | meta.title |
|------|------|------|------------|
| `/system/users` | UserManagement | `views/system/user.vue` | 用户管理 |
| `/system/sites` | SiteManagement | `views/system/sites.vue` | 站点管理 |
| `/system/audit-log` | AuditLog | `views/system/audit-log.vue` | 操作审计 |
| `/system/settings` | SystemSettings | `views/settings/index.vue` | 系统设置 |
| `/system/site-selection` | SiteSelection | `views/topology/site-selection.vue` | 智能选址 |

### 1.5 旧路由兼容重定向 (40 条)

| 旧路径 | 重定向目标 |
|--------|-----------|
| `/power/monitor` | `/energy/monitor` |
| `/power/statistics` | `/energy/statistics` |
| `/power/config` | `/collection/power-config` |
| `/energy-saving/analysis` | `/energy/analysis` |
| `/energy-saving/regulation` | `/energy/regulation` |
| `/energy-saving/execution` | `/energy/execution` |
| `/energy-saving` | `/energy/monitor` |
| `/infrastructure/asset` | `/asset/list` |
| `/infrastructure/cabinet` | `/asset/cabinet` |
| `/infrastructure/capacity` | `/asset/capacity` |
| `/infrastructure/spatial` | `/asset/spatial` |
| `/infrastructure/power-topology` | `/collection/power-config` |
| `/infrastructure/cooling-topology` | `/collection/power-config` |
| `/infrastructure/site-selection` | `/system/site-selection` |
| `/infrastructure/fault-impact` | `/asset/capacity` |
| `/infrastructure` | `/asset/list` |
| `/devices` | `/collection/devices` |
| `/datasources` | `/collection/datasources` |
| `/device-templates` | `/collection/device-templates` |
| `/device-manage` | `/collection/device-manage` |
| `/device-status` | `/collection/device-status` |
| `/history` | `/operation/history` |
| `/reports` | `/operation/reports` |
| `/settings` | `/system/settings` |
| `/linkage/policy` | `/strategy/linkage/policy` |
| `/linkage/execution` | `/strategy/linkage/execution` |
| `/linkage/recovery` | `/strategy/linkage/recovery` |
| `/linkage/timeline` | `/strategy/linkage/timeline` |
| `/linkage/command` | `/strategy/linkage/command` |
| `/linkage` | `/strategy/linkage/policy` |
| `/diagnosis/results` | `/strategy/diagnosis/results` |
| `/diagnosis/rules` | `/strategy/diagnosis/rules` |
| `/diagnosis` | `/strategy/diagnosis/results` |
| `/video/cameras` | `/security/video/cameras` |
| `/video/control` | `/security/video/control` |
| `/video/playback` | `/security/video/playback` |
| `/video` | `/security/video/cameras` |
| `/energy/config` | `/collection/power-config` |
| `/energy/topology` | `/power/topology` |
| `/capacity` | `/asset/capacity` |

---

## 2. Pinia 状态管理 (9 stores)

文件: `frontend/src/stores/index.ts` 统一导出

### 2.1 useUserStore (`user`)

用途: 用户认证、权限管理

| 类型 | 名称 | 说明 |
|------|------|------|
| State | token | JWT token (localStorage 持久化) |
| State | userInfo | 用户信息 (UserInfo) |
| State | permissions | 权限列表 string[] |
| Getter | isLoggedIn | 是否已登录 |
| Getter | isAdmin | 是否管理员 |
| Getter | isOperator | 是否操作员 (admin/operator) |
| Getter | role / username / realName | 角色/用户名/真实姓名 |
| Action | doLogin(username, password) | 登录 → 存 token → fetchUserInfo + fetchPermissions |
| Action | doLogout() | 登出 → 清除 token/userInfo/permissions |
| Action | fetchUserInfo() | 获取当前用户信息 |
| Action | fetchPermissions() | 获取权限列表 |
| Action | hasPermission(perm) | 检查单个权限 |
| Action | hasAnyPermission(perms) | 检查任意权限 |
| Action | initFromStorage() | 从 localStorage 恢复 token 并拉取用户信息 |
| API 调用 | auth.login / auth.logout / auth.getCurrentUser / auth.getPermissions | |

### 2.2 useAppStore (`app`)

用途: 应用全局 UI 状态

| 类型 | 名称 | 说明 |
|------|------|------|
| State | sidebarCollapsed | 侧边栏折叠 |
| State | theme | 主题 light/dark |
| State | language | 语言 zh-CN/en-US |
| State | alarmSoundEnabled | 告警声音开关 |
| State | alarmPopupEnabled | 告警弹窗开关 |
| State | refreshInterval | 数据刷新间隔(秒) |
| State | isFullscreen | 全屏模式 |
| State | globalLoading / loadingText | 全局加载状态 |
| State | breadcrumbs | 面包屑 |
| State | tabs / activeTab | 标签页 |
| Getter | settings | 所有设置的计算属性 |
| Action | toggleSidebar / setSidebarCollapsed | 侧边栏控制 |
| Action | toggleTheme / setTheme | 主题切换 |
| Action | setLanguage | 语言设置 |
| Action | toggleAlarmSound / toggleAlarmPopup | 告警设置 |
| Action | setRefreshInterval | 刷新间隔 |
| Action | showLoading / hideLoading | 全局加载 |
| Action | setBreadcrumbs | 面包屑 |
| Action | addTab / removeTab | 标签页管理 |
| Action | initFromStorage | 从 localStorage 恢复所有设置 |

### 2.3 useAlarmStore (`alarm`)

用途: 活跃告警管理, WebSocket 推送消费

| 类型 | 名称 | 说明 |
|------|------|------|
| State | activeAlarms | 活跃告警列表 Alarm[] |
| State | alarmCount | 按级别统计 {critical, major, minor, info, total} |
| State | loading | 加载状态 |
| Action | fetchActiveAlarms() | 从 API 加载活跃告警 (版本号防竞态) |
| Action | addAlarm(alarm) | 添加告警 (去重, 限制1000条) |
| Action | removeAlarm(id) | 移除告警 |
| Action | updateAlarm(id, fields) | 更新告警字段, resolved 自动移除 |
| 站点切换 | siteEvents.on → fetchActiveAlarms | 站点切换时重新加载 |
| API 调用 | alarm.getActiveAlarms | |

### 2.4 useRealtimeStore (`realtime`)

用途: 实时点位数据 SSOT (Story 27.2)

| 类型 | 名称 | 说明 |
|------|------|------|
| State | dataMap | Map<number, RealtimeData> 点位数据映射 |
| State | summary | RealtimeSummary 汇总 |
| State | lastUpdateTime | 最后更新时间 |
| State | wsConnected | WebSocket 连接状态 |
| State | loading | 加载状态 |
| Getter | realtimeData | dataMap 转数组 |
| Getter | totalPoints / alarmCount / offlineCount | 统计 |
| Getter | alarmPoints / offlinePoints | 过滤列表 |
| Getter | simpleSummary | 简化汇总 {total, normal, alarm, offline} |
| Action | fetchAllData(pointIds?) | API 加载全量数据 (版本号防竞态) |
| Action | fetchSummary() | 加载汇总 |
| Action | reload() | 加载全部 (数据+汇总) |
| Action | updatePoint(data) | 单点更新 (WS 推送) |
| Action | updatePoints(data[]) | 批量更新 (WS 批量推送) |
| Action | setAllData(data[]) | 整体替换 |
| Action | getPointData(pointId) | 获取单点 |
| Action | getDataByType(type) / getDataByArea(area) | 按类型/区域过滤 |
| Action | groupByArea(deviceType?) | 按区域分组 (Story 27.8) |
| Action | clearData() | 清空 |
| 站点切换 | siteEvents.on → reload | 站点切换时重新加载 |
| API 调用 | realtime.getAllRealtimeData / realtime.getRealtimeSummary | |

### 2.5 useEnergyStore (`energy`)

用途: 用电管理数据 SSOT (Story 27.3)

| 类型 | 名称 | 说明 |
|------|------|------|
| State | realtimePowerData | Map<number, RealtimePowerData> |
| State | powerSummary | 电力汇总 |
| State | pueData | PUE 数据 |
| State | suggestions | 节能建议列表 |
| State | distributionDiagram | 配电图 |
| State | lastUpdateTime / wsConnected / loading | 状态标志 |
| Getter | powerDataList / currentPUE / totalPower | 电力计算 |
| Getter | itPower / coolingPower | IT/制冷功率 |
| Getter | todayEnergy / todayCost / monthEnergy / monthCost | 能耗/费用 |
| Getter | pendingCount / highPrioritySuggestions | 建议统计 |
| Action | updatePowerData / updatePowerDataBatch / setAllPowerData | 电力数据更新 |
| Action | setPowerSummary / setPUEData / setSuggestions | 设置数据 |
| Action | addSuggestion / updateSuggestionStatus | 建议管理 |
| Action | reload() | 并发加载 (电力+汇总+PUE, 版本号防竞态) |
| Action | clearData() | 清空 |
| 站点切换 | siteEvents.on → reload | 站点切换时重新加载 |
| API 调用 | energy.getRealtimePower / energy.getPowerSummary / energy.getCurrentPUE | |

### 2.6 useOpportunityStore (`opportunity`)

用途: 节能机会管理 (V2.5)

| 类型 | 名称 | 说明 |
|------|------|------|
| State | dashboard | 仪表盘数据 DashboardResponse |
| State | opportunities / opportunitiesTotal | 机会列表 + 总数 |
| State | currentOpportunity | 当前选中机会 |
| State | simulationResult | 模拟结果 |
| State | availableDevices / selectedDeviceIds | 可选设备 + 已选设备 |
| State | executionPlans / plansTotal | 执行计划列表 |
| State | currentPlan / executionStats | 当前计划 + 执行统计 |
| Getter | pendingCount / executingCount | 待处理/执行中数量 |
| Getter | annualPotentialSaving / monthlyActualSaving | 年度潜在/月度实际节省 |
| Getter | opportunitiesByCategory / highPriorityOpportunities | 分类/高优先级 |
| Getter | totalSelectedPower / currentPlanProgress | 选中功率/计划进度 |
| Action | loadDashboard / loadOpportunities / loadOpportunityDetail | 加载数据 |
| Action | loadAvailableDevices / toggleDeviceSelection / selectAllDevices | 设备选择 |
| Action | loadExecutionPlans / loadPlanDetail / loadExecutionStats | 执行计划 |
| Action | updateTaskStatus / getCategoryName / getCategoryKey | 任务/分类 |
| Action | clearData / clearCurrentSelection | 清空 |
| API 调用 | opportunities.* (dashboard/list/detail/plans/stats/devices) | |

### 2.7 useBigscreenStore (`bigscreen`)

用途: 3D 数字孪生大屏状态 (Story 27.10 setup API)

| 类型 | 名称 | 说明 |
|------|------|------|
| State | mode | 场景模式 SceneMode (command/operation/showcase) |
| State | layout | 数据中心布局 DataCenterLayout |
| State | deviceData | 设备实时数据 Record<string, DeviceRealtimeData> |
| State | layers | 数据图层开关 {heatmap, status, power, airflow} |
| State | selectedDeviceId | 选中设备 |
| State | cameraPresets | 相机预设 (overview/topDown/moduleA) |
| State | panelStates | 面板状态 (位置/折叠/可见) |
| Getter | activeAlarms / alarmCount / criticalAlarmCount | 从 alarmStore 聚合 |
| Getter | recentAlarms | 最近10条告警 |
| Getter | energy | 从 energyStore 聚合 (totalPower/itPower/pue等) |
| Getter | environment | 从 realtimeStore 聚合温湿度 (max/avg/min) |
| Getter | modeConfig | 模式配置 (刷新间隔/面板显示) |
| Action | setMode / setLayout / selectDevice | 模式/布局/设备 |
| Action | updateDeviceData / updateAllDeviceData | 设备数据更新 |
| Action | toggleLayer | 图层开关 |
| Action | updatePanelPosition / updatePanelCollapsed / togglePanelVisible | 面板控制 |
| Action | savePanelStates / loadPanelStates / resetPanelStates | 面板持久化 |
| 跨 Store | 依赖 alarmStore + energyStore + realtimeStore | |

### 2.8 useDegradationStore (`degradation`)

用途: 优雅降级状态管理 (Story 4.5)

| 类型 | 名称 | 说明 |
|------|------|------|
| State | redisDown | Redis 降级标志 |
| State | websocketDown | WebSocket 降级标志 |
| State | mqttDown | MQTT 降级标志 |
| State | degradedMessage | 降级消息 |
| Getter | hasDegradation | 是否有任何降级 |
| Action | setRedisDown / setWebsocketDown / setMqttDown | 设置降级状态 |
| Action | syncFromFlags() | 从 degradationFlags 同步 (供组件 onMounted) |
| 特殊 | degradationFlags (reactive) | 独立响应式标志, 可在 Pinia 初始化前写入 |

### 2.9 useSiteStore (`site`)

用途: 多站点切换管理

| 类型 | 名称 | 说明 |
|------|------|------|
| State | currentSiteId | 当前站点 ID (localStorage 持久化) |
| State | sites | 站点列表 Site[] |
| State | summary | 站点汇总 SiteSummaryResponse |
| State | loading | 加载状态 |
| Getter | currentSite | 当前站点对象 |
| Getter | currentSiteName | 当前站点名称 (默认 "全部站点") |
| Action | fetchSites() | 获取站点列表 |
| Action | fetchSummary() | 获取站点汇总 |
| Action | switchSite(siteId) | 切换站点 → siteEvents.emit 通知所有订阅者 |
| API 调用 | spatial.getSites / spatial.getSiteSummary | |

---

## 3. 页面视图 (96 views)

目录: `frontend/src/views/`

### 3.1 dashboard/ (1)

| 组件 | 用途 |
|------|------|
| `index.vue` | 综合概览仪表盘, 系统总览 |

### 3.2 login/ (1)

| 组件 | 用途 |
|------|------|
| `index.vue` | 用户登录页 |

### 3.3 bigscreen/ (1)

| 组件 | 用途 |
|------|------|
| `index.vue` | 3D 数字孪生大屏, Three.js 场景 |

### 3.4 power/ (5)

| 组件 | 用途 |
|------|------|
| `overview.vue` | 供配电总览 |
| `ups.vue` | UPS 监控 |
| `battery.vue` | 电池组监控 |
| `cabinet.vue` | 配电柜监控 |
| `pdu.vue` | 机柜 PDU 监控 |

### 3.5 cooling/ (5)

| 组件 | 用途 |
|------|------|
| `overview.vue` | 制冷总览 |
| `indoor.vue` | 精密空调监控 |
| `outdoor.vue` | 室外机监控 |
| `cold-aisle.vue` | 冷通道监控 |
| `group-control.vue` | 群控状态 |

### 3.6 environment/ (4)

| 组件 | 用途 |
|------|------|
| `overview.vue` | 环境总览 |
| `temperature.vue` | 温湿度监测 |
| `water-leak.vue` | 水浸检测 |
| `smoke-infrared.vue` | 烟雾/红外检测 |

### 3.7 security/ (3)

| 组件 | 用途 |
|------|------|
| `overview.vue` | 安防总览 |
| `access-control.vue` | 门禁管理 |
| `fire-linkage.vue` | 消防联动 |

### 3.8 video/ (3)

| 组件 | 用途 |
|------|------|
| `index.vue` | 摄像头管理 |
| `control.vue` | 视频控制 (PTZ) |
| `playback.vue` | 告警回放 |

### 3.9 alarm/ (6)

| 组件 | 用途 |
|------|------|
| `index.vue` | 告警中心主页 |
| `thresholds.vue` | 阈值配置 |
| `compound.vue` | 复合告警规则 |
| `CompoundConditionGroup.vue` | 复合条件组子组件 |
| `escalation.vue` | 告警升级规则 |
| `shield.vue` | 告警屏蔽管理 |

### 3.10 energy/ (28)

**根目录 (7)**

| 组件 | 用途 |
|------|------|
| `monitor.vue` | 用电监控 |
| `statistics.vue` | 能耗统计 |
| `analysis.vue` | 节能分析 (6 插件) |
| `regulation.vue` | 负荷调节 |
| `execution.vue` | 执行管理 |
| `report.vue` | 能效报告 |
| `config.vue` | 配电配置 |
| `topology.vue` | 配电拓扑 |
| `suggestions.vue` | 节能建议 |

**shift/ 子目录 (16 + 3 子组件)**

| 组件 | 用途 |
|------|------|
| `ShiftDashboard.vue` | 负荷转移仪表盘 |
| `ShiftPlanList.vue` | 转移计划列表 |
| `ShiftPlanCreate.vue` | 新建/编辑转移计划 |
| `ShiftPlanDetail.vue` | 计划详情 |
| `ShiftOpportunityList.vue` | 转移机会列表 |
| `ShiftOpportunityDetail.vue` | 机会详情 |
| `ShiftExecutionList.vue` | 执行记录列表 |
| `ShiftExecutionDetail.vue` | 执行详情 |
| `ShiftExecutionMonitor.vue` | 实时监控 |
| `CoolingLinkageConfig.vue` | 制冷联动配置 |
| `CoolingLinkageMonitor.vue` | 制冷状态监控 |
| `ShiftConstraintConfig.vue` | 约束管理 |
| `ShiftReports.vue` | 收益报表 |
| `PrecoolScheduleView.vue` | 预冷计划 |
| `DeploymentPhaseView.vue` | 部署管理 |
| `VppMonitorView.vue` | VPP 集成监控 |
| `components/ConstraintCheckResult.vue` | 约束检查结果子组件 |
| `components/DeviceSelector.vue` | 设备选择器子组件 |
| `components/ExecutionProgress.vue` | 执行进度子组件 |

### 3.11 linkage/ (6)

| 组件 | 用途 |
|------|------|
| `policy.vue` | 联动策略管理 |
| `execution.vue` | 联动执行日志 |
| `recovery.vue` | 联动恢复 |
| `timeline.vue` | 事件时间线 |
| `command.vue` | 命令管理 |
| `drift.vue` | 漂移检测 |

### 3.12 diagnosis/ (6)

| 组件 | 用途 |
|------|------|
| `results.vue` | 诊断结果列表 |
| `rules.vue` | 诊断规则管理 |
| `Reports.vue` | 误诊报告 |
| `TimeWindowTuning.vue` | 时间窗口调参 |
| `ProbabilityTuning.vue` | 概率调参 |
| `FaultTreeEditor.vue` | 故障树编辑器 |

### 3.13 asset/ (2)

| 组件 | 用途 |
|------|------|
| `index.vue` | 资产台账 |
| `cabinet.vue` | 机柜管理 |

### 3.14 capacity/ (1)

| 组件 | 用途 |
|------|------|
| `index.vue` | 容量管理 |

### 3.15 operation/ (3)

| 组件 | 用途 |
|------|------|
| `workorder.vue` | 工单管理 |
| `inspection.vue` | 巡检管理 |
| `knowledge.vue` | 知识库 |

### 3.16 report/ (1)

| 组件 | 用途 |
|------|------|
| `index.vue` | 报表分析 |

### 3.17 history/ (1)

| 组件 | 用途 |
|------|------|
| `index.vue` | 历史数据查询 |

### 3.18 topology/ (5)

| 组件 | 用途 |
|------|------|
| `spatial.vue` | 空间拓扑 |
| `power.vue` | 配电拓扑 |
| `cooling.vue` | 制冷拓扑 |
| `fault-impact.vue` | 故障影响分析 |
| `site-selection.vue` | 智能选址 |

### 3.19 device-manage/ (2)

| 组件 | 用途 |
|------|------|
| `index.vue` | 设备管理列表 |
| `detail.vue` | 设备详情 |

### 3.20 device/ (1), device-status/ (1), device-template/ (1), datasource/ (1)

| 组件 | 用途 |
|------|------|
| `device/index.vue` | 点位管理 |
| `device-status/index.vue` | 设备状态看板 |
| `device-template/index.vue` | 设备模板管理 |
| `datasource/index.vue` | 数据源管理 |

### 3.21 gateway/ (2)

| 组件 | 用途 |
|------|------|
| `index.vue` | 网关管理列表 |
| `GatewayConfigDialog.vue` | 网关配置对话框 |

### 3.22 system/ (3)

| 组件 | 用途 |
|------|------|
| `user.vue` | 用户管理 |
| `sites.vue` | 站点管理 |
| `audit-log.vue` | 操作审计日志 |

### 3.23 settings/ (2)

| 组件 | 用途 |
|------|------|
| `index.vue` | 系统设置 |
| `UserManagement.vue` | 用户管理 (旧) |

### 3.24 vpp/ (1)

| 组件 | 用途 |
|------|------|
| `VPPAnalysis.vue` | VPP 方案分析 |

---

## 4. 可复用组件 (90 components)

目录: `frontend/src/components/`

### 4.1 根目录 (2)

| 组件 | 用途 |
|------|------|
| `DemoDataLoader.vue` | Demo 数据加载器 |
| `MetricDisplay.vue` | 指标展示卡片 |

### 4.2 common/ (11)

| 组件 | 用途 |
|------|------|
| `AlarmSoundToggle.vue` | 告警声音开关按钮 |
| `ConfirmDialog.vue` | 通用确认对话框 |
| `DataQualityTag.vue` | 数据质量标签 |
| `DataTable.vue` | 通用数据表格 |
| `DateRangePicker.vue` | 日期范围选择器 |
| `DegradationBanner.vue` | 降级状态横幅 (Story 4.5) |
| `DeleteConfirmDialog.vue` | 删除确认对话框 |
| `ExportButton.vue` | 导出按钮 |
| `SearchForm.vue` | 通用搜索表单 |
| `SiteSwitcher.vue` | 站点切换器 |
| `StatusTag.vue` | 状态标签 |

### 4.3 charts/ (6)

| 组件 | 用途 |
|------|------|
| `BarChart.vue` | 柱状图 (ECharts) |
| `GaugeChart.vue` | 仪表盘图 |
| `LineChart.vue` | 折线图 |
| `PieChart.vue` | 饼图 |
| `RealtimeChart.vue` | 实时数据图表 |
| `Sparkline.vue` | 迷你趋势线 |

### 4.4 monitor/ (4)

| 组件 | 用途 |
|------|------|
| `AlarmBadge.vue` | 告警徽章 |
| `PointCard.vue` | 点位卡片 |
| `StatusPanel.vue` | 状态面板 |
| `ValueDisplay.vue` | 数值展示 |

### 4.5 energy/ (30)

**根目录 (28)**

| 组件 | 用途 |
|------|------|
| `CalculationDetails.vue` | 计算详情展示 |
| `CostCard.vue` | 费用卡片 |
| `DemandDashboard.vue` | 需量仪表盘 |
| `DemandStatusCard.vue` | 需量状态卡片 |
| `DeviceList.vue` | 设备列表 |
| `DevicePowerCurveChart.vue` | 设备功率曲线图 |
| `DeviceShiftDetailDrawer.vue` | 设备转移详情抽屉 |
| `DispatchConfig.vue` | 调度配置 |
| `EnergySuggestionCard.vue` | 节能建议卡片 |
| `ExecutionPlanDialog.vue` | 执行计划对话框 |
| `InteractivePowerCard.vue` | 交互式功率卡片 |
| `LoadComparisonChart.vue` | 负荷对比图 |
| `OptimizationOverview.vue` | 优化总览 |
| `OptimizationReport.vue` | 优化报告 |
| `PUEGauge.vue` | PUE 仪表盘 |
| `PUEIndicatorCard.vue` | PUE 指标卡片 |
| `ParameterAdjustment.vue` | 参数调整 |
| `PowerCard.vue` | 功率卡片 |
| `PrecoolTimeline.vue` | 预冷时间线 |
| `PricingSchemeManager.vue` | 电价方案管理 |
| `PricingTimeline.vue` | 电价时间线 |
| `RollbackStatusCard.vue` | 回滚状态卡片 |
| `RollbackTimeline.vue` | 回滚时间线 |
| `ScheduleDashboard.vue` | 调度仪表盘 |
| `ShiftPlanBuilder.vue` | 转移计划构建器 |
| `SuggestionDetailDrawer.vue` | 建议详情抽屉 |
| `SuggestionOverview.vue` | 建议总览 |
| `SuggestionsCard.vue` | 建议卡片 |
| `TemperaturePredictionChart.vue` | 温度预测图 |

**shift/ 子目录 (1)**

| 组件 | 用途 |
|------|------|
| `ConstraintEditor.vue` | 约束编辑器 |

### 4.6 demand/ (3)

| 组件 | 用途 |
|------|------|
| `DemandComparisonCard.vue` | 需量对比卡片 |
| `DemandCurveMini.vue` | 需量曲线迷你图 |
| `LoadPeriodChart.vue` | 负荷时段图 |

### 4.7 diagnosis/ (5)

| 组件 | 用途 |
|------|------|
| `AnnotationDialog.vue` | 诊断标注对话框 |
| `CounterfactualExplanation.vue` | 反事实解释 |
| `FaultTreeCanvas.vue` | 故障树画布 |
| `NodePropertiesPanel.vue` | 节点属性面板 |
| `NodeToolbar.vue` | 节点工具栏 |

### 4.8 bigscreen/ (21)

**根目录 (10)**

| 组件 | 用途 |
|------|------|
| `AlarmBubbles.vue` | 告警气泡动画 |
| `BigscreenFloor3D.vue` | 3D 楼层视图 |
| `BigscreenHistoryDialog.vue` | 历史数据对话框 |
| `CabinetLabels.vue` | 机柜标签 |
| `DataCenterModel.vue` | 数据中心 3D 模型 |
| `DeviceDetailPanel.vue` | 设备详情面板 |
| `Floor2DView.vue` | 2D 楼层视图 |
| `FloorSelector.vue` | 楼层选择器 |
| `HeatmapOverlay.vue` | 热力图叠加层 |
| `ThreeScene.vue` | Three.js 场景容器 |

**charts/ (5)**

| 组件 | 用途 |
|------|------|
| `BaseChart.vue` | 大屏基础图表 |
| `GaugeChart.vue` | 大屏仪表盘图 |
| `PowerDistribution.vue` | 功率分布图 |
| `PueTrend.vue` | PUE 趋势图 |
| `TemperatureTrend.vue` | 温度趋势图 |

**panels/ (2)**

| 组件 | 用途 |
|------|------|
| `LeftPanel.vue` | 大屏左侧面板 |
| `RightPanel.vue` | 大屏右侧面板 |

**ui/ (4)**

| 组件 | 用途 |
|------|------|
| `ContextMenu.vue` | 右键菜单 |
| `DigitalFlop.vue` | 数字翻牌器 |
| `DraggablePanel.vue` | 可拖拽面板 |
| `ThemeSelector.vue` | 主题选择器 |

### 4.9 floor-layouts/ (6)

| 组件 | 用途 |
|------|------|
| `FloorLayoutBase.vue` | 楼层布局基础组件 |
| `FloorLayoutSelector.vue` | 楼层布局选择器 |
| `FloorB1Layout.vue` | B1 层布局 |
| `FloorF1Layout.vue` | F1 层布局 |
| `FloorF2Layout.vue` | F2 层布局 |
| `FloorF3Layout.vue` | F3 层布局 |

### 4.10 asset/ (1)

| 组件 | 用途 |
|------|------|
| `LifecycleTimeline.vue` | 资产生命周期时间线 |

### 4.11 video/ (1)

| 组件 | 用途 |
|------|------|
| `VideoPopup.vue` | 视频弹窗播放器 |

---

## 5. API 模块 (41 modules)

目录: `frontend/src/api/modules/`

### 5.1 alarm.ts — 告警管理 (27 函数)

| 函数 | 方法 | 路径 |
|------|------|------|
| getAlarmList | GET | /api/v1/alarms |
| getActiveAlarms | GET | /api/v1/alarms/active |
| getAlarmById | GET | /api/v1/alarms/:id |
| acknowledgeAlarm | POST | /api/v1/alarms/:id/acknowledge |
| resolveAlarm | POST | /api/v1/alarms/:id/resolve |
| processAlarm | POST | /api/v1/alarms/:id/process |
| batchAcknowledgeAlarms | POST | /api/v1/alarms/batch-acknowledge |
| getAlarmCount | GET | /api/v1/alarms/count |
| getAlarmStatistics | GET | /api/v1/alarms/statistics |
| getAlarmTrend | GET | /api/v1/alarms/trend |
| getTopAlarmPoints | GET | /api/v1/alarms/top-points |
| exportAlarms | GET | /api/v1/alarms/export |
| getAlarmRules | GET | /api/v1/alarm-rules |
| createAlarmRule | POST | /api/v1/alarm-rules |
| getAlarmRuleById | GET | /api/v1/alarm-rules/:id |
| updateAlarmRule | PUT | /api/v1/alarm-rules/:id |
| deleteAlarmRule | DELETE | /api/v1/alarm-rules/:id |
| toggleAlarmRule | POST | /api/v1/alarm-rules/:id/toggle |
| getAlarmShields | GET | /api/v1/alarm-shields |
| createAlarmShield | POST | /api/v1/alarm-shields |
| deleteAlarmShield | DELETE | /api/v1/alarm-shields/:id |
| getEscalations | GET | /api/v1/alarm-escalations |
| createEscalation | POST | /api/v1/alarm-escalations |
| getEscalation | GET | /api/v1/alarm-escalations/:id |
| updateEscalation | PUT | /api/v1/alarm-escalations/:id |
| deleteEscalation | DELETE | /api/v1/alarm-escalations/:id |
| toggleEscalation | POST | /api/v1/alarm-escalations/:id/toggle |

### 5.2 asset.ts — 资产管理 (22 函数)

| 函数 | 说明 |
|------|------|
| getCabinets / getCabinet / createCabinet / updateCabinet / deleteCabinet | 机柜 CRUD |
| getCabinetUsage | 机柜使用率 |
| moveAssetInCabinet | 机柜内资产移动 |
| getAssets / getAsset / createAsset / updateAsset / deleteAsset | 资产 CRUD |
| getAssetLifecycle | 资产生命周期 |
| createMaintenance / completeMaintenance / getMaintenanceRecords | 维保管理 |
| createInventory / getInventoryList / getInventoryItems / updateInventoryItem | 盘点管理 |
| getAssetStatistics | 资产统计 |
| getWarrantyExpiringAssets / getWarrantyAlerts | 保修预警 |
| importAssets / exportAssets / downloadImportTemplate | 导入导出 |

### 5.3 auth.ts — 认证 (6 函数)

| 函数 | 方法 | 说明 |
|------|------|------|
| login | POST | 登录 (form-urlencoded) |
| logout | POST | 登出 |
| refreshToken | POST | 刷新 token |
| getCurrentUser | GET | 获取当前用户 |
| changePassword | POST | 修改密码 |
| getPermissions | GET | 获取权限列表 |

### 5.4 bigscreen.ts — 大屏 (3 函数)

| 函数 | 说明 |
|------|------|
| getDataCenterLayout | 获取数据中心布局 |
| saveDataCenterLayout | 保存布局 |
| getDefaultLayout | 获取默认布局 |

### 5.5 capacity.ts — 容量管理 (22 函数)

| 函数 | 说明 |
|------|------|
| getSpaceCapacities / getSpaceCapacity / create / update / delete | 空间容量 CRUD |
| getPowerCapacities / getPowerCapacity / create / update / delete | 电力容量 CRUD |
| getCoolingCapacities / getCoolingCapacity / create / update / delete | 制冷容量 CRUD |
| getWeightCapacities / getWeightCapacity / create / update / delete | 承重容量 CRUD |
| getCapacityPlans / getCapacityPlan / create / update / delete | 容量规划 CRUD |
| getCapacityStatistics / getCapacityByLocation | 统计/按位置查询 |
| getCapacityTrend / getCapacityForecast / getCapacityAlerts | 趋势/预测/告警 |
| getRackingRecommendation / overridePlanCabinet | 上架推荐/覆盖 |

### 5.6 command.ts — 命令管理 (8 函数)

| 函数 | 说明 |
|------|------|
| submitCommand | 提交命令 |
| getCommandApprovals / getCommandApproval | 审批列表/详情 |
| approveCommand / rejectCommand | 审批/拒绝 |
| getCommandAuditLogs | 审计日志 |
| getRiskConfigs / updateRiskConfigs | 风险配置 |

### 5.7 config.ts — 系统配置 (9 函数)

| 函数 | 说明 |
|------|------|
| getSystemConfigs / updateSystemConfigs / getSystemConfig | 系统配置 CRUD |
| getDictionaries / getDictionaryOptions | 字典管理 |
| getLicenseInfo / activateLicense | 许可证 |
| exportConfigs / importConfigs | 配置导入导出 |

### 5.8 cooling.ts — 制冷监控 (6 函数)

| 函数 | 说明 |
|------|------|
| getCoolingOverview | 制冷总览 |
| getCoolingUnitList / getCoolingUnitDetail | 制冷机组列表/详情 |
| getCoolingGroupList | 制冷组列表 |
| getColdAisleList / getColdAisleDetail | 冷通道列表/详情 |

### 5.9 dataQuality.ts — 数据质量 (2 函数)

| 函数 | 说明 |
|------|------|
| getDataQualityStatus | 数据质量状态 |
| getDataQualityPoints | 数据质量点位 |

### 5.10 demand.ts — 需量管理 (4 函数)

| 函数 | 说明 |
|------|------|
| getDemandComparison | 需量对比 |
| getDemandCurveMini | 需量曲线迷你图 |
| getLoadPeriodDistribution | 负荷时段分布 |
| getPowerFactorTrend | 功率因数趋势 |

### 5.11 demo.ts — Demo 数据 (7 函数)

| 函数 | 说明 |
|------|------|
| getDemoStatus / loadDemoData / getDemoProgress | Demo 状态/加载/进度 |
| unloadDemoData / unloadDemoDataPreview | 卸载 Demo 数据 |
| getDemoDataStats / refreshDemoDataDates | 统计/刷新日期 |

### 5.12 device.ts — 设备管理 (10 函数)

| 函数 | 说明 |
|------|------|
| getDeviceList / getDeviceById / createDevice / updateDevice | 设备 CRUD |
| getDeleteImpact / deleteDevice | 删除影响分析/删除 |
| getDeviceDetail / getDevicePoints | 设备详情/点位 |
| getDeviceTree | 设备树 |
| getDeviceStatusSummary / getDeviceStatusBoard | 状态汇总/看板 |

### 5.13 diagnosis.ts — 智能诊断 (20 函数)

| 函数 | 说明 |
|------|------|
| getDiagnosisRules / getDiagnosisRule / create / update / delete / toggle | 诊断规则 CRUD |
| reloadDiagnosisRules | 重载规则 |
| getDiagnosisResults / getDiagnosisResult | 诊断结果列表/详情 |
| getDiagnosisByAlarm / manualDiagnose | 按告警查询/手动诊断 |
| getDiagnosisCategories | 诊断分类 |
| createDiagnosisAnnotation / getDiagnosisAnnotations / delete / getStats | 标注管理 |
| getCounterfactualAnalysis / getCounterfactualAnalysisList | 反事实分析 |
| getMisdiagnosisReports / getMisdiagnosisReport / generate / export | 误诊报告 |
| getTimeWindowAdjustments / triggerTimeWindowAnalysis / approve / reject | 时间窗口调参 |
| getFaultTrees | 故障树列表 |

### 5.14 dispatch.ts — 调度管理 (16 函数)

| 函数 | 说明 |
|------|------|
| getDispatchableDevices / getDispatchableDevice / create / update / delete | 可调度设备 CRUD |
| getDeviceStats | 设备统计 |
| getStorageSystems / getStorageSystem / create / update / delete | 储能系统 CRUD |
| getPVSystems / getPVSystem / create / update / delete | 光伏系统 CRUD |
| getDispatchSummary / initDispatchDemoData | 调度汇总/初始化 Demo |

### 5.15 drift.ts — 漂移检测 (5 函数)

| 函数 | 说明 |
|------|------|
| triggerDriftDetection | 触发漂移检测 |
| getDriftResults / getDriftResult | 结果列表/详情 |
| resolveDrift | 解决漂移 |
| getDriftSummary | 漂移汇总 |

### 5.16 energy.ts — 能效管理 (35 函数)

| 函数 | 说明 |
|------|------|
| getPowerDevices / getPowerDeviceTree / create / get / update / delete | 配电设备 CRUD |
| getRealtimePower / getPowerSummary / getDeviceRealtimePower | 实时电力 |
| getCurrentPUE / getPUETrend | PUE 数据 |
| getDailyStatistics / getMonthlyStatistics | 日/月统计 |
| getEnergySummary / getEnergyTrend / getEnergyComparison | 能耗汇总/趋势/对比 |
| getDailyCost / getMonthlyCost | 日/月费用 |
| getPricingList / getElectricityPricings / create / update / delete | 电价管理 |
| getSuggestions / getSuggestion / accept / reject / complete | 节能建议 |
| getSavingPotential | 节能潜力 |
| getDistributionDiagram | 配电图 |
| exportDailyData / exportMonthlyData | 数据导出 |
| getAnalysisPlugins / enablePlugin / disablePlugin | 分析插件管理 |
| runAnalysis / runSingleAnalysis / getAnalysisSummary | 运行分析 |
| getTransformersWithMeters / getTransformers | 变压器 |
