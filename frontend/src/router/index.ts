import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/bigscreen',
    name: 'Bigscreen',
    component: () => import('@/views/bigscreen/index.vue'),
    meta: {
      title: '数字孪生大屏',
      fullscreen: true,
      requiresAuth: false
    }
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      // ══════ 监控域 ══════
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/index.vue'),
        meta: { title: '综合概览', icon: 'Monitor' }
      },

      // 供配电监控
      {
        path: 'power',
        name: 'Power',
        redirect: '/power/overview',
        meta: { title: '供配电监控', icon: 'Lightning' },
        children: [
          { path: 'overview', name: 'PowerOverview', component: () => import('@/views/power/overview.vue'), meta: { title: '供配电总览', icon: 'DataBoard' } },
          { path: 'ups', name: 'PowerUPS', component: () => import('@/views/power/ups.vue'), meta: { title: 'UPS监控', icon: 'Lightning' } },
          { path: 'battery', name: 'PowerBattery', component: () => import('@/views/power/battery.vue'), meta: { title: '电池组', icon: 'Coin' } },
          { path: 'cabinet', name: 'PowerCabinet', component: () => import('@/views/power/cabinet.vue'), meta: { title: '配电柜', icon: 'Grid' } },
          { path: 'pdu', name: 'PowerPDU', component: () => import('@/views/power/pdu.vue'), meta: { title: '机柜PDU', icon: 'Menu' } },
          { path: 'topology', name: 'PowerTopology', component: () => import('@/views/energy/topology.vue'), meta: { title: '配电拓扑', icon: 'Share' } }
        ]
      },

      // 制冷监控
      {
        path: 'cooling',
        name: 'Cooling',
        redirect: '/cooling/overview',
        meta: { title: '制冷监控', icon: 'IceCream' },
        children: [
          { path: 'overview', name: 'CoolingOverview', component: () => import('@/views/cooling/overview.vue'), meta: { title: '制冷总览', icon: 'DataBoard' } },
          { path: 'indoor', name: 'CoolingIndoor', component: () => import('@/views/cooling/indoor.vue'), meta: { title: '精密空调', icon: 'IceCream' } },
          { path: 'outdoor', name: 'CoolingOutdoor', component: () => import('@/views/cooling/outdoor.vue'), meta: { title: '室外机', icon: 'Sunny' } },
          { path: 'cold-aisle', name: 'CoolingColdAisle', component: () => import('@/views/cooling/cold-aisle.vue'), meta: { title: '冷通道', icon: 'Box' } },
          { path: 'group-control', name: 'CoolingGroupControl', component: () => import('@/views/cooling/group-control.vue'), meta: { title: '群控状态', icon: 'Connection' } }
        ]
      },

      // 环境监控
      {
        path: 'environment',
        name: 'Environment',
        redirect: '/environment/overview',
        meta: { title: '环境监控', icon: 'Sunny' },
        children: [
          { path: 'overview', name: 'EnvironmentOverview', component: () => import('@/views/environment/overview.vue'), meta: { title: '环境总览', icon: 'DataBoard' } },
          { path: 'temperature', name: 'EnvironmentTemperature', component: () => import('@/views/environment/temperature.vue'), meta: { title: '温湿度监测', icon: 'Odometer' } },
          { path: 'water-leak', name: 'EnvironmentWaterLeak', component: () => import('@/views/environment/water-leak.vue'), meta: { title: '水浸检测', icon: 'Warning' } },
          { path: 'smoke-infrared', name: 'EnvironmentSmokeInfrared', component: () => import('@/views/environment/smoke-infrared.vue'), meta: { title: '烟雾/红外检测', icon: 'View' } }
        ]
      },

      // 安防消防
      {
        path: 'security',
        name: 'Security',
        redirect: '/security/overview',
        meta: { title: '安防消防', icon: 'Lock' },
        children: [
          { path: 'overview', name: 'SecurityOverview', component: () => import('@/views/security/overview.vue'), meta: { title: '安防总览', icon: 'DataBoard' } },
          { path: 'access-control', name: 'SecurityAccessControl', component: () => import('@/views/security/access-control.vue'), meta: { title: '门禁管理', icon: 'Key' } },
          {
            path: 'video',
            name: 'SecurityVideo',
            redirect: '/security/video/cameras',
            meta: { title: '视频监控', icon: 'VideoCamera' },
            children: [
              { path: 'cameras', name: 'VideoCameras', component: () => import('@/views/video/index.vue'), meta: { title: '摄像头管理', icon: 'Camera' } },
              { path: 'control', name: 'VideoControl', component: () => import('@/views/video/control.vue'), meta: { title: '视频控制', icon: 'VideoPlay' } },
              { path: 'playback', name: 'VideoPlayback', component: () => import('@/views/video/playback.vue'), meta: { title: '告警回放', icon: 'Timer' } }
            ]
          },
          { path: 'fire-linkage', name: 'SecurityFireLinkage', component: () => import('@/views/security/fire-linkage.vue'), meta: { title: '消防联动', icon: 'Warning' } }
        ]
      },

      // 告警中心
      {
        path: 'alarms',
        name: 'Alarms',
        component: () => import('@/views/alarm/index.vue'),
        meta: { title: '告警中心', icon: 'Bell' }
      },

      // ══════ 管理域 ══════

      // 能效管理
      {
        path: 'energy',
        name: 'Energy',
        redirect: '/energy/monitor',
        meta: { title: '能效管理', icon: 'Opportunity' },
        children: [
          { path: 'monitor', name: 'EnergyMonitor', component: () => import('@/views/energy/monitor.vue'), meta: { title: '用电监控', icon: 'Odometer' } },
          { path: 'statistics', name: 'EnergyStatistics', component: () => import('@/views/energy/statistics.vue'), meta: { title: '能耗统计', icon: 'TrendCharts' } },
          { path: 'analysis', name: 'EnergyAnalysis', component: () => import('@/views/energy/analysis.vue'), meta: { title: '节能分析', icon: 'Opportunity' } },
          { path: 'regulation', name: 'EnergyRegulation', component: () => import('@/views/energy/regulation.vue'), meta: { title: '负荷调节', icon: 'Operation' } },
          { path: 'execution', name: 'EnergyExecution', component: () => import('@/views/energy/execution.vue'), meta: { title: '执行管理', icon: 'VideoPlay' } },
          { path: 'report', name: 'EnergyReport', component: () => import('@/views/energy/report.vue'), meta: { title: '能效报告', icon: 'Document' } },
          {
            path: 'shift',
            name: 'Shift',
            redirect: '/energy/shift/dashboard',
            meta: { title: '负荷转移', icon: 'Operation' },
            children: [
              { path: 'dashboard', name: 'ShiftDashboard', component: () => import('@/views/energy/shift/ShiftDashboard.vue'), meta: { title: '转移仪表盘', icon: 'DataBoard' } },
              { path: 'list', name: 'ShiftPlanList', component: () => import('@/views/energy/shift/ShiftPlanList.vue'), meta: { title: '计划列表', icon: 'Document' } },
              { path: 'create', name: 'ShiftPlanCreate', component: () => import('@/views/energy/shift/ShiftPlanCreate.vue'), meta: { title: '新建计划', icon: 'Plus' } },
              { path: 'edit/:id', name: 'ShiftPlanEdit', component: () => import('@/views/energy/shift/ShiftPlanCreate.vue'), meta: { title: '编辑计划', icon: 'Edit', hidden: true } },
              { path: 'detail/:id', name: 'ShiftPlanDetail', component: () => import('@/views/energy/shift/ShiftPlanDetail.vue'), meta: { title: '计划详情', icon: 'View', hidden: true } },
              { path: 'opportunities', name: 'ShiftOpportunityList', component: () => import('@/views/energy/shift/ShiftOpportunityList.vue'), meta: { title: '转移机会', icon: 'Opportunity' } },
              { path: 'opportunity/:id', name: 'ShiftOpportunityDetail', component: () => import('@/views/energy/shift/ShiftOpportunityDetail.vue'), meta: { title: '机会详情', icon: 'View', hidden: true } },
              { path: 'executions', name: 'ShiftExecutionList', component: () => import('@/views/energy/shift/ShiftExecutionList.vue'), meta: { title: '执行记录', icon: 'List' } },
              { path: 'execution/:id', name: 'ShiftExecutionDetail', component: () => import('@/views/energy/shift/ShiftExecutionDetail.vue'), meta: { title: '执行详情', icon: 'View', hidden: true } },
              { path: 'monitor/:id', name: 'ShiftExecutionMonitor', component: () => import('@/views/energy/shift/ShiftExecutionMonitor.vue'), meta: { title: '实时监控', icon: 'Monitor', hidden: true } },
              { path: 'cooling-config', name: 'CoolingLinkageConfig', component: () => import('@/views/energy/shift/CoolingLinkageConfig.vue'), meta: { title: '制冷联动配置', icon: 'Setting' } },
              { path: 'cooling-monitor', name: 'CoolingLinkageMonitor', component: () => import('@/views/energy/shift/CoolingLinkageMonitor.vue'), meta: { title: '制冷状态监控', icon: 'Monitor' } },
              { path: 'constraints', name: 'ShiftConstraintConfig', component: () => import('@/views/energy/shift/ShiftConstraintConfig.vue'), meta: { title: '约束管理', icon: 'Lock' } },
              { path: 'reports', name: 'ShiftReports', component: () => import('@/views/energy/shift/ShiftReports.vue'), meta: { title: '收益报表', icon: 'Document' } },
              { path: 'precool-schedule', name: 'PrecoolSchedule', component: () => import('@/views/energy/shift/PrecoolScheduleView.vue'), meta: { title: '预冷计划', icon: 'Timer' } },
              { path: 'deployment', name: 'DeploymentPhase', component: () => import('@/views/energy/shift/DeploymentPhaseView.vue'), meta: { title: '部署管理', icon: 'SetUp' } },
              { path: 'vpp-monitor', name: 'VppMonitor', component: () => import('@/views/energy/shift/VppMonitorView.vue'), meta: { title: 'VPP 集成监控', icon: 'Connection' } },
            ]
          },
        ]
      },

      // 资产与容量
      {
        path: 'asset',
        name: 'Asset',
        redirect: '/asset/list',
        meta: { title: '资产与容量', icon: 'OfficeBuilding' },
        children: [
          { path: 'list', name: 'AssetList', component: () => import('@/views/asset/index.vue'), meta: { title: '资产台账', icon: 'Document' } },
          { path: 'cabinet', name: 'AssetCabinet', component: () => import('@/views/asset/cabinet.vue'), meta: { title: '机柜管理', icon: 'Grid' } },
          { path: 'capacity', name: 'AssetCapacity', component: () => import('@/views/capacity/index.vue'), meta: { title: '容量管理', icon: 'DataAnalysis' } },
          { path: 'spatial', name: 'AssetSpatial', component: () => import('@/views/topology/spatial.vue'), meta: { title: '空间拓扑', icon: 'OfficeBuilding' } }
        ]
      },

      // 运维管理
      {
        path: 'operation',
        name: 'Operation',
        redirect: '/operation/workorder',
        meta: { title: '运维管理', icon: 'Tools' },
        children: [
          { path: 'workorder', name: 'WorkOrder', component: () => import('@/views/operation/workorder.vue'), meta: { title: '工单管理', icon: 'Tickets' } },
          { path: 'inspection', name: 'Inspection', component: () => import('@/views/operation/inspection.vue'), meta: { title: '巡检管理', icon: 'List' } },
          { path: 'knowledge', name: 'Knowledge', component: () => import('@/views/operation/knowledge.vue'), meta: { title: '知识库', icon: 'Reading' } },
          { path: 'reports', name: 'Reports', component: () => import('@/views/report/index.vue'), meta: { title: '报表分析', icon: 'Document' } },
          { path: 'history', name: 'History', component: () => import('@/views/history/index.vue'), meta: { title: '历史数据', icon: 'TrendCharts' } },
          { path: 'predictive', name: 'Predictive', component: () => import('@/views/operation/predictive.vue'), meta: { title: '预测性维护', icon: 'TrendCharts' } }
        ]
      },

      // 虚拟电厂
      {
        path: 'vpp',
        name: 'VPP',
        redirect: '/vpp/analysis',
        meta: { title: '虚拟电厂', icon: 'Connection' },
        children: [
          { path: 'analysis', name: 'VPPAnalysis', component: () => import('@/views/vpp/VPPAnalysis.vue'), meta: { title: 'VPP方案分析', icon: 'DataAnalysis' } }
        ]
      },

      // ══════ 配置域 ══════

      // 采集配置
      {
        path: 'collection',
        name: 'Collection',
        redirect: '/collection/device-manage',
        meta: { title: '采集配置', icon: 'Connection' },
        children: [
          { path: 'device-manage', name: 'DeviceManage', component: () => import('@/views/device-manage/index.vue'), meta: { title: '设备管理', icon: 'SetUp' } },
          { path: 'device-manage/detail/:id', name: 'DeviceDetail', component: () => import('@/views/device-manage/detail.vue'), meta: { title: '设备详情', icon: 'View', hidden: true } },
          { path: 'device-status', name: 'DeviceStatus', component: () => import('@/views/device-status/index.vue'), meta: { title: '设备状态看板', icon: 'Odometer' } },
          { path: 'devices', name: 'Devices', component: () => import('@/views/device/index.vue'), meta: { title: '点位管理', icon: 'Cpu' } },
          { path: 'datasources', name: 'Datasources', component: () => import('@/views/datasource/index.vue'), meta: { title: '数据源管理', icon: 'Connection' } },
          { path: 'device-templates', name: 'DeviceTemplates', component: () => import('@/views/device-template/index.vue'), meta: { title: '设备模板', icon: 'Files' } },
          { path: 'power-config', name: 'PowerConfig', component: () => import('@/views/energy/config.vue'), meta: { title: '配电配置', icon: 'Setting' } },
          { path: 'gateway', name: 'Gateway', component: () => import('@/views/gateway/index.vue'), meta: { title: '网关管理', icon: 'Connection' } },
          { path: 'drift', name: 'CollectionDrift', component: () => import('@/views/linkage/drift.vue'), meta: { title: '漂移检测', icon: 'TrendCharts' } }
        ]
      },

      // 策略引擎
      {
        path: 'strategy',
        name: 'Strategy',
        redirect: '/strategy/linkage/policy',
        meta: { title: '策略引擎', icon: 'SetUp' },
        children: [
          {
            path: 'alarm-rules',
            name: 'StrategyAlarmRules',
            redirect: '/strategy/alarm-rules/thresholds',
            meta: { title: '告警规则', icon: 'Bell' },
            children: [
              { path: 'thresholds', name: 'AlarmThresholds', component: () => import('@/views/alarm/thresholds.vue'), meta: { title: '阈值配置', icon: 'Odometer' } },
              { path: 'compound', name: 'AlarmCompound', component: () => import('@/views/alarm/compound.vue'), meta: { title: '复合规则', icon: 'Connection' } },
              { path: 'escalation', name: 'AlarmEscalation', component: () => import('@/views/alarm/escalation.vue'), meta: { title: '升级规则', icon: 'Top' } },
              { path: 'shield', name: 'AlarmShield', component: () => import('@/views/alarm/shield.vue'), meta: { title: '告警屏蔽', icon: 'TurnOff' } }
            ]
          },
          {
            path: 'linkage',
            name: 'StrategyLinkage',
            redirect: '/strategy/linkage/policy',
            meta: { title: '联动策略', icon: 'Connection' },
            children: [
              { path: 'policy', name: 'LinkagePolicy', component: () => import('@/views/linkage/policy.vue'), meta: { title: '联动策略', icon: 'SetUp' } },
              { path: 'execution', name: 'LinkageExecution', component: () => import('@/views/linkage/execution.vue'), meta: { title: '执行日志', icon: 'Document' } },
              { path: 'recovery', name: 'LinkageRecovery', component: () => import('@/views/linkage/recovery.vue'), meta: { title: '联动恢复', icon: 'RefreshRight' } },
              { path: 'timeline', name: 'LinkageTimeline', component: () => import('@/views/linkage/timeline.vue'), meta: { title: '事件时间线', icon: 'Timer' } },
              { path: 'command', name: 'LinkageCommand', component: () => import('@/views/linkage/command.vue'), meta: { title: '命令管理', icon: 'Operation' } }
            ]
          },
          {
            path: 'diagnosis',
            name: 'StrategyDiagnosis',
            redirect: '/strategy/diagnosis/results',
            meta: { title: '智能诊断', icon: 'FirstAidKit' },
            children: [
              { path: 'results', name: 'DiagnosisResults', component: () => import('@/views/diagnosis/results.vue'), meta: { title: '诊断结果', icon: 'DataAnalysis' } },
              { path: 'rules', name: 'DiagnosisRules', component: () => import('@/views/diagnosis/rules.vue'), meta: { title: '诊断规则', icon: 'SetUp' } },
              { path: 'reports', name: 'DiagnosisReports', component: () => import('@/views/diagnosis/Reports.vue'), meta: { title: '误诊报告', icon: 'Document' } },
              { path: 'time-window-tuning', name: 'TimeWindowTuning', component: () => import('@/views/diagnosis/TimeWindowTuning.vue'), meta: { title: '时间窗口调参', icon: 'Timer' } },
              { path: 'probability-tuning', name: 'ProbabilityTuning', component: () => import('@/views/diagnosis/ProbabilityTuning.vue'), meta: { title: '概率调参', icon: 'TrendCharts' } },
              { path: 'fault-trees/:id/editor', name: 'FaultTreeEditor', component: () => import('@/views/diagnosis/FaultTreeEditor.vue'), meta: { title: '故障树编辑器', icon: 'Edit', hidden: true } }
            ]
          },
          { path: 'drift', name: 'StrategyDrift', redirect: '/collection/drift' }
        ]
      },

      // 系统管理
      {
        path: 'system',
        name: 'System',
        redirect: '/system/users',
        meta: { title: '系统管理', icon: 'Setting' },
        children: [
          { path: 'users', name: 'UserManagement', component: () => import('@/views/system/user.vue'), meta: { title: '用户管理', icon: 'User' } },
          { path: 'sites', name: 'SiteManagement', component: () => import('@/views/system/sites.vue'), meta: { title: '站点管理', icon: 'OfficeBuilding' } },
          { path: 'audit-log', name: 'AuditLog', component: () => import('@/views/system/audit-log.vue'), meta: { title: '操作审计', icon: 'Document' } },
          { path: 'notification', name: 'NotificationManagement', component: () => import('@/views/system/notification.vue'), meta: { title: '通知管理', icon: 'Bell' } },
          { path: 'settings', name: 'SystemSettings', component: () => import('@/views/settings/index.vue'), meta: { title: '系统设置', icon: 'Setting' } },
          { path: 'site-selection', name: 'SiteSelection', component: () => import('@/views/topology/site-selection.vue'), meta: { title: '智能选址', icon: 'MapLocation' } }
        ]
      },

      // ══════ 旧路由兼容重定向 ══════
      { path: 'power/monitor', redirect: '/energy/monitor' },
      { path: 'power/statistics', redirect: '/energy/statistics' },
      { path: 'power/config', redirect: '/collection/power-config' },
      { path: 'energy-saving/analysis', redirect: '/energy/analysis' },
      { path: 'energy-saving/regulation', redirect: '/energy/regulation' },
      { path: 'energy-saving/execution', redirect: '/energy/execution' },
      { path: 'energy-saving', redirect: '/energy/monitor' },
      { path: 'infrastructure/asset', redirect: '/asset/list' },
      { path: 'infrastructure/cabinet', redirect: '/asset/cabinet' },
      { path: 'infrastructure/capacity', redirect: '/asset/capacity' },
      { path: 'infrastructure/spatial', redirect: '/asset/spatial' },
      { path: 'infrastructure/power-topology', redirect: '/collection/power-config' },
      { path: 'infrastructure/cooling-topology', redirect: '/collection/power-config' },
      { path: 'infrastructure/site-selection', redirect: '/system/site-selection' },
      { path: 'infrastructure/fault-impact', redirect: '/asset/capacity' },
      { path: 'infrastructure', redirect: '/asset/list' },
      { path: 'devices', redirect: '/collection/devices' },
      { path: 'datasources', redirect: '/collection/datasources' },
      { path: 'device-templates', redirect: '/collection/device-templates' },
      { path: 'device-manage', redirect: '/collection/device-manage' },
      { path: 'device-status', redirect: '/collection/device-status' },
      { path: 'history', redirect: '/operation/history' },
      { path: 'reports', redirect: '/operation/reports' },
      { path: 'settings', redirect: '/system/settings' },
      { path: 'linkage/policy', redirect: '/strategy/linkage/policy' },
      { path: 'linkage/execution', redirect: '/strategy/linkage/execution' },
      { path: 'linkage/recovery', redirect: '/strategy/linkage/recovery' },
      { path: 'linkage/timeline', redirect: '/strategy/linkage/timeline' },
      { path: 'linkage/command', redirect: '/strategy/linkage/command' },
      { path: 'linkage', redirect: '/strategy/linkage/policy' },
      { path: 'diagnosis/results', redirect: '/strategy/diagnosis/results' },
      { path: 'diagnosis/rules', redirect: '/strategy/diagnosis/rules' },
      { path: 'diagnosis', redirect: '/strategy/diagnosis/results' },
      { path: 'video/cameras', redirect: '/security/video/cameras' },
      { path: 'video/control', redirect: '/security/video/control' },
      { path: 'video/playback', redirect: '/security/video/playback' },
      { path: 'video', redirect: '/security/video/cameras' },
      { path: 'energy/config', redirect: '/collection/power-config' },
      { path: 'energy/topology', redirect: '/power/topology' },
      { path: 'capacity', name: 'CapacityRedirect', redirect: '/asset/capacity' }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const userStore = useUserStore()

  if (to.meta.requiresAuth !== false && !userStore.token) {
    next('/login')
  } else {
    next()
  }
})

export default router
