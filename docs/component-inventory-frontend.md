# 前端组件清单

> 基于 frontend/src/ 目录的穷举式扫描。
> 技术栈: Vue 3 + TypeScript + Element Plus + ECharts + Three.js + Pinia

## Pinia 状态管理 (8 个 Store)

### user.ts — 用户状态
- 状态: token, userInfo, permissions
- Getters: isLoggedIn, isAdmin, isOperator, role, username, realName
- Actions: doLogin, fetchUserInfo, fetchPermissions, doLogout, hasPermission, hasAnyPermission, initFromStorage

### app.ts — 应用全局状态
- 状态: sidebarCollapsed, theme, language, alarmSoundEnabled, alarmPopupEnabled, refreshInterval, isFullscreen, globalLoading, loadingText, breadcrumbs, tabs, activeTab
- Getters: settings
- Actions: toggleSidebar, setSidebarCollapsed, toggleTheme, setTheme, setLanguage, toggleAlarmSound, toggleAlarmPopup, setRefreshInterval, showLoading, hideLoading, setBreadcrumbs, addTab, removeTab, initFromStorage

### alarm.ts — 告警状态
- 状态: activeAlarms, alarmCount, soundEnabled
- Actions: addAlarm, removeAlarm, updateAlarm, toggleSound

### realtime.ts — 实时数据状态
- 状态: dataMap, summary, lastUpdateTime, wsConnected
- Getters: realtimeData, totalPoints, alarmPoints, offlinePoints, alarmCount, offlineCount
- Actions: updatePoint, updatePoints, setAllData, setSummary, getPointData, getDataByType, getDataByArea, setWsConnected, clearData

### energy.ts — 能源状态
- 状态: realtimePowerData, powerSummary, pueData, suggestions, pendingSuggestions, distributionDiagram, lastUpdateTime, wsConnected
- Getters: powerDataList, currentPUE, totalPower, itPower, coolingPower, todayEnergy, todayCost, monthEnergy, monthCost, pendingCount, highPrioritySuggestions
- Actions: updatePowerData, updatePowerDataBatch, setAllPowerData, setPowerSummary, setPUEData, setSuggestions, addSuggestion, updateSuggestionStatus, setDistributionDiagram, getDevicePower, getPowerByType, setWsConnected, clearData

### bigscreen.ts — 大屏状态
- 状态: mode, layout, deviceData, layers, selectedDeviceId, activeAlarms, environment, energy, cameraPresets, loading, panelStates
- Getters: getDeviceData, alarmCount, criticalAlarmCount, hasSelectedDevice, modeConfig, recentAlarms
- Actions: setMode, setLayout, updateDeviceData, updateAllDeviceData, toggleLayer, selectDevice, setAlarms, updateEnvironment, updateEnergy, setLoading, updatePanelPosition, updatePanelCollapsed, togglePanelVisible, savePanelStates, loadPanelStates, resetPanelStates

### opportunity.ts — 节能机会状态
- 状态: dashboard, dashboardLoading, opportunities, opportunitiesTotal, opportunitiesLoading, currentOpportunity, simulationResult, simulationLoading, availableDevices, selectedDeviceIds, executionPlans, plansTotal, currentPlan, executionStats, lastUpdateTime
- Getters: pendingCount, executingCount, annualPotentialSaving, monthlyActualSaving, opportunitiesByCategory, highPriorityOpportunities, totalSelectedPower, currentPlanProgress
- Actions: loadDashboard, loadOpportunities, loadOpportunityDetail, loadAvailableDevices, setSimulationResult, toggleDeviceSelection, selectAllDevices, loadExecutionPlans, loadPlanDetail, loadExecutionStats, updateTaskStatus, clearData

### degradation.ts — 降级状态
- 状态: redisDown, websocketDown, mqttDown, degradedMessage
- Getters: hasDegradation
- Actions: setRedisDown, setWebsocketDown, setMqttDown, syncFromFlags

---

## 组件库 (74 个 Vue 组件)

### common/ — 公共组件 (9 个)

| 组件 | 文件 | 用途 |
|------|------|------|
| DataTable | DataTable.vue | 通用数据表格 (分页/排序/筛选) |
| SearchForm | SearchForm.vue | 通用搜索表单 |
| ConfirmDialog | ConfirmDialog.vue | 确认对话框 |
| DateRangePicker | DateRangePicker.vue | 日期范围选择器 |
| ExportButton | ExportButton.vue | 数据导出按钮 |
| StatusTag | StatusTag.vue | 状态标签 |
| AlarmSoundToggle | AlarmSoundToggle.vue | 告警声音开关 |
| DataQualityTag | DataQualityTag.vue | 数据质量标记 |
| DegradationBanner | DegradationBanner.vue | 降级提示横幅 |

### charts/ — 通用图表组件 (6 个)

| 组件 | 文件 | 用途 |
|------|------|------|
| LineChart | LineChart.vue | 折线图 (ECharts) |
| BarChart | BarChart.vue | 柱状图 |
| PieChart | PieChart.vue | 饼图 |
| GaugeChart | GaugeChart.vue | 仪表盘图 |
| RealtimeChart | RealtimeChart.vue | 实时数据图表 |
| Sparkline | Sparkline.vue | 迷你趋势图 |

### monitor/ — 监控组件 (4 个)

| 组件 | 文件 | 用途 |
|------|------|------|
| PointCard | PointCard.vue | 点位卡片 |
| ValueDisplay | ValueDisplay.vue | 数值展示 |
| StatusPanel | StatusPanel.vue | 状态面板 |
| AlarmBadge | AlarmBadge.vue | 告警徽章 |

### energy/ — 能源管理组件 (20 个)

| 组件 | 文件 | 用途 |
|------|------|------|
| PUEGauge | PUEGauge.vue | PUE 仪表盘 |
| PUEIndicatorCard | PUEIndicatorCard.vue | PUE 指标卡片 |
| PowerCard | PowerCard.vue | 功率卡片 |
| InteractivePowerCard | InteractivePowerCard.vue | 交互式功率卡片 |
| CostCard | CostCard.vue | 费用卡片 |
| DeviceList | DeviceList.vue | 设备列表 |
| SuggestionsCard | SuggestionsCard.vue | 建议卡片 |
| EnergySuggestionCard | EnergySuggestionCard.vue | 节能建议卡片 |
| SuggestionOverview | SuggestionOverview.vue | 建议总览 |
| SuggestionDetailDrawer | SuggestionDetailDrawer.vue | 建议详情抽屉 |
| CalculationDetails | CalculationDetails.vue | 计算详情 |
| ShiftPlanBuilder | ShiftPlanBuilder.vue | 负荷转移计划构建器 |
| DeviceShiftDetailDrawer | DeviceShiftDetailDrawer.vue | 设备转移详情 |
| LoadComparisonChart | LoadComparisonChart.vue | 负荷对比图 |
| DevicePowerCurveChart | DevicePowerCurveChart.vue | 设备功率曲线 |
| DemandDashboard | DemandDashboard.vue | 需量仪表盘 |
| DemandStatusCard | DemandStatusCard.vue | 需量状态卡片 |
| ScheduleDashboard | ScheduleDashboard.vue | 调度仪表盘 |
| DispatchConfig | DispatchConfig.vue | 调度配置 |
| ExecutionPlanDialog | ExecutionPlanDialog.vue | 执行计划对话框 |
| OptimizationOverview | OptimizationOverview.vue | 优化总览 |
| OptimizationReport | OptimizationReport.vue | 优化报告 |
| ParameterAdjustment | ParameterAdjustment.vue | 参数调整 |

### bigscreen/ — 大屏组件 (16 个)

| 组件 | 文件 | 用途 |
|------|------|------|
| ThreeScene | ThreeScene.vue | Three.js 3D 场景容器 |
| DataCenterModel | DataCenterModel.vue | 数据中心 3D 模型 |
| Floor2DView | Floor2DView.vue | 楼层 2D 平面图 |
| FloorSelector | FloorSelector.vue | 楼层选择器 |
| HeatmapOverlay | HeatmapOverlay.vue | 热力图叠加层 |
| AlarmBubbles | AlarmBubbles.vue | 告警气泡 |
| CabinetLabels | CabinetLabels.vue | 机柜标签 |
| DeviceDetailPanel | DeviceDetailPanel.vue | 设备详情面板 |

bigscreen/charts/:
| GaugeChart | GaugeChart.vue | 大屏仪表盘 |
| PueTrend | PueTrend.vue | PUE 趋势图 |
| PowerDistribution | PowerDistribution.vue | 功率分布图 |
| TemperatureTrend | TemperatureTrend.vue | 温度趋势图 |
| BaseChart | BaseChart.vue | 图表基类 |

bigscreen/panels/:
| LeftPanel | LeftPanel.vue | 左侧面板 |
| RightPanel | RightPanel.vue | 右侧面板 |

bigscreen/ui/:
| DraggablePanel | DraggablePanel.vue | 可拖拽面板 |
| ThemeSelector | ThemeSelector.vue | 主题选择器 |
| ContextMenu | ContextMenu.vue | 右键菜单 |
| DigitalFlop | DigitalFlop.vue | 数字翻牌器 |

### floor-layouts/ — 楼层布局组件 (5 个)

| 组件 | 文件 | 用途 |
|------|------|------|
| FloorLayoutBase | FloorLayoutBase.vue | 楼层布局基类 |
| FloorLayoutSelector | FloorLayoutSelector.vue | 布局选择器 |
| FloorF1Layout | FloorF1Layout.vue | 1楼布局 |
| FloorF2Layout | FloorF2Layout.vue | 2楼布局 |
| FloorF3Layout | FloorF3Layout.vue | 3楼布局 |
| FloorB1Layout | FloorB1Layout.vue | 地下1层布局 |

### demand/ — 需量管理组件 (3 个)

| 组件 | 文件 | 用途 |
|------|------|------|
| LoadPeriodChart | LoadPeriodChart.vue | 负荷时段图 |
| DemandComparisonCard | DemandComparisonCard.vue | 需量对比卡片 |
| DemandCurveMini | DemandCurveMini.vue | 需量曲线迷你图 |

### 其他组件

| 组件 | 文件 | 用途 |
|------|------|------|
| MetricDisplay | MetricDisplay.vue | 指标展示 |
| DemoDataLoader | DemoDataLoader.vue | 演示数据加载器 |
| LifecycleTimeline | asset/LifecycleTimeline.vue | 资产生命周期时间线 |
| VideoPopup | video/VideoPopup.vue | 视频弹窗 |

---

## 页面视图 (60 个 Vue 页面)

### 独立入口页面

| 页面 | 路由 | 说明 |
|------|------|------|
| login/index.vue | /login | 登录页 |
| bigscreen/index.vue | /bigscreen | 数字孪生大屏 (全屏) |
| dashboard/index.vue | /dashboard | 监控仪表盘 (首页) |

### 供配电管理 (/power/*)

| 页面 | 路由 | 说明 |
|------|------|------|
| power/overview.vue | /power/overview | 供配电总览 |
| power/ups.vue | /power/ups | UPS 监控 |
| power/battery.vue | /power/battery | 电池组 |
| power/cabinet.vue | /power/cabinet | 配电柜 |
| power/pdu.vue | /power/pdu | 机柜 PDU |
| energy/monitor.vue | /power/monitor | 用电监控 |
| energy/statistics.vue | /power/statistics | 能耗统计 |
| energy/config.vue | /power/config | 配电配置 |
| energy/topology.vue | /power/topology | 配电拓扑 |

### 制冷系统 (/cooling/*)

| 页面 | 路由 | 说明 |
|------|------|------|
| cooling/overview.vue | /cooling/overview | 制冷总览 |
| cooling/indoor.vue | /cooling/indoor | 精密空调 |
| cooling/outdoor.vue | /cooling/outdoor | 室外机 |
| cooling/cold-aisle.vue | /cooling/cold-aisle | 冷通道 |
| cooling/group-control.vue | /cooling/group-control | 群控状态 |

### 环境与安防

| 页面 | 路由 | 说明 |
|------|------|------|
| environment/overview.vue | /environment/overview | 环境总览 |
| security/overview.vue | /security/overview | 安防总览 |

### 基础设施 (/infrastructure/*)

| 页面 | 路由 | 说明 |
|------|------|------|
| asset/index.vue | /infrastructure/asset | 资产台账 |
| asset/cabinet.vue | /infrastructure/cabinet | 机柜管理 |
| capacity/index.vue | /infrastructure/capacity | 容量管理 |
| topology/spatial.vue | /infrastructure/spatial | 空间拓扑 |
| topology/power.vue | /infrastructure/power-topology | PDU 相位配置 |
| topology/cooling.vue | /infrastructure/cooling-topology | 制冷区域配置 |
| topology/site-selection.vue | /infrastructure/site-selection | 智能选址 |
| topology/fault-impact.vue | /infrastructure/fault-impact | 故障影响分析 |

### 节能中心 (/energy-saving/*)

| 页面 | 路由 | 说明 |
|------|------|------|
| energy/analysis.vue | /energy-saving/analysis | 节能分析 |
| energy/regulation.vue | /energy-saving/regulation | 负荷调节 |
| energy/execution.vue | /energy-saving/execution | 执行管理 |
| energy/report.vue | /energy-saving/report | 能效报告 |
| energy/suggestions.vue | — | 节能建议 (独立) |

### 告警/历史/报表

| 页面 | 路由 | 说明 |
|------|------|------|
| alarm/index.vue | /alarms | 告警管理 |
| history/index.vue | /history | 历史数据 |
| report/index.vue | /reports | 报表分析 |

### 设备管理

| 页面 | 路由 | 说明 |
|------|------|------|
| device/index.vue | /devices | 点位管理 |
| device-manage/index.vue | /device-manage | 设备管理 |
| device-manage/detail.vue | /device-manage/detail/:id | 设备详情 |
| device-status/index.vue | /device-status | 设备状态看板 |
| device-template/index.vue | /device-templates | 设备模板 |
| datasource/index.vue | /datasources | 数据源管理 |

### 运维管理 (/operation/*)

| 页面 | 路由 | 说明 |
|------|------|------|
| operation/workorder.vue | /operation/workorder | 工单管理 |
| operation/inspection.vue | /operation/inspection | 巡检管理 |
| operation/knowledge.vue | /operation/knowledge | 知识库 |

### 联动管理 (/linkage/*)

| 页面 | 路由 | 说明 |
|------|------|------|
| linkage/policy.vue | /linkage/policy | 联动策略 |
| linkage/execution.vue | /linkage/execution | 执行日志 |
| linkage/recovery.vue | /linkage/recovery | 联动恢复 |
| linkage/timeline.vue | /linkage/timeline | 事件时间线 |
| linkage/command.vue | /linkage/command | 命令管理 |
| linkage/drift.vue | /linkage/drift | 漂移检测 |

### 智能诊断 (/diagnosis/*)

| 页面 | 路由 | 说明 |
|------|------|------|
| diagnosis/results.vue | /diagnosis/results | 诊断结果 |
| diagnosis/rules.vue | /diagnosis/rules | 诊断规则 |

### 视频监控 (/video/*)

| 页面 | 路由 | 说明 |
|------|------|------|
| video/index.vue | /video/cameras | 摄像头管理 |
| video/control.vue | /video/control | 视频控制 |
| video/playback.vue | /video/playback | 告警回放 |

### 虚拟电厂

| 页面 | 路由 | 说明 |
|------|------|------|
| vpp/VPPAnalysis.vue | /vpp/analysis | VPP 方案分析 |

### 系统管理

| 页面 | 路由 | 说明 |
|------|------|------|
| system/user.vue | /system/users | 用户管理 |
| system/audit-log.vue | /system/audit-log | 操作审计 |
| settings/index.vue | /settings | 系统设置 |

---

## 组合式函数 (Composables)

### 通用组合式函数

| 文件 | 导出函数 | 用途 |
|------|----------|------|
| useWebSocket.ts | useWebSocket | WebSocket 连接管理 |
| useRealtime.ts | useRealtime | 实时数据订阅 |
| useAlarm.ts | useAlarm | 告警处理 |
| useEnergy.ts | useEnergy | 能源数据 |
| usePermission.ts | usePermission | 权限检查 |
| useSound.ts | useSound | 告警声音播放 |
| useDataQuality.ts | useDataQuality | 数据质量标记 |

### 大屏专用组合式函数 (bigscreen/)

| 文件 | 导出函数 | 用途 |
|------|----------|------|
| useThreeScene.ts | useThreeScene | Three.js 场景管理 |
| useBuildingModel.ts | useBuildingModel | 建筑模型加载 |
| useCameraAnimation.ts | useCameraAnimation | 相机动画 |
| useAutoTour.ts | useAutoTour | 自动巡游 |
| useRaycaster.ts | useRaycaster | 射线检测 (点击交互) |
| useSceneMode.ts | useSceneMode | 场景模式切换 |
| useEntranceAnimation.ts | useEntranceAnimation | 入场动画 |
| useScreenAdapt.ts | useScreenAdapt | 屏幕自适应 |
| useBigscreenData.ts | useBigscreenData | 大屏数据获取 |
| useTheme.ts | useTheme | 主题管理 |
| useKeyboardShortcuts.ts | useKeyboardShortcuts | 键盘快捷键 |

---

## API 模块 (frontend/src/api/)

### 顶层 API 文件

| 文件 | 用途 |
|------|------|
| index.ts | API 统一导出 |
| auth.ts | 认证 API |
| alarm.ts | 告警 API |
| realtime.ts | 实时数据 API |
| point.ts | 点位 API |
| websocket.ts | WebSocket 管理 |
| datasource.ts | 数据源 API |
| device-template.ts | 设备模板 API |

### modules/ — 业务 API 模块

| 文件 | 对应后端模块 |
|------|-------------|
| user.ts | 用户管理 |
| device.ts | 设备管理 |
| point.ts | 点位管理 |
| realtime.ts | 实时数据 |
| threshold.ts | 阈值配置 |
| history.ts | 历史数据 |
| statistics.ts | 统计分析 |
| log.ts | 系统日志 |
| report.ts | 报表管理 |
| energy.ts | 用电管理 |
| power.ts | 供配电管理 |
| opportunities.ts | 节能机会 |
| optimization.ts | 日前调度优化 |
| monitoring.ts | 电费监控 |
| dispatch.ts | 可调度资源 |
| operation.ts | 运维管理 |
| demo.ts | 演示数据 |
| floorMap.ts | 楼层图 |
| vpp.ts | VPP 分析 |
| spatial.ts | 空间拓扑 |
| topologyConfig.ts | 拓扑配置 |
| linkage.ts | 联动管理 |
| diagnosis.ts | 智能诊断 |
| drift.ts | 漂移检测 |
| video.ts | 视频监控 |

---

## 路由配置

路由守卫: 未登录用户自动跳转 /login (除 requiresAuth: false 的路由)

旧路由兼容重定向:
- /energy/* → /power/* 或 /energy-saving/*
- /asset/* → /infrastructure/*
- /capacity → /infrastructure/capacity
